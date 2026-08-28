"""Unit-aware spinbox — the conversion boundary between UI and backend.

The backend always works in SI metric (MPa, mm, kg, m³, kg/m³, litres).
A ``UnitSpinBox`` stores its authoritative value in the metric unit the
backend expects and derives the displayed number, suffix, range and step
from the active :class:`~app.unit_preferences.UnitPreferences`.

Call contract:

- ``value()`` / ``setValue(v)`` operate in **metric** — every existing
  backend call site keeps working unconverted-in-metric, and programmatic
  writers (defaults, history loads, transfer handoffs) pass metric.
- ``display_value()`` / ``set_display_value(v)`` operate in the unit the
  user currently sees (what a typed edit produces).
- Unit-system changes re-derive the display from the stored metric value,
  so toggling preferences can never corrupt or clamp the underlying input.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QDoubleSpinBox

from app.unit_preferences import UnitPreferences, get_unit_prefs


# Display-unit factors: how many display units make one metric unit.
_F_VOLUME = 1.30795  # yd³ per m³
_F_MASS = 2.20462  # lb per kg
_F_WATER_1000 = 264.172  # gal per 1000 L


class _Kind:
    """Conversion + label rules for one quantity kind."""

    def __init__(
        self,
        to_display: Callable[[UnitPreferences, float], float],
        to_metric: Callable[[UnitPreferences, float], float],
        unit_label: Callable[[UnitPreferences], str],
        decimals_metric: int | None = None,
        decimals_imperial: int | None = None,
    ) -> None:
        self.to_display = to_display
        self.to_metric = to_metric
        self.unit_label = unit_label
        self.decimals_metric = decimals_metric
        self.decimals_imperial = decimals_imperial


_KINDS: dict[str, _Kind] = {
    # strength: metric base MPa
    "strength": _Kind(
        lambda up, v: up.convert_strength_mpa(v),
        lambda up, v: up.to_metric_strength(v),
        lambda up: up.strength_unit(),
        decimals_imperial=1,
    ),
    # length with mm metric base; metric shows m (currently unused — kept
    # for future mm-based fields whose magnitude suits metres)
    "length_mm": _Kind(
        lambda up, v: up.convert_length_mm(v),
        lambda up, v: up.to_metric_length(v),
        lambda up: up.length_unit(),
        decimals_metric=3,
        decimals_imperial=2,
    ),
    # slump: mm base unit; metric stays mm (metres are never used for slump),
    # imperial shows inches (1 in = 25.4 mm exactly)
    "slump": _Kind(
        lambda up, v: v / 25.4 if up.is_imperial() else v,
        lambda up, v: v * 25.4 if up.is_imperial() else v,
        lambda up: "in" if up.is_imperial() else "mm",
        decimals_metric=0,
        decimals_imperial=1,
    ),
    # length with metre metric base (element dimensions)
    "length_m": _Kind(
        lambda up, v: up.convert_length_mm(v * 1000.0),
        lambda up, v: up.to_metric_length(v) / 1000.0,
        lambda up: up.length_unit(),
        decimals_metric=3,
        decimals_imperial=2,
    ),
    "mass": _Kind(
        lambda up, v: up.convert_mass_kg(v),
        lambda up, v: up.to_metric_mass(v),
        lambda up: up.mass_unit(),
        decimals_imperial=1,
    ),
    "volume": _Kind(
        lambda up, v: up.convert_volume_m3(v),
        lambda up, v: up.to_metric_volume(v),
        lambda up: up.volume_unit(),
    ),
    # true density (kg/m³ ↔ lb/ft³)
    "density": _Kind(
        lambda up, v: up.convert_density_kg_m3(v),
        lambda up, v: v / 0.062428 if up.is_imperial() else v,
        lambda up: up.density_unit(),
        decimals_imperial=1,
    ),
    # mass per concrete volume (kg/m³ ↔ lb/yd³), e.g. cement content limits
    "mass_per_volume": _Kind(
        lambda up, v: v * 1.68555 if up.is_imperial() else v,
        lambda up, v: v / 1.68555 if up.is_imperial() else v,
        lambda up: up.mass_per_volume_unit(),
        decimals_imperial=1,
    ),
    # water volume (L ↔ gal)
    "water": _Kind(
        lambda up, v: up.convert_water_liters(v),
        lambda up, v: v / 0.264172 if up.is_imperial() else v,
        lambda up: up.water_unit(),
        decimals_imperial=2,
    ),
    # currency rates: price per metric unit ↔ price per display unit.
    # qty_display = qty_metric × F  ⟹  rate_display = rate_metric / F.
    "rate_volume": _Kind(
        lambda up, v: v / _F_VOLUME,
        lambda up, v: v * _F_VOLUME,
        lambda up: f"per {up.volume_unit()}",
    ),
    "rate_mass": _Kind(
        lambda up, v: v / _F_MASS,
        lambda up, v: v * _F_MASS,
        lambda up: f"per {up.mass_unit()}",
    ),
    "rate_water": _Kind(
        lambda up, v: v / _F_WATER_1000,
        lambda up, v: v * _F_WATER_1000,
        lambda up: "per 1000 gal",
    ),
}
# metric labels for the rate kinds (kind callables run against live prefs,
# so mirror the metric side explicitly)
_RATE_METRIC_LABELS = {
    "rate_volume": "per m³",
    "rate_mass": "per kg",
    "rate_water": "per 1000 L",
}


class UnitSpinBox(QDoubleSpinBox):
    """Spinbox whose ``value()`` is always in backend metric units."""

    def __init__(
        self,
        kind: str,
        default: float,
        lo: float,
        hi: float,
        step: float = 1.0,
        decimals: int = 2,
        prefix: str = "",
        parent=None,
    ) -> None:
        self._kind = _KINDS[kind]
        self._metric = float(default)
        self._lo_metric = float(lo)
        self._hi_metric = float(hi)
        self._step_metric = float(step)
        self._decimals = int(decimals)
        self._prefix = prefix
        self._syncing = False
        super().__init__(parent)
        self._prefs = get_unit_prefs()
        self._apply_unit_scales()
        self.valueChanged.connect(self._on_display_edited)
        self._prefs.changed.connect(self._on_prefs_changed)

    # ── Metric API (what backend-facing code must use) ──────────────

    def value(self) -> float:  # noqa: D102 - overrides QDoubleSpinBox
        return self._metric

    def metric_value(self) -> float:
        return self._metric

    def setValue(self, v: float) -> None:  # noqa: N802 - Qt naming
        self._metric = min(max(float(v), self._lo_metric), self._hi_metric)
        self._sync_display()

    def set_metric_value(self, v: float) -> None:
        self.setValue(v)

    # ── Display API (what the user sees/types) ──────────────────────

    def display_value(self) -> float:
        return super().value()

    def set_display_value(self, v: float) -> None:
        """Set the shown number exactly as if the user typed it."""
        super().setValue(float(v))

    def unit_label(self) -> str:
        if not self._prefs.is_imperial() and self._kind in _RATE_METRIC_LABELS:
            return _RATE_METRIC_LABELS[self._kind]
        return self._kind.unit_label(self._prefs)

    # ── Internals ───────────────────────────────────────────────────

    def _on_display_edited(self, display: float) -> None:
        if self._syncing:
            return
        metric = self._kind.to_metric(self._prefs, display)
        self._metric = min(max(metric, self._lo_metric), self._hi_metric)

    def _on_prefs_changed(self) -> None:
        self._apply_unit_scales()

    def _apply_unit_scales(self) -> None:
        self._syncing = True
        self.blockSignals(True)
        try:
            imperial = self._prefs.is_imperial()
            lo = self._kind.to_display(self._prefs, self._lo_metric)
            hi = self._kind.to_display(self._prefs, self._hi_metric)
            super().setRange(min(lo, hi), max(lo, hi))
            super().setSingleStep(self._kind.to_display(self._prefs, self._step_metric))
            decimals = self._decimals
            if imperial:
                if self._kind.decimals_imperial is not None:
                    decimals = self._kind.decimals_imperial
            elif self._kind.decimals_metric is not None:
                decimals = self._kind.decimals_metric
            super().setDecimals(decimals)
            super().setValue(self._kind.to_display(self._prefs, self._metric))
            if self._prefix:
                super().setPrefix(self._prefix)
            super().setSuffix(f" {self.unit_label()}")
        finally:
            self.blockSignals(False)
            self._syncing = False

    def _sync_display(self) -> None:
        self._syncing = True
        self.blockSignals(True)
        try:
            super().setValue(self._kind.to_display(self._prefs, self._metric))
        finally:
            self.blockSignals(False)
            self._syncing = False
