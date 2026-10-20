#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build D-Changer end to end.

Three stages, in order:
  1. PyInstaller builds the Python engine (backend/D-Changer.spec) into
     backend/dist/dchanger-backend/.
  2. Vite builds the React UI into ui/dist/.
  3. Tauri bundles the desktop app, taking the engine from stage 1 as its
     sidecar so the installed app is self-contained.

Rust (cargo) and Node are required for stages 2 and 3; stage 1 needs only the
Python requirements. Pass --skip-backend / --skip-ui to run a subset while
iterating.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
UI = ROOT / "ui"

MIN_PYTHON = (3, 11)
if sys.version_info < MIN_PYTHON:
    sys.stderr.write(f"D-Changer build requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+\n")
    sys.exit(1)


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(cmd)}  (in {cwd})")
    subprocess.run(cmd, cwd=cwd, check=True)


def build_backend() -> Path:
    """Build the Python engine with PyInstaller; return its output folder."""
    print("\n=== Stage 1/3: backend (PyInstaller) ===")
    _run(["pyinstaller", "--clean", "--noconfirm", "D-Changer.spec"], BACKEND)
    out = BACKEND / "dist" / "dchanger-backend"
    if not out.is_dir():
        raise SystemExit(f"backend build produced no output at {out}")
    return out


def build_ui() -> None:
    """Build the React front end with Vite."""
    print("\n=== Stage 2/3: UI (Vite) ===")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    _run([npm, "install"], UI)
    _run([npm, "run", "build"], UI)


def _stage_sidecar(backend_out: Path) -> None:
    """Copy the engine next to the Tauri binary so the shell finds its sidecar.

    Tauri's bundler picks up files named ``<name>-<target-triple>.exe`` as
    external binaries; the shell also looks for ``dchanger-backend.exe`` beside
    itself at runtime. Copying the whole PyInstaller folder keeps the engine's
    DLLs and data files together.
    """
    target = UI / "src-tauri" / "dchanger-backend"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(backend_out, target)
    print(f"[OK] Staged the engine at {target}")


def build_tauri() -> None:
    """Bundle the desktop app with Tauri."""
    print("\n=== Stage 3/3: Tauri bundle ===")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    _run([npm, "run", "tauri", "build"], UI)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build D-Changer")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument("--skip-tauri", action="store_true")
    args = parser.parse_args()

    start = time.time()
    backend_out = None
    if not args.skip_backend:
        backend_out = build_backend()
    if not args.skip_ui:
        build_ui()
    if not args.skip_tauri:
        if backend_out is None:
            backend_out = BACKEND / "dist" / "dchanger-backend"
        if backend_out.is_dir():
            _stage_sidecar(backend_out)
        build_tauri()

    elapsed = int(time.time() - start)
    print(f"\n[OK] Build finished in {elapsed // 60}m {elapsed % 60}s")


if __name__ == "__main__":
    main()
