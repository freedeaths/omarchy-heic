import math
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import test_controller as helpers

m = helpers.m


def solid_png(path, width, height):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    compressor = zlib.compressobj(1)
    row = b'\0' + bytes((45, 90, 140)) * width
    pieces = [compressor.compress(row) for _ in range(height)]
    pieces.append(compressor.flush())
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', b''.join(pieces)) + chunk(b'IEND', b''))


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.library = Path(self.tmp.name) / 'library' / 'one'
        self.library.mkdir(parents=True)
        self.source = self.library / '0.png'
        self.backend = m.Backend(type('Paths', (), {'data': Path(self.tmp.name)})())

    def test_fuji_size_is_scaled_and_original_is_preserved(self):
        solid_png(self.source, 9600, 7168)
        original = self.source.read_bytes()
        render = Path(self.backend.derived_image(self.source, (3840, 2160), 'display'))
        thumb = Path(self.backend.derived_image(self.source, (1024, 1024), 'thumbnails'))
        self.assertEqual(self.backend.png_size(render), (3840, 2867))
        self.assertEqual(self.backend.png_size(thumb), (1024, 764))
        self.assertEqual(self.source.read_bytes(), original)
        self.assertLess(math.prod(self.backend.png_size(render)) * 4, 256 * 1024 * 1024)
        with patch.object(m.subprocess, 'run', side_effect=AssertionError('repeated conversion')):
            self.assertEqual(self.backend.derived_image(self.source, (3840, 2160), 'display'), str(render))
        thumb.write_bytes(b'broken cache')
        self.backend.derived_image(self.source, (1024, 1024), 'thumbnails')
        self.assertEqual(self.backend.png_size(thumb), (1024, 764))

    def test_existing_entry_is_upgraded_without_heic_decode(self):
        solid_png(self.source, 64, 64)
        entry = dict(id='one', name='old.heic', kind='time', properties=dict(ti=[dict(i=0, t=0)]),
                     frames=[dict(index=0, path=str(self.source))])
        with patch.object(self.backend, 'run', side_effect=AssertionError('HEIC decoded again')):
            upgraded = self.backend.prepare_entry(entry)
        self.assertEqual(upgraded['name'], 'old.heic')
        self.assertTrue(Path(upgraded['frames'][0]['thumbnail']).is_file())
        self.assertEqual(upgraded['frames'][0]['path'], str(self.source))
        self.assertEqual(m.read_json(self.library / 'metadata.json', {})['properties'], entry['properties'])

    def test_monitor_rotation_and_pixel_budget(self):
        result = type('Result', (), {'stdout': '[{"width":3840,"height":2160,"transform":1}]'})()
        with patch.object(m.subprocess, 'run', return_value=result):
            self.assertEqual(self.backend.display_bounds(), (2160, 3840))
        self.backend.profile_checked = m.time.monotonic()
        self.backend.profile = 16000, 12000
        w, h = self.backend.display_bounds()
        self.assertLessEqual(w * h, 32_000_000)
        self.assertLessEqual(max(w, h), 8192)

    def test_resize_failure_is_not_published_and_source_survives(self):
        solid_png(self.source, 64, 64)
        result = type('Result', (), {'returncode': 1, 'stderr': 'decoder failed'})()
        with patch.object(m.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'decoder failed'):
                self.backend.derived_image(self.source, (32, 32), 'thumbnails')
        self.assertEqual(list((self.library / 'thumbnails').rglob('*.png')), [])
        self.assertEqual(self.backend.png_size(self.source), (64, 64))

    def test_unsafe_library_identity_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Invalid library'):
            self.backend.library_image(dict(id='..'), 0)
