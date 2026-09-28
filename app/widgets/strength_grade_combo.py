"""Closed-set characteristic-strength selector.

The characteristic strength of a mix is not a free number: each code the app
implements defines a specific set of values it may take (see
:mod:`concrete_mix.codes.tables.strength_grades`). This widget makes that set
the *only* thing the user can choose, and repopulates it when the design
standard changes.

It deliberately keeps the metric-first API of
:class:`~app.widgets.unit_spin.UnitSpinBox` — ``value()`` is always metric
MPa, ``setValue(v)`` takes metric — so every backend-facing call site reads
exactly as it did when this was a spin box. Display units are handled by
re-rendering the item texts, never by converting the stored value.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from PyQt6.QtWidgets import QComboBox

from app.unit_preferences import get_unit_prefs
from app.widgets.psd_widget import _shrinkable_combo
from concrete_mix.codes.tables.strength_grades import (
    GradeOption,
    format_grade,
    grades_for_code,
    nearest_grade,
)

# Tolerance for matching a stored value back to a listed grade. The ACI grid
# stores psi x 0.00689476, so a value that came back from the engine as a
# float needs a little slack to land on its own row.
_MATCH_TOLERANCE_MPA = 1e-3


class StrengthGradeCombo(QComboBox):
    """Per-standard dropdown of selectable characteristic strengths.

    Signals:
        valueChanged(float): Emitted with the **metric MPa** value whenever
            the selection changes. Exists so callers wired to the old
            ``UnitSpinBox.valueChanged`` keep working untouched.
    """

    valueChanged = pyqtSignal(float)

    def __init__(self, code: str = "is10262", parent=None) -> None:
        super().__init__(parent)
        _shrinkable_combo(self)
        self.setToolTip("")
        self._code = code
        self._options: tuple[GradeOption, ...] = ()
        self._extra: GradeOption | None = None
        self._min_fc_mpa: float | None = None
        self._metric: float = 25.0
        self._prefs = get_unit_prefs()
        self.currentIndexChanged.connect(self._on_index_changed)
        self._prefs.changed.connect(self._on_prefs_changed)
        self._rebuild(preferred_mpa=self._metric)

    # ── Metric API (what backend-facing code must use) ──────────────

    def value(self) -> float:  # noqa: D102 - mirrors UnitSpinBox
        return self._metric

    def metric_value(self) -> float:
        """Alias of :meth:`value`, for call sites that spell it out."""
        return self._metric

    def setValue(self, v: float) -> None:  # noqa: N802 - Qt naming
        """Select ``v`` (metric MPa), adding it as a temporary item if the
        selected code does not offer it.

        The fallback matters for history restore: a record saved before the
        field became a dropdown may hold a strength no grade matches, and
        re-snapping it to a listed grade would silently change the design.
        Carrying the exact value as a marked extra item keeps such a record
        round-tripping to the same result.

        Args:
            v: Characteristic strength in metric MPa.
        """
        v = float(v)
        idx = self._index_of(v)
        if idx >= 0:
            self._select(idx)
            return
        # set_extra_value rebuilds with the value already selected.
        self.set_extra_value(v)

    def set_metric_value(self, v: float) -> None:
        """Alias of :meth:`setValue`, matching ``UnitSpinBox``."""
        self.setValue(v)

    # ── Population ──────────────────────────────────────────────────

    def populate(
        self,
        code: str,
        keep_value: bool = True,
        min_fc_mpa: float | None = None,
        extra_value: float | None = None,
    ) -> None:
        """Reload the grade list for ``code``.

        Args:
            code: "aci211", "is10262" or "doe".
            keep_value: Carry the current strength across the switch when the
                new code offers it. When it does not, land on the nearest
                grade the new code does offer — a standard switch is an
                explicit request to re-express the design in the new code.
            min_fc_mpa: Lowest strength the active exposure class allows.
                Grades below it are shown greyed out, not hidden, so the user
                can see that stronger options exist and why they are locked.
            extra_value: An off-list strength to offer as a temporary item
                (see :meth:`setValue`).
        """
        self._code = code
        self._min_fc_mpa = min_fc_mpa
        self._extra = None
        target = (
            extra_value
            if extra_value is not None
            else (self._metric if keep_value else None)
        )
        self._rebuild(preferred_mpa=target)

    def set_extra_value(self, v: float) -> None:
        """Offer ``v`` (metric MPa) as a marked, off-list item.

        Args:
            v: Characteristic strength in metric MPa.
        """
        self._extra = GradeOption(
            value_mpa=float(v),
            label_override=f"{float(v):.2f} MPa · saved record",
            clause="Not a grade of the selected code — carried from a saved record",
        )
        self._rebuild(preferred_mpa=self._extra.value_mpa)

    def set_minimum(self, min_fc_mpa: float | None) -> None:
        """Re-apply an exposure-driven grade floor.

        Never changes the current selection. If the selected grade drops
        below a newly chosen minimum it stays selected and greyed, and the
        engine rejects it at Calculate with its existing, more specific
        message — the same as if the user had typed the value by hand.
        Remapping silently would contradict that.

        Args:
            min_fc_mpa: Lowest allowed strength, or None for no floor.
        """
        self._min_fc_mpa = min_fc_mpa
        self._apply_gating()

    def current_grade(self) -> GradeOption | None:
        """The selected :class:`GradeOption`, or None if nothing is selected."""
        index = self.currentIndex()
        if 0 <= index < len(self._options):
            return self._options[index]
        return None

    # ── Internals ───────────────────────────────────────────────────

    def _index_of(self, mpa: float) -> int:
        for i, opt in enumerate(self._options):
            if abs(opt.value_mpa - mpa) <= _MATCH_TOLERANCE_MPA:
                return i
        return -1

    def _select(self, index: int) -> None:
        self.blockSignals(True)
        try:
            self.setCurrentIndex(index)
        finally:
            self.blockSignals(False)
        if 0 <= index < len(self._options):
            self._metric = self._options[index].value_mpa
            self.valueChanged.emit(self._metric)

    def _rebuild(self, preferred_mpa: float | None) -> None:
        """Rebuild items and select the best match for ``preferred_mpa``."""
        options = grades_for_code(self._code)
        if self._extra is not None and not any(
            abs(o.value_mpa - self._extra.value_mpa) <= _MATCH_TOLERANCE_MPA
            for o in options
        ):
            options = options + (self._extra,)
        self._options = options
        imperial = self._prefs.is_imperial()

        self.blockSignals(True)
        try:
            self.clear()
            for opt in self._options:
                self.addItem(format_grade(opt, imperial), opt.value_mpa)
        finally:
            self.blockSignals(False)

        index = -1
        if preferred_mpa is not None:
            index = self._index_of(preferred_mpa)
            if index < 0:
                nearest = nearest_grade(self._code, preferred_mpa)
                if nearest is not None:
                    index = self._index_of(nearest.value_mpa)
        if index < 0 and self._options:
            index = 0
        if index < 0:
            self._metric = 0.0
            return

        self.blockSignals(True)
        try:
            self.setCurrentIndex(index)
        finally:
            self.blockSignals(False)
        self._metric = self._options[index].value_mpa
        self._apply_gating()
        self.valueChanged.emit(self._metric)

    def _apply_gating(self) -> None:
        """Grey out grades the active exposure class forbids."""
        model = self.model()
        if model is None:
            return
        for i, opt in enumerate(self._options):
            item = model.item(i)
            if item is None:
                continue
            below = (
                self._min_fc_mpa is not None
                and opt is not self._extra
                and opt.value_mpa < self._min_fc_mpa - _MATCH_TOLERANCE_MPA
            )
            item.setEnabled(not below)
            item.setToolTip(
                f"{opt.clause}\n"
                f"Below the {self._min_fc_mpa:.1f} MPa minimum this exposure "
                f"class requires."
                if below
                else opt.clause
            )

    def _on_index_changed(self, _index: int) -> None:
        if 0 <= _index < len(self._options):
            self._metric = self._options[_index].value_mpa
        self.valueChanged.emit(self._metric)

    def _on_prefs_changed(self) -> None:
        """Re-render item text for the new display unit, selection intact."""
        imperial = self._prefs.is_imperial()
        for i, opt in enumerate(self._options):
            self.setItemText(i, format_grade(opt, imperial))
