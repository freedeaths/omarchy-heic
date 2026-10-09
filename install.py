#!/usr/bin/env python3
"""Install/remove only user-owned HEIC plugin files. No sudo required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
ID = 'org.omarchy.heic'
HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
RECORD = DATA / 'omarchy-heic/install.json'
BIN = HOME / '.local/bin'
SHELL = CONFIG / 'omarchy/shell.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def shell_widget(add):
    # Preserve the user's entire bar configuration and all other plugins.
    path = SHELL if SHELL.exists() else Path('/usr/share/omarchy/config/omarchy/shell.json')
    cfg = json.loads(path.read_text())
    layout = cfg.setdefault('bar', {}).setdefault('layout', {})
    if add:
        if not any(isinstance(row, dict) and row.get('id') == ID
                   for section in layout.values() if isinstance(section, list) for row in section):
            layout.setdefault('right', []).insert(0, {'id': ID})
    else:
        for section in list(layout):
            if isinstance(layout[section], list):
                layout[section] = [row for row in layout[section]
                                   if not (isinstance(row, dict) and row.get('id') == ID)]
        cfg['plugins'] = [row for row in cfg.get('plugins', [])
                          if (row.get('id') if isinstance(row, dict) else row) != ID]
    if SHELL.exists():
        shutil.copy2(SHELL, SHELL.with_name('shell.json.heic-backup-' + str(time.time_ns())))
    write_json(SHELL, cfg)


def systemctl(*args):
    subprocess.run(['systemctl', '--user', *args], check=True)


def install(backend, shell_managed=False):
    old = json.loads(RECORD.read_text()) if RECORD.exists() else {'files': {}}
    files = {}
    def put(src, dest):
        if dest.exists() and str(dest) not in old['files']:
            if digest(dest) != digest(src):
                raise RuntimeError(f'Refusing to replace an unrelated file: {dest}')
        if str(dest) in old['files'] and dest.exists() and digest(dest) != old['files'][str(dest)]:
            raise RuntimeError(f'Installed file has local edits; retain or move it first: {dest}')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        files[str(dest)] = digest(dest)
    candidate = str(backend) if backend else shutil.which('timewall')
    if not candidate:
        raise RuntimeError('Install timewall 2.1.0 first, or pass --backend /path/to/timewall')
    version = subprocess.check_output([candidate, '--version'], text=True).strip()
    if version != 'timewall 2.1.0':
        raise RuntimeError(f'Validated backend is timewall 2.1.0; found {version}')
    # Preflight all file conflicts before writing any of the installation.
    mappings = [(ROOT / 'bin' / name, BIN / name) for name in ('omarchy-heic', 'omarchy-heic-capture', 'omarchy-heic-picker')]
    if not shell_managed:
        mappings += [(src, CONFIG / 'omarchy/plugins' / ID / src.name) for src in (ROOT / 'plugin').iterdir() if src.is_file()]
    mappings += [(ROOT / 'systemd/omarchy-heic.service', CONFIG / 'systemd/user/omarchy-heic.service'),
                 (ROOT / 'hooks/90-omarchy-heic', CONFIG / 'omarchy/hooks/theme-set.d/90-omarchy-heic')]
    if backend and Path(backend).resolve() != (BIN / 'timewall').resolve():
        mappings += [(Path(backend), BIN / 'timewall')]
    for src, dest in mappings:
        if dest.exists() and digest(dest) != old['files'].get(str(dest), digest(src)):
            raise RuntimeError(f'File conflict: {dest}')
    for src, dest in mappings:
        put(src, dest)
    # Keep previous owned backend in the uninstall inventory on repeat installs.
    for dest, checksum in old['files'].items():
        if dest not in files:
            files[dest] = checksum
    write_json(RECORD, dict(version=1, files=files))
    if not shell_managed:
        shell_widget(True)
    systemctl('daemon-reload')
    systemctl('enable', 'omarchy-heic.service')
    systemctl('restart', 'omarchy-heic.service')
    print('Installed. Open Dynamic Desktop from the new wallpaper icon in the bar. Import a HEIC, then enable it.')


def uninstall():
    if not RECORD.exists():
        raise RuntimeError('No installation inventory found; no files removed')
    record = json.loads(RECORD.read_text())
    # Restore only if controller still owns the visible background.
    subprocess.run([str(BIN / 'omarchy-heic'), 'disable'], check=False)
    subprocess.run(['systemctl', '--user', 'disable', '--now', 'omarchy-heic.service'], check=False)
    shell_widget(False)
    kept = {}
    for name, checksum in record['files'].items():
        path = Path(name)
        if path.exists() and digest(path) == checksum:
            path.unlink()
        elif path.exists():
            kept[name] = checksum
            print(f'Preserved locally edited file: {path}')
    if kept:
        write_json(RECORD, dict(version=1, files=kept))
    else:
        RECORD.unlink()
    systemctl('daemon-reload')
    print('Uninstalled. Library, preferences and other themes/darkman configuration retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--backend', type=Path)
    parser.add_argument('--shell-managed', action='store_true', help='Set up only the runtime; Omarchy manages the cloned plugin and bar')
    args = parser.parse_args()
    try:
        uninstall() if args.uninstall else install(args.backend, args.shell_managed)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
