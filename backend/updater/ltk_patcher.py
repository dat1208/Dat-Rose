#!/usr/bin/env python3
"""
LTK patcher auto-fetch

The skin overlay needs the LTK patcher (ltk_patcher_host.exe + ltk_patcher_dll.dll).
Rose made the user copy these by hand from an LTK Manager install. D-Changer
fetches them straight from a pinned commit of the LTK Manager repository, the
same way ame (github.com/hoangvu12/ame) builds its runtime: no installer is
downloaded or run, and nothing is installed on the machine.

Both files are pinned by commit, SHA-256 and size in PIN below. A download is
written to a temp file next to its target, checked against the pin (and, on
Windows, against its Authenticode signature), and only then moved into place,
so a failed fetch never replaces a working pair.

The patcher DLL carries an end-of-life date; the caller (injection) already
refuses builds past it, and this module replaces a stale copy when the
installed one is older than the game.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from config import APP_USER_AGENT
from injection.tools.patcher import (
    LTK_PATCHER_DLL,
    LTK_PATCHER_HOST,
    read_dll_eol,
    read_game_build,
)
from utils.core.logging import get_logger

from . import verify

log = get_logger()

PATCHER_FILES = (LTK_PATCHER_HOST, LTK_PATCHER_DLL)

# The one place the patcher binaries are pinned. Update all three fields per
# file together, after re-downloading the commit and re-hashing it by hand.
#
# Pinned to 08468a32, not to the newest commit. From 46198022 onward the DLL
# checks the process that started the game against a hardcoded allowlist
# (ltk_patcher_host.exe, ltk-manager.exe, explorer.exe) and refuses the overlay
# with "host verification failed, refusing overlay: [VRF00000008]" when the
# parent is anything else. D-Changer's engine spawns the host itself, so the
# parent is dchanger-backend.exe, which is not on that list: every injection
# with a newer DLL fails and the game runs with the stock skin. This pair has
# no such check and is what Rose itself ships.
#
# The cost: this DLL's built-in end-of-life date is 2026-10-18, already past.
# It still works until League ships a build newer than that date, at which
# point injection stops and the pin has to move to a DLL that accepts a
# D-Changer host.
PIN_COMMIT = "08468a32392f43dc604ebf7a8fcaf05c2bbeacb9"
PIN_DIR = "src-tauri/resources"
PIN = {
    LTK_PATCHER_HOST: (
        "23fa1aaeda1a0c743da44227f179084e1fb81c7cd262144a3c8604ffc49d3bc1",
        1238272,
    ),
    LTK_PATCHER_DLL: (
        "6d419057e6667994ba752ad0fb089b363db98267618644d7f7b6632441a21d74",
        764160,
    ),
}

_RAW = "https://raw.githubusercontent.com/LeagueToolkit/ltk-manager/{commit}/{path}"


class PatcherInstallError(RuntimeError):
    """The patcher could not be fetched or installed."""


@dataclass(frozen=True)
class _Download:
    """A verified download, ready to be moved into the tools dir."""
    name: str
    temp: Path
    target: Path


def _download(name: str, dest: Path) -> _Download:
    """Download one pinned file to a temp file beside dest and verify it."""
    sha256, size = PIN[name]
    url = _RAW.format(commit=PIN_COMMIT, path=f"{PIN_DIR}/{name}")
    log.info(f"Downloading {name}: {url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".part", dir=dest.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            session = requests.Session()
            session.headers.update({"User-Agent": APP_USER_AGENT})
            with session.get(url, timeout=60, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        if tmp.stat().st_size != size:
            raise PatcherInstallError(
                f"{name} is {tmp.stat().st_size} bytes, expected {size}"
            )
        if not verify.verify_file(tmp, sha256):
            raise PatcherInstallError(f"{name} failed its checksum check")
        _require_valid_signature(tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return _Download(name=name, temp=tmp, target=dest)


def _require_valid_signature(path: Path) -> None:
    """Reject a file whose Authenticode signature is not Valid (Windows only).

    Non-Windows hosts cannot check Authenticode; the pinned SHA-256 still
    covers the bytes, so the check is skipped there.
    """
    if sys.platform != "win32":
        return
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:DCHANGER_SIGNED_FILE;"
        "Write-Output $s.Status"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "DCHANGER_SIGNED_FILE": str(path)},
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise PatcherInstallError(f"Could not check the signature of {path.name}: {e}") from e
    status = result.stdout.strip()
    if status != "Valid":
        raise PatcherInstallError(
            f"{path.name} has no valid Authenticode signature ({status or 'no status'})"
        )


def _install(downloads: list[_Download]) -> None:
    """Move verified downloads into place, one os.replace per file."""
    for item in downloads:
        os.replace(item.temp, item.target)
        log.debug(f"Installed {item.name}")


def _discard(downloads: list[_Download]) -> None:
    for item in downloads:
        item.temp.unlink(missing_ok=True)


def _verifies_host(dll: Path) -> bool:
    """True when the DLL carries the host-verification refusal message.

    Only logged. The pinned DLL has no such check, so a True here means the
    file is not the pinned one; the pin comparison is what decides whether it
    is replaced, never this.
    """
    try:
        return b"host verification failed" in dll.read_bytes()
    except OSError:
        return False


def _matches_pin(path: Path, name: str) -> bool:
    """True when path is exactly the pinned file for name."""
    sha256, size = PIN[name]
    try:
        if not path.is_file() or path.stat().st_size != size:
            return False
    except OSError:
        return False
    return verify.verify_file(path, sha256)


def fetch_patcher(tools_dir: Path, force: bool = False) -> Path:
    """Make sure tools_dir holds a usable LTK patcher; return the tools dir.

    The installed pair is compared against the pin, not merely checked for
    presence: a copy left by an older build (or by the LTK Manager installer
    this module used to run) has a different hash and is replaced, so an
    existing install is upgraded instead of being kept forever.

    Args:
        tools_dir: Where ltk_patcher_host.exe and ltk_patcher_dll.dll go.
        force: Replace an existing patcher even if it already matches the pin.

    Raises:
        PatcherInstallError when the pinned pair could not be fetched and
        verified; the existing files are left untouched in that case.
    """
    tools_dir = Path(tools_dir)
    if not force and all(_matches_pin(tools_dir / n, n) for n in PATCHER_FILES):
        log.debug("LTK patcher already matches the pin")
        return tools_dir

    downloads: list[_Download] = []
    try:
        for name in PATCHER_FILES:
            downloads.append(_download(name, tools_dir / name))
        _install(downloads)
    except BaseException:
        _discard(downloads)
        raise

    if _verifies_host(tools_dir / LTK_PATCHER_DLL):
        log.warning(
            "The installed LTK patcher DLL carries a host verification check; "
            "it will refuse the overlay when D-Changer starts the game. The pin "
            "is a pair without that check, so check PIN_COMMIT"
        )
    log.info(f"Installed the LTK patcher from {PIN_COMMIT[:10]}")
    return tools_dir


def patcher_is_stale(tools_dir: Path, game_dir: Path | None = None) -> bool:
    """True when the installed DLL refuses the game it will be used with.

    The EOL date is compared against the game executable's build timestamp, not
    against the wall clock: a DLL past its date keeps working until League
    itself updates, which is exactly what the DLL checks at runtime.
    """
    if game_dir is None:
        return False
    eol = read_dll_eol(Path(tools_dir) / LTK_PATCHER_DLL)
    build = read_game_build(Path(game_dir))
    return eol is not None and build is not None and build > eol
