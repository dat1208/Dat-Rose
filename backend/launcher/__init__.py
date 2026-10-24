#!/usr/bin/env python3
"""
Launcher package
Main entry point for launcher functionality
"""

# Re-export main functions for backward compatibility
from .core.launcher import run_launcher
from .sequences.hash_check_sequence import HashCheckSequence
from .sequences.patcher_sequence import PatcherSequence
from .sequences.skin_sync_sequence import SkinSyncSequence
from .ui.update_dialog import UpdateDialog
from .update.github_client import GitHubClient
from .update.update_downloader import UpdateDownloader
from .update.update_installer import UpdateInstaller

# Re-export subpackage classes for convenience
from .update.update_sequence import UpdateSequence
from .updater import auto_update

__all__ = [
    'GitHubClient',
    'HashCheckSequence',
    'PatcherSequence',
    'SkinSyncSequence',
    'UpdateDialog',
    'UpdateDownloader',
    'UpdateInstaller',
    'UpdateSequence',
    'auto_update',
    'run_launcher',
]
