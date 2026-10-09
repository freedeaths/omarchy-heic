#!/usr/bin/env python3
"""Run the real Omarchy library picker in an isolated offscreen Quickshell."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='heic-library-ui-') as tmp:
    config = Path(tmp)
    for item in Path('/usr/share/omarchy/shell').iterdir():
        if item.is_dir():
            (config / item.name).symlink_to(item, target_is_directory=True)
    source = (root / 'tests/qml/tst_library.qml').read_text()
    source = source.replace('import "../../plugin"', f'import "{(root / "plugin").as_uri()}"')
    source = 'import Quickshell\n' + source.replace('Item {\n  width: 500; height: 500',
        'ShellRoot {\nFloatingWindow {\n id: window\n visible: true\n implicitWidth: 500; implicitHeight: 500')
    source = source.replace('when: windowShown', 'when: window.visible') + '\n}\n'
    (config / 'shell.qml').write_text(source)
    runtime = config / 'runtime'
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='', XDG_RUNTIME_DIR=str(runtime))
    env.pop('WAYLAND_DISPLAY', None)
    result = subprocess.run(['quickshell', '-p', str(config)], env=env, capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    if result.returncode or 'HEIC_LIBRARY_UI_OK' not in output:
        print(output)
        raise SystemExit(1)
    print('Library selection, hover delete and separate action signals passed')
