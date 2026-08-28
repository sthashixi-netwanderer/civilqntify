"""IS 10262:2019 Clause 5.8 Trial Mixes and Reporting Dialog.

Provides a detailed protocol and batch proportions schedule for the mandatory
4 trial batches specified in IS 10262:2019 Section 5.8, plus the Clause 5.8.1
reporting checklist.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from concrete_mix.codes.is10262 import calculate_is10262_trial_mixes
from concrete_mix.models.mix_result import MixDesignResult


class ISTrialMixesDialog(QDialog):
    """Dialog displaying the IS 10262:2019 Clause 5.8 Trial Mixes protocol."""

    def __init__(
        self,
        result: MixDesignResult,
        inp: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IS 10262:2019 Clause 5.8 — Trial Mixes Protocol & Reporting")
        self.resize(880, 680)
        self.setMinimumSize(700, 520)

        self._result = result
        self._inp = inp
        self._protocol = calculate_is10262_trial_mixes(result, inp)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Scroll area for entire dialog content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Header banner
        header_frame = QFrame()
        header_frame.setObjectName("result-card")
        header_frame.setStyleSheet(
            "background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(4)

        title = QLabel("IS 10262:2019 Section 5.8 — Trial Mixes Procedure")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        h_layout.addWidget(title)

        desc = QLabel(
            "The calculated mix proportions shall be checked by means of trial batches in the laboratory. "
            "Four trial mixes are prepared to adjust workability and establish the relationship between "
            "compressive strength and water-cement ratio before finalizing production proportions."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #1e293b; line-height: 1.4;")
        h_layout.addWidget(desc)
        layout.addWidget(header_frame)

        # 4-Trial Batches Table Group
        tbl_group = QGroupBox("Mandatory 4-Trial Batches Schedule (Clause 5.8)")
        tbl_layout = QVBoxLayout(tbl_group)
        tbl_layout.setContentsMargins(10, 12, 10, 10)
        tbl_layout.setSpacing(8)

        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Trial Batch",
            "W/C",
            "Water (kg)",
            "Cement (kg)",
            "SCM (kg)",
            "Fine Agg (kg)",
            "Coarse Agg (kg)",
            "Admixture (kg)",
        ])
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        trials = self._protocol["trials"]
        self._table.setRowCount(len(trials))
        for row, t in enumerate(trials):
            item_name = QTableWidgetItem(f"Trial {t['trial_number']}: {t['name'].split('(')[0].strip()}")
            item_name.setToolTip(f"{t['name']}\n{t['purpose']}\nAction: {t['action']}")
            item_wc = QTableWidgetItem(f"{t['w_c_ratio']:.2f}")
            item_w = QTableWidgetItem(f"{t['water_kg']:.1f}")
            item_c = QTableWidgetItem(f"{t['cement_kg']:.1f}")
            item_scm = QTableWidgetItem(f"{t['scm_kg']:.1f}")
            item_fa = QTableWidgetItem(f"{t['fine_agg_kg']:.1f}")
            item_ca = QTableWidgetItem(f"{t['coarse_agg_kg']:.1f}")
            item_adm = QTableWidgetItem(f"{t['admixture_kg']:.2f}")

            for it in (item_wc, item_w, item_c, item_scm, item_fa, item_ca, item_adm):
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self._table.setItem(row, 0, item_name)
            self._table.setItem(row, 1, item_wc)
            self._table.setItem(row, 2, item_w)
            self._table.setItem(row, 3, item_c)
            self._table.setItem(row, 4, item_scm)
            self._table.setItem(row, 5, item_fa)
            self._table.setItem(row, 6, item_ca)
            self._table.setItem(row, 7, item_adm)

        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            self._table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setFixedHeight(150)
        tbl_layout.addWidget(self._table)
        layout.addWidget(tbl_group)

        # Step-by-step guidance cards
        guide_group = QGroupBox("Clause 5.8 Step-by-Step Lab & Field Procedure")
        guide_layout = QVBoxLayout(guide_group)
        guide_layout.setSpacing(8)

        steps_text = (
            "<b>1. Trial Mix No. 1 (Initial Calculated Batch):</b><br/>"
            "• Batch concrete using the calculated laboratory proportions.<br/>"
            "• Measure workability (slump test per IS 1199).<br/>"
            "• Carefully observe freedom from segregation and bleeding and inspect finishing properties.<br/><br/>"
            "<b>2. Trial Mix No. 2 (Workability Adjustment):</b><br/>"
            "• If measured slump differs from the required target value, adjust water and/or chemical admixture dosage.<br/>"
            f"• Recalculate mix proportions holding the free W/C ratio constant at <b>{self._result.w_c_ratio:.2f}</b>.<br/><br/>"
            "<b>3. Trial Mixes No. 3 & No. 4 (W/C Variation by ±10%):</b><br/>"
            f"• <b>Trial Mix No. 3 (W/C = {self._result.w_c_ratio * 0.90:.2f}, -10%):</b> Same water content as Trial 2 with increased cementitious content.<br/>"
            f"• <b>Trial Mix No. 4 (W/C = {self._result.w_c_ratio * 1.10:.2f}, +10%):</b> Same water content as Trial 2 with decreased cementitious content (verify IS 456 durability limits).<br/>"
            "• Cast standard test cubes (150 mm) for 7-day and 28-day compressive strength testing.<br/><br/>"
            "<b>4. Proportions Finalization & Field Trials:</b><br/>"
            "• Plot the compressive strength vs. water-cement ratio curve across Trials 2, 3, and 4.<br/>"
            "• Select the optimal W/C and proportions satisfying target mean strength (f'ck) and IS 456 Table 5 durability.<br/>"
            "• Perform full-scale field trial batches produced by actual site concrete production methods."
        )
        lbl_steps = QLabel(steps_text)
        lbl_steps.setWordWrap(True)
        lbl_steps.setStyleSheet("font-size: 12px; line-height: 1.4; color: #334155;")
        guide_layout.addWidget(lbl_steps)
        layout.addWidget(guide_group)

        # Clause 5.8.1 Reporting Checklist
        rep_group = QGroupBox("Clause 5.8.1 Mandatory Reporting Checklist")
        rep_layout = QVBoxLayout(rep_group)
        rep_layout.setSpacing(6)

        rep_intro = QLabel("Ensure the final mix design report includes all mandatory items required by IS 10262:2019 Clause 5.8.1:")
        rep_intro.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        rep_layout.addWidget(rep_intro)

        for code_letter, req_text in self._protocol["reporting_checklist"]:
            chk = QCheckBox(f"<b>({code_letter})</b> {req_text}")
            chk.setChecked(True)
            chk.setStyleSheet("font-size: 12px; color: #1e293b;")
            rep_layout.addWidget(chk)

        layout.addWidget(rep_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Action Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        btn_copy = QPushButton("Copy Trial Batches to Clipboard")
        btn_copy.setObjectName("secondary")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_bar.addWidget(btn_copy)

        btn_csv = QPushButton("Export Trial Batches (CSV)")
        btn_csv.setObjectName("secondary")
        btn_csv.clicked.connect(self._export_csv)
        btn_bar.addWidget(btn_csv)

        btn_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        main_layout.addLayout(btn_bar)

    def _copy_to_clipboard(self) -> None:
        """Format the trial batches schedule and copy to system clipboard."""
        buf = io.StringIO()
        buf.write("IS 10262:2019 Clause 5.8 — Trial Mixes Schedule\n")
        buf.write("=" * 60 + "\n")
        trials = self._protocol["trials"]
        for t in trials:
            buf.write(f"\n[{t['name']}]\n")
            buf.write(f"  W/C Ratio: {t['w_c_ratio']:.2f}\n")
            buf.write(f"  Water:     {t['water_kg']:.1f} kg/m³\n")
            buf.write(f"  Cement:    {t['cement_kg']:.1f} kg/m³\n")
            buf.write(f"  SCM:       {t['scm_kg']:.1f} kg/m³\n")
            buf.write(f"  Fine Agg:  {t['fine_agg_kg']:.1f} kg/m³\n")
            buf.write(f"  Coarse Agg:{t['coarse_agg_kg']:.1f} kg/m³\n")
            if t["admixture_kg"] > 0:
                buf.write(f"  Admixture: {t['admixture_kg']:.2f} kg/m³\n")
            buf.write(f"  Purpose:   {t['purpose']}\n")
            buf.write(f"  Action:    {t['action']}\n")

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(buf.getvalue())
            QMessageBox.information(
                self,
                "Copied to Clipboard",
                "IS 10262:2019 Clause 5.8 Trial Mixes schedule copied to clipboard.",
            )

    def _export_csv(self) -> None:
        """Export the trial batches table to CSV."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export IS 10262 Trial Mixes to CSV",
            "is10262_trial_mixes.csv",
            "CSV Files (*.csv)",
        )
        if not filepath:
            return

        trials = self._protocol["trials"]
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Standard", "IS 10262:2019 Clause 5.8 Trial Mixes"])
                writer.writerow(["Target Strength (MPa)", self._result.target_mean_strength_mpa])
                writer.writerow([])
                writer.writerow([
                    "Trial Number",
                    "Description",
                    "W/C Ratio",
                    "Water (kg/m3)",
                    "Cement (kg/m3)",
                    "SCM (kg/m3)",
                    "Fine Aggregate (kg/m3)",
                    "Coarse Aggregate (kg/m3)",
                    "Admixture (kg/m3)",
                    "Purpose",
                    "Action",
                ])
                for t in trials:
                    writer.writerow([
                        t["trial_number"],
                        t["name"],
                        t["w_c_ratio"],
                        t["water_kg"],
                        t["cement_kg"],
                        t["scm_kg"],
                        t["fine_agg_kg"],
                        t["coarse_agg_kg"],
                        t["admixture_kg"],
                        t["purpose"],
                        t["action"],
                    ])
            QMessageBox.information(
                self,
                "Export Successful",
                f"Trial mixes exported successfully to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export CSV:\n{e}")
