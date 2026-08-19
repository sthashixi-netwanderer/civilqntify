"""CivilQntify — Main application window."""

from __future__ import annotations

import pathlib
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase, QIcon


def _resource_path(name: str) -> pathlib.Path:
    """Resolve ``app/resources/<name>`` both in dev and in a PyInstaller bundle.

    Uses ``sys._MEIPASS`` when frozen; otherwise resolves relative to this
    file.  Covers both onefile (temp extraction) and onedir (sibling) layouts.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = pathlib.Path(meipass) / "app" / "resources" / name
        if p.exists():
            return p
        # Fallback: resources at top-level of bundle
        p2 = pathlib.Path(meipass) / "resources" / name
        if p2.exists():
            return p2
    # Dev fallback
    return pathlib.Path(__file__).resolve().parent / "resources" / name
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QMainWindow,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
    QVBoxLayout,
)

from app.styles import STYLESHEET
from app.unit_preferences import get_unit_prefs
from app.widgets.concrete_tab import ConcreteMixTab
from app.widgets.material_quantify_tab import MaterialQuantifyTab
from app.widgets.cost_estimation_tab import CostEstimationTab
from app.widgets.history_tab import HistoryTab
from app.widgets.weather_widget import WeatherWidget
from app.widgets.settings_dialog import SettingsDialog
from history.db import HistoryDB


class MainWindow(QMainWindow):
    """Top-level application window with tab-based navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CivilQntify")
        self.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
        self.setMinimumSize(1024, 640)
        self.resize(1360, 820)
        self.setStyleSheet(STYLESHEET)

        # Unit preferences (singleton)
        self.unit_prefs = get_unit_prefs()

        # Toolbar
        self._build_toolbar()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        # Concrete mix design tab
        self.concrete_tab = ConcreteMixTab()
        self.tabs.addTab(self.concrete_tab, "Concrete Mix Design")

        # Material quantification tab
        self.quant_tab = MaterialQuantifyTab()
        self.tabs.addTab(self.quant_tab, "Material Quantification")

        # Cost estimation tab
        self.cost_tab = CostEstimationTab()
        self.tabs.addTab(self.cost_tab, "Cost Estimation")
        self.tabs.setTabVisible(2, True)

        # History tab
        self.history_db = HistoryDB()
        self.history_tab = HistoryTab(db=self.history_db)
        _icon_path = _resource_path("history.svg")
        self.tabs.addTab(self.history_tab, QIcon(str(_icon_path)), "History")

        # Wire data handoff: mix design → quantification
        self.concrete_tab.mix_design_ready.connect(self._on_send_to_quant)

        # Wire data handoff: quantification → cost estimation
        self.quant_tab.quant_result_panel.send_to_cost_estimation.connect(self._on_send_to_cost)

        # Wire history loading signals
        self.history_tab.load_mix_design.connect(self._on_history_load_mix)
        self.history_tab.load_quantification.connect(self._on_history_load_quant)
        self.history_tab.load_cost_estimation.connect(self._on_history_load_cost)

        # Pass history_db to tabs
        self.concrete_tab._history_db = self.history_db
        self.quant_tab._history_db = self.history_db
        self.cost_tab._history_db = self.history_db

        # Pass unit_prefs to tabs
        self.concrete_tab.unit_prefs = self.unit_prefs
        self.quant_tab.unit_prefs = self.unit_prefs
        self.cost_tab.unit_prefs = self.unit_prefs

        # Wire unit preference changes
        self.unit_prefs.changed.connect(self._on_unit_changed)

        # Refresh history tab when switching to it
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _build_toolbar(self) -> None:
        """Create the top toolbar with weather and settings buttons."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)

        # Stretch spacer — pushes remaining widgets to the right
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        # Weather button — unified to primary palette
        self._btn_weather = QPushButton("Weather")
        self._btn_weather.setObjectName("weather-btn")
        self._btn_weather.setToolTip("View Weather Data")
        self._btn_weather.setFixedSize(80, 36)
        self._btn_weather.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                background-color: #1e40af;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1e3a8a;
            }
            QPushButton:pressed {
                background-color: #172554;
            }
        """)
        self._btn_weather.clicked.connect(self._open_weather)
        self._btn_weather.setVisible(False)  # hidden for now
        toolbar.addWidget(self._btn_weather)

        # Settings button
        _icon_path = _resource_path("settings.svg")
        self._btn_settings = QPushButton()
        self._btn_settings.setObjectName("settings-btn")
        self._btn_settings.setIcon(QIcon(str(_icon_path)))
        self._btn_settings.setToolTip("Unit Settings")
        self._btn_settings.setFixedSize(36, 36)
        self._btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(self._btn_settings)

    def _open_settings(self) -> None:
        """Open the unit settings dialog."""
        dialog = SettingsDialog(self.unit_prefs, parent=self)
        dialog.exec()

    def _open_weather(self) -> None:
        """Open the weather data modal dialog."""
        from PyQt6.QtWidgets import QDialog, QScrollArea

        dialog = QDialog(self)
        dialog.setWindowTitle("Weather Data")
        dialog.setModal(True)
        dialog.setMinimumSize(560, 700)
        dialog.resize(560, 780)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Scroll area so content never clips
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        weather_widget = WeatherWidget()
        api_key = self.unit_prefs.weather_api_key()
        weather_widget.set_api_key(api_key)
        scroll.setWidget(weather_widget)
        layout.addWidget(scroll)

        dialog.exec()

    def _on_unit_changed(self) -> None:
        """Handle unit preference changes — notify all tabs."""
        for tab in (self.concrete_tab, self.quant_tab, self.cost_tab):
            if hasattr(tab, "on_unit_changed"):
                tab.on_unit_changed()

    def _on_send_to_quant(self, result) -> None:
        """Handle mix design → quantification handoff."""
        try:
            self.quant_tab.load_transfer_data(
                result,
                cement_bag_weight=50.0,
                coarse_agg_bulk_density=1600.0,
                fine_agg_sg=2.65,
                coarse_agg_sg=2.70,
            )
            self.tabs.setCurrentWidget(self.quant_tab)
            up = self.unit_prefs
            cement_pv = (
                result.cement_kg * 1.68555 if up.is_imperial() else result.cement_kg
            )
            self.status_bar.showMessage(
                f"Mix design transferred to Quantification  |  "
                f"{result.code_used}  |  Cement: {cement_pv:.1f} "
                f"{up.mass_per_volume_unit()}",
                6000,
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Transfer Error", str(e))

    def _on_send_to_cost(self, bill) -> None:
        """Handle quantification → cost estimation handoff."""
        try:
            self.cost_tab.load_bill(bill)
            self.tabs.setCurrentWidget(self.cost_tab)
            up = self.unit_prefs
            self.status_bar.showMessage(
                f"Material bill transferred to Cost Estimation  |  "
                f"Gross Volume: {up.convert_volume_m3(bill.gross_concrete_volume_m3):.3f} "
                f"{up.volume_unit()}  |  "
                f"Cement: {bill.total_cement_bags:.0f} bags",
                6000,
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Transfer Error", str(e))

    def _on_history_load_mix(self, calc_id: int) -> None:
        """Load a mix design record from history into the concrete tab."""
        try:
            self.concrete_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.concrete_tab)
            self.status_bar.showMessage(f"Loaded mix design #{calc_id} from history", 5000)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_history_load_quant(self, calc_id: int) -> None:
        """Load a quantification record from history."""
        try:
            self.quant_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.quant_tab)
            self.status_bar.showMessage(f"Loaded quantification #{calc_id} from history", 5000)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_history_load_cost(self, calc_id: int) -> None:
        """Load a cost estimation record from history."""
        try:
            self.cost_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.cost_tab)
            self.status_bar.showMessage(f"Loaded cost estimation #{calc_id} from history", 5000)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_tab_changed(self, index: int) -> None:
        """Refresh history tab when user switches to it."""
        if index == self.tabs.indexOf(self.history_tab):
            self.history_tab.refresh()
