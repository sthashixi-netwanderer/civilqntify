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
# Stage and validate everything before replacing installed files. Backups allow
# rollback if a later write fails; the launcher is published last.
"$PYTHON" - "$APPDIR" "$PYTHON" "$DEST_DIR" "$ICON_BASE" <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

appdir, python, dest, icons = sys.argv[1:]
appdir, dest, icons = Path(appdir), Path(dest), Path(icons)
source = appdir / "packaging/linux-icons/hicolor"
if not source.is_dir():
    raise SystemExit("Installation failed: source icons are missing; launcher unchanged")
dest.mkdir(parents=True, exist_ok=True)
(icons / "hicolor").mkdir(parents=True, exist_ok=True)
def quoted(value):
    value = str(value).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value + '"'
text = (appdir / "packaging/civilqntify.desktop.template").read_text(encoding="utf-8")
text = text.replace("@PYTHON@ @APPDIR@/main.py", quoted(python) + " " + quoted(appdir / "main.py"))
with tempfile.TemporaryDirectory(prefix=".civilqntify-install-", dir=dest.parent) as temp:
    stage = Path(temp)
    launcher = stage / "civilqntify.desktop"
    launcher.write_text(text, encoding="utf-8")
    launcher.chmod(0o644)
    validator = shutil.which("desktop-file-validate")
    if validator:
        subprocess.run([validator, str(launcher)], check=True, timeout=15)
    files = [(p, icons / "hicolor" / p.relative_to(source))
             for p in source.rglob("*") if p.is_file()]
    files.append((launcher, dest / launcher.name))
    changed = []
    try:
        for index, (src, target) in enumerate(files):
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = stage / f"backup-{index}"
            existed = target.exists()
            if existed:
                shutil.copy2(target, backup)
            pending = stage / f"pending-{index}"
            shutil.copy2(src, pending)
            os.replace(pending, target)
            changed.append((target, backup if existed else None))
    except Exception as exc:
        for target, backup in reversed(changed):
            if backup is not None:
                os.replace(backup, target)
            else:
                target.unlink(missing_ok=True)
        raise SystemExit(f"Installation failed; installed files rolled back: {exc}")
PY
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE/hicolor" >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DEST_DIR" >/dev/null 2>&1 || true
fi
echo "Installed: $DEST_DIR/civilqntify.desktop (Exec: $PYTHON $APPDIR/main.py)"
