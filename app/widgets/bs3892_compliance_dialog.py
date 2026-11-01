"""BS 3892-1:1997 pfa conformity dialog — laboratory quality checker.

Self-contained counterpart of the ASTM C33/IS 383 compliance reports: the
laboratory results for the pfa destined for a BRE 331 clause 9 mix are
entered against the grade BRE 331 clause 9.1 assumes ("the pfa is assumed
to comply with BS 3892:Part 1"), and every clause 5–12 requirement is
checked live with its clause citation. Fields left on the "—" sentinel are
treated as not tested (``not_evaluated``) and never fail the report.

Limits, Table G.3 major-defect allowances and the 15.4
acceptance-at-delivery equivalence all come from
``concrete_mix.validation.bs3892`` (extracted standard:
``BS-3892-1-1997-PFA-Specification.md``).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.widgets.frameless_dialog import FramelessDialog
from app.widgets.wrap_label import WrapLabel
from concrete_mix.validation.base import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    ClauseCheck,
)
from concrete_mix.validation.bs3892 import (
    BS3892LabResults,
    evaluate_bs3892_pfa,
    major_defects,
)

_STATUS_TEXT = {
    FAIL: "✗ NOT MET",
    PASS: "✓ Meets",
    NOT_EVALUATED: "— n/a",
}

# (BS3892LabResults field, label, min sentinel, max, decimals, suffix,
# tooltip). The range minimum doubles as the "not tested" sentinel and
# renders as "—" via specialValueText (the agg_rd_spin "Auto" pattern): a
# value of 0 % moisture is a real result, so percent fields sentinel at −1;
# density and setting times cannot be 0, so they sentinel at 0.
_FIELDS: tuple[tuple[str, str, float, float, int, str, str], ...] = (
    ("moisture_pct", "Moisture content (%)", -1.0, 10.0, 2, " %",
     "Clause 5 — ≤ 0.5 %. Oven-dried at (105 ± 5) °C for (60 ± 5) min "
     "(annex C); report to 0.1 %."),
    ("fineness_45um_pct", "Fineness — 45 µm sieve residue (%)", -1.0, 50.0, 2, " %",
     "Clause 6 — ≤ 12.0 %. Wet sieving on a calibrated 45 µm sieve, "
     "correction factor F = r₃/r₂ (annex D); report to 0.1 %."),
    ("particle_density_kg_m3", "Particle density (kg/m³)", 0.0, 4000.0, 0, "",
     "Clause 7 — ≥ 2000 kg/m³ (4.5.3 of BS EN 196-6 : 1992)."),
    ("water_requirement_pct", "Water requirement (%)", -1.0, 150.0, 1, " %",
     "Clause 8 — ≤ 95 % of the control mortar. Flow-table method on the "
     "30 % pfa : 70 % class 42.5 combination (annex E); report to 1 %."),
    ("strength_factor", "Strength factor (28 d)", 0.0, 1.50, 2, "",
     "Clause 9 — ≥ 0.80. Test/control 28-day mortar strengths of the "
     "clause 8 combination (annex F); report to 0.01. Absolute limit."),
    ("setting_time_paste_min", "Initial setting time — combination paste (min)",
     0.0, 720.0, 0, " min",
     "Clause 10 — not less than the Portland cement alone. Standard-"
     "consistence paste of the clause 8 combination (BS EN 196-3)."),
    ("setting_time_cement_min", "Initial setting time — reference cement (min)",
     0.0, 720.0, 0, " min",
     "Clause 10 reference: initial setting time of the Portland cement "
     "tested alone (BS EN 196-3)."),
    ("soundness_expansion_mm", "Soundness — expansion (mm)", -1.0, 50.0, 1, " mm",
     "Clause 11 — ≤ 10 mm expansion of the combination paste "
     "(BS EN 196-3)."),
    ("so3_pct", "Sulfuric anhydride SO₃ (%)", -1.0, 10.0, 2, " %",
     "Clause 12.1 — ≤ 2.0 % (m/m), clause 8 of BS EN 196-2 : 1995."),
    ("loi_pct", "Loss on ignition (%)", -1.0, 25.0, 2, " %",
     "Clause 12.2 — ≤ 7 % (m/m), clause 7 of BS EN 196-2 : 1995 with a "
     "1 h ignition. Absolute limit."),
    ("chloride_pct", "Chloride ion content (%)", -1.0, 2.0, 3, " %",
     "Clause 12.3 — ≤ 0.10 % (m/m), clause 4 of BS EN 196-21 : 1992."),
    ("cao_pct", "Calcium oxide content (%)", -1.0, 40.0, 2, " %",
     "Clause 12.4 — ≤ 10.0 % (m/m), clause 13 of BS EN 196-2 : 1995."),
)


class BS3892ComplianceDialog(FramelessDialog):
    """Live clause-by-clause conformity report for a pfa sample."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent, title="BS 3892-1:1997 pfa Conformity — Clauses 5–12"
        )
        self.resize(860, 640)
        self.setMinimumSize(700, 480)

        layout = self.content_layout
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._banner = WrapLabel("Enter the laboratory results to evaluate.")
        self._banner.setObjectName("info-banner")
        layout.addWidget(self._banner)

        # ── Laboratory inputs ──
        inputs_group = QGroupBox("Laboratory results — leave '—' if not tested")
        form = QFormLayout(inputs_group)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(6)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._minimums: dict[str, float] = {}
        for attr, label, lo, hi, dec, suffix, tip in _FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(dec)
            spin.setSingleStep(10.0 ** (-dec) if dec else 1.0)
            if suffix:
                spin.setSuffix(suffix)
            spin.setSpecialValueText("—")
            spin.setValue(lo)  # sentinel = not tested
            spin.setToolTip(tip)
            spin.setMinimumWidth(0)
            spin.valueChanged.connect(self._refresh)
            self._spins[attr] = spin
            self._minimums[attr] = lo
            form.addRow(QLabel(label), spin)
        inputs_scroll = QScrollArea()
        inputs_scroll.setWidgetResizable(True)
        inputs_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inputs_scroll.setWidget(inputs_group)
        inputs_scroll.setMaximumHeight(260)
        layout.addWidget(inputs_scroll)

        # ── Clause-by-clause report ──
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Status", "Clause", "Requirement", "Result / measured value"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table, 1)

        note = WrapLabel(
            "Limits follow BS 3892-1:1997 (extracted in "
            "BS-3892-1-1997-PFA-Specification.md) — the pfa grade BRE 331 "
            "clause 9.1 assumes for Portland cement/pfa mix design. A result "
            "outside a clause 5–12 value is a defect (G.3.3); one deviating "
            "by more than the Table G.3 allowance is a major defect and the "
            "lot does not conform (G.6). Acceptance inspection at delivery "
            "uses the same major-defect levels (15.4). Strength factor and "
            "loss on ignition are absolute limits (clause 1 NOTE). "
            "'— n/a' rows were not tested and are not failures."
        )
        note.setObjectName("dialog-note")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh()

    # ------------------------------------------------------------------
    # Live evaluation
    # ------------------------------------------------------------------

    def _collect(self) -> BS3892LabResults:
        values: dict[str, float | None] = {}
        for attr, _label, lo, _hi, _dec, _suffix, _tip in _FIELDS:
            value = self._spins[attr].value()
            values[attr] = None if value <= lo + 1e-12 else value
        return BS3892LabResults(**values)

    def _refresh(self) -> None:
        checks = evaluate_bs3892_pfa(self._collect())
        self._render(checks)

    def _render(self, checks: list[ClauseCheck]) -> None:
        failures = [c for c in checks if c.failed]
        majors = major_defects(checks)
        evaluated = [c for c in checks if c.status != NOT_EVALUATED]

        if majors:
            self._banner.setObjectName("compliance-failure-banner")
            self._banner.setText(
                f"⚠ {len(failures)} requirement(s) NOT met, including "
                f"{len(majors)} Table G.3 major defect(s) — the lot does "
                f"not conform to BS 3892-1:1997 (G.6)."
            )
            self._banner.setProperty("statusKind", "fail")
        elif failures:
            self._banner.setObjectName("compliance-failure-banner")
            self._banner.setText(
                f"⚠ {len(failures)} requirement(s) NOT met — outside the "
                f"clause 5–12 characteristic values, but within the "
                f"Table G.3 major-defect allowance."
            )
            self._banner.setProperty("statusKind", "fail")
        elif evaluated:
            self._banner.setObjectName("success-banner")
            self._banner.setText(
                f"✓ All {len(evaluated)} tested requirement(s) meet "
                f"BS 3892-1:1997."
            )
            self._banner.setProperty("statusKind", "pass")
        else:
            self._banner.setObjectName("info-banner")
            self._banner.setText(
                "Enter the laboratory results to evaluate — '—' fields are "
                "not tested and are not failures."
            )
            self._banner.setProperty("statusKind", "partial")
        # Repolish so the QSS objectName swap takes effect immediately.
        self._banner.style().unpolish(self._banner)
        self._banner.style().polish(self._banner)

        self._table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            status_item = QTableWidgetItem(_STATUS_TEXT[check.status])
            status_item.setForeground(
                Qt.GlobalColor.red
                if check.status == FAIL
                else Qt.GlobalColor.darkGreen
                if check.status == PASS
                else Qt.GlobalColor.gray
            )
            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 0, status_item)
            self._table.setItem(row, 1, QTableWidgetItem(check.clause))
            self._table.setItem(row, 2, QTableWidgetItem(check.requirement))
            self._table.setItem(row, 3, QTableWidgetItem(check.measured))
        self._table.resizeColumnsToContents()
        self._table.resizeRowsToContents()
