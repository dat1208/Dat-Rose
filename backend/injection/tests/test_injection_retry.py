import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from injection.core import injector as injector_module
from injection.core.injector import SkinInjector
from injection.mods.mod_manager import ModManager
from injection.mods.zip_resolver import ZipResolver


class InjectionRetryTests(unittest.TestCase):
    """A transient overlay failure is retried once before giving up."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        skins_dir = root / 'skins'
        self._fantome(skins_dir / '1' / '1001' / '1001.fantome')

        self.injector = SkinInjector.__new__(SkinInjector)
        self.injector.zips_dir, self.injector.classic_dir = skins_dir, skins_dir
        self.injector.zip_resolver = ZipResolver(skins_dir)
        self.injector.classic_resolver = ZipResolver(skins_dir)
        self.injector.mod_manager = ModManager(root / 'mods')
        self.injector.game_dir, self.injector.mods_dir = root / 'game', root / 'mods'
        self.injector.last_injection_timing = None

        reporter = patch.object(injector_module, 'report_issue')
        reporter.start()
        self.addCleanup(reporter.stop)
        # Keep the retry backoff out of the test's runtime.
        sleeper = patch.object(injector_module.time, 'sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)

    @staticmethod
    def _fantome(path):
        path.parent.mkdir(parents=True)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('META/info.json', json.dumps({'Library': 'regular'}))

    def test_retries_once_after_a_failure(self):
        run_overlay = patch.object(
            SkinInjector, '_mk_run_overlay', side_effect=[1, 0]
        )
        with run_overlay as mock:
            self.assertTrue(self.injector.inject_skin('skin_1001', champion_id=1))
            self.assertEqual(mock.call_count, 2)

    def test_gives_up_after_two_failures(self):
        run_overlay = patch.object(SkinInjector, '_mk_run_overlay', return_value=1)
        with run_overlay as mock:
            self.assertFalse(self.injector.inject_skin('skin_1001', champion_id=1))
            self.assertEqual(mock.call_count, 2)

    def test_no_retry_when_stopped(self):
        run_overlay = patch.object(SkinInjector, '_mk_run_overlay', return_value=1)
        with run_overlay as mock:
            self.assertFalse(self.injector.inject_skin(
                'skin_1001', champion_id=1, stop_callback=lambda: True,
            ))
            self.assertEqual(mock.call_count, 1)

    def test_success_on_first_attempt_is_not_retried(self):
        run_overlay = patch.object(SkinInjector, '_mk_run_overlay', return_value=0)
        with run_overlay as mock:
            self.assertTrue(self.injector.inject_skin('skin_1001', champion_id=1))
            self.assertEqual(mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
