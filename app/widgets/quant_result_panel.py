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

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(QWidget())
        outer = QVBoxLayout(scroll.widget())
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

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
        self._table.setFixedHeight(280)
        outer.addWidget(self._table)

        # ── Export Buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
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
        outer.addLayout(btn_row)

        outer.addStretch()

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
        mu = up.mass_unit()
        vu = up.volume_unit()
        wu = up.water_unit()

        rows = [
            ("Cement",
             up.convert_mass_kg(td.cement_kg_per_m3),
             up.convert_mass_kg(bill.total_cement_kg), mu,
             f"{bill.total_cement_bags:.0f} bags"),
            ("Water (field)",
             up.convert_mass_kg(td.field_water_kg_per_m3),
             up.convert_mass_kg(bill.total_water_kg), mu,
             f"{up.convert_water_liters(bill.total_water_liters):.1f} {wu}"),
            ("Fine Aggregate (SSD)",
             up.convert_mass_kg(td.fine_aggregate_kg_per_m3),
             up.convert_mass_kg(bill.total_fine_aggregate_kg), mu,
             f"{up.convert_volume_m3(bill.total_fine_aggregate_bulk_m3):.3f} {vu}"),
            ("Fine Aggregate (field)",
             up.convert_mass_kg(td.field_fine_aggregate_kg_per_m3),
             up.convert_mass_kg(bill.total_fine_aggregate_kg), mu, ""),
            ("Coarse Aggregate (SSD)",
             up.convert_mass_kg(td.coarse_aggregate_kg_per_m3),
             up.convert_mass_kg(bill.total_coarse_aggregate_kg), mu,
             f"{up.convert_volume_m3(bill.total_coarse_aggregate_bulk_m3):.3f} {vu}"),
            ("Coarse Aggregate (field)",
             up.convert_mass_kg(td.field_coarse_aggregate_kg_per_m3),
             up.convert_mass_kg(bill.total_coarse_aggregate_kg), mu, ""),
        ]

        if bill.total_scm_kg > 0:
            rows.append(("SCM",
                         up.convert_mass_kg(td.scm_kg_per_m3),
                         up.convert_mass_kg(bill.total_scm_kg), mu, ""))

        if bill.total_admixture_kg > 0:
            rows.append(("Admixture",
                         up.convert_mass_kg(td.admixture_kg_per_m3),
                         up.convert_mass_kg(bill.total_admixture_kg), mu, ""))

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

        # Enable export
        self.btn_csv.setEnabled(True)
        self.btn_report.setEnabled(True)
        self._btn_cost.setEnabled(True)

    def on_unit_changed(self) -> None:
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
        self.btn_csv.setEnabled(False)
        self.btn_report.setEnabled(False)
        self._btn_cost.setEnabled(False)
