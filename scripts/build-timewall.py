#!/usr/bin/env python3
"""Build upstream timewall with bindings generated from the local libheif headers.

The binding overlay avoids copying a newer security-limit structure into older
fixed-size bindings. Rust sources remain unchanged unless --fast-png is requested;
that option changes only lossless PNG compression in the private source copy.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

COMMIT = '19897aee9fee4f4ebd5cbd37b0fc4e3271cb6480'
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clean bcyran/timewall checkout')
    parser.add_argument('--cargo', default='cargo')
    parser.add_argument('--toolchain', default='stable')
    parser.add_argument('--fast-png', action='store_true', help='Use fast lossless PNG encoding in the private build copy')
    args = parser.parse_args()
    source = args.source.resolve()
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != COMMIT or subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']):
        raise SystemExit(f'Use a clean upstream checkout at {COMMIT}')
    output = ROOT / '.test-output'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='timewall-build-', dir=output) as tmp:
        staged = Path(tmp)
        shutil.copytree(source, staged, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.git', 'target'))
        manifest = staged / 'Cargo.toml'
        manifest.write_text(manifest.read_text().replace('[dependencies]',
            '[dependencies]\nlibheif-sys = { version = "=5.2.0", features = ["v1_19", "use-bindgen"] }'))
        shutil.copy2(ROOT / 'scripts/timewall-bindgen.lock', staged / 'Cargo.lock')
        if args.fast_png:
            converter = staged / 'src/heif/convert.rs'
            original = converter.read_text()
            anchor = 'png_encoder.set_depth(png::BitDepth::Eight);'
            if original.count(anchor) != 1:
                raise RuntimeError('Unexpected upstream PNG encoder; refusing to patch')
            converter.write_text(original.replace(anchor, anchor + '\n    png_encoder.set_compression(png::Compression::Fast);'))
        env = os.environ.copy()
        env['CARGO_TARGET_DIR'] = str(output / 'timewall-target')
        # libheif 1.23 moved two enum aliases into macros, which bindgen omits.
        # Normalize their spelling in private headers; values/layout stay intact.
        include = subprocess.check_output(['pkg-config', '--variable=includedir', 'libheif'], text=True).strip()
        compat = staged / 'include/libheif'
        shutil.copytree(Path(include) / 'libheif', compat)
        for header in compat.glob('*.h'):
            text = header.read_text()
            for new, old in [('heif_colorspace_custom', 'heif_colorspace_nonvisual'),
                             ('heif_chroma_planar', 'heif_chroma_monochrome')]:
                if re.search(rf'^#define {old} {new}$', text, re.M):
                    text = re.sub(rf'^#define {old} {new}$', '', text, flags=re.M)
                    text = re.sub(rf'\b{new}\b', old, text)
            header.write_text(text)
        env['BINDGEN_EXTRA_CLANG_ARGS'] = env.get('BINDGEN_EXTRA_CLANG_ARGS', '') + ' -I' + str(staged / 'include')
        subprocess.run([args.cargo, '+' + args.toolchain, 'build', '--release', '--locked'],
                       cwd=staged, env=env, check=True)
        shutil.copy2(staged / 'Cargo.lock', output / 'timewall-bindgen.lock')
    print(output / 'timewall-target/release/timewall')


if __name__ == '__main__':
    main()
