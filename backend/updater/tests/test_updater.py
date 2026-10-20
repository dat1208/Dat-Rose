#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Updater: download verification and patcher discovery."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from updater import ltk_patcher, verify


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _file(self, name, data: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_matching_digest_passes(self):
        data = b"patcher bytes"
        path = self._file("host.exe", data)
        self.assertTrue(verify.verify_file(path, hashlib.sha256(data).hexdigest()))

    def test_wrong_digest_fails(self):
        path = self._file("host.exe", b"tampered")
        self.assertFalse(verify.verify_file(path, "00" * 32))

    def test_no_digest_is_accepted(self):
        path = self._file("host.exe", b"anything")
        self.assertTrue(verify.verify_file(path, None))

    def test_missing_file_fails(self):
        self.assertFalse(verify.verify_file(self.dir / "nope.exe", "00" * 32))

    def test_digest_of_asset(self):
        self.assertEqual(
            verify.digest_of_asset({"digest": "sha256:ABCDEF"}),
            "abcdef",
        )
        self.assertIsNone(verify.digest_of_asset({"digest": None}))
        self.assertIsNone(verify.digest_of_asset({}))


class PatcherDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_patcher(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ltk_patcher.LTK_PATCHER_HOST).write_bytes(b"host")
        (directory / ltk_patcher.LTK_PATCHER_DLL).write_bytes(b"dll")
        return directory

    def test_finds_patcher_at_root(self):
        self._make_patcher(self.dir)
        self.assertEqual(ltk_patcher._patcher_in_dir(self.dir), self.dir)

    def test_finds_patcher_nested(self):
        nested = self.dir / "resources" / "deep"
        self._make_patcher(nested)
        self.assertEqual(ltk_patcher._patcher_in_dir(self.dir), nested)

    def test_none_when_absent(self):
        self.assertIsNone(ltk_patcher._patcher_in_dir(self.dir))

    def test_fetch_copies_from_local_install(self):
        local = self._make_patcher(self.dir / "ltk-install")
        tools = self.dir / "tools"
        with patch.object(ltk_patcher, "find_local_patcher", return_value=local):
            ltk_patcher.fetch_patcher(tools)
        self.assertTrue((tools / ltk_patcher.LTK_PATCHER_HOST).is_file())
        self.assertTrue((tools / ltk_patcher.LTK_PATCHER_DLL).is_file())

    def test_fetch_skips_when_present(self):
        tools = self._make_patcher(self.dir / "tools")
        with patch.object(ltk_patcher, "find_local_patcher") as finder:
            ltk_patcher.fetch_patcher(tools)
            finder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
