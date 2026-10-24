#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTK patcher auto-fetch

The skin overlay needs the LTK patcher (ltk_patcher_host.exe + ltk_patcher_dll.dll).
Rose made the user copy these by hand from an LTK Manager install. D-Changer
fetches them for you, in the order that touches the network least:

1. A local LTK Manager install (default install dirs, or a path from config).
2. The official LTK Manager installer from its GitHub release: downloaded,
   checksum-verified, run silently, and the two files are copied out. The
   installer is per-machine and installs to a fixed Program Files directory
   (it ignores /D=), so it is uninstalled again once the files are copied.

The patcher DLL carries an end-of-life date; the caller (injection) already
refuses builds past it, and this module replaces a stale copy when the
installed one is older than the latest release.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

from config import APP_USER_AGENT
from utils.core.logging import get_logger
from injection.tools.patcher import (
    LTK_PATCHER_DLL,
    LTK_PATCHER_HOST,
    check_ltk_patcher,
    read_dll_eol,
    read_game_build,
)

from . import sources, verify

log = get_logger()

PATCHER_FILES = (LTK_PATCHER_HOST, LTK_PATCHER_DLL)

# Where an LTK Manager install keeps the patcher, relative to its install dir.
_PATCHER_SUBDIRS = (".", "resources", "bin")

# Default LTK Manager install locations on Windows. The Tauri NSIS installer
# is per-machine and always uses the Program Files one.
_DEFAULT_INSTALL_DIRS = (
    Path(os.environ.get("PROGRAMFILES", "")) / "LTK Manager",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "LTK Manager",
    Path(os.environ.get("LOCALAPPDATA", "")) / "LTK Manager",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "LTK Manager",
)

# The installer's fixed per-machine target, used to find the files after /S.
_INSTALL_DIR = Path(os.environ.get("PROGRAMFILES", "")) / "LTK Manager"

_SILENT_INSTALL_TIMEOUT_S = 180
_SILENT_UNINSTALL_TIMEOUT_S = 120


class PatcherInstallError(RuntimeError):
    """The patcher could not be fetched or installed."""


def _patcher_in_dir(directory: Path) -> Optional[Path]:
    """The patcher host inside a directory tree, if both files are there."""
    for sub in _PATCHER_SUBDIRS:
        candidate = directory / sub
        if (candidate / LTK_PATCHER_HOST).is_file() and (candidate / LTK_PATCHER_DLL).is_file():
            return candidate
    # Fall back to a shallow search (installers nest the patcher under resources/)
    try:
        for host in directory.rglob(LTK_PATCHER_HOST):
            if (host.parent / LTK_PATCHER_DLL).is_file():
                return host.parent
    except OSError:
        pass
    return None


def find_local_patcher(extra_dirs: tuple[Path, ...] = ()) -> Optional[Path]:
    """A patcher already on this machine, from an LTK Manager install."""
    for directory in (*extra_dirs, *_DEFAULT_INSTALL_DIRS):
        if not directory or not str(directory):
            continue
        found = _patcher_in_dir(directory)
        if found:
            log.info(f"Found an LTK patcher install at {found}")
            return found
    return None


def _copy_patcher(source_dir: Path, tools_dir: Path) -> None:
    """Copy both patcher files into the tools dir."""
    tools_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    for name in PATCHER_FILES:
        shutil.copyfile(source_dir / name, tools_dir / name)


def _download_installer(url: str, expected_sha256: Optional[str], dest: Path) -> None:
    """Download the LTK Manager installer and verify it before use."""
    log.info(f"Downloading the LTK Manager installer: {url}")
    session = requests.Session()
    session.headers.update({"User-Agent": APP_USER_AGENT})
    with session.get(url, timeout=60, stream=True) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

    if not verify.verify_file(dest, expected_sha256):
        dest.unlink(missing_ok=True)
        raise PatcherInstallError("The LTK Manager installer failed its checksum check")


def _run_silent_install(installer: Path) -> None:
    """Run the NSIS installer silently.

    The Tauri installer is per-machine and installs to a fixed Program Files
    directory: it ignores /D=, so we let it use its own target and read the
    files from there.
    """
    log.info("Installing LTK Manager silently")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        [str(installer), "/S"],
        timeout=_SILENT_INSTALL_TIMEOUT_S,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        raise PatcherInstallError(f"LTK Manager installer exited with code {result.returncode}")


