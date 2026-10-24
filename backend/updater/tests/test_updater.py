#!/usr/bin/env python3
"""Updater: download verification and pinned patcher fetch."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from updater import ltk_patcher, verify

HOST = ltk_patcher.LTK_PATCHER_HOST
DLL = ltk_patcher.LTK_PATCHER_DLL

HOST_BYTES = b"pinned host bytes"
DLL_BYTES = b"pinned dll bytes"
FAKE_PIN = {
    HOST: (hashlib.sha256(HOST_BYTES).hexdigest(), len(HOST_BYTES)),
    DLL: (hashlib.sha256(DLL_BYTES).hexdigest(), len(DLL_BYTES)),
}


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=0):
        yield self._body


class _FakeSession:
    """Stands in for requests.Session; serves bodies by file name."""

    def __init__(self, bodies):
        self.bodies = bodies
        self.urls = []
        self.headers = {}

    def get(self, url, timeout=None, stream=False):
        self.urls.append(url)
        name = url.rsplit("/", 1)[-1]
        return _FakeResponse(self.bodies[name])


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


class FetchPatcherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.tools = self.dir / "tools"
        self.session = _FakeSession({HOST: HOST_BYTES, DLL: DLL_BYTES})
        for patcher in (
            patch.object(ltk_patcher, "PIN", FAKE_PIN),
            patch.object(ltk_patcher.requests, "Session", lambda: self.session),
            patch.object(ltk_patcher, "_require_valid_signature", lambda path: None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fetch_writes_both_files(self):
        ltk_patcher.fetch_patcher(self.tools)
        self.assertEqual((self.tools / HOST).read_bytes(), HOST_BYTES)
        self.assertEqual((self.tools / DLL).read_bytes(), DLL_BYTES)
        self.assertEqual(len(self.session.urls), 2)
        self.assertTrue(all(ltk_patcher.PIN_COMMIT in u for u in self.session.urls))
        self.assertEqual(list(self.tools.glob("*.part")), [])

    def test_hash_mismatch_leaves_existing_files_untouched(self):
        self.tools.mkdir(parents=True)
        (self.tools / HOST).write_bytes(b"old host")
        (self.tools / DLL).write_bytes(b"old dll")
        self.session.bodies[DLL] = b"tampered dll"

        with self.assertRaises(ltk_patcher.PatcherInstallError):
            ltk_patcher.fetch_patcher(self.tools, force=True)

        self.assertEqual((self.tools / HOST).read_bytes(), b"old host")
        self.assertEqual((self.tools / DLL).read_bytes(), b"old dll")
        self.assertEqual(list(self.tools.glob("*.part")), [])

    def test_present_pair_is_not_downloaded(self):
        self.tools.mkdir(parents=True)
        (self.tools / HOST).write_bytes(HOST_BYTES)
        (self.tools / DLL).write_bytes(DLL_BYTES)

        ltk_patcher.fetch_patcher(self.tools)

        self.assertEqual(self.session.urls, [])

    def test_force_redownloads_present_pair(self):
        self.tools.mkdir(parents=True)
        (self.tools / HOST).write_bytes(b"old host")
        (self.tools / DLL).write_bytes(b"old dll")

        ltk_patcher.fetch_patcher(self.tools, force=True)

        self.assertEqual((self.tools / HOST).read_bytes(), HOST_BYTES)
        self.assertEqual((self.tools / DLL).read_bytes(), DLL_BYTES)


if __name__ == "__main__":
    unittest.main()
