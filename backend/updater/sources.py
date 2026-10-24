#!/usr/bin/env python3
"""
Upstream sources

One place that knows where every external piece of D-Changer comes from and
how to ask each one for its latest version. Used by the updater to keep the
app, the skin library, Pengu Loader and the LTK patcher current.

All of these are public GitHub repositories; every request carries the app's
User-Agent and is read-only.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from config import APP_USER_AGENT
from utils.core.logging import get_logger

log = get_logger()

_API = "https://api.github.com"


@dataclass(frozen=True)
class Release:
    """A GitHub release's tag and its downloadable assets."""
    tag: str
    assets: tuple[dict, ...]

    def asset(self, predicate) -> dict | None:
        return next((a for a in self.assets if predicate(a)), None)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": APP_USER_AGENT,
        "Accept": "application/vnd.github.v3+json",
    })
    return session


def latest_release(repo: str, timeout: int = 20) -> Release | None:
    """Latest release of owner/name, or None when it cannot be read."""
    try:
        response = _session().get(f"{_API}/repos/{repo}/releases/latest", timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return Release(tag=data.get("tag_name") or data.get("name") or "", assets=tuple(data.get("assets", ())))
    except requests.RequestException as e:
        log.warning(f"Could not read the latest release of {repo}: {e}")
        return None


def latest_commit_sha(repo: str, path: str = "", branch: str = "main", timeout: int = 15) -> str | None:
    """Newest commit SHA of owner/name (optionally under a path)."""
    params = {"sha": branch, "per_page": 1}
    if path:
        params["path"] = path
    try:
        response = _session().get(f"{_API}/repos/{repo}/commits", params=params, timeout=timeout)
        response.raise_for_status()
        commits = response.json()
        return commits[0]["sha"] if commits else None
    except (requests.RequestException, KeyError, IndexError) as e:
        log.warning(f"Could not read the latest commit of {repo}: {e}")
        return None


# ── The sources D-Changer tracks ────────────────────────────────────────────

LTK_MANAGER_REPO = "LeagueToolkit/ltk-manager"
LEAGUE_SKINS_REPO = "Alban1911/LeagueSkins"
PENGU_LOADER_REPO = "PenguLoader/PenguLoader"
ROSE_REPO = "Alban1911/Rose"


def ltk_manager_release() -> Release | None:
    """LTK Manager, which ships the patcher D-Changer extracts."""
    return latest_release(LTK_MANAGER_REPO)


def ltk_manager_installer(release: Release | None) -> dict | None:
    """The Windows installer asset of an LTK Manager release."""
    if not release:
        return None
    return release.asset(
        lambda a: a.get("name", "").lower().endswith(".exe")
        and "setup" in a.get("name", "").lower()
    )


def league_skins_sha() -> str | None:
    """Current commit of the skin library."""
    return latest_commit_sha(LEAGUE_SKINS_REPO, branch="main")


def pengu_loader_release() -> Release | None:
    return latest_release(PENGU_LOADER_REPO)


def rose_release() -> Release | None:
    """Upstream Rose, tracked to notice new engine work worth porting."""
    return latest_release(ROSE_REPO)
