"""Central unit system preferences for CivilQntify.

Provides a singleton UnitPreferences instance that manages the active unit
system (Metric or American Imperial). Metric lengths always display in
metres.

All conversion is display-layer only — the backend always works in SI metric.

Persistence: QSettings (survives app restarts).
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QObject, QSettings, pyqtSignal


class UnitSystem(Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


# ── Conversion factors (metric → target) ────────────────────────────────

_MPA_TO_PSI = 145.038
_MM_TO_INCH = 1.0 / 25.4
_CM_TO_INCH = 1.0 / 2.54
_M_TO_FT = 3.28084
_KG_TO_LB = 2.20462
_M3_TO_YD3 = 1.30795
_KGM3_TO_LBFT3 = 0.062428
_KGM3_TO_LBYD3 = 1.68555
_LITER_TO_GAL = 0.264172


class UnitPreferences(QObject):
    """Manages the active unit system and provides conversion helpers.

    Use the module-level ``get_unit_prefs()`` singleton rather than
    instantiating this class directly.
    """

    changed = pyqtSignal()

    _SETTINGS_ORG = "CivilQntify"
    _SETTINGS_APP = "CivilQntify"
    _KEY_SYSTEM = "unit_system"
    _KEY_WEATHER_API_KEY = "weather_api_key"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)

    # ── Persistence ──────────────────────────────────────────────────

    def system(self) -> UnitSystem:
        raw = self._settings.value(self._KEY_SYSTEM, UnitSystem.METRIC.value)
        try:
            return UnitSystem(raw)
        except ValueError:
            return UnitSystem.METRIC

    def set_system(self, system: UnitSystem) -> None:
        if self.system() != system:
            self._settings.setValue(self._KEY_SYSTEM, system.value)
            self.changed.emit()

    def weather_api_key(self) -> str:
        """Get the WeatherAPI.com API key."""
        return self._settings.value(self._KEY_WEATHER_API_KEY, "")

    def set_weather_api_key(self, api_key: str) -> None:
        """Set the WeatherAPI.com API key."""
        self._settings.setValue(self._KEY_WEATHER_API_KEY, api_key)

    def is_imperial(self) -> bool:
        return self.system() == UnitSystem.IMPERIAL


    # ── Forward conversions (metric → display) ───────────────────────

    def convert_strength_mpa(self, mpa: float) -> float:
        """Convert MPa to the active strength unit."""
        if self.is_imperial():
            return mpa * _MPA_TO_PSI
        return mpa

    def convert_length_mm(self, mm: float) -> float:
        """Convert a length stored in mm to the active length unit.

        Metric always displays metres; imperial displays inches.
        """
        if self.is_imperial():
            return mm * _MM_TO_INCH
        return mm / 1000.0

    def convert_mass_kg(self, kg: float) -> float:
        """Convert kg to the active mass unit."""
        if self.is_imperial():
            return kg * _KG_TO_LB
        return kg

    def convert_volume_m3(self, m3: float) -> float:
        """Convert m³ to the active volume unit."""
        if self.is_imperial():
            return m3 * _M3_TO_YD3
        return m3

    def convert_density_kg_m3(self, kg_m3: float) -> float:
        """Convert kg/m³ to the active density unit."""
        if self.is_imperial():
            return kg_m3 * _KGM3_TO_LBFT3
        return kg_m3

    def convert_water_liters(self, liters: float) -> float:
        """Convert litres to the active water volume unit."""
        if self.is_imperial():
            return liters * _LITER_TO_GAL
        return liters

    # ── Inverse conversions (display → metric) ───────────────────────

    def to_metric_strength(self, value: float) -> float:
        """Convert from active strength unit back to MPa."""
        if self.is_imperial():
            return value / _MPA_TO_PSI
        return value

    def to_metric_length(self, value: float) -> float:
        """Convert from the active length unit (m or in) back to mm."""
        if self.is_imperial():
            return value / _MM_TO_INCH
        return value * 1000.0

    def to_metric_mass(self, value: float) -> float:
        """Convert from active mass unit back to kg."""
        if self.is_imperial():
            return value / _KG_TO_LB
        return value

    def to_metric_volume(self, value: float) -> float:
        """Convert from active volume unit back to m³."""
        if self.is_imperial():
            return value / _M3_TO_YD3
        return value

    # ── Unit label helpers ───────────────────────────────────────────

    def strength_unit(self) -> str:
        return "psi" if self.is_imperial() else "MPa"

    def length_unit(self) -> str:
        return "in" if self.is_imperial() else "m"

    def mass_unit(self) -> str:
        return "lb" if self.is_imperial() else "kg"

    def volume_unit(self) -> str:
        return "yd\u00b3" if self.is_imperial() else "m\u00b3"

    def density_unit(self) -> str:
        return "lb/ft\u00b3" if self.is_imperial() else "kg/m\u00b3"

    def mass_per_volume_unit(self) -> str:
        return "lb/yd\u00b3" if self.is_imperial() else "kg/m\u00b3"

    def water_unit(self) -> str:
        return "gal" if self.is_imperial() else "L"


# ── Module-level singleton ──────────────────────────────────────────────

_instance: UnitPreferences | None = None


def get_unit_prefs() -> UnitPreferences:
    """Return the global UnitPreferences singleton."""
    global _instance
    if _instance is None:
        _instance = UnitPreferences()
    return _instance
