#!/usr/bin/env python3
"""Generate application icon artifacts from ``app/resources/icon.png``.

Outputs:
1. ``app/resources/icon.ico``  — multi-resolution Windows icon
   (16/24/32/48/64/128/256 px) embedded into the .exe by PyInstaller
   via ``icon=`` in ``civilqntify.spec``.
2. ``packaging/linux-icons/hicolor/<N>x<N>/apps/civilqntify.png`` —
   icon tree installed to ``/usr/share/icons/hicolor`` by the .deb/.rpm
   packages and referenced by the ``Icon=civilqntify`` desktop entry.

Run from the project root:
    python scripts/make_icon.py

Requires Pillow (installed transitively via matplotlib).
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "resources" / "icon.png"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
HICOLOR_SIZES = [16, 22, 24, 32, 36, 42, 48, 64, 72, 96, 128, 192, 256]


def main() -> int:
    if not SOURCE.is_file():
        print(f"error: source icon not found: {SOURCE}", file=sys.stderr)
        return 1

    src = Image.open(SOURCE).convert("RGBA")
    if src.size != (256, 256):
        src = src.resize((256, 256), Image.LANCZOS)

    # ── Windows .ico ────────────────────────────────────────────────
    ico_path = ROOT / "app" / "resources" / "icon.ico"
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    frames = [src.resize((s, s), Image.LANCZOS) for s in ICO_SIZES]
    frames[-1].save(
        ico_path,
        format="ICO",
        append_images=frames[:-1],
    )
    print(f"wrote {ico_path.relative_to(ROOT)} ({ico_path.stat().st_size} bytes)")

    # ── Linux hicolor tree ──────────────────────────────────────────
    base = ROOT / "packaging" / "linux-icons" / "hicolor"
    for s in HICOLOR_SIZES:
        out = base / f"{s}x{s}" / "apps" / "civilqntify.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        src.resize((s, s), Image.LANCZOS).save(out, format="PNG")
        print(f"wrote {out.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
