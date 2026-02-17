<<<<<<< copilot/vscode-mlqm5qvk-vf5h
# Wondershaper QuickToggle v1.1.0 — Release Notes

## Overview

Wondershaper QuickToggle v1.1 adds multi-language support and preset management enhancements. Users can now:
- Use the app in **French, German, and Spanish** (in addition to English)
- **Add and delete custom presets** directly from the settings UI
- View a **visual status indicator** showing current state and active preset

## New Features

- **Multi-language support** — French (`fr`), German (`de`), and Spanish (`es`) translations added. Language auto-detected from system locale.
- **Preset management** — "Add Preset" and "Delete Preset" buttons in settings window. Create unlimited custom presets with validation.
- **Visual status indicator** — Settings window header displays current enable/disable state and active preset name.
- **Enhanced UX** — All preset operations (add/delete/modify) provide immediate notifications and update the tray menu dynamically.

## Changes Since 1.0.0

- Added `i18n/fr.json`, `i18n/de.json`, `i18n/es.json` translation catalogs
- Settings window now shows status header at the top
- `on_add_preset()` and `on_delete_preset()` methods for preset CRUD
- Translation strings for preset operations: `preset_add`, `preset_delete`, `preset_added`, `preset_deleted`, etc.
- README updated with new feature list

---

=======
>>>>>>> main
# Wondershaper QuickToggle v1.0.0 — Release Notes

## Overview

Wondershaper QuickToggle v1.0 is the first stable release. It provides a
Linux desktop tray application to quickly enable or disable traffic-shaping
presets without running the GUI as root.

## Features

- **Tray menu** — Toggle ON/OFF, switch presets (Work, Gaming, Streaming,
  Custom), open settings, and quit.
- **Settings window** — Interface selector with auto-detect, preset editor,
  language selector, and start-on-login checkbox.
- **Privileged helper** — Uses `pkexec` / polkit so the GUI never runs as
  root. Supports `wondershaper` with automatic `tc` fallback.
- **Input validation** — Interface names are allow-listed, rates are clamped
  to 1–10 000 Mbps, and all subprocess calls use safe argument lists (no
  `shell=True`).
- **i18n** — English catalog included; add new languages by dropping a JSON
  file in `/usr/share/wondershaper-quicktoggle/i18n/`.
- **Debian package** — `dpkg-buildpackage` produces a ready-to-install
  `.deb` that places the helper, policy, icons, and desktop entry in the
  correct FHS paths.

## Known Limitations

- **GNOME Shell** requires the *AppIndicator / KStatusNotifierItem Support*
  extension for the tray icon to appear.
- **Flatpak / Snap** — polkit interaction may not work inside sandboxed
  environments; native `.deb` install is recommended.
- Only English (`en.json`) is shipped. Community translations are welcome.
- The helper calls `wondershaper` or `tc` directly; exotic traffic-shaping
  setups are not supported.

## Changes Since 0.1.0

- **Security / correctness**
  - Autostart desktop entry now uses the packaged launcher path
    (`/usr/bin/wondershaper-quicktoggle`) instead of the source-tree path.
  - Settings save wraps rate parsing in `try/except` to prevent crashes on
    invalid user input and shows a notification instead.
  - Config loading catches `JSONDecodeError` and `OSError`, falling back to
    defaults instead of crashing.
  - Replaced deprecated `locale.getdefaultlocale()` with `locale.getlocale()`.

- **Packaging**
  - Debian changelog bumped to `1.0.0-1`.
  - `src/__init__.py` added to the install manifest.

- **Tests**
  - Added unit tests for `ConfigStore`, `validate_preset`, `clamp_mbps`,
    and `I18N`.
