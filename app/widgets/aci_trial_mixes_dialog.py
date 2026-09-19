"""ACI PRC-211.1-22 trial mixes — batch schedule and post-trial workbook.

Mirrors :class:`app.widgets.doe_trial_mixes_dialog.DOETrialMixesDialog`:

1. Batch weight summary (§5.3.9, Table 5.3.9.1): design-SSD vs. batched
   weights with the (1+MC%)/(1+A%) moisture adjustment, free water, and
   water to batch; optional Appendix A.5 trial-series mixtures (cement
   contents above/below design at constant water).
2. Post-trial adjustments (§5.3.10): the free-water reversal, relative
   yield and gravimetric air (ASTM C138), Adjustments 1–3, and the
   §5.3.10.4 next-trial proportions.
3. ASTM test checklist (Chapter 8 / §5.3.10) and the Table 8 adjustment
   guidance.

Trial records persist to history as ``aci_trial`` records chained to the
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

from concrete_mix.codes.aci_trial import (
    RELATIVE_YIELD_TOLERANCE,
    calculate_aci_trial_batches,
    evaluate_aci_trial,
)
from concrete_mix.models.mix_result import MixDesignResult


class ACITrialMixesDialog(QDialog):
    """Dialog implementing the ACI PRC-211.1-22 trial-batching workflow."""

    def __init__(
        self,
        result: MixDesignResult,
        inp: Any = None,
        design_calc_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACI PRC-211.1-22 — Trial Batching Workbook")
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

        title = QLabel("ACI PRC-211.1-22 — Trial Batching (Ch. 8, §5.3.9–5.3.10)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        h_layout.addWidget(title)

        desc = QLabel(
            "Trial batching demonstrates that the proportions produce the required properties "
            "(§4.1). Batch per ASTM C192 with the §5.3.9.1 moisture adjustments below, test per "
            "ASTM C143/C138/C173/C231, then enter the measured results to obtain the §5.3.10 "
            "post-trial adjustments and the recalculated proportions for the next trial."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #1e293b; line-height: 1.4;")
        h_layout.addWidget(desc)
        return header

    def _build_schedule_group(self) -> QGroupBox:
        group = QGroupBox("Batch Weight Summary (§5.3.9, Table 5.3.9.1)")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Trial volume (m³):"))
        self._volume_spin = QDoubleSpinBox()
        self._volume_spin.setRange(0.005, 0.500)
        self._volume_spin.setSingleStep(0.005)
        self._volume_spin.setDecimals(4)
        self._volume_spin.setValue(0.05)
        self._volume_spin.setToolTip(
            "§9.2.9's reference trial is 1 ft³ (0.0283 m³); any volume works — "
            "quantities scale linearly"
        )
        controls.addWidget(self._volume_spin)

        self._series_chk = QCheckBox("Add A.5 trial series (±cementitious)")
        self._series_chk.setToolTip(
            "Appendix A.5 / three-point curve: mixtures above and below the "
            "design cement content at the same water establish the "
            "w/cm–strength relationship for the project materials"
        )
        self._series_chk.toggled.connect(self._update_schedule)
        controls.addWidget(self._series_chk)

        controls.addWidget(QLabel("Cement step (%):"))
        self._cem_step_spin = QDoubleSpinBox()
        self._cem_step_spin.setRange(1.0, 50.0)
        self._cem_step_spin.setSingleStep(1.0)
        self._cem_step_spin.setDecimals(0)
        self._cem_step_spin.setValue(10.0)
        self._cem_step_spin.valueChanged.connect(self._update_schedule)
        controls.addWidget(self._cem_step_spin)
        controls.addStretch()
        layout.addLayout(controls)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Mixture",
            "w/cm",
            "Water to batch (kg)",
            "Cementitious (kg)",
            "Fine Agg batched (kg)",
            "Coarse Agg batched (kg)",
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
        group = QGroupBox("Trial Results & §5.3.10 Post-Trial Adjustments")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        def _spin(lo: float, hi: float, step: float, dec: int, tip: str) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(dec)
            s.setSpecialValueText("—")
            s.setToolTip(tip)
            return s

        row1.addWidget(QLabel("Water actually added (kg):"))
        self._actual_water_spin = _spin(0.0, 100.0, 0.1, 1, "Water added to the trial batch at the mixer")
        row1.addWidget(self._actual_water_spin)
        row1.addWidget(QLabel("Batched Fine Agg (kg):"))
        self._batched_fa_spin = _spin(0.0, 200.0, 0.1, 1, "Moist fine aggregate actually batched (blank = scheduled)")
        row1.addWidget(self._batched_fa_spin)
        row1.addWidget(QLabel("Batched Coarse Agg (kg):"))
        self._batched_ca_spin = _spin(0.0, 300.0, 0.1, 1, "Moist coarse aggregate actually batched (blank = scheduled)")
        row1.addWidget(self._batched_ca_spin)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("Measured slump (mm):"))
        self._slump_spin = _spin(0.0, 250.0, 5.0, 0, "ASTM C143/C143M")
        row2.addWidget(self._slump_spin)
        row2.addWidget(QLabel("Fresh density (kg/m³):"))
        self._density_spin = _spin(0.0, 3000.0, 10.0, 0, "ASTM C138/C138M — density and yield")
        row2.addWidget(self._density_spin)
        row2.addWidget(QLabel("Air content (%):"))
        self._air_spin = _spin(0.0, 15.0, 0.1, 1, "ASTM C231/C231M or C173/C173M")
        row2.addWidget(self._air_spin)
        row2.addWidget(QLabel("Strength (MPa):"))
        self._strength_spin = _spin(0.0, 120.0, 0.5, 1, "Compressive strength of the trial specimens")
        row2.addWidget(self._strength_spin)
        row2.addWidget(QLabel("Age (d):"))
        self._age_spin = QSpinBox()
        self._age_spin.setRange(1, 91)
        self._age_spin.setValue(28)
        row2.addWidget(self._age_spin)

        self._calc_btn = QPushButton("Calculate Adjustments")
        self._calc_btn.setObjectName("primary")
        self._calc_btn.clicked.connect(self._on_calculate)
        row2.addWidget(self._calc_btn)
        layout.addLayout(row2)

        self._eval_result = QLabel()
        self._eval_result.setWordWrap(True)
        self._eval_result.setTextFormat(Qt.TextFormat.RichText)
        self._eval_result.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.45;")
        self._eval_result.setVisible(False)
        layout.addWidget(self._eval_result)
        return group

    def _build_checklist_group(self) -> QGroupBox:
        group = QGroupBox("Trial Batch Tests — ASTM Checklist (Ch. 8 / §5.3.10)")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(6)

        intro = QLabel(
            "Execute trial batches per ASTM C192/C192M with tests by certified personnel; "
            "proper curing is essential for reproducible results. Record the water actually "
            "added, the batched aggregate masses, slump, density/yield, air content and strengths."
        )
        intro.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        from concrete_mix.codes.aci_trial import TEST_CHECKLIST
        self._checklist_boxes: list[QCheckBox] = []
        for test, standard in TEST_CHECKLIST:
            chk = QCheckBox(f"{test} — {standard}")  # QCheckBox is plain-text: no rich-text tags
            chk.setChecked(True)
            chk.setStyleSheet("QCheckBox { font-size: 12px; color: #1e293b; }")
            layout.addWidget(chk)
            self._checklist_boxes.append(chk)

        t8 = QLabel(self._schedule_table8_text())
        t8.setWordWrap(True)
        t8.setStyleSheet("font-size: 11px; color: #475569;")
        layout.addWidget(t8)
        return group

    def _schedule_table8_text(self) -> str:
        if self._schedule:
            return self._schedule.get("table8_guidance", "")
        from concrete_mix.codes.aci_trial import TABLE_8_GUIDANCE
        return TABLE_8_GUIDANCE

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
            self._schedule = calculate_aci_trial_batches(
                self._result,
                self._inp,
                volume_m3=self._volume_spin.value(),
                include_series=self._series_chk.isChecked(),
                cement_step_pct=self._cem_step_spin.value(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Trial Schedule", str(e))
            return
        self._fill_schedule_table()
        self._update_schedule_note()

    def _fill_schedule_table(self) -> None:
        sched = self._schedule
        rows = list(sched["batches"]) + list(sched["series"])
        self._table.setRowCount(len(rows))
        for r, b in enumerate(rows):
            pm = b["per_m3"]
            name_item = QTableWidgetItem(b["name"])
            name_item.setToolTip("\n".join(b["notes"]))
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, QTableWidgetItem(f"{b['w_c_ratio']:.3f}"))

            water = pm.get("water_to_batch", pm["water"])
            fa = pm.get("fine_agg_batched", pm["fine_agg_ssd"])
            ca = pm.get("coarse_agg_batched", pm["coarse_agg_ssd"])
            values = [
                f"{water * sched['volume_m3']:.2f}",
                f"{pm['cementitious'] * sched['volume_m3']:.2f}",
                f"{fa * sched['volume_m3']:.2f}",
                f"{ca * sched['volume_m3']:.2f}",
                f"{pm['admixture'] * sched['volume_m3']:.2f}" if pm["admixture"] else "—",
            ]
            for col, txt in enumerate(values, start=2):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, col, item)

    def _update_schedule_note(self) -> None:
        sched = self._schedule
        m = sched["moisture"]
        parts = [
            f"Free water at stockpile moisture: fine {m['free_water_fine_kg_m3']:.1f} + "
            f"coarse {m['free_water_coarse_kg_m3']:.1f} kg/m³ — deducted from the "
            f"mixing water (§5.3.9.1). Total batch weight equals total mixture weight."
        ]
        for w in sched["warnings"]:
            parts.append(f"⚠ {w}")
        self._schedule_note.setText("  ".join(parts))

    # ------------------------------------------------------------------
    # §5.3.10 evaluation
    # ------------------------------------------------------------------

    def _collect_measurements(self) -> dict[str, Any]:
        measurements: dict[str, Any] = {"volume_m3": self._volume_spin.value()}
        if self._actual_water_spin.value() > 0:
            measurements["actual_water_kg"] = self._actual_water_spin.value()
        if self._batched_fa_spin.value() > 0:
            measurements["batched_fine_kg"] = self._batched_fa_spin.value()
        if self._batched_ca_spin.value() > 0:
            measurements["batched_coarse_kg"] = self._batched_ca_spin.value()
        if self._slump_spin.value() > 0:
            measurements["measured_slump_mm"] = self._slump_spin.value()
        if self._density_spin.value() > 0:
            measurements["measured_density_kg_m3"] = self._density_spin.value()
        if self._air_spin.value() > 0:
            measurements["measured_air_pct"] = self._air_spin.value()
        if self._strength_spin.value() > 0:
            measurements["cube_strength_mpa"] = self._strength_spin.value()
        measurements["test_age_days"] = self._age_spin.value()
        return measurements

    def _on_calculate(self) -> None:
        try:
            self._evaluation = evaluate_aci_trial(self._result, self._inp, self._collect_measurements())
        except ValueError as e:
            QMessageBox.warning(self, "Trial Evaluation", str(e))
            return
        self._render_evaluation()

    def _render_evaluation(self) -> None:
        ev = self._evaluation
        html: list[str] = []

        fw = ev["free_water"]
        html.append("<b>Free-water reversal (§9.2.9.1):</b>")
        html.append(
            f"<ul><li>Water added {fw['water_added_kg']:.2f} kg + free water on "
            f"aggregates {fw['free_water_fine_kg']:.2f} (fine) + "
            f"{fw['free_water_coarse_kg']:.2f} (coarse) kg → net mixing water "
            f"<b>{fw['net_water_kg_m3']:.1f} kg/m³</b></li></ul>"
        )

        y = ev["yield"]
        if y["measured_density_kg_m3"]:
            ry = y["relative_yield"]
            colour = "#166534" if y["in_tolerance"] else "#92400e"
            html.append("<b>Yield & air (ASTM C138, §5.3.10):</b>")
            html.append(
                f"<ul><li>Theoretical {y['theoretical_density_kg_m3']:.1f} vs measured "
                f"{y['measured_density_kg_m3']:.1f} kg/m³ → relative yield "
                f"<b style='color:{colour};'>{ry:.4f}</b> "
                f"({'within' if y['in_tolerance'] else 'OUTSIDE'} the "
                f"{RELATIVE_YIELD_TOLERANCE[0]:.2f}–{RELATIVE_YIELD_TOLERANCE[1]:.2f} tolerance)</li>"
                f"<li>Gravimetric air content <b>{y['gravimetric_air_pct']:.2f}%</b></li></ul>"
            )

        a1 = ev["adjustment_1"]
        html.append("<b>Adjustment 1 — mixing water (§5.3.10.1):</b>")
        html.append(
            f"<ul><li>Net water {a1['net_water_kg_m3']:.1f}"
            + (f" ÷ yield → {a1['yield_corrected_kg_m3']:.1f}" if a1["yield_corrected_kg_m3"] is not None else "")
            + (f" {a1['slump_correction_kg_m3']:+.1f} kg/m³ for the slump difference"
               if a1["slump_correction_kg_m3"] is not None else "")
            + f" → <b>{a1['re_estimated_water_kg_m3']:.1f} kg/m³</b></li></ul>"
        )
        for n in a1.get("notes", []):
            html.append(f"<div style='margin-left:14px;'>• {n}</div>")

        a2 = ev["adjustment_2"]
        if a2["provided"]:
            html.append("<b>Adjustment 2 — air content (§5.3.10.2):</b>")
            html.append(
                f"<ul><li>Measured {a2['measured_air_pct']:.1f}% vs target "
                f"{a2['target_air_pct']:.1f}% → water {a2['water_correction_kg_m3']:+.1f} "
                f"kg/m³; re-estimate the air-entrainer dosage</li></ul>"
            )

        a3 = ev["adjustment_3"]
        if a3["provided"]:
            html.append("<b>Adjustment 3 — strength (§5.3.10.3):</b>")
            html.append(
                f"<ul><li>Measured {a3['measured_strength_mpa']:.1f} vs f'cr "
                f"{a3['fcr_mpa']:.1f} MPa → cement efficiency "
                f"{a3['efficiency_mpa_per_kg']:.4f} MPa per kg/m³ → cementitious "
                f"<b>{a3['delta_cement_kg_m3']:+.1f} kg/m³</b> (water "
                f"{a3['delta_water_kg_m3']:+.1f} at constant w/cm, sand offset "
                f"for yield)</li></ul>"
            )

        nt = ev["next_trial"]
        pm = nt["per_m3"]
        html.append("<b>Next-trial proportions (§5.3.10.4, per m³ SSD):</b>")
        parts = [
            f"water {pm['water']:.0f}",
            f"cementitious {pm['cement'] + pm['scm']:.0f}"
            + (f" (incl. SCM {pm['scm']:.0f})" if pm["scm"] else ""),
            f"fine {pm['fine_agg_ssd']:.0f}",
            f"coarse {pm['coarse_agg_ssd']:.0f}",
        ]
        if pm["admixture"]:
            parts.append(f"admixture {pm['admixture']:.2f}")
        html.append(
            "<div style='margin-left:14px;'>" + ", ".join(parts) + " kg — w/cm "
            + (f"{nt['w_c_ratio']:.3f}" if nt["w_c_ratio"] else "—")
            + f"; air basis {nt['air_basis_pct']:.1f}%</div>"
        )
        html.append(f"<div style='color:#64748b; font-size:11px;'>{nt['note']}</div>")

        for w in ev["warnings"]:
            html.append(f"<div style='color:#b45309;'>⚠ {w}</div>")

        self._eval_result.setText("".join(html))
        self._eval_result.setVisible(True)

    # ------------------------------------------------------------------
    # Export / persistence
    # ------------------------------------------------------------------

    def _schedule_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._schedule:
            return rows
        for b in list(self._schedule["batches"]) + list(self._schedule["series"]):
            pm = b["per_m3"]
            rows.append({
                "mixture": b["name"],
                "w_cm": b["w_c_ratio"],
                "water_to_batch_kg_m3": pm.get("water_to_batch", pm["water"]),
                "cementitious_kg_m3": pm["cementitious"],
                "fine_agg_ssd_kg_m3": pm.get("fine_agg_ssd"),
                "fine_agg_batched_kg_m3": pm.get("fine_agg_batched"),
                "coarse_agg_ssd_kg_m3": pm.get("coarse_agg_ssd"),
                "coarse_agg_batched_kg_m3": pm.get("coarse_agg_batched"),
                "admixture_kg_m3": pm["admixture"],
                "notes": " | ".join(b["notes"]),
            })
        return rows

    def _copy_to_clipboard(self) -> None:
        if not self._schedule:
            return
        buf = io.StringIO()
        buf.write("ACI PRC-211.1-22 — Trial Batching Schedule (Table 5.3.9.1)\n")
        buf.write("=" * 60 + "\n")
        buf.write(f"Trial volume: {self._volume_spin.value():.4f} m³\n")
        for row in self._schedule_rows():
            buf.write(f"\n[{row['mixture']}]  w/cm {row['w_cm']:.3f}\n")
            buf.write(f"  Water to batch:   {row['water_to_batch_kg_m3']:.1f} kg/m³\n")
            buf.write(f"  Cementitious:     {row['cementitious_kg_m3']:.1f} kg/m³\n")
            buf.write(f"  Fine Agg batched: {row['fine_agg_batched_kg_m3']:.1f} kg/m³ "
                      f"(SSD {row['fine_agg_ssd_kg_m3']:.1f})\n")
            buf.write(f"  Coarse Agg batched:{row['coarse_agg_batched_kg_m3']:.1f} kg/m³ "
                      f"(SSD {row['coarse_agg_ssd_kg_m3']:.1f})\n")
            if row["admixture_kg_m3"]:
                buf.write(f"  Admixture: {row['admixture_kg_m3']:.2f} kg/m³\n")
            if row["notes"]:
                buf.write(f"  Notes: {row['notes']}\n")

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(buf.getvalue())
            QMessageBox.information(
                self, "Copied to Clipboard",
                "ACI trial batching schedule copied to clipboard.",
            )

    def _export_csv(self) -> None:
        if not self._schedule:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export ACI Trial Mixes to CSV",
            "aci_trial_mixes.csv", "CSV Files (*.csv)",
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Standard", "ACI PRC-211.1-22 Trial Batching"])
                writer.writerow(["Required average strength f'cr (MPa)", self._result.target_mean_strength_mpa])
                writer.writerow(["Design w/cm", self._result.w_c_ratio])
                writer.writerow(["Trial volume (m3)", self._volume_spin.value()])
                writer.writerow([])
                writer.writerow([
                    "Mixture", "w/cm", "Water to batch (kg/m3)",
                    "Cementitious (kg/m3)", "Fine Agg SSD (kg/m3)",
                    "Fine Agg batched (kg/m3)", "Coarse Agg SSD (kg/m3)",
                    "Coarse Agg batched (kg/m3)", "Admixture (kg/m3)", "Notes",
                ])
                for row in self._schedule_rows():
                    writer.writerow([
                        row["mixture"], row["w_cm"], row["water_to_batch_kg_m3"],
                        row["cementitious_kg_m3"], row["fine_agg_ssd_kg_m3"],
                        row["fine_agg_batched_kg_m3"], row["coarse_agg_ssd_kg_m3"],
                        row["coarse_agg_batched_kg_m3"], row["admixture_kg_m3"],
                        row["notes"],
                    ])
                ev = self._evaluation
                if ev:
                    writer.writerow([])
                    writer.writerow(["§5.3.10 Post-Trial Adjustments"])
                    fw = ev["free_water"]
                    writer.writerow(["Net mixing water (kg/m3)", fw["net_water_kg_m3"]])
                    y = ev["yield"]
                    if y["measured_density_kg_m3"]:
                        writer.writerow(["Relative yield", y["relative_yield"]])
                        writer.writerow(["Gravimetric air (%)", y["gravimetric_air_pct"]])
                    a1 = ev["adjustment_1"]
                    writer.writerow(["Re-estimated water (kg/m3)", a1["re_estimated_water_kg_m3"]])
                    nt = ev["next_trial"]["per_m3"]
                    writer.writerow([
                        "Next trial (kg/m3)",
                        f"water={nt['water']}", f"cement={nt['cement']}",
                        f"scm={nt['scm']}", f"fine={nt['fine_agg_ssd']}",
                        f"coarse={nt['coarse_agg_ssd']}",
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
                "code": "aci211",
                "design_fcr_mpa": self._result.target_mean_strength_mpa,
                "design_w_cm": self._result.w_c_ratio,
                "design_water_kg": self._result.water_kg,
                "design_cement_kg": self._result.cement_kg,
                "design_scm_kg": self._result.scm_kg,
                "design_fine_agg_kg": self._result.fine_aggregate_kg,
                "design_coarse_agg_kg": self._result.coarse_aggregate_kg,
                "trial_volume_m3": self._volume_spin.value(),
                "include_series": self._series_chk.isChecked(),
                "cement_step_pct": self._cem_step_spin.value(),
                "measurements": self._collect_measurements(),
            }
            trial_result: dict[str, Any] = {
                "schedule": self._schedule_rows(),
                "warnings": list(self._schedule["warnings"]) if self._schedule else [],
                "relative_yield_tolerance": list(RELATIVE_YIELD_TOLERANCE),
            }
            if self._evaluation:
                ev = self._evaluation
                trial_result["free_water"] = ev["free_water"]
                trial_result["yield"] = ev["yield"]
                trial_result["adjustments"] = {
                    "1_water": ev["adjustment_1"],
                    "2_air": ev["adjustment_2"],
                    "3_strength": ev["adjustment_3"],
                }
                trial_result["next_trial_per_m3"] = ev["next_trial"]["per_m3"]
                trial_result["next_trial_w_cm"] = ev["next_trial"]["w_c_ratio"]
                trial_result["warnings"] = (
                    list(self._schedule["warnings"]) if self._schedule else []
                ) + list(ev["warnings"])
            calc_id = db.save_aci_trial(
                trial_input, trial_result,
                name=f"ACI Trial — f'cr {self._result.target_mean_strength_mpa:.1f} MPa",
                parent_id=self._design_calc_id,
            )
            QMessageBox.information(
                self, "Trial Record Saved",
                f"ACI trial record #{calc_id} saved to history"
                + (" and linked to the parent design." if self._design_calc_id else "."),
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save trial record:\n{e}")
