#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bundled path resolution in a frozen (PyInstaller onedir) install.

Three releases in a row shipped a path bug where the app looked for its
bundled files in the build machine's directory, because PyInstaller's onedir
builds set sys._MEIPASS to the builder's _internal folder. These tests pin the
contract: every bundled path comes from the running executable.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.core import paths


class FrozenPathTests(unittest.TestCase):
    """Every bundled path must resolve under the running executable."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.internal = self.root / "_internal"
        self.internal.mkdir()
        self.exe = self.root / "dchanger-backend.exe"
        self.exe.write_bytes(b"")

    def _frozen(self):
        """Patch sys so the code under test believes it is a frozen onedir build."""
        return (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(self.exe)),
            # A build machine's _MEIPASS: the app must never read from it.
            patch.object(sys, "_MEIPASS", str(Path("C:/build-machine/_internal")), create=True),
        )

    def test_bundle_dir_is_the_internal_folder(self):
        patches = self._frozen()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(paths.get_bundle_dir(), self.internal)

    def test_tools_dir_is_under_the_bundle(self):
        patches = self._frozen()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(paths.get_tools_dir(), self.internal / "injection" / "tools")

    def test_assets_dir_is_under_the_bundle(self):
        patches = self._frozen()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(paths.get_assets_dir(), self.internal / "assets")

    def test_bundle_dir_falls_back_when_internal_is_missing(self):
        """An older layout keeps the data files next to the executable."""
        self.internal.rmdir()
        patches = self._frozen()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual(paths.get_bundle_dir(), self.root)

    def test_no_bundled_path_uses_meipass(self):
        """The build machine's _MEIPASS must never leak into a resolved path."""
        patches = self._frozen()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        for resolved in (paths.get_bundle_dir(), paths.get_tools_dir(), paths.get_assets_dir()):
            self.assertNotIn("build-machine", str(resolved))


class InjectionToolsPathTests(unittest.TestCase):
    """The injection code must agree with get_tools_dir()."""

    def test_injector_and_manager_use_the_shared_resolver(self):
        """No module may read sys._MEIPASS in code (comments may mention it)."""
        import ast

        from injection.core import injector, manager

        for module in (injector, manager):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "_MEIPASS":
                    self.fail(f"{module.__name__} reads sys._MEIPASS at line {node.lineno}")


if __name__ == "__main__":
    unittest.main()
