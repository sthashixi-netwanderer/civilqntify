"""Settings dialog for unit system preferences."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.unit_preferences import UnitPreferences, UnitSystem
from app.version import BUILD_TAG, STANDARDS_INFO, __version__
from app.widgets.frameless_dialog import FramelessDialog


class SettingsDialog(FramelessDialog):
    """Dialog for changing unit system preferences."""

    def __init__(
        self,
        unit_prefs: UnitPreferences,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, title="Settings")
        self._prefs = unit_prefs
        self.setMinimumWidth(400)
        # Modeless: opened through open_detached as an independent window,
        # so the main window stays usable and the window switcher can move
        # between this dialog and the rest of the app.
        self._build_ui()
        self._load_current()
        self.resize(440, 700)

    def _build_ui(self) -> None:
        root = self.content_layout
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Title ──
        title = QLabel("Unit Settings")
        title.setObjectName("dialog-title")
        root.addWidget(title)

        desc = QLabel(
            "Choose the unit system for all inputs and results. "
            "The backend always stores metric values internally."
        )
        desc.setObjectName("dialog-desc")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # ── Unit System ──
        sys_group = QGroupBox("Unit system")
        sys_layout = QVBoxLayout(sys_group)

        self._radio_metric = QRadioButton("Metric (kg, m\u00b3, MPa)")
        self._radio_imperial = QRadioButton("American Imperial (lb, yd\u00b3, psi)")
        sys_layout.addWidget(self._radio_metric)
        sys_layout.addWidget(self._radio_imperial)
        root.addWidget(sys_group)

        # ── Weather API Key ──
        api_group = QGroupBox("Weather API settings")
        api_layout = QVBoxLayout(api_group)

        api_desc = QLabel(
            "WeatherAPI.com requires a free API key for use.\n"
            "Get your free key at: https://www.weatherapi.com/"
        )
        api_desc.setObjectName("dialog-note")
        api_desc.setWordWrap(True)
        api_layout.addWidget(api_desc)

        # Title-bar visibility toggle for the Weather button
        self._show_weather_check = QCheckBox("Show weather button in title bar")
        api_layout.addWidget(self._show_weather_check)

        spacer = QLabel()
        spacer.setFixedHeight(6)
        api_layout.addWidget(spacer)

        api_key_row = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setObjectName("form-label")
        api_key_row.addWidget(api_key_label)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("Enter your WeatherAPI.com API key")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_row.addWidget(self._api_key_input, stretch=1)

        api_layout.addLayout(api_key_row)
        root.addWidget(api_group)

        # ── About & Build Information ──
        about_group = QGroupBox("Application & build information")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(6)

        ver_lbl = QLabel(f"<b>CivilQntify</b> — Version <b>{BUILD_TAG}</b>")
        ver_lbl.setObjectName("dialog-desc")
        about_layout.addWidget(ver_lbl)

        build_lbl = QLabel(f"Build: <code>{BUILD_TAG} (Release {__version__})</code>")
        build_lbl.setObjectName("dialog-note")
        about_layout.addWidget(build_lbl)

        std_lbl = QLabel(f"Standards: {STANDARDS_INFO}")
        std_lbl.setObjectName("dialog-note")
        std_lbl.setWordWrap(True)
        about_layout.addWidget(std_lbl)

        root.addWidget(about_group)

        # Stretch above the buttons pins the footer to the bottom edge so
        # the dialog never shows dead space under the action row when the
        # window is enlarged.
        root.addStretch(1)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setObjectName("secondary")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_apply = QPushButton("Apply")
        self._btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_apply)
        root.addLayout(btn_row)

    def _load_current(self) -> None:
        """Pre-select radios from current preferences."""
        if self._prefs.is_imperial():
            self._radio_imperial.setChecked(True)
        else:
            self._radio_metric.setChecked(True)

        # Load API key
        api_key = self._prefs.weather_api_key()
        self._api_key_input.setText(api_key)

        # Load title-bar visibility toggle
        self._show_weather_check.setChecked(self._prefs.weather_button_visible())

    def _apply(self) -> None:
        """Save preferences and close."""
        if self._radio_imperial.isChecked():
            self._prefs.set_system(UnitSystem.IMPERIAL)
        else:
            self._prefs.set_system(UnitSystem.METRIC)

        # Save API key
        api_key = self._api_key_input.text().strip()
        self._prefs.set_weather_api_key(api_key)

        # Save Weather button title-bar visibility
        self._prefs.set_weather_button_visible(self._show_weather_check.isChecked())

        self.accept()
