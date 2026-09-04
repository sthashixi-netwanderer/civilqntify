"""CivilQntify — Entry point.

Run:  python main.py
"""

import os
import pathlib
import sys

# Ensure project root & PyInstaller temp directory (_MEIPASS) are in sys.path
# Covers both onefile (PyInstaller extracts to _MEIPASS) and onedir
# (executable sits next to bundled packages) layouts, plus the plain dev run.
def _init_sys_path() -> None:
    candidates: list[str] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(meipass)
    # Directory containing the executable / script — works for onedir and dev
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    try:
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception:
        pass
    # Also try pathlib for robustness on different OS path separators
    try:
        candidates.append(str(pathlib.Path(__file__).resolve().parent))
    except Exception:
        pass
    for p in candidates:
        if p and p not in sys.path:
            sys.path.insert(0, p)


_init_sys_path()

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.main import MainWindow, _resource_path

# Explicit imports to force PyInstaller to bundle all widget modules.
# PyInstaller's static analysis can miss modules imported only inside
# app.main when frozen; importing them here guarantees they are traced
# from the entry point (main.py) which is always analyzed.
import app.widgets.concrete_tab  # noqa: F401
import app.widgets.material_quantify_tab  # noqa: F401
import app.widgets.cost_estimation_tab  # noqa: F401
import app.widgets.history_tab  # noqa: F401
import app.widgets.psd_widget  # noqa: F401
import app.widgets.weather_widget  # noqa: F401
import app.pricing.price_sheet_service  # noqa: F401
import app.pricing.price_sheet_worker  # noqa: F401

# Windows: give the process an explicit AppUserModelID so the taskbar
# shows/groups it under our own icon instead of a generic one.
if sys.platform == "win32":
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CivilQntify")
    except Exception:
        pass


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("CivilQntify")
    app.setOrganizationName("CivilQntify")
    # Linux (Wayland/X11): ties windows to the civilqntify.desktop entry so
    # the taskbar/dock shows the app logo instead of a generic icon.
    # Must match the .desktop file name installed by
    # scripts/install_linux_desktop.sh (StartupWMClass=CivilQntify covers X11).
    try:
        app.setDesktopFileName("civilqntify")
    except Exception:
        pass
    app.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
    window = MainWindow()
    window.show()
    # X11 only: force the logo pixels into _NET_WM_ICON so the taskbar
    # never falls back to a generic glyph (no-op elsewhere, never raises).
    try:
        if app.platformName() == "xcb":
            app.processEvents()
            from app.x11_icon import push_window_icon
            push_window_icon(window, str(_resource_path("icon.png")))
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
