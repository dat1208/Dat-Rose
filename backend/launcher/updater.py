"""Launcher auto-update logic for Rose.

Downloads the latest release ZIP from GitHub, stages it under the
user data directory, and replaces the current installation when running
as a frozen executable.
"""

from __future__ import annotations

from collections.abc import Callable

from .update.update_sequence import UpdateSequence


# Backward compatibility - maintain the auto_update function signature
def auto_update(
    status_callback: Callable[[str], None],
    progress_callback: Callable[[int], None],
    bytes_callback: Callable[[int, int | None], None] | None = None,
    confirm_callback: Callable[[str, str], bool] | None = None,
) -> bool:
    """Download and install the latest release if a new version is available.

    Returns True when an update was installed, False otherwise.
    """
    sequence = UpdateSequence()
    return sequence.perform_update(
        status_callback,
        progress_callback,
        bytes_callback,
        confirm_callback=confirm_callback,
    )
