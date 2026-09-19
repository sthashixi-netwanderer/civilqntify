"""DOE (BRE 331:1997 §6) Trial Mixes — batch schedule and feedback workbook.

Mirrors :class:`app.widgets.is_trial_mixes_dialog.ISTrialMixesDialog`:

1. Batch schedule (§6.1): design quantities scaled to the trial volume,
   optional w/c variant batches at the same water content, and BS 1881
   Part 125 moisture-condition batching (SSD / oven-dry / air-dried /
   surface-wet) with absorption-water corrections.
2. Trial feedback (§6.3): measured workability, fresh density and cube
   strength produce the Table 3 water guidance, the density-corrected
   unit proportions, the Figure 7 A/B/B′/C/D w/c adjustment, and a
   minor-adjustment / second-trial verdict with recomputed proportions.
3. §6.2 test checklist (BS 1881 parts) for the laboratory.

Trial records persist to history as ``doe_trial`` records chained to the
parent design record when its id is known.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from concrete_mix.codes.doe_trial import (
    MINOR_ADJUSTMENT_WC_LIMIT,
    calculate_doe_trial_batches,
    evaluate_doe_trial,
)
from concrete_mix.models.mix_result import MixDesignResult


class DOETrialMixesDialog(QDialog):
    """Dialog implementing the BRE 331:1997 §6 trial-mix workflow."""

    def __init__(
        self,
        result: MixDesignResult,
        inp: Any = None,
        design_calc_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("DOE (BRE 331:1997) §6 — Trial Mixes Workbook")
        self.resize(940, 760)
        self.setMinimumSize(760, 560)

        self._result = result
        self._inp = inp if inp is not None else getattr(result, "_input", None)
        self._design_calc_id = design_calc_id
        self._schedule: dict[str, Any] | None = None
        self._evaluation: dict[str, Any] | None = None

        self._build_ui()
        self._update_schedule()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_schedule_group())
        layout.addWidget(self._build_feedback_group())
        layout.addWidget(self._build_checklist_group())

        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        main_layout.addWidget(self._build_button_bar())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("result-card")
        header.setStyleSheet(
            "background-color: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 6px; padding: 10px;"
        )
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(4)

        title = QLabel("BRE 331:1997 §6 — Trial Mixes")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        h_layout.addWidget(title)

        desc = QLabel(
            "The design method gives proportions for concrete with approximately the required "
            "strength and workability — the trial mix checks that the selected materials behave "
            "as anticipated (§6). Batch the quantities below (typically 0.05 m³ for six 150 mm "
            "cubes plus slump/Vebe and density tests), test per §6.2, then enter the measured "
            "results to obtain the §6.3 adjustments: workability (Table 3), density correction "
            "of the unit proportions, and the Figure 7 water/cement adjustment."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #1e293b; line-height: 1.4;")
        h_layout.addWidget(desc)
        return header

    def _build_schedule_group(self) -> QGroupBox:
        group = QGroupBox("Trial Batch Schedule (§6.1)")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        # -- Controls row --
        controls = QHBoxLayout()
        controls.setSpacing(10)

        controls.addWidget(QLabel("Trial volume (m³):"))
        self._volume_spin = QDoubleSpinBox()
        self._volume_spin.setRange(0.005, 0.500)
        self._volume_spin.setSingleStep(0.005)
        self._volume_spin.setDecimals(3)
        self._volume_spin.setValue(0.05)
        self._volume_spin.setToolTip(
            "§6.1: 0.05 m³ is sufficient for six 150 mm cubes plus slump, "
            "Vebe and density measurements"
        )
        controls.addWidget(self._volume_spin)

        self._variants_chk = QCheckBox("Add ±w/c variant batches")
        self._variants_chk.setToolTip(
            "§6 intro: prepare two or more initial trial mixes with the "
            "same water content but different water/cement ratios to "
            "avoid delays if strength tests require a second mix"
        )
        self._variants_chk.toggled.connect(self._update_schedule)
        controls.addWidget(self._variants_chk)

        controls.addWidget(QLabel("w/c step:"))
        self._wc_step_spin = QDoubleSpinBox()
        self._wc_step_spin.setRange(0.01, 0.10)
        self._wc_step_spin.setSingleStep(0.01)
        self._wc_step_spin.setDecimals(2)
        self._wc_step_spin.setValue(0.05)
        self._wc_step_spin.valueChanged.connect(self._update_schedule)
        controls.addWidget(self._wc_step_spin)

        controls.addStretch()
        layout.addLayout(controls)

        controls2 = QHBoxLayout()
        controls2.setSpacing(10)
        controls2.addWidget(QLabel("Aggregate moisture condition (BS 1881 Part 125):"))
        self._moisture_combo = QComboBox()
        self._moisture_combo.addItem("Saturated surface-dry (design basis)", "ssd")
        self._moisture_combo.addItem("Oven-dry", "oven_dry")
        self._moisture_combo.addItem("Air-dried", "air_dried")
        self._moisture_combo.addItem("Surface-wet / saturated", "surface_wet")
        self._moisture_combo.currentIndexChanged.connect(self._update_schedule)
        controls2.addWidget(self._moisture_combo)
        controls2.addStretch()
        layout.addLayout(controls2)

        # -- Batch table --
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Trial Batch",
            "W/C",
            "Cement (kg)",
            "Water added (kg)",
            "Fine Agg (kg)",
            "Coarse Agg (kg)",
            "Admixture (kg)",
        ])
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):
            self._table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setMinimumHeight(150)
        layout.addWidget(self._table)

        self._schedule_note = QLabel()
        self._schedule_note.setWordWrap(True)
        self._schedule_note.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(self._schedule_note)
        return group

    def _build_feedback_group(self) -> QGroupBox:
        group = QGroupBox("Trial Results & §6.3 Adjustments")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        def _spin(suffix: str, lo: float, hi: float, step: float, dec: int, tip: str) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(dec)
            s.setSpecialValueText("—")
            s.setToolTip(tip)
            return s

        lbl_w = QLabel("Water actually added (kg):")
        lbl_w.setToolTip("Total mixing water added to the trial batch")
        form_row.addWidget(lbl_w)
        self._actual_water_spin = _spin("", 0.0, 100.0, 0.1, 1, "Total water added to the trial batch (kg)")
        form_row.addWidget(self._actual_water_spin)

        form_row.addWidget(QLabel("Measured slump (mm):"))
        self._slump_spin = _spin("", 0.0, 250.0, 5.0, 0, "Slump of the trial mix (BS 1881:Part 102)")
        form_row.addWidget(self._slump_spin)

        form_row.addWidget(QLabel("Vebe (s):"))
        self._vebe_spin = _spin("", 0.0, 50.0, 0.5, 1, "Vebe time of the trial mix (BS 1881:Part 104)")
        form_row.addWidget(self._vebe_spin)

        layout.addLayout(form_row)

        form_row2 = QHBoxLayout()
        form_row2.setSpacing(10)
        form_row2.addWidget(QLabel("Fresh density (kg/m³):"))
        self._density_spin = _spin("", 0.0, 3000.0, 10.0, 0, "Density of the fully compacted fresh concrete (BS 1881:Part 107)")
        form_row2.addWidget(self._density_spin)

        form_row2.addWidget(QLabel("Mean cube strength (MPa):"))
        self._strength_spin = _spin("", 0.0, 120.0, 0.5, 1, "Mean compressive strength of the trial cubes (BS 1881:Part 116)")
        form_row2.addWidget(self._strength_spin)

        form_row2.addWidget(QLabel("Test age (days):"))
        self._age_spin = QSpinBox()
        self._age_spin.setRange(3, 91)
        self._age_spin.setValue(int(getattr(self._inp, "age_days", 28) or 28) if self._inp is not None else 28)
        self._age_spin.setToolTip("Age of the cubes at test — Table 2 reference strengths cover 3/7/28/91 days")
        form_row2.addWidget(self._age_spin)

        self._calc_btn = QPushButton("Calculate Adjustments")
        self._calc_btn.setObjectName("primary")
        self._calc_btn.clicked.connect(self._on_calculate)
        form_row2.addWidget(self._calc_btn)
        layout.addLayout(form_row2)

        self._eval_result = QLabel()
        self._eval_result.setWordWrap(True)
        self._eval_result.setTextFormat(Qt.TextFormat.RichText)
        self._eval_result.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.45;")
        self._eval_result.setVisible(False)
        layout.addWidget(self._eval_result)
        return group

    def _build_checklist_group(self) -> QGroupBox:
        group = QGroupBox("Tests on Trial Mixes — §6.2 Checklist")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(6)

        intro = QLabel(
            "Tests on the fresh concrete, specimen making, curing and testing follow BS 1881. "
            "Record the actual water/cement ratio used, the fresh density and all cube results."
        )
        intro.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        from concrete_mix.codes.doe_trial import TEST_CHECKLIST
        self._checklist_boxes: list[QCheckBox] = []
        for test, standard in TEST_CHECKLIST:
            chk = QCheckBox(f"{test} — {standard}")  # QCheckBox is plain-text: no rich-text tags
            chk.setChecked(True)
            chk.setStyleSheet("QCheckBox { font-size: 12px; color: #1e293b; }")
            layout.addWidget(chk)
            self._checklist_boxes.append(chk)
        return group

    def _build_button_bar(self) -> QWidget:
        bar = QWidget()
        btn_bar = QHBoxLayout(bar)
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(8)

        btn_save = QPushButton("Save Trial Record")
        btn_save.setObjectName("secondary")
        btn_save.clicked.connect(self._save_trial_record)
        btn_bar.addWidget(btn_save)

        btn_copy = QPushButton("Copy Schedule to Clipboard")
        btn_copy.setObjectName("secondary")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_bar.addWidget(btn_copy)

        btn_csv = QPushButton("Export Workbook (CSV)")
        btn_csv.setObjectName("secondary")
        btn_csv.clicked.connect(self._export_csv)
        btn_bar.addWidget(btn_csv)

        btn_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)
        return bar

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    def _update_schedule(self) -> None:
        try:
            self._schedule = calculate_doe_trial_batches(
                self._result,
                self._inp,
                volume_m3=self._volume_spin.value(),
                wc_step=self._wc_step_spin.value(),
                include_variants=self._variants_chk.isChecked(),
                moisture_condition=self._moisture_combo.currentData(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Trial Schedule", str(e))
            return
        self._fill_schedule_table()
        self._update_schedule_note()

    def _fill_schedule_table(self) -> None:
        sched = self._schedule
        batches = sched["batches"]
        self._table.setRowCount(len(batches))
        condition = sched["moisture_condition"]
        for row, b in enumerate(batches):
            name_item = QTableWidgetItem(b["name"])
            tips = "\n".join(b["notes"]) if b["notes"] else ""
            per_m3 = b["per_m3"]
            name_item.setToolTip(
                (f"Per m³: cement {per_m3['cement']:.0f}, water {per_m3['water']:.0f}, "
                 f"fine {per_m3['fine_agg']:.0f}, coarse {per_m3['coarse_agg']:.0f} kg"
                 + (f"\n{tips}" if tips else ""))
            )
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(f"{b['w_c_ratio']:.2f}"))

            bt = b["batch"]
            fa_txt = f"{bt['fine_agg']:.1f}"
            ca_txt = f"{bt['coarse_agg']:.1f}"
            if condition in ("oven_dry", "air_dried") and b["dry_aggregate_kg"]:
                fa_txt = f"{b['dry_aggregate_kg']['fine_agg']:.1f} (dry)"
                ca_txt = f"{b['dry_aggregate_kg']['coarse_agg']:.1f} (dry)"
            split = bt.get("ca_split") or (self._result.ca_split_kg if row == 0 else None)
            if split and row == 0:
                ca_parts = ", ".join(f"{sz}: {m * sched['volume_m3']:.1f} kg" for sz, m in split.items())
                ca_txt += f"  [{ca_parts}]"

            values = [
                f"{bt['cement']:.1f}",
                f"{b['added_water_kg']:.1f}",
                fa_txt,
                ca_txt,
                f"{bt['admixture']:.2f}" if bt["admixture"] > 0 else "—",
            ]
            for col, txt in enumerate(values, start=2):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row, col, item)

    def _update_schedule_note(self) -> None:
        sched = self._schedule
        condition = sched["moisture_condition"]
        parts: list[str] = []
        if condition in ("oven_dry", "air_dried"):
            parts.append(
                "Dry batching: aggregates ×100/(100+A), mixing water increased by the "
                "absorbed mass (§6.1). Soak the aggregates with about half the mixing "
                "water before adding cement (BS 1881 Part 125)."
            )
        elif condition == "surface_wet":
            parts.append(
                "Surface-wet aggregates: the free water on the aggregates is deducted "
                "from the water added at the mixer (§6.1)."
            )
        else:
            parts.append(
                "Design quantities are saturated surface-dry (SSD) batch masses (§6.1)."
            )
        for w in sched["warnings"]:
            parts.append(f"⚠ {w}")
        self._schedule_note.setText("  ".join(parts))

    # ------------------------------------------------------------------
    # §6.3 evaluation
    # ------------------------------------------------------------------

    def _collect_measurements(self) -> dict[str, Any]:
        measurements: dict[str, Any] = {"volume_m3": self._volume_spin.value()}
        if self._actual_water_spin.value() > 0:
            measurements["actual_water_kg"] = self._actual_water_spin.value()
        if self._slump_spin.value() > 0:
            measurements["measured_slump_mm"] = self._slump_spin.value()
        if self._vebe_spin.value() > 0:
            measurements["measured_vebe_s"] = self._vebe_spin.value()
        if self._density_spin.value() > 0:
            measurements["measured_density_kg_m3"] = self._density_spin.value()
        if self._strength_spin.value() > 0:
            measurements["cube_strength_mpa"] = self._strength_spin.value()
        measurements["test_age_days"] = self._age_spin.value()
        return measurements

    def _on_calculate(self) -> None:
        try:
            self._evaluation = evaluate_doe_trial(self._result, self._inp, self._collect_measurements())
        except ValueError as e:
            QMessageBox.warning(self, "Trial Evaluation", str(e))
            return
        self._render_evaluation()

    def _render_evaluation(self) -> None:
        ev = self._evaluation
        html_parts: list[str] = []

        # Workability (§6.3.1)
        wk = ev["workability"]
        if wk["provided"]:
            html_parts.append("<b>Workability (§6.3.1):</b>")
            html_parts.append(
                f"<ul><li>Specified: {wk['design_label']}"
                + (f" — measured: {wk['measured_label']}" if wk["measured_label"] else "")
                + "</li></ul>"
            )
            for g in wk["guidance"]:
                html_parts.append(f"<div style='margin-left:14px;'>• {g}</div>")

        # Density (§6.3.2)
        dn = ev["density"]
        if dn["provided"]:
            html_parts.append("<b>Density correction (§6.3.2):</b>")
            html_parts.append(
                f"<ul><li>Measured {dn['measured']:.0f} kg/m³ vs assumed "
                f"{dn['assumed']:.0f} kg/m³ → factor {dn['factor']:.4f}</li>"
                f"<li>Actual unit proportions of the trial mix (per m³): "
                f"cement {dn['corrected_per_m3']['cement']:.0f}"
                + (f" + SCM {dn['corrected_per_m3']['scm']:.0f}" if dn['corrected_per_m3']['scm'] else "")
                + f", water {dn['corrected_per_m3']['water']:.0f}, fine "
                f"{dn['corrected_per_m3']['fine_agg']:.0f}, coarse "
                f"{dn['corrected_per_m3']['coarse_agg']:.0f} kg</li></ul>"
            )

        # Strength (§6.3.3)
        st = ev["strength"]
        if st["provided"]:
            html_parts.append("<b>Strength — Figure 7 adjustment (§6.3.3):</b>")
            html_parts.append(
                f"<ul><li>A — Table 2 reference strength at w/c 0.5 "
                f"({st['age_days']} d): <b>{st['A']:.0f}</b> N/mm²</li>"
                f"<li>B — designed w/c: <b>{st['B']:.2f}</b>"
                + (f"; B′ — actual trial w/c: <b>{st['B_prime']:.2f}</b>"
                    if abs(st["B_prime"] - st["B"]) > 0.005 else
                    f"; B′ = B (no water adjustment during the trial)")
                + f"</li><li>C — measured cube strength: <b>{st['C']:.1f}</b> N/mm² "
                f"(target mean {st['target_mean']:.0f})</li>"
                f"<li>D — new w/c estimate for the target mean: <b>{st['D']:.2f}</b></li></ul>"
            )
            vd = ev["verdict"]
            if vd["decision"] == "minor":
                colour, bg = "#166534", "#dcfce7"
            else:
                colour, bg = "#92400e", "#fef3c7"
            html_parts.append(
                f"<div style='background-color:{bg}; border:1px solid {colour}33; "
                f"border-radius:6px; padding:8px; color:{colour};'><b>"
                + ("✓ " if vd["decision"] == "minor" else "⚠ ")
                + f"{vd['text']}</b></div>"
            )

        # Revised proportions
        rv = ev["revised"]
        if rv:
            pm = rv["per_m3"]
            title = (
                "Revised production proportions (per m³, SSD)"
                if rv["basis"] == "production"
                else "Second trial mix at w/c "
                     f"{rv['w_c_ratio']:.2f} — unit proportions (per m³)"
            )
            html_parts.append(f"<b>{title}:</b>")
            parts = [
                f"cement {pm['cement']:.0f}",
                f"water {pm['water']:.0f}",
                f"fine {pm['fine_agg']:.0f}",
                f"coarse {pm['coarse_agg']:.0f}",
            ]
            if pm["scm"]:
                parts.insert(1, f"SCM {pm['scm']:.0f}")
            if pm["admixture"]:
                parts.append(f"admixture {pm['admixture']:.2f}")
            if pm["ca_split"]:
                parts.append("CA split " + " + ".join(f"{sz} {m:.0f}" for sz, m in pm["ca_split"].items()))
            html_parts.append(
                f"<div style='margin-left:14px;'>" + ", ".join(parts) + " kg"
                + (f" (density basis {rv['density_basis']:.0f} kg/m³)"
                   if rv["density_basis"] else "")
                + (f"; water {'+' if rv['water_delta_kg_m3'] >= 0 else '−'}{abs(rv['water_delta_kg_m3']):.0f} kg/m³ per Table 3 workability adjustment" if rv["water_delta_kg_m3"] else "")
                + f"; Figure 6 fine proportion {rv['fine_proportion_pct']:.1f}%</div>"
            )

        for w in ev["warnings"]:
            html_parts.append(f"<div style='color:#b45309;'>⚠ {w}</div>")

        self._eval_result.setText("".join(html_parts))
        self._eval_result.setVisible(True)

    # ------------------------------------------------------------------
    # Export / persistence
    # ------------------------------------------------------------------

    def _schedule_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._schedule:
            return rows
        for b in self._schedule["batches"]:
            bt = b["batch"]
            row = {
                "batch": b["name"],
                "wc": b["w_c_ratio"],
                "cement_kg": bt["cement"],
                "water_added_kg": b["added_water_kg"],
                "fine_agg_kg": bt["fine_agg"],
                "coarse_agg_kg": bt["coarse_agg"],
                "admixture_kg": bt["admixture"],
                "dry_fine_agg_kg": (b["dry_aggregate_kg"] or {}).get("fine_agg"),
                "dry_coarse_agg_kg": (b["dry_aggregate_kg"] or {}).get("coarse_agg"),
                "absorption_water_kg": b["absorption_water_kg"],
                "free_water_kg": b["free_water_kg"],
                "notes": " | ".join(b["notes"]),
            }
            rows.append(row)
        return rows

    def _copy_to_clipboard(self) -> None:
        if not self._schedule:
            return
        buf = io.StringIO()
        buf.write("BRE 331:1997 §6 — DOE Trial Mixes Schedule\n")
        buf.write("=" * 60 + "\n")
        buf.write(f"Trial volume: {self._volume_spin.value():.3f} m³\n")
        for row in self._schedule_rows():
            buf.write(f"\n[{row['batch']}]  w/c {row['wc']:.2f}\n")
            buf.write(f"  Cement:      {row['cement_kg']:.1f} kg\n")
            buf.write(f"  Water added: {row['water_added_kg']:.1f} kg\n")
            buf.write(f"  Fine Agg:    {row['fine_agg_kg']:.1f} kg\n")
            buf.write(f"  Coarse Agg:  {row['coarse_agg_kg']:.1f} kg\n")
            if row["admixture_kg"]:
                buf.write(f"  Admixture:   {row['admixture_kg']:.2f} kg\n")
            if row["dry_fine_agg_kg"] is not None:
                buf.write(f"  Oven-dry FA/CA: {row['dry_fine_agg_kg']:.1f} / {row['dry_coarse_agg_kg']:.1f} kg, absorption water {row['absorption_water_kg']:.1f} kg\n")
            if row["notes"]:
                buf.write(f"  Notes: {row['notes']}\n")

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(buf.getvalue())
            QMessageBox.information(
                self, "Copied to Clipboard",
                "DOE trial mixes schedule copied to clipboard.",
            )

    def _export_csv(self) -> None:
        if not self._schedule:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export DOE Trial Mixes to CSV",
            "doe_trial_mixes.csv", "CSV Files (*.csv)",
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Standard", "BRE 331:1997 §6 Trial Mixes"])
                writer.writerow(["Target mean strength (MPa)", self._result.target_mean_strength_mpa])
                writer.writerow(["Design w/c", self._result.w_c_ratio])
                writer.writerow(["Trial volume (m3)", self._volume_spin.value()])
                writer.writerow(["Moisture condition", self._schedule["moisture_condition"]])
                writer.writerow([])
                writer.writerow([
                    "Batch", "W/C", "Cement (kg)", "Water added (kg)",
                    "Fine Agg (kg)", "Coarse Agg (kg)", "Admixture (kg)",
                    "Dry Fine Agg (kg)", "Dry Coarse Agg (kg)",
                    "Absorption water (kg)", "Free water (kg)", "Notes",
                ])
                for row in self._schedule_rows():
                    writer.writerow([
                        row["batch"], row["wc"], row["cement_kg"],
                        row["water_added_kg"], row["fine_agg_kg"],
                        row["coarse_agg_kg"], row["admixture_kg"],
                        row["dry_fine_agg_kg"], row["dry_coarse_agg_kg"],
                        row["absorption_water_kg"], row["free_water_kg"],
                        row["notes"],
                    ])
                ev = self._evaluation
                if ev:
                    writer.writerow([])
                    writer.writerow(["§6.3 Trial Evaluation"])
                    st = ev["strength"]
                    if st["provided"]:
                        writer.writerow([
                            "Figure 7", f"A={st['A']}", f"B={st['B']}",
                            f"B'={st['B_prime']}", f"C={st['C']}", f"D={st['D']}",
                        ])
                        writer.writerow(["Verdict", ev["verdict"]["text"]])
                    rv = ev["revised"]
                    if rv:
                        pm = rv["per_m3"]
                        writer.writerow([
                            "Revised proportions (kg/m3)",
                            f"w/c={rv['w_c_ratio']}",
                            f"cement={pm['cement']}", f"scm={pm['scm']}",
                            f"water={pm['water']}", f"fine={pm['fine_agg']}",
                            f"coarse={pm['coarse_agg']}",
                        ])
            QMessageBox.information(
                self, "Export Successful",
                f"Trial mixes exported successfully to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export CSV:\n{e}")

    def _save_trial_record(self) -> None:
        from history.db import get_db

        try:
            db = get_db()
            trial_input: dict[str, Any] = {
                "code": "doe",
                "design_target_mean_mpa": self._result.target_mean_strength_mpa,
                "design_w_c_ratio": self._result.w_c_ratio,
                "design_cement_kg": self._result.cement_kg,
                "design_scm_kg": self._result.scm_kg,
                "design_water_kg": self._result.water_kg,
                "design_fine_agg_kg": self._result.fine_aggregate_kg,
                "design_coarse_agg_kg": self._result.coarse_aggregate_kg,
                "trial_volume_m3": self._volume_spin.value(),
                "wc_step": self._wc_step_spin.value(),
                "include_variants": self._variants_chk.isChecked(),
                "moisture_condition": self._moisture_combo.currentData(),
                "measurements": self._collect_measurements(),
            }
            trial_result: dict[str, Any] = {
                "batches": self._schedule_rows(),
                "warnings": list(self._schedule["warnings"]) if self._schedule else [],
                "minor_adjustment_wc_limit": MINOR_ADJUSTMENT_WC_LIMIT,
            }
            if self._evaluation:
                ev = self._evaluation
                st = ev["strength"]
                trial_result["figure7"] = {
                    "A": st["A"], "B": st["B"], "B_prime": st["B_prime"],
                    "C": st["C"], "D": st["D"], "age_days": st["age_days"],
                }
                trial_result["verdict"] = ev["verdict"]
                trial_result["workability"] = ev["workability"]
                trial_result["density"] = ev["density"]
                if ev["revised"]:
                    trial_result["revised_per_m3"] = ev["revised"]["per_m3"]
                    trial_result["revised_wc"] = ev["revised"]["w_c_ratio"]
                trial_result["warnings"] = (
                    list(self._schedule["warnings"]) if self._schedule else []
                ) + list(ev["warnings"])
            calc_id = db.save_doe_trial(
                trial_input, trial_result,
                name=f"DOE Trial — {self._result.target_mean_strength_mpa:.0f} MPa target",
                parent_id=self._design_calc_id,
            )
            QMessageBox.information(
                self, "Trial Record Saved",
                f"DOE trial record #{calc_id} saved to history"
                + (" and linked to the parent design." if self._design_calc_id else "."),
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save trial record:\n{e}")
