"""Material Quantification tab — element inputs + material bill dashboard.

Layout follows the same Stitch design system as ConcreteMixTab:
- Left panel: mix design inputs (editable), element definition, wastage
- Right panel: material bill summary cards, detailed breakdown table, export
- Real-time recalculation when inputs change (debounced via worker thread)

Data flow:
  ConcreteMixTab → MixDesignResult → MixDesignTransferData → this tab
  OR standalone: user enters mix parameters directly
  User edits overrides / adds elements → MaterialQuantifier → MaterialBill → display
"""

from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from material_quantify import StructuralElement
from material_quantify.models.bill import MaterialBill
from material_quantify.models.transfer_data import MixDesignTransferData
from app.widgets.info_button import InfoButton
from app.widgets.quant_result_panel import QuantResultPanel
from app.widgets.report_preview_dialog import ReportPreviewDialog
from app.workers.quantification_worker import QuantificationWorker


# Override fields: (attribute_name, display_label, default)
_OVERRIDE_FIELDS: list[tuple[str, str, float]] = [
    ("cement_kg_per_m3", "Cement (kg/m\u00b3)", 0.0),
    ("field_water_kg_per_m3", "Water - field (kg/m\u00b3)", 0.0),
    ("field_fine_aggregate_kg_per_m3", "Fine Agg - field (kg/m\u00b3)", 0.0),
    ("field_coarse_aggregate_kg_per_m3", "Coarse Agg - field (kg/m\u00b3)", 0.0),
    ("scm_kg_per_m3", "SCM (kg/m\u00b3)", 0.0),
    ("admixture_kg_per_m3", "Admixture (kg/m\u00b3)", 0.0),
]

# Element table columns
_ELEM_HEADERS = ["Type", "L (m)", "W (m)", "D (m)", "Qty", "Vol (m\u00b3)"]
_ELEMENT_TYPES = ["Footing", "Column", "Beam", "Slab", "Wall", "Custom"]


@dataclass
class ManualTransferData:
    """Lightweight transfer data created from manual user input."""

    code_used: str = "Manual"
    target_mean_strength_mpa: float = 25.0
    w_c_ratio: float = 0.5
    cement_kg_per_m3: float = 350.0
    water_kg_per_m3: float = 175.0
    field_water_kg_per_m3: float = 175.0
    fine_aggregate_kg_per_m3: float = 700.0
    field_fine_aggregate_kg_per_m3: float = 700.0
    coarse_aggregate_kg_per_m3: float = 1100.0
    field_coarse_aggregate_kg_per_m3: float = 1100.0
    scm_kg_per_m3: float = 0.0
    admixture_kg_per_m3: float = 0.0
    air_volume_percent: float = 1.0
    fine_aggregate_sg: float = 2.65
    coarse_aggregate_sg: float = 2.70
    cement_bag_weight_kg: float = 50.0
    coarse_agg_bulk_density_kg_m3: float = 1600.0


