import importlib.machinery
import importlib.util
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('heic_controller', str(ROOT / 'bin/omarchy-heic'))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class FakeBackend:
    binary = 'python3'
    image = None
    failure = None
    def select(self, entry, location, appearance):
        if self.failure:
            raise RuntimeError(self.failure)
        return self.image


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {f'XDG_{name}_HOME': str(root / name.lower())
                         for name in ('CONFIG', 'DATA', 'STATE', 'CACHE')})
        self.env.start()
        self.runtime_env = patch.dict(os.environ, XDG_RUNTIME_DIR=str(root / 'run'))
        self.runtime_env.start()
        self.p = m.Paths()
        self.backend = FakeBackend()
        self.c = m.Controller(self.p, self.backend)
        self.old = root / 'old.png'; self.old.touch()
        self.image = root / 'dynamic.png'; self.image.touch()
        self.external = root / 'external.png'; self.external.touch()
        self.link(self.old)
        self.p.theme.write_text('day')
        self.c.last_theme = 'day'
        entry = self.p.data / 'library/one/metadata.json'
        m.atomic_json(entry, dict(id='one', name='test.heic', kind='time', frames=[]))
        self.c.cfg['selected'] = 'one'
        self.backend.image = str(self.image)
        self.applied = []
        def apply(image):
            self.applied.append(image)
            self.link(Path(image))
        self.c.apply = apply
        self.c.appearance = lambda: 'light'

    def tearDown(self):
        self.runtime_env.stop(); self.env.stop(); self.tmp.cleanup()

    def link(self, path):
        self.p.background.parent.mkdir(parents=True, exist_ok=True)
        self.p.background.unlink(missing_ok=True)
        self.p.background.symlink_to(path)

    def active(self):
        self.c.dispatch(dict(command='enable'))
        self.c.tick()

    def test_enable_and_disable_restore(self):
        self.active()
        self.assertEqual(self.c.background(), str(self.image))
        self.c.dispatch(dict(command='disable'))
        self.assertEqual(self.c.background(), str(self.old))

    def test_user_selection_pauses_and_is_retained(self):
        self.active(); self.link(self.external)
        self.c.tick(); self.c.mismatch_since -= 3; self.c.tick()
        self.assertEqual(self.c.state['mode'], 'paused')
        self.c.dispatch(dict(command='disable'))
        self.assertEqual(self.c.background(), str(self.external))

    def test_changed_theme_reapplies_same_frame(self):
        self.active(); self.link(self.external); self.p.theme.write_text('night')
        self.c.tick()
        self.assertEqual(self.c.state['mode'], 'active')
        self.c.theme_settling = 0; self.c.tick()
        self.assertEqual(self.c.background(), str(self.image))

    def test_same_theme_hook_reapplies(self):
        self.active(); self.link(self.external)
        self.c.dispatch(dict(command='theme-changed')); self.c.tick()
        self.c.theme_settling = 0; self.c.tick()
        self.assertEqual(self.c.background(), str(self.image))

    def test_backend_failure_does_not_replace_wallpaper(self):
        self.active(); self.backend.failure = 'bad cache'
        self.c.next_compute = 0; self.c.tick()
        self.assertEqual(self.c.background(), str(self.image))
        self.assertEqual(self.c.state['error'], 'bad cache')
        count = len(self.applied); self.c.tick()
        self.assertEqual(len(self.applied), count)

    def test_pause_and_resume(self):
        self.active(); self.c.dispatch(dict(command='pause'))
        self.link(self.external); self.c.tick()
        self.assertEqual(self.c.background(), str(self.external))
        self.c.dispatch(dict(command='resume')); self.c.tick()
        self.assertEqual(self.c.background(), str(self.image))

    def test_invalid_location_is_transactional(self):
        for lat, lon in [(91, 0), (0, 181), (float('nan'), 0), (0, float('inf'))]:
            with self.assertRaises(ValueError):
                self.c.dispatch(dict(command='location', lat=lat, lon=lon))
        self.assertIsNone(self.c.cfg['location'])

    def test_darkman_import_is_explicit(self):
        f = Path(os.environ['XDG_CONFIG_HOME']) / 'darkman/config.yaml'
        f.parent.mkdir(); f.write_text('lat: 33.59 # city\nlng: 130.40\nportal: false\n')
        self.assertIsNone(self.c.cfg['location'])
        self.c.dispatch(dict(command='import-location'))
        self.assertEqual(self.c.cfg['location'], dict(lat=33.59, lon=130.4))

    def test_solar_requires_location(self):
        e = self.p.data / 'library/one/metadata.json'
        v = json.loads(e.read_text()); v['kind'] = 'solar'; m.atomic_json(e, v)
        with self.assertRaises(ValueError):
            self.c.dispatch(dict(command='enable'))
        self.assertEqual(self.c.state['mode'], 'disabled')

    def test_same_frame_does_not_reapply(self):
        self.active(); self.c.next_compute = 0; self.c.tick()
        self.assertEqual(len(self.applied), 1)

    def test_switch_image_without_changing_frame_number(self):
        self.active(); self.backend.image = str(self.external)
        self.c.dispatch(dict(command='select', id='one')); self.c.tick()
        self.assertEqual(self.c.background(), str(self.external))

    def test_unknown_id_preserves_selection(self):
        with self.assertRaises(ValueError):
            self.c.dispatch(dict(command='select', id='missing'))
        self.assertEqual(self.c.cfg['selected'], 'one')

    def test_missing_original_keeps_last_image(self):
        self.active(); (self.p.data / 'library/one/metadata.json').unlink()
        self.c.next_compute = 0; self.c.tick()
        self.assertEqual(self.c.background(), str(self.image))
        self.assertIsNotNone(self.c.state['error'])

    def test_status_serializable(self):
        self.assertEqual(json.loads(json.dumps(self.c.status()))['mode'], 'disabled')

    def test_wallpaper_selected_during_decode_is_preserved(self):
        self.active()
        def decode(*args):
            self.link(self.external)
            return str(self.image)
        self.backend.select = decode
        self.c.next_compute = 0
        self.c.tick()
        self.assertEqual(self.c.state['mode'], 'paused')
        self.assertEqual(self.c.background(), str(self.external))

    def test_theme_changed_during_decode_defers_application(self):
        self.active()
        def decode(*args):
            self.p.theme.write_text('night')
            self.link(self.external)
            return str(self.image)
        self.backend.select = decode
        self.c.next_compute = 0
        self.c.tick()
        self.assertTrue(self.c.theme_pending)
        self.assertEqual(self.c.state['mode'], 'active')
        self.assertEqual(self.c.background(), str(self.external))

    def test_restart_does_not_steal_wallpaper_selected_while_stopped(self):
        self.active()
        self.link(self.external)
        restarted = m.Controller(self.p, self.backend)
        restarted.tick()
        restarted.mismatch_since -= 3
        restarted.tick()
        self.assertEqual(restarted.state['mode'], 'paused')
        self.assertEqual(restarted.background(), str(self.external))

    def test_resume_from_suspend_reevaluates_schedule(self):
        self.active()
        self.backend.image = str(self.external)
        self.c.last_clock = (time.time() - 100, time.monotonic())
        self.c.tick()
        self.assertEqual(self.c.background(), str(self.external))


