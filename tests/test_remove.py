import json
from pathlib import Path
import unittest
import test_controller as helpers

m = helpers.m

class RemoveTests(unittest.TestCase):
    setUp = helpers.ControllerTests.setUp
    tearDown = helpers.ControllerTests.tearDown
    link = helpers.ControllerTests.link
    active = helpers.ControllerTests.active

    def test_selected_removal_restores_original_and_preserves_source(self):
        source = Path(self.tmp.name) / 'source.heic'
        source.write_bytes(b'original')
        owned = self.p.data / 'library/one/wallpaper.heic'
        owned.write_bytes(source.read_bytes())
        self.active()
        self.c.dispatch(dict(command='remove', id='one'))
        self.assertEqual(self.c.background(), str(self.old))
        self.assertEqual(self.c.state['mode'], 'disabled')
        self.assertIsNone(self.c.cfg['selected'])
        self.assertFalse(owned.parent.exists())
        self.assertEqual(source.read_bytes(), b'original')
        self.assertIsNone(json.loads(self.p.config_file.read_text())['selected'])

    def test_unselected_removal_preserves_active_wallpaper(self):
        m.atomic_json(self.p.data / 'library/two/metadata.json', dict(id='two', name='other.heic'))
        self.active()
        self.c.dispatch(dict(command='remove', id='two'))
        self.assertEqual(self.c.cfg['selected'], 'one')
        self.assertEqual(self.c.state['mode'], 'active')
        self.assertEqual(self.c.background(), str(self.image))
        self.assertEqual(len(self.c.entries()), 1)

    def test_external_wallpaper_is_preserved(self):
        self.active()
        self.link(self.external)
        self.c.dispatch(dict(command='remove', id='one'))
        self.assertEqual(self.c.background(), str(self.external))
        self.assertEqual(self.c.state['mode'], 'disabled')

    def test_missing_original_keeps_visible_cached_image(self):
        self.active()
        self.old.unlink()
        self.c.dispatch(dict(command='remove', id='one'))
        self.assertEqual(self.c.background(), str(self.image))
        self.assertEqual(self.c.state['mode'], 'disabled')

    def test_unknown_and_unsafe_paths_rejected(self):
        with self.assertRaises(ValueError):
            self.c.dispatch(dict(command='remove', id='missing'))
        outside = Path(self.tmp.name) / 'outside'
        m.atomic_json(outside / 'metadata.json', dict(id='linked', name='external.heic'))
        (self.p.data / 'library/linked').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Invalid library path'):
            self.c.dispatch(dict(command='remove', id='linked'))
        self.assertTrue((outside / 'metadata.json').exists())
        self.assertEqual(self.c.cfg['selected'], 'one')

    def test_missing_previous_retains_visible_library_png_before_delete(self):
        owned = self.p.data / 'library/one/0.png'
        owned.write_bytes(b'visible pixels')
        self.backend.image = str(owned)
        self.active()
        self.old.unlink()
        self.c.dispatch(dict(command='remove', id='one'))
        self.assertFalse(owned.exists())
        retained = Path(self.c.background())
        self.assertTrue(retained.is_relative_to(self.p.cache))
        self.assertEqual(retained.read_bytes(), b'visible pixels')
        self.assertEqual(self.c.state['mode'], 'disabled')

    def test_restore_failure_keeps_entry_selected(self):
        self.active()
        def fail(_):
            raise RuntimeError('renderer failed')
        self.c.apply = fail
        with self.assertRaises(RuntimeError):
            self.c.dispatch(dict(command='remove', id='one'))
        self.assertEqual(self.c.cfg['selected'], 'one')
        self.assertTrue((self.p.data / 'library/one/metadata.json').exists())
