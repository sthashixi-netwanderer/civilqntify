"""CivilQntify — Entry point.

Run:  python main.py
"""

import sys

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
