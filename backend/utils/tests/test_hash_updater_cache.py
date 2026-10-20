#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hash updater: the cached check must skip GitHub within its TTL."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.download import hash_updater


class HashCheckCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_file = Path(self._tmp.name) / "hash_updater_state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_state(self, sha, checked_at):
        self.state_file.write_text(
            json.dumps({"sha": sha, "checked_at": checked_at}), encoding="utf-8"
        )

    def test_recent_check_is_cached(self):
        """A check within the TTL must not call GitHub again."""
        self._write_state("abc123", time.time() - 60)
        with patch.object(hash_updater, "get_state_file", return_value=self.state_file), \
             patch.object(hash_updater, "get_directory_commit_sha") as api:
            self.assertFalse(hash_updater.check_for_updates())
            api.assert_not_called()

    def test_expired_check_asks_github(self):
        """Past the TTL the check runs again."""
        self._write_state("abc123", time.time() - hash_updater.HASH_CHECK_TTL_S - 1)
        with patch.object(hash_updater, "get_state_file", return_value=self.state_file), \
             patch.object(hash_updater, "get_directory_commit_sha", return_value="abc123") as api:
            self.assertFalse(hash_updater.check_for_updates())
            api.assert_called_once()

    def test_new_commit_reports_update(self):
        self._write_state("abc123", time.time() - hash_updater.HASH_CHECK_TTL_S - 1)
        with patch.object(hash_updater, "get_state_file", return_value=self.state_file), \
             patch.object(hash_updater, "get_directory_commit_sha", return_value="def456"):
            self.assertTrue(hash_updater.check_for_updates())

    def test_force_bypasses_cache(self):
        self._write_state("abc123", time.time())
        with patch.object(hash_updater, "get_state_file", return_value=self.state_file), \
             patch.object(hash_updater, "get_directory_commit_sha", return_value="abc123") as api:
            self.assertFalse(hash_updater.check_for_updates(force=True))
            api.assert_called_once()


if __name__ == "__main__":
    unittest.main()
