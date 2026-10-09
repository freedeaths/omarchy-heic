import datetime
import hashlib
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import test_controller as helpers

m = helpers.m

class PerformanceTests(unittest.TestCase):
    setUp = helpers.ControllerTests.setUp
    link = helpers.ControllerTests.link
    def tearDown(self):
        self.c.shutdown()
        helpers.ControllerTests.tearDown(self)

    def test_cached_import_does_not_run_backend(self):
        source = Path(self.tmp.name) / 'original.heic'
        source.write_bytes(b'existing wallpaper')
        identity = hashlib.sha256(source.read_bytes()).hexdigest()
        expected = dict(id=identity, name=source.name)
        m.atomic_json(self.p.data / 'library' / identity / 'metadata.json', expected)
        backend = m.Backend(self.p)
        with patch.object(backend, 'run', side_effect=AssertionError('duplicate backend inspection')):
            self.assertEqual(backend.inspect(source), expected)

    def test_time_and_appearance_selection_reuses_owned_png(self):
        image = self.p.data / 'library/one/0.png'
        from heic_factory import png
        png(image, (10, 20, 30))
        backend = m.Backend(self.p)
        with patch.object(backend, 'run', side_effect=AssertionError('duplicate decode')):
            for entry in (dict(id='one', kind='time', properties=dict(ti=[dict(t=0, i=0)])),
                          dict(id='one', kind='appearance', properties=dict(l=0, d=0))):
                self.assertEqual(backend.select(entry, None, 'dark'), str(image))

    def test_background_import_status_is_responsive_and_progress_completes(self):
        source = Path(self.tmp.name) / 'wall.heic'; source.touch()
        gate = threading.Event()
        started = threading.Event()
        def inspect(_):
            started.set()
            gate.wait(3)
            return dict(id='one')
        self.backend.inspect = inspect
        try:
            status = self.c.dispatch(dict(command='import', files=[str(source)], background=True))
            self.assertTrue(started.wait(1))
            self.assertEqual(status['importing']['total'], 1)
            self.assertEqual(self.c.dispatch(dict(command='status'))['mode'], 'disabled')
            for request in (dict(command='preview'), dict(command='remove', id='one')):
                with self.assertRaisesRegex(ValueError, 'import is already running'):
                    self.c.dispatch(request)
        finally:
            gate.set()
        self.c.import_job.result(timeout=3)
        self.c.tick()
        status = self.c.status()
        self.assertIsNone(status['importing'])
        self.assertEqual(status['import_result']['imported'], ['one'])
        self.assertIn('finished_at', status['import_result'])

    def test_legacy_preparation_keeps_status_responsive_and_waits_before_rendering(self):
        gate = threading.Event()
        started = threading.Event()
        entry = self.p.data / 'library/one/metadata.json'
        m.atomic_json(entry, dict(id='one', name='old.heic', kind='time',
                                 frames=[dict(index=0, path='old.png')]))
        def prepare(_):
            started.set()
            gate.wait(3)
        self.backend.prepare_entry = prepare
        self.c.state['mode'] = 'active'
        try:
            self.c.dispatch(dict(command='select', id='one'))
            self.assertTrue(started.wait(1))
            self.assertEqual(self.c.dispatch(dict(command='status'))['selected'], 'one')
            self.c.compute()
            self.assertEqual(self.applied, [])
        finally:
            gate.set()
        self.c.import_job.result(timeout=3)
        self.c.import_tick()
        self.assertFalse(self.c.preparing_selection)
        self.c.compute()
        self.assertEqual(self.applied, [str(self.image)])
