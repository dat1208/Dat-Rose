#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Failed-skins state: failures are recorded, written, and cleared on retry."""

import json
import tempfile
import unittest
from pathlib import Path

from utils.download.repo_downloader import RepoDownloader


class FailedSkinsStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "skins"
        self.target.mkdir()
        self.downloader = RepoDownloader(target_dir=self.target)

    def tearDown(self):
        self._tmp.cleanup()

    def test_failures_are_written_and_read_back(self):
        self.downloader._reset_failed_state()
        self.downloader._record_failure("skins/Ahri/103000/103000.zip", "boom")
        self.downloader._write_failed_state()

        data = json.loads(self.downloader.failed_state_file.read_text(encoding="utf-8"))
        self.assertEqual(data["files"], [{"path": "skins/Ahri/103000/103000.zip", "reason": "boom"}])

    def test_no_failures_clears_the_state_file(self):
        self.downloader.failed_state_file.write_text('{"files": [{"path": "x", "reason": "y"}]}', encoding="utf-8")
        self.downloader._reset_failed_state()
        self.downloader._write_failed_state()
        self.assertFalse(self.downloader.failed_state_file.exists())

    def test_remove_from_failed_state_drops_one_path(self):
        self.downloader.failed_state_file.write_text(
            json.dumps({"files": [
                {"path": "a", "reason": "x"},
                {"path": "b", "reason": "y"},
            ]}),
            encoding="utf-8",
        )
        self.downloader._remove_from_failed_state("a")
        data = json.loads(self.downloader.failed_state_file.read_text(encoding="utf-8"))
        self.assertEqual([f["path"] for f in data["files"]], ["b"])

    def test_remove_last_failure_deletes_the_file(self):
        self.downloader.failed_state_file.write_text(
            json.dumps({"files": [{"path": "a", "reason": "x"}]}), encoding="utf-8"
        )
        self.downloader._remove_from_failed_state("a")
        self.assertFalse(self.downloader.failed_state_file.exists())


if __name__ == "__main__":
    unittest.main()
