
<img width="430" height="394" alt="Capture d’écran du 2026-02-17 12-05-34" src="https://github.com/user-attachments/assets/620d1099-ab67-4049-bf1a-3f8a9af162c6" />

<img width="408" height="262" alt="Capture d’écran du 2026-02-17 12-06-21" src="https://github.com/user-attachments/assets/cbd2e9fc-a489-4751-aa19-f01e6a1ad39a" />

# Wondershaper QuickToggle (MVP)

Wondershaper QuickToggle is a Linux desktop tray app that enables/disables traffic shaping presets quickly, without running the GUI as root.

## Why this stack
This MVP uses **Python 3 + PyGObject (GTK3) + Ayatana AppIndicator + libnotify** because it is the fastest path to a portable tray app across KDE/Cinnamon/XFCE, with GNOME support when the tray extension is installed.

## Features
- Tray menu with:
  - Toggle ON/OFF
  - Presets: Work, Gaming, Streaming, Custom
  - Open Settings
  - Quit
- Immediate apply/disable with desktop notifications.
- Settings window:
  - Visual status indicator (enabled/disabled + active preset)
  - Interface selector with auto-detect
  - Preset editor (name/down/up)
  - Add/Delete preset buttons for custom preset management
  - Apply now, Disable, Save
  - Language selector (English, French, German, Spanish)
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
cp -r packaging/debian .
dpkg-buildpackage -us -uc
cd ..
sudo apt install ./wondershaper-quicktoggle_*_all.deb
```

Installed paths:
- `/usr/bin/wondershaper-quicktoggle` (launcher shell script -> `python3 /usr/lib/wondershaper-quicktoggle/main.py`)
- `/usr/lib/wondershaper-quicktoggle/` (application + helper code)
- `/usr/share/polkit-1/actions/io.github.wondershaper.quicktoggle.policy`
- `/usr/share/applications/wondershaper-quicktoggle.desktop`
- `/usr/share/icons/hicolor/` (scalable + common app icon sizes)

For local/manual policy install, keep helper path aligned with policy annotation:
`/usr/lib/wondershaper-quicktoggle/wsqt_helper.py`.

## Troubleshooting
- **No tray icon on GNOME**: install/enable AppIndicator/KStatusNotifierItem extension.
- **Permission denied or auth prompt fails**: verify policy file exists and helper path matches policy `exec.path`.
- **Apply fails**: ensure `wondershaper` or `tc` exists (`command -v wondershaper` / `command -v tc`).
- **Interface not detected**: check `ip route show default`; manually set interface in Settings.
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
