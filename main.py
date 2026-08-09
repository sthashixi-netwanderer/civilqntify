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

from PyQt6.QtWidgets import QApplication

from app.main import MainWindow



def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("CivilQntify")
    app.setOrganizationName("CivilQntify")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
