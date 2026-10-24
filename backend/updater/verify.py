#!/usr/bin/env python3
"""
Download verification

Every file D-Changer fetches from the network is checked before it is used:
the GitHub release API publishes a SHA-256 digest per asset, so a download is
rejected unless its bytes match. This is the one place that decides whether a
downloaded file is trusted.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from utils.core.logging import get_logger

log = get_logger()

_CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str | None:
    """Hex SHA-256 of a file, or None when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK), b""):
                digest.update(chunk)
    except OSError as e:
        log.warning(f"Could not hash {path}: {e}")
        return None
    return digest.hexdigest()


def digest_of_asset(asset: dict) -> str | None:
    """The ``sha256:...`` digest GitHub reports for a release asset, if any."""
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest[len("sha256:"):].lower()
    return None


def verify_file(path: Path, expected_sha256: str | None) -> bool:
    """True when the file matches the expected digest.

    With no expected digest the file is accepted as-is (the caller decided the
    source is trusted); a wrong digest always fails.
    """
    if not path.is_file():
        log.error(f"Verification failed: {path} does not exist")
        return False
    if not expected_sha256:
        log.debug(f"No digest published for {path.name}; skipping checksum")
        return True
    actual = sha256_file(path)
    if actual is None:
        return False
    if actual.lower() != expected_sha256.lower():
        log.error(f"Checksum mismatch for {path.name}: expected {expected_sha256}, got {actual}")
        return False
    log.debug(f"Checksum OK for {path.name}")
    return True
