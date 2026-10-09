"""Opt-in real GTK/Hyprland picker checks; never imports fixtures into the library."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('OMARCHY_HEIC_PICKER_UI_TEST') == '1', 'requires a live GTK/Hyprland session')
class PickerUITests(unittest.TestCase):
    def check_selection(self, mode, expected):
        result = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def _check_selection(self, mode, expected):
        os.environ['GIO_USE_VFS'] = 'local'
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk, GLib
        script = Path(__file__).resolve().parents[1] / 'bin/omarchy-heic-picker'
        original = Gtk.FileChooserDialog.run
        errors = []
        def descendants(widget):
            yield widget
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    yield from descendants(child)
        def drive(dialog):
            def ready():
                tree = next((w for w in descendants(dialog) if isinstance(w, Gtk.TreeView)
                             and w.get_model() is not None and len(w.get_model()) == 3), None)
                if tree is None:
                    return True
                try:
                    tree.grab_focus()
                    tree.set_cursor(Gtk.TreePath.new_from_indices([0]))
                    if mode == 'all':
                        subprocess.run(['hyprctl', 'dispatch',
                            'hl.dsp.send_shortcut({mods="CTRL",key="A",window="title:^HEIC-Picker-UI-Test$"})'],
                            check=True, capture_output=True)
                    else:
                        rect = tree.get_background_area(Gtk.TreePath.new_from_indices([2]), None)
                        for kind in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE):
                            event = Gdk.Event.new(kind)
                            event.window = tree.get_bin_window()
                            event.send_event = True
                            event.time = (GLib.get_monotonic_time() // 1000) % (2**32)
                            event.x, event.y = 20, rect.y + rect.height / 2
                            event.button = 1
                            event.state = Gdk.ModifierType.CONTROL_MASK if mode == 'ctrl' else Gdk.ModifierType.SHIFT_MASK
                            event.set_device(Gdk.Display.get_default().get_default_seat().get_pointer())
                            Gtk.main_do_event(event)
                    def finish():
                        try:
                            self.assertEqual(sorted(Path(p).name for p in dialog.get_filenames()), expected)
                        except Exception as exc:
                            errors.append(exc)
                        dialog.response(Gtk.ResponseType.ACCEPT)
                        return False
                    GLib.timeout_add(250, finish)
                except Exception as exc:
                    errors.append(exc)
                    dialog.response(Gtk.ResponseType.CANCEL)
                return False
            GLib.timeout_add(500, ready)
            def timeout():
                errors.append(AssertionError('Picker file list did not load'))
                dialog.response(Gtk.ResponseType.CANCEL)
                return False
            deadline = GLib.timeout_add(5000, timeout)
            result = original(dialog)
            GLib.source_remove(deadline)
            return result
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('a.heic', 'b.HEIF', 'c.hEiC', 'hidden.png'):
                (Path(tmp) / name).touch()
            args = ['picker', '--title', 'HEIC-Picker-UI-Test', '--filter', 'HEIC', '--accept', 'Open',
                    '--cancel', 'Cancel', '--hint', 'Ctrl / Shift / Ctrl+A', '--folder', tmp]
            out = io.StringIO()
            with patch.object(sys, 'argv', args), patch.object(Gtk.FileChooserDialog, 'run', drive), contextlib.redirect_stdout(out):
                runpy.run_path(str(script), run_name='__main__')
            if errors:
                raise errors[0]
            self.assertEqual(sorted(Path(p).name for p in json.loads(out.getvalue())), expected)

    def test_ctrl_click_non_adjacent_files(self):
        self.check_selection('ctrl', ['a.heic', 'c.hEiC'])

    def test_shift_click_range(self):
        self.check_selection('shift', ['a.heic', 'b.HEIF', 'c.hEiC'])

    def test_ctrl_a_all_filtered_files(self):
        self.check_selection('all', ['a.heic', 'b.HEIF', 'c.hEiC'])


if __name__ == '__main__':
    mode = sys.argv[1]
    expected = ['a.heic', 'c.hEiC'] if mode == 'ctrl' else ['a.heic', 'b.HEIF', 'c.hEiC']
    PickerUITests()._check_selection(mode, expected)
