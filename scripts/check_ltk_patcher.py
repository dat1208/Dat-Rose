#!/usr/bin/env python3
"""Check whether LeagueToolkit/ltk-manager ships a patcher pair we can use.

The patcher is pinned by hand in backend/updater/ltk_patcher.py. A newer DLL is
only usable when it is Authenticode-signed and does not carry the host
verification check, which refuses D-Changer as the process that started the
game. This script walks the commits that touched src-tauri/resources, downloads
each DLL, and reports the newest one that passes both tests and has a later
end-of-life date than the pinned one. A commit that ships no host binary of
its own is tested with the pinned host, since the host has not changed since
08468a32.

It also reports the pin itself when its end-of-life date is close, because the
pinned DLL refuses game builds newer than that date and injection stops until
a replacement is found.

Run by .github/workflows/ltk-patcher-watch.yml on a schedule. Exit code 0 means
"nothing to do"; 1 means a better DLL exists or the pin is about to expire, and`nthe pin should be updated.

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
import time
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


def _pinned() -> tuple[str, str, int, str, int]:
    """(commit, dll sha256, dll size, host sha256, host size) from the pin table."""
    text = PIN_FILE.read_text(encoding="utf-8")
    commit = re.search(r'PIN_COMMIT = "([0-9a-f]{40})"', text)
    dll = re.search(r'LTK_PATCHER_DLL: \(\s*"([0-9a-f]{64})",\s*(\d+),', text)
    host = re.search(r'LTK_PATCHER_HOST: \(\s*"([0-9a-f]{64})",\s*(\d+),', text)
    if not commit or not dll or not host:
        raise SystemExit(f"could not read the pin from {PIN_FILE}")
    return (
        commit.group(1),
        dll.group(1),
        int(dll.group(2)),
        host.group(1),
        int(host.group(2)),
    )


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


def evaluate(commit: str, workdir: Path, pinned_host: bytes) -> dict | None:
    """Download and test one commit's DLL. None when it cannot be used.

    A commit only has to ship a DLL: the host binary is unchanged since
    08468a32, so commits that only touch the DLL (46198022 is one) carry no
    host of their own and the pinned host is used with them.
    """
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
        host_source = "commit"
    except OSError:
        host = pinned_host
        host_source = "pin"

    print(f"  {commit[:10]}: usable, EOL {eol}, host from {host_source}")
    return {
        "commit": commit,
        "dll_sha256": hashlib.sha256(dll).hexdigest(),
        "dll_size": len(dll),
        "host_sha256": hashlib.sha256(host).hexdigest(),
        "host_size": len(host),
        "host_source": host_source,
        "eol": eol,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PATH", help="write the result as JSON to PATH")
    parser.add_argument(
        "--warn-days",
        type=int,
        default=14,
        help="report the pin as expiring when its EOL is this close (default 14)",
    )
    args = parser.parse_args()

    pinned_commit, _, pinned_size, _, _ = _pinned()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        pinned_path = workdir / "pinned.dll"
        pinned_dll = _raw(pinned_commit, DLL)
        pinned_path.write_bytes(pinned_dll)
        pinned_eol = read_dll_eol(pinned_path)
        pinned_host = _raw(pinned_commit, HOST)
    print(f"pinned: {pinned_commit[:10]} ({pinned_size} bytes), EOL {pinned_eol}")
    if pinned_eol is None:
        raise SystemExit("could not read the end-of-life date of the pinned DLL")

    # The pinned DLL refuses any game build newer than its EOL date, so a pin
    # that is close to expiring is worth an issue even before a replacement
    # exists: the fix takes a new DLL plus a real injection test.
    now = int(time.time())
    seconds_left = pinned_eol - now
    days_left = seconds_left // 86400
    expiring = seconds_left <= args.warn_days * 86400
    if expiring:
        when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(pinned_eol))
        if seconds_left <= 0:
            print(f"the pinned DLL expired on {when} UTC: injection is already broken")
        else:
            print(f"the pinned DLL expires in {days_left} day(s) ({when} UTC)")

    print("checking commits that touched the resources folder:")
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for commit in candidates():
            if commit == pinned_commit:
                continue
            result = evaluate(commit, workdir, pinned_host)
            if result and result["eol"] > pinned_eol:
                result["pinned_commit"] = pinned_commit
                result["pinned_eol"] = pinned_eol
                result["pinned_expiring"] = expiring
                result["pinned_days_left"] = days_left
                if args.json:
                    Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(
                    f"\nA better DLL exists: {result['commit']}\n"
                    f"  dll  sha256: {result['dll_sha256']}  ({result['dll_size']} bytes)\n"
                    f"  host sha256: {result['host_sha256']}  ({result['host_size']} bytes, "
                    f"from {result['host_source']})\n"
                    f"  EOL:         {result['eol']} (pinned {pinned_eol})\n"
                    "Update PIN_COMMIT and the DLL hash in "
                    "backend/updater/ltk_patcher.py, then test an injection."
                )
                return 1

    if expiring:
        result = {
            "pinned_commit": pinned_commit,
            "pinned_eol": pinned_eol,
            "pinned_days_left": days_left,
            "pinned_expiring": True,
        }
        if args.json:
            Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(
            "\nNo usable replacement yet, but the pinned DLL is about to expire. "
            "Injection stops once League ships a build newer than its EOL date."
        )
        return 1

    print("\nNo usable DLL newer than the pin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
