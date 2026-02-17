#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPDIR="$ROOT_DIR/dist/AppDir"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib/wondershaper-quicktoggle" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/share/icons/hicolor/scalable/status" \
         "$APPDIR/usr/lib/wondershaper-quicktoggle/i18n"

cp "$ROOT_DIR/data/bin/wondershaper-quicktoggle" "$APPDIR/usr/bin/"
cp "$ROOT_DIR/src/"*.py "$APPDIR/usr/lib/wondershaper-quicktoggle/"
cp "$ROOT_DIR/helper/wsqt_helper.py" "$APPDIR/usr/lib/wondershaper-quicktoggle/"
cp "$ROOT_DIR/i18n/"*.json "$APPDIR/usr/lib/wondershaper-quicktoggle/i18n/"
cp "$ROOT_DIR/data/applications/wondershaper-quicktoggle.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT_DIR/data/icons/hicolor/scalable/apps/wondershaper-quicktoggle.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cp "$ROOT_DIR/data/icons/hicolor/scalable/status/"*.svg "$APPDIR/usr/share/icons/hicolor/scalable/status/"

chmod +x "$APPDIR/usr/bin/wondershaper-quicktoggle"

echo "AppDir prepared at: $APPDIR"
echo "Note: AppImage cannot bundle host polkit integration safely. Install helper/policy on host:"
echo "  /usr/lib/wondershaper-quicktoggle/wsqt_helper.py"
echo "  /usr/share/polkit-1/actions/io.github.wondershaper.quicktoggle.policy"
