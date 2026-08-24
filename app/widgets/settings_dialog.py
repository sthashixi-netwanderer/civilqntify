"""Settings dialog for unit system preferences."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
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


class SettingsDialog(QDialog):
    """Dialog for changing unit system preferences."""

    def __init__(
        self,
        unit_prefs: UnitPreferences,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = unit_prefs
        self.setWindowTitle("Settings — Units")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 24)

        # ── Title ──
        title = QLabel("Unit Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0b1c30;")
        root.addWidget(title)

        desc = QLabel(
            "Choose the unit system for all inputs and results. "
            "The backend always stores metric values internally."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #444653; font-size: 12px;")
        root.addWidget(desc)

        # ── Unit System ──
        sys_group = QGroupBox("Unit System")
        sys_group.setStyleSheet(
            "QGroupBox { font-weight: 600; border: 1px solid #c4c5d5; "
            "border-radius: 4px; margin-top: 12px; padding: 16px 12px 12px 12px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        sys_layout = QVBoxLayout(sys_group)

        self._radio_metric = QRadioButton("Metric (kg, m\u00b3, MPa)")
        self._radio_imperial = QRadioButton("American Imperial (lb, yd\u00b3, psi)")
        self._radio_metric.setStyleSheet("font-size: 13px; padding: 4px 0;")
        self._radio_imperial.setStyleSheet("font-size: 13px; padding: 4px 0;")
        sys_layout.addWidget(self._radio_metric)
        sys_layout.addWidget(self._radio_imperial)
        root.addWidget(sys_group)

        # ── Weather API Key ──
        api_group = QGroupBox("Weather API Settings")
        api_group.setStyleSheet(
            "QGroupBox { font-weight: 600; border: 1px solid #c4c5d5; "
            "border-radius: 4px; margin-top: 12px; padding: 16px 12px 12px 12px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        api_layout = QVBoxLayout(api_group)

        api_desc = QLabel(
            "WeatherAPI.com requires a free API key for use.\n"
            "Get your free key at: https://www.weatherapi.com/"
        )
        api_desc.setWordWrap(True)
        api_desc.setStyleSheet("color: #444653; font-size: 11px; margin-bottom: 8px;")
        api_layout.addWidget(api_desc)

        # Toolbar visibility toggle for the Weather button
        self._show_weather_check = QCheckBox("Show weather button in toolbar")
        self._show_weather_check.setStyleSheet("font-size: 13px; padding: 2px 0;")
        api_layout.addWidget(self._show_weather_check)

        spacer = QLabel()
        spacer.setFixedHeight(6)
        api_layout.addWidget(spacer)

        api_key_row = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        api_key_row.addWidget(api_key_label)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("Enter your WeatherAPI.com API key")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setStyleSheet(
            "QLineEdit { padding: 6px 10px; border: 1px solid #d1d5db; "
            "border-radius: 5px; font-size: 12px; }"
            "QLineEdit:focus { border-color: #2563eb; }"
        )
        api_key_row.addWidget(self._api_key_input, stretch=1)

        api_layout.addLayout(api_key_row)
        root.addWidget(api_group)

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

        # Load toolbar visibility toggle
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

        # Save Weather button toolbar visibility
        self._prefs.set_weather_button_visible(self._show_weather_check.isChecked())

        self.accept()
