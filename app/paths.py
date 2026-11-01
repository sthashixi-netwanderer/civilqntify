"""Locate bundled application resources in dev and frozen builds."""

from __future__ import annotations

import pathlib
import sys


def resource_path(name: str) -> pathlib.Path:
    """Resolve ``app/resources/<name>`` both in dev and in a PyInstaller bundle.

    Uses ``sys._MEIPASS`` when frozen; otherwise resolves relative to the
    ``app`` package. Covers both onefile (temp extraction) and onedir
    (sibling) layouts.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for base in (
            pathlib.Path(meipass) / "app" / "resources",
            pathlib.Path(meipass) / "resources",
        ):
            candidate = base / name
            if candidate.exists():
                return candidate
    return pathlib.Path(__file__).resolve().parent / "resources" / name
