"""CivilQntify — Main application window."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QPushButton,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)

from app.paths import resource_path as _resource_path
from app.styles import STYLESHEET
from app.unit_preferences import get_unit_prefs
from app.widgets.concrete_tab import ConcreteMixTab
from app.widgets.frameless import FramelessResizeHelper
from app.widgets.frameless_dialog import FramelessDialog, open_detached
from app.widgets.material_quantify_tab import MaterialQuantifyTab
from app.widgets.cost_estimation_tab import CostEstimationTab
from app.widgets.history_tab import HistoryTab
from app.widgets.message_dialog import MessageBox as QMessageBox
from app.widgets.title_bar import TitleBar
from app.widgets.weather_widget import WeatherWidget
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.window_switcher import add_window_switch_shortcuts
from history.db import HistoryDB


class MainWindow(QMainWindow):
    """Top-level application window with tab-based navigation."""

    def __init__(self) -> None:
        super().__init__()
        # The OS decoration is replaced by the theme-matched TitleBar below;
        # keep the system menu + min/max hints so task switching, Alt+F4 and
        # platform window menus continue to work.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setWindowTitle("CivilQntify")
        self.setObjectName("main-window")
        self.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
        self.setMinimumSize(1024, 640)
        self.resize(1360, 820)
        self.setStyleSheet(STYLESHEET)

        # Unit preferences (singleton)
        self.unit_prefs = get_unit_prefs()

        # Custom frameless title bar (identity, weather/settings, controls)
        self._build_titlebar()

        # Central widget
        central = QWidget()
        central.setObjectName("main-content")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.titlebar)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        # Mix design tab
        self.concrete_tab = ConcreteMixTab()
        self.tabs.addTab(self.concrete_tab, "Mix Design")

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
        self.history_tab.load_psd.connect(self._on_history_load_psd)

        # Pass history_db to tabs
        self.concrete_tab._history_db = self.history_db
        self.quant_tab._history_db = self.history_db
        self.cost_tab._history_db = self.history_db
        self.concrete_tab._psd_tab._history_db = self.history_db

        # Pass unit_prefs to tabs
        self.concrete_tab.unit_prefs = self.unit_prefs
        self.quant_tab.unit_prefs = self.unit_prefs
        self.cost_tab.unit_prefs = self.unit_prefs

        # Wire unit preference changes
        self.unit_prefs.changed.connect(self._on_unit_changed)
        self.unit_prefs.weather_button_changed.connect(
            self._on_weather_visibility_changed
        )

        # Refresh history tab when switching to it
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Edge-resize support for the frameless shell (native system resize
        # where available, manual fallback elsewhere).
        self._frameless_helper = FramelessResizeHelper(self)

        # Ctrl+Tab / Ctrl+Shift+Tab cycle between this window and the open
        # detached dialogs (mirrored on every dialog's title bar).
        add_window_switch_shortcuts(self)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt naming
        """Keep the custom maximise/restore glyph in sync with the window."""
        if event.type() == QEvent.Type.WindowStateChange:
            titlebar = getattr(self, "titlebar", None)
            if titlebar is not None:
                titlebar.sync_window_state()
        super().changeEvent(event)

    def _build_titlebar(self) -> None:
        """Create the custom title bar with weather and settings actions."""
        self.titlebar = TitleBar(
            self,
            icon_path=str(_resource_path("icon.png")),
        )

        # Weather button — styled centrally via #weather-btn in STYLESHEET
        self._btn_weather = QPushButton("Weather")
        self._btn_weather.setObjectName("weather-btn")
        self._btn_weather.setToolTip("View Weather Data")
        self._btn_weather.setFixedSize(80, 30)
        self._btn_weather.clicked.connect(self._open_weather)
        weather_visible = self.unit_prefs.weather_button_visible()
        self._btn_weather.setVisible(weather_visible)
        self.titlebar.add_action_widget(self._btn_weather)

        # The title bar owns the widget; this action mirrors its visibility so
        # preference listeners (and the settings dialog) have one state object
        # to toggle rather than reaching into the title bar internals.
        self._action_weather = QAction("Weather", self)
        self._action_weather.setVisible(weather_visible)

        # Settings button
        _icon_path = _resource_path("settings.svg")
        self._btn_settings = QPushButton()
        self._btn_settings.setObjectName("settings-btn")
        self._btn_settings.setIcon(QIcon(str(_icon_path)))
        self._btn_settings.setToolTip("Unit Settings")
        self._btn_settings.setFixedSize(32, 30)
        self._btn_settings.clicked.connect(self._open_settings)
        self.titlebar.add_action_widget(self._btn_settings)

    def _open_settings(self) -> None:
        """Open the unit settings dialog."""
        dialog = SettingsDialog(self.unit_prefs, parent=self)
        open_detached(dialog)

    def _open_weather(self) -> None:
        """Open the weather data dialog as a detached window."""
        from PyQt6.QtWidgets import QScrollArea

        dialog = FramelessDialog(self, title="Weather Data")
        dialog.setMinimumSize(560, 700)
        dialog.resize(560, 780)

        layout = dialog.content_layout
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Scroll area so content never clips
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        weather_widget = WeatherWidget()
        api_key = self.unit_prefs.weather_api_key()
        weather_widget.set_api_key(api_key)
        scroll.setWidget(weather_widget)
        layout.addWidget(scroll)

        open_detached(dialog)

    def _on_unit_changed(self) -> None:
        """Handle unit preference changes — notify all tabs."""
        for tab in (self.concrete_tab, self.quant_tab, self.cost_tab):
            if hasattr(tab, "on_unit_changed"):
                tab.on_unit_changed()

    def _on_weather_visibility_changed(self, visible: bool) -> None:
        """Show or hide the Weather title-bar button when the setting changes."""
        self._action_weather.setVisible(visible)
        self._btn_weather.setVisible(visible)
        self.titlebar.updateGeometry()

    def _on_send_to_quant(self, result) -> None:
        """Handle mix design → quantification handoff."""
        try:
            from material_quantify.models.transfer_data import MixDesignTransferData

            # Use the inputs of the displayed calculation, not current widgets
            # (which may have been edited since that calculation).
            params = self.concrete_tab._last_input_params or {}
            if isinstance(result, MixDesignTransferData):
                transfer = result
            else:
                transfer = MixDesignTransferData.from_mix_design_result(
                    result,
                    coarse_agg_bulk_density_kg_m3=params.get("coarse_agg_bulk_density", 1600.0),
                    fine_agg_sg=params.get("fine_agg_sg", 2.65),
                    coarse_agg_sg=params.get("coarse_agg_sg", 2.70),
                )
                transfer.scm_type = params.get("scm_type") or "SCM (unspecified)"
            self.quant_tab.load_transfer_data(transfer)
            self.tabs.setCurrentWidget(self.quant_tab)
            up = self.unit_prefs
            cement_pv = (
                transfer.cement_kg_per_m3 * 1.68555 if up.is_imperial() else transfer.cement_kg_per_m3
            )
            self.status_bar.showMessage(
                f"Mix design transferred to Quantification  |  "
                f"{transfer.code_used}  |  Cement: {cement_pv:.1f} "
                f"{up.mass_per_volume_unit()}",
                6000,
            )
        except Exception as e:
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
            QMessageBox.critical(self, "Transfer Error", str(e))

    def _on_history_load_mix(self, calc_id: int) -> None:
        """Load a mix design record from history into the concrete tab."""
        try:
            self.concrete_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.concrete_tab)
            self.status_bar.showMessage(f"Loaded mix design #{calc_id} from history", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_history_load_quant(self, calc_id: int) -> None:
        """Load a quantification record from history."""
        try:
            self.quant_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.quant_tab)
            self.status_bar.showMessage(f"Loaded quantification #{calc_id} from history", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_history_load_cost(self, calc_id: int) -> None:
        """Load a cost estimation record from history."""
        try:
            self.cost_tab.load_from_history(calc_id)
            self.tabs.setCurrentWidget(self.cost_tab)
            self.status_bar.showMessage(f"Loaded cost estimation #{calc_id} from history", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_history_load_psd(self, calc_id: int) -> None:
        """Load a PSD record from history into the PSD subtab."""
        try:
            self.concrete_tab.load_psd_from_history(calc_id)
            self.tabs.setCurrentWidget(self.concrete_tab)
            self.status_bar.showMessage(f"Loaded PSD analysis #{calc_id} from history", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _on_tab_changed(self, index: int) -> None:
        """Refresh history tab when user switches to it."""
        if index == self.tabs.indexOf(self.history_tab):
            self.history_tab.refresh()
