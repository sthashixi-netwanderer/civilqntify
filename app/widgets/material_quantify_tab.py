"""Material Quantification tab — element inputs + material bill dashboard.

Provides two quantification workflows via subtabs:
1. Design Mix Proportions: Per-m³ batch inputs / automated transfer from Mix Design tab
2. Mix Ratios & Volume: Volumetric nominal mix ratios (e.g. 1:2:4, 1:1.5:3, 1:1:2, mortars)
   with dry volume shrinkage factor (1.54 / 1.33) and cement bag volume (1 bag = 0.035 m³).

Layout follows the Stitch design system:
- Left panel: subtabbed input forms (Design Mix Proportions / Mix Ratios & Volume)
- Right panel: material bill summary cards, detailed breakdown table, export
- Real-time recalculation when inputs change (debounced via worker thread)
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from material_quantify import (
    MIX_RATIO_PRESETS,
    MaterialQuantifier,
    MixRatioPreset,
    MixRatioQuantifier,
    StructuralElement,
)
from material_quantify.models.bill import MaterialBill
from material_quantify.models.transfer_data import MixDesignTransferData
from app.unit_preferences import get_unit_prefs
from app.widgets.info_button import InfoButton, set_label_with_info_text
from app.widgets.quant_result_panel import QuantResultPanel
from app.widgets.report_preview_dialog import ReportPreviewDialog
from app.widgets.unit_spin import UnitSpinBox
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
    """Tab for material quantification from mix designs or mix ratios."""

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

        # Left: tabbed input panel — responsive: min 360, stretchable via splitter
        self._left_tabs = QTabWidget()
        self._left_tabs.setMinimumWidth(360)
        self._left_tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._left_tabs.currentChanged.connect(self._on_subtab_changed)

        # Subtab 1: Design Mix Proportions
        design_scroll = QScrollArea()
        design_scroll.setWidgetResizable(True)
        design_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        design_widget = QWidget()
        self._form = QVBoxLayout(design_widget)
        self._form.setContentsMargins(16, 16, 12, 16)
        self._form.setSpacing(8)
        self._build_form()
        design_scroll.setWidget(design_widget)

        design_page = QWidget()
        design_layout = QVBoxLayout(design_page)
        design_layout.setContentsMargins(0, 0, 0, 0)
        design_layout.setSpacing(0)
        design_layout.addWidget(design_scroll, 1)
        design_layout.addLayout(self._action_bar)
        self._left_tabs.addTab(design_page, "Design Mix Proportions")

        # Subtab 2: Mix Ratios & Volume
        ratio_scroll = QScrollArea()
        ratio_scroll.setWidgetResizable(True)
        ratio_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        ratio_widget = QWidget()
        self._ratio_form = QVBoxLayout(ratio_widget)
        self._ratio_form.setContentsMargins(16, 16, 12, 16)
        self._ratio_form.setSpacing(8)
        self._build_ratio_form()
        ratio_scroll.setWidget(ratio_widget)

        ratio_page = QWidget()
        ratio_layout = QVBoxLayout(ratio_page)
        ratio_layout.setContentsMargins(0, 0, 0, 0)
        ratio_layout.setSpacing(0)
        ratio_layout.addWidget(ratio_scroll, 1)
        ratio_layout.addLayout(self._ratio_action_bar)
        self._left_tabs.addTab(ratio_page, "Mix Ratios & Volume")

        splitter.addWidget(self._left_tabs)

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
        """Build Subtab 1: Design Mix Proportions form."""
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

        # ── Total Volume ── (moved to top so user sees the calculation volume immediately)
        self._grp_volume = self._group("Total Volume")
        vol_form = QFormLayout()
        vol_form.setSpacing(8)
        vol_form.setContentsMargins(12, 16, 12, 12)
        self.volume_spin = UnitSpinBox("volume", 10.0, 0.01, 100000.0, 1.0, 3)
        self.volume_spin.valueChanged.connect(self._on_input_changed)
        self._volume_label = self._label_with_info(
            "Concrete Volume (m\u00b3)",
            "Total net volume of concrete required for the project in cubic metres. "
            "Wastage will be added on top of this.",
        )
        vol_form.addRow(
            self._volume_label,
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
        self._elem_table.setHorizontalHeaderLabels(self._element_headers())
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

        self._strength_spin = UnitSpinBox("strength", 25.0, 10.0, 100.0, 5.0, 1)
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

        self._bag_weight_spin = UnitSpinBox("mass", 50.0, 25.0, 100.0, 1.0, 0)
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

        # ── Calculate Button ──
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(16, 6, 12, 14)
        self.calc_btn = QPushButton("  Calculate Material Quantities")
        self.calc_btn.setMinimumHeight(44)
        self.calc_btn.clicked.connect(self._run_quantification)
        action_bar.addWidget(self.calc_btn)
        self._action_bar = action_bar

        self._form.addStretch()

    # ── Subtab 2: Mix Ratios & Volume ─────────────────────────────────

    def _build_ratio_form(self) -> None:
        """Build Subtab 2: Mix Ratios & Volume form."""
        # ── Status / Info Banner ──
        self._ratio_status_banner = QLabel(
            "Mix Ratio Mode \u2014 enter mix proportions (Cement : Sand : Coarse Agg) and work volume. "
            "Note: 1 bag of cement = 0.035 m\u00b3."
        )
        self._ratio_status_banner.setObjectName("info-banner")
        self._ratio_status_banner.setWordWrap(True)
        self._ratio_status_banner.setStyleSheet(
            "background-color: #dbeafe; color: #1e40af; "
            "border: 1px solid #3b82f6; border-radius: 4px; "
            "padding: 10px 14px; font-weight: 600;"
        )
        self._ratio_form.addWidget(self._ratio_status_banner)

        # ── Volume Scope — moved to top so user sees the calculation volume immediately ──
        grp_ratio_mode = self._group("Volume of Work Basis")
        ratio_mode_form = QFormLayout()
        ratio_mode_form.setSpacing(8)
        ratio_mode_form.setContentsMargins(12, 16, 12, 12)
        self.ratio_mode_combo = self._combo(
            [
                ("Total Work Volume", "volume"),
                ("Structural Element Dimensions", "elements"),
            ],
            default="volume",
        )
        self.ratio_mode_combo.currentIndexChanged.connect(self._on_ratio_mode_changed)
        ratio_mode_form.addRow(
            self._label_with_info(
                "Mode",
                "Volume mode: enter total volume of concrete/mortar directly.\n"
                "Element mode: define structural elements (slabs, beams, columns, etc.) and auto-calculate volume.",
            ),
            self.ratio_mode_combo,
        )
        grp_ratio_mode.setLayout(ratio_mode_form)
        self._ratio_form.addWidget(grp_ratio_mode)

        # ── Volume Mode Group ──
        self._grp_ratio_volume = self._group("Total Volume of Work")
        vol_form = QFormLayout()
        vol_form.setSpacing(8)
        vol_form.setContentsMargins(12, 16, 12, 12)
        self.ratio_volume_spin = UnitSpinBox("volume", 10.0, 0.01, 100000.0, 1.0, 3)
        self.ratio_volume_spin.valueChanged.connect(self._on_input_changed)
        self._ratio_volume_label = self._label_with_info(
            "Work Volume (m\u00b3)",
            "Total net volume of concrete or mortar work in cubic metres.\n"
            "Wastage and dry-volume void factors will be applied during estimation.",
        )
        vol_form.addRow(self._ratio_volume_label, self.ratio_volume_spin)
        self._grp_ratio_volume.setLayout(vol_form)
        self._ratio_form.addWidget(self._grp_ratio_volume)

        # ── Element Mode Group ──
        self._grp_ratio_elements = self._group("Structural Elements")
        elem_layout = QVBoxLayout()
        elem_layout.setSpacing(8)
        elem_layout.setContentsMargins(12, 16, 12, 12)

        self._ratio_elem_table = QTableWidget(0, len(_ELEM_HEADERS))
        self._ratio_elem_table.setHorizontalHeaderLabels(self._element_headers())
        self._ratio_elem_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._ratio_elem_table.setMinimumHeight(160)
        self._ratio_elem_table.setMaximumHeight(260)
        self._ratio_elem_table.itemChanged.connect(self._on_ratio_element_changed)
        elem_layout.addWidget(self._ratio_elem_table)

        elem_btn_row = QHBoxLayout()
        elem_btn_row.setSpacing(8)
        self._btn_add_ratio_elem = QPushButton("Add Element")
        self._btn_add_ratio_elem.setObjectName("secondary")
        self._btn_add_ratio_elem.clicked.connect(self._add_ratio_element)
        self._btn_del_ratio_elem = QPushButton("Remove Selected")
        self._btn_del_ratio_elem.setObjectName("secondary")
        self._btn_del_ratio_elem.clicked.connect(self._remove_ratio_element)
        self._ratio_elem_total_label = QLabel("Total: 0.000 m\u00b3")
        self._ratio_elem_total_label.setStyleSheet(
            "font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        )
        elem_btn_row.addWidget(self._btn_add_ratio_elem)
        elem_btn_row.addWidget(self._btn_del_ratio_elem)
        elem_btn_row.addStretch()
        elem_btn_row.addWidget(self._ratio_elem_total_label)
        elem_layout.addLayout(elem_btn_row)

        self._grp_ratio_elements.setLayout(elem_layout)
        self._grp_ratio_elements.setVisible(False)
        self._ratio_form.addWidget(self._grp_ratio_elements)

        # ── Mix Preset & Proportions ──
        grp_ratio = self._group("Mix Proportions (Cement : Sand : Coarse Agg)")
        ratio_form = QFormLayout()
        ratio_form.setSpacing(6)
        ratio_form.setContentsMargins(12, 16, 12, 12)

        # Presets dropdown
        preset_items = [(name, name) for name in MIX_RATIO_PRESETS.keys()]
        preset_items.append(("Custom Ratio", "Custom"))
        self.ratio_preset_combo = self._combo(preset_items, default="M20 (1:1.5:3)")
        self.ratio_preset_combo.currentIndexChanged.connect(self._on_ratio_preset_changed)
        ratio_form.addRow(
            self._label_with_info(
                "Standard Preset",
                "Select a standard nominal concrete or mortar mix preset,\n"
                "or choose 'Custom Ratio' to specify any arbitrary proportion.\n\n"
                "Standard Nominal Mixes:\n"
                "  M25 (1:1:2): Heavy RCC, columns, water tanks\n"
                "  M20 (1:1.5:3): Standard RCC slabs, beams, columns\n"
                "  M15 (1:2:4): General RCC, small slabs, mass work\n"
                "  M10 (1:3:6): Plain cement concrete (PCC), bedding\n"
                "  M7.5 (1:4:8): Foundation leveling bed\n"
                "  M5 (1:5:10): Lean concrete base\n\n"
                "Mortar Mixes (Sand only, Coarse Agg = 0):\n"
                "  1:3: Pointing, repairs, waterproof plaster\n"
                "  1:4: External plastering, loadbearing masonry\n"
                "  1:5: General brick/block masonry\n"
                "  1:6: Internal plastering, partition walls",
            ),
            self.ratio_preset_combo,
        )

        # Cement parts
        self.ratio_cement_spin = self._spin(1.0, 0.1, 100.0, 0.1, 2)
        self.ratio_cement_spin.valueChanged.connect(self._on_ratio_spin_changed)
        ratio_form.addRow(
            self._label_with_info(
                "Cement Ratio (Parts)",
                "Volumetric proportion of cement (normally 1.0 part).\n"
                "1 bag of cement occupies 0.035 m³.",
            ),
            self.ratio_cement_spin,
        )

        # Fine Aggregate (Sand) parts
        self.ratio_sand_spin = self._spin(1.5, 0.0, 100.0, 0.1, 2)
        self.ratio_sand_spin.valueChanged.connect(self._on_ratio_spin_changed)
        ratio_form.addRow(
            self._label_with_info(
                "Fine Agg / Sand (Parts)",
                "Volumetric proportion of fine aggregate (sand).\n"
                "e.g., 1.5 in a 1:1.5:3 mix.",
            ),
            self.ratio_sand_spin,
        )

        # Coarse Aggregate (Gravel/Stone) parts
        self.ratio_gravel_spin = self._spin(3.0, 0.0, 100.0, 0.1, 2)
        self.ratio_gravel_spin.valueChanged.connect(self._on_ratio_spin_changed)
        ratio_form.addRow(
            self._label_with_info(
                "Coarse Agg / Stone (Parts)",
                "Volumetric proportion of coarse aggregate (gravel/crushed stone).\n"
                "Set to 0.0 for mortar / plaster mixes.",
            ),
            self.ratio_gravel_spin,
        )

        # Water-Cement Ratio
        self.ratio_wc_spin = self._spin(0.50, 0.20, 1.50, 0.01, 3)
        self.ratio_wc_spin.valueChanged.connect(self._on_ratio_spin_changed)
        ratio_form.addRow(
            self._label_with_info(
                "Water-Cement Ratio (W/C)",
                "Ratio of water mass to cement mass.\n"
                "Typical values:\n"
                "  0.45: M25 high strength\n"
                "  0.50: M20 standard RCC (~25 L per 50 kg bag)\n"
                "  0.55: M15 general concrete (~27.5 L per bag)\n"
                "  0.60: M10 / PCC (~30 L per bag)",
            ),
            self.ratio_wc_spin,
        )

        # Ratio summary label
        self.ratio_summary_lbl = QLabel("Proportion: 1 : 1.5 : 3  (Total Parts = 5.50)")
        self.ratio_summary_lbl.setStyleSheet(
            "font-weight: 700; color: #1e40af; font-family: 'JetBrains Mono', monospace; padding: 4px 0;"
        )
        ratio_form.addRow(self.ratio_summary_lbl)

        grp_ratio.setLayout(ratio_form)
        self._ratio_form.addWidget(grp_ratio)

        # ── Estimation Factors & Material Densities ──
        grp_factors = self._group("Factors & Material Constants")
        fact_form = QFormLayout()
        fact_form.setSpacing(6)
        fact_form.setContentsMargins(12, 16, 12, 12)

        # Dry volume factor
        self.ratio_dry_factor_spin = self._spin(1.54, 1.0, 2.50, 0.01, 2)
        self.ratio_dry_factor_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Dry Volume Factor",
                "Multiplier to convert wet compacted volume into dry unmixed ingredient volume.\n\n"
                "Standard engineering values:\n"
                "  Concrete: 1.54 (54% extra for aggregate void filling and shrinkage)\n"
                "  Mortar: 1.33 (33% extra for sand void filling)\n\n"
                "Dry Volume = Wet Gross Volume × Dry Volume Factor.",
            ),
            self.ratio_dry_factor_spin,
        )

        # Wastage
        self.ratio_wastage_spin = self._spin(5.0, 0.0, 30.0, 0.5, 1)
        self.ratio_wastage_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Wastage Factor (%)",
                "Percentage added for handling, mixing, transporting, and compaction losses.\n"
                "Typical: 3–5% for batch plant, 5–10% for site mixing.",
            ),
            self.ratio_wastage_spin,
        )

        # Cement Bag Volume
        self.ratio_bag_vol_spin = self._spin(0.035, 0.010, 0.100, 0.001, 3, suffix=" m\u00b3")
        self.ratio_bag_vol_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Cement Bag Volume",
                "Volume occupied by one bag of cement.\n\n"
                "Standard: 1 bag (50 kg) = 0.035 m³\n"
                "(1 m³ of dry cement = 1 / 0.035 ≈ 28.57 bags).\n\n"
                "Cement Bags = Cement Volume (m³) ÷ 0.035 m³",
            ),
            self.ratio_bag_vol_spin,
        )

        # Cement Bag Weight
        self.ratio_bag_weight_spin = UnitSpinBox("mass", 50.0, 20.0, 100.0, 1.0, 0)
        self.ratio_bag_weight_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Cement Bag Weight",
                "Mass of one bag of cement (standard: 50 kg / 110.2 lb).",
            ),
            self.ratio_bag_weight_spin,
        )

        # Sand Bulk Density
        self.ratio_sand_density_spin = self._spin(1600.0, 1000.0, 2500.0, 50.0, 0, suffix=" kg/m\u00b3")
        self.ratio_sand_density_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Sand Bulk Density",
                "Bulk density of dry sand (typically 1450–1650 kg/m³).\n"
                "Used to calculate total sand mass from volume.",
            ),
            self.ratio_sand_density_spin,
        )

        # Coarse Agg Bulk Density
        self.ratio_gravel_density_spin = self._spin(1500.0, 1000.0, 2500.0, 50.0, 0, suffix=" kg/m\u00b3")
        self.ratio_gravel_density_spin.valueChanged.connect(self._on_input_changed)
        fact_form.addRow(
            self._label_with_info(
                "Coarse Agg Density",
                "Bulk density of coarse aggregate (typically 1450–1600 kg/m³).\n"
                "Used to calculate total coarse aggregate mass from volume.",
            ),
            self.ratio_gravel_density_spin,
        )

        grp_factors.setLayout(fact_form)
        self._ratio_form.addWidget(grp_factors)

        # Pinned Action Bar
        ratio_action_bar = QHBoxLayout()
        ratio_action_bar.setContentsMargins(16, 6, 12, 14)
        self.ratio_calc_btn = QPushButton("  Calculate Material Quantities")
        self.ratio_calc_btn.setMinimumHeight(44)
        self.ratio_calc_btn.clicked.connect(self._run_quantification)
        ratio_action_bar.addWidget(self.ratio_calc_btn)
        self._ratio_action_bar = ratio_action_bar

        self._ratio_form.addStretch()

    # ── Helpers ──────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        return QGroupBox(title)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 0.05em; color: #444653;"
        )
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
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

    # ── Mix Ratio Subtab Event Handlers ──────────────────────────────

    def _block_ratio_signals(self, block: bool) -> None:
        self.ratio_cement_spin.blockSignals(block)
        self.ratio_sand_spin.blockSignals(block)
        self.ratio_gravel_spin.blockSignals(block)
        self.ratio_wc_spin.blockSignals(block)
        self.ratio_dry_factor_spin.blockSignals(block)

    def _on_ratio_preset_changed(self) -> None:
        preset_name = self.ratio_preset_combo.currentText()
        if preset_name in MIX_RATIO_PRESETS:
            p = MIX_RATIO_PRESETS[preset_name]
            self._block_ratio_signals(True)
            self.ratio_cement_spin.setValue(p.cement_ratio)
            self.ratio_sand_spin.setValue(p.sand_ratio)
            self.ratio_gravel_spin.setValue(p.gravel_ratio)
            self.ratio_wc_spin.setValue(p.w_c_ratio)
            self.ratio_dry_factor_spin.setValue(p.dry_volume_factor)
            self._block_ratio_signals(False)
            self._update_ratio_summary()
            self._on_input_changed()

    def _on_ratio_spin_changed(self) -> None:
        self._update_ratio_summary()
        # Check if current ratio matches any preset
        c = self.ratio_cement_spin.value()
        s = self.ratio_sand_spin.value()
        g = self.ratio_gravel_spin.value()
        matched = False
        for name, p in MIX_RATIO_PRESETS.items():
            if (
                abs(p.cement_ratio - c) < 0.001
                and abs(p.sand_ratio - s) < 0.001
                and abs(p.gravel_ratio - g) < 0.001
            ):
                self.ratio_preset_combo.blockSignals(True)
                self.ratio_preset_combo.setCurrentText(name)
                self.ratio_preset_combo.blockSignals(False)
                matched = True
                break
        if not matched:
            self.ratio_preset_combo.blockSignals(True)
            self.ratio_preset_combo.setCurrentText("Custom Ratio")
            self.ratio_preset_combo.blockSignals(False)
        self._on_input_changed()

    def _update_ratio_summary(self) -> None:
        c = self.ratio_cement_spin.value()
        s = self.ratio_sand_spin.value()
        g = self.ratio_gravel_spin.value()
        total = c + s + g
        if g > 0:
            text = f"Proportion: {c:g} : {s:g} : {g:g}  (Total Parts = {total:g})"
        else:
            text = f"Mortar Proportion: {c:g} : {s:g}  (Total Parts = {total:g})"
        self.ratio_summary_lbl.setText(text)

    def _on_ratio_mode_changed(self) -> None:
        mode = self.ratio_mode_combo.currentData()
        is_vol = mode == "volume"
        self._grp_ratio_volume.setVisible(is_vol)
        self._grp_ratio_elements.setVisible(not is_vol)
        self._on_input_changed()

    def _on_subtab_changed(self, index: int) -> None:
        """Handle user switching subtabs."""
        self._on_input_changed()

    # ── Ratio Element Table ──────────────────────────────────────────

    def _add_ratio_element(self) -> None:
        """Add a new element row to the ratio elements table."""
        self._ratio_elem_table.blockSignals(True)
        row = self._ratio_elem_table.rowCount()
        self._ratio_elem_table.insertRow(row)

        type_combo = QComboBox()
        for t in _ELEMENT_TYPES:
            type_combo.addItem(t)
        self._ratio_elem_table.setCellWidget(row, 0, type_combo)
        type_combo.currentIndexChanged.connect(lambda: self._on_input_changed())

        for col in range(1, 5):
            if col < 4:
                spin = UnitSpinBox("length_m", 1.0, 0.001, 1000.0, 0.1, 3)
            else:
                spin = QDoubleSpinBox()  # type: ignore[assignment]
                spin.setRange(1, 10000)
                spin.setDecimals(0)
                spin.setValue(1)
                spin.setSingleStep(1)
            spin.valueChanged.connect(self._on_input_changed)
            spin.valueChanged.connect(lambda _=None: self._update_ratio_element_volumes())
            self._ratio_elem_table.setCellWidget(row, col, spin)

        vol_item = QTableWidgetItem("1.000")
        vol_item.setFlags(vol_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._ratio_elem_table.setItem(row, 5, vol_item)

        self._ratio_elem_table.blockSignals(False)
        self._update_ratio_element_volumes()
        self._on_input_changed()

    def _remove_ratio_element(self) -> None:
        """Remove the selected row from ratio elements table."""
        row = self._ratio_elem_table.currentRow()
        if row >= 0:
            self._ratio_elem_table.removeRow(row)
            self._update_ratio_element_volumes()
            self._on_input_changed()

    def _on_ratio_element_changed(self, item: QTableWidgetItem) -> None:
        """Handle cell edit in ratio elements table."""
        self._update_ratio_element_volumes()

    def _update_ratio_element_volumes(self) -> None:
        """Recalculate and display per-element and total volumes for ratio elements."""
        up = self.unit_prefs or get_unit_prefs()
        total = 0.0
        for row in range(self._ratio_elem_table.rowCount()):
            l_spin = self._ratio_elem_table.cellWidget(row, 1)
            w_spin = self._ratio_elem_table.cellWidget(row, 2)
            d_spin = self._ratio_elem_table.cellWidget(row, 3)
            q_spin = self._ratio_elem_table.cellWidget(row, 4)
            if all(w is not None for w in [l_spin, w_spin, d_spin, q_spin]):
                vol = l_spin.value() * w_spin.value() * d_spin.value() * q_spin.value()
                total += vol
                vol_item = self._ratio_elem_table.item(row, 5)
                if vol_item:
                    vol_item.setText(f"{up.convert_volume_m3(vol):.3f}")
        self._ratio_elem_total_label.setText(
            f"Total: {up.convert_volume_m3(total):.3f} {up.volume_unit()}"
        )

    def _get_ratio_elements(self) -> list[StructuralElement]:
        """Parse ratio elements table into StructuralElement list."""
        elements: list[StructuralElement] = []
        for row in range(self._ratio_elem_table.rowCount()):
            type_combo: QComboBox = self._ratio_elem_table.cellWidget(row, 0)  # type: ignore[assignment]
            l_spin: QDoubleSpinBox = self._ratio_elem_table.cellWidget(row, 1)  # type: ignore[assignment]
            w_spin: QDoubleSpinBox = self._ratio_elem_table.cellWidget(row, 2)  # type: ignore[assignment]
            d_spin: QDoubleSpinBox = self._ratio_elem_table.cellWidget(row, 3)  # type: ignore[assignment]
            q_spin: QDoubleSpinBox = self._ratio_elem_table.cellWidget(row, 4)  # type: ignore[assignment]

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

        # Switch to Design Mix subtab
        self._left_tabs.setCurrentIndex(0)
        self._transfer_data = td
        self._populate_data_from_transfer(td)
        up = self.unit_prefs or get_unit_prefs()
        pvu = up.mass_per_volume_unit()
        cement_pv = (
            td.cement_kg_per_m3 * 1.68555 if up.is_imperial() else td.cement_kg_per_m3
        )
        self._status_banner.setText(
            f"Loaded: {td.code_used}  |  "
            f"f'cr={up.convert_strength_mpa(td.target_mean_strength_mpa):.1f} "
            f"{up.strength_unit()}  |  "
            f"W/C={td.w_c_ratio:.3f}  |  "
            f"Cement={cement_pv:.1f} {pvu}"
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
        """Update unit-dependent labels when unit preferences change."""
        if self.unit_prefs is None:
            return
        up = self.unit_prefs

        # Design Mix subtab
        set_label_with_info_text(
            self._volume_label, f"Concrete Volume ({up.volume_unit()})"
        )
        self._elem_table.setHorizontalHeaderLabels(self._element_headers())
        self._update_element_volumes()

        # Mix Ratio subtab
        set_label_with_info_text(
            self._ratio_volume_label, f"Work Volume ({up.volume_unit()})"
        )
        self._ratio_elem_table.setHorizontalHeaderLabels(self._element_headers())
        self._update_ratio_element_volumes()

    def _element_headers(self) -> list[str]:
        up = self.unit_prefs or get_unit_prefs()
        lu = up.length_unit()
        vu = up.volume_unit()
        return ["Type", f"L ({lu})", f"W ({lu})", f"D ({lu})", "Qty", f"Vol ({vu})"]

    # ── Element Table (Design Mix Subtab) ─────────────────────────────

    def _add_element(self) -> None:
        """Add a new element row to the table."""
        self._elem_table.blockSignals(True)
        row = self._elem_table.rowCount()
        self._elem_table.insertRow(row)

        type_combo = QComboBox()
        for t in _ELEMENT_TYPES:
            type_combo.addItem(t)
        self._elem_table.setCellWidget(row, 0, type_combo)
        type_combo.currentIndexChanged.connect(lambda: self._on_input_changed())

        for col in range(1, 5):
            if col < 4:
                spin = UnitSpinBox("length_m", 1.0, 0.001, 1000.0, 0.1, 3)
            else:
                spin = QDoubleSpinBox()  # type: ignore[assignment]
                spin.setRange(1, 10000)
                spin.setDecimals(0)
                spin.setValue(1)
                spin.setSingleStep(1)
            spin.valueChanged.connect(self._on_input_changed)
            spin.valueChanged.connect(lambda _=None: self._update_element_volumes())
            self._elem_table.setCellWidget(row, col, spin)

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
        up = self.unit_prefs or get_unit_prefs()
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
                    vol_item.setText(f"{up.convert_volume_m3(vol):.3f}")
        self._elem_total_label.setText(
            f"Total: {up.convert_volume_m3(total):.3f} {up.volume_unit()}"
        )

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
        if self._worker.isRunning():
            return

        self._debounce.stop()
        self.calc_btn.setEnabled(False)
        self.calc_btn.setText("  Calculating...")
        self.ratio_calc_btn.setEnabled(False)
        self.ratio_calc_btn.setText("  Calculating...")

        active_tab = self._left_tabs.currentIndex()

        try:
            if active_tab == 1:
                # ── Mix Ratio Subtab ──
                quantifier = MixRatioQuantifier(
                    cement_ratio=self.ratio_cement_spin.value(),
                    sand_ratio=self.ratio_sand_spin.value(),
                    gravel_ratio=self.ratio_gravel_spin.value(),
                    w_c_ratio=self.ratio_wc_spin.value(),
                    dry_volume_factor=self.ratio_dry_factor_spin.value(),
                    cement_bag_volume_m3=self.ratio_bag_vol_spin.value(),
                    cement_bag_weight_kg=self.ratio_bag_weight_spin.value(),
                    fine_agg_bulk_density_kg_m3=self.ratio_sand_density_spin.value(),
                    coarse_agg_bulk_density_kg_m3=self.ratio_gravel_density_spin.value(),
                    label=self.ratio_preset_combo.currentText(),
                )
                mode = self.ratio_mode_combo.currentData()
                wastage = self.ratio_wastage_spin.value()

                if mode == "volume":
                    vol = self.ratio_volume_spin.value()
                    if vol <= 0:
                        raise ValueError("Volume must be positive")
                    self._worker.set_ratio_volume_mode(quantifier, vol, wastage)
                else:
                    elements = self._get_ratio_elements()
                    if not elements:
                        raise ValueError("Add at least one structural element")
                    self._worker.set_ratio_elements_mode(quantifier, elements, wastage)

            else:
                # ── Design Mix Subtab ──
                td = self._build_transfer_data_from_inputs()
                self._transfer_data = td
                self._worker.set_transfer_data(td)

                overrides = self._get_overrides()
                self._worker.set_overrides(overrides)

                mode = self.mode_combo.currentData()
                wastage = self.wastage_spin.value()

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
        self.ratio_calc_btn.setEnabled(True)
        self.ratio_calc_btn.setText("  Calculate Material Quantities")

        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            up = self.unit_prefs or get_unit_prefs()
            self.window().status_bar.showMessage(
                f"Quantified \u2014 Gross: {up.convert_volume_m3(bill.gross_concrete_volume_m3):.3f} "
                f"{up.volume_unit()}  |  "
                f"Cement: {up.convert_mass_kg(bill.total_cement_kg):,.1f} {up.mass_unit()} "
                f"({bill.total_cement_bags:.0f} bags)  |  "
                f"Water: {up.convert_mass_kg(bill.total_water_kg):,.1f} {up.mass_unit()}",
                8000,
            )
        # Auto-save to history
        self._auto_save_history(bill)

    def _on_error(self, msg: str) -> None:
        """Handle quantification error."""
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("  Calculate Material Quantities")
        self.ratio_calc_btn.setEnabled(True)
        self.ratio_calc_btn.setText("  Calculate Material Quantities")
        QMessageBox.warning(self, "Quantification Error", msg)

    # ── History ──────────────────────────────────────────────────────

    _history_db = None  # Set by MainWindow

    def _auto_save_history(self, bill: MaterialBill) -> None:
        """Auto-save quantification result to history DB."""
        if self._history_db is None:
            return
        try:
            from dataclasses import asdict

            # UI state the transfer data alone cannot carry back into the
            # form: subtab, mode, element rows and mix-ratio parts.
            extra: dict = {}
            if self._left_tabs.currentIndex() == 1:
                inp = bill.transfer_data
                extra["ratio_ui"] = {
                    "cement_ratio": self.ratio_cement_spin.value(),
                    "sand_ratio": self.ratio_sand_spin.value(),
                    "gravel_ratio": self.ratio_gravel_spin.value(),
                    "w_c_ratio": self.ratio_wc_spin.value(),
                    "dry_volume_factor": self.ratio_dry_factor_spin.value(),
                    "cement_bag_volume_m3": self.ratio_bag_vol_spin.value(),
                    "cement_bag_weight_kg": self.ratio_bag_weight_spin.value(),
                    "fine_agg_bulk_density": self.ratio_sand_density_spin.value(),
                    "coarse_agg_bulk_density": self.ratio_gravel_density_spin.value(),
                    "mode": self.ratio_mode_combo.currentData() or "volume",
                    "elements": [
                        asdict(e) for e in self._get_ratio_elements()
                    ],
                }
            else:
                inp = self._build_transfer_data_from_inputs()
                extra["design_ui"] = {
                    "mode": self.mode_combo.currentData() or "volume",
                    "elements": [asdict(e) for e in self._get_elements()],
                }
            name = f"Quantification - {bill.net_concrete_volume_m3:.2f} m\u00b3"
            self._history_db.save_quantification(
                inp, bill, name=name, extra_input=extra
            )
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

        try:
            inp_data = json.loads(rec["input_json"])
        except (json.JSONDecodeError, TypeError):
            inp_data = {}

        # Restore inputs to UI if transfer_data is available
        if bill.transfer_data:
            td = bill.transfer_data
            self._transfer_data = td

            ratio_ui = inp_data.get("ratio_ui")
            design_ui = inp_data.get("design_ui")
            is_ratio = design_ui is None and (
                ratio_ui is not None
                or "Mix Ratio" in td.code_used
                or "Mortar" in td.code_used
            )
            if is_ratio:
                # Switch to Mix Ratio subtab
                self._left_tabs.setCurrentIndex(1)
                if ratio_ui:
                    self.ratio_cement_spin.setValue(
                        ratio_ui.get("cement_ratio", self.ratio_cement_spin.value())
                    )
                    self.ratio_sand_spin.setValue(
                        ratio_ui.get("sand_ratio", self.ratio_sand_spin.value())
                    )
                    self.ratio_gravel_spin.setValue(
                        ratio_ui.get("gravel_ratio", self.ratio_gravel_spin.value())
                    )
                    self.ratio_wc_spin.setValue(
                        ratio_ui.get("w_c_ratio", self.ratio_wc_spin.value())
                    )
                    self.ratio_dry_factor_spin.setValue(
                        ratio_ui.get(
                            "dry_volume_factor", self.ratio_dry_factor_spin.value()
                        )
                    )
                    self.ratio_bag_vol_spin.setValue(
                        ratio_ui.get(
                            "cement_bag_volume_m3", self.ratio_bag_vol_spin.value()
                        )
                    )
                    self.ratio_bag_weight_spin.setValue(
                        ratio_ui.get(
                            "cement_bag_weight_kg", self.ratio_bag_weight_spin.value()
                        )
                    )
                    self.ratio_sand_density_spin.setValue(
                        ratio_ui.get(
                            "fine_agg_bulk_density",
                            self.ratio_sand_density_spin.value(),
                        )
                    )
                    self.ratio_gravel_density_spin.setValue(
                        ratio_ui.get(
                            "coarse_agg_bulk_density",
                            self.ratio_gravel_density_spin.value(),
                        )
                    )
                    mode = ratio_ui.get("mode", "volume")
                    idx = self.ratio_mode_combo.findData(mode)
                    if idx >= 0:
                        self.ratio_mode_combo.setCurrentIndex(idx)
                    if mode == "elements":
                        self._restore_element_rows(
                            self._ratio_elem_table,
                            self._add_ratio_element,
                            ratio_ui.get("elements") or [],
                        )
                    else:
                        self.ratio_volume_spin.setValue(bill.net_concrete_volume_m3)
                else:
                    idx = self.ratio_mode_combo.findData("volume")
                    if idx >= 0:
                        self.ratio_mode_combo.setCurrentIndex(idx)
                    self.ratio_volume_spin.setValue(bill.net_concrete_volume_m3)
                self.ratio_wastage_spin.setValue(bill.wastage_percent)
            else:
                # Switch to Design Mix subtab
                self._left_tabs.setCurrentIndex(0)
                self._populate_data_from_transfer(td)

                # Select the mode the record was made with and restore
                # its inputs (element rows when not volume mode).
                mode = (design_ui or {}).get("mode", "volume")
                idx = self.mode_combo.findData(mode)
                if idx < 0:
                    idx = self.mode_combo.findData("volume")
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
                if mode == "elements":
                    self._restore_element_rows(
                        self._elem_table,
                        self._add_element,
                        (design_ui or {}).get("elements") or [],
                    )
                else:
                    self.volume_spin.setValue(bill.net_concrete_volume_m3)
                self.wastage_spin.setValue(bill.wastage_percent)

                # Show group override and populate override values
                self._grp_over.setVisible(True)
                self._populate_override_defaults(td)

                up = self.unit_prefs or get_unit_prefs()
                cement_pv = (
                    td.cement_kg_per_m3 * 1.68555
                    if up.is_imperial()
                    else td.cement_kg_per_m3
                )
                self._status_banner.setText(
                    f"Loaded from history: {td.code_used}  |  "
                    f"f'cr={up.convert_strength_mpa(td.target_mean_strength_mpa):.1f} "
                    f"{up.strength_unit()}  |  "
                    f"W/C={td.w_c_ratio:.3f}  |  "
                    f"Cement={cement_pv:.1f} {up.mass_per_volume_unit()}"
                )
                self._status_banner.setStyleSheet(
                    "background-color: #d1fae5; color: #065f46; "
                    "border: 1px solid #10b981; border-radius: 4px; "
                    "padding: 10px 14px; font-weight: 600;"
                )

    @staticmethod
    def _restore_element_rows(table, add_row_fn, elements: list[dict]) -> None:
        """Rebuild an element table from saved StructuralElement dicts."""
        table.setRowCount(0)
        for e in elements:
            add_row_fn()
            row = table.rowCount() - 1
            combo = table.cellWidget(row, 0)
            if combo is not None:
                for i in range(combo.count()):
                    if combo.itemText(i).lower() == str(
                        e.get("element_type", "")
                    ).lower():
                        combo.setCurrentIndex(i)
                        break
            for col, key in ((1, "length_m"), (2, "width_m"), (3, "depth_m")):
                spin = table.cellWidget(row, col)
                if spin is not None and e.get(key) is not None:
                    spin.setValue(float(e[key]))
            q_spin = table.cellWidget(row, 4)
            if q_spin is not None and e.get("quantity") is not None:
                q_spin.setValue(int(e["quantity"]))

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
            up = self.unit_prefs or get_unit_prefs()
            mu = up.mass_unit()
            vu = up.volume_unit()
            pvu = up.mass_per_volume_unit()

            def pv(kg_m3: float) -> float:
                return kg_m3 * 1.68555 if up.is_imperial() else kg_m3

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Material", f"Per {vu} ({pvu})", "Total", "Unit"])
            writer.writerow(
                [
                    "Cement",
                    f"{pv(td.cement_kg_per_m3):.1f}",
                    f"{up.convert_mass_kg(bill.total_cement_kg):.1f}",
                    mu,
                ]
            )
            writer.writerow(
                [
                    "Water (field)",
                    f"{pv(td.field_water_kg_per_m3):.1f}",
                    f"{up.convert_mass_kg(bill.total_water_kg):.1f}",
                    mu,
                ]
            )
            writer.writerow(
                [
                    "Fine Aggregate (field)",
                    f"{pv(td.field_fine_aggregate_kg_per_m3):.1f}",
                    f"{up.convert_mass_kg(bill.total_fine_aggregate_kg):.1f}",
                    mu,
                ]
            )
            if bill.total_coarse_aggregate_kg > 0:
                writer.writerow(
                    [
                        "Coarse Aggregate (field)",
                        f"{pv(td.field_coarse_aggregate_kg_per_m3):.1f}",
                        f"{up.convert_mass_kg(bill.total_coarse_aggregate_kg):.1f}",
                        mu,
                    ]
                )
            if bill.total_scm_kg > 0:
                writer.writerow(
                    [
                        "SCM",
                        f"{pv(td.scm_kg_per_m3):.1f}",
                        f"{up.convert_mass_kg(bill.total_scm_kg):.1f}",
                        mu,
                    ]
                )
            writer.writerow(
                [
                    "Cement Bags",
                    "",
                    f"{bill.total_cement_bags:.0f}",
                    f"bags ({up.convert_mass_kg(bill.cement_bag_weight_kg):.0f} {mu})",
                ]
            )
            writer.writerow([])
            writer.writerow(
                [f"Net Volume ({vu})", f"{up.convert_volume_m3(bill.net_concrete_volume_m3):.3f}"]
            )
            writer.writerow(["Wastage (%)", f"{bill.wastage_percent:.1f}"])
            writer.writerow(
                [
                    f"Gross Volume ({vu})",
                    f"{up.convert_volume_m3(bill.gross_concrete_volume_m3):.3f}",
                ]
            )

            with open(path, "w", newline="") as f:
                f.write(output.getvalue())
            if hasattr(self.window(), "status_bar") and self.window().status_bar:
                self.window().status_bar.showMessage(f"Exported to {path}", 5000)

    def _generate_quant_report_html(self) -> str:
        """Generate HTML report for material quantification preview."""
        bill = self._last_bill
        if not bill:
            return ""

        td = bill.transfer_data

        # ── Display-unit conversions ──
        up = self.unit_prefs or get_unit_prefs()
        vu = up.volume_unit()
        mu = up.mass_unit()
        wu = up.water_unit()
        su = up.strength_unit()
        pvu = up.mass_per_volume_unit()

        def pv(kg_m3: float) -> float:
            return kg_m3 * 1.68555 if up.is_imperial() else kg_m3

        net_v = up.convert_volume_m3(bill.net_concrete_volume_m3)
        gross_v = up.convert_volume_m3(bill.gross_concrete_volume_m3)
        waste_v = up.convert_volume_m3(
            bill.gross_concrete_volume_m3 - bill.net_concrete_volume_m3
        )
        target_s = up.convert_strength_mpa(td.target_mean_strength_mpa)
        cement_m = up.convert_mass_kg(bill.total_cement_kg)
        scm_m = up.convert_mass_kg(bill.total_scm_kg)
        admix_m = up.convert_mass_kg(bill.total_admixture_kg)
        fa_bulk = up.convert_volume_m3(bill.total_fine_aggregate_bulk_m3)
        ca_bulk = up.convert_volume_m3(bill.total_coarse_aggregate_bulk_m3)
        water_l = up.convert_water_liters(bill.total_water_liters)
        t_fa = up.convert_mass_kg(bill.total_fine_aggregate_kg)
        t_ca = up.convert_mass_kg(bill.total_coarse_aggregate_kg)
        t_w = up.convert_mass_kg(bill.total_water_kg)

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
                <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-primary uppercase">Mix Specification</div>
                <div class="text-[24px] leading-[32px] font-semibold text-on-surface">{td.code_used}</div>
                <div class="text-on-surface-variant font-body-md mt-2">Target/Strength: {target_s:.1f} {su}</div>
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
                        <span class="text-[24px] font-bold">{net_v:,.3f}</span>
                        <span class="text-[11px] pb-1">{vu}</span>
                    </div>
                </div>
                <div class="border border-outline-variant p-4 flex flex-col gap-2 bg-surface-container-low">
                    <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant uppercase">Wastage ({bill.wastage_percent:.1f}%)</div>
                    <div class="flex justify-between items-end">
                        <span class="text-[24px] font-bold">{waste_v:,.3f}</span>
                        <span class="text-[11px] pb-1">{vu}</span>
                    </div>
                </div>
                <div class="border-2 border-primary p-4 flex flex-col gap-2">
                    <div class="text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-primary uppercase">Gross Volume</div>
                    <div class="flex justify-between items-end text-primary">
                        <span class="text-[24px] font-bold">{gross_v:,.3f}</span>
                        <span class="text-[11px] pb-1 font-bold">{vu}</span>
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
                            <span class="text-[16px] leading-[24px] font-medium">{cement_m:,.1f} {mu}</span>
                        </div>
                        {f'<div class="flex justify-between items-center"><span class="font-body-md text-on-surface">SCM</span><span class="text-[16px] leading-[24px] font-medium font-bold">{scm_m:,.1f} {mu}</span></div>' if bill.total_scm_kg > 0 else ""}
                    </div>
                </div>
                <div class="border border-outline-variant">
                    <div class="bg-surface-container-high px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold border-b border-outline-variant">Aggregates & Water</div>
                    <div class="p-4 space-y-4">
                        <div class="flex justify-between items-center">
                            <span class="font-body-md text-on-surface">Fine Aggregate (Sand)</span>
                            <span class="text-[16px] leading-[24px] font-medium font-bold">{fa_bulk:,.3f} {vu}</span>
                        </div>
                        {f'<div class="flex justify-between items-center"><span class="font-body-md text-on-surface">Coarse Aggregate</span><span class="text-[16px] leading-[24px] font-medium font-bold">{ca_bulk:,.3f} {vu}</span></div>' if bill.total_coarse_aggregate_kg > 0 else ""}
                        <div class="flex justify-between items-center text-on-surface-variant">
                            <span class="font-body-md">Water (Field/Mixing)</span>
                            <span class="text-[16px] leading-[24px] font-medium">{water_l:,.1f} {wu}</span>
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
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Per {vu} ({pvu})</th>
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Total ({mu})</th>
                        <th class="px-4 py-2 text-[11px] leading-[16px] tracking-[0.05em] font-semibold text-on-surface-variant text-right">Volume/Bags</th>
                    </tr>
                </thead>
                <tbody class="text-[13px] leading-[18px]">
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Portland Cement</td>
                        <td class="px-4 py-2 text-right">{pv(td.cement_kg_per_m3):,.1f}</td>
                        <td class="px-4 py-2 text-right">{cement_m:,.1f}</td>
                        <td class="px-4 py-2 text-right">{bill.total_cement_bags:,.0f} bags</td>
                    </tr>
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Fine Aggregate</td>
                        <td class="px-4 py-2 text-right">{pv(td.field_fine_aggregate_kg_per_m3):,.1f}</td>
                        <td class="px-4 py-2 text-right">{t_fa:,.1f}</td>
                        <td class="px-4 py-2 text-right">{fa_bulk:,.3f} {vu}</td>
                    </tr>
                    {f'<tr class="zebra-row border-b border-outline-variant"><td class="px-4 py-2 text-on-surface font-semibold">Coarse Aggregate</td><td class="px-4 py-2 text-right">{pv(td.field_coarse_aggregate_kg_per_m3):,.1f}</td><td class="px-4 py-2 text-right">{t_ca:,.1f}</td><td class="px-4 py-2 text-right">{ca_bulk:,.3f} {vu}</td></tr>' if bill.total_coarse_aggregate_kg > 0 else ""}
                    <tr class="zebra-row border-b border-outline-variant">
                        <td class="px-4 py-2 text-on-surface font-semibold">Water</td>
                        <td class="px-4 py-2 text-right">{pv(td.field_water_kg_per_m3):,.1f}</td>
                        <td class="px-4 py-2 text-right">{t_w:,.1f}</td>
                        <td class="px-4 py-2 text-right">{water_l:,.1f} {wu}</td>
                    </tr>
                    {f'<tr class="zebra-row border-b border-outline-variant"><td class="px-4 py-2 text-on-surface font-semibold">SCM</td><td class="px-4 py-2 text-right">{pv(td.scm_kg_per_m3):,.1f}</td><td class="px-4 py-2 text-right">{scm_m:,.1f}</td><td class="px-4 py-2 text-right">-</td></tr>' if bill.total_scm_kg > 0 else ""}
                    {f'<tr class="zebra-row border-b border-outline-variant"><td class="px-4 py-2 text-on-surface font-semibold">Admixture</td><td class="px-4 py-2 text-right">{pv(td.admixture_kg_per_m3):,.3f}</td><td class="px-4 py-2 text-right">{admix_m:,.3f}</td><td class="px-4 py-2 text-right">-</td></tr>' if bill.total_admixture_kg > 0 else ""}
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
            if hasattr(self.window(), "status_bar") and self.window().status_bar:
                self.window().status_bar.showMessage(f"Report saved to {path}", 5000)
