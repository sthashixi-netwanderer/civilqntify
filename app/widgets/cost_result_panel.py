"""Results panel for cost estimation output.

Displays a complete cost breakdown with:
- Summary stat cards (material cost/m³, total material, total project, cost/bag)
- Material cost breakdown table
- Project summary with grand total
- Export and print buttons

All monetary values are in Ghana Cedis (GH₵).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from app.unit_preferences import UnitPreferences, get_unit_prefs
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _StatCard(QFrame):
    """Metric card for cost display — mirrors QuantResultPanel._StatCard."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("result-card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setObjectName("result-label")
        self._value = QLabel("\u2014")
        self._value.setObjectName("result-value")
        self._value.setStyleSheet(
            "font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        self._unit = QLabel("")
        self._unit.setObjectName("result-unit")

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._unit)

    def set_value(self, value: float, unit: str = "GH\u20B5", fmt: str = ",.2f") -> None:
        self._value.setText(f"{value:{fmt}}")
        self._unit.setText(unit)


class CostResultPanel(QWidget):
    """Right-side panel showing cost estimation results in GH₵."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cost_data: dict | None = None
        self.unit_prefs: UnitPreferences = get_unit_prefs()
        self._build_ui()
        self.unit_prefs.changed.connect(self.on_unit_changed)

    def _build_ui(self) -> None:
        # Scroll area for content + fixed action bar at bottom
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(QWidget())
        outer = QVBoxLayout(scroll.widget())
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # ── Warnings ──
        self._warning_banner = QLabel()
        self._warning_banner.setObjectName("warning-banner")
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setVisible(False)
        outer.addWidget(self._warning_banner)

        # ── Summary Cards ──
        summary_label = QLabel("Cost Summary")
        summary_label.setObjectName("section-title")
        outer.addWidget(summary_label)

        summary_grid = QGridLayout()
        summary_grid.setSpacing(10)
        self._card_mat_cost_m3 = _StatCard("Material Cost / m\u00b3")
        self._card_total_mat = _StatCard("Total Material Cost")
        self._card_total_proj = _StatCard("Total Project Cost")
        self._card_cost_bag = _StatCard("Cost / Bag of Concrete")
        summary_grid.addWidget(self._card_mat_cost_m3, 0, 0)
        summary_grid.addWidget(self._card_total_mat, 0, 1)
        summary_grid.addWidget(self._card_total_proj, 1, 0)
        summary_grid.addWidget(self._card_cost_bag, 1, 1)
        outer.addLayout(summary_grid)

        # ── Material Cost Breakdown Table ──
        breakdown_label = QLabel("Material Cost Breakdown")
        breakdown_label.setObjectName("section-title")
        outer.addWidget(breakdown_label)

        self._mat_table = QTableWidget()
        self._mat_table.setColumnCount(5)
        self._mat_table.setHorizontalHeaderLabels([
            "Material", "Qty", "Unit", "Unit Price (GH\u20B5)", "Total Cost (GH\u20B5)"
        ])
        self._mat_table.setAlternatingRowColors(True)
        self._mat_table.setFixedHeight(240)
        self._mat_table.horizontalHeader().setStretchLastSection(True)
        outer.addWidget(self._mat_table)

        # ── Project Summary ──
        summary_proj_label = QLabel("Project Summary")
        summary_proj_label.setObjectName("section-title")
        outer.addWidget(summary_proj_label)

        self._summary_frame = QFrame()
        self._summary_frame.setObjectName("result-card")
        self._summary_frame.setStyleSheet(
            "#result-card { border: 1px solid #1e40af; }"
        )
        self._summary_layout = QVBoxLayout(self._summary_frame)
        self._summary_layout.setContentsMargins(16, 12, 16, 12)
        self._summary_layout.setSpacing(6)
        outer.addWidget(self._summary_frame)

        # Summary rows placeholder
        self._summary_rows: dict[str, tuple[QLabel, QLabel]] = {}

        outer.addStretch()

        scroll.setWidget(scroll.widget())

        # ── Fixed action bar at bottom (outside scroll area) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(12, 8, 12, 8)
        self.btn_csv = QPushButton("  Export Cost Report (CSV)")
        self.btn_csv.setObjectName("secondary")
        self.btn_csv.setEnabled(False)
        self.btn_pdf = QPushButton("  Export Cost Report (PDF)")
        self.btn_pdf.setObjectName("primary_action")
        self.btn_pdf.setEnabled(False)
        btn_row.addWidget(self.btn_csv)
        btn_row.addWidget(self.btn_pdf)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll, 1)
        layout.addLayout(btn_row)

    # ── Display Methods ────────────────────────────────────────────

    def display_cost(self, cost_data: dict) -> None:
        """Update the panel with cost estimation data.

        Args:
            cost_data: Dict containing:
                - material_cost_per_m3: float
                - total_material_cost: float
                - total_project_cost: float
                - cost_per_bag: float
                - material_breakdown: list[dict] with keys: name, qty, unit, unit_price, total
                - summary_rows: list[dict] with keys: label, amount, is_subtotal, is_total
                - warnings: list[str] (optional)
        """
        self._cost_data = cost_data

        # Warnings
        warnings = cost_data.get("warnings", [])
        if warnings:
            self._warning_banner.setText("Warnings:\n" + "\n".join(warnings))
            self._warning_banner.setVisible(True)
        else:
            self._warning_banner.setVisible(False)

        # Summary cards (per-volume card converts to the active volume unit)
        mat_m3 = cost_data.get("material_cost_per_m3", 0.0)
        total_mat = cost_data.get("total_material_cost", 0.0)
        total_proj = cost_data.get("total_project_cost", 0.0)
        cost_bag = cost_data.get("cost_per_bag", 0.0)

        vu = self.unit_prefs.volume_unit()
        self._card_mat_cost_m3._label.setText(f"Material Cost / {vu}")
        mat_m3_display = mat_m3 / 1.30795 if self.unit_prefs.is_imperial() else mat_m3
        self._card_mat_cost_m3.set_value(mat_m3_display)
        self._card_total_mat.set_value(total_mat)
        self._card_total_proj.set_value(total_proj, fmt=",.2f")
        self._card_cost_bag.set_value(cost_bag)

        # Material breakdown table (quantities converted via their kind)
        self._mat_table.setRowCount(0)
        breakdown = cost_data.get("material_breakdown", [])
        for row_data in breakdown:
            row = self._mat_table.rowCount()
            self._mat_table.insertRow(row)
            qty, unit, unit_price = self._convert_breakdown_row(row_data)
            self._mat_table.setItem(row, 0, QTableWidgetItem(row_data["name"]))
            self._mat_table.setItem(row, 1, QTableWidgetItem(f"{qty:,.2f}"))
            self._mat_table.setItem(row, 2, QTableWidgetItem(unit))
            self._mat_table.setItem(row, 3, QTableWidgetItem(f"{unit_price:,.2f}"))
            self._mat_table.setItem(row, 4, QTableWidgetItem(f"{row_data['total']:,.2f}"))
        self._mat_table.resizeColumnsToContents()

        # Project summary
        self._clear_summary_rows()
        summary_rows = cost_data.get("summary_rows", [])
        for row_data in summary_rows:
            self._add_summary_row(
                row_data["label"],
                row_data["amount"],
                is_subtotal=row_data.get("is_subtotal", False),
                is_total=row_data.get("is_total", False),
            )

        # Enable buttons
        self.btn_csv.setEnabled(True)
        self.btn_pdf.setEnabled(True)

    def _convert_breakdown_row(self, row_data: dict) -> tuple[float, str, float]:
        """Convert a metric breakdown row to the active display units.

        Rows carry metric qty/unit_price plus an optional ``kind``
        ("volume" | "water" | "mass" | "count").  Legacy rows without a
        kind are shown verbatim (already metric-labelled).
        """
        up = self.unit_prefs
        qty = row_data["qty"]
        unit = row_data.get("unit", "")
        price = row_data["unit_price"]
        kind = row_data.get("kind")
        imperial = up.is_imperial()
        if kind == "volume":
            qty = up.convert_volume_m3(qty)
            unit = up.volume_unit()
            if imperial:
                price = price / 1.30795  # per m³ → per yd³
        elif kind == "water":
            qty = up.convert_water_liters(qty)
            unit = up.water_unit()
            if imperial:
                price = price / 264.172  # per 1000 L → per 1000 gal
        elif kind == "mass":
            qty = up.convert_mass_kg(qty)
            unit = up.mass_unit()
            if imperial:
                price = price / 2.20462  # per kg → per lb
        return qty, unit, price

    def _clear_summary_rows(self) -> None:
        """Remove all existing summary rows."""
        while self._summary_layout.count():
            child = self._summary_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._summary_rows.clear()

    def _add_summary_row(
        self, label: str, amount: float,
        is_subtotal: bool = False, is_total: bool = False,
    ) -> None:
        """Add a row to the project summary frame."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 4, 0, 4)

        lbl = QLabel(label)
        if is_total:
            lbl.setStyleSheet(
                "font-size: 16px; font-weight: 700; color: #00288e;"
                "font-family: 'Inter', sans-serif;"
            )
        elif is_subtotal:
            lbl.setStyleSheet("font-weight: 600;")
        else:
            lbl.setStyleSheet("color: #444653;")

        amt = QLabel(f"GH\u20B5 {amount:,.2f}")
        if is_total:
            amt.setStyleSheet(
                "font-size: 16px; font-weight: 700; color: #00288e;"
                "font-family: 'JetBrains Mono', monospace;"
            )
        elif is_subtotal:
            amt.setStyleSheet(
                "font-weight: 600; font-family: 'JetBrains Mono', monospace;"
            )
        else:
            amt.setStyleSheet("font-family: 'JetBrains Mono', monospace;")

        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(amt)
        self._summary_layout.addWidget(row_widget)

    def clear(self) -> None:
        """Reset panel to empty state."""
        self._cost_data = None
        self._warning_banner.setVisible(False)
        for card in [
            self._card_mat_cost_m3, self._card_total_mat,
            self._card_total_proj, self._card_cost_bag,
        ]:
            card._value.setText("\u2014")
            card._unit.setText("")
        self._mat_table.setRowCount(0)
        self._clear_summary_rows()
        self.btn_csv.setEnabled(False)
        self.btn_pdf.setEnabled(False)

    def on_unit_changed(self) -> None:
        """Update display when unit preferences change."""
        # Update the cost/m³ card title to reflect current volume unit
        vu = self.unit_prefs.volume_unit()
        self._card_mat_cost_m3._label.setText(f"Material Cost / {vu}")
        # Re-render if data is present
        if self._cost_data is not None:
            self.display_cost(self._cost_data)
