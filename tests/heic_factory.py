"""Generate original tiny HEIC fixtures with Apple XMP; no bundled artwork."""
import base64
import ctypes as C
import ctypes.util
from pathlib import Path
import plistlib
import struct
import subprocess
import zlib


def png(path, rgb):
    def chunk(kind, value):
        return struct.pack('!I', len(value)) + kind + value + struct.pack('!I', zlib.crc32(kind + value))
    width = height = 64
    pixels = b''.join(b'\0' + bytes(rgb) * width for _ in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def create(directory, kind):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    a, b = directory / 'day.png', directory / 'night.png'
    png(a, (100, 180, 230)); png(b, (10, 15, 40))
    dest = directory / f'{kind}.heic'
    subprocess.run(['heif-enc', '-q', '30', '-o', str(dest), str(a), str(b)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if kind == 'static':
        return dest
    value = {
        'time': dict(ti=[dict(i=0, t=0.5), dict(i=1, t=0.0)], ap=dict(l=0, d=1)),
        'solar': dict(si=[dict(i=0, a=15., z=130.), dict(i=1, a=-70., z=54.)], ap=dict(l=0, d=1)),
        'appearance': dict(l=0, d=1)
    }[kind]
    tag = dict(time='h24', solar='solar', appearance='apr')[kind]
    payload = base64.b64encode(plistlib.dumps(value, fmt=plistlib.FMT_BINARY)).decode()
    xmp = (f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           f'<rdf:Description xmlns:apple_desktop="http://ns.apple.com/namespace/1.0/" apple_desktop:{tag}="{payload}"/>'
           f'</rdf:RDF></x:xmpmeta>').encode()
    class Error(C.Structure):
        _fields_ = [('code', C.c_int), ('subcode', C.c_int), ('message', C.c_char_p)]
    lib = C.CDLL(ctypes.util.find_library('heif'))
    lib.heif_context_alloc.restype = C.c_void_p
    lib.heif_context_free.argtypes = [C.c_void_p]
    lib.heif_image_handle_release.argtypes = [C.c_void_p]
    for name, arguments in (
        ('heif_image_create', [C.c_int, C.c_int, C.c_int, C.c_int, C.POINTER(C.c_void_p)]),
        ('heif_image_add_plane', [C.c_void_p, C.c_int, C.c_int, C.c_int, C.c_int]),
        ('heif_context_get_encoder_for_format', [C.c_void_p, C.c_int, C.POINTER(C.c_void_p)]),
        ('heif_context_encode_image', [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)]),
        ('heif_context_get_primary_image_handle', [C.c_void_p, C.POINTER(C.c_void_p)]),
        ('heif_context_add_XMP_metadata', [C.c_void_p, C.c_void_p, C.c_char_p, C.c_int]),
        ('heif_context_write_to_file', [C.c_void_p, C.c_char_p])):
        f = getattr(lib, name); f.argtypes = arguments; f.restype = Error
    def check(error):
        if error.code:
            raise RuntimeError(error.message.decode())
    lib.heif_image_get_plane.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_int)]
    lib.heif_image_get_plane.restype = C.c_void_p
    lib.heif_image_release.argtypes = [C.c_void_p]
    lib.heif_encoder_release.argtypes = [C.c_void_p]
    context = lib.heif_context_alloc()
    handle = C.c_void_p()
    encoder = C.c_void_p()
    try:
        check(lib.heif_context_get_encoder_for_format(context, 1, C.byref(encoder)))
        for rgb in [(100, 180, 230), (10, 15, 40)]:
            image = C.c_void_p()
            check(lib.heif_image_create(64, 64, 1, 10, C.byref(image)))
            try:
                check(lib.heif_image_add_plane(image, 10, 64, 64, 8))
                stride = C.c_int()
                plane = lib.heif_image_get_plane(image, 10, C.byref(stride))
                for row in range(64):
                    C.memmove(plane + row * stride.value, bytes(rgb) * 64, 64 * 3)
                item = C.c_void_p()
                check(lib.heif_context_encode_image(context, image, encoder, None, C.byref(item)))
                if not handle:
                    handle = item
                else:
                    lib.heif_image_handle_release(item)
            finally:
                lib.heif_image_release(image)
        check(lib.heif_context_add_XMP_metadata(context, handle, xmp, len(xmp)))
        output = directory / 'metadata.heic'
        check(lib.heif_context_write_to_file(context, bytes(output)))
        output.replace(dest)
    finally:
        if handle:
            lib.heif_image_handle_release(handle)
        if encoder:
            lib.heif_encoder_release(encoder)
        lib.heif_context_free(context)
    return dest
