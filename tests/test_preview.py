import concurrent.futures
import datetime
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
import test_controller as helpers
m = helpers.m


class PreviewTests(unittest.TestCase):
    setUp = helpers.ControllerTests.setUp
    link = helpers.ControllerTests.link
    active = helpers.ControllerTests.active
    def tearDown(self):
        self.c.shutdown()
        helpers.ControllerTests.tearDown(self)

    def start(self, seconds=2):
        self.backend.day_plan = lambda *args: [dict(image=str(self.external), time='00:00', appearance=None),
                                              dict(image=str(self.old), time='12:00', appearance=None)]
        self.c.dispatch(dict(command='preview', seconds=seconds))
        self.c.preview_job.result(timeout=2)
        self.c.tick()

    def test_remove_selected_during_preview_restores_and_clears_selection(self):
        self.start()
        self.c.preview_tick(time.monotonic())
        self.assertEqual(self.c.background(), str(self.external))
        self.c.dispatch(dict(command='remove', id='one'))
        self.assertIsNone(self.c.preview)
        self.assertIsNone(self.c.cfg['selected'])
        self.assertEqual(self.c.background(), str(self.old))
        self.assertEqual(self.c.state['mode'], 'disabled')
        self.assertEqual(self.c.entries(), [])

    def test_full_desktop_stop_restores_disabled_state(self):
        self.start()
        self.assertEqual(self.c.background(), str(self.external))
        self.assertEqual(self.c.status()['preview']['total_seconds'], 4)
        self.c.dispatch(dict(command='preview-stop'))
        self.assertEqual(self.c.background(), str(self.old))
        self.assertEqual(self.c.state['mode'], 'disabled')
        self.assertIsNone(self.c.status()['preview'])

    def test_completion_restores_active_wallpaper_and_mode(self):
        self.active()
        self.start()
        for _ in range(2):
            self.c.preview['deadline'] = 0
            self.c.tick()
        self.assertEqual(self.c.state['mode'], 'active')
        self.assertEqual(self.c.background(), str(self.image))
        self.assertNotIn('preview_restore', self.c.state)

    def test_completion_preserves_paused_state(self):
        self.active()
        self.c.dispatch(dict(command='pause'))
        self.start()
        self.c.stop_preview()
        self.assertEqual(self.c.state['mode'], 'paused')
        self.assertEqual(self.c.background(), str(self.image))

    def test_external_wallpaper_wins_during_trial(self):
        self.active()
        self.start()
        other = Path(self.tmp.name) / 'chosen.png'
        other.touch()
        self.link(other)
        self.c.tick()
        self.assertIsNone(self.c.preview)
        self.assertEqual(self.c.background(), str(other))
        self.assertEqual(self.c.state['mode'], 'paused')

    def test_bad_date_and_duration_do_not_start_trial(self):
        for request in [dict(command='preview', seconds=0), dict(command='preview', seconds=float('nan')),
                        dict(command='preview', date='tomorrow')]:
            with self.assertRaises(ValueError):
                self.c.dispatch(request)
        self.assertIsNone(self.c.preview)
        self.assertEqual(self.c.background(), str(self.old))

    def test_preparation_can_be_cancelled_without_touching_wallpaper(self):
        gate = threading.Event()
        def prepare(*args):
            gate.wait(2)
            args[-1](1)  # A late callback must not mutate a new/stopped session.
            return []
        self.backend.day_plan = prepare
        self.c.start_preview(2, None)
        job = self.c.preview_job
        self.c.stop_preview()
        gate.set()
        job.result(timeout=2)
        self.assertEqual(self.c.background(), str(self.old))
        self.assertIsNone(self.c.preview)

    def test_restart_recovers_trial_snapshot(self):
        self.start()
        # Emulate a restart without graceful shutdown.
        with patch.object(m.Controller, 'apply', lambda controller, image: self.link(Path(image))):
            restarted = m.Controller(self.p, self.backend)
        try:
            self.assertEqual(restarted.background(), str(self.old))
            self.assertEqual(restarted.state['mode'], 'disabled')
        finally:
            restarted.shutdown()

    def test_apply_failure_restores_last_owned_preview_frame(self):
        self.start()
        original_apply = self.c.apply
        def failing(image):
            if image == str(self.old):
                raise RuntimeError('renderer failure')
            original_apply(image)
        self.c.apply = failing
        self.c.preview['deadline'] = 0
        # Force a failure on the second frame, then permit restore of the original.
        failed = False
        def fail_once(image):
            nonlocal failed
            if image == str(self.old) and not failed:
                failed = True
                raise RuntimeError('renderer failure')
            original_apply(image)
        self.c.apply = fail_once
        self.c.tick()
        self.assertEqual(self.c.background(), str(self.old))
        self.assertEqual(self.c.state['error'], 'renderer failure')

    def test_batch_import_continues_after_invalid_file(self):
        good = Path(self.tmp.name) / 'good.HEIC'; good.touch()
        bad = Path(self.tmp.name) / 'bad.png'; bad.touch()
        self.backend.inspect = lambda source: dict(id='one')
        status = self.c.dispatch(dict(command='import', files=[str(bad), str(good)]))
        self.assertEqual(status['import_result']['imported'], ['one'])
        self.assertEqual(len(status['import_result']['errors']), 1)
        self.assertEqual(status['selected'], 'one')


class ScheduleTests(unittest.TestCase):
    def test_time_plan_includes_short_phase_and_midnight_wrap(self):
        class Selector:
            day_plan = m.Backend.day_plan
            def select(self, entry, location, appearance, simulated, dry):
                instant = datetime.datetime.fromisoformat(simulated)
                value = (instant.hour * 3600 + instant.minute * 60 + instant.second) / 86400
                markers = entry['properties']['ti']
                marker = min(markers, key=lambda item: min(abs(item['t']-value), 1-abs(item['t']-value)))
                return str(marker['i'])
        entry = dict(kind='time', properties=dict(ti=[dict(t=0, i=0), dict(t=0.5, i=1), dict(t=0.5001, i=2)]))
        frames = Selector().day_plan(entry, None, datetime.date(2026, 10, 9), threading.Event(), lambda v: None)
        self.assertEqual({f['image'] for f in frames}, {'0', '1', '2'})
        self.assertEqual(frames[0]['time'], '00:00')

    def test_translation_catalog_has_matching_keys_and_placeholders(self):
        import re
        catalog = json.loads((Path(__file__).resolve().parents[1] / 'plugin/i18n.json').read_text())
        for language, messages in catalog.items():
            self.assertEqual(set(messages), set(catalog['en']))
            for key, text in messages.items():
                self.assertEqual(set(re.findall(r'\{\w+\}', text)),
                                 set(re.findall(r'\{\w+\}', catalog['en'][key])), (language, key))
