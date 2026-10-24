"""
GitHub Client
Handles GitHub API interactions for release checking
"""

from __future__ import annotations

import requests

from utils.core.logging import get_logger

log = get_logger()

# The self-update channel is configured in config.py. It stays off while
# SELF_UPDATE_ENABLED is False or no repository is set, so a fork is never
# replaced by the upstream Rose release.
from config import SELF_UPDATE_ENABLED, SELF_UPDATE_REPO

GITHUB_RELEASE_API = (
    f"https://api.github.com/repos/{SELF_UPDATE_REPO}/releases/latest"
    if SELF_UPDATE_ENABLED and SELF_UPDATE_REPO
    else ""
)


def self_update_enabled() -> bool:
    """Whether a self-update release channel is configured."""
    return bool(GITHUB_RELEASE_API)


class GitHubClient:
    """Client for interacting with GitHub API"""
    
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
    
    def get_latest_release(self) -> dict | None:
        """Get the latest release information from GitHub
        
        Returns:
            Release data dictionary or None if failed
        """
        if not GITHUB_RELEASE_API:
            return None
        try:
            response = requests.get(GITHUB_RELEASE_API, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # noqa: BLE001
            log.warning("Update check failed while fetching latest release: %s", e)
            return None
    
    def get_release_version(self, release: dict) -> str:
        """Extract version string from release data"""
        return release.get("tag_name") or release.get("name") or ""
    
    def get_zip_asset(self, release: dict) -> dict | None:
        """Get the ZIP asset from release data"""
        assets = release.get("assets", [])
        return next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
    
    def get_hash_asset(self, release: dict) -> dict | None:
        """Get the hash file asset from release data"""
        assets = release.get("assets", [])
        return next((a for a in assets if a.get("name", "").lower() == "hashes.game.txt"), None)