class MaterialQuantifyTab(QWidget):
    """Tab for material quantification from mix design results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._transfer_data: MixDesignTransferData | None = None
        self._last_bill: MaterialBill | None = None
        self.unit_prefs = None  # Set by MainWindow
        self._worker = QuantificationWorker(self)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)

        # Debounce timer — triggers recalculation 300ms after last input change
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run_quantification)

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
        self._result_panel = QuantResultPanel()
        self.quant_result_panel = self._result_panel  # Public alias for signal wiring
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
        self._result_panel.btn_report.clicked.connect(self._show_preview)

    def _build_form(self) -> None:
        # ── Status Banner ──
        self._status_banner = QLabel("Standalone mode — enter mix parameters manually.")
        self._status_banner.setObjectName("info-banner")
        self._status_banner.setWordWrap(True)
        self._status_banner.setStyleSheet(
            "background-color: #dbeafe; color: #1e40af; "
            "border: 1px solid #3b82f6; border-radius: 4px; "
            "padding: 10px 14px; font-weight: 600;"
        )
        self._form.addWidget(self._status_banner)

        # ── Quantification Mode ──
        grp_mode = self._group("Quantification Basis")
        mode_form = QFormLayout()
        mode_form.setSpacing(8)
        mode_form.setContentsMargins(12, 16, 12, 12)
        self.mode_combo = self._combo(
            [
                ("Total Concrete Volume", "volume"),
                ("Structural Element Dimensions", "elements"),
            ],
            default="volume",
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_form.addRow(
            self._label_with_info(
                "Mode",
                "Volume mode: enter total m\u00b3 directly. "
                "Element mode: define structural elements (beams, columns, etc.) and auto-calculate volume.",
            ),
            self.mode_combo,
        )
        grp_mode.setLayout(mode_form)
        self._form.addWidget(grp_mode)

        # ── Mix Design Parameters (editable) ──
        grp_data = self._group("Mix Design Parameters (per m\u00b3)")
        self._data_form = QFormLayout()
        self._data_form.setSpacing(6)
        self._data_form.setContentsMargins(12, 16, 12, 12)
        self._data_spins: dict[str, QDoubleSpinBox] = {}

        mix_fields = [
            (
                "cement",
                "Cement (kg/m\u00b3)",
                0.0,
                1000.0,
                350.0,
                1,
                "Mass of cement per m³.\n"
                "IS 10262 Table 5 / ACI 5.3:\n"
                "  Min for durability: 220–340 kg/m³ (by exposure)\n"
                "  Max: 450 kg/m³ (prevents cracking)\n"
                "  Typical: 300–400 kg/m³",
            ),
            (
                "water",
                "Water - design (kg/m\u00b3)",
                0.0,
                500.0,
                175.0,
                1,
                "Mixing water per m³ at SSD aggregate condition.\n"
                "IS 10262 Table 7 / ACI 5.3.3:\n"
                "  20mm agg, 50mm slump: 186 kg/m³\n"
                "  With superplasticizer: reduce by 20–30%\n"
                "  Design water = cement × w/c ratio",
            ),
            (
                "water_field",
                "Water - field (kg/m\u00b3)",
                0.0,
                500.0,
                175.0,
                1,
                "Actual water added on site.\n"
                "Field water = Design water − free water from aggregates\n"
                "  Free water = aggregate mass × (field moisture% − absorption%)\n"
                "Wet aggregates → less field water needed\n"
                "Dry aggregates → more field water needed",
            ),
            (
                "fa",
                "Fine Agg - SSD (kg/m\u00b3)",
                0.0,
                2000.0,
                700.0,
                1,
                "Sand mass per m³ at Saturated Surface Dry condition.\n"
                "SSD = pores saturated, surface dry.\n"
                "IS 10262 D-9 / ACI 5.3.6:\n"
                "  Mass = volume fraction × SG × 1000\n"
                "  Typical: 600–900 kg/m³",
            ),
            (
                "fa_field",
                "Fine Agg - field (kg/m\u00b3)",
                0.0,
                2000.0,
                700.0,
                1,
                "Sand mass in the field (actual batch weight).\n"
                "Field mass = SSD mass × (1 + free moisture%)\n"
                "  = SSD mass × (1 + field moisture% − absorption%)\n"
                "Adjust before batching to maintain correct w/c ratio.",
            ),
            (
                "ca",
                "Coarse Agg - SSD (kg/m\u00b3)",
                0.0,
                3000.0,
                1100.0,
                1,
                "Gravel/stone mass per m³ at SSD condition.\n"
                "IS 10262 Table 10 / ACI 5.3.6:\n"
                "  Volume fraction from Table 10 by FM and w/c\n"
                "  Mass = fraction × SG × 1000\n"
                "  Typical: 900–1200 kg/m³",
            ),
            (
                "ca_field",
                "Coarse Agg - field (kg/m\u00b3)",
                0.0,
                3000.0,
                1100.0,
                1,
                "Gravel mass in the field (actual batch weight).\n"
                "Same moisture correction as fine aggregate:\n"
                "  Field mass = SSD mass × (1 + free moisture%)\n"
                "Critical for maintaining correct w/c ratio on site.",
            ),
            (
                "scm",
                "SCM (kg/m\u00b3)",
                0.0,
                200.0,
                0.0,
                1,
                "Supplementary Cementitious Material per m³.\n"
                "IS 10262 D-7 / ACI 232:\n"
                "  Fly ash: 15–35% of cementitious material\n"
                "  GGBFS: 30–70%\n"
                "  Silica fume: 5–10%\n"
                "Total cementitious = cement + SCM",
            ),
            (
                "admixture",
                "Admixture (kg/m\u00b3)",
                0.0,
                50.0,
                0.0,
                3,
                "Chemical admixture dosage per m³.\n"
                "IS 10262 Annex G / ACI 212:\n"
                "  Superplasticizer: 2–8 kg/m³ (0.5–1.5% of cement)\n"
                "  Plasticizer: 1–3 kg/m³\n"
                "Check supplier data sheet for exact dosage range.",
            ),
        ]
        for key, label_text, lo, hi, default, decimals, info in mix_fields:
            spin = self._spin(default, lo, hi, 10.0, decimals)
            spin.valueChanged.connect(self._on_input_changed)
            self._data_spins[key] = spin
            self._data_form.addRow(self._label_with_info(label_text, info), spin)

        grp_data.setLayout(self._data_form)
        self._grp_data = grp_data
        self._form.addWidget(grp_data)

        # ── Mix Info ──
        grp_info = self._group("Mix Information")
        info_form = QFormLayout()
        info_form.setSpacing(6)
        info_form.setContentsMargins(12, 16, 12, 12)

        self._code_combo = self._combo(
            [("IS 10262", "is10262"), ("ACI 211.1", "aci211"), ("Manual", "manual")],
            default="manual",
        )
        self._code_combo.currentIndexChanged.connect(self._on_input_changed)
        info_form.addRow(
            self._label_with_info(
                "Code Standard",
                "Design code used for the original mix proportions.\n\n"
                "IS 10262: Indian standard, metric units (kg/m³)\n"
                "ACI 211.1: American standard, metric adaptation\n"
                "Manual: Values entered directly (no code-specific logic)\n\n"
                "This affects how material quantities are interpreted and validated.",
            ),
            self._code_combo,
        )

        self._strength_spin = self._spin(25.0, 10.0, 100.0, 5.0, 1, suffix=" MPa")
        self._strength_spin.valueChanged.connect(self._on_input_changed)
        info_form.addRow(
            self._label_with_info(
                "Target Strength",
                "Target average compressive strength at 28 days.\n\n"
                "IS 10262 Clause 7.1:\n"
                "  f'ck = max(fck + 1.65·S,  fck + X)\n"
                "  S = standard deviation (Table 2: 3.5–6.0 MPa)\n"
                "  X = grade factor (Table 1: 5.0–8.0 MPa)\n\n"
                "This is NOT the characteristic strength — it's higher to account for\n"
                "variability. E.g., M30 → f'ck = 38.25 MPa.",
            ),
            self._strength_spin,
        )

        self._wc_spin = self._spin(0.5, 0.3, 0.8, 0.01, 3)
        self._wc_spin.valueChanged.connect(self._on_input_changed)
        info_form.addRow(
            self._label_with_info(
                "W/C Ratio",
                "Water-to-cementitious material ratio by mass.\n\n"
                "IS 10262 Table 8 / ACI 5.3.4:\n"
                "  Lower w/c → higher strength & durability\n"
                "  Higher w/c → more workable but weaker\n\n"
                "Typical ranges:\n"
                "  0.30–0.40: High-strength (M50+)\n"
                "  0.40–0.50: Normal structures (M25–M40)\n"
                "  0.50–0.60: Non-structural (M15–M20)\n\n"
                "Max w/c for durability:\n"
                "  Severe exposure: 0.45 (IS 456 Table 5)\n"
                "  Moderate exposure: 0.55\n"
                "  Sulfate exposure: 0.40 (ACI 318 Table 19.3.2.1)",
            ),
            self._wc_spin,
        )

        self._bag_weight_spin = self._spin(50.0, 25.0, 100.0, 1.0, 0, suffix=" kg")
        self._bag_weight_spin.valueChanged.connect(self._on_input_changed)
        info_form.addRow(
            self._label_with_info(
                "Cement Bag Weight",
                "Weight of one bag of cement.\n\n"
                "Ghana / International: 50 kg (standard)\n"
                "Some regions: 42.5 kg or 94 lb (US)\n\n"
                "Used to convert total cement mass to number of bags:\n"
                "  Bags = total cement kg ÷ bag weight kg\n\n"
                "e.g., 1750 kg ÷ 50 kg = 35 bags",
            ),
            self._bag_weight_spin,
        )

        grp_info.setLayout(info_form)
        self._form.addWidget(grp_info)

        # ── Override Mix Values (for loaded data) ──
        grp_over = self._group("Override Mix Values (per m\u00b3)")
        over_form = QFormLayout()
        over_form.setSpacing(6)
        over_form.setContentsMargins(12, 16, 12, 12)
        self._override_spins: dict[str, QDoubleSpinBox] = {}
        _override_info = {
            "cement_kg_per_m3": "Override the cement content per m\u00b3 for this batch.",
            "field_water_kg_per_m3": "Override the field water content per m\u00b3.",
            "field_fine_aggregate_kg_per_m3": "Override the field fine aggregate content per m\u00b3.",
            "field_coarse_aggregate_kg_per_m3": "Override the field coarse aggregate content per m\u00b3.",
            "scm_kg_per_m3": "Override the SCM content per m\u00b3.",
            "admixture_kg_per_m3": "Override the admixture content per m\u00b3.",
        }
        for attr, label_text, default in _OVERRIDE_FIELDS:
            spin = self._spin(0.0, 0.0, 9999.0, 1.0, 1)
            spin.setReadOnly(True)
            spin.setStyleSheet("background-color: #f8fafc; color: #94a3b8;")
            spin.setToolTip("Enable by double-clicking, then edit the value")
            spin.setProperty("attr_name", attr)
            spin.installEventFilter(self)
            self._override_spins[attr] = spin
            info = _override_info.get(attr, "")
            over_form.addRow(self._label_with_info(label_text, info), spin)
        self._btn_reset_overrides = QPushButton("Reset All Overrides")
        self._btn_reset_overrides.setObjectName("secondary")
        self._btn_reset_overrides.clicked.connect(self._reset_overrides)
        over_form.addRow(self._btn_reset_overrides)
        grp_over.setLayout(over_form)
        self._grp_over = grp_over
        self._grp_over.setVisible(False)  # Hidden in standalone mode
        self._form.addWidget(grp_over)

        # ── Volume Mode ──
        self._grp_volume = self._group("Total Volume")
        vol_form = QFormLayout()
        vol_form.setSpacing(8)
        vol_form.setContentsMargins(12, 16, 12, 12)
        self.volume_spin = self._spin(10.0, 0.01, 100000.0, 1.0, 3)
        self.volume_spin.valueChanged.connect(self._on_input_changed)
        vol_form.addRow(
            self._label_with_info(
                "Concrete Volume (m\u00b3)",
                "Total net volume of concrete required for the project in cubic metres. "
                "Wastage will be added on top of this.",
            ),
            self.volume_spin,
        )
        self._grp_volume.setLayout(vol_form)
        self._form.addWidget(self._grp_volume)

        # ── Element Mode ──
        self._grp_elements = self._group("Structural Elements")
        elem_layout = QVBoxLayout()
        elem_layout.setSpacing(8)
        elem_layout.setContentsMargins(12, 16, 12, 12)

        self._elem_table = QTableWidget(0, len(_ELEM_HEADERS))
        self._elem_table.setHorizontalHeaderLabels(_ELEM_HEADERS)
        self._elem_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._elem_table.setMinimumHeight(160)
        self._elem_table.setMaximumHeight(260)
        self._elem_table.itemChanged.connect(self._on_element_changed)
        elem_layout.addWidget(self._elem_table)

        elem_btn_row = QHBoxLayout()
        elem_btn_row.setSpacing(8)
        self._btn_add_elem = QPushButton("Add Element")
        self._btn_add_elem.setObjectName("secondary")
        self._btn_add_elem.clicked.connect(self._add_element)
        self._btn_del_elem = QPushButton("Remove Selected")
        self._btn_del_elem.setObjectName("secondary")
        self._btn_del_elem.clicked.connect(self._remove_element)
        self._elem_total_label = QLabel("Total: 0.000 m\u00b3")
        self._elem_total_label.setStyleSheet(
            "font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        )
        elem_btn_row.addWidget(self._btn_add_elem)
        elem_btn_row.addWidget(self._btn_del_elem)
        elem_btn_row.addStretch()
        elem_btn_row.addWidget(self._elem_total_label)
        elem_layout.addLayout(elem_btn_row)

        self._grp_elements.setLayout(elem_layout)
        self._grp_elements.setVisible(False)
        self._form.addWidget(self._grp_elements)

        # ── Wastage ──
        grp_wastage = self._group("Wastage")
        wastage_form = QFormLayout()
        wastage_form.setSpacing(8)
        wastage_form.setContentsMargins(12, 16, 12, 12)
        self.wastage_spin = self._spin(5.0, 0.0, 30.0, 0.5, 1)
        self.wastage_spin.valueChanged.connect(self._on_input_changed)
        wastage_form.addRow(
            self._label_with_info(
                "Wastage Factor (%)",
                "Percentage of material added to cover wastage during transport, placing, and compaction. "
                "Typical: 3–5% for ready-mix, 5–10% for site-mixed concrete.",
            ),
            self.wastage_spin,
        )
        grp_wastage.setLayout(wastage_form)
        self._form.addWidget(grp_wastage)

        # ── Calculate Button ──
        self._form.addSpacing(8)
        self.calc_btn = QPushButton("  Calculate Material Quantities")
        self.calc_btn.setMinimumHeight(44)
        self.calc_btn.clicked.connect(self._run_quantification)
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

    def _combo(
        self, items: list[tuple[str, object]], default: object = None
    ) -> QComboBox:
        cb = QComboBox()
        cb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, data in items:
            cb.addItem(label, data)
        if default is not None:
            for i, (_, data) in enumerate(items):
                if data == default:
                    cb.setCurrentIndex(i)
                    break
        return cb

    def _spin(
        self,
        default: float,
        lo: float,
        hi: float,
        step: float,
        decimals: int = 2,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(default)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        if suffix:
            sb.setSuffix(suffix)
        sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return sb

    # ── Data Handoff (public API) ────────────────────────────────────

    def load_transfer_data(
        self,
        result_or_data: object,
        cement_bag_weight: float = 50.0,
        coarse_agg_bulk_density: float = 1600.0,
        fine_agg_sg: float = 2.65,
        coarse_agg_sg: float = 2.70,
    ) -> None:
        """Load mix design data into the quantification tab.

        Accepts either a MixDesignResult or a MixDesignTransferData.
        This is the primary API called by ConcreteMixTab for handoff.
        """
        from concrete_mix.models.mix_result import MixDesignResult

        if isinstance(result_or_data, MixDesignResult):
            td = MixDesignTransferData.from_mix_design_result(
                result_or_data,
                cement_bag_weight_kg=cement_bag_weight,
                coarse_agg_bulk_density_kg_m3=coarse_agg_bulk_density,
                fine_agg_sg=fine_agg_sg,
                coarse_agg_sg=coarse_agg_sg,
            )
        elif isinstance(result_or_data, MixDesignTransferData):
            td = result_or_data
        else:
            raise TypeError(
                f"Expected MixDesignResult or MixDesignTransferData, got {type(result_or_data)}"
            )

        self._transfer_data = td
        self._populate_data_from_transfer(td)
        self._status_banner.setText(
            f"Loaded: {td.code_used}  |  "
            f"f'cr={td.target_mean_strength_mpa:.1f} MPa  |  "
            f"W/C={td.w_c_ratio:.3f}  |  "
            f"Cement={td.cement_kg_per_m3:.1f} kg/m\u00b3"
        )
        self._status_banner.setStyleSheet(
            "background-color: #d1fae5; color: #065f46; "
            "border: 1px solid #10b981; border-radius: 4px; "
            "padding: 10px 14px; font-weight: 600;"
        )
        self._grp_over.setVisible(True)

        # Auto-run initial quantification
        self._run_quantification()

    def _populate_data_from_transfer(self, td: MixDesignTransferData) -> None:
        """Fill the editable spinboxes from transfer data."""
        m = self._data_spins
        m["cement"].setValue(td.cement_kg_per_m3)
        m["water"].setValue(td.water_kg_per_m3)
        m["water_field"].setValue(td.field_water_kg_per_m3)
        m["fa"].setValue(td.fine_aggregate_kg_per_m3)
        m["fa_field"].setValue(td.field_fine_aggregate_kg_per_m3)
        m["ca"].setValue(td.coarse_aggregate_kg_per_m3)
        m["ca_field"].setValue(td.field_coarse_aggregate_kg_per_m3)
        m["scm"].setValue(td.scm_kg_per_m3)
        m["admixture"].setValue(td.admixture_kg_per_m3)

        self._strength_spin.setValue(td.target_mean_strength_mpa)
        self._wc_spin.setValue(td.w_c_ratio)
        self._bag_weight_spin.setValue(td.cement_bag_weight_kg)

    def _build_transfer_data_from_inputs(self) -> MixDesignTransferData:
        """Create a MixDesignTransferData from current spinbox values."""
        m = self._data_spins
        return MixDesignTransferData(
            code_used=self._code_combo.currentData(),
            target_mean_strength_mpa=self._strength_spin.value(),
            w_c_ratio=self._wc_spin.value(),
            cement_kg_per_m3=m["cement"].value(),
            water_kg_per_m3=m["water"].value(),
            field_water_kg_per_m3=m["water_field"].value(),
            fine_aggregate_kg_per_m3=m["fa"].value(),
            field_fine_aggregate_kg_per_m3=m["fa_field"].value(),
            coarse_aggregate_kg_per_m3=m["ca"].value(),
            field_coarse_aggregate_kg_per_m3=m["ca_field"].value(),
            scm_kg_per_m3=m["scm"].value(),
            admixture_kg_per_m3=m["admixture"].value(),
            air_volume_percent=1.0,
            fine_agg_specific_gravity=2.65,
            coarse_agg_specific_gravity=2.70,
            cement_bag_weight_kg=self._bag_weight_spin.value(),
            coarse_agg_bulk_density_kg_m3=1600.0,
        )

    def _populate_override_defaults(self, td: MixDesignTransferData) -> None:
        """Set override spin boxes to current transfer data values."""
        import dataclasses

        td_dict = dataclasses.asdict(td)
        for attr, spin in self._override_spins.items():
            val = td_dict.get(attr, 0.0)
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

    # ── Override Handling ────────────────────────────────────────────

    def eventFilter(self, obj, event):
        """Double-click on override spin box to enable editing."""
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.MouseButtonDblClick and obj.property(
            "attr_name"
        ):
            spin = obj
            if spin.isReadOnly():
                spin.setReadOnly(False)
                spin.setStyleSheet("")  # clear grey style
            return False
        return super().eventFilter(obj, event)

    def _get_overrides(self) -> dict[str, float]:
        """Collect enabled (non-read-only) override values."""
        overrides: dict[str, float] = {}
        if self._transfer_data is None:
            return overrides
        import dataclasses

        td_dict = dataclasses.asdict(self._transfer_data)
        for attr, spin in self._override_spins.items():
            if not spin.isReadOnly():
                original = td_dict.get(attr, 0.0)
                if abs(spin.value() - original) > 0.01:
                    overrides[attr] = spin.value()
        return overrides

    def _reset_overrides(self) -> None:
        """Reset all overrides to original values."""
        if self._transfer_data is None:
            return
        self._populate_override_defaults(self._transfer_data)
        for spin in self._override_spins.values():
            spin.setReadOnly(True)
            spin.setStyleSheet("background-color: #f8fafc; color: #94a3b8;")
        self._on_input_changed()

    # ── Mode Switching ───────────────────────────────────────────────

    def _on_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        is_vol = mode == "volume"
        self._grp_volume.setVisible(is_vol)
        self._grp_elements.setVisible(not is_vol)
        self._on_input_changed()

    def on_unit_changed(self) -> None:
        """Update spinbox suffixes and labels when unit preferences change."""
        if self.unit_prefs is None:
            return
        up = self.unit_prefs

        # Block signals to prevent cascading recalculations
        spinboxes = [
            self._strength_spin, self.volume_spin, self._bag_weight_spin,
        ]
        for sb in spinboxes:
            sb.blockSignals(True)

        # Snapshot metric values before first conversion
        if not hasattr(self, '_metric_snapshot'):
            self._metric_snapshot = {
                'strength': self._strength_spin.value(),
                'volume': self.volume_spin.value(),
                'bag_weight': self._bag_weight_spin.value(),
            }

        ms = self._metric_snapshot

        # Apply conversions from metric snapshot
        self._strength_spin.setValue(up.convert_strength_mpa(ms['strength']))
        self.volume_spin.setValue(up.convert_volume_m3(ms['volume']))
        self._bag_weight_spin.setValue(up.convert_mass_kg(ms['bag_weight']))

        # Update suffixes
        self._strength_spin.setSuffix(f" {up.strength_unit()}")
        self.volume_spin.setSuffix(f" {up.volume_unit()}")
        self._bag_weight_spin.setSuffix(f" {up.mass_unit()}")

        # Update element table headers
        lu = up.length_unit()
        vu = up.volume_unit()
        self._elem_table.setHorizontalHeaderLabels(
            ["Type", f"L ({lu})", f"W ({lu})", f"D ({lu})", "Qty", f"Vol ({vu})"]
        )

        # Unblock signals
        for sb in spinboxes:
            sb.blockSignals(False)

    # ── Element Table ────────────────────────────────────────────────

    def _add_element(self) -> None:
        """Add a new element row to the table."""
        self._elem_table.blockSignals(True)
        row = self._elem_table.rowCount()
        self._elem_table.insertRow(row)

        # Type combo
        type_combo = QComboBox()
        for t in _ELEMENT_TYPES:
            type_combo.addItem(t)
        self._elem_table.setCellWidget(row, 0, type_combo)
        type_combo.currentIndexChanged.connect(lambda: self._on_input_changed())

        # Dimension spin boxes
        for col in range(1, 5):
            spin = QDoubleSpinBox()
            spin.setRange(0.01, 1000.0)
            spin.setDecimals(3)
            if col < 4:
                spin.setValue(1.0)
                spin.setSingleStep(0.1)
            else:
                spin = QDoubleSpinBox()  # type: ignore[assignment]
                spin.setRange(1, 10000)
                spin.setDecimals(0)
                spin.setValue(1)
                spin.setSingleStep(1)
            spin.valueChanged.connect(self._on_input_changed)
            self._elem_table.setCellWidget(row, col, spin)

        # Volume display (read-only)
        vol_item = QTableWidgetItem("1.000")
        vol_item.setFlags(vol_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._elem_table.setItem(row, 5, vol_item)

        self._elem_table.blockSignals(False)
        self._update_element_volumes()
        self._on_input_changed()

    def _remove_element(self) -> None:
        """Remove the selected element row."""
        row = self._elem_table.currentRow()
        if row >= 0:
            self._elem_table.removeRow(row)
            self._update_element_volumes()
            self._on_input_changed()

    def _on_element_changed(self, item: QTableWidgetItem) -> None:
        """Handle cell edits in element table."""
        self._update_element_volumes()

    def _update_element_volumes(self) -> None:
        """Recalculate and display per-element and total volumes."""
        total = 0.0
        for row in range(self._elem_table.rowCount()):
            l_spin = self._elem_table.cellWidget(row, 1)
            w_spin = self._elem_table.cellWidget(row, 2)
            d_spin = self._elem_table.cellWidget(row, 3)
            q_spin = self._elem_table.cellWidget(row, 4)
            if all(w is not None for w in [l_spin, w_spin, d_spin, q_spin]):
                vol = l_spin.value() * w_spin.value() * d_spin.value() * q_spin.value()
                total += vol
                vol_item = self._elem_table.item(row, 5)
                if vol_item:
                    vol_item.setText(f"{vol:.3f}")
        self._elem_total_label.setText(f"Total: {total:.3f} m\u00b3")

    def _get_elements(self) -> list[StructuralElement]:
        """Parse element table into StructuralElement list."""
        elements: list[StructuralElement] = []
        for row in range(self._elem_table.rowCount()):
            type_combo: QComboBox = self._elem_table.cellWidget(row, 0)  # type: ignore[assignment]
            l_spin: QDoubleSpinBox = self._elem_table.cellWidget(row, 1)  # type: ignore[assignment]
            w_spin: QDoubleSpinBox = self._elem_table.cellWidget(row, 2)  # type: ignore[assignment]
            d_spin: QDoubleSpinBox = self._elem_table.cellWidget(row, 3)  # type: ignore[assignment]
            q_spin: QDoubleSpinBox = self._elem_table.cellWidget(row, 4)  # type: ignore[assignment]

            if all(w is not None for w in [type_combo, l_spin, w_spin, d_spin, q_spin]):
                elements.append(
                    StructuralElement(
                        element_type=type_combo.currentText().lower(),
                        length_m=l_spin.value(),
                        width_m=w_spin.value(),
                        depth_m=d_spin.value(),
                        quantity=int(q_spin.value()),
                    )
                )
        return elements

    # ── Input Change → Debounced Recalculation ───────────────────────

    def _on_input_changed(self, *_args) -> None:
        """Debounce: restart 300ms timer on any input change."""
        self._debounce.start()

    # ── Quantification ───────────────────────────────────────────────

    def _run_quantification(self) -> None:
        """Trigger async quantification via worker thread."""
        # Build transfer data from current inputs
        td = self._build_transfer_data_from_inputs()
        self._transfer_data = td

        if self._worker.isRunning():
            return

        self._debounce.stop()
        self.calc_btn.setEnabled(False)
        self.calc_btn.setText("  Calculating...")

        self._worker.set_transfer_data(td)

        overrides = self._get_overrides()
        self._worker.set_overrides(overrides)

        mode = self.mode_combo.currentData()
        wastage = self.wastage_spin.value()

        try:
            if mode == "volume":
                vol = self.volume_spin.value()
                if vol <= 0:
                    raise ValueError("Volume must be positive")
                self._worker.set_volume_mode(vol, wastage)
            else:
                elements = self._get_elements()
                if not elements:
                    raise ValueError("Add at least one structural element")
                self._worker.set_elements_mode(elements, wastage)
        except Exception as e:
            self._on_error(str(e))
            return

        self._worker.start()

    def _on_result(self, bill: MaterialBill) -> None:
        """Handle quantification result."""
        self._last_bill = bill
        self._result_panel.display_bill(bill)
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("  Calculate Material Quantities")

        if hasattr(self.window(), "status_bar"):
            self.window().status_bar.showMessage(
                f"Quantified \u2014 Gross: {bill.gross_concrete_volume_m3:.3f} m\u00b3  |  "
                f"Cement: {bill.total_cement_kg:,.1f} kg ({bill.total_cement_bags:.0f} bags)  |  "
                f"Water: {bill.total_water_kg:,.1f} kg",
                8000,
            )
        # Auto-save to history
        self._auto_save_history(bill)

    def _on_error(self, msg: str) -> None:
        """Handle quantification error."""
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("  Calculate Material Quantities")
        QMessageBox.warning(self, "Quantification Error", msg)

    # ── History ──────────────────────────────────────────────────────

    _history_db = None  # Set by MainWindow

    def _auto_save_history(self, bill: MaterialBill) -> None:
        """Auto-save quantification result to history DB."""
        if self._history_db is None:
            return
        try:
            inp = self._build_transfer_data_from_inputs()
            name = f"Quantification - {bill.net_concrete_volume_m3:.2f} m\u00b3"
            self._history_db.save_quantification(inp, bill, name=name)
        except Exception:
            pass

    def load_from_history(self, calc_id: int) -> None:
        """Load a quantification record from history into this tab."""
        if self._history_db is None:
            return
        from history.serializers import deserialize_bill
        import json
        rec = self._history_db.get_calculation(calc_id)
        if rec is None:
            return
        bill = deserialize_bill(json.loads(rec["result_json"]))
        self._last_bill = bill
        self._result_panel.display_bill(bill)

        # Restore inputs to UI if transfer_data is available
        if bill.transfer_data:
            self._transfer_data = bill.transfer_data
            self._populate_data_from_transfer(bill.transfer_data)

            # Select "volume" mode and populate inputs
            idx = self.mode_combo.findData("volume")
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            self.volume_spin.setValue(bill.net_concrete_volume_m3)
            self.wastage_spin.setValue(bill.wastage_percent)

            # Show group override and populate override values
            self._grp_over.setVisible(True)
            self._populate_override_defaults(bill.transfer_data)

            self._status_banner.setText(
                f"Loaded from history: {bill.transfer_data.code_used}  |  "
                f"f'cr={bill.transfer_data.target_mean_strength_mpa:.1f} MPa  |  "
                f"W/C={bill.transfer_data.w_c_ratio:.3f}  |  "
                f"Cement={bill.transfer_data.cement_kg_per_m3:.1f} kg/m\u00b3"
            )
            self._status_banner.setStyleSheet(
                "background-color: #d1fae5; color: #065f46; "
                "border: 1px solid #10b981; border-radius: 4px; "
                "padding: 10px 14px; font-weight: 600;"
            )

    # ── Export ────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._last_bill:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Material Bill CSV", "material_bill.csv", "CSV (*.csv)"
        )
        if path:
            import csv
            import io

            bill = self._last_bill
            td = bill.transfer_data
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Material", "Per m\u00b3", "Total", "Unit"])
            writer.writerow(
                [
                    "Cement",
                    f"{td.cement_kg_per_m3:.1f}",
                    f"{bill.total_cement_kg:.1f}",
                    "kg",
                ]
            )
            writer.writerow(
                [
                    "Water (field)",
                    f"{td.field_water_kg_per_m3:.1f}",
                    f"{bill.total_water_kg:.1f}",
                    "kg",
                ]
            )
            writer.writerow(
                [
                    "Fine Aggregate (field)",
                    f"{td.field_fine_aggregate_kg_per_m3:.1f}",
                    f"{bill.total_fine_aggregate_kg:.1f}",
                    "kg",
                ]
            )
            writer.writerow(
                [
                    "Coarse Aggregate (field)",
                    f"{td.field_coarse_aggregate_kg_per_m3:.1f}",
                    f"{bill.total_coarse_aggregate_kg:.1f}",
                    "kg",
                ]
            )
            if bill.total_scm_kg > 0:
                writer.writerow(
                    ["SCM", f"{td.scm_kg_per_m3:.1f}", f"{bill.total_scm_kg:.1f}", "kg"]
                )
            writer.writerow(
                [
                    "Cement Bags",
                    "",
                    f"{bill.total_cement_bags:.0f}",
                    f"bags ({bill.cement_bag_weight_kg:.0f} kg)",
                ]
            )
            writer.writerow([])
            writer.writerow(
                ["Net Volume (m\u00b3)", f"{bill.net_concrete_volume_m3:.3f}"]
            )
            writer.writerow(["Wastage (%)", f"{bill.wastage_percent:.1f}"])
            writer.writerow(
                ["Gross Volume (m\u00b3)", f"{bill.gross_concrete_volume_m3:.3f}"]
            )

            with open(path, "w", newline="") as f:
                f.write(output.getvalue())
            self.window().status_bar.showMessage(f"Exported to {path}", 5000)

    def _generate_quant_report_html(self) -> str:
        """Generate HTML report for material quantification preview."""
        bill = self._last_bill
        if not bill:
            return ""

        td = bill.transfer_data

        html = f"""<!DOCTYPE html>
