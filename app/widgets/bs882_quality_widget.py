"""BS 882 / BS 812 laboratory inputs, separate from ASTM quality controls."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QWidget,
)
from app.widgets.info_button import InfoButton
from concrete_mix.engine.bs812 import washed_fines_percent
from concrete_mix.validation.bs882 import BS882QualityInputs


class BS882QualityWidget(QGroupBox):
    """Record method and independent measured quality, never infer FI from PSD."""

    changed = pyqtSignal()
    stack_changed = pyqtSignal()

    # Per-field help, grounded in the extracted standards (BS 882:1992
    # Tables 3/4/6 §§4.2/5.1/5.2/5.4/App A; BS 812-103.1 §§6/7/8/10;
    # BS 812-105.1). Keys match the row attribute suffixes.
    _INFO = {
        "sample": (
            "Sample identification (BS 812-103.1 §10(a)).\n\n"
            "The test report must identify the sample and state whether a "
            "certificate of sampling is available. For compliance "
            "assessment also record the source (quarry/pit, BS 882 "
            "Appendix A) — grading and fines results are only meaningful "
            "against a known source."
        ),
        "method": (
            "Test method (BS 812-103.1 §7).\n\n"
            "§7.2 washing + sieving is the preferred method and must be "
            "used when the aggregate may contain clay or anything that "
            "agglomerates particles. §7.3 dry sieving is only for clean "
            "aggregates free of such material. The report must state which "
            "method was used (§10(c))."
        ),
        "m1": (
            "Original oven-dry mass M1 (BS 812-103.1 §6).\n\n"
            "Dry at 105 ± 5 °C to constant mass (within 0.1%) and weigh "
            "as M1; respect the Table 2 minimum test-portion mass for the "
            "nominal size. Every percentage retained/passing (§8) is "
            "computed against M1 — never against recovered sieve masses."
        ),
        "m2": (
            "Washed oven-dry residue M2 (BS 812-103.1 §7.2.1).\n\n"
            "After washing through the guarded 75 µm sieve until the water "
            "runs clear, dry the residue to constant mass as M2. Fines = "
            "M1 − M2 (§7.2.1.5). BS 882 Table 6 fines limits use this "
            "washing-only value — never the dry-sieve pan."
        ),
        "source": (
            "Aggregate source type (BS 882 §2.2 gravel/crushed rock, "
            "§2.3 sand; supplier details Appendix A).\n\n"
            "Selects the applicable limits: Table 6 fines (coarse 2% "
            "gravel / 4% rock; sand 4% gravel / 16% rock), flakiness §4.2 "
            "(50 uncrushed gravel, 40 crushed rock/gravel), and the 150 µm "
            "20% crushed-rock-fines footnote. Also maps to the BRE 331 "
            "§1.2.4 crushed/uncrushed type in mix design (partially "
            "crushed gravel has no single equivalent)."
        ),
        "heavy": (
            "Heavy-duty floor finish (BS 882 §5.2.2).\n\n"
            "Sand for heavy-duty floors must satisfy grading C or M — F "
            "is excluded. The crushed-rock-sand Table 6 limit drops from "
            "16% to 9%, and the 150 µm 20% crushed-rock relaxation does "
            "not apply."
        ),
        "extended": (
            "Extended BS 812 Table 1 sieve stack.\n\n"
            "Uses the full BS 812-103.1 Table 1 series (75 down to "
            "0.075 mm, exact BS apertures — never IS/ASTM near-"
            "equivalents) instead of just the Tables 3/4 grading sieves. "
            "Conformance is still checked only on the Table 3/4 sieves; "
            "extra sieves only refine the curve."
        ),
        "sieve75": (
            "Include the 75 µm sieve in a dry stack.\n\n"
            "Every washed analysis must end at the 75 µm sieve (§7.2.2.1 — "
            "preliminary separation never removes all sub-75 µm material, "
            "so it is sieved again dry). Fines assessment (Table 6) still "
            "needs the M1 − M2 washing value, not this sieve alone."
        ),
        "fi": (
            "Flakiness index by BS 812-105.1 (separate shape test).\n\n"
            "Gauged on the 6.3–63 mm fraction with the thickness gauge "
            "(flaky = thickness < 0.6 × mean sieve size); FI = 100 × M3/M2 "
            "to the nearest whole number. BS 882 §4.2: at most 50 for "
            "uncrushed gravel, 40 for crushed rock/gravel. It cannot be "
            "derived from PSD masses. Coarse aggregate only."
        ),
    }

    def __init__(self, parent=None) -> None:
        super().__init__("BS 882 / BS 812 laboratory record", parent)
        form = QFormLayout(self)
        self.method_combo = QComboBox()
        self.method_combo.addItem("Dry sieving — §7.3", "dry")
        self.method_combo.addItem("Washing + sieving — §7.2", "washed")
        self.sample_edit = QLineEdit()
        self.sample_edit.setPlaceholderText("Sample identification")
        self.m1_spin = self._mass_spin()
        self.m2_spin = self._mass_spin()
        self.m2_spin.setEnabled(False)
        self.source_combo = QComboBox()
        for label, key in (
            ("Not provided", "unknown"),
            ("Uncrushed gravel / sand", "uncrushed_gravel"),
            ("Partially crushed gravel / sand", "partially_crushed_gravel"),
            ("Crushed gravel / sand", "crushed_gravel"),
            ("Crushed rock / sand", "crushed_rock"),
        ):
            self.source_combo.addItem(label, key)
        self.heavy_check = QCheckBox("Heavy duty floor finish")
        self.extended_check = QCheckBox("Extended BS 812 Table 1 stack")
        self.sieve75_check = QCheckBox("Include 75 µm sieve")
        self.fi_spin = QDoubleSpinBox()
        self.fi_spin.setRange(-1, 100)
        self.fi_spin.setSpecialValueText("Not tested")
        self.fi_spin.setValue(-1)
        self.fi_spin.setSuffix(" %")
        self.fi_label = QLabel("Measured flakiness index")
        self._fi_row = self._label_row(self.fi_label, self._INFO["fi"])
        self.note = QLabel(
            "Dry sieving is suitable only when fines do not agglomerate. "
            "Table 6 washing fines use (M1 − M2) only, never the dry pan. "
            "FI is a separate BS 812-105.1 test; no shape calculator."
        )
        self.note.setWordWrap(True)
        self.checks_label = QLabel("Compute to evaluate BS 882 requirements.")
        self.checks_label.setWordWrap(True)
        form.addRow(self._label_row(QLabel("Sample"), self._INFO["sample"]),
                    self.sample_edit)
        form.addRow(self._label_row(QLabel("Method"), self._INFO["method"]),
                    self.method_combo)
        form.addRow(self._label_row(QLabel("Original dry mass M1"), self._INFO["m1"]),
                    self.m1_spin)
        form.addRow(self._label_row(QLabel("Washed dry mass M2"), self._INFO["m2"]),
                    self.m2_spin)
        form.addRow(self._label_row(QLabel("Material"), self._INFO["source"]),
                    self.source_combo)
        form.addRow(self._field_row(self.heavy_check, self._INFO["heavy"]))
        form.addRow(self._field_row(self.extended_check, self._INFO["extended"]))
        form.addRow(self._field_row(self.sieve75_check, self._INFO["sieve75"]))
        form.addRow(self._fi_row, self.fi_spin)
        form.addRow(self.note)
        form.addRow(self.checks_label)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        self.extended_check.toggled.connect(self.stack_changed.emit)
        self.sieve75_check.toggled.connect(self.stack_changed.emit)
        self.sample_edit.textChanged.connect(self.changed.emit)
        self.source_combo.currentIndexChanged.connect(self.changed.emit)
        for spin in (self.m1_spin, self.m2_spin, self.fi_spin):
            spin.valueChanged.connect(self.changed.emit)
        self.heavy_check.toggled.connect(self.changed.emit)

    @staticmethod
    def _mass_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10000000)
        spin.setDecimals(2)
        spin.setSuffix(" g")
        return spin

    def _method_changed(self) -> None:
        washed = self.method_combo.currentData() == "washed"
        self.m2_spin.setEnabled(washed)
        if washed:
            self.sieve75_check.blockSignals(True)
            self.sieve75_check.setChecked(True)
            self.sieve75_check.blockSignals(False)
        self.sieve75_check.setEnabled(not washed)
        self.stack_changed.emit()

    def set_fine(self, fine: bool) -> None:
        self.fi_spin.setVisible(not fine)
        self.fi_label.setVisible(not fine)
        self._fi_row.setVisible(not fine)

    @staticmethod
    def _label_row(label: QLabel, info: str) -> QWidget:
        """Label + 'i' button container for a form row (cf. PSD helper)."""
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(label)
        lay.addWidget(InfoButton(info))
        lay.addStretch()
        w = QWidget()
        w.setLayout(lay)
        return w

    @staticmethod
    def _field_row(field: QWidget, info: str) -> QWidget:
        """Checkbox + 'i' button for rows whose control carries its own text."""
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(field)
        lay.addWidget(InfoButton(info))
        lay.addStretch()
        w = QWidget()
        w.setLayout(lay)
        return w

    def metadata(self) -> dict:
        return {
            "sample_id": self.sample_edit.text(),
            "method": self.method_combo.currentData(),
            "original_dry_mass": self.m1_spin.value(),
            "washed_dry_mass": self.m2_spin.value(),
            "source_type": self.source_combo.currentData(),
            "heavy_duty_floor": self.heavy_check.isChecked(),
            "extended_stack": self.extended_check.isChecked(),
            "include_75um": self.sieve75_check.isChecked(),
            "flakiness_index_pct": (
                None if self.fi_spin.value() < 0 else self.fi_spin.value()
            ),
        }

    def quality_inputs(self) -> BS882QualityInputs:
        data = self.metadata()
        fines = None
        if data["method"] == "washed":
            fines = washed_fines_percent(
                data["original_dry_mass"], data["washed_dry_mass"]
            )
        return BS882QualityInputs(
            source_type=data["source_type"],
            heavy_duty_floor=data["heavy_duty_floor"],
            washed_fines_pct=fines,
            flakiness_index_pct=data["flakiness_index_pct"],
        )

    def restore(self, data: dict) -> None:
        self.sample_edit.setText(data.get("sample_id", ""))
        self.method_combo.setCurrentIndex(
            self.method_combo.findData(data.get("method", "dry"))
        )
        self.m1_spin.setValue(data.get("original_dry_mass", 0))
        self.m2_spin.setValue(data.get("washed_dry_mass", 0))
        source_index = self.source_combo.findData(data.get("source_type", "unknown"))
        self.source_combo.setCurrentIndex(max(0, source_index))
        self.heavy_check.setChecked(data.get("heavy_duty_floor", False))
        self.extended_check.setChecked(data.get("extended_stack", False))
        self.sieve75_check.setChecked(
            data.get("include_75um", False) or data.get("method") == "washed"
        )
        value = data.get("flakiness_index_pct")
        self.fi_spin.setValue(-1 if value is None else value)

    def show_checks(self, checks: list) -> None:
        self.checks_label.setText("\n".join(
            f"{check.status.replace('_', ' ').upper()} — "
            f"{check.clause}: {check.title}\n{check.requirement}\n"
            f"{check.measured} {check.detail}"
            for check in checks
        ))
