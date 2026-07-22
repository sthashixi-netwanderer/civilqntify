"""Detail dialog for viewing a single history record.

Shows full input parameters and result values in a structured
read-only layout, with actions to load into the appropriate tab.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


_TAB_LABELS = {
    "mix_design": "Concrete Mix Design",
    "quantification": "Material Quantification",
    "cost_estimation": "Cost Estimation",
}


class HistoryDetailDialog(QDialog):
    """Modal dialog showing full details of a history record."""

    def __init__(self, record: dict, parent=None) -> None:
        super().__init__(parent)
        self._rec = record
        self.setWindowTitle(
            f"History #{record['id']} — {_TAB_LABELS.get(record['tab_type'], record['tab_type'])}"
        )
        self.setMinimumSize(700, 600)
        self.resize(800, 700)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # -- Header --
        header = QHBoxLayout()
        id_lbl = QLabel(f"#{self._rec['id']}")
        id_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        header.addWidget(id_lbl)

        name = self._rec.get("name", "")
        if name:
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("font-size: 15px; color: #0b1c30;")
            header.addWidget(name_lbl)

        header.addStretch()

        date_lbl = QLabel(self._rec.get("created_at", "")[:19].replace("T", " "))
        date_lbl.setObjectName("result-unit")
        header.addWidget(date_lbl)

        root.addLayout(header)

        # -- Scroll area for content --
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        # Parse JSON blobs
        try:
            input_data = json.loads(self._rec.get("input_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            input_data = {}
        try:
            result_data = json.loads(self._rec.get("result_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            result_data = {}

        # -- Input parameters --
        input_group = QGroupBox("Input Parameters")
        input_grid = QGridLayout(input_group)
        input_grid.setSpacing(6)
        row = 0
        for key, value in self._flatten_dict(input_data):
            key_lbl = QLabel(key.replace("_", " ").title() + ":")
            key_lbl.setStyleSheet("font-weight: 600;")
            val_lbl = QLabel(str(value))
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            input_grid.addWidget(key_lbl, row, 0)
            input_grid.addWidget(val_lbl, row, 1)
            row += 1
        content_layout.addWidget(input_group)

        # -- Result values --
        result_group = QGroupBox("Results")
        result_grid = QGridLayout(result_group)
        result_grid.setSpacing(6)
        row = 0

        tt = self._rec["tab_type"]
        if tt == "mix_design":
            display_fields = [
                ("code_used", "Standard"),
                ("target_mean_strength_mpa", "Target Mean Strength (MPa)"),
                ("w_c_ratio", "W/C Ratio"),
                ("water_kg", "Water (kg/m\u00b3)"),
                ("cement_kg", "Cement (kg/m\u00b3)"),
                ("scm_kg", "SCM (kg/m\u00b3)"),
                ("fine_aggregate_kg", "Fine Aggregate (kg/m\u00b3)"),
                ("coarse_aggregate_kg", "Coarse Aggregate (kg/m\u00b3)"),
                ("air_volume_percent", "Air Content (%)"),
                ("volume_m3", "Volume (m\u00b3)"),
                ("cost_per_m3", "Cost per m\u00b3"),
                ("carbon_kg_co2_per_m3", "Carbon (kg CO\u2082/m\u00b3)"),
            ]
        elif tt == "quantification":
            display_fields = [
                ("net_concrete_volume_m3", "Net Volume (m\u00b3)"),
                ("wastage_percent", "Wastage (%)"),
                ("gross_concrete_volume_m3", "Gross Volume (m\u00b3)"),
                ("total_cement_kg", "Total Cement (kg)"),
                ("total_cement_bags", "Cement Bags"),
                ("total_water_kg", "Total Water (kg)"),
                ("total_fine_aggregate_kg", "Fine Aggregate (kg)"),
                ("total_coarse_aggregate_kg", "Coarse Aggregate (kg)"),
                ("total_scm_kg", "SCM (kg)"),
                ("total_admixture_kg", "Admixture (kg)"),
            ]
        elif tt == "cost_estimation":
            display_fields = [
                ("material_cost_per_m3", "Material Cost/m\u00b3"),
                ("total_material_cost", "Total Material Cost"),
                ("total_project_cost", "Total Project Cost"),
                ("cost_per_bag", "Cost per Bag"),
            ]
        else:
            display_fields = list(result_data.items())

        for key, label in display_fields:
            value = result_data.get(key, "")
            if value is None or value == "":
                continue
            key_lbl = QLabel(f"{label}:")
            key_lbl.setStyleSheet("font-weight: 600;")
            val_lbl = QLabel(str(value))
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            result_grid.addWidget(key_lbl, row, 0)
            result_grid.addWidget(val_lbl, row, 1)
            row += 1

        # Also show any extra keys not in display_fields
        shown_keys = {k for k, _ in display_fields}
        for key, value in sorted(result_data.items()):
            if key in shown_keys or key in ("steps", "warnings", "transfer_data"):
                continue
            if value is None or value == "":
                continue
            key_lbl = QLabel(f"{key.replace('_', ' ').title()}:")
            key_lbl.setStyleSheet("font-weight: 600;")
            val_lbl = QLabel(str(value))
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            result_grid.addWidget(key_lbl, row, 0)
            result_grid.addWidget(val_lbl, row, 1)
            row += 1

        content_layout.addWidget(result_group)

        # -- Calculation steps (mix design only) --
        steps = result_data.get("steps", [])
        if steps:
            steps_group = QGroupBox(f"Calculation Steps ({len(steps)})")
            steps_layout = QVBoxLayout(steps_group)
            table = QTableWidget(len(steps), 6)
            table.setHorizontalHeaderLabels(
                ["#", "Description", "Formula", "Result", "Unit", "Reference"]
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            for i, step in enumerate(steps):
                table.setItem(i, 0, QTableWidgetItem(str(step.get("step_number", ""))))
                table.setItem(i, 1, QTableWidgetItem(step.get("description", "")))
                table.setItem(i, 2, QTableWidgetItem(step.get("formula", "")))
                table.setItem(i, 3, QTableWidgetItem(str(step.get("result", ""))))
                table.setItem(i, 4, QTableWidgetItem(step.get("unit", "")))
                table.setItem(i, 5, QTableWidgetItem(step.get("clause_ref", "")))
            steps_layout.addWidget(table)
            content_layout.addWidget(steps_group)

        # -- Warnings --
        warnings = result_data.get("warnings", [])
        if warnings:
            warn_group = QGroupBox("Warnings")
            warn_layout = QVBoxLayout(warn_group)
            for w in warnings:
                lbl = QLabel(f"\u26a0 {w}")
                lbl.setStyleSheet("color: #f59e0b;")
                warn_layout.addWidget(lbl)
            content_layout.addWidget(warn_group)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # -- Close button --
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    @staticmethod
    def _flatten_dict(d: dict, prefix: str = "") -> list[tuple[str, str]]:
        """Flatten nested dicts into a list of (label, value) pairs."""
        items = []
        for k, v in d.items():
            label = f"{prefix}{k}".replace("_", " ").title()
            if isinstance(v, dict):
                items.extend(HistoryDetailDialog._flatten_dict(v, f"{prefix}{k}_"))
            elif isinstance(v, list) and len(v) < 5:
                items.append((label, str(v)))
            elif isinstance(v, list):
                items.append((label, f"({len(v)} items)"))
            else:
                items.append((label, str(v)))
        return items
