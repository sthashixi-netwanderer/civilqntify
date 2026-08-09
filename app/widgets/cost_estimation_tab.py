"""Cost Estimation tab — input form + results panel.

Layout follows Stitch "Civil Engineering Precision" design system:
- Left panel: scrollable form with editable quantities, material prices (GH₵),
  additional costs, project info, and estimate button
- Right panel: cost summary cards, material cost breakdown table,
  project summary with grand total, export buttons

All monetary values are in Ghana Cedis (GH₵).
Data flow:
  MaterialQuantifyTab → MaterialBill → this tab → CostEstimate → display
  OR standalone: user enters quantities directly
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.unit_preferences import get_unit_prefs
from app.widgets.cost_result_panel import CostResultPanel
from app.widgets.info_button import InfoButton
from app.widgets.report_preview_dialog import ReportPreviewDialog

# Default material prices in GH₵ (Ghana Cedis)
_DEFAULT_PRICES = {
    "cement_per_bag": 85.00,
    "fine_agg_per_m3": 350.00,
    "coarse_agg_per_m3": 400.00,
    "water_per_1000l": 15.00,
    "admixture_per_kg": 12.00,
}

# Default additional costs in GH₵ or percentage
_DEFAULT_ADDITIONAL = {
    "labour_count": 5.0,
    "labour_cost_per_unit": 150.00,
    "transport_per_m3": 80.00,
    "plant_overhead_pct": 10.0,
    "profit_pct": 15.0,
    "contingency_pct": 5.0,
}


@dataclass
class ManualCostBill:
    """Lightweight bill created from manual user input (no MaterialBill dependency)."""

    net_concrete_volume_m3: float
    wastage_percent: float
    gross_concrete_volume_m3: float
    total_cement_kg: float
    total_cement_bags: float
    cement_bag_weight_kg: float
    total_water_kg: float
    total_water_liters: float
    total_fine_aggregate_kg: float
    total_fine_aggregate_bulk_m3: float
    total_coarse_aggregate_kg: float
    total_coarse_aggregate_bulk_m3: float
    total_scm_kg: float
    total_admixture_kg: float


class CostEstimationTab(QWidget):
    """Tab for project cost estimation — standalone or from material quantification."""

    cost_estimated = pyqtSignal(dict)  # Emits cost data dict for external use

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bill = None  # MaterialBill or ManualCostBill
        self._is_standalone = True
        self._last_cost_data: dict | None = None
        self.unit_prefs = None  # Set by MainWindow
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        # Left: scrollable input form — responsive
        input_scroll = QScrollArea()
        input_scroll.setWidgetResizable(True)
        input_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        input_scroll.setMinimumWidth(360)
        input_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        input_widget = QWidget()
        self._form = QVBoxLayout(input_widget)
        self._form.setContentsMargins(16, 16, 12, 16)
        self._form.setSpacing(8)
        self._build_form()
        input_scroll.setWidget(input_widget)
        splitter.addWidget(input_scroll)

        # Right: result panel — expands
        self._result_panel = CostResultPanel()
        self._result_panel.setMinimumWidth(380)
        self._result_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._result_panel)

        splitter.setSizes([460, 740])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setHandleWidth(6)

        # Wire export buttons
        self._result_panel.btn_csv.clicked.connect(self._export_csv)
        self._result_panel.btn_pdf.clicked.connect(self._show_preview)

    def _build_form(self) -> None:
        # ── Status Banner ──
        self._status_banner = QLabel(
            "Standalone mode — enter material quantities manually."
        )
        self._status_banner.setObjectName("info-banner")
        self._status_banner.setWordWrap(True)
        self._status_banner.setStyleSheet(
            "background-color: #dbeafe; color: #1e40af; "
            "border: 1px solid #3b82f6; border-radius: 4px; "
            "padding: 10px 14px; font-weight: 600;"
        )
        self._form.addWidget(self._status_banner)

        # ── Material Quantities (editable) ──
        grp_data = self._group("Material Quantities")
        data_form = QFormLayout()
        data_form.setSpacing(8)
        data_form.setContentsMargins(12, 16, 12, 12)

        self._qty_spins: dict[str, QDoubleSpinBox] = {}
        qty_fields = [
            (
                "cement_bags",
                "Cement (Bags)",
                0.0,
                100000.0,
                0.0,
                0,
                "Total number of cement bags required.\n"
                "Standard bag = 50 kg (Ghana/International).\n"
                "Bags = total cement kg ÷ bag weight.",
            ),
            (
                "fine_agg_m3",
                "Fine Agg (m\u00b3)",
                0.0,
                100000.0,
                0.0,
                3,
                "Total volume of fine aggregate (sand) in m³.\n"
                "Convert from weight: V = mass / (SG × 1000).\n"
                "Order by bulk volume accounting for void content.",
            ),
            (
                "coarse_agg_m3",
                "Coarse Agg (m\u00b3)",
                0.0,
                100000.0,
                0.0,
                3,
                "Total volume of coarse aggregate (gravel) in m³.\n"
                "Convert from weight: V = mass / (SG × 1000).\n"
                "Typical bulk density: 1400–1700 kg/m³.",
            ),
            (
                "water_l",
                "Water (L)",
                0.0,
                1000000.0,
                0.0,
                1,
                "Total mixing water in litres.\n"
                "1 kg water = 1 litre.\n"
                "Field water may differ from design water due to\n"
                "aggregate moisture corrections.",
            ),
            (
                "scm_kg",
                "SCMs (kg)",
                0.0,
                100000.0,
                0.0,
                1,
                "Total Supplementary Cementitious Material in kg.\n"
                "Fly ash, GGBFS, or silica fume.\n"
                "Priced separately from cement if applicable.",
            ),
            (
                "admix_l",
                "Admix (L)",
                0.0,
                10000.0,
                0.0,
                3,
                "Total chemical admixture volume in litres.\n"
                "Superplasticizer, plasticizer, retarder, etc.\n"
                "Priced per litre or per kg depending on supplier.",
            ),
        ]
        for key, label_text, lo, hi, default, decimals, info in qty_fields:
            spin = self._spin(default, lo, hi, 10.0, decimals)
            spin.valueChanged.connect(self._on_input_changed)
            self._qty_spins[key] = spin
            data_form.addRow(self._label_with_info(label_text, info), spin)

        # Volume input
        self._volume_spin = self._spin(1.0, 0.01, 100000.0, 1.0, 2, suffix=" m\u00b3")
        self._volume_spin.valueChanged.connect(self._on_input_changed)
        data_form.addRow(
            self._label_with_info(
                "Total Volume",
                "Total gross volume of concrete including wastage. "
                "Cost per m\u00b3 is calculated from this volume.",
            ),
            self._volume_spin,
        )

        # Wastage input
        self._wastage_spin = self._spin(5.0, 0.0, 30.0, 0.5, 1, suffix="%")
        self._wastage_spin.valueChanged.connect(self._on_input_changed)
        data_form.addRow(
            self._label_with_info(
                "Wastage",
                "Percentage of material wastage allowed. "
                "Typically 3–10% depending on site conditions.",
            ),
            self._wastage_spin,
        )

        grp_data.setLayout(data_form)
        self._grp_data = grp_data
        self._form.addWidget(grp_data)

        # ── Material Prices (GH₵) ──
        grp_prices = self._group("Material Prices (GH\u20b5)")
        prices_form = QFormLayout()
        prices_form.setSpacing(8)
        prices_form.setContentsMargins(12, 16, 12, 12)

        self._price_spins: dict[str, QDoubleSpinBox] = {}
        price_fields = [
            (
                "cement_per_bag",
                "Cement (per bag)",
                0.01,
                10000.0,
                85.00,
                "Current market price per 50 kg bag in GH₵.\n"
                "Ghana range: GH₵ 60–120 depending on brand and region.\n"
                "Includes manufacturer margin but excludes transport.",
            ),
            (
                "fine_agg_per_m3",
                "Fine Agg (per m\u00b3)",
                0.01,
                50000.0,
                350.00,
                "Price per m³ of sand delivered to site in GH₵.\n"
                "Includes quarrying/river sand cost + transport.\n"
                "Void content affects actual vs loose volume.",
            ),
            (
                "coarse_agg_per_m3",
                "Coarse Agg (per m\u00b3)",
                0.01,
                50000.0,
                400.00,
                "Price per m³ of gravel/stone delivered to site in GH₵.\n"
                "Varies by size (20mm, 40mm) and source distance.\n"
                "Typically 10–20% higher than sand.",
            ),
            (
                "water_per_1000l",
                "Water (per 1000L)",
                0.01,
                1000.0,
                15.00,
                "Cost per 1000 litres of water supply in GH₵.\n"
                "Includes tanker/borehole/tap water costs.\n"
                "Some sites have free municipal water.",
            ),
            (
                "admixture_per_kg",
                "Admixture (per kg)",
                0.01,
                10000.0,
                12.00,
                "Price per kg of chemical admixture in GH₵.\n"
                "Varies by type: plasticizer, superplasticizer, retarder.\n"
                "Typical range: GH₵ 8–25 per kg depending on brand.",
            ),
        ]
        for key, label_text, lo, hi, default, info in price_fields:
            spin = self._spin(default, lo, hi, 5.0, 2, prefix="GH\u20b5 ")
            spin.valueChanged.connect(self._on_input_changed)
            self._price_spins[key] = spin
            prices_form.addRow(self._label_with_info(label_text, info), spin)

        # Reset button
        self._btn_reset_prices = QPushButton("Reset to Default Prices")
        self._btn_reset_prices.setObjectName("secondary")
        self._btn_reset_prices.clicked.connect(self._reset_prices)
        prices_form.addRow(self._btn_reset_prices)

        grp_prices.setLayout(prices_form)
        self._form.addWidget(grp_prices)

        # ── Additional Costs ──
        grp_addl = self._group("Additional Costs (GH\u20b5 or %)")
        addl_form = QFormLayout()
        addl_form.setSpacing(8)
        addl_form.setContentsMargins(12, 16, 12, 12)

        self._addl_spins: dict[str, QDoubleSpinBox] = {}
        addl_fields = [
            (
                "labour_count",
                "No. of Labourers",
                0.0,
                100.0,
                5.0,
                0,
                "",
                "Number of labourers required for the project.\n"
                "Includes skilled + unskilled workers for mixing,\n"
                "placing, compacting, and finishing.",
            ),
            (
                "labour_cost_per_unit",
                "Cost per Labourer (GH\u20b5)",
                0.0,
                10000.0,
                150.00,
                2,
                "GH\u20b5 ",
                "Daily unit cost per labourer.\n"
                "Ghana range: GH₵ 100–300/day depending on skill level.\n"
                "Total labour cost = No. of labourers × Cost per labourer.",
            ),
            (
                "transport_per_m3",
                "Transport (GH\u20b5/m\u00b3)",
                0.0,
                10000.0,
                80.00,
                2,
                "GH\u20b5 ",
                "Transport cost per m³ of concrete or materials.\n"
                "Higher for remote sites or ready-mix delivery.\n"
                "Includes fuel, vehicle, and driver costs.",
            ),
            (
                "plant_overhead_pct",
                "Plant/Overhead (%)",
                0.0,
                50.0,
                10.0,
                1,
                "",
                "Percentage of (material + labour + transport) for:\n"
                "  • Equipment depreciation\n"
                "  • Site facilities\n"
                "  • Supervision & management\n"
                "  • Insurance & utilities\n"
                "Typical: 8–15%.",
            ),
            (
                "profit_pct",
                "Profit (%)",
                0.0,
                50.0,
                15.0,
                1,
                "",
                "Contractor profit margin on total cost.\n"
                "Typical: 10–20% depending on project size and risk.\n"
                "Applied to (material + labour + transport + overhead).",
            ),
            (
                "contingency_pct",
                "Contingency (%)",
                0.0,
                30.0,
                5.0,
                1,
                "",
                "Buffer for unforeseen costs (price fluctuations,\n"
                "  design changes, weather delays, waste).\n"
                "Typical: 3–10%. Applied to subtotal.",
            ),
        ]
        for key, label_text, lo, hi, default, decimals, pfx, info in addl_fields:
            spin = self._spin(default, lo, hi, 1.0, decimals, prefix=pfx)
            spin.valueChanged.connect(self._on_input_changed)
            self._addl_spins[key] = spin
            addl_form.addRow(self._label_with_info(label_text, info), spin)

        grp_addl.setLayout(addl_form)
        self._form.addWidget(grp_addl)

        # ── Project Information ──
        grp_proj = self._group("Project Information")
        proj_form = QFormLayout()
        proj_form.setSpacing(8)
        proj_form.setContentsMargins(12, 16, 12, 12)

        self._proj_name = QLineEdit()
        self._proj_name.setPlaceholderText("e.g., Terminal 3 Expansion")
        self._proj_location = QLineEdit()
        self._proj_location.setPlaceholderText("e.g., Accra")
        self._proj_client = QLineEdit()
        self._proj_client.setPlaceholderText("e.g., GAA")
        self._proj_date = QDateEdit()
        self._proj_date.setDate(date.today())
        self._proj_date.setCalendarPopup(True)

        proj_form.addRow(
            self._label_with_info(
                "Project Name",
                "Official project name as it appears on contract documents.\n"
                "Used in the report header and PDF export.",
            ),
            self._proj_name,
        )
        proj_form.addRow(
            self._label_with_info(
                "Location",
                "Project site city or region.\n"
                "Affects transport costs and material availability.",
            ),
            self._proj_location,
        )
        proj_form.addRow(
            self._label_with_info(
                "Client",
                "Client or organisation commissioning the project.\n"
                "Appears on official cost estimate documents.",
            ),
            self._proj_client,
        )
        proj_form.addRow(
            self._label_with_info(
                "Date",
                "Date of the cost estimate.\n"
                "Defaults to today's date. Material prices should\n"
                "reflect current market rates as of this date.",
            ),
            self._proj_date,
        )

        grp_proj.setLayout(proj_form)
        self._form.addWidget(grp_proj)

        # ── Estimate Button ──
        self._form.addSpacing(8)
        self.calc_btn = QPushButton("  Estimate Project Cost")
        self.calc_btn.setMinimumHeight(44)
        self.calc_btn.clicked.connect(self._on_estimate)
        self._form.addWidget(self.calc_btn)

        self._form.addStretch()

    # ── Helpers ──────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        return QGroupBox(title)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 0.05em; color: #444653;"
        )
        return lbl

    def _label_with_info(self, text: str, info: str) -> QWidget:
        """Create a label with an info button beside it."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        lbl = self._label(text)
        layout.addWidget(lbl)
        btn = InfoButton(info)
        layout.addWidget(btn)
        layout.addStretch()
        container = QWidget()
        container.setLayout(layout)
        return container

    def _spin(
        self,
        default: float,
        lo: float,
        hi: float,
        step: float,
        decimals: int = 2,
        prefix: str = "",
        suffix: str = "",
    ) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(default)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        if prefix:
            sb.setPrefix(prefix)
        if suffix:
            sb.setSuffix(suffix)
        sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return sb

    def on_unit_changed(self) -> None:
        """Update spinbox suffixes when unit preferences change."""
        if self.unit_prefs is None:
            return
        up = self.unit_prefs

        # Block signals
        self._volume_spin.blockSignals(True)

        # Snapshot metric value
        if not hasattr(self, '_metric_snapshot'):
            self._metric_snapshot = {
                'volume': self._volume_spin.value(),
            }

        ms = self._metric_snapshot

        # Apply conversion
        self._volume_spin.setValue(up.convert_volume_m3(ms['volume']))
        self._volume_spin.setSuffix(f" {up.volume_unit()}")

        # Unblock signals
        self._volume_spin.blockSignals(False)

    # ── Data Handoff (public API) ────────────────────────────────────

    def load_bill(self, bill) -> None:
        """Load material bill data into the cost estimation tab.

        Called by MaterialQuantifyTab when user clicks 'Send to Cost Estimation'.
        Can accept MaterialBill or ManualCostBill.
        """
        self._bill = bill
        self._is_standalone = False
        self._populate_quantities(bill)
        self._status_banner.setText(
            f"Quantification loaded  |  "
            f"Gross Volume: {bill.gross_concrete_volume_m3:.3f} m\u00b3  |  "
            f"Cement: {bill.total_cement_bags:.0f} bags  |  "
            f"FA: {bill.total_fine_aggregate_bulk_m3:.3f} m\u00b3  |  "
            f"CA: {bill.total_coarse_aggregate_bulk_m3:.3f} m\u00b3"
        )
        self._status_banner.setStyleSheet(
            "background-color: #d1fae5; color: #065f46; "
            "border: 1px solid #10b981; border-radius: 4px; "
            "padding: 10px 14px; font-weight: 600;"
        )

    def _populate_quantities(self, bill) -> None:
        """Fill the editable quantity spinboxes."""
        m = self._qty_spins
        m["cement_bags"].setValue(bill.total_cement_bags)
        m["fine_agg_m3"].setValue(bill.total_fine_aggregate_bulk_m3)
        m["coarse_agg_m3"].setValue(bill.total_coarse_aggregate_bulk_m3)
        m["water_l"].setValue(bill.total_water_liters)
        m["scm_kg"].setValue(bill.total_scm_kg)
        m["admix_l"].setValue(bill.total_admixture_kg)
        self._volume_spin.setValue(bill.gross_concrete_volume_m3)

    # ── Price Management ─────────────────────────────────────────────

    def _reset_prices(self) -> None:
        """Reset material prices to Ghana Cedis defaults."""
        defaults = _DEFAULT_PRICES
        for key, spin in self._price_spins.items():
            spin.setValue(defaults.get(key, 0.0))

    # ── Cost Estimation ──────────────────────────────────────────────

    def _on_input_changed(self) -> None:
        """Handle input changes (placeholder for live preview)."""
        pass

    def _build_bill_from_inputs(self):
        """Create a ManualCostBill from current spinbox values."""
        gross_vol = self._volume_spin.value()
        wastage = self._wastage_spin.value()
        net_vol = gross_vol / (1.0 + wastage / 100.0) if wastage < 100 else gross_vol

        cement_bags = self._qty_spins["cement_bags"].value()
        bag_weight = 50.0  # Standard 50 kg bag

        return ManualCostBill(
            net_concrete_volume_m3=net_vol,
            wastage_percent=wastage,
            gross_concrete_volume_m3=gross_vol,
            total_cement_kg=cement_bags * bag_weight,
            total_cement_bags=cement_bags,
            cement_bag_weight_kg=bag_weight,
            total_water_kg=self._qty_spins["water_l"].value(),
            total_water_liters=self._qty_spins["water_l"].value(),
            total_fine_aggregate_kg=0.0,  # Not used in cost calc
            total_fine_aggregate_bulk_m3=self._qty_spins["fine_agg_m3"].value(),
            total_coarse_aggregate_kg=0.0,  # Not used in cost calc
            total_coarse_aggregate_bulk_m3=self._qty_spins["coarse_agg_m3"].value(),
            total_scm_kg=self._qty_spins["scm_kg"].value(),
            total_admixture_kg=self._qty_spins["admix_l"].value(),
        )

    def _on_estimate(self) -> None:
        """Run cost estimation based on loaded bill and input prices."""
        # Build bill from current inputs (standalone or loaded)
        bill = self._build_bill_from_inputs()

        gross_vol = bill.gross_concrete_volume_m3
        if gross_vol <= 0:
            QMessageBox.warning(
                self,
                "Invalid Volume",
                "Total volume must be greater than zero.",
            )
            return

        # Material prices (GH₵)
        cement_price = self._price_spins["cement_per_bag"].value()
        fa_price = self._price_spins["fine_agg_per_m3"].value()
        ca_price = self._price_spins["coarse_agg_per_m3"].value()
        water_price = self._price_spins["water_per_1000l"].value()
        admix_price = self._price_spins["admixture_per_kg"].value()

        # Material costs
        cement_cost = bill.total_cement_bags * cement_price
        fa_cost = bill.total_fine_aggregate_bulk_m3 * fa_price
        ca_cost = bill.total_coarse_aggregate_bulk_m3 * ca_price
        water_cost = (bill.total_water_liters / 1000.0) * water_price
        admix_cost = bill.total_admixture_kg * admix_price
        total_material = cement_cost + fa_cost + ca_cost + water_cost + admix_cost

        # Per m³
        mat_cost_m3 = total_material / gross_vol if gross_vol > 0 else 0.0

        # Additional costs
        labour_count = self._addl_spins["labour_count"].value()
        labour_cost_per_unit = self._addl_spins["labour_cost_per_unit"].value()
        labour = labour_count * labour_cost_per_unit
        transport = self._addl_spins["transport_per_m3"].value() * gross_vol
        overhead_pct = self._addl_spins["plant_overhead_pct"].value() / 100.0
        profit_pct = self._addl_spins["profit_pct"].value() / 100.0
        contingency_pct = self._addl_spins["contingency_pct"].value() / 100.0

        overhead_profit = (total_material + labour + transport) * (
            overhead_pct + profit_pct
        )
        subtotal = total_material + labour + transport + overhead_profit
        contingency = subtotal * contingency_pct
        grand_total = subtotal + contingency

        # Cost per bag of concrete
        cost_per_bag = (
            grand_total / bill.total_cement_bags if bill.total_cement_bags > 0 else 0.0
        )

        # Build result data
        self._last_cost_data = {
            "material_cost_per_m3": mat_cost_m3,
            "total_material_cost": total_material,
            "total_project_cost": grand_total,
            "cost_per_bag": cost_per_bag,
            "material_breakdown": [
                {
                    "name": "Cement",
                    "qty": bill.total_cement_bags,
                    "unit": "bags",
                    "unit_price": cement_price,
                    "total": cement_cost,
                },
                {
                    "name": "Fine Aggregate",
                    "qty": bill.total_fine_aggregate_bulk_m3,
                    "unit": "m\u00b3",
                    "unit_price": fa_price,
                    "total": fa_cost,
                },
                {
                    "name": "Coarse Aggregate",
                    "qty": bill.total_coarse_aggregate_bulk_m3,
                    "unit": "m\u00b3",
                    "unit_price": ca_price,
                    "total": ca_cost,
                },
                {
                    "name": "Water",
                    "qty": bill.total_water_liters / 1000.0,
                    "unit": "1000L",
                    "unit_price": water_price,
                    "total": water_cost,
                },
                {
                    "name": "Admixture",
                    "qty": bill.total_admixture_kg,
                    "unit": "kg",
                    "unit_price": admix_price,
                    "total": admix_cost,
                },
            ],
            "summary_rows": [
                {"label": "Material Cost", "amount": total_material},
                {"label": "Labour & Transport", "amount": labour + transport},
                {
                    "label": f"Overhead & Profit ({(overhead_pct + profit_pct) * 100:.0f}%)",
                    "amount": overhead_profit,
                },
                {"label": "Subtotal", "amount": subtotal, "is_subtotal": True},
                {
                    "label": f"Contingency ({contingency_pct * 100:.0f}%)",
                    "amount": contingency,
                },
                {"label": "GRAND TOTAL", "amount": grand_total, "is_total": True},
            ],
            "project_info": {
                "name": self._proj_name.text(),
                "location": self._proj_location.text(),
                "client": self._proj_client.text(),
                "date": self._proj_date.date().toString("yyyy-MM-dd"),
            },
        }

        self._result_panel.display_cost(self._last_cost_data)
        self.cost_estimated.emit(self._last_cost_data)

        self._auto_save_history(self._last_cost_data)

        if hasattr(self.window(), "status_bar"):
            self.window().status_bar.showMessage(
                f"Cost estimated \u2014 Grand Total: GH\u20b5 {grand_total:,.2f}  |  "
                f"Per m\u00b3: GH\u20b5 {mat_cost_m3:,.2f}  |  "
                f"Material: GH\u20b5 {total_material:,.2f}",
                8000,
            )

    # ── History ──────────────────────────────────────────────────────

    _history_db = None  # Set by MainWindow

    def _auto_save_history(self, cost_data: dict) -> None:
        """Auto-save cost estimation result to history DB."""
        if self._history_db is None:
            return
        try:
            proj_info = cost_data.get("project_info", {})
            name = proj_info.get("name", "").strip()
            if not name:
                name = "Cost Estimate"
            else:
                name = f"Cost Estimate - {name}"
            self._history_db.save_cost_estimation(cost_data, name=name)
        except Exception:
            pass  # Don't break the UI for history failures

    def load_from_history(self, calc_id: int) -> None:
        """Load a cost estimation record from history into this tab."""
        if self._history_db is None:
            return
        # Restored records carry locally-edited prices — make them editable.
        rec = self._history_db.get_calculation(calc_id)
        if rec is None:
            return
        import json
        try:
            data = json.loads(rec["result_json"])
        except (json.JSONDecodeError, TypeError):
            return
        self._last_cost_data = data
        self._result_panel.display_cost(data)

        # Restore project info inputs
        proj_info = data.get("project_info", {})
        self._proj_name.setText(proj_info.get("name", ""))
        self._proj_location.setText(proj_info.get("location", ""))
        self._proj_client.setText(proj_info.get("client", ""))
        from PyQt6.QtCore import QDate
        date_str = proj_info.get("date", "")
        if date_str:
            self._proj_date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))

        # Restore material quantities and prices if available
        breakdown = data.get("material_breakdown", [])
        for item in breakdown:
            name = item.get("name")
            qty = item.get("qty", 0.0)
            price = item.get("unit_price", 0.0)
            if name == "Cement":
                self._qty_spins["cement_bags"].setValue(qty)
                self._price_spins["cement_per_bag"].setValue(price)
            elif name == "Fine Aggregate":
                self._qty_spins["fine_agg_m3"].setValue(qty)
                self._price_spins["fine_agg_per_m3"].setValue(price)
            elif name == "Coarse Aggregate":
                self._qty_spins["coarse_agg_m3"].setValue(qty)
                self._price_spins["coarse_agg_per_m3"].setValue(price)
            elif name == "Water":
                self._qty_spins["water_l"].setValue(qty * 1000.0)
                self._price_spins["water_per_1000l"].setValue(price)
            elif name == "Admixture":
                self._qty_spins["admix_l"].setValue(qty)
                self._price_spins["admixture_per_kg"].setValue(price)

        # Restore concrete volume from per m3 cost and total cost
        mat_cost_m3 = data.get("material_cost_per_m3", 0.0)
        total_material = data.get("total_material_cost", 0.0)
        if mat_cost_m3 > 0.0:
            self._volume_spin.setValue(total_material / mat_cost_m3)

    # ── Export ────────────────────────────────────────────────────────

    def _generate_cost_report_html(self) -> str:
        """Generate HTML report for cost estimation preview."""
        data = self._last_cost_data
        if not data:
            return ""

        proj = data.get("project_info", {})
        breakdown = data.get("material_breakdown", [])
        summary = data.get("summary_rows", [])

        # Build material breakdown rows
        material_rows = ""
        for i, row in enumerate(breakdown):
            bg_class = "zebra-row" if i % 2 == 0 else ""
            material_rows += f"""
            <tr class="{bg_class} border-b border-outline-variant">
                <td class="py-sm px-md font-body-md text-on-surface">{row["name"]}</td>
                <td class="py-sm px-md text-right font-data-table">{row["qty"]:,.2f}</td>
                <td class="py-sm px-md text-right font-data-table">{row["unit"]}</td>
                <td class="py-sm px-md text-right font-data-table">{row["unit_price"]:,.2f}</td>
                <td class="py-sm px-md text-right font-data-table">{row["total"]:,.2f}</td>
            </tr>"""

        # Build summary rows
        summary_rows = ""
        for row in summary:
            if row.get("is_total"):
                summary_rows += f"""
                <div class="flex justify-between border-t-2 border-primary pt-sm mt-sm">
                    <span class="font-body-md font-bold text-primary">{row["label"]}</span>
                    <span class="font-data-table font-bold text-primary text-[15px]">GH₵ {row["amount"]:,.2f}</span>
                </div>"""
            elif row.get("is_subtotal"):
                summary_rows += f"""
                <div class="flex justify-between border-t border-outline-variant pt-sm mt-sm">
                    <span class="font-body-md font-semibold">{row["label"]}</span>
                    <span class="font-data-table font-semibold">GH₵ {row["amount"]:,.2f}</span>
                </div>"""
            else:
                summary_rows += f"""
                <div class="flex justify-between">
                    <span class="font-body-md text-on-surface-variant">{row["label"]}</span>
                    <span class="font-data-table">GH₵ {row["amount"]:,.2f}</span>
                </div>"""

        # Calculate additional costs for the report
        gross_vol = self._volume_spin.value()
        labour_total = self._addl_spins["labour_count"].value() * self._addl_spins["labour_cost_per_unit"].value()
        transport_total = self._addl_spins["transport_per_m3"].value() * gross_vol
        overhead_pct = self._addl_spins["plant_overhead_pct"].value()
        profit_pct = self._addl_spins["profit_pct"].value()
        contingency_pct = self._addl_spins["contingency_pct"].value()

        html = f"""<!DOCTYPE html>
<html class="light" lang="en">
<head>
    <meta charset="utf-8"/>
    <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
    <title>Project Cost Estimate - CivilQntify</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    <script>
        tailwind.config = {{
            darkMode: "class",
            theme: {{
                extend: {{
                    "colors": {{
                        "primary": "#00288e",
                        "primary-container": "#1e40af",
                        "on-primary": "#ffffff",
                        "on-primary-container": "#a8b8ff",
                        "surface": "#fbf8ff",
                        "surface-container": "#eeedf7",
                        "surface-container-low": "#f4f2fc",
                        "surface-container-high": "#e8e7f1",
                        "surface-container-lowest": "#ffffff",
                        "on-surface": "#1a1b22",
                        "on-surface-variant": "#444653",
                        "outline": "#757684",
                        "outline-variant": "#c4c5d5"
                    }},
                    "fontFamily": {{
                        "body-md": ["Inter"],
                        "section-header": ["Inter"],
                        "headline-md": ["Inter"],
                        "data-table": ["JetBrains Mono"],
                        "label-caps": ["Inter"],
                        "headline-lg": ["Inter"],
                        "data-display": ["JetBrains Mono"]
                    }},
                    "fontSize": {{
                        "body-md": ["14px", {{"lineHeight": "20px", "fontWeight": "400"}}],
                        "section-header": ["12px", {{"lineHeight": "16px", "letterSpacing": "0.1em", "fontWeight": "700"}}],
                        "headline-md": ["24px", {{"lineHeight": "32px", "letterSpacing": "-0.01em", "fontWeight": "600"}}],
                        "data-table": ["13px", {{"lineHeight": "18px", "fontWeight": "400"}}],
                        "label-caps": ["11px", {{"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "600"}}],
                        "headline-lg": ["30px", {{"lineHeight": "36px", "letterSpacing": "-0.02em", "fontWeight": "700"}}],
                        "data-display": ["16px", {{"lineHeight": "24px", "fontWeight": "500"}}]
                    }}
                }},
            }},
        }}
    </script>
    <style>
        @media print {{
            .no-print {{ display: none; }}
            body {{ background: white; padding: 0; }}
            .pdf-container {{ border: none; box-shadow: none; width: 100%; max-width: 100%; margin: 0; }}
        }}
        .pdf-page-border {{ border: 1px solid #e2e8f0; }}
        .zebra-row:nth-child(even) {{ background-color: #f1f5f9; }}
        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
    </style>
</head>
<body class="bg-surface-container-low text-on-surface font-body-md min-h-screen">
    <!-- Top Navigation Bar -->
    <header class="w-full top-0 bg-surface border-b border-outline-variant no-print z-50 fixed">
        <div class="flex justify-between items-center px-5 py-3 w-full max-w-[1280px] mx-auto">
            <div class="flex items-center gap-3">
                <span class="font-headline-md text-primary font-bold">CivilQntify</span>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="pt-20 pb-8 px-5 flex justify-center">
        <!-- PDF Template Container -->
        <div class="pdf-container pdf-page-border bg-white w-full max-w-[850px] min-h-[1100px] shadow-sm p-8 flex flex-col relative">
            <!-- Document Header -->
            <header class="flex justify-between items-start border-b border-outline-variant pb-4 mb-8">
                <div>
                    <h1 class="text-primary font-headline-md text-[24px] leading-[32px] mb-1">PROJECT COST ESTIMATE</h1>
                    <div class="space-y-1">
                        <div class="flex items-center gap-2">
                            <span class="font-label-caps text-[11px] text-on-surface-variant w-24 uppercase">Project</span>
                            <span class="font-body-md text-[14px] font-semibold">{proj.get("name", "N/A")}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="font-label-caps text-[11px] text-on-surface-variant w-24 uppercase">Location</span>
                            <span class="font-body-md text-[14px]">{proj.get("location", "N/A")}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="font-label-caps text-[11px] text-on-surface-variant w-24 uppercase">Client</span>
                            <span class="font-body-md text-[14px]">{proj.get("client", "N/A")}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="font-label-caps text-[11px] text-on-surface-variant w-24 uppercase">Date</span>
                            <span class="font-body-md text-[14px]">{proj.get("date", "N/A")}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="font-headline-md text-[24px] font-bold text-primary mb-1">CivilQntify</div>
                    <p class="text-on-surface-variant font-label-caps text-[11px]">Engineering Precision Systems</p>
                </div>
            </header>

            <!-- Section 1: Grand Total Highlight -->
            <section class="mb-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                <div class="space-y-4">
                    <h3 class="font-section-header text-[12px] text-primary uppercase tracking-[0.1em] font-bold">Financial Summary</h3>
                    <div class="bg-surface-container rounded p-4 space-y-2">
                        <div class="flex justify-between">
                            <span class="font-body-md text-[14px] text-on-surface-variant">Material Subtotal</span>
                            <span class="font-data-table text-[13px]">GH₵ {data["total_material_cost"]:,.2f}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="font-body-md text-[14px] text-on-surface-variant">Labour & Transport</span>
                            <span class="font-data-table text-[13px]">GH₵ {labour_total + transport_total:,.2f}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="font-body-md text-[14px] text-on-surface-variant">Overhead & Profit ({overhead_pct + profit_pct:.0f}%)</span>
                            <span class="font-data-table text-[13px]">GH₵ {(data["total_material_cost"] + labour_total + transport_total) * (overhead_pct + profit_pct) / 100:,.2f}</span>
                        </div>
                        <div class="flex justify-between border-t border-outline-variant pt-2">
                            <span class="font-body-md text-[14px] text-on-surface-variant">Subtotal</span>
                            <span class="font-data-table text-[13px]">GH₵ {data["total_project_cost"] / (1 + contingency_pct / 100):,.2f}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="font-body-md text-[14px] text-on-surface-variant">Contingency ({contingency_pct:.0f}%)</span>
                            <span class="font-data-table text-[13px]">GH₵ {data["total_project_cost"] * contingency_pct / (100 + contingency_pct):,.2f}</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col justify-center items-end border-l border-outline-variant pl-8">
                    <span class="font-label-caps text-[11px] text-on-surface-variant uppercase mb-1 text-right">Grand Estimated Total</span>
                    <div class="text-primary flex flex-col items-end">
                        <span class="font-data-display text-[24px] font-bold">GH₵ {data["total_project_cost"]:,.2f}</span>
                        <div class="h-1 w-full bg-primary mt-1"></div>
                    </div>
                    <p class="text-on-surface-variant font-label-caps text-[11px] mt-4 italic">All values in Ghana Cedis (GH₵)</p>
                </div>
            </section>

            <!-- Section 2: Material Cost Breakdown -->
            <section class="mb-8">
                <h3 class="font-section-header text-[12px] text-primary uppercase mb-4 flex items-center gap-2 tracking-[0.1em] font-bold">
                    <span class="material-symbols-outlined text-[16px]">inventory_2</span> 01. Material Cost Breakdown
                </h3>
                <table class="w-full border-collapse">
                    <thead>
                        <tr class="bg-surface-container-high border-y border-outline-variant">
                            <th class="text-left py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase">Material Description</th>
                            <th class="text-right py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase w-24">Qty</th>
                            <th class="text-right py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase w-20">Unit</th>
                            <th class="text-right py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase w-32">Unit Price</th>
                            <th class="text-right py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase w-40">Total (GH₵)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {material_rows}
                    </tbody>
                </table>
            </section>

            <!-- Section 3: Additional Costs -->
            <section class="mb-8">
                <h3 class="font-section-header text-[12px] text-primary uppercase mb-4 flex items-center gap-2 tracking-[0.1em] font-bold">
                    <span class="material-symbols-outlined text-[16px]">payments</span> 02. Additional Direct & Indirect Costs
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <table class="w-full border-collapse">
                        <thead>
                            <tr class="bg-surface-container-high border-y border-outline-variant">
                                <th class="text-left py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase">Cost Center</th>
                                <th class="text-right py-2 px-4 font-label-caps text-[11px] text-on-surface uppercase">Total (GH₵)</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr class="zebra-row border-b border-outline-variant">
                                <td class="py-2 px-4 font-body-md text-[14px] text-on-surface">Labour (Skilled/Unskilled)</td>
                                <td class="py-2 px-4 text-right font-data-table text-[13px]">{labour_total:,.2f}</td>
                            </tr>
                            <tr class="zebra-row border-b border-outline-variant">
                                <td class="py-2 px-4 font-body-md text-[14px] text-on-surface">Transport & Logistics</td>
                                <td class="py-2 px-4 text-right font-data-table text-[13px]">{transport_total:,.2f}</td>
                            </tr>
                            <tr class="zebra-row border-b border-outline-variant">
                                <td class="py-2 px-4 font-body-md text-[14px] text-on-surface">Plant & Overhead ({overhead_pct:.0f}%)</td>
                                <td class="py-2 px-4 text-right font-data-table text-[13px]">{data["total_material_cost"] * overhead_pct / 100:,.2f}</td>
                            </tr>
                            <tr class="zebra-row border-b border-outline-variant">
                                <td class="py-2 px-4 font-body-md text-[14px] text-on-surface">Profit ({profit_pct:.0f}%)</td>
                                <td class="py-2 px-4 text-right font-data-table text-[13px]">{data["total_material_cost"] * profit_pct / 100:,.2f}</td>
                            </tr>
                        </tbody>
                    </table>
                    <div class="p-4 border border-outline-variant rounded bg-surface-container-low flex flex-col justify-center">
                        <div class="flex items-start gap-3">
                            <span class="material-symbols-outlined text-primary text-[40px]">info</span>
                            <div>
                                <h4 class="font-body-md text-[14px] font-bold mb-1">Technical Note</h4>
                                <p class="text-on-surface-variant font-body-md text-[14px] leading-relaxed">
                                    This estimate is based on current material prices and standard labour rates. 
                                    Actual costs may vary based on market conditions, supplier agreements, and 
                                    project-specific factors. Contingency of {contingency_pct:.0f}% has been included.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Signature & Approval -->
            <section class="mt-auto pt-8 border-t border-outline-variant">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <div class="w-full border-b border-gray-400 max-w-[240px] h-12 mb-1"></div>
                        <p class="font-label-caps text-[11px] text-on-surface-variant uppercase">Prepared By: Lead Quantity Surveyor</p>
                    </div>
                    <div>
                        <div class="w-full border-b border-gray-400 max-w-[240px] h-12 mb-1"></div>
                        <p class="font-label-caps text-[11px] text-on-surface-variant uppercase">Approved By: Project Manager</p>
                    </div>
                </div>
            </section>

            <!-- Footer -->
            <footer class="mt-8 flex justify-between items-center text-on-surface-variant font-label-caps text-[11px] pt-4 border-t border-outline-variant">
                <div class="flex items-center gap-2">
                    <span class="text-primary font-bold">CivilQntify</span>
                    <span>• Generated by CivilQntify Technical Systems</span>
                </div>
                <div class="flex items-center gap-3">
                    <span>Page 1 of 1</span>
                    <span class="material-symbols-outlined text-[14px]">lock</span>
                </div>
            </footer>
        </div>
    </main>
</body>
</html>"""
        return html

    def _show_preview(self) -> None:
        """Show the report preview dialog."""
        if not self._last_cost_data:
            QMessageBox.warning(
                self,
                "No Data",
                "No cost estimate to preview. Please estimate costs first.",
            )
            return

        html = self._generate_cost_report_html()
        dialog = ReportPreviewDialog(self, title="Cost Estimate Report Preview")
        dialog.set_html(html)
        dialog.set_export_callback(self._do_export_pdf)
        dialog.exec()

    def _do_export_pdf(self) -> None:
        """Actually export the PDF after preview."""
        if not self._last_cost_data:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cost Report PDF", "cost_estimate.pdf", "PDF (*.pdf)"
        )
        if path:
            try:
                from fpdf import FPDF

                data = self._last_cost_data
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()

                # Add Unicode font
                pdf.add_font(
                    "DejaVu",
                    "",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    uni=True,
                )
                pdf.add_font(
                    "DejaVu",
                    "B",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    uni=True,
                )
                pdf.add_font(
                    "DejaVu",
                    "I",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
                    uni=True,
                )

                # Title
                pdf.set_font("DejaVu", "B", 18)
                pdf.cell(
                    0,
                    12,
                    "Cost Estimate Report",
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="C",
                )
                pdf.set_font("DejaVu", "", 10)
                pdf.cell(
                    0,
                    8,
                    "CivilQntify - Concrete Quantification Tool",
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="C",
                )
                pdf.ln(8)

                # Project info
                proj = data.get("project_info", {})
                if proj.get("name"):
                    pdf.set_font("DejaVu", "B", 11)
                    pdf.cell(0, 7, "PROJECT INFORMATION", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("DejaVu", "", 10)
                    pdf.cell(
                        0,
                        6,
                        f"Project: {proj.get('name', 'N/A')}",
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )
                    pdf.cell(
                        0,
                        6,
                        f"Location: {proj.get('location', 'N/A')}",
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )
                    pdf.cell(
                        0,
                        6,
                        f"Client: {proj.get('client', 'N/A')}",
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )
                    pdf.cell(
                        0,
                        6,
                        f"Date: {proj.get('date', 'N/A')}",
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )
                    pdf.ln(6)

                # Summary
                pdf.set_font("DejaVu", "B", 11)
                pdf.cell(0, 7, "COST SUMMARY", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("DejaVu", "", 10)
                pdf.cell(
                    0,
                    6,
                    f"Material Cost / m\u00b3: GH\u20b5 {data['material_cost_per_m3']:,.2f}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.cell(
                    0,
                    6,
                    f"Total Material Cost: GH\u20b5 {data['total_material_cost']:,.2f}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.cell(
                    0,
                    6,
                    f"Total Project Cost: GH\u20b5 {data['total_project_cost']:,.2f}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.cell(
                    0,
                    6,
                    f"Cost / Bag: GH\u20b5 {data['cost_per_bag']:,.2f}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.ln(6)

                # Material breakdown table
                pdf.set_font("DejaVu", "B", 11)
                pdf.cell(0, 7, "MATERIAL COST BREAKDOWN", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("DejaVu", "B", 9)
                pdf.cell(50, 6, "Material", border=1)
                pdf.cell(30, 6, "Qty", border=1, align="R")
                pdf.cell(25, 6, "Unit", border=1)
                pdf.cell(35, 6, "Unit Price", border=1, align="R")
                pdf.cell(40, 6, "Total Cost", border=1, align="R")
                pdf.ln()
                pdf.set_font("DejaVu", "", 9)
                for row in data["material_breakdown"]:
                    pdf.cell(50, 6, row["name"], border=1)
                    pdf.cell(30, 6, f"{row['qty']:,.2f}", border=1, align="R")
                    pdf.cell(25, 6, row["unit"], border=1)
                    pdf.cell(
                        35, 6, f"GH\u20b5 {row['unit_price']:,.2f}", border=1, align="R"
                    )
                    pdf.cell(
                        40, 6, f"GH\u20b5 {row['total']:,.2f}", border=1, align="R"
                    )
                    pdf.ln()
                pdf.ln(6)

                # Project summary
                pdf.set_font("DejaVu", "B", 11)
                pdf.cell(0, 7, "PROJECT SUMMARY", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("DejaVu", "", 10)
                for row in data["summary_rows"]:
                    if row.get("is_total"):
                        pdf.set_font("DejaVu", "B", 12)
                        pdf.cell(
                            0,
                            8,
                            f"{row['label']}: GH\u20b5 {row['amount']:,.2f}",
                            new_x="LMARGIN",
                            new_y="NEXT",
                        )
                        pdf.set_font("DejaVu", "", 10)
                    elif row.get("is_subtotal"):
                        pdf.set_font("DejaVu", "B", 10)
                        pdf.cell(
                            0,
                            7,
                            f"{row['label']}: GH\u20b5 {row['amount']:,.2f}",
                            new_x="LMARGIN",
                            new_y="NEXT",
                        )
                        pdf.set_font("DejaVu", "", 10)
                    else:
                        pdf.cell(
                            0,
                            6,
                            f"{row['label']}: GH\u20b5 {row['amount']:,.2f}",
                            new_x="LMARGIN",
                            new_y="NEXT",
                        )

                # Disclaimer
                pdf.ln(10)
                pdf.set_font("DejaVu", "I", 8)
                pdf.multi_cell(
                    0,
                    4,
                    "Disclaimer: This estimate is for planning purposes only. "
                    "Actual costs may vary based on market conditions, supplier "
                    "agreements, and project-specific factors. All values in "
                    "Ghana Cedis (GH\u20b5).",
                )

                pdf.output(path)
                self.window().status_bar.showMessage(f"PDF saved to {path}", 5000)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "PDF Export",
                    f"Error exporting PDF: {str(e)}",
                )

    def _export_csv(self) -> None:
        if not self._last_cost_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cost Report CSV", "cost_estimate.csv", "CSV (*.csv)"
        )
        if path:
            data = self._last_cost_data
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(["CivilQntify - Cost Estimate Report"])
            writer.writerow([])

            # Project info
            proj = data.get("project_info", {})
            writer.writerow(["Project", proj.get("name", "")])
            writer.writerow(["Location", proj.get("location", "")])
            writer.writerow(["Client", proj.get("client", "")])
            writer.writerow(["Date", proj.get("date", "")])
            writer.writerow([])

            # Summary
            writer.writerow(["SUMMARY"])
            writer.writerow(
                [
                    "Material Cost / m\u00b3",
                    f"GH\u20b5 {data['material_cost_per_m3']:,.2f}",
                ]
            )
            writer.writerow(
                ["Total Material Cost", f"GH\u20b5 {data['total_material_cost']:,.2f}"]
            )
            writer.writerow(
                ["Total Project Cost", f"GH\u20b5 {data['total_project_cost']:,.2f}"]
            )
            writer.writerow(
                ["Cost / Bag of Concrete", f"GH\u20b5 {data['cost_per_bag']:,.2f}"]
            )
            writer.writerow([])

            # Material breakdown
            writer.writerow(["MATERIAL COST BREAKDOWN"])
            writer.writerow(
                [
                    "Material",
                    "Qty",
                    "Unit",
                    "Unit Price (GH\u20b5)",
                    "Total Cost (GH\u20b5)",
                ]
            )
            for row in data["material_breakdown"]:
                writer.writerow(
                    [
                        row["name"],
                        f"{row['qty']:,.2f}",
                        row["unit"],
                        f"{row['unit_price']:,.2f}",
                        f"{row['total']:,.2f}",
                    ]
                )
            writer.writerow([])

            # Project summary
            writer.writerow(["PROJECT SUMMARY"])
            for row in data["summary_rows"]:
                writer.writerow([row["label"], f"GH\u20b5 {row['amount']:,.2f}"])

            with open(path, "w", newline="") as f:
                f.write(output.getvalue())
            self.window().status_bar.showMessage(f"Exported to {path}", 5000)
