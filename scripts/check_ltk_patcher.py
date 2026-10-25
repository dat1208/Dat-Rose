#!/usr/bin/env python3
"""Check whether LeagueToolkit/ltk-manager ships a patcher pair we can use.

The patcher is pinned by hand in backend/updater/ltk_patcher.py. A newer DLL is
only usable when it is Authenticode-signed and does not carry the host
verification check, which refuses D-Changer as the process that started the
game. This script walks the commits that touched src-tauri/resources, downloads
each DLL, and reports the newest one that passes both tests and has a later
end-of-life date than the pinned one.

Run by .github/workflows/ltk-patcher-watch.yml on a schedule. Exit code 0 means
"nothing to do"; 1 means a better pair exists and the pin should be updated.

Usage:
    python scripts/check_ltk_patcher.py [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = "LeagueToolkit/ltk-manager"
RESOURCES = "src-tauri/resources"
DLL = "ltk_patcher_dll.dll"
HOST = "ltk_patcher_host.exe"

ROOT = Path(__file__).resolve().parent.parent
PIN_FILE = ROOT / "backend" / "updater" / "ltk_patcher.py"

sys.path.insert(0, str(ROOT / "backend"))

from injection.tools.patcher import read_dll_eol

# The DLL prints this when it refuses a host that is not on its allowlist
HOST_CHECK_MARKER = b"host verification failed"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "D-Changer-patcher-watch"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _api(path: str) -> object:
    return json.loads(_get(f"https://api.github.com/repos/{REPO}/{path}"))


def _raw(commit: str, name: str) -> bytes:
    return _get(f"https://raw.githubusercontent.com/{REPO}/{commit}/{RESOURCES}/{name}")


def _pinned() -> tuple[str, str, int]:
    """(commit, dll sha256, dll size) from the pin table."""
    text = PIN_FILE.read_text(encoding="utf-8")
    commit = re.search(r'PIN_COMMIT = "([0-9a-f]{40})"', text)
    dll = re.search(r'LTK_PATCHER_DLL: \(\s*"([0-9a-f]{64})",\s*(\d+),', text)
    if not commit or not dll:
        raise SystemExit(f"could not read the pin from {PIN_FILE}")
    return commit.group(1), dll.group(1), int(dll.group(2))


def is_signed(path: Path) -> bool:
    """True when Windows reports a valid Authenticode signature."""
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:PATCHER_FILE;"
        "Write-Output $s.Status"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "PATCHER_FILE": str(path)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return result.stdout.strip() == "Valid"


def candidates() -> list[str]:
    """Commits that touched the resources folder, newest first."""
    return [c["sha"] for c in _api(f"commits?path={RESOURCES}&per_page=30")]


def evaluate(commit: str, workdir: Path) -> dict | None:
    """Download and test one commit's pair. None when it cannot be used."""
    try:
        dll = _raw(commit, DLL)
    except OSError as e:
        print(f"  {commit[:10]}: no DLL at this commit ({e})")
        return None

    if HOST_CHECK_MARKER in dll:
        print(f"  {commit[:10]}: has the host verification check, unusable")
        return None

    path = workdir / f"{commit}.dll"
    path.write_bytes(dll)
    eol = read_dll_eol(path)
    if eol is None:
        print(f"  {commit[:10]}: no end-of-life date found, unusable")
        return None

    if not is_signed(path):
        print(f"  {commit[:10]}: not Authenticode-signed, unusable")
        return None

    try:
        host = _raw(commit, HOST)
    except OSError as e:
        print(f"  {commit[:10]}: no host at this commit ({e})")
        return None

    print(f"  {commit[:10]}: usable, EOL {eol}")
    return {
        "commit": commit,
        "dll_sha256": hashlib.sha256(dll).hexdigest(),
        "dll_size": len(dll),
        "host_sha256": hashlib.sha256(host).hexdigest(),
        "host_size": len(host),
        "eol": eol,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PATH", help="write the result as JSON to PATH")
    args = parser.parse_args()

    pinned_commit, _, pinned_size = _pinned()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        pinned_path = workdir / "pinned.dll"
        pinned_path.write_bytes(_raw(pinned_commit, DLL))
        pinned_eol = read_dll_eol(pinned_path)
    print(f"pinned: {pinned_commit[:10]} ({pinned_size} bytes), EOL {pinned_eol}")
    if pinned_eol is None:
        raise SystemExit("could not read the end-of-life date of the pinned DLL")

    print("checking commits that touched the resources folder:")
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for commit in candidates():
            if commit == pinned_commit:
                continue
            result = evaluate(commit, workdir)
            if result and result["eol"] > pinned_eol:
                result["pinned_commit"] = pinned_commit
                result["pinned_eol"] = pinned_eol
                if args.json:
                    Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(
                    f"\nA better pair exists: {result['commit']}\n"
                    f"  host sha256: {result['host_sha256']}  ({result['host_size']} bytes)\n"
                    f"  dll  sha256: {result['dll_sha256']}  ({result['dll_size']} bytes)\n"
                    f"  EOL:         {result['eol']} (pinned {pinned_eol})\n"
                    "Update PIN_COMMIT and both hashes in "
                    "backend/updater/ltk_patcher.py, then test an injection."
                )
                return 1

    print("\nNo usable pair newer than the pin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
