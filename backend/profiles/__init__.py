#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-account profiles

D-Changer keeps one set of skin choices per League account. Each account's
choices live in the same state files Rose already uses (historic.json,
historic_targets.json, mod_historic.json, plus the skin selection keys in
config.ini); a profile is a snapshot of those files keyed by the account's
PUUID, so switching accounts restores the right choices.

Layout under the user data dir::

    profiles/
        index.json                 # {puuid: {name, updated_at}}
        <puuid>/
            historic.json
            historic_targets.json
            mod_historic.json
            config.ini             # only the [Skin] section

The current profile is tracked in config.ini ([Profiles] current) so a restart
remembers it. All writes go through the crash-safe atomic writer.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import get_config_file_path, get_config_option, read_config_file, set_config_option, write_config_file
from utils.core.atomic_file import atomic_write
from utils.core.logging import get_logger
from utils.core.paths import get_user_data_dir

log = get_logger()

# Files that make up a profile, relative to the user data dir.
_PROFILE_FILES = ("historic.json", "historic_targets.json", "mod_historic.json")

# config.ini section holding per-account skin choices.
_SKIN_SECTION = "Skin"

# PUUIDs are UUID-like; reject anything that could escape the profiles dir.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Read-modify-write cycles run from several threads (injection, UI, bridge).
_lock = threading.RLock()


@dataclass(frozen=True)
class Profile:
    """A stored account profile."""
    puuid: str
    name: str
    updated_at: float


def _profiles_dir() -> Path:
    directory = get_user_data_dir() / "profiles"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _index_path() -> Path:
    return _profiles_dir() / "index.json"


def _profile_dir(puuid: str) -> Path:
    if not _SAFE_ID.match(puuid or ""):
        raise ValueError(f"invalid profile id: {puuid!r}")
    return _profiles_dir() / puuid


def _read_index() -> dict:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f"Could not read the profile index, starting fresh: {e}")
        return {}


def _write_index(index: dict) -> None:
    with atomic_write(_index_path()) as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)


def list_profiles() -> list[Profile]:
    """Every stored profile, newest first."""
    index = _read_index()
    profiles = [
        Profile(puuid=str(k), name=str(v.get("name", "")), updated_at=float(v.get("updated_at", 0.0)))
        for k, v in index.items()
        if isinstance(v, dict)
    ]
    return sorted(profiles, key=lambda p: p.updated_at, reverse=True)


def current_profile() -> Optional[str]:
    """PUUID of the active profile, or None."""
    value = get_config_option("Profiles", "current")
    return value or None


def _skin_section() -> dict:
    """The [Skin] section of config.ini as a plain dict."""
    import configparser

    parser = configparser.ConfigParser(interpolation=None)
    path = get_config_file_path()
    if path.exists():
        try:
            read_config_file(parser, path)
        except Exception as e:
            log.warning(f"Could not read config.ini while saving a profile: {e}")
            return {}
    if _SKIN_SECTION not in parser:
        return {}
    return dict(parser[_SKIN_SECTION])


def _write_skin_section(values: dict) -> None:
    """Replace the [Skin] section of config.ini, leaving every other section alone."""
    import configparser

    parser = configparser.ConfigParser(interpolation=None)
    path = get_config_file_path()
    if path.exists():
        try:
            read_config_file(parser, path)
        except Exception as e:
            log.warning(f"Not restoring the profile: config.ini could not be read: {e}")
            return
    if _SKIN_SECTION in parser:
        parser.remove_section(_SKIN_SECTION)
    parser.add_section(_SKIN_SECTION)
    for key, value in values.items():
        parser.set(_SKIN_SECTION, key, value)
    write_config_file(parser, path)


def save_profile(puuid: str, name: str = "") -> Profile:
    """Snapshot the current choices under ``puuid`` and mark it active."""
    if not _SAFE_ID.match(puuid or ""):
        raise ValueError(f"invalid profile id: {puuid!r}")

    with _lock:
        target = _profile_dir(puuid)
        target.mkdir(parents=True, exist_ok=True)
        data_dir = get_user_data_dir()

        for filename in _PROFILE_FILES:
            source = data_dir / filename
            if source.is_file():
                (target / filename).write_bytes(source.read_bytes())

        with atomic_write(target / "config.ini") as fh:
            json.dump(_skin_section(), fh, ensure_ascii=False, indent=2)

        index = _read_index()
        existing_name = index.get(puuid, {}).get("name", "") if isinstance(index.get(puuid), dict) else ""
        profile = Profile(puuid=puuid, name=name or existing_name or puuid[:8], updated_at=time.time())
        index[puuid] = {"name": profile.name, "updated_at": profile.updated_at}
        _write_index(index)
        set_config_option("Profiles", "current", puuid)
        log.info(f"Saved profile {profile.name} ({puuid[:8]})")
        return profile


def load_profile(puuid: str) -> bool:
    """Restore a stored profile's choices into the live state files.

    Returns False when the profile does not exist or its files cannot be read.
    """
    if not _SAFE_ID.match(puuid or ""):
        return False

    with _lock:
        source = _profile_dir(puuid)
        if not source.is_dir():
            log.warning(f"Profile {puuid[:8]} does not exist")
            return False

        data_dir = get_user_data_dir()
        for filename in _PROFILE_FILES:
            stored = source / filename
            if stored.is_file():
                (data_dir / filename).write_bytes(stored.read_bytes())

        stored_config = source / "config.ini"
        if stored_config.is_file():
            try:
                with stored_config.open("r", encoding="utf-8") as fh:
                    _write_skin_section(json.load(fh))
            except (OSError, json.JSONDecodeError) as e:
                log.warning(f"Could not restore the skin section of profile {puuid[:8]}: {e}")

        set_config_option("Profiles", "current", puuid)
        log.info(f"Loaded profile {puuid[:8]}")
        return True


def delete_profile(puuid: str) -> bool:
    """Remove a stored profile. The active profile is cleared if it was the one."""
    if not _SAFE_ID.match(puuid or ""):
        return False

    with _lock:
        target = _profile_dir(puuid)
        if not target.is_dir():
            return False
        import shutil

        shutil.rmtree(target, ignore_errors=True)
        index = _read_index()
        index.pop(puuid, None)
        _write_index(index)
        if current_profile() == puuid:
            set_config_option("Profiles", "current", "")
        log.info(f"Deleted profile {puuid[:8]}")
        return True


def rename_profile(puuid: str, name: str) -> bool:
    """Give a stored profile a new display name."""
    if not _SAFE_ID.match(puuid or "") or not name:
        return False
    with _lock:
        index = _read_index()
        if puuid not in index or not isinstance(index[puuid], dict):
            return False
        index[puuid]["name"] = name
        _write_index(index)
        return True
