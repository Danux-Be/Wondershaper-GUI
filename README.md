# Wondershaper QuickToggle (MVP)

Wondershaper QuickToggle is a Linux desktop tray app that enables/disables traffic shaping presets quickly, without running the GUI as root.

## Why this stack
This MVP uses **Python 3 + PyGObject (GTK3) + Ayatana AppIndicator + libnotify** because it is the fastest path to a portable tray app across KDE/Cinnamon/XFCE, with GNOME support when the tray extension is installed.

## Features
- Tray menu with:
  - Toggle ON/OFF
  - Temporary limit durations (15/30/60/custom minutes)
  - Presets: Work, Gaming, Streaming, Custom
  - About…, Export Config…, Import Config…, Show 10s Activity…
  - Open Settings
  - Quit
- Dynamic symbolic tray icons:
  - OFF icon when shaping is disabled
  - ON icon when shaping is enabled
  - TIMER icon while temporary-limit mode is active
- Immediate apply/disable with desktop notifications.
- Lightweight live status line in tray menu (interface, active/inactive, down/up Mbps, timer state).
- Automatic active-interface tracking with graceful fallback when a selected interface disappears.
- Settings window:
  - Interface selector with auto-detect/manual override
  - Preset editor (name/down/up)
  - Apply now, Disable, Save
  - Language selector (English catalog included; ready for new languages)
  - Start on login checkbox
- Privileged helper with Polkit for running `wondershaper`/`tc` safely.
- Configuration at `~/.config/wondershaper-quicktoggle/config.json`.
- Logs at `~/.local/state/wondershaper-quicktoggle/app.log`.

## Repository layout
- `src/`: GTK app, tray, settings UI, backend, config, i18n loader
- `helper/`: privileged helper executable used with `pkexec`
- `data/`: icons, desktop entry, autostart template, polkit policy
- `i18n/`: translation catalogs (`en.json`)
- `packaging/`: minimal Debian packaging scaffold

## Security model
- Main app runs as normal user.
- Privileged operations are delegated to `helper/wsqt_helper.py` via `pkexec`.
- Inputs are validated before helper execution:
  - interface allow-list regex
  - bandwidth range clamp (`1..10000 Mbps`)
- UI stores rates in **Mbps**; helper converts to **Kbps** (`mbps * 1000`) before invoking `wondershaper`/`tc`.
- Helper uses argument arrays (`subprocess.run([...])`) and never `shell=True`.
- Polkit policy (`data/polkit/io.github.wondershaper.quicktoggle.policy`) uses action id `io.github.wondershaper.quicktoggle` and scopes authorization to the helper path.

## GNOME tray note
GNOME Shell usually needs the extension **AppIndicator/KStatusNotifierItem Support** for tray icons.

## Tray icon states
OFF state:

![OFF icon](data/icons/hicolor/scalable/status/wondershaper-quicktoggle-off-symbolic.svg)

ON state:

![ON icon](data/icons/hicolor/scalable/status/wondershaper-quicktoggle-on-symbolic.svg)

TIMER state:

![TIMER icon](data/icons/hicolor/scalable/status/wondershaper-quicktoggle-timer-symbolic.svg)

## v0.2 usability additions
- **Temporary Limit mode**: start a timed shaping session from the tray; when the timer expires, limits are cleared automatically and a notification is shown.
- **Active interface auto-detection**: by default the app tracks the active route using `ip route get 1.1.1.1` with `nmcli` fallback and notifies on interface switches.
- **Manual interface respect**: choosing a specific interface in Settings disables auto-mode; if it disappears, the app falls back gracefully to an available active interface.
- **Live status indicator**: tray menu includes a low-cost status line with interface, active state, current preset rates, and temporary timer state.

## Supported languages
- English (`en`)
- Français (`fr`)
- Deutsch (`de`)
- Español (`es`)
- Nederlands (`nl`)

Language entries are auto-discovered from the `i18n/` directory and missing keys fall back to English.

## About and configuration tools
- **About dialog** (tray + Settings): app version, project URL, license, runtime interface/mode/limits/timer/SSID.
- **Export Config…**: exports presets, language, interface mode, selected preset, and Wi-Fi preset mappings.
- **Import Config…**: schema-validated merge, automatic timestamped backup of current config, optional immediate apply.

