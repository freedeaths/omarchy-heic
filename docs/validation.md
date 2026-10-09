# Validation record

Validated locally on 2026-10-09 with Omarchy 4.0.4-1, Hyprland 0.56.2-2,
Python 3.14, libheif 1.23.4-1 and Rust stable 1.99.0. timewall reports 2.1.0;
the supported build is upstream commit 19897aee9fee4f4ebd5cbd37b0fc4e3271cb6480
with the local-header build overlay and committed dependency lockfile.

## Automated checks

All 27 tests passed with real backend tests enabled:

```sh
OMARCHY_HEIC_TIMEWALL="$PWD/.test-output/timewall-target/release/timewall" \
  python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

Coverage includes generated time, solar and appearance HEICs; noon/midnight
selection; light/dark appearance; filenames with spaces, Chinese and shell
metacharacters; invalid/static inputs; setter acknowledgement and process timeout;
ownership loss; theme changes during decoding; service restart; suspend recovery;
failure retention; location validation; opt-in darkman import; and installer
conflicts, repeat installation, uninstall and retention of local edits.

The socket test runs the real daemon/CLI/backend with isolated XDG directories
and a substitute renderer. It verifies socket permissions, import/enable,
external-wallpaper pause, persisted state after restart and socket cleanup.
Restricted execution environments must allow local Unix sockets for this test.

`qmllint -I /tmp/heic-qml-imports plugin/Panel.qml` passed with two static type
warnings for Quickshell QProcess::ExitStatus and the dynamic Style.font.heading
property; both resolved at runtime. The import directory's `qs` symlink points to
/usr/share/omarchy/shell.

## Live desktop checks

The installed user service responded through its CLI/socket. The panel rendered
in the live Omarchy bar, and its file chooser opened. A generated appearance HEIC
was imported and enabled through the installed controller and actual
`omarchy theme bg set` renderer. Selecting the original ordinary wallpaper paused
the controller. Disable retained that wallpaper. Initial plugin state/preferences
were restored and the synthetic library entry removed after the smoke test.
The installed service remains running with dynamic wallpaper disabled.

## Compatibility findings and limits

The official timewall 2.1.0 binary and a default source build both failed with
libheif 1.23.4: the security-limit structure copied by older bindings carried a
newer version number than its layout, producing a one-byte memory budget. The
build overlay generates the complete current layout without disabling security
limits. Two enum aliases now expressed as C macros are normalized to their older
names in temporary headers for libheif-rs 2.7. Rust source and the user's installed
headers remain unchanged. The locked build recipe was rerun successfully.

The native Qt/GTK file chooser triggered a Quickshell SIGABRT during desktop
testing. coredumpctl showed GTK/GVfs/GIO frames ending in GLib allocation/abort;
the exact cause inside those libraries was not established. The plugin uses
FileDialog.DontUseNativeDialog to avoid that in-process native path. The shell was
restarted and its panel/file chooser validated afterward.

No Apple artwork was used. Large original macOS assets, HDR handling, a physical
suspend/resume cycle, multi-monitor rendering and newer Omarchy/OWE versions have
not been separately tested. Theme and suspend behaviors are covered by controller
tests. Theme-hook ownership has a documented two-second settling window. This
project is ready for further user testing; it has not been published remotely.

## 0.2 preview and i18n update

39 Python tests passed with real timewall, including all three day-preview plans,
short time phases, cancellation, original modes, external ownership, failed apply,
restart recovery and mixed batch imports. A generated solar plan sampled every
minute and prepared in 9.40 seconds locally; time and appearance took under
0.05 seconds after decoding. Node checks passed for locale precedence, fallback,
placeholder interpolation and known-message translations. Catalog keys and
placeholders match across English and Simplified Chinese. qmllint passed with
the same two existing dynamic-type warnings.

The user's selected Japan road wallpaper was trialled through the installed
service and real renderer at 0.5 seconds per frame. Its chronological day plan
had five playback segments (the final segment repeats the midnight image),
lasting 2.5 seconds. Both explicit stop and natural completion restored the
original active wallpaper and selection. Two existing library entries and their
location were preserved by installation. The shell required a restart to replace
its cached old QML component after plugin rescan.

Final UI was simplified to a dropdown, a 128-pixel-high thumbnail with frame
controls, one Preview/Stop action and conditional solar location controls. The
whole panel uses a Column without Flickable, adapting its height to content.
The live thumbnail and compact layout were visually checked. Temporary image
diagnostic IPC was removed from the final source.

## Multi-file chooser correction

Qt 6.11.2's non-native Quick file dialog still has QTBUG-92585 TODOs in its
implementation and returns just one file. Replaced it with the isolated
`omarchy-heic-picker` GTK 3 process. GIO_USE_VFS=local and local-only selection
avoid loading remote GVfs modules; the desktop shell does not load GTK.

Three opt-in real GTK interaction tests passed in separate processes: Ctrl
click returns non-adjacent files, Shift click returns a range, and an actual
Hyprland-dispatched Ctrl+A returns every matching file. Mixed-case HEIC/HEIF
files are included; a PNG fixture is excluded. Tests never import fixtures or
change the wallpaper. Run with
`OMARCHY_HEIC_PICKER_UI_TEST=1 python -m unittest discover -s tests -p test_picker_ui.py -v`
in a live GTK/Hyprland session. Installer tests and locale checks also passed.

## 0.2.1 library deletion and frame metadata

Six controller removal tests cover selected/unselected entries, external
ownership, unavailable original background, invalid/symlink paths and renderer
failure. Preview tests additionally verify removal during playback restores the
prior background before deleting the entry. Real backend import tests already
delete the source and continue selecting all three wallpaper kinds successfully.
The socket test passed with permission to create local Unix sockets (the initial
restricted run could not create its socket).

`node tests/frame-info.test.cjs` passed for time markers including repeated image
indices, solar coordinates and appearance states. Locale checks passed.
`python scripts/test-library-ui.py` runs the actual themed component in isolated
offscreen Quickshell and passed selection, hover delete, and independent action
signals. User library entries were not deleted during verification.

## 0.3 import performance, locales and standard packaging

Real Downloads benchmarks were isolated in temporary XDG paths and did not
change the user's sources or library. Tokyo Tower (22.9 MiB, 15 frames): original
cold import 13.601s, fast PNG import 5.531s, first preview preparation
16.197s → 0.005s, duplicate import 0.152s → 0.095s. Japan road's four decoded
frames were pixel-identical under ffmpeg SHA-256 verification; PNG storage
18.38 MiB → 22.72 MiB. The optional build patch is confined to the private
source copy and retains libheif security limits.

The controller suite passed apart from Unix-socket tests blocked in the
restricted sandbox; that integration test passed separately with local socket
permission. Additional tests passed for duplicate-import backend avoidance,
direct PNG reuse, responsive background import/progress, upstream time-selection
parity at boundary/tie times, and shell-managed runtime setup preserving the
git-managed manifest and unrelated bar configuration.

Node locale tests verify all nine catalogs have the same keys/placeholders and
select the seven added language codes and country variants. Real themed library
interaction checks still pass. A staged source package passed the installed
`omarchy-plugin-validate`; root manifest points to plugin/Panel.qml. No GitHub
repository was published or user wallpaper library entry removed.

After installation, the 0.3.0 runtime inventory matched every installed file.
A live preview of the user's selected wallpaper rendered its first frame in
0.352 seconds and restored the original background, active mode and selection
without error. Ten existing library entries remained. Removal now retains a
visible library PNG in a private cache before deleting it when no previous
background is available; the additional regression test passed.

## Publication checks

The final pre-push suite ran 55 Python tests: 52 passed, with three live GTK
picker tests skipped in this non-interactive run (their earlier live checks
passed). Locale and frame-label Node checks and the real offscreen Quickshell
library interaction check passed. The publication includes only source, docs,
manifest and tests; built binaries, decoded artwork, screenshots and temporary
XDG data are excluded.

Marketplace submission requires exactly one `manifest.json` at the repository
root. The standalone compatibility manifest is therefore named
`plugin/standalone-manifest.json`; the Python installer still installs it as
`manifest.json` with the flattened `Panel.qml` entry point. Repeat-install and
uninstall regression checks cover this mapping. The submission preparation run
passed 44 Python tests, skipping 11 backend/live-desktop tests, and the root
package passed `omarchy-plugin-validate`.