@unittest.skipUnless(os.environ.get('OMARCHY_HEIC_TIMEWALL') and shutil.which('heif-enc'),
                     'Set OMARCHY_HEIC_TIMEWALL and install libheif tools for real HEIC tests')
class RealBackendTests(unittest.TestCase):
    def setUp(self):
        ControllerTests.setUp(self)
        self.real = m.Backend(self.p)

    tearDown = ControllerTests.tearDown
    link = ControllerTests.link

    def test_direct_time_selection_matches_upstream_at_boundaries(self):
        from heic_factory import create
        entry = self.real.inspect(create(Path(self.tmp.name) / 'parity', 'time'))
        source = self.p.data / 'library' / entry['id'] / 'wallpaper.heic'
        for clock in ('00:00:00', '03:00:00', '06:00:00', '06:00:01', '12:00:00', '18:00:00', '23:59:59'):
            instant = datetime.datetime.fromisoformat('2026-10-09T' + clock).astimezone().isoformat()
            direct = self.real.select(entry, None, 'dark', instant, dry=True)
            upstream = self.real.run(['set', str(source)], simulated=instant, dry=True)
            self.assertEqual(Path(direct).name, Path(upstream).name, clock)

    def test_three_metadata_types_and_safe_paths(self):
        from heic_factory import create
        for kind in ('time', 'solar', 'appearance'):
            file = create(Path(self.tmp.name) / kind, kind)
            safe_path = file.with_name("中文 ' ` $() ; " + file.name)
            file.rename(safe_path)
            entry = self.real.inspect(safe_path)
            self.assertEqual(entry['kind'], kind)
            safe_path.unlink()  # owned source must survive independently
            location = dict(lat=33.59, lon=130.4)
            for appearance in ('light', 'dark'):
                image = self.real.select(entry, location, appearance)
                self.assertTrue(Path(image).is_file())
            self.assertFalse(list(self.p.runtime.glob('call-*')))
            if kind == 'appearance':
                self.assertNotEqual(self.real.select(entry, location, 'light'),
                                    self.real.select(entry, location, 'dark'))

    def test_static_and_corrupt_rejected(self):
        from heic_factory import create
        file = create(Path(self.tmp.name) / 'static', 'static')
        with self.assertRaises(RuntimeError):
            self.real.inspect(file)
        file.write_text('invalid')
        with self.assertRaises(RuntimeError):
            self.real.inspect(file)

    def test_time_and_solar_schedule(self):
        from heic_factory import create
        location = dict(lat=33.59, lon=130.4)
        for kind in ('time', 'solar'):
            entry = self.real.inspect(create(Path(self.tmp.name) / kind, kind))
            with patch.dict(os.environ, TIMEWALL_OVERRIDE_TIME='2026-10-09T12:00:00+09:00'):
                noon = self.real.select(entry, location, 'light')
            with patch.dict(os.environ, TIMEWALL_OVERRIDE_TIME='2026-10-09T00:00:00+09:00'):
                night = self.real.select(entry, location, 'light')
            self.assertNotEqual(noon, night)

    def test_day_preview_plans_use_real_upstream_selection(self):
        from heic_factory import create
        for kind in ('time', 'solar', 'appearance'):
            entry = self.real.inspect(create(Path(self.tmp.name) / kind, kind))
            started = time.monotonic()
            progress = []
            frames = self.real.day_plan(entry, dict(lat=33.59, lon=130.4),
                                       datetime.date(2026, 10, 9), threading.Event(), progress.append)
            self.assertTrue(all(Path(frame['image']).is_file() for frame in frames))
            self.assertGreaterEqual(len({frame['image'] for frame in frames}), 2)
            self.assertEqual(progress[-1], 1)
            print(f'{kind} day preview: {len(frames)} frames, prepared in {time.monotonic()-started:.2f}s')

    def test_failed_setter_acknowledgement(self):
        executable = Path(self.tmp.name) / 'broken'
        executable.write_text('#!/bin/sh\nexit 0\n'); executable.chmod(0o755)
        result = self.p.runtime / 'absent.json'
        with self.assertRaisesRegex(RuntimeError, 'acknowledge'):
            m.backend_run([str(executable)], os.environ.copy(), timeout=0.1, confirmation=result)

    def test_backend_timeout(self):
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            m.backend_run([sys.executable, '-c', 'import time; time.sleep(10)'], os.environ.copy(), timeout=0.1)


import sys
if __name__ == '__main__':
    unittest.main()