## Wi-Fi SSID based presets
- Configure mappings in Settings: `SSID -> preset`.
- In auto-interface mode, the watchdog checks active SSID (`nmcli`, optional `iwgetid` fallback).
- When a mapped SSID is detected:
  - active preset is switched automatically,
  - if shaping is already enabled, limits are re-applied with the mapped preset,
  - user gets a desktop notification.

## 10-second activity view
- Open from tray (**Show 10s Activity…**).
- Samples once per second from `/sys/class/net/<iface>/statistics/{rx_bytes,tx_bytes}` only while window is open.
- Displays current RX/TX rates and tiny history sparklines (no heavy graph dependencies).

## Install dependencies (Ubuntu / Linux Mint)
```bash
sudo apt update
sudo apt install -y \
  python3 python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 \
  gir1.2-ayatanaappindicator3-0.1 \
  policykit-1 iproute2 wondershaper
```

## Run from source
```bash
cd /workspace/danux
python3 src/main.py
```

## Install policy/helper (dev machine)
```bash
sudo install -m 0755 helper/wsqt_helper.py /usr/lib/wondershaper-quicktoggle/wsqt_helper.py
sudo install -m 0644 data/polkit/io.github.wondershaper.quicktoggle.policy /usr/share/polkit-1/actions/
```

## Install from .deb
From repo root:
```bash
dpkg-buildpackage -us -uc -b
cd ..
sudo apt install ./wondershaper-quicktoggle_*_all.deb
```

Installed paths:
- `/usr/bin/wondershaper-quicktoggle` (launcher shell script -> `python3 /usr/lib/wondershaper-quicktoggle/main.py`)
- `/usr/lib/wondershaper-quicktoggle/` (application + helper code + i18n catalogs)
- `/usr/share/polkit-1/actions/io.github.wondershaper.quicktoggle.policy`
- `/usr/share/applications/wondershaper-quicktoggle.desktop`
- `/usr/share/icons/hicolor/` (scalable + common app icon sizes)
- `/etc/xdg/autostart/wondershaper-quicktoggle.desktop` (system-wide autostart entry template)

For local/manual policy install, keep helper path aligned with policy annotation:
`/usr/lib/wondershaper-quicktoggle/wsqt_helper.py`.

To verify polkit registration after install:
```bash
pkcheck --action-id io.github.wondershaper.quicktoggle --process $$ --allow-user-interaction
```

## Troubleshooting
- **No tray icon on GNOME**: install/enable AppIndicator/KStatusNotifierItem extension.
- **Permission denied or auth prompt fails**: verify policy file exists and helper path matches policy `exec.path`; confirm action is visible with `pkaction | grep io.github.wondershaper.quicktoggle`.
- **Apply fails**: ensure `wondershaper` or `tc` exists (`command -v wondershaper` / `command -v tc`).
- **Interface not detected**: check `ip route get 1.1.1.1` and `nmcli -t -f DEVICE,STATE device`; manually set interface in Settings.
- **Unexpected interface switching**: if you want a fixed NIC, open Settings and pick a specific interface instead of Auto-detect.
- **Temporary mode did not clear limits**: check policy/auth prompts and helper logs in `~/.local/state/wondershaper-quicktoggle/app.log`.
- **No notifications**: verify desktop notifications are enabled.

## Verification commands
```bash
python3 -m py_compile src/*.py helper/wsqt_helper.py
python3 helper/wsqt_helper.py status --iface lo || true
ip route show default
```

## Migrations / env vars
- No database migrations.
- No required environment variables for MVP.

## AppImage (experimental packaging)
Build AppDir layout:
```bash
packaging/appimage/build.sh
```

Notes:
- This prepares `dist/AppDir` for artifact distribution.
- Applying limits still depends on host-side helper/polkit installation:
  - `/usr/lib/wondershaper-quicktoggle/wsqt_helper.py`
  - `/usr/share/polkit-1/actions/io.github.wondershaper.quicktoggle.policy`

## Flatpak (manifest and caveats)
Manifest:
- `packaging/flatpak/io.github.wondershaper.quicktoggle.json`

Important limitations:
- Tray icon behavior on GNOME depends on AppIndicator extension.
- Privileged shaping cannot be fully sandboxed inside Flatpak with pkexec/polkit.
- Recommended approach: Flatpak GUI + host-installed helper/policy for actual limit apply/clear operations.

