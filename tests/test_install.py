import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('heic_install', ROOT / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        config = home / '.config'
        data = home / '.local/share'
        self.shell = config / 'omarchy/shell.json'
        self.shell.parent.mkdir(parents=True)
        self.original = {'bar': {'layout': {'right': [{'id': 'custom.sysstats'}],
                                           'left': [{'id': 'workspaces'}]}},
                         'plugins': [{'id': 'custom.sysstats', 'settings': {'interval': 5}}],
                         'custom': {'untouched': True}}
        self.shell.write_text(json.dumps(self.original))
        self.addCleanup(patch.stopall)
        patch.multiple(installer, HOME=home, CONFIG=config, DATA=data,
                       BIN=home / '.local/bin', SHELL=self.shell,
                       RECORD=data / 'omarchy-heic/install.json').start()
        self.systemctl = patch.object(installer, 'systemctl').start()
        patch.object(installer.subprocess, 'check_output', return_value='timewall 2.1.0\n').start()
        patch.object(installer.subprocess, 'run').start()
        self.backend = home / 'downloaded-timewall'
        self.backend.write_bytes(b'backend fixture')

    def test_repeat_install_and_uninstall_preserve_other_configuration(self):
        installer.install(self.backend)
        installer.install(self.backend)
        cfg = json.loads(self.shell.read_text())
        self.assertEqual(cfg['custom'], self.original['custom'])
        self.assertEqual(cfg['plugins'], self.original['plugins'])
        self.assertEqual(cfg['bar']['layout']['right'].count({'id': installer.ID}), 1)
        installer.uninstall()
        self.assertEqual(json.loads(self.shell.read_text()), self.original)
        self.assertFalse((installer.BIN / 'timewall').exists())
        self.assertTrue(list(self.shell.parent.glob('shell.json.heic-backup-*')))

    def test_conflict_preflight_leaves_config_and_earlier_files_untouched(self):
        collision = installer.CONFIG / 'systemd/user/omarchy-heic.service'
        collision.parent.mkdir(parents=True)
        collision.write_text('unrelated user service')
        with self.assertRaisesRegex(RuntimeError, 'conflict'):
            installer.install(self.backend)
        self.assertEqual(collision.read_text(), 'unrelated user service')
        self.assertFalse((installer.BIN / 'omarchy-heic').exists())
        self.assertEqual(json.loads(self.shell.read_text()), self.original)
        self.systemctl.assert_not_called()

    def test_local_edits_survive_uninstall(self):
        installer.install(self.backend)
        edited = installer.CONFIG / 'omarchy/plugins' / installer.ID / 'Panel.qml'
        edited.write_text('user changes')
        with self.assertRaises(RuntimeError):
            installer.install(self.backend)
        installer.uninstall()
        self.assertEqual(edited.read_text(), 'user changes')
        self.assertIn(str(edited), json.loads(installer.RECORD.read_text())['files'])

    def test_shell_managed_setup_does_not_overwrite_git_plugin_or_bar(self):
        plugin = installer.CONFIG / 'omarchy/plugins' / installer.ID
        plugin.mkdir(parents=True)
        manifest = plugin / 'manifest.json'
        manifest.write_text('git-managed manifest')
        installer.install(self.backend, shell_managed=True)
        self.assertEqual(manifest.read_text(), 'git-managed manifest')
        self.assertEqual(json.loads(self.shell.read_text()), self.original)
        self.assertTrue((installer.BIN / 'omarchy-heic').exists())
        self.assertTrue((installer.CONFIG / 'systemd/user/omarchy-heic.service').exists())