def _run_silent_uninstall(install_dir: Path) -> None:
    """Remove the LTK Manager install we made, keeping only the patcher files."""
    uninstaller = install_dir / "uninstall.exe"
    if not uninstaller.is_file():
        return
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(
            [str(uninstaller), "/S"],
            timeout=_SILENT_UNINSTALL_TIMEOUT_S,
            creationflags=creationflags,
        )
        log.info("Removed the LTK Manager install after copying the patcher")
    except (OSError, subprocess.SubprocessError) as e:
        log.debug(f"Could not uninstall LTK Manager after copying the patcher: {e}")


def _verifies_host(dll: Path) -> bool:
    """True when the DLL checks that its host is the official LTK Manager.

    Newer patcher DLLs refuse to overlay unless the pipe server that handed
    them the handshake is ltk-manager.exe itself ("host verification failed,
    refusing overlay"). Rose runs ltk_patcher_host.exe directly, so such a DLL
    rejects every overlay it is asked to apply. Keep the older DLL that only
    checks the game build instead of replacing it with a newer one.
    """
    try:
        return b"host verification failed" in dll.read_bytes()
    except OSError:
        return False


def fetch_patcher(tools_dir: Path, force: bool = False) -> Path:
    """Make sure tools_dir holds a usable LTK patcher; return the tools dir.

    Args:
        tools_dir: Where ltk_patcher_host.exe and ltk_patcher_dll.dll go.
        force: Replace an existing patcher even if one is present.

    Raises:
        PatcherInstallError when no patcher could be obtained.
    """
    tools_dir = Path(tools_dir)
    status = check_ltk_patcher(tools_dir)
    if not status.missing and not force:
        log.debug("LTK patcher already present")
        return tools_dir

    # 1. A local install needs no network
    local = find_local_patcher()
    if local:
        _copy_patcher(local, tools_dir)
        log.info(f"Copied the LTK patcher from {local}")
        return tools_dir

    # 2. Fetch the official installer, install it, and copy the files out
    release = sources.ltk_manager_release()
    asset = sources.ltk_manager_installer(release)
    if not asset:
        raise PatcherInstallError(
            "Could not find an LTK Manager installer release to fetch the patcher from"
        )

    url = asset.get("browser_download_url")
    expected = verify.digest_of_asset(asset)
    with tempfile.TemporaryDirectory(prefix="dchanger-ltk-") as tmp:
        installer = Path(tmp) / (asset.get("name") or "ltk-manager-setup.exe")
        _download_installer(url, expected, installer)
        _run_silent_install(installer)

    found = _patcher_in_dir(_INSTALL_DIR)
    if not found:
        raise PatcherInstallError(
            "The LTK Manager installer ran but no patcher files were found in it"
        )
    if _verifies_host(found / LTK_PATCHER_DLL):
        _run_silent_uninstall(_INSTALL_DIR)
        raise PatcherInstallError(
            f"LTK Manager {release.tag if release else ''} ships a patcher that only runs "
            "under LTK Manager itself; keep the previous patcher files".rstrip()
        )
    _copy_patcher(found, tools_dir)
    _run_silent_uninstall(_INSTALL_DIR)

    log.info(f"Installed the LTK patcher from LTK Manager {release.tag if release else ''}".rstrip())
    return tools_dir


def patcher_is_stale(tools_dir: Path, game_dir: Optional[Path] = None) -> bool:
    """True when the installed DLL refuses the game it will be used with.

    The EOL date is compared against the game executable's build timestamp, not
    against the wall clock: a DLL past its date keeps working until League
    itself updates, which is exactly what the DLL checks at runtime.

    A DLL that verifies its host is never "stale": replacing it would only get
    another host-verifying DLL that Rose cannot use.
    """
    dll = Path(tools_dir) / LTK_PATCHER_DLL
    if _verifies_host(dll):
        return False
    if game_dir is None:
        return False
    eol = read_dll_eol(dll)
    build = read_game_build(Path(game_dir))
    return eol is not None and build is not None and build > eol
