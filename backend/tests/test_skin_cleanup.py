#!/usr/bin/env python3
"""Skin cleanup only removes files the library itself wrote."""

import tempfile
import unittest
from pathlib import Path

from utils.download.repo_downloader import _is_library_file


class LibraryFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepts_library_layout(self):
        for rel in (
            "1/1001/1001.zip",
            "1/1001/1001.fantome",
            "1/1001/1001.png",
            "1/1001/1001001/1001001.zip",
            "1/1001/1001001/1001001.png",
        ):
            self.assertTrue(_is_library_file(self.root / rel, self.root), rel)

    def test_rejects_user_files(self):
        for rel in (
            "my-skin.zip",                    # user archive at the root
            "1/my-skin.zip",                  # user archive in a champion dir
            "1/1001/my-skin.zip",             # user archive beside a skin
            "1/1001/1001.zip.bak",            # wrong extension
            "1/1001/notes.txt",               # not a skin file
            "failed_skins.json",              # app state, not a skin
            "1/1001/1001/1001/1001.zip",      # too deep
        ):
            self.assertFalse(_is_library_file(self.root / rel, self.root), rel)

    def test_rejects_path_outside_root(self):
        self.assertFalse(_is_library_file(Path("C:/elsewhere/1/1001/1001.zip"), self.root))


if __name__ == "__main__":
    unittest.main()