<html class="light" lang="en">
<head>
    <meta charset="utf-8"/>
    <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
    <title>Material Quantification Bill - CivilQntify</title>
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
            .print-container {{ border: none; box-shadow: none; width: 100%; max-width: 100%; margin: 0; }}
        }}
        .zebra-row:nth-child(even) {{ background-color: #f1f5f9; }}
        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
    </style>
</head>
<body class="bg-surface-dim font-body-md text-on-surface">
    <!-- Main Content Area -->
    <main class="print-container bg-white w-full max-w-[850px] min-h-[1100px] mx-auto my-8 p-[40px] shadow-2xl border border-outline-variant flex flex-col">
        <!-- Document Header -->
        <header class="flex justify-between items-start border-b-2 border-primary pb-4 mb-8">
            <div class="flex flex-col gap-1">
                <div class="flex items-center gap-2">
                    <h1 class="text-[30px] leading-[36px] text-primary tracking-tight font-bold">CivilQntify</h1>
                </div>
                <h2 class="text-[12px] leading-[16px] tracking-[0.1em] text-on-surface-variant uppercase font-bold mt-2">MATERIAL QUANTIFICATION BILL</h2>
            </div>
            <div class="text-right flex flex-col gap-1">
                <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-primary uppercase">Mix Design Reference</div>
                <div class="text-[24px] leading-[32px] font-semibold text-on-surface">{td.code_used}</div>
                <div class="text-on-surface-variant font-body-md mt-2">Target: {td.target_mean_strength_mpa:.1f} MPa</div>
                <div class="text-on-surface-variant font-body-md">W/C Ratio: {td.w_c_ratio:.3f}</div>
            </div>
        </header>

        <!-- Section 1: Volume Summary -->
        <section class="mb-8">
            <div class="text-[12px] leading-[16px] tracking-[0.1em] text-primary mb-4 uppercase border-l-4 border-primary pl-2 font-bold">Section 1: Volume Summary</div>
            <div class="grid grid-cols-3 gap-5">
                <div class="border border-outline-variant p-4 flex flex-col gap-2">
                    <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant uppercase">Net Volume</div>
                    <div class="flex justify-between items-end">
                        <span class="text-[24px] font-bold">{bill.net_concrete_volume_m3:,.3f}</span>
                        <span class="text-[11px] pb-1">m³</span>
                    </div>
                </div>
                <div class="border border-outline-variant p-4 flex flex-col gap-2 bg-surface-container-low">
                    <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant uppercase">Wastage ({bill.wastage_percent:.1f}%)</div>
                    <div class="flex justify-between items-end">
                        <span class="text-[24px] font-bold">{bill.gross_concrete_volume_m3 - bill.net_concrete_volume_m3:,.3f}</span>
                        <span class="text-[11px] pb-1">m³</span>
                    </div>
                </div>
                <div class="border-2 border-primary p-4 flex flex-col gap-2">
                    <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-primary uppercase">Gross Volume</div>
                    <div class="flex justify-between items-end text-primary">
                        <span class="text-[24px] font-bold">{bill.gross_concrete_volume_m3:,.3f}</span>
                        <span class="text-[11px] pb-1 font-bold">m³</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Section 2: Material Totals -->
        <section class="mb-8">
            <div class="text-[12px] leading-[16px] tracking-[0.1em] text-primary mb-4 uppercase border-l-4 border-primary pl-2 font-bold">Section 2: Material Totals</div>
            <div class="grid grid-cols-2 gap-5">
                <div class="border border-outline-variant">
                    <div class="bg-surface-container-high px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold border-b border-outline-variant">Cementitious Materials</div>
                    <div class="p-4 space-y-4">
                        <div class="flex justify-between items-center">
                            <span class="font-body-md text-on-surface">Portland Cement</span>
                            <span class="text-[16px] leading-[24px] font-medium font-bold">{bill.total_cement_bags:,.0f} Bags</span>
                        </div>
                        <div class="flex justify-between items-center text-on-surface-variant">
                            <span class="font-body-md">Total Cement Weight</span>
                            <span class="text-[16px] leading-[24px] font-medium">{bill.total_cement_kg:,.1f} kg</span>
                        </div>
                        {f'<div class="flex justify-between items-center"><span class="font-body-md text-on-surface">SCM</span><span class="text-[16px] leading-[24px] font-medium font-bold">{bill.total_scm_kg:,.1f} kg</span></div>' if bill.total_scm_kg > 0 else ""}
                    </div>
                </div>
                <div class="border border-outline-variant">
                    <div class="bg-surface-container-high px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold border-b border-outline-variant">Aggregates & Water</div>
                    <div class="p-4 space-y-4">
                        <div class="flex justify-between items-center">
                            <span class="font-body-md text-on-surface">Fine Aggregate (Sand)</span>
                            <span class="text-[16px] leading-[24px] font-medium font-bold">{bill.total_fine_aggregate_bulk_m3:,.3f} m³</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="font-body-md text-on-surface">Coarse Aggregate (20mm)</span>
                            <span class="text-[16px] leading-[24px] font-medium font-bold">{bill.total_coarse_aggregate_bulk_m3:,.3f} m³</span>
                        </div>
                        <div class="flex justify-between items-center text-on-surface-variant">
                            <span class="font-body-md">Water (Field)</span>
                            <span class="text-[16px] leading-[24px] font-medium">{bill.total_water_liters:,.1f} L</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Section 3: Detailed Breakdown Table -->
        <section class="mb-8 flex-grow">
            <div class="text-[12px] leading-[16px] tracking-[0.1em] text-primary mb-4 uppercase border-l-4 border-primary pl-2 font-bold">Section 3: Detailed Breakdown</div>
            <table class="w-full border-collapse">
                <thead>
                    <tr class="border-y border-outline text-left bg-surface-container-lowest">
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant">Material</th>
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Per m³</th>
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Total (kg)</th>
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Volume/Bags</th>
                    </tr>
                </thead>
                <tbody class="text-[13px] leading-[18px]">
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Portland Cement</td>
                        <td class="px-4 py-2 text-right">{td.cement_kg_per_m3:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_cement_kg:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_cement_bags:,.0f} bags</td>
                    </tr>
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Fine Aggregate</td>
                        <td class="px-4 py-2 text-right">{td.field_fine_aggregate_kg_per_m3:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_fine_aggregate_kg:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_fine_aggregate_bulk_m3:,.3f} m³</td>
                    </tr>
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Coarse Aggregate</td>
                        <td class="px-4 py-2 text-right">{td.field_coarse_aggregate_kg_per_m3:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_coarse_aggregate_kg:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_coarse_aggregate_bulk_m3:,.3f} m³</td>
                    </tr>
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Water</td>
                        <td class="px-4 py-2 text-right">{td.field_water_kg_per_m3:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_water_kg:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_water_liters:,.1f} L</td>
                    </tr>
                    {f'<tr class="zebra-row border-b border-outline-variant"><td class="px-4 py-2 text-on-surface font-semibold">SCM</td><td class="px-4 py-2 text-right">{td.scm_kg_per_m3:,.1f}</td><td class="px-4 py-2 text-right">{bill.total_scm_kg:,.1f}</td><td class="px-4 py-2 text-right">-</td></tr>' if bill.total_scm_kg > 0 else ""}
                    {f'<tr class="zebra-row border-b border-outline-variant"><td class="px-4 py-2 text-on-surface font-semibold">Admixture</td><td class="px-4 py-2 text-right">{td.admixture_kg_per_m3:,.3f}</td><td class="px-4 py-2 text-right">{bill.total_admixture_kg:,.3f}</td><td class="px-4 py-2 text-right">-</td></tr>' if bill.total_admixture_kg > 0 else ""}
                </tbody>
            </table>
        </section>

        <!-- Document Footer -->
        <footer class="mt-auto pt-8 border-t border-outline-variant flex justify-between items-end">
            <div class="flex flex-col gap-1">
                <div class="text-on-surface-variant text-[10px] uppercase font-bold tracking-tighter">Authorized Signature</div>
                <div class="h-12 w-48 border-b border-dotted border-outline mb-1"></div>
                <div class="text-on-surface-variant font-body-md">Chief Site Engineer</div>
            </div>
            <div class="text-right">
                <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-primary">Generated by CivilQntify Technical Systems</div>
                <div class="text-on-surface-variant font-body-md">Page 1 of 1</div>
            </div>
        </footer>
    </main>
</body>
</html>"""
        return html

    def _show_preview(self) -> None:
        """Show the report preview dialog."""
        if not self._last_bill:
            QMessageBox.warning(
                self,
                "No Data",
                "No material bill to preview. Please calculate material quantities first.",
            )
            return

        html = self._generate_quant_report_html()
        dialog = ReportPreviewDialog(
            self, title="Material Quantification Report Preview"
        )
        dialog.set_html(html)
        dialog.set_export_callback(self._do_export_report)
        dialog.exec()

    def _do_export_report(self) -> None:
        """Actually export the report after preview."""
        if not self._last_bill:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Material Bill Report",
            "material_bill_report.txt",
            "Text (*.txt)",
        )
        if path:
            with open(path, "w") as f:
                f.write(self._last_bill.format_report())
            self.window().status_bar.showMessage(f"Report saved to {path}", 5000)
