"""Results panel for material quantification output.

Displays a complete material bill of quantities with:
- Volume summary cards (net, wastage, gross)
- Material quantity cards (cement, water, FA, CA, SCM, admixture)
- Detailed breakdown table
- Export buttons
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from material_quantify.models.bill import MaterialBill
from app.unit_preferences import UnitPreferences, get_unit_prefs


class _StatCard(QFrame):
    """Compact metric card — mirrors ResultPanel.StatCard."""

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

    def set_value(self, value: float, unit: str = "kg", fmt: str = ",.1f") -> None:
        self._value.setText(f"{value:{fmt}}")
        self._unit.setText(unit)


class QuantResultPanel(QWidget):
    """Right-side panel showing material quantification results."""

    send_to_cost_estimation = pyqtSignal(object)  # MaterialBill

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bill: MaterialBill | None = None
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

        # ── Volume Summary ──
        vol_label = QLabel("Volume Summary")
        vol_label.setObjectName("section-title")
        outer.addWidget(vol_label)

        vol_grid = QGridLayout()
        vol_grid.setSpacing(10)
        self._card_net = _StatCard("Net Volume")
        self._card_wastage = _StatCard("Wastage")
        self._card_gross = _StatCard("Gross Volume")
        vol_grid.addWidget(self._card_net, 0, 0)
        vol_grid.addWidget(self._card_wastage, 0, 1)
        vol_grid.addWidget(self._card_gross, 0, 2)
        outer.addLayout(vol_grid)

        # ── Material Quantities ──
        mat_label = QLabel("Total Material Quantities")
        mat_label.setObjectName("section-title")
        outer.addWidget(mat_label)

        mat_grid = QGridLayout()
        mat_grid.setSpacing(10)
        self._mat_cards: dict[str, _StatCard] = {}
        mat_defs = [
            ("cement", "Cement"),
            ("cement_bags", "Cement Bags"),
            ("water", "Water"),
            ("fine_agg", "Fine Aggregate"),
            ("coarse_agg", "Coarse Aggregate"),
            ("scm", "SCM"),
            ("admixture", "Admixture"),
            ("wc_ratio", "W/C Ratio"),
        ]
        for i, (key, label) in enumerate(mat_defs):
            card = _StatCard(label)
            self._mat_cards[key] = card
            mat_grid.addWidget(card, i // 4, i % 4)
        outer.addLayout(mat_grid)

        # ── Detailed Breakdown Table ──
        breakdown_label = QLabel("Detailed Breakdown")
        breakdown_label.setObjectName("section-title")
        outer.addWidget(breakdown_label)

        self._table = QTreeWidget()
        self._table.setHeaderLabels([
            "Material", "Per m\u00b3", "Total", "Unit", "Volume/Bags"
        ])
        self._table.setAlternatingRowColors(True)
        self._table.setRootIsDecorated(False)
        self._table.setColumnCount(5)
        # Expanding (not fixed) so the breakdown uses the space below
        # it; _fit_table_height() grows it per result. See ResultPanel
        # calculation-steps fix: a fixed height + trailing stretch left
        # the table cut halfway with blank space underneath.
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setMinimumHeight(220)
        outer.addWidget(self._table, stretch=1)
        self._table_header_units()

        outer.addStretch(0)

        scroll.setWidget(scroll.widget())

        # ── Fixed action bar at bottom (outside scroll area) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(12, 8, 12, 8)
        self.btn_csv = QPushButton("Export CSV")
        self.btn_csv.setObjectName("secondary")
        self.btn_csv.setEnabled(False)
        self.btn_report = QPushButton("Export Text Report")
        self.btn_report.setObjectName("secondary")
        self.btn_report.setEnabled(False)
        btn_row.addWidget(self.btn_csv)
        btn_row.addWidget(self.btn_report)

        btn_row.addSpacing(16)
        self._btn_cost = QPushButton("  Send to Cost Estimation")
        self._btn_cost.setObjectName("secondary")
        self._btn_cost.setEnabled(False)
        self._btn_cost.clicked.connect(self._on_send_to_cost)
        btn_row.addWidget(self._btn_cost)

        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll, 1)
        layout.addLayout(btn_row)

    def display_bill(self, bill: MaterialBill) -> None:
        """Update the panel with a material bill result."""
        self._bill = bill
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render the current bill with active unit conversions."""
        bill = self._bill
        if bill is None:
            return

        up = self.unit_prefs
        self._table_header_units()

        # Volume cards
        self._card_net.set_value(
            up.convert_volume_m3(bill.net_concrete_volume_m3),
            unit=up.volume_unit(), fmt=",.3f")
        self._card_wastage.set_value(bill.wastage_percent, unit="%", fmt=".1f")
        self._card_gross.set_value(
            up.convert_volume_m3(bill.gross_concrete_volume_m3),
            unit=up.volume_unit(), fmt=",.3f")

        # Material cards
        self._mat_cards["cement"].set_value(
            up.convert_mass_kg(bill.total_cement_kg), unit=up.mass_unit())
        bag_wt = up.convert_mass_kg(bill.cement_bag_weight_kg)
        self._mat_cards["cement_bags"].set_value(
            bill.total_cement_bags,
            unit=f"bags ({bag_wt:.0f} {up.mass_unit()})", fmt=",.0f")
        self._mat_cards["water"].set_value(
            up.convert_mass_kg(bill.total_water_kg), unit=up.mass_unit())
        self._mat_cards["fine_agg"].set_value(
            up.convert_mass_kg(bill.total_fine_aggregate_kg), unit=up.mass_unit())
        self._mat_cards["coarse_agg"].set_value(
            up.convert_mass_kg(bill.total_coarse_aggregate_kg), unit=up.mass_unit())
        self._mat_cards["scm"].set_value(
            up.convert_mass_kg(bill.total_scm_kg), unit=up.mass_unit())
        self._mat_cards["admixture"].set_value(
            up.convert_mass_kg(bill.total_admixture_kg), unit=up.mass_unit(), fmt=",.3f")
        self._mat_cards["wc_ratio"].set_value(
            bill.transfer_data.w_c_ratio, unit="", fmt=".3f")

        # Detailed table
        self._table.clear()
        td = bill.transfer_data
        vu = up.volume_unit()
        wu = up.water_unit()

        rows = [
            ("Cement",
             self._per_volume_mass(td.cement_kg_per_m3, up),
             up.convert_mass_kg(bill.total_cement_kg), up.mass_per_volume_unit(),
             f"{bill.total_cement_bags:.0f} bags"),
            ("Water (field)",
             self._per_volume_mass(td.field_water_kg_per_m3, up),
             up.convert_mass_kg(bill.total_water_kg), up.mass_per_volume_unit(),
             f"{up.convert_water_liters(bill.total_water_liters):.1f} {wu}"),
            ("Fine Aggregate (SSD)",
             self._per_volume_mass(td.fine_aggregate_kg_per_m3, up),
             up.convert_mass_kg(bill.total_fine_aggregate_kg), up.mass_per_volume_unit(),
             f"{up.convert_volume_m3(bill.total_fine_aggregate_bulk_m3):.3f} {vu}"),
            ("Fine Aggregate (field)",
             self._per_volume_mass(td.field_fine_aggregate_kg_per_m3, up),
             up.convert_mass_kg(bill.total_fine_aggregate_kg), up.mass_per_volume_unit(), ""),
            ("Coarse Aggregate (SSD)",
             self._per_volume_mass(td.coarse_aggregate_kg_per_m3, up),
             up.convert_mass_kg(bill.total_coarse_aggregate_kg), up.mass_per_volume_unit(),
             f"{up.convert_volume_m3(bill.total_coarse_aggregate_bulk_m3):.3f} {vu}"),
            ("Coarse Aggregate (field)",
             self._per_volume_mass(td.field_coarse_aggregate_kg_per_m3, up),
             up.convert_mass_kg(bill.total_coarse_aggregate_kg), up.mass_per_volume_unit(), ""),
        ]

        if bill.total_scm_kg > 0:
            rows.append(("SCM",
                         self._per_volume_mass(td.scm_kg_per_m3, up),
                         up.convert_mass_kg(bill.total_scm_kg), up.mass_per_volume_unit(), ""))

        if bill.total_admixture_kg > 0:
            rows.append(("Admixture",
                         self._per_volume_mass(td.admixture_kg_per_m3, up),
                         up.convert_mass_kg(bill.total_admixture_kg), up.mass_per_volume_unit(), ""))

        for name, per_m3, total, unit, extra in rows:
            item = QTreeWidgetItem([
                name,
                f"{per_m3:.1f}",
                f"{total:,.1f}",
                unit,
                extra,
            ])
            self._table.addTopLevelItem(item)

        for col in range(5):
            self._table.resizeColumnToContents(col)

        self._fit_table_height()

        # Enable export
        self.btn_csv.setEnabled(True)
        self.btn_report.setEnabled(True)
        self._btn_cost.setEnabled(True)

    def _fit_table_height(self) -> None:
        """Size the breakdown table to its content height.

        Same fix as ResultPanel calculation steps: the table sits in
        the outer scroll area, so growing its minimum height consumes
        the space below instead of cutting rows behind a nested
        scrollbar. Clamped so long bills still scroll.
        """
        count = self._table.topLevelItemCount()
        if count == 0:
            self._table.setMinimumHeight(220)
            return
        try:
            row_h = max(
                (self._table.sizeHintForRow(i) or 0)
                for i in range(count)
            )
        except Exception:
            row_h = 0
        if not row_h or row_h <= 0:
            row_h = 30
        try:
            header_h = self._table.header().sizeHint().height() or 30
        except Exception:
            header_h = 30
        try:
            frame = 2 * self._table.frameWidth()
        except Exception:
            frame = 2
        needed = header_h + count * row_h + frame + 6
        self._table.setMinimumHeight(max(220, min(needed, 520)))

    def on_unit_changed(self) -> None:
        """Re-render the bill when unit preferences change."""
        self._refresh_display()

    def _table_header_units(self) -> None:
        """Set the breakdown table header to the active per-volume unit."""
        vu = self.unit_prefs.volume_unit()
        self._table.setHeaderLabels([
            "Material", f"Per {vu}", "Total", "Unit", "Volume/Bags"
        ])

    @staticmethod
    def _per_volume_mass(kg_per_m3: float, up) -> float:
        """Convert a kg/m³ content to the active per-volume mass unit.

        Metric shows kg/m³ (IS 10262 basis); imperial shows lb/yd³
        (ACI 211.1 basis).
        """
        return kg_per_m3 * 1.68555 if up.is_imperial() else kg_per_m3
        """Re-display bill when unit preferences change."""
        self._refresh_display()

    def _on_send_to_cost(self) -> None:
        """Emit signal to transfer material bill to cost estimation tab."""
        if self._bill is not None:
            self.send_to_cost_estimation.emit(self._bill)

    def clear(self) -> None:
        """Reset panel to empty state."""
        self._bill = None
        self._warning_banner.setVisible(False)

        self._card_net.set_value(0, unit="m\u00b3", fmt=",.3f")
        self._card_net._value.setText("\u2014")
        self._card_wastage.set_value(0, unit="%")
        self._card_wastage._value.setText("\u2014")
        self._card_gross.set_value(0, unit="m\u00b3", fmt=",.3f")
        self._card_gross._value.setText("\u2014")

        for card in self._mat_cards.values():
            card._value.setText("\u2014")

        self._table.clear()
        self._table.setMinimumHeight(220)
        self.btn_csv.setEnabled(False)
        self.btn_report.setEnabled(False)
        self._btn_cost.setEnabled(False)
