"""CivilQntify — Entry point.

Run:  python main.py
"""

import os
import sys

# Ensure project root & PyInstaller temp directory (_MEIPASS) are in sys.path
if getattr(sys, "frozen", False):
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

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
