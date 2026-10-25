#!/usr/bin/env python3
"""
Patcher Sequence

Makes sure the LTK patcher is present before the app starts. Rose asked the
user to copy ltk_patcher_host.exe and ltk_patcher_dll.dll by hand; D-Changer
fetches them from a pinned LTK Manager commit and verifies them.

Never fatal: if the patcher cannot be obtained (offline, bad download), startup
continues and the injection system reports the missing files when it needs
them.
"""

from __future__ import annotations

import time
from pathlib import Path

from injection.tools.patcher import LTK_PATCHER_DLL, read_dll_eol, read_game_build
from updater import ltk_patcher
from utils.core.issue_reporter import report_issue
from utils.core.logging import get_logger, get_named_logger

log = get_logger()
updater_log = get_named_logger("updater", prefix="log_updater")


def _tools_dir() -> Path:
    """The injection tools directory (same resolution as the engine)."""
    from utils.core.paths import get_tools_dir

    return get_tools_dir()


def _game_dir():
    """The League game folder from config, or None when it is not set yet."""
    try:
        from config import get_config_option

        path = get_config_option("General", "leaguePath")
        return Path(path) if path else None
    except Exception:  # noqa: BLE001
        return None


def _warn_if_expired(tools_dir: Path, game_dir: Path | None) -> None:
    """Report an expired patcher at startup, before an injection can fail.

    Without this the user only learns the DLL is too old when a game loads with
    the stock skin. The DLL's end-of-life date is fixed at build time, so the
    only fix is a newer pin; say so instead of leaving it to the log.
    """
    if game_dir is None:
        return
    eol = read_dll_eol(tools_dir / LTK_PATCHER_DLL)
    build = read_game_build(game_dir)
    if eol is None or build is None or build <= eol:
        return

    eol_s = time.strftime("%Y-%m-%d", time.gmtime(eol))
    build_s = time.strftime("%Y-%m-%d", time.gmtime(build))
    updater_log.warning(
        f"The LTK patcher expired for this game build (EOL {eol_s}, game {build_s}); "
        "injection will not work until the pin is updated"
    )
    report_issue(
        "LTK_PATCHER_EOL",
        "error",
        f"The LTK patcher expired on {eol_s}, and this game build is from {build_s}.",
        hint="Injection will not work until D-Changer ships a newer patcher. "
             "Update the app; if it is already current, report it with rose_*.log.",
    )


class PatcherSequence:
    """Ensures the LTK patcher is available before the app starts."""

    def perform_patcher_setup(self, dialog, dev_mode: bool = False) -> bool:
        """Fetch the LTK patcher if it is missing or stale.

        Returns True when a patcher is in place afterwards.

        Unlike the update/hash/skin steps, this one runs in dev mode too: the
        patcher is what makes injection possible at all, and fetching it is the
        whole point of the auto-setup. It stays non-fatal when it fails.
        """
        dialog.clear_transfer_text()
        dialog.set_detail("Preparing the skin patcher...")
        dialog.set_status("Checking the LTK patcher...")
        dialog.set_marquee(True)
        dialog.pump_messages()

        tools_dir = _tools_dir()
        try:
            game_dir = _game_dir()
            force = ltk_patcher.patcher_is_stale(tools_dir, game_dir)
            if force:
                dialog.set_status("Updating the LTK patcher...")
                dialog.pump_messages()
            ltk_patcher.fetch_patcher(tools_dir, force=force)
            _warn_if_expired(tools_dir, game_dir)
            updater_log.info("LTK patcher is ready.")
            dialog.set_status("Skin patcher ready.")
            dialog.set_marquee(False)
            dialog.pump_messages()
            return True
        except ltk_patcher.PatcherInstallError as exc:
            log.warning(f"LTK patcher could not be prepared: {exc}")
            updater_log.warning(f"LTK patcher setup failed: {exc}")
            dialog.set_status("Skin patcher unavailable - injection needs it later")
            dialog.set_marquee(False)
            dialog.pump_messages()
            return False
        except Exception as exc:
            log.exception("Unexpected error while preparing the LTK patcher")
            updater_log.warning(f"Patcher setup error: {exc}")
            dialog.set_status("Skin patcher check failed - continuing")
            dialog.set_marquee(False)
            dialog.pump_messages()
            return False
