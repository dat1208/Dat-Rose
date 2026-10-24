import struct
import tempfile
import unittest
from pathlib import Path

from injection.tools.patcher import LtkPatcherStatus, days_of_builds_left, read_game_build

EOL = 1_791_097_200  # 2026-10-04


def write_game(game_dir: Path, build: int, name: str = "League of Legends.exe") -> None:
    """A minimal PE header carrying build as its TimeDateStamp."""
    header = bytearray(0x200)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x80)
    header[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<I", header, 0x88, build)
    (game_dir / name).write_bytes(bytes(header))


class PatcherEndOfLifeTests(unittest.TestCase):
    """The DLL compares its end of life against the game build, not today's date"""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.game_dir = Path(temp_dir.name)
        self.status = LtkPatcherStatus(host=Path(), dll=Path(), missing=[], eol=EOL)

    def test_a_game_built_before_the_end_of_life_is_supported(self):
        write_game(self.game_dir, EOL - 86400)
        self.assertFalse(self.status.expired_for(self.game_dir))

    def test_a_game_built_after_the_end_of_life_is_refused(self):
        write_game(self.game_dir, EOL + 1)
        self.assertTrue(self.status.expired_for(self.game_dir))

    def test_the_other_game_executable_name_is_read(self):
        write_game(self.game_dir, EOL + 1, "League of Legends (TM) Client.exe")
        self.assertEqual(read_game_build(self.game_dir), EOL + 1)

    def test_an_unknown_game_is_not_refused(self):
        self.assertFalse(self.status.expired_for(None))
        self.assertFalse(self.status.expired_for(self.game_dir))
        (self.game_dir / "League of Legends.exe").write_bytes(b"not a PE file")
        self.assertFalse(self.status.expired_for(self.game_dir))


class PatcherExpiryWarningTests(unittest.TestCase):
    """Rose can tell how many days of game builds the patcher still accepts."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.game_dir = Path(temp_dir.name)
        self.status = LtkPatcherStatus(host=Path(), dll=Path(), missing=[], eol=EOL)

    def test_counts_the_builds_left(self):
        write_game(self.game_dir, EOL - 86400)
        self.assertEqual(days_of_builds_left(self.status, self.game_dir), 1)

    def test_reports_zero_once_the_game_is_refused(self):
        write_game(self.game_dir, EOL + 86400)
        self.assertEqual(days_of_builds_left(self.status, self.game_dir), -1)

    def test_unknown_without_a_game(self):
        self.assertIsNone(days_of_builds_left(self.status, None))
        self.assertIsNone(days_of_builds_left(self.status, self.game_dir))


if __name__ == '__main__':
    unittest.main()
