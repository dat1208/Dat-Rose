#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Startup progress and the headless launcher dialog stand-in."""

import unittest

from startup_progress import StartupProgress


class StartupProgressTests(unittest.TestCase):
    def test_defaults(self):
        p = StartupProgress()
        snap = p.snapshot()
        self.assertFalse(snap["ready"])
        self.assertEqual(snap["progress"], 0)
        self.assertTrue(snap["marquee"])

    def test_update_fields(self):
        p = StartupProgress()
        p.update(message="Syncing skin data…", detail="42%", progress=42, marquee=False)
        snap = p.snapshot()
        self.assertEqual(snap["message"], "Syncing skin data…")
        self.assertEqual(snap["detail"], "42%")
        self.assertEqual(snap["progress"], 42)
        self.assertFalse(snap["marquee"])

    def test_progress_clamped(self):
        p = StartupProgress()
        p.update(progress=150)
        self.assertEqual(p.snapshot()["progress"], 100)
        p.update(progress=-5)
        self.assertEqual(p.snapshot()["progress"], 0)

    def test_finish(self):
        p = StartupProgress()
        p.finish()
        snap = p.snapshot()
        self.assertTrue(snap["ready"])
        self.assertEqual(snap["progress"], 100)
        self.assertFalse(snap["marquee"])

    def test_fail_records_error(self):
        p = StartupProgress()
        p.fail("boom")
        snap = p.snapshot()
        self.assertEqual(snap["error"], "boom")
        self.assertFalse(snap["marquee"])


class HeadlessDialogTests(unittest.TestCase):
    def test_forwards_to_progress(self):
        from launcher.core.launcher import _HeadlessDialog

        p = StartupProgress()
        dialog = _HeadlessDialog(p)
        dialog.set_status("Preparing the skin patcher…")
        dialog.set_progress(70)
        snap = p.snapshot()
        self.assertEqual(snap["message"], "Preparing the skin patcher…")
        self.assertEqual(snap["progress"], 70)
        self.assertFalse(snap["marquee"])

    def test_pump_messages_is_noop(self):
        from launcher.core.launcher import _HeadlessDialog

        dialog = _HeadlessDialog(StartupProgress())
        self.assertTrue(dialog.pump_messages())
        self.assertIsNone(dialog.hwnd)


if __name__ == "__main__":
    unittest.main()
