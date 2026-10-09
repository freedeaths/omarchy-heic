import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('OMARCHY_HEIC_TIMEWALL') and shutil.which('heif-enc'),
                     'Real timewall backend required')
class SocketIntegrationTests(unittest.TestCase):
    def test_import_schedule_manual_pause_and_restart(self):
        from heic_factory import create
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.update({f'XDG_{name}_HOME': str(root / name.lower())
                        for name in ('CONFIG', 'DATA', 'STATE', 'CACHE')})
            env['XDG_RUNTIME_DIR'] = str(root / 'run')
            command_dir = root / 'bin'
            command_dir.mkdir()
            env['PATH'] = str(command_dir) + os.pathsep + env['PATH']
            # Exercise IPC/backend/process behavior without changing the user's desktop.
            fake = command_dir / 'omarchy'
            fake.write_text(f'#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n'
                'assert sys.argv[1:4] == ["theme","bg","set"]\n'
                'p=Path(os.environ["XDG_STATE_HOME"])/"omarchy/current/background"\n'
                'p.unlink(missing_ok=True)\np.symlink_to(sys.argv[4])\n')
            fake.chmod(0o755)
            current = root / 'state/omarchy/current'
            current.mkdir(parents=True)
            old = root / 'old.png'
            old.touch()
            background = current / 'background'
            background.symlink_to(old)
            (current / 'theme.name').write_text('test')
            cli = [sys.executable, str(ROOT / 'bin/omarchy-heic')]
            socket = root / 'run/omarchy-heic/control.sock'

            def command(*args):
                result = subprocess.run([*cli, *args], env=env, capture_output=True,
                                        text=True, timeout=20, check=True)
                return json.loads(result.stdout)

            def wait_for(predicate):
                deadline = time.monotonic() + 10
                while not predicate():
                    if time.monotonic() > deadline:
                        self.fail('Controller did not reach the expected state')
                    time.sleep(0.05)

            def start():
                daemon = subprocess.Popen([*cli, 'daemon'], env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                def cleanup():
                    if daemon.poll() is None:
                        daemon.terminate()
                        daemon.wait(timeout=10)
                self.addCleanup(cleanup)
                wait_for(socket.exists)
                self.assertEqual(socket.stat().st_mode & 0o777, 0o600)
                return daemon

            daemon = start()
            try:
                source = create(root / 'fixture', 'appearance')
                imported = command('import', str(source))
                self.assertEqual(imported['mode'], 'disabled')
                command('enable')
                wait_for(lambda: background.resolve() != old)
                self.assertTrue(background.resolve().is_file())
                background.unlink()
                background.symlink_to(old)
                wait_for(lambda: command('status')['mode'] == 'paused')
                daemon.terminate()
                daemon.wait(timeout=10)
                daemon = start()
                self.assertEqual(command('status')['mode'], 'paused')
                command('disable')
                self.assertEqual(background.resolve(), old)
            finally:
                daemon.terminate()
                daemon.wait(timeout=10)
            self.assertFalse(socket.exists())
