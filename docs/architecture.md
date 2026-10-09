# Architecture

QML bar panel → JSON CLI → private Unix socket → serialized Python controller →
validated library PNG (time/appearance) or timewall CLI + capture helper (solar) →
`omarchy theme bg set` → existing Quickshell Background plugin.

Time selection uses the upstream circular nearest-marker rule and metadata-order
ties, verified against timewall at boundaries. Appearance reads the light/dark
indices directly. Reusing imported PNGs avoids a second HEIC decode and repeated
file hashing during desktop preview. Import decoding runs in one background
worker, with progress polled by the service loop; all desktop and config changes
stay in the serialized controller. Imports publish complete library directories
atomically. Background import completion carries a unique timestamp; the panel
shows its summary for five seconds and ignores the historical result on startup.

The graphical-session user service owns all mutations. Socket and containing
directory are user-only. Requests are one newline-terminated JSON object, maximum
1 MiB. Responses are `{ok:true,data:status}` or `{ok:false,error:message}`. CLI
success prints status JSON; failure prints JSON to stderr and exits nonzero.
Commands: import(files, optional background), select(id), remove(id),
location(lat,lon), import-location, enable, pause, resume, disable, refresh,
theme-changed, preview(seconds,date), preview-stop, status. Schema version 1.

Metadata is read from timewall's unpacked properties.xml with Python plistlib,
not by scraping human-readable CLI output. A SHA-256 library ID addresses the
owned source, metadata and preview frames. Backend caches remain independent.
Each backend call receives private TIMEWALL_CONFIG_DIR and TIMEWALL_RUNTIME_DIR,
with a persistent private TIMEWALL_CACHE_DIR. The runtime directory is new for
every call, so timewall cannot reuse a stale setter PID. Commands use argv arrays;
paths are never embedded in shell commands. The capture helper atomically writes
the selected path; controller waits for acknowledgement, validates that it belongs
to its cache and only then applies it. The entire backend process group is cleaned
up after completion or timeout. No externally running timewall instance is used.

A service loop serializes commands, checks ownership each second and reevaluates
current frames every 60 seconds. Theme name changes and the existing theme-set
flock defer processing; a theme hook wakes reevaluation. We do not use timewall's
own daemon: it compares only frame indexes and loads config before the loop,
which complicates replacing wallpapers and reapplying after external updates.

Appearance selection explicitly uses the current theme's `omarchy-theme-color`
mode, with legacy light.mode fallback. Appearance HEIC directly uses the matching metadata index; solar/time HEIC
follows its original schedule.
GeoClue is disabled in the private backend configuration. Coordinates are opt-in.

Plugin ID: org.omarchy.heic. Locations under XDG config/data/state/cache are
namespaced omarchy-heic. Installed CLI goes in ~/.local/bin; the graphical
session service and theme hook are user-owned. The installer tracks content hashes
and refuses to overwrite unrelated files or discard local edits.

First version supports a shared wallpaper across monitors, manual location and
in-panel frame preview. It does not override color themes, create HEIC files,
implement HDR handling, interpolate a full-day smooth video, or add per-monitor
renderers. Future OWE integration requires separate verification.

Upstream research: timewall master 19897aee9fee4f4ebd5cbd37b0fc4e3271cb6480;
release 2.1.0 tag 6bc9d48f1bb912d1f12b8db54f910e9922a571b5 was investigated.
The supported local build uses the pinned master commit with generated bindings;
see README for the libheif 1.23 compatibility build overlay.
Upstream uses Rust/libheif, Apple XMP containing Base64 plist data, PNG cache,
location from GeoClue or config, XDG appearance Portal, and configurable setters.
Nix/Home Manager integration is in upstream nix/hm-module.nix. Arch AUR has
packaging records; this is not a claim that any distribution ships it by default.
