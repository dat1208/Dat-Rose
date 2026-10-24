#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Hash File Updater

Checks CommunityDragon/Data for updates to the game hash files and
downloads/combines them into hashes.game.txt.

Startup speed: Rose checked each of the 9 hash files with its own GitHub
commits API call (9 round-trips) on every launch. This version asks for the
newest commit that touched the whole hashes/lol directory (1 call) and caches
the result for HASH_CHECK_TTL_S, so an unchanged library costs one request
every few hours instead of nine on every start.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional

import requests

from config import APP_USER_AGENT, get_config_file_path
from utils.core.logging import get_logger, get_named_logger, log_success

log = get_logger()
updater_log = get_named_logger("updater", prefix="log_updater")

GITHUB_API_BASE = "https://api.github.com/repos/CommunityDragon/Data"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/CommunityDragon/Data/master"
HASHES_DIR = "hashes/lol"
HASH_FILES = [f"hashes.game.txt.{i}" for i in range(9)]
TARGET_FILE = "hashes.game.txt"

# How long a "no update" answer is trusted before asking GitHub again.
HASH_CHECK_TTL_S = 6 * 60 * 60


def get_state_file() -> Path:
    """Path to the hash updater state file."""
    return get_config_file_path().parent / "hash_updater_state.json"


def load_state() -> Dict:
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"Failed to load hash updater state: {e}")
        return {}


def save_state(state: Dict) -> None:
    state_file = get_state_file()
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        log.warning(f"Failed to save hash updater state: {e}")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": APP_USER_AGENT,
        "Accept": "application/vnd.github.v3+json",
    })
    return session


def get_directory_commit_sha(session: requests.Session) -> Optional[str]:
    """Newest commit SHA that touched hashes/lol (one API call).

    Returns None on error or rate limit.
    """
    try:
        response = session.get(
            f"{GITHUB_API_BASE}/commits",
            params={"path": HASHES_DIR, "sha": "master", "per_page": 1},
            timeout=10,
        )
        if response.status_code in (403, 429):
            log.warning("GitHub API rate limit exceeded while checking hash commits")
            return None
        response.raise_for_status()
        commits = response.json()
        if not commits:
            return None
        return commits[0]["sha"]
    except requests.RequestException as e:
        log.error(f"Failed to check hash commits: {e}")
        return None


def check_for_updates(force: bool = False) -> bool:
    """True when the hash library changed since the last download.

    Cached for HASH_CHECK_TTL_S: an unchanged library is only re-checked
    against GitHub after the TTL, not on every startup.
    """
    state = load_state()
    local_sha = state.get("sha")
    checked_at = float(state.get("checked_at") or 0)

    if (
        not force
        and local_sha
        and (time.time() - checked_at) < HASH_CHECK_TTL_S
    ):
        log.debug("Hash check skipped (cached, within TTL)")
        return False

    session = _session()
    remote_sha = get_directory_commit_sha(session)
    if remote_sha is None:
        # Cannot tell: keep what we have rather than re-download blindly
        log.warning("Could not read the hash library commit; keeping the local copy")
        return False

    state["checked_at"] = time.time()
    save_state(state)

    if not local_sha:
        log.info("No local hash state, hash files will be downloaded")
        return True

    if remote_sha != local_sha:
        log.info(f"Hash library updated: {local_sha[:8]} -> {remote_sha[:8]}")
        return True

    log.debug("Hash files are up to date")
    return False


def download_file(
    url: str,
    session: requests.Session,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Optional[bytes]:
    try:
        filename = url.split("/")[-1]
        if status_callback:
            status_callback(f"Downloading {filename}...")
        response = session.get(url, timeout=30, stream=True)
        response.raise_for_status()
        chunks = []
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
        content = b"".join(chunks)
        size_mb = len(content) / (1024 * 1024)
        updater_log.info(f"Downloaded {filename} ({size_mb:.1f} MB)")
        if status_callback:
            status_callback(f"Downloaded {filename} ({size_mb:.1f} MB)")
        return content
    except requests.RequestException as e:
        log.error(f"Failed to download {url}: {e}")
        if status_callback:
            status_callback(f"Failed to download {url.split('/')[-1]}")
        return None


def combine_hash_files(contents: list[bytes]) -> bytes:
    texts = [c.decode("utf-8") for c in contents]
    combined = "\n".join(t.rstrip("\n") for t in texts)
    if combined and not combined.endswith("\n"):
        combined += "\n"
    return combined.encode("utf-8")


def _tools_dir() -> Path:
    """Where hashes.game.txt lives (works frozen and in development)."""
    from utils.core.paths import get_tools_dir

    return get_tools_dir()


def update_hash_files(
    status_callback: Optional[Callable[[str], None]] = None,
    dev_mode: bool = False,
) -> bool:
    """Check for updates and download/combine hash files if needed.

    Returns True when the files were updated.
    """
    if dev_mode:
        log.info("Hash file update skipped (dev mode)")
        if status_callback:
            status_callback("Hash check skipped (dev mode)")
        return False

    if status_callback:
        status_callback("Checking game hashes...")

    target_path = _tools_dir() / TARGET_FILE
    target_exists = target_path.exists()

    if not check_for_updates():
        if target_exists:
            updater_log.info("Game hashes are valid (no update needed)")
            if status_callback:
                status_callback("Game hashes are valid")
            return False
        log.warning("Hash file missing on disk, forcing download")
        if status_callback:
            status_callback("Downloading game hashes...")

    session = _session()
    contents = []
    for hash_file in HASH_FILES:
        url = f"{GITHUB_RAW_BASE}/{HASHES_DIR}/{hash_file}"
        content = download_file(url, session, status_callback)
        if content is None:
            log.error(f"Failed to download {hash_file}")
            return False
        contents.append(content)

    if status_callback:
        status_callback("Merging hash files...")
    combined_content = combine_hash_files(contents)

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(combined_content)
        size_mb = len(combined_content) / (1024 * 1024)
        log_success(log, f"Successfully created {TARGET_FILE} ({size_mb:.1f} MB)", "")
    except IOError as e:
        log.error(f"Failed to write {TARGET_FILE}: {e}")
        return False

    # Record the commit we just downloaded, so the next start can skip the check
    remote_sha = get_directory_commit_sha(session)
    if remote_sha:
        save_state({"sha": remote_sha, "checked_at": time.time()})

    if status_callback:
        status_callback("Game hashes updated successfully")
    return True
