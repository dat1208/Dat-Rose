#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Profiles: save, load, delete and rename account snapshots."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.core import paths
from profiles import (
    current_profile,
    delete_profile,
    list_profiles,
    load_profile,
    rename_profile,
    save_profile,
)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # Redirect every "user data dir" lookup into the temp dir for this test.
        self._patches = [
            patch.object(paths, "_cached_user_data_dir", self.dir),
            patch.object(paths, "get_user_data_dir", return_value=self.dir),
        ]
        for p in self._patches:
            p.start()
        # config.ini lives in the temp dir too.
        self._config_patch = patch("profiles.get_config_file_path", return_value=self.dir / "config.ini")
        self._config_patch.start()

    def tearDown(self):
        self._config_patch.stop()
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def _write_state(self, name: str, data: dict) -> None:
        (self.dir / name).write_text(json.dumps(data), encoding="utf-8")

    def test_save_snapshots_state_files(self):
        self._write_state("historic.json", {"234": 234000})
        profile = save_profile("puuid-aaa", "Main")
        self.assertEqual(profile.name, "Main")
        stored = self.dir / "profiles" / "puuid-aaa" / "historic.json"
        self.assertEqual(json.loads(stored.read_text(encoding="utf-8")), {"234": 234000})

    def test_save_marks_current(self):
        save_profile("puuid-aaa", "Main")
        self.assertEqual(current_profile(), "puuid-aaa")

    def test_load_restores_state(self):
        self._write_state("historic.json", {"234": 234000})
        save_profile("puuid-aaa", "Main")
        # Change the live state, then load the profile back.
        self._write_state("historic.json", {"234": 999})
        self.assertTrue(load_profile("puuid-aaa"))
        self.assertEqual(json.loads((self.dir / "historic.json").read_text(encoding="utf-8")), {"234": 234000})

    def test_load_missing_profile_fails(self):
        self.assertFalse(load_profile("puuid-nope"))

    def test_invalid_id_rejected(self):
        for bad in ("../evil", "a/b", "", "x" * 200):
            with self.assertRaises(ValueError):
                save_profile(bad, "bad")
            self.assertFalse(load_profile(bad))
            self.assertFalse(delete_profile(bad))

    def test_delete_removes_profile(self):
        save_profile("puuid-aaa", "Main")
        self.assertTrue(delete_profile("puuid-aaa"))
        self.assertEqual(list_profiles(), [])
        self.assertIsNone(current_profile())

    def test_rename_updates_name(self):
        save_profile("puuid-aaa", "Main")
        self.assertTrue(rename_profile("puuid-aaa", "Smurf"))
        self.assertEqual(list_profiles()[0].name, "Smurf")

    def test_list_newest_first(self):
        save_profile("puuid-aaa", "First")
        save_profile("puuid-bbb", "Second")
        names = [p.name for p in list_profiles()]
        self.assertEqual(names[0], "Second")


if __name__ == "__main__":
    unittest.main()
