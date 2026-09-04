#!/usr/bin/env bash
# Install the CivilQntify taskbar/dock integration for the current user.
# Copies the .desktop launcher (with this checkout's python + path baked in)
# to ~/.local/share/applications and the hicolor icons to
# ~/.local/share/icons, then refreshes the icon cache.
# No sudo needed. Safe to re-run after moving the checkout (it regenerates).
set -euo pipefail
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$APPDIR/.venv/bin/python" ]; then
    PYTHON="$APPDIR/.venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi
DEST_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons"
mkdir -p "$DEST_DIR"
sed -e "s#@PYTHON@#$PYTHON#" -e "s#@APPDIR@#$APPDIR#" \
    "$APPDIR/packaging/civilqntify.desktop.template" > "$DEST_DIR/civilqntify.desktop"
chmod 644 "$DEST_DIR/civilqntify.desktop"
cp -r "$APPDIR/packaging/linux-icons/hicolor/." "$ICON_BASE/hicolor/"
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE/hicolor" >/dev/null 2>&1 || true
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DEST_DIR/civilqntify.desktop"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DEST_DIR" >/dev/null 2>&1 || true
fi
echo "Installed: $DEST_DIR/civilqntify.desktop (Exec: $PYTHON $APPDIR/main.py)"
