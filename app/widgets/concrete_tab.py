"""Concrete mix design tab — input form + results panel.

Layout follows Stitch "Civil Engineering Precision" design system:
- Left panel: scrollable form with labeled inputs, grouped sections
- Right panel: stat cards, calculation steps table, export buttons
- Spacing: 4px base, 8px compact, 16px padding
- Labels above inputs (label-bold style)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.unit_preferences import get_unit_prefs
from app.widgets.info_button import InfoButton
from app.widgets.psd_widget import ParticleSizeDistributionTab, PSDResultPanel
from app.widgets.report_preview_dialog import ReportPreviewDialog
from app.widgets.result_panel import ResultPanel, TargetStrengthResultPanel
from app.widgets.unit_spin import UnitSpinBox
from app.workers.mix_design_worker import MixDesignWorker
from concrete_mix import (
    MixDesignResult,
    calculate_target_strength,
    export_to_csv,
    generate_pdf_report,
    map_cement_type,
)
from concrete_mix.codes.tables.is_tables import (
    CA_VOLUME_FRACTION,
    WATER_CONTENT,
    compute_water_reduction,
    get_exposure_limits,
)
from concrete_mix.models.materials import AggregateShape


class ConcreteMixTab(QWidget):
    """Tab for concrete mix design calculations (ACI 211.1 / IS 10262)."""

    mix_design_ready = pyqtSignal(
        object
    )  # MixDesignResult — for quantification handoff

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker = MixDesignWorker(self)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._last_result: MixDesignResult | None = None
        self._last_target_result = None
        self._last_input_params: dict | None = None
        self.unit_prefs = None  # Set by MainWindow
        # PSD handoff lock state: keys currently locked from a sieve
        # analysis ('fm', 'zone', 'p600', 'nmsa') and their pre-application
        # defaults, so the PSD Clear button can restore them on unlock.
        self._psd_locked: set[str] = set()
        self._psd_snapshot: dict = {}
        self._psd_zone_value: str | None = None
        self._mixdesign_idx: int = 0
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        # Left: tabbed input panel — responsive: min 360, no max, stretchable via splitter
        self._left_tabs = QTabWidget()
        self._left_tabs.setMinimumWidth(360)
        self._left_tabs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # Tab 1: Particle Size Distribution (sieve analysis runs FIRST —
        # its derived parameters feed the mix-design form on the next tab).
        self._psd_result_panel = PSDResultPanel()
        self._psd_tab = ParticleSizeDistributionTab(
            self, result_panel=self._psd_result_panel
        )
        # PSD → mix-design handoff: sieve-analysis-derived parameters fill
        # the form fields each standard's engine consumes (and lock them).
        self._psd_result_panel.apply_to_mix_design.connect(self._on_psd_apply)
        # Clearing the PSD tab unlocks and resets every fed field.
        self._psd_result_panel.clear_all_inputs.connect(
            self._on_psd_inputs_cleared
        )
        self._psd_idx = self._left_tabs.addTab(self._psd_tab, "PSD")
        self._left_tabs.setTabToolTip(self._psd_idx, "Particle Size Distribution")

        # Tab 2: Mix Design (main form)
        input_scroll = QScrollArea()
        input_scroll.setWidgetResizable(True)
        input_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        input_widget = QWidget()
        self._form = QVBoxLayout(input_widget)
        self._form.setContentsMargins(16, 16, 12, 16)
        self._form.setSpacing(8)
        self._build_form()
        input_scroll.setWidget(input_widget)

        # Wrap the scroll area in a page container and pin its action bar
        # below it, so Calculate/Clear stay visible without scrolling to
        # the bottom of the form.
        mix_page = QWidget()
        page_layout = QVBoxLayout(mix_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(input_scroll, 1)
        page_layout.addLayout(self._action_bar)
        self._mixdesign_idx = self._left_tabs.addTab(mix_page, "Mix Design")

        splitter.addWidget(self._left_tabs)

        # Right: dynamic results stack — shows the result type matching the
        # active form mode or PSD subtab.
        self._result_stack = QStackedWidget()
        self._result_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._result_stack.setMinimumWidth(380)

        # Page 0: full mix-design results (quantities, ratio, steps, exports)
        self._result_panel = ResultPanel()
        self._result_stack.addWidget(self._result_panel)

        # Page 1: target-strength-only result
        self._target_strength_panel = TargetStrengthResultPanel()
        self._result_stack.addWidget(self._target_strength_panel)

        # Page 2: PSD gradation curve + stat cards
        self._result_stack.addWidget(self._psd_result_panel)

        # PSD is the default (first) tab, so show its panel by default.
        self._result_stack.setCurrentWidget(self._psd_result_panel)

        splitter.addWidget(self._result_stack)

        splitter.setSizes([440, 760])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setHandleWidth(6)

        # Switch the right results section when the left subtab changes
        self._left_tabs.currentChanged.connect(self._on_left_tab_changed)

        # Wire export buttons
        self._result_panel.btn_csv.clicked.connect(self._export_csv)
        self._result_panel.btn_report.clicked.connect(self._show_preview)

        # Wire quantification handoff
        self._result_panel.send_to_quantification.connect(self.mix_design_ready.emit)

    def _on_left_tab_changed(self, index: int) -> None:
        """Show the result type matching the active left subtab and mode."""
        if index == self._psd_idx:
            self._result_stack.setCurrentWidget(self._psd_result_panel)
        else:
            self._update_result_view()

    def _is_target_strength_mode(self) -> bool:
        """Return whether the form is currently in target-strength mode."""
        return self.mode_combo.currentData() == "target_strength"

    def _update_result_view(self) -> None:
        """Show the result panel matching the selected calculation mode."""
        if not hasattr(self, "_result_stack"):
            return
        if self._left_tabs.currentIndex() == self._psd_idx:
            return
        if self._is_target_strength_mode():
            self._result_stack.setCurrentWidget(self._target_strength_panel)
        else:
            self._result_stack.setCurrentWidget(self._result_panel)

    def _on_mode_changed(self) -> None:
        """Switch between target-strength and full mix-design workflows."""
        if hasattr(self, "_result_panel"):
            self._result_panel.clear()
        if hasattr(self, "_target_strength_panel"):
            self._target_strength_panel.clear()
        self._last_result = None
        self._last_target_result = None
        self._apply_mode_state()
        self._update_result_view()
        self._update_calculate_button()

    def _set_enabled(self, label: QWidget, control: QWidget, enabled: bool) -> None:
        """Enable/disable a form row while preserving its disabled styling."""
        label.setEnabled(enabled)
        control.setEnabled(enabled)

    def _apply_mode_state(self) -> None:
        """Apply the mode-specific active-field matrix.

        Target Strength mode keeps only the selected standard's strength and
        variability inputs active. All other visible controls remain present
        but disabled so users can see which full-design inputs are excluded.
        """
        if not hasattr(self, "mode_combo"):
            return

        target_mode = self._is_target_strength_mode()
        mix_mode = not target_mode
        code = self.code_combo.currentData()
        is_aci = code == "aci211"
        is_is = code == "is10262"
        is_doe = code == "doe"

        # Step 2 and Step 3 are only meaningful for full mix proportioning.
        self._grp_step2.setEnabled(mix_mode)
        self._grp_step3.setEnabled(mix_mode)

        # Step 1: standard and mode are always available.
        self.code_combo.setEnabled(True)
        self.mode_combo.setEnabled(True)

        # Standard-specific durability/workability fields affect mix design,
        # not the target mean strength itself.
        for label, control in (
            (self._lbl_concrete_type, self.concrete_type_combo),
            (self._lbl_exposure, self.exposure_combo),
            (self._lbl_max_wc, self.max_wc_label),
            (self._lbl_air, self.air_check),
            (self._lbl_sulfate, self.sulfate_combo),
            (self._slump_label_container, self.slump_spin),
            (self._lbl_nmsa, self.nmsa_combo),
            (self._lbl_water, self.water_content_label),
            (self._lbl_volume, self.volume_spin),
        ):
            self._set_enabled(label, control, mix_mode)

        # ACI target strength uses the production-data choice. The current
        # implementation applies its documented 4 MPa default deviation when
        # production data is selected.
        self.prod_data_check.setEnabled(mix_mode or is_aci)

        # DOE target strength uses defective percentage and Figure 3's n rule.
        for label, control in (
            (self._lbl_defective_pct, self.defective_pct_spin),
            (self._lbl_n_cubes, self.n_cubes_spin),
        ):
            self._set_enabled(label, control, mix_mode or is_doe)
        self._set_enabled(
            self._lbl_std_dev,
            self.std_dev_display,
            mix_mode or is_doe,
        )
        self.doe_structural_label.setEnabled(mix_mode or is_doe)

        # Target-strength mode does not need DOE age, durability cement limits,
        # or a manual W/C limit. These are re-enabled for full design mode.
        for label, control in (
            (self._lbl_age, self.age_combo),
            (self._lbl_min_cement, self.min_cement_spin),
            (self._lbl_max_cement, self.max_cement_spin),
            (self._lbl_max_wc_override, self.max_wc_override_spin),
        ):
            self._set_enabled(label, control, mix_mode)

        # Characteristic strength is the sole target input for IS and the
        # common strength input for ACI/DOE.
        self._set_enabled(self._lbl_strength, self.strength_spin, True)

        # Keep the standard-specific visual visibility rules after enablement.
        # These booleans are intentionally unused here; they document why the
        # controls above are allowed to remain disabled when hidden by code.
        _ = (is_aci, is_is, is_doe)

        # Locked PSD-fed fields must stay locked regardless of mode/standard
        # toggling (mode swaps re-enable rows above).
        self._enforce_psd_locks()

    def _update_calculate_button(self) -> None:
        """Update the primary action label for the selected mode."""
        if not hasattr(self, "calc_btn") or not self.calc_btn.isEnabled():
            return
        label = "Calculate Target Strength" if self._is_target_strength_mode() else "Calculate Mix Design"
        self.calc_btn.setText(f"  {label}")

    # ── Per-Standard Info Texts ─────────────────────────────────────
    # Keys match the field names used in _info_buttons
    _INFO_TEXTS: dict[str, dict[str, str]] = {
        "standard": {
            "is10262": "IS 10262:2019 — Indian Standard for concrete mix proportioning.\n"
            "Uses metric units (kg/m³). Tables 7–10, Fig. 1 for w/c vs strength.\n"
            "Clause 8: Covers ordinary, high-strength, SCC, and mass concrete.",
            "aci211": "ACI 211.1-22 — American Concrete Institute guide for mix proportioning.\n"
            "Uses absolute volume method. Tables 5.3.3–5.3.6 for water, w/c, and aggregates.\n"
            "Chapter 9: Worked examples for various scenarios.",
            "doe": "DOE (BR 331:1997) — British Department of the Environment standard.\n"
            "Uses metric units (kg/m³). Structured into 5 calculation stages:\n"
            "Stage 1: Strength margin & w/c ratio\n"
            "Stage 2: Water content; Stage 3: Cement content\n"
            "Stage 4: Wet density & total aggregate; Stage 5: Aggregate split.",
        },
        "strength": {
            "is10262": "Target mean compressive strength at 28 days (IS 10262 Clause 7.1).\n\n"
            "f'ck = max(fck + 1.65·S,  fck + X)\n"
            "  fck = characteristic strength (e.g., 30 MPa for M30)\n"
            "  S = standard deviation (Table 2: 3.5–6.0 N/mm²)\n"
            "  X = grade factor (Table 1: 5.0–8.0 N/mm²)\n\n"
            "Example M30:\n"
            "  f'ck = max(30 + 1.65×5, 30+6.5) = max(38.25, 36.5) = 38.25 MPa\n\n"
            "Always use the HIGHER of the two values.",
            "aci211": "Target average compressive strength (ACI 211.1 §5.3.2).\n\n"
            "f'cr = f'c + 1.2·s  (no production data, <30 tests)\n"
            "f'cr = f'c + 2.33·s − 500 psi  (≥30 tests)\n\n"
            "  f'c = specified compressive strength\n"
            "  s = standard deviation (Table 5.3.2.2)\n\n"
            "Example (f'c = 4000 psi, s = 500 psi):\n"
            "  f'cr = 4000 + 1.2×500 = 4600 psi (≈31.7 MPa)",
            "doe": "Target mean strength — DOE Stage 1 (structural, BRE 331:1997 §4.4).\n\n"
             "fm = fc + M = fc + k × s\n"
             "  fc = characteristic strength (structural: fc ≥ 25 MPa)\n"
             "  k = defectives multiplier (e.g., 1.64 for 5%, 1.96 for 2.5%)\n"
             "  s = standard deviation: n < 20 → 8 MPa (Line A), n ≥ 20 → 4 MPa (Line B)\n"
             "      (n = number of test cubes cast for strength testing, Figure 3)\n"
             "      n < 20 → s = 8 MPa (Figure 3 Line A)\n"
             "      n ≥ 20 → s = 4 MPa (Figure 3 Line B, §4.4)\n"
             "This app assumes the mix is for structural elements (fc ≥ 25 MPa).",
        },
        "slump": {
            "is10262": "Workability per IS 1199 (Part 1) — slump test method.\n\n"
            "IS 10262 Table 7 (water content for 20 mm aggregate):\n"
            "  25–50 mm slump → 162 kg/m³ water\n"
            "  75–100 mm slump → 186 kg/m³ water\n"
            "  150–180 mm slump → 208 kg/m³ water\n\n"
            "With superplasticizer: reduce water by 20–30% (IS 10262 §9.5).\n"
            "Typical: 50–100 mm for beams/slabs.",
            "aci211": "Workability per ASTM C143 (slump test).\n\n"
            "ACI 211.1 Table 5.3.3 (mixing water per yd³):\n"
            "  20mm agg, 75mm slump → 325 lb/yd³ (193 kg/m³)\n"
            "  20mm agg, 100mm slump → 345 lb/yd³ (205 kg/m³)\n"
            "  20mm agg, 150mm slump → 375 lb/yd³ (223 kg/m³)\n\n"
            "Air entrainment reduces water by ~25 lb/yd³.\n"
            "Typical: 75–100 mm for general construction.",
            "doe": "Workability classification (DOE Table 3 slump ranges).\n\n"
            "Table 3 classifies slump into 4 classes:\n"
            "  0\u201310 mm slump \u2014 Class 0 (very low slump)\n"
            "  10\u201330 mm slump \u2014 Class 1\n"
            "  30\u201360 mm slump \u2014 Class 2\n"
            "  60\u2013180 mm slump \u2014 Class 3 (high workability)\n\n"
            "Used to select base water content from Table 3.",
        },
        "nmsa": {
            "is10262": "Nominal Maximum Size of Aggregate (IS 10262 §9.3, Table 7).\n\n"
            "Largest sieve retaining 0–15% of aggregate.\n"
            "  10 mm → thin sections, precast, narrow forms\n"
            "  20 mm → general construction (most common)\n"
            "  40 mm → mass concrete, foundations\n\n"
            "IS 383 Table 7 specifies grading for each NMSA.\n"
            "Larger NMSA → less water, less cement, better economy.",
            "aci211": "Nominal Maximum Size of Aggregate (ACI 211.1 §5.3.3).\n\n"
            "Common sizes and typical applications:\n"
            "  3/8 in (10 mm) → thin sections, precast\n"
            "  3/4 in (20 mm) → general construction\n"
            "  1 in (25 mm) → beams, walls\n"
            "  1-1/2 in (40 mm) → mass concrete\n\n"
            "ACI 318 §26.4.2: min cover depends on NMSA.\n"
            "Larger aggregate → lower water demand, higher strength.",
            "doe": "Nominal Maximum Size of Aggregate (DOE Table 3).\n\n"
            "Standard aggregate sizes in DOE:\n"
            "  10 mm,  20 mm,  or  40 mm.\n\n"
            "Used directly for Table 3 water demand and Figure 6 fines proportion.",
        },
        "volume": {
            "is10262": "Volume of concrete for batch proportioning (IS 10262 §9).\n\n"
            "Enter 1.0 m³ for standard per-cubic-metre design.\n"
            "All material quantities are calculated per this volume.\n\n"
            "This is NET volume. Wastage is added in the Quantification tab.\n"
            "For large pours, enter actual volume for direct batch weights.",
            "aci211": "Volume of concrete for batch proportioning (ACI 211.1 §9).\n\n"
            "Enter 1.0 yd³ (or 1.0 m³ in metric) for standard design.\n"
            "All material quantities are calculated per this volume.\n\n"
            "ACI uses absolute volume method: sum of all ingredient volumes = 27 ft³/yd³.\n"
            "For large pours, enter actual volume.",
            "doe": "Volume of concrete for batch proportioning.\n\n"
            "Enter 1.0 m\u00b3 for standard per-cubic-metre design. All material quantities are calculated per this volume.",
        },
        "cement_type": {
            "is10262": "Cement grade per IS 269 / IS 8112 / IS 12269.\n\n"
            "  32.5R (OPC 33) → General purpose, low heat\n"
            "  42.5R (OPC 43) → High early strength (most common)\n"
            "  42.5N (OPC 43) → Normal hardening\n"
            "  52.5N (OPC 53) → High strength, fast construction\n\n"
            "IS 10262 D-3: Maps to ACI cement types.\n"
            "Higher grade → faster strength gain, higher 28-day strength.",
            "aci211": "Cement type per ASTM C150 (ACI 211.1 §6.3).\n\n"
            "  TYPE I → Normal Portland cement\n"
            "  TYPE II → Moderate sulfate resistance\n"
            "  TYPE III → High early strength (≈1 week)\n"
            "  TYPE IV → Low heat of hydration\n"
            "  TYPE V → High sulfate resistance\n\n"
            "In Ghana: OPC grades map to ACI types:\n"
            "  42.5R ≈ TYPE III,  42.5N ≈ TYPE I,  52.5N ≈ TYPE I (high fineness)",
            "doe": "Cement strength class per BS EN 197-1 (mapped from OPC grade).\n\n"
            "The standard maps grades to classes:\n"
            "  52.5N (OPC 53) \u2192 Class 52.5\n"
            "  42.5R/42.5N/32.5R (OPC 43/33) \u2192 Class 42.5\n\n"
            "Used to select reference strength from Table 2.",
        },
        "cement_sg": {
            "is10262": "Specific gravity of cement (IS 10262 Annex D).\n\n"
            "  OPC: SG = 3.15 (standard assumption for all types)\n"
            "  Fly ash: SG = 2.20 (IS 3812)\n"
            "  GGBFS: SG = 2.90 (IS 455)\n"
            "  Silica fume: SG = 2.20 (IS 15388)\n\n"
            "Volume = mass / (SG × 1000) m³\n"
            "Certified SG from supplier should be used if available.",
            "aci211": "Specific gravity of cement (ACI 211.1 Appendix A.3.1).\n\n"
            "  Portland cement: SG = 3.15 (ASTM C150)\n"
            "  Blended cement: check supplier data\n"
            "  Fly ash: SG = 2.20–2.40 (ASTM C618)\n"
            "  GGBFS: SG = 2.80–3.00 (ASTM C989)\n\n"
            "Volume = weight / (SG × 62.4 lb/ft³)\n"
            "3.15 is assumed unless test data is available.",
        },
        "fa_sg": {
            "is10262": "Fine aggregate specific gravity at SSD condition (IS 2386 Part 3).\n\n"
            "  Natural sand: 2.60–2.70\n"
            "  Manufactured sand: 2.50–2.70\n"
            "  Typical value: 2.65\n\n"
            "IS 10262 D-9: Used in volume calculation:\n"
            "  V = mass / (SG × 1000) per m³\n"
            "Test per IS 2386 (Part 3) / ASTM C128.",
            "aci211": "Fine aggregate specific gravity at SSD condition (ACI A.4).\n\n"
            "  Natural sand: 2.60–2.70\n"
            "  Manufactured sand: 2.50–2.70\n"
            "  Typical value: 2.65\n\n"
            "ACI 211.1 uses bulk SG for volume calculations:\n"
            "  V = weight / (SG × 62.4) ft³\n"
            "Test per ASTM C128.",
        },
        "fa_absorption": {
            "is10262": "Water absorption of fine aggregate (IS 2386 Part 3).\n\n"
            "Typical range: 0.5–3.0%\n"
            "  Natural sand: 0.5–2.0%\n"
            "  Manufactured sand: 1.0–3.0%\n\n"
            "Moisture correction (IS 10262 §9.10):\n"
            "  SSD weight = OD weight × (1 + absorption%)\n"
            "  Free water = field moisture% − absorption%\n"
            "  Positive free water → reduce batch water\n"
            "  Negative free water → increase batch water",
            "aci211": "Water absorption of fine aggregate (ACI A.4.1).\n\n"
            "Typical range: 0.5–3.0%\n"
            "  Natural sand: 0.5–2.0%\n"
            "  Manufactured sand: 1.0–3.0%\n\n"
            "Moisture correction (ACI 9.3.8):\n"
            "  Free water = moisture% − absorption%\n"
            "  Positive → wet aggregate, reduce batch water\n"
            "  Negative → dry aggregate, increase batch water\n"
            "Test per ASTM C128 (specific gravity & absorption).",
        },
        "fa_moisture": {
            "is10262": "Free moisture on fine aggregate above SSD condition.\n\n"
            "IS 10262 §9.10 / ACI 9.3.8:\n"
            "  0% = SSD condition (no adjustment needed)\n"
            "  Positive (+%) = wet aggregate → REDUCE mixing water\n"
            "  Negative (−%) = dry aggregate → INCREASE mixing water\n\n"
            "Calculation:\n"
            "  Field moisture = 3%, Absorption = 1%\n"
            "  Free moisture = 3 − 1 = +2%\n"
            "  Water saved = FA mass × 0.02\n\n"
            "Critical for maintaining correct w/c ratio on site.",
            "aci211": "Free moisture on fine aggregate above SSD condition.\n\n"
            "ACI 9.3.8 — Moisture adjustments:\n"
            "  0% = SSD condition (no adjustment)\n"
            "  Positive (+%) = wet → REDUCE batch water\n"
            "  Negative (−%) = dry → INCREASE batch water\n\n"
            "Example (ACI Example 2, §9.3.8):\n"
            "  FA SSD = 1124 lb/yd³, field moisture = +3%\n"
            "  FA field = 1124 × 1.03 = 1158 lb/yd³\n"
            "  Free water = 1158 − 1124 = 34 lb/yd³ (deducted from batch water)",
        },
        "ca_sg": {
            "is10262": "Coarse aggregate specific gravity at SSD condition (IS 2386 Part 3).\n\n"
            "  Granite: 2.65–2.80\n"
            "  Limestone: 2.50–2.70\n"
            "  Basalt: 2.80–3.00\n"
            "  Typical value: 2.70\n\n"
            "IS 10262 D-9: Volume = mass / (SG × 1000) per m³\n"
            "Test per IS 2386 (Part 3) / ASTM C127.",
            "aci211": "Coarse aggregate specific gravity at SSD condition (ACI A.4).\n\n"
            "  Granite: 2.65–2.80\n"
            "  Limestone: 2.50–2.70\n"
            "  Basalt: 2.80–3.00\n"
            "  Typical value: 2.70\n\n"
            "ACI 211.1 Appendix B (Table B.2):\n"
            "  Bulk density × volume fraction = coarse agg weight\n"
            "Test per ASTM C127.",
        },
        "ca_absorption": {
            "is10262": "Water absorption of coarse aggregate (IS 2386 Part 3).\n\n"
            "Typical range: 0.2–2.0%\n"
            "  Dense aggregates (granite): 0.2–0.8%\n"
            "  Porous aggregates: 1.0–5.0%\n\n"
            "IS 10262 §9.10: Critical for moisture correction:\n"
            "  Field weight = SSD weight × (1 + free moisture%)\n"
            "  Free water = moisture% − absorption%\n"
            "  Must be measured before each batch.",
            "aci211": "Water absorption of coarse aggregate (ACI A.4.1).\n\n"
            "Typical range: 0.2–2.0%\n"
            "  Dense aggregates (granite): 0.2–0.8%\n"
            "  Porous aggregates: 1.0–5.0%\n\n"
            "ACI 9.3.8 — Moisture correction:\n"
            "  Free water = moisture% − absorption%\n"
            "  Positive → reduce batch water\n"
            "  Negative → increase batch water\n"
            "Test per ASTM C127.",
        },
        "ca_moisture": {
            "is10262": "Free moisture on coarse aggregate above SSD condition.\n\n"
            "IS 10262 §9.10 / ACI 9.3.8:\n"
            "  Positive (+%) = wet → REDUCE mixing water\n"
            "  Negative (−%) = dry → INCREASE mixing water\n\n"
            "Example (IS 10262 D-9.1):\n"
            "  CA SSD = 1951 kg/m³, field moisture = +1%\n"
            "  CA field = 1951 × 1.01 = 1971 kg/m³\n"
            "  Free water = 1971 − 1951 = 20 L/m³",
            "aci211": "Free moisture on coarse aggregate above SSD condition.\n\n"
            "ACI 9.3.8 — Moisture adjustments:\n"
            "  Positive (+%) = wet → REDUCE batch water\n"
            "  Negative (−%) = dry → INCREASE batch water\n\n"
            "Example (ACI Example 2, §9.3.8):\n"
            "  CA SSD = 1951 lb/yd³, field moisture = +1%\n"
            "  CA field = 1951 × 1.01 = 1971 lb/yd³\n"
            "  Free water = 1971 − 1951 = 20 lb/yd³",
        },
        "ca_bulk": {
            "is10262": "Bulk density of coarse aggregate (IS 2386 Part 3).\n\n"
            "Loose: 1400–1600 kg/m³\n"
            "Compacted: 1500–1700 kg/m³\n\n"
            "IS 10262: Used for volume-to-weight conversion when ordering.\n"
            "Also used in ACI Table 5.3.6 for estimating coarse agg weight.\n"
            "Test per IS 2386 (Part 3) / ASTM C29.",
            "aci211": "Bulk density (unit weight) of coarse aggregate (ACI A.4.1).\n\n"
            "  Loose: 85–105 lb/ft³ (1360–1680 kg/m³)\n"
            "  Rodded: 95–115 lb/ft³ (1520–1840 kg/m³)\n\n"
            "ACI 211.1 Table 5.3.6: Uses bulk density to estimate coarse agg weight.\n"
            "  Weight = bulk density × volume fraction × 27 ft³/yd³\n"
            "Test per ASTM C29.",
        },
        "ca_type": {
            "doe": "Coarse aggregate classification (BRE 331:1997 §1.2.4, Tables 2 & 3).\n\n"
            "BRE 331 considers only two types of aggregate:\n"
            "  • Uncrushed — river gravel, smooth/irregular particles (Table 2 & 3)\n"
            "  • Crushed — crushed rock, angular/rough texture (Table 2 & 3)\n\n"
            "Affects reference compressive strength at W/C=0.5 (Table 2) and free water demand (Table 3).",
        },
        "fa_type": {
            "doe": "Fine aggregate classification (BRE 331:1997 §1.2.4 & Table 3).\n\n"
            "BRE 331 considers only two types of aggregate:\n"
            "  • Uncrushed — natural sand (rounded/irregular particles)\n"
            "  • Crushed — manufactured / crushed rock sand (angular particles)\n\n"
            "When fine and coarse aggregates differ in type, DOE applies:\n"
            "  W = 2/3 Wf + 1/3 Wc (BRE 331:1997 Note to Table 3).",
        },
        "agg_shape": {
            "is10262": "Coarse aggregate particle shape per IS 10262:2019 Table 6.\n\n"
            "  • Angular — crushed rock (standard reference)\n"
            "  • Sub-angular — partially rounded (reduce water by 10 kg/m³)\n"
            "  • Gravel with crushed particles — mixed (reduce water by 20 kg/m³)\n"
            "  • Rounded gravel — river gravel (reduce water by 25 kg/m³)",
        },
        "pct_passing_600um": {
            "doe": "Percentage of fine aggregate passing the 600 \u00b5m sieve (BRE 331:1997 Figure 6).\n\n"
            "Fine aggregate grading is characterized by % passing 600 \u00b5m:\n"
            "  • Coarse sand: ~15–35% passing 600 \u00b5m\n"
            "  • Medium sand: ~40–60% passing 600 \u00b5m\n"
            "  • Fine sand: ~65–100% passing 600 \u00b5m\n\n"
            "Used with slump and NMSA to find fine aggregate % in total aggregate (Figure 6).",
        },
        "exposure": {
            "is10262": "Environmental exposure class per IS 456:2000 Table 3.\n\n"
            "Mild — Protected interiors, surfaces in contact with soil\n"
            "  Min grade: M20, max w/c: 0.60, min cement: 220 kg/m³\n\n"
            "Moderate — Rain exposure, alternating wet & dry\n"
            "  Min grade: M25, max w/c: 0.55, min cement: 240 kg/m³\n\n"
            "Severe — Coastal areas, immersion in water\n"
            "  Min grade: M30, max w/c: 0.50, min cement: 300 kg/m³\n\n"
            "Very Severe — Severe exposure, splash zones\n"
            "  Min grade: M35, max w/c: 0.45, min cement: 320 kg/m³\n\n"
            "Extreme — Sea water, aggressive chemicals\n"
            "  Min grade: M40, max w/c: 0.40, min cement: 340 kg/m³\n\n"
            "IS 10262 Table 5 links exposure to min cement and max w/c.",
            "aci211": "Sulfate exposure classification per ACI 318 Table 19.3.2.1.\n\n"
            "S0 — None: No sulfate exposure\n"
            "S1 — Moderate: Soil with 0.1–0.2% SO₄, water <150 ppm\n"
            "S2 — Severe: Soil with 0.2–2.0% SO₄, water 150–1500 ppm\n"
            "S3 — Very Severe: Soil >2.0% SO₄, seawater\n\n"
            "Determines cement type and max w/c:\n"
            "  S0: Any cement, no w/c limit\n"
            "  S1: w/c ≤ 0.50, min 335 kg/m³\n"
            "  S2: w/c ≤ 0.45, min 370 kg/m³\n"
            "  S3: w/c ≤ 0.40, min 390 kg/m³ (Type V)",
        },
        "scm_type": {
            "is10262": "Supplementary Cementitious Material (IS 10262 §6.3).\n\n"
            "  Fly Ash (IS 3812): Pozzolanic, improves long-term strength\n"
            "    Typical replacement: 15–30%\n"
            "  GGBFS (IS 455): Latent hydraulic, high replacement\n"
            "    Typical replacement: 30–70%\n"
            "  Silica Fume (IS 15388): Ultra-fine, high early strength\n"
            "    Typical replacement: 5–10%\n\n"
            "IS 10262 D-7: Increase cementitious content by 10–15% when using SCMs.",
            "aci211": "Supplementary Cementitious Materials (ACI 211.1 §6.3, ACI 232).\n\n"
            "  Fly Ash (ASTM C618): Pozzolanic, Class F or C\n"
            "    Typical: 15–25% of cementitious material\n"
            "  GGBFS (ASTM C989): Latent hydraulic, Grade 100/120\n"
            "    Typical: 25–50% replacement\n"
            "  Silica Fume (ASTM C1240): Ultra-fine, high performance\n"
            "    Typical: 5–8% replacement\n\n"
            "ACI 232.2R: Fly ash reduces heat, improves durability.\n"
            "ACI 234R: Silica fume dramatically reduces permeability.",
            "doe": "Supplementary Cementitious Material (BRE 331:1997 Part three).\n\n"
            "  Pulverised-Fuel Ash (pfa, BS 3892 / BS EN 450): Pozzolanic with efficiency factor k=0.30 (§9).\n"
            "  Ground Granulated Blastfurnace Slag (ggbs, BS 6699): Latent hydraulic cement replacement (§10).\n\n"
            "BRE 331 Part 3 covers mix design incorporating pfa or ggbs.",
        },
        "scm_pct": {
            "is10262": "SCM replacement percentage by weight of total cementitious material.\n\n"
            "IS 10262 §6.3 / IS standards:\n"
            "  Fly ash: 15–30% (max 35% for structural, IS 3812)\n"
            "  GGBFS: 30–70% (IS 455 allows up to 70%)\n"
            "  Silica fume: 5–10% (IS 15388, typically 7–8%)\n\n"
            "IS 10262 D-7 note: When using SCMs, increase cementitious\n"
            "content by 10–15% to maintain equivalent strength.",
            "aci211": "SCM replacement percentage by weight of total cementitious material.\n\n"
            "ACI 232 / ACI 211.1 §6.3:\n"
            "  Fly ash: 15–25% (Class F), up to 40% (Class C)\n"
            "  GGBFS: 25–50% (ACI 233R)\n"
            "  Silica fume: 5–8% (ACI 234R)\n\n"
            "Higher replacement may require strength adjustment.\n"
            "Check ACI 318 Table 5.3.3.1 for max SCM limits by exposure.",
            "doe": "Percentage replacement of cement by weight (BRE 331:1997 Part three).\n\n"
            "  pfa (fly ash): Typically 15–35% (efficiency factor k=0.30, §9)\n"
            "  ggbs: Typically 30–70% (§10)",
        },
        "scm_sg": {
            "is10262": "Specific gravity of SCM at SSD condition.\n\n"
            "Typical values (auto-fills on selection):\n"
            "  Fly ash: 2.20 (range 1.80–2.40, IS 3812)\n"
            "  GGBFS: 2.90 (range 2.80–3.00, IS 455)\n"
            "  Silica fume: 2.20 (range 2.10–2.30, IS 15388)\n\n"
            "Used in absolute volume method:\n"
            "  V = mass / (SG × 1000) per m³",
            "aci211": "Specific gravity of SCM at SSD condition.\n\n"
            "Typical values (auto-fills on selection):\n"
            "  Fly ash: 2.20 (range 1.80–2.40, ASTM C618)\n"
            "  GGBFS: 2.90 (range 2.80–3.00, ASTM C989)\n"
            "  Silica fume: 2.20 (range 2.10–2.30, ASTM C1240)\n\n"
            "Used in absolute volume method:\n"
            "  V = weight / (SG × 62.4) ft³",
            "doe": "Specific gravity of SCM at SSD condition (BRE 331 Part 3).\n\n"
            "Typical values (auto-fills on selection):\n"
            "  pfa: 2.20 (range 2.00–2.40)\n"
            "  ggbs: 2.90 (range 2.80–3.00)",
        },
        "admix_type": {
            "is10262": "Chemical admixture per IS 9103 (IS 10262 Annex G).\n\n"
            "  Superplasticizer (PCE/SNFC): Water reduction 15–30%\n"
            "    IS 10262 G-3: 0.5–1.5% by cement weight\n"
            "  Plasticizer: Water reduction 8–15%\n"
            "    0.3–0.5% by cement weight\n"
            "  Retarder: Delays setting (hot weather concreting)\n"
            "  Accelerator: Speeds setting (cold weather, precast)\n"
            "  Air-Entraining: 4–8% air for freeze-thaw\n\n"
            "IS 10262 Annex G: Always verify cement-admixture compatibility by trial.",
            "aci211": "Chemical admixture per ASTM C494 / ASTM C260 (ACI 211.1 §6.3, ACI 212.3R).\n\n"
            "  Water Reducers (Type A): 5–12% water reduction\n"
            "  Retarders (Type B): Delay setting 1–3 hours\n"
            "  Accelerators (Type C): Speed up setting\n"
            "  Water Reducers + Retarder (Type D)\n"
            "  Water Reducers + Accelerator (Type E)\n"
            "  Superplasticizers / HRWRA (Type F/G): 12–40% water reduction\n"
            "  Air-Entraining Admixture: ASTM C260\n\n"
            "ACI 211.1 §6.3: Admixture dosage per manufacturer recommendations.",
            "doe": "Chemical admixture per BS 5075 / BS EN 934-2 (BRE 331:1997 §5.3).\n\n"
            "  Water-reducing plasticiser: reduces mixing water by 8–15%\n"
            "  Superplasticiser (HRWRA): reduces mixing water by 15–30%\n\n"
            "Used to meet workability or prevent exceeding maximum cement content limits.",
        },
        "admix_dosage": {
            "is10262": "Admixture dosage as % of cementitious material weight.\n\n"
            "IS 10262 Annex G / IS 9103:\n"
            "  Plasticizer: 0.3–0.5% (water reduction 8–12%)\n"
            "  Superplasticizer: 0.5–1.5% (water reduction 15–30%)\n"
            "  PCE type: 0.3–0.8% (water reduction 30%+)\n\n"
            "Over-dosing causes:\n"
            "  • Excessive retardation\n"
            "  • Segregation and bleeding\n"
            "  • Unwanted air entrainment\n\n"
            "Always check supplier's technical data sheet.",
            "aci211": "Admixture dosage as % of cementitious material weight (ACI 211.1 §4.5, ACI 212.3R).\n\n"
            "Typical ranges (ASTM C494):\n"
            "  Water reducer (Type A): 0.2–0.6% by wt. cementitious\n"
            "  Superplasticizer (Type F): 0.5–1.5% by wt. cementitious\n"
            "  Retarder (Type B): 0.2–0.5%\n\n"
            "Always verify with trial batches.",
            "doe": "Admixture dosage as % of cement weight (BRE 331:1997 §5.3).\n\n"
            "Typical ranges:\n"
            "  Plasticiser: 0.2–0.5% by weight of cement\n"
            "  Superplasticiser: 0.5–1.5% by weight of cement",
        },
        "admix_reduction": {
            "is10262": "Percentage of mixing water reduced by admixture.\n\n"
            "IS 10262 Annex G / IS 9103:\n"
            "  Plasticizer: 8–15% reduction\n"
            "  Mid-range WR: 15–25% reduction\n"
            "  Superplasticizer: 15–30% reduction\n"
            "  PCE-based: 30%+ reduction\n\n"
            "Effect: 10% water reduction ≈ 15% strength increase\n"
            "(Abrams' law: strength ∝ 1/(w/c ratio))\n\n"
            "Higher reduction → lower w/c → higher strength & durability.",
            "aci211": "Percentage of mixing water reduced by admixture.\n\n"
            "ACI PRC-211.1-22 §6.3 / ACI 212.3R:\n"
            "  Normal-range WRA (Type A): ≥5% (typically 5–12%)\n"
            "  Mid-range WRA: 5–10%\n"
            "  High-range WRA / HRWRA (Type F): 12–40%\n\n"
            "Effect: 10% water reduction ≈ 15% strength increase\n"
            "(Abrams' law: strength ∝ 1/(w/c ratio))",
            "doe": "Percentage of free water reduced from Table 3 baseline (BRE 331:1997 §5.3).\n\n"
            "  Water-reducing plasticiser: 8–15%\n"
            "  Superplasticiser: 15–30%",
        },
        "admix_sg": {
            "is10262": "Specific gravity of liquid chemical admixture (IS 10262:2019 Clause 5.7 / Annex A Step A-9(e)).\n\n"
            "  Typical range: 1.05–1.25 (default 1.15).\n"
            "Used in absolute volume calculation:\n"
            "  Volume = mass / (SG × 1000) m³.",
            "aci211": "Specific gravity of liquid chemical admixture (ACI PRC-211.1-22 §4.5 / §4.7.7).\n\n"
            "  Typical range: 1.05–1.25 (default 1.15).\n"
            "Used in absolute volume calculation:\n"
            "  Volume = mass / (SG × 1000) m³.",
        },
    }

    def _build_form(self) -> None:
        self._info_buttons: dict[str, InfoButton] = {}

        # ════════════════════════════════════════════════════════════════
        # Step 1 — Design Parameters
        # IS 10262 Step 1: Grade, exposure, workability, placement
        # ════════════════════════════════════════════════════════════════
        grp1 = self._group("Step 1 — Design Parameters")
        f1 = QFormLayout()
        f1.setSpacing(8)
        f1.setContentsMargins(12, 16, 12, 12)

        # Design standard
        self.code_combo = self._combo(
            [("ACI 211.1", "aci211"), ("IS 10262", "is10262"), ("DOE (BR 331)", "doe")],
            default="is10262",
        )
        self.code_combo.currentIndexChanged.connect(self._on_code_changed)
        f1.addRow(
            self._label_with_info(
                "Standard",
                "Design code governing the mix proportioning method.\n\n"
                "ACI 211.1: American Concrete Institute — uses absolute volume method, "
                "imperial units (lb/yd³), Tables 5.3.3–5.3.6.\n\n"
                "IS 10262: Bureau of Indian Standards — uses metric units (kg/m³), "
                "Tables 7–10, Fig. 1 for w/c vs strength.",
                key="standard",
            ),
            self.code_combo,
        )

        self.mode_combo = self._combo(
            [
                ("Concrete Mix Design", "mix_design"),
                ("Target Strength", "target_strength"),
            ],
            default="mix_design",
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        f1.addRow(
            self._label_with_info(
                "Calculation",
                "Choose whether to calculate the complete concrete mix proportions "
                "or only the standard-based target mean strength.\n\n"
                "Target Strength mode does not calculate W/C, material quantities, "
                "or a mix ratio.",
            ),
            self.mode_combo,
        )

        # IS-specific: Concrete Type
        self.concrete_type_combo = self._combo(
            [
                ("Reinforced Concrete", "reinforced"),
                ("Plain Concrete", "plain"),
            ],
            default="reinforced",
        )
        self._lbl_concrete_type = self._label_with_info(
            "Concrete Type",
            "IS 456:2000 Table 5 specifies different limits\n"
            "for Plain and Reinforced concrete.\n\n"
            "Reinforced — structural members with steel reinforcement\n"
            "Plain — mass concrete, foundations without reinforcement",
            key="concrete_type",
        )
        f1.addRow(self._lbl_concrete_type, self.concrete_type_combo)

        # IS-specific: Exposure Class
        self.exposure_combo = self._combo(
            [
                ("None", ""),
                ("Mild", "mild"),
                ("Moderate", "moderate"),
                ("Severe", "severe"),
                ("Very Severe", "very_severe"),
                ("Extreme", "extreme"),
            ],
            default="",
        )
        self._lbl_exposure = self._label_with_info(
            "Exposure Class (IS 456)",
            "Environmental exposure class per IS 456:2000 Table 5.\n"
            "Values depend on concrete type (Plain / Reinforced).\n\n"
            "Mild — Protected interiors\n"
            "Moderate — Exposed to rain, alternating wet & dry\n"
            "Severe — Coastal areas, immersion in water\n"
            "Very Severe — Severe exposure, splash zones\n"
            "Extreme — Aggressive chemical environment\n\n"
            "IS 456 Table 5 links exposure to min cement and max w/c.",
            key="exposure",
        )
        f1.addRow(self._lbl_exposure, self.exposure_combo)

        # Max Free W/C display — uses warning palette from design system
        self.max_wc_label = QLabel("—")
        self.max_wc_label.setWordWrap(True)
        self.max_wc_label.setStyleSheet(
            "font-weight: 600; color: #92400e; font-size: 12px; padding: 6px 10px; "
            "background: #fef3c7; border: 1px solid #f59e0b; border-radius: 4px;"
        )
        self._lbl_max_wc = self._label("Max Free W/C Ratio")
        f1.addRow(self._lbl_max_wc, self.max_wc_label)
        self.exposure_combo.currentIndexChanged.connect(
            self._update_exposure_wc_display
        )
        self.concrete_type_combo.currentIndexChanged.connect(
            self._update_exposure_wc_display
        )

        # ACI-specific: Air-Entrained
        self.air_check = QCheckBox("Air-Entrained Concrete")
        self._lbl_air = QWidget()
        _air_layout = QHBoxLayout(self._lbl_air)
        _air_layout.setContentsMargins(0, 0, 0, 0)
        _air_lbl = self._label("Air Entrainment")
        _air_layout.addWidget(_air_lbl)
        _air_layout.addStretch()
        f1.addRow(self._lbl_air, self.air_check)

        # ACI-specific: Sulfate Exposure
        self.sulfate_combo = self._combo(
            [
                ("S0 \u2014 None", "S0"),
                ("S1 \u2014 Moderate", "S1"),
                ("S2 \u2014 Severe", "S2"),
                ("S3 \u2014 Very Severe", "S3"),
            ],
            default="S0",
        )
        self._lbl_sulfate = self._label_with_info(
            "Sulfate Exposure",
            "Sulfate exposure classification per ACI 318 Table 19.3.2.1.\n\n"
            "S0 — None: No sulfate exposure\n"
            "S1 — Moderate: Soil with 0.1–0.2% SO₄, water <150 ppm\n"
            "S2 — Severe: Soil with 0.2–2.0% SO₄, water 150–1500 ppm\n"
            "S3 — Very Severe: Soil >2.0% SO₄, seawater, brackish water\n\n"
            "Determines cement type (V or IP) and max w/c ratio:\n"
            "  S0: Any cement, no w/c limit\n"
            "  S1: w/c ≤ 0.50, min cement 335 kg/m³\n"
            "  S2: w/c ≤ 0.45, min cement 370 kg/m³\n"
            "  S3: w/c ≤ 0.40, min cement 390 kg/m³ (Type V)",
            key="exposure",
        )
        f1.addRow(self._lbl_sulfate, self.sulfate_combo)

        # ACI-specific: Production Data
        self.prod_data_check = QCheckBox("Has Production Data (\u226530 tests)")
        self.prod_data_check.setChecked(True)
        f1.addRow(None, self.prod_data_check)

        # DOE-specific fields in Step 1
        self.defective_pct_spin = self._spin(5.0, 1.0, 10.0, 0.5, 1)
        self._lbl_defective_pct = self._label_with_info(
            "Defective Percent (%)",
            "Permitted percentage of results falling below the characteristic strength (DOE only).\n\n"
            "Common values:\n"
            "  5% (k = 1.64) \u2014 standard for BS 5328 / EN 206\n"
            "  2.5% (k = 1.96)\n"
            "  1% (k = 2.33)",
            key="defective_percent",
        )

        # DOE: Number of test cubes (n) — structural assumption
        self.n_cubes_spin = QSpinBox()
        self.n_cubes_spin.setRange(1, 200)
        self.n_cubes_spin.setValue(20)
        self.n_cubes_spin.setSingleStep(1)
        self.n_cubes_spin.setToolTip(
            "Number of test cubes (n) cast for compressive strength testing.\n"
            "BRE 331:1997 §4.4, Figure 3 — used to determine standard deviation s."
        )
        self.n_cubes_spin.valueChanged.connect(self._update_std_dev_display)
        self._lbl_n_cubes = self._label_with_info(
            "Number of Test Cubes (n)",
            "Number of test cubes (number of results, n) that will be cast for testing "
            "the compressive strength (BRE 331:1997 §4.4, Figure 3).\n\n"
            "DOE structural assumption (this app assumes structural elements, fc ≥ 25 MPa):\n"
            "  n < 20 → standard deviation s = 8 MPa (Figure 3 Line A)\n"
            "  n ≥ 20 → s = 4 MPa (Figure 3 Line B, §4.4)\n\n"
            "The s value is then used to compute the margin M = k×s\n"
            "and target mean strength f_m = f_c + M (Calculations C1/C2).\n"
            "For non-structural reference the classic Figure 3 is retained when n\n"
            "is not supplied, but the UI always supplies n for DOE structural designs.",
            key="n_cubes",
        )

        # DOE: Standard deviation — display only (shows the s actually applied)
        # BRE 331 §4.4 Figure 3: n<20 → 8 MPa (Line A), n≥20 → 4 MPa (Line B)
        # This field is NOT editable; it simply shows the calculation value.
        self.std_dev_display = QLabel("—")
        self.std_dev_display.setWordWrap(True)
        self.std_dev_display.setStyleSheet(
            "font-weight: 600; color: #1e40af; font-size: 13px; padding: 6px 10px; "
            "background: #eff4ff; border: 1px solid #dbeafe; border-radius: 4px;"
        )
        self._lbl_std_dev = self._label_with_info(
            "Std Deviation (MPa) — Applied",
            "Standard deviation actually applied in the DOE calculation "
            "(BRE 331 §4.4, Figure 3) — display only.\n\n"
            "n < 20 → s = 8 MPa (Line A)\n"
            "n ≥ 20 → s = 4 MPa (Line B)\n"
            "This value is used for M = k×s and fm = fc + M and is derived "
            "from the Number of Test Cubes (n) you entered above. For structural "
            "DOE (fc ≥ 25 MPa) it is the only value used — no manual override.",
            key="std_deviation",
        )
        # Keep a hidden spin for backwards compat where some code may still read it;
        # it is never shown for DOE and always stays at Auto (0) → engine derives s from n.
        self.std_dev_spin = UnitSpinBox("strength", 0.0, 0.0, 20.0, 0.1, 1)
        self.std_dev_spin.setSpecialValueText("Auto (Figure 3: n<20→8, n≥20→4)")
        self.std_dev_spin.setVisible(False)

        self.age_combo = self._combo(
            [("3 Days", 3), ("7 Days", 7), ("28 Days", 28), ("91 Days", 91)],
            default=28,
        )
        self._lbl_age = self._label_with_info(
            "Age (Days)",
            "Concrete age in days for the target compressive strength (DOE only).\n\n"
            "Table 2 provides reference strengths at 3, 7, 28, and 91 days.",
            key="age_days",
        )

        self.min_cement_spin = UnitSpinBox("mass_per_volume", 0.0, 0.0, 1000.0, 10.0, 0)
        self._lbl_min_cement = self._label_with_info(
            "Min Cement (kg/m\u00b3)",
            "Minimum cement content limit for durability (DOE only).\n\n"
            "If the calculated cement content is lower, it will be raised to this limit.",
            key="min_cement",
        )

        self.max_cement_spin = UnitSpinBox("mass_per_volume", 0.0, 0.0, 1000.0, 10.0, 0)
        self._lbl_max_cement = self._label_with_info(
            "Max Cement (kg/m\u00b3)",
            "Maximum cement content limit (DOE only).\n\n"
            "If the calculated cement content is higher, it will be reduced to this limit.",
            key="max_cement",
        )

        self.max_wc_override_spin = self._spin(0.00, 0.00, 1.00, 0.01, 2)
        self._lbl_max_wc_override = self._label_with_info(
            "Max W/C (Durability)",
            "Maximum allowable water-cement ratio for durability (DOE only).\n\n"
            "If the calculated W/C is higher, it will be reduced to this limit.",
            key="max_wc_override",
        )

        f1.addRow(self._lbl_defective_pct, self.defective_pct_spin)
        f1.addRow(self._lbl_n_cubes, self.n_cubes_spin)
        f1.addRow(self._lbl_std_dev, self.std_dev_display)
        f1.addRow(self._lbl_age, self.age_combo)
        f1.addRow(self._lbl_min_cement, self.min_cement_spin)
        f1.addRow(self._lbl_max_cement, self.max_cement_spin)
        f1.addRow(self._lbl_max_wc_override, self.max_wc_override_spin)

        # Structural concrete assumption banner (applicable to all design standards)
        self.doe_structural_label = QLabel(
            "ⓘ Structural Concrete Design: This app assumes the mix is for structural elements "
            "(characteristic strength ≥ 25 MPa across IS 10262, ACI 211.1, and BRE 331). "
            "Minimum characteristic strength is 25 MPa."
        )
        self.doe_structural_label.setWordWrap(True)
        self.doe_structural_label.setStyleSheet(
            "font-size: 11px; color: #92400e; padding: 8px 10px; "
            "background: #fef3c7; border: 1px solid #f59e0b; border-radius: 4px; "
            "margin-top: 4px;"
        )
        f1.addRow(self.doe_structural_label)

        # Strength, slump, NMSA, water, volume (minimum strength 25 MPa for structural concrete)
        self.strength_spin = UnitSpinBox("strength", 25.0, 25.0, 100.0, 0.5, 2)
        self.strength_spin.valueChanged.connect(self._update_std_dev_display)
        self.slump_spin = UnitSpinBox("slump", 75.0, 10.0, 250.0, 5.0, 0)
        self.nmsa_combo = self._combo(
            [("10 mm", 10), ("20 mm", 20), ("40 mm", 40)],
            default=20,
        )
        self.nmsa_combo.currentIndexChanged.connect(self._on_nmsa_changed)
        self.water_content_label = QLabel("—")
        self.water_content_label.setWordWrap(True)
        self.water_content_label.setStyleSheet("font-weight: 600; color: #1e40af; font-size: 13px;")
        self.volume_spin = UnitSpinBox("volume", 1.0, 0.01, 1000.0, 0.1, 3)

        self._lbl_strength = self._label_with_info(
            "Characteristic Strength fck (MPa)",
            "Characteristic compressive strength at 28 days.\n\n"
            "This application assumes concrete is proportioned for structural use "
            "(minimum 25 MPa across IS 10262, ACI 211.1, and BRE 331/DOE).\n\n"
            "IS 10262:2019: f'ck = max(fck + 1.65·S,  fck + X) — take the higher value.\n"
            "  S = standard deviation (Table 2); X = grade factor (Table 1).\n"
            "  e.g., M30 → f'ck = max(30+8.25, 30+6.5) = 38.25 MPa.\n\n"
            "ACI 211.1: f'cr = f'c + 1.34·s (with data) or ACI 318 Table 26.4.3.1(b) overdesign.\n\n"
            "DOE (BRE 331): fm = fc + k·s (Line A: s=8 MPa for n<20, Line B: s=4 MPa for n≥20).\n\n"
            "Typical range: 25–50 MPa (structural), 50–100 MPa (high-strength).",
            key="strength",
        )
        f1.addRow(self._lbl_strength, self.strength_spin)

        f1.addRow(
            self._slump_label_widget(),
            self.slump_spin,
        )
        self._lbl_nmsa = self._label_with_info(
            "NMSA",
            "Nominal Maximum Size of Aggregate — largest sieve retaining 0–15% of aggregate.\n\n"
            "Affects water demand, cement content, and aggregate proportions.\n\n"
            "Common sizes:\n"
            "  10 mm → thin sections, precast, narrow forms\n"
            "  20 mm → general construction (most common)\n"
            "  40 mm → mass concrete, foundations\n\n"
            "IS 10262 Table 7 / ACI 5.3.3: water content varies by NMSA.",
            key="nmsa",
        )
        f1.addRow(self._lbl_nmsa, self.nmsa_combo)
        self._lbl_water = self._label_with_info(
            "Water Content (kg/m\u00b3)",
            "Water content from IS 10262:2019 Table 4 \u2014 determined by NMSA only.\n\n"
            "  10 mm \u2192 208 kg/m\u00b3\n"
            "  20 mm \u2192 186 kg/m\u00b3\n"
            "  40 mm \u2192 165 kg/m\u00b3\n\n"
            "This is a read-only field. Water content depends solely on NMSA.\n"
            "Actual water is adjusted for admixture/shape in the engine.",
            key="water_content",
        )
        f1.addRow(self._lbl_water, self.water_content_label)
        self._lbl_volume = self._label_with_info(
            "Volume (m³)",
            "Volume of concrete for batch proportioning.\n\n"
            "Enter 1.0 m³ for standard per-cubic-metre design, or the actual pour volume.\n"
            "All material quantities will be calculated for this volume.\n\n"
            "Note: This is net volume. Wastage factor is applied in the Quantification tab.",
            key="volume",
        )
        f1.addRow(self._lbl_volume, self.volume_spin)
        grp1.setLayout(f1)
        self._grp_step1 = grp1
        self._form.addWidget(grp1)

        # ════════════════════════════════════════════════════════════════
        # Step 2 — Material Properties
        # IS 10262 Step 1 material params + Steps 6-7 prerequisites
        # ════════════════════════════════════════════════════════════════
        grp2 = self._group("Step 2 — Material Properties")
        f2 = QFormLayout()
        f2.setSpacing(8)
        f2.setContentsMargins(12, 16, 12, 12)

        # -- Cement --
        self.cement_type_combo = self._combo(
            [
                ("32.5R (General Purpose)", "GRADE_32_5R"),
                ("42.5R (High Early Strength)", "GRADE_42_5R"),
                ("42.5N (Normal Hardening)", "GRADE_42_5N"),
                ("52.5N (Extra High Strength)", "GRADE_52_5N"),
            ],
            default="GRADE_42_5R",
        )
        self.cement_sg_spin = self._spin(3.15, 2.8, 3.5, 0.01, 2)
        f2.addRow(
            self._label_with_info(
                "Cement Type",
                "Cement grade determines strength class and setting characteristics.\n\n"
                "IS grades (IS 269/8112/12269):\n"
                "  32.5R → OPC 33, general purpose\n"
                "  42.5R → OPC 43, high early strength\n"
                "  42.5N → OPC 43, normal hardening\n"
                "  52.5N → OPC 53, high strength\n\n"
                "ACI types (ASTM C150):\n"
                "  TYPE I → Normal\n  TYPE III → High early strength\n\n"
                "Higher grade = faster strength gain, higher 28-day strength.",
                key="cement_type",
            ),
            self.cement_type_combo,
        )
        f2.addRow(
            self._label_with_info(
                "Cement Specific Gravity",
                "Ratio of cement density to water density (water = 1.000).\n\n"
                "IS 10262 Annex D / ACI A.3.1:\n"
                "  OPC (all types): SG = 3.15 (standard assumption)\n"
                "  Fly ash: SG = 2.20 (typical)\n"
                "  GGBFS: SG = 2.90 (typical)\n"
                "  Silica fume: SG = 2.20 (typical)\n\n"
                "Used in absolute volume method: V = mass / (SG × 1000) for metric,"
                " V = mass / (SG × 62.4) for ACI.",
                key="cement_sg",
            ),
            self.cement_sg_spin,
        )

        # -- Fine Aggregate --
        self.fa_sg_spin = self._spin(2.65, 2.2, 3.0, 0.01, 2)
        self.fm_spin = self._spin(2.70, 1.0, 4.0, 0.1, 2)
        self.grading_combo = self._combo(
            [
                ("Zone I", "I"),
                ("Zone II", "II"),
                ("Zone III", "III"),
                ("Zone IV", "IV"),
            ],
            default="II",
        )
        self._lbl_fm = self._label_with_info(
            "Fineness Modulus",
            "Fineness modulus of fine aggregate (ACI only).\n\n"
            "FM = cumulative % retained on standard sieves / 100\n"
            "  Coarse sand: FM 2.8–3.2\n"
            "  Medium sand: FM 2.4–2.8\n"
            "  Fine sand: FM 2.0–2.4\n\n"
            "Lower FM → finer sand → more water demand.",
            key="fa_fm",
        )
        self._lbl_zone = self._label_with_info(
            "Grading Zone",
            "Fine aggregate grading zone per IS 383 (IS only).\n\n"
            "Zone I — Coarse sand (higher FM)\n"
            "Zone II — Medium sand (most common)\n"
            "Zone III — Fine sand\n"
            "Zone IV — Very fine sand\n\n"
            "Affects CA volume fraction from IS 10262 Table 5.",
            key="fa_zone",
        )
        self.ca_fraction_combo = QComboBox()
        self._lbl_ca_frac = self._label_with_info(
            "CA Volume Fraction (Table 5)",
            "Volume of coarse aggregate per unit volume of total aggregate\n"
            "from IS 10262:2019 Table 5, at reference w/c = 0.50.\n\n"
            "Varies by NMSA and grading zone.\n"
            "Adjusted for w/c ratio per Clause 5.5.1:\n"
            "  w/c < 0.50 → increase CA fraction by 0.01 per 0.05 deviation\n"
            "  w/c > 0.50 → decrease CA fraction by 0.01 per 0.05 deviation",
            key="ca_fraction",
        )
        self.fa_abs_spin = self._spin(1.0, 0.0, 10.0, 0.1, 1)
        self.fa_moist_spin = self._spin(0.0, 0.0, 20.0, 0.5, 1)
        self.pct_passing_600um_spin = self._spin(60.0, 0.0, 100.0, 1.0, 1)
        self._lbl_pct_passing_600um = self._label_with_info(
            "FA Passing 600 \u00b5m (%)",
            "Percentage of fine aggregate passing the 600 \u00b5m sieve (DOE only).\n\n"
            "This value determines the grading of the sand. Figure 6 uses this percentage "
            "along with the nominal maximum size of aggregate (NMSA) and slump to "
            "determine the fine aggregate proportion in the total aggregate.",
            key="pct_passing_600um",
        )

        # DOE: Fine aggregate type (Uncrushed vs Crushed per BRE 331 §1.2.4 & Table 3)
        self.fa_type_combo = self._combo(
            [
                ("Uncrushed (Natural Sand)", "uncrushed"),
                ("Crushed (Crushed Rock Sand)", "crushed"),
            ],
            default="uncrushed",
        )
        self._lbl_fa_type = self._label_with_info(
            "Fine Aggregate Type",
            "Classification of fine aggregate per BRE 331:1997 §1.2.4 & Table 3.\n\n"
            "BRE 331 considers only two types of aggregate:\n"
            "  • Uncrushed — natural sand (rounded/irregular particles)\n"
            "  • Crushed — manufactured / crushed rock sand (angular particles)\n\n"
            "When fine and coarse aggregates differ in type, DOE applies:\n"
            "  W = 2/3 Wf + 1/3 Wc (BRE 331:1997 Note to Table 3).",
            key="fa_type",
        )

        f2.addRow(
            self._label_with_info(
                "Fine Aggregate SG",
                "Relative density of fine aggregate at SSD condition (water = 1.000).\n\n"
                "IS 10262 D-2 / ACI A.4 / BRE 331 §5.4 Table 9:\n"
                "  Typical range: 2.50–2.75\n\n"
                "Used in volume and density calculations.",
                key="fa_sg",
            ),
            self.fa_sg_spin,
        )
        f2.addRow(self._lbl_fm, self.fm_spin)
        f2.addRow(self._lbl_zone, self.grading_combo)
        f2.addRow(self._lbl_ca_frac, self.ca_fraction_combo)
        f2.addRow(self._lbl_pct_passing_600um, self.pct_passing_600um_spin)
        f2.addRow(self._lbl_fa_type, self.fa_type_combo)
        f2.addRow(
            self._label_with_info(
                "FA Absorption (%)",
                "Water absorbed into aggregate pores to reach SSD condition.\n\n"
                "IS 10262 D-2 / ACI A.4.1:\n"
                "  Fine aggregate: 0.5–3.0% (typical 1.0%)\n\n"
                "Measured per IS 2386 (Part 3) / ASTM C128.\n\n"
                "Moisture adjustment:\n"
                "  SSD weight × (1 + absorption%) = wet weight\n"
                "  Free water = field moisture − absorption%",
                key="fa_absorption",
            ),
            self.fa_abs_spin,
        )
        f2.addRow(
            self._label_with_info(
                "FA Free Moisture (%)",
                "Surface moisture on fine aggregate above SSD condition.\n\n"
                "IS 10262 Clause 9.10 / ACI 9.3.8:\n"
                "  Positive (+%) → wet aggregate, reduces mixing water\n"
                "  Negative (−%) → dry aggregate, absorbs mixing water\n"
                "  Zero (0%) → SSD condition, no adjustment needed",
                key="fa_moisture",
            ),
            self.fa_moist_spin,
        )

        # -- Coarse Aggregate --
        self.ca_sg_spin = self._spin(2.70, 2.2, 3.2, 0.01, 2)
        self.ca_abs_spin = self._spin(0.5, 0.0, 10.0, 0.1, 1)
        self.ca_moist_spin = self._spin(0.0, 0.0, 20.0, 0.5, 1)
        self.ca_bulk_spin = UnitSpinBox("density", 1600.0, 1000.0, 2000.0, 10.0, 0)

        # DOE: Coarse aggregate type (Uncrushed vs Crushed per BRE 331 §1.2.4, Table 2 & Table 3)
        self.ca_type_combo = self._combo(
            [
                ("Uncrushed (Gravel)", "uncrushed"),
                ("Crushed (Crushed Rock)", "crushed"),
            ],
            default="uncrushed",
        )
        self._lbl_ca_type = self._label_with_info(
            "Coarse Aggregate Type",
            "Classification of coarse aggregate per BRE 331:1997 §1.2.4.\n\n"
            "BRE 331 considers only two types of aggregate:\n"
            "  • Uncrushed — river gravel, smooth/irregular particles (Table 2 & 3)\n"
            "  • Crushed — crushed rock, angular/rough texture (Table 2 & 3)\n\n"
            "Affects reference compressive strength (Table 2) and free water demand (Table 3).",
            key="ca_type",
        )

        # IS 10262: Coarse aggregate shape (IS 10262:2019 Table 6)
        self.agg_shape_combo = self._combo(
            [(s.value.replace("_", " ").title(), s.value) for s in AggregateShape],
            default="angular",
        )
        self._lbl_shape = self._label_with_info(
            "Aggregate Shape",
            "Shape of coarse aggregate particles (IS 10262 Table 6).\n\n"
            "Angular — crushed stone (most common)\n"
            "Sub-angular — partially rounded\n"
            "Gravel — rounded river aggregate\n"
            "Gravel with crushed particles — mixed\n\n"
            "Shape affects water demand per IS 10262 Clause 5.2.",
            key="agg_shape",
        )

        self._lbl_ca_bulk = self._label_with_info(
            "Dry-Rodded Bulk Density",
            "Mass of dry-rodded coarse aggregate per unit volume (ASTM C29).\n\n"
            "ACI 211.1 Table 5.3.6 uses bulk volume fraction × dry-rodded bulk density "
            "to calculate coarse aggregate weight per m³ (or yd³).\n\n"
            "Typical range: 1400–1750 kg/m³.",
            key="ca_bulk",
        )

        f2.addRow(
            self._label_with_info(
                "Coarse Aggregate SG",
                "Relative density of coarse aggregate at SSD condition.\n\n"
                "IS 10262 D-2 / ACI A.4 / BRE 331 Table 9:\n"
                "  Granite: 2.65–2.80\n"
                "  Limestone: 2.50–2.70\n"
                "  Basalt: 2.80–3.00\n\n"
                "Measured per IS 2386 (Part 3) / ASTM C127 / BS 812.",
                key="ca_sg",
            ),
            self.ca_sg_spin,
        )
        f2.addRow(self._lbl_ca_type, self.ca_type_combo)
        f2.addRow(self._lbl_shape, self.agg_shape_combo)
        f2.addRow(self._lbl_ca_bulk, self.ca_bulk_spin)
        f2.addRow(
            self._label_with_info(
                "CA Absorption (%)",
                "Water absorbed into coarse aggregate pores to reach SSD state.\n\n"
                "IS 10262 D-2 / ACI A.4.1:\n"
                "  Typical range: 0.2–2.0%\n"
                "  Dense aggregates (granite): 0.2–0.8%\n"
                "  Porous aggregates: 1.0–5.0%",
                key="ca_absorption",
            ),
            self.ca_abs_spin,
        )
        f2.addRow(
            self._label_with_info(
                "CA Free Moisture (%)",
                "Surface moisture on coarse aggregate in the field.\n\n"
                "Positive = wet (water on surface, adds to mixing water)\n"
                "Negative = dry (absorbs from mixing water)\n\n"
                "IS 10262 Clause 9.10 / ACI 9.3.8:",
                key="ca_moisture",
            ),
            self.ca_moist_spin,
        )
        grp2.setLayout(f2)
        self._grp_step2 = grp2
        self._form.addWidget(grp2)

        # ════════════════════════════════════════════════════════════════
        # Step 3 — Admixtures & SCM
        # IS 10262 Annex G / ACI 212
        # ════════════════════════════════════════════════════════════════
        grp3 = self._group("Step 3 — Admixtures & SCM")
        f3 = QFormLayout()
        f3.setSpacing(8)
        f3.setContentsMargins(12, 16, 12, 12)

        # SCM
        self.scm_type_combo = self._combo(
            [
                ("None", ""),
                ("Fly Ash", "fly_ash"),
                ("GGBFS", "ggbfs"),
                ("Metakaolin", "metakaolin"),
                ("Silica Fume", "silica_fume"),
            ],
            default="",
        )
        self.scm_pct_spin = self._spin(0.0, 0.0, 60.0, 1.0, 1)
        self.scm_sg_spin = self._spin(2.20, 1.5, 4.0, 0.05, 2)
        self.scm_type_combo.currentIndexChanged.connect(self._on_scm_type_changed)

        self._lbl_scm_type = self._label_with_info(
            "SCM Type",
            "Supplementary Cementitious Material — partial cement replacement.\n\n"
            "IS 10262 D-7 / ACI 6.3:\n"
            "  Fly Ash (IS 3812): Pozzolanic, improves long-term strength\n"
            "  GGBFS (IS 455): Latent hydraulic, 30–70% replacement\n"
            "  Silica Fume (IS 15388): Ultra-fine, 5–10%\n\n"
            "Benefits: lower heat, better durability, reduced cement usage.",
            key="scm_type",
        )
        f3.addRow(self._lbl_scm_type, self.scm_type_combo)

        self._lbl_scm_pct = self._label_with_info(
            "SCM Replacement (%)",
            "Percentage of cement replaced by SCM by weight.\n\n"
            "IS 10262 D-7 / ACI 232:\n"
            "  Fly Ash: 15–30% (max 35% for structural)\n"
            "  GGBFS: 30–70%\n"
            "  Silica Fume: 5–10% (typically 7–8%)",
            key="scm_pct",
        )
        f3.addRow(self._lbl_scm_pct, self.scm_pct_spin)

        self._lbl_scm_sg = self._label_with_info(
            "SCM Specific Gravity",
            "Relative density of the SCM at SSD condition.\n\n"
            "Typical values (auto-fills on selection):\n"
            "  Fly ash: 2.20 (range 1.80–2.40)\n"
            "  GGBFS: 2.90 (range 2.80–3.00)\n"
            "  Silica fume: 2.20 (range 2.10–2.30)",
            key="scm_sg",
        )
        f3.addRow(self._lbl_scm_sg, self.scm_sg_spin)

        # Admixture
        self.admix_type_combo = self._combo(
            [
                ("None", ""),
                ("Superplasticizer", "superplasticizer"),
                ("Plasticizer", "plasticizer"),
                ("Retarder", "retarder"),
                ("Accelerator", "accelerator"),
                ("Air-Entraining", "air_entraining"),
            ],
            default="",
        )
        self.admix_dosage_spin = self._spin(1.0, 0.0, 5.0, 0.1, 1)
        self.admix_spin = self._spin(0.0, 0.0, 40.0, 0.5, 1)
        self.admix_sg_spin = self._spin(1.15, 1.0, 1.5, 0.01, 2)

        self._lbl_admix_type = self._label_with_info(
            "Admixture Type",
            "Chemical admixture per IS 9103 / ASTM C494 / BS 5075.\n\n"
            "Superplasticizer: Water reduction 15–30%\n"
            "Plasticizer: Water reduction 8–15%\n"
            "Retarder: Delays setting (hot weather)\n"
            "Accelerator: Speeds setting (cold weather)\n"
            "Air-Entraining: 4–8% air for freeze-thaw",
            key="admix_type",
        )
        f3.addRow(self._lbl_admix_type, self.admix_type_combo)

        self._lbl_admix_dosage = self._label_with_info(
            "Dosage (% by wt. cement)",
            "Admixture as percentage of total cementitious material weight.\n\n"
            "IS 10262 G-3 / ACI 212 / BRE 331 §5.3:\n"
            "  Plasticizer: 0.3–0.5%\n"
            "  Superplasticizer: 0.5–1.5%\n"
            "  PCE type: 0.3–0.8%",
            key="admix_dosage",
        )
        f3.addRow(self._lbl_admix_dosage, self.admix_dosage_spin)

        self._lbl_admix_reduction = self._label_with_info(
            "Water Reduction (%)",
            "Mixing water reduced while maintaining target slump.\n\n"
            "IS 10262 G-3 / ACI 212 / BRE 331 §5.3:\n"
            "  Plasticizer: 8–15%  |  Mid-range WR: 15–25%\n"
            "  Superplasticizer: 15–30%  |  PCE: 30%+\n\n"
            "Effect: 10% water reduction ≈ 15% strength increase\n"
            "(Abrams' law: strength ∝ 1/(w/c ratio))",
            key="admix_reduction",
        )
        f3.addRow(self._lbl_admix_reduction, self.admix_spin)

        self._lbl_admix_sg = self._label_with_info(
            "Admixture SG",
            "Specific gravity of liquid chemical admixture.\n\n"
            "IS 10262:2019 Clause 5.7 / Annex A Step A-9(e) / ACI 211.1 §4.5:\n"
            "  Typical range: 1.05–1.25 (default 1.15)\n"
            "Used in absolute volume calculation: V = mass / (SG × 1000) m³.",
            key="admix_sg",
        )
        f3.addRow(self._lbl_admix_sg, self.admix_sg_spin)

        self.reduced_water_label = QLabel("—")
        self.reduced_water_label.setWordWrap(True)
        self.reduced_water_label.setStyleSheet(
            "font-weight: 600; color: #1e40af; font-size: 12px; padding: 6px 10px; "
            "background: #eff4ff; border: 1px solid #dbeafe; border-radius: 4px;"
        )
        self._lbl_reduced_water = self._label_with_info(
            "Reduced Water (kg/m\u00b3)",
            "Mixing water after applying admixture water reduction.\n\n"
            "Reduced water = Base water × (1 \u2212 reduction% / 100)\n\n"
            "IS 10262 / ACI 211.1 / BRE 331: Admixture water reduction is applied to the\n"
            "base water content (determined by NMSA and slump).\n"
            "This reduced value is used for cement content calculation.",
            key="reduced_water",
        )
        f3.addRow(self._lbl_reduced_water, self.reduced_water_label)
        self._base_water_content: float = 0.0
        grp3.setLayout(f3)
        self._grp_step3 = grp3
        self._form.addWidget(grp3)

        # ── Buttons ──
        # Built as a standalone action bar and pinned below the scroll area
        # by _build_ui, so the primary action is always reachable without
        # scrolling to the end of the form.
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(16, 6, 12, 14)

        self.calc_btn = QPushButton("  Calculate Mix Design")
        self.calc_btn.setMinimumHeight(44)
        self.calc_btn.clicked.connect(self._on_calculate)
        btn_layout.addWidget(self.calc_btn, 3)

        self.clear_btn = QPushButton("  Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setMinimumHeight(44)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn, 1)

        self._action_bar = btn_layout

        # Auto-compute water reduction when admixture type or dosage changes
        self.admix_type_combo.currentIndexChanged.connect(self._on_admix_changed)
        self.admix_dosage_spin.valueChanged.connect(self._on_admix_changed)
        self.admix_spin.valueChanged.connect(self._update_reduced_water)

        # Update water content display when slump or NMSA changes
        self.slump_spin.valueChanged.connect(self._update_water_display)
        self.grading_combo.currentIndexChanged.connect(self._update_water_display)

        self._form.addStretch()

        # Initial visibility
        self._on_code_changed()

    # ── Helpers ──────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        """Create a styled group box with Stitch header pattern."""
        g = QGroupBox(title)
        return g

    def _label(self, text: str) -> QLabel:
        """Create a bold uppercase label — refined from Stitch, reduced slop (0.03em, 600).

        Word-wrap is enabled so long labels reflow to multiple lines when the
        sidebar is narrowed; without it the label's minimum size hint equals
        the full text width, which forces the whole form wider than the
        sidebar's 360px floor and clips the input fields.
        """
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; text-transform: uppercase; "
            "letter-spacing: 0.03em; color: #444653;"
        )
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return lbl

    def _label_with_info(self, text: str, info: str, key: str | None = None) -> QWidget:
        """Create a label with an info button beside it.

        If *key* is provided, the button is stored in self._info_buttons[key]
        so its text can be updated dynamically when the design standard changes.
        """
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
        if key and hasattr(self, "_info_buttons"):
            self._info_buttons[key] = btn
        return container

    def _slump_label_widget(self) -> QWidget:
        """Label + info button for the slump input.

        The trailing unit (mm or in) is dynamic — it follows the active
        :class:`UnitPreferences` because the metric slump is always stored in
        mm internally but is shown to imperial users in inches.
        """
        info = (
            "Workability measured by ASTM C143 / IS 1199 (Part 1).\n\n"
            "Slump = vertical drop of concrete after mould removal.\n\n"
            "IS 10262 Table 7 (20 mm agg):\n"
            "  25–50 mm → 162 kg/m³ water\n"
            "  75–100 mm → 186 kg/m³ water\n"
            "  150–180 mm → 208 kg/m³ water\n\n"
            "ACI 211.1 Table 5.3.3: similar lookup by NMSA and slump.\n\n"
            "Typical: 50–100 mm for beams/slabs, 100–150 mm for pumped concrete."
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._lbl_slump = self._label("Slump (mm)")
        layout.addWidget(self._lbl_slump)
        btn = InfoButton(info)
        layout.addWidget(btn)
        layout.addStretch()
        if hasattr(self, "_info_buttons"):
            self._info_buttons["slump"] = btn
        self._refresh_slump_label()
        container = QWidget()
        container.setLayout(layout)
        self._slump_label_container = container
        return container

    def _refresh_slump_label(self) -> None:
        """Rewrite the slump label's unit suffix to match the active units."""
        if not hasattr(self, "_lbl_slump"):
            return
        up = self.unit_prefs or get_unit_prefs()
        suffix = "in" if up.is_imperial() else "mm"
        self._lbl_slump.setText(f"Slump ({suffix})")

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
        self, default: float, lo: float, hi: float, step: float, decimals: int = 2
    ) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(default)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return sb

    # ── Dynamic Visibility ───────────────────────────────────────────

    _SCM_SG_DEFAULTS = {
        "fly_ash": 2.20,
        "fly_ash_c": 2.60,
        "ggbfs": 2.90,
        "metakaolin": 2.60,
        "silica_fume": 2.20,
    }

    # SCM replacement ranges per standards (IS 10262 Table 9 / ACI 232 / BRE 331 Part 3)
    _SCM_REPLACEMENT_RANGE = {
        "fly_ash": (15, 35),
        "fly_ash_c": (15, 40),
        "ggbfs": (25, 70),
        "metakaolin": (5, 15),
        "silica_fume": (5, 10),
    }

    def _on_scm_type_changed(self) -> None:
        scm_type = self.scm_type_combo.currentData()
        if scm_type and scm_type in self._SCM_SG_DEFAULTS:
            self.scm_sg_spin.setValue(self._SCM_SG_DEFAULTS[scm_type])
        # Constrain replacement % range
        if scm_type and scm_type in self._SCM_REPLACEMENT_RANGE:
            lo, hi = self._SCM_REPLACEMENT_RANGE[scm_type]
            self.scm_pct_spin.setRange(lo, hi)
            self.scm_pct_spin.setValue((lo + hi) // 2)
            self.scm_pct_spin.setSuffix(f"  ({lo}–{hi}%)")
        else:
            self.scm_pct_spin.setRange(0, 70)
            self.scm_pct_spin.setSuffix("")

    def _on_admix_changed(self) -> None:
        """Auto-compute water reduction from admixture type + dosage per relevant standard."""
        code = self.code_combo.currentData()
        admix_type = self.admix_type_combo.currentData()
        dosage = self.admix_dosage_spin.value()

        if admix_type and admix_type != "" and dosage > 0:
            reduction, desc = compute_water_reduction(admix_type, dosage, code=code)
            self.admix_spin.setValue(reduction)
            self.admix_spin.setToolTip(desc)
        else:
            if code == "aci211":
                self.admix_spin.setToolTip(
                    "Percentage of mixing water reduced (ACI PRC-211.1-22 §6.3).\n\n"
                    "ASTM C494 / ACI 212.3R:\n"
                    "  Type A (Normal WR): ≥5% (typically 5–12%)\n"
                    "  Type F (HRWRA / Superplasticizer): 12–40%\n"
                    "  Mid-range WRA: 5–10%"
                )
            elif code == "doe":
                self.admix_spin.setToolTip(
                    "Percentage of free water reduced from Table 3 baseline (BRE 331 §5.3).\n\n"
                    "  Water-reducing plasticiser: 8–15%\n"
                    "  Superplasticiser: 15–30%"
                )
            else:
                self.admix_spin.setToolTip(
                    "Percentage of mixing water reduced while maintaining target slump.\n\n"
                    "IS 10262 Annex G:\n"
                    "  Plasticizer (lignosulphonates): 0.3–0.5% → 8–12%\n"
                    "  Superplasticizer (SMFC/SNFC): 0.5–1.5% → 15–30%\n"
                    "  PCE type: 0.3–1.0% → 25–35%\n"
                    "  HRWRA: 0.5–1.5% → 20–35%\n\n"
                    "Effect: Reducing water by 10% → ~15% increase in strength\n"
                    "(Abrams' law: strength ∝ 1/(w/c ratio))"
                )
        self._update_reduced_water()

    def _update_reduced_water(self) -> None:
        """Update the reduced water content display based on base water and reduction %."""
        reduction = self.admix_spin.value()
        if self._base_water_content > 0:
            if reduction > 0:
                reduced = self._base_water_content * (1.0 - reduction / 100.0)
                self.reduced_water_label.setText(
                    f"{self._fmt_water_content(reduced)}  "
                    f"({self._fmt_water_content(self._base_water_content)} \u2212 {reduction:.1f}%)"
                )
            else:
                self.reduced_water_label.setText(
                    f"{self._fmt_water_content(self._base_water_content)} (no admixture reduction)"
                )
        else:
            self.reduced_water_label.setText("\u2014")

    def _update_water_display(self) -> None:
        """Update the water content display for the active standard."""
        nmsa = self.nmsa_combo.currentData()
        code = self.code_combo.currentData()
        is_is = code == "is10262"
        is_aci = code == "aci211"
        is_doe = code == "doe"

        if is_is and nmsa in WATER_CONTENT:
            from concrete_mix.codes.tables.is_tables import (
                interpolate_water_content,
                AGGREGATE_SHAPE_ADJUSTMENT_KG,
            )

            slump = self.slump_spin.value()
            zone = self.grading_combo.currentData() or "II"

            wc = interpolate_water_content(nmsa, slump, zone)
            shape = self.agg_shape_combo.currentData() or "gravel"
            shape_adj_kg = AGGREGATE_SHAPE_ADJUSTMENT_KG.get(shape, 0.0)
            wc = wc + shape_adj_kg

            base = WATER_CONTENT[nmsa]
            delta = (slump - 50.0) / 25.0 * 3.0
            parts = [f"{base:.0f}"]
            if abs(delta) > 0.01:
                parts.append(f"× {1 + delta / 100:.3f} slump")
            if shape_adj_kg != 0:
                parts.append(f"{shape_adj_kg:+.0f} kg shape")
            self.water_content_label.setText(
                f"{self._fmt_water_content(wc)}  ({' '.join(parts)})"
            )
            self._lbl_water.setVisible(True)
            self.water_content_label.setVisible(True)
            self._base_water_content = wc
        elif is_aci:
            from concrete_mix.codes.tables.aci_tables import interpolate_water_content
            slump = self.slump_spin.value()
            air_entrained = self.air_check.isChecked()
            try:
                wc = interpolate_water_content(nmsa, slump, air_entrained=air_entrained)
                air_text = " (air-entrained)" if air_entrained else " (non-air-entrained)"
                self.water_content_label.setText(
                    f"{self._fmt_water_content(wc)}  (ACI Table 5.3.3{air_text})"
                )
                self._lbl_water.setVisible(True)
                self.water_content_label.setVisible(True)
                self._base_water_content = wc
            except Exception:
                self._lbl_water.setVisible(False)
                self.water_content_label.setVisible(False)
                self._base_water_content = 0.0
        elif is_doe:
            from concrete_mix.codes.tables.doe_tables import get_free_water_content
            slump = self.slump_spin.value()
            ca_type = self.ca_type_combo.currentData() or "uncrushed"
            fa_type = self.fa_type_combo.currentData() or "uncrushed"
            try:
                if ca_type != fa_type:
                    w_fine = get_free_water_content(nmsa, fa_type, slump)
                    w_coarse = get_free_water_content(nmsa, ca_type, slump)
                    wc = (2.0 / 3.0) * w_fine + (1.0 / 3.0) * w_coarse
                    self.water_content_label.setText(
                        f"{self._fmt_water_content(wc)}  (BRE 331 Table 3 Note: 2/3 Wf + 1/3 Wc)"
                    )
                else:
                    wc = get_free_water_content(nmsa, ca_type, slump)
                    self.water_content_label.setText(
                        f"{self._fmt_water_content(wc)}  (BRE 331 Table 3)"
                    )
                self._lbl_water.setVisible(True)
                self.water_content_label.setVisible(True)
                self._base_water_content = wc
            except Exception:
                self._lbl_water.setVisible(False)
                self.water_content_label.setVisible(False)
                self._base_water_content = 0.0
        else:
            self._lbl_water.setVisible(False)
            self.water_content_label.setVisible(False)
            self._base_water_content = 0.0
        self._update_reduced_water()

    def _on_nmsa_changed(self) -> None:
        nmsa = self.nmsa_combo.currentData()
        code = self.code_combo.currentData()
        is_is = code == "is10262"

        # Update water content display
        self._update_water_display()

        # Update CA fraction combo — show zone label alongside fraction

        # Update CA fraction combo — show zone label alongside fraction
        self.ca_fraction_combo.clear()
        if is_is and nmsa in CA_VOLUME_FRACTION:
            options = CA_VOLUME_FRACTION[nmsa]
            for zone, frac in options.items():
                self.ca_fraction_combo.addItem(f"Zone {zone} — {frac:.2f}", frac)
            self._lbl_ca_frac.setVisible(True)
            self.ca_fraction_combo.setVisible(True)
            self._lbl_zone.setVisible(False)
            self.grading_combo.setVisible(False)
        else:
            self._lbl_ca_frac.setVisible(False)
            self.ca_fraction_combo.setVisible(False)
            self._lbl_zone.setVisible(is_is)
            self.grading_combo.setVisible(is_is)

        # NMSA change is exactly when the IS zone source swaps; keep a locked
        # zone re-targeted (and disabled) on whichever combo is now visible.
        self._enforce_psd_locks()

    def _update_info_texts(self) -> None:
        """Update all info button texts based on the currently selected standard."""
        code = self.code_combo.currentData()
        for key, btn in self._info_buttons.items():
            texts = self._INFO_TEXTS.get(key)
            if texts and code in texts:
                btn.set_text(texts[code])

    def _update_exposure_wc_display(self) -> None:
        """Show max free W/C ratio from IS 456:2000 Table 5 when exposure is selected."""
        exposure = self.exposure_combo.currentData()
        concrete_type = self.concrete_type_combo.currentData()
        if exposure:
            limits = get_exposure_limits(exposure, concrete_type)
            max_wc = limits["max_wc"]
            self.max_wc_label.setText(str(max_wc))
        else:
            self.max_wc_label.setText("N/A")

    def _update_std_dev_display(self) -> None:
        """Update the DOE Std Deviation display to show the s actually applied.

        BRE 331:1997 Figure 3: n < 20 → 8 MPa (Line A), n ≥ 20 → 4 MPa (Line B).
        For fc ≤ 20 MPa the ramp fc*8/20 or fc*4/20 is used, but structural
        DOE enforces fc ≥ 25 MPa so the plateau always applies. This field is
        display-only — it shows the calculation value, nothing else.
        """
        if not hasattr(self, "std_dev_display"):
            return
        try:
            n = self.n_cubes_spin.value() if hasattr(self, "n_cubes_spin") else 20
            fc = self.strength_spin.value() if hasattr(self, "strength_spin") else 25.0
        except Exception:
            return
        if n < 20:
            s = 8.0 if fc >= 20 else fc * 8.0 / 20.0
            line = "Line A"
        else:
            s = 4.0 if fc >= 20 else fc * 4.0 / 20.0
            line = "Line B"
        up = self.unit_prefs or get_unit_prefs()
        s_disp = up.convert_strength_mpa(s)
        unit = up.strength_unit()
        # Show one decimal; for imperial psi the conversion will be large (e.g., 8 MPa ≈ 1160 psi)
        self.std_dev_display.setText(f"{s_disp:.1f} {unit}  (n={n}, {line}, BRE 331 §4.4)")

    def _on_code_changed(self) -> None:
        code = self.code_combo.currentData()
        is_aci = code == "aci211"
        is_is = code == "is10262"
        is_doe = code == "doe"

        # IS-specific fields in Step 1
        self._lbl_concrete_type.setVisible(is_is)
        self.concrete_type_combo.setVisible(is_is)
        self._lbl_exposure.setVisible(is_is)
        self.exposure_combo.setVisible(is_is)
        self._lbl_max_wc.setVisible(is_is)
        self.max_wc_label.setVisible(is_is)

        # ACI-specific fields in Step 1
        self._lbl_air.setVisible(is_aci)
        self.air_check.setVisible(is_aci)
        self._lbl_sulfate.setVisible(is_aci)
        self.sulfate_combo.setVisible(is_aci)

        # Production Data check is for ACI only (>=30 tests).  For DOE the
        # standard deviation is now derived from the number of test cubes n
        # (structural: n<20 → 8 MPa Line A, n≥20 → 4 MPa Line B).
        if is_aci:
            self.prod_data_check.setText("Has Production Data (\u226530 tests)")
            self.prod_data_check.setVisible(True)
        else:
            self.prod_data_check.setVisible(False)

        # DOE-specific fields in Step 1
        self._lbl_defective_pct.setVisible(is_doe)
        self.defective_pct_spin.setVisible(is_doe)
        self._lbl_n_cubes.setVisible(is_doe)
        self.n_cubes_spin.setVisible(is_doe)
        self._lbl_std_dev.setVisible(is_doe)
        self.std_dev_display.setVisible(is_doe)
        self.std_dev_spin.setVisible(False)
        self._lbl_age.setVisible(is_doe)
        self.age_combo.setVisible(is_doe)
        self._lbl_min_cement.setVisible(is_doe)
        self.min_cement_spin.setVisible(is_doe)
        self._lbl_max_cement.setVisible(is_doe)
        self.max_cement_spin.setVisible(is_doe)
        self._lbl_max_wc_override.setVisible(is_doe)
        self.max_wc_override_spin.setVisible(is_doe)
        if hasattr(self, "doe_structural_label"):
            self.doe_structural_label.setVisible(True)

        # Strength spin: structural assumption requires characteristic strength ≥ 25 MPa for all codes
        self.strength_spin.setMinimum(25.0)
        self.strength_spin.setToolTip(
            "Characteristic compressive strength (fck / f'c / fc).\n"
            "This app assumes structural concrete → characteristic strength ≥ 25 MPa.\n"
            "Values below 25 MPa are not permitted for structural mix design."
        )
        if self.strength_spin.value() < 25.0:
            self.strength_spin.setValue(25.0)

        # Fine aggregate: show FM for ACI, grading zone / CA fraction for IS, % passing 600um & Type for DOE
        self._lbl_fm.setVisible(is_aci)
        self.fm_spin.setVisible(is_aci)
        self._lbl_pct_passing_600um.setVisible(is_doe)
        self.pct_passing_600um_spin.setVisible(is_doe)
        self._lbl_fa_type.setVisible(is_doe)
        self.fa_type_combo.setVisible(is_doe)

        self._on_nmsa_changed()

        # Coarse aggregate controls:
        # - DOE: Coarse Aggregate Type (Uncrushed / Crushed per BRE 331 §1.2.4, Table 2/3)
        # - IS: Aggregate Shape (IS 10262 Table 6)
        # - ACI: Dry-Rodded Bulk Density (ACI Table 5.3.6)
        self._lbl_ca_type.setVisible(is_doe)
        self.ca_type_combo.setVisible(is_doe)
        self._lbl_shape.setVisible(is_is)
        self.agg_shape_combo.setVisible(is_is)
        self._lbl_ca_bulk.setVisible(is_aci)
        self.ca_bulk_spin.setVisible(is_aci)

        # Update cement type combo with Ghana grades + equivalent code
        self.cement_type_combo.blockSignals(True)
        current_data = self.cement_type_combo.currentData()
        self.cement_type_combo.clear()

        if is_aci:
            ghana_types = [
                ("32.5R (Type I)", "GRADE_32_5R"),
                ("42.5R (Type III)", "GRADE_42_5R"),
                ("42.5N (Type I)", "GRADE_42_5N"),
                ("52.5N (Type I)", "GRADE_52_5N"),
            ]
        else:
            ghana_types = [
                ("32.5R (OPC 33)", "GRADE_32_5R"),
                ("42.5R (OPC 43)", "GRADE_42_5R"),
                ("42.5N (OPC 43)", "GRADE_42_5N"),
                ("52.5N (OPC 53)", "GRADE_52_5N"),
            ]

        for label, data in ghana_types:
            self.cement_type_combo.addItem(label, data)

        # Restore previous selection if it exists
        for i in range(self.cement_type_combo.count()):
            if self.cement_type_combo.itemData(i) == current_data:
                self.cement_type_combo.setCurrentIndex(i)
                break
        else:
            # Default to 42.5R
            self.cement_type_combo.setCurrentIndex(1)

        self.cement_type_combo.blockSignals(False)

        # Standard-specific Admixture types & visibility
        self.admix_type_combo.blockSignals(True)
        cur_admix = self.admix_type_combo.currentData()
        self.admix_type_combo.clear()

        if is_is:
            admix_items = [
                ("None", ""),
                ("Superplasticizer / HRWRA (PCE / SNFC / SMFC)", "superplasticizer"),
                ("Plasticizer (Lignosulfonate)", "plasticizer"),
                ("Retarder / Retarding Superplasticizer", "retarder"),
                ("Accelerator", "accelerator"),
                ("Air-Entraining Admixture", "air_entraining"),
            ]
        elif is_aci:
            admix_items = [
                ("None", ""),
                ("Type A — Water-Reducing (min 5%)", "water_reducer"),
                ("Type B — Retarding", "retarder"),
                ("Type C — Accelerating", "accelerator"),
                ("Type D — Water-Reducing & Retarding", "water_reducer_retarder"),
                ("Type E — Water-Reducing & Accelerating", "water_reducer_accelerator"),
                ("Type F — High-Range Water-Reducing / HRWRA (12–40%)", "superplasticizer"),
                ("Type G — High-Range WR & Retarding", "hrwra_retarder"),
                ("Air-Entraining Admixture (ASTM C260)", "air_entraining"),
            ]
        else:  # doe
            admix_items = [
                ("None", ""),
                ("Water-Reducing Admixture (Plasticiser)", "plasticizer"),
                ("High-Range Water-Reducing (Superplasticiser)", "superplasticizer"),
                ("Retarding Water-Reducing Admixture", "retarder"),
                ("Accelerating Water-Reducing Admixture", "accelerator"),
            ]

        for lbl, val in admix_items:
            self.admix_type_combo.addItem(lbl, val)

        for i in range(self.admix_type_combo.count()):
            if self.admix_type_combo.itemData(i) == cur_admix:
                self.admix_type_combo.setCurrentIndex(i)
                break
        else:
            self.admix_type_combo.setCurrentIndex(0)
        self.admix_type_combo.blockSignals(False)

        # Admixture SG visibility: used in IS & ACI absolute volume calculations, not in DOE wet density
        self._lbl_admix_sg.setVisible(is_is or is_aci)
        self.admix_sg_spin.setVisible(is_is or is_aci)

        # Standard-specific SCM types
        self.scm_type_combo.blockSignals(True)
        cur_scm = self.scm_type_combo.currentData()
        self.scm_type_combo.clear()

        if is_is:
            scm_items = [
                ("None", ""),
                ("Fly Ash (IS 3812 Part 1)", "fly_ash"),
                ("GGBFS / Slag (IS 455)", "ggbfs"),
                ("Silica Fume (IS 15388)", "silica_fume"),
                ("Metakaolin (IS 16354)", "metakaolin"),
            ]
        elif is_aci:
            scm_items = [
                ("None", ""),
                ("Fly Ash Class F (ASTM C618)", "fly_ash"),
                ("Fly Ash Class C (ASTM C618)", "fly_ash_c"),
                ("Slag Cement / GGBFS (ASTM C989)", "ggbfs"),
                ("Silica Fume (ASTM C1240)", "silica_fume"),
                ("Metakaolin / Natural Pozzolan (ASTM C618)", "metakaolin"),
            ]
        else:  # doe (BRE 331 Part 3 covers pfa and ggbs)
            scm_items = [
                ("None", ""),
                ("Pulverised-Fuel Ash / pfa (BS 3892 / BS EN 450)", "fly_ash"),
                ("Ground Granulated Blastfurnace Slag / ggbs (BS 6699)", "ggbfs"),
            ]

        for lbl, val in scm_items:
            self.scm_type_combo.addItem(lbl, val)

        for i in range(self.scm_type_combo.count()):
            if self.scm_type_combo.itemData(i) == cur_scm:
                self.scm_type_combo.setCurrentIndex(i)
                break
        else:
            self.scm_type_combo.setCurrentIndex(0)
        self.scm_type_combo.blockSignals(False)

        # Update exposure W/C display
        self._update_exposure_wc_display()

        # Update all info button texts for the selected standard
        self._update_info_texts()

        # DOE Std Deviation display — show the s actually applied (n<20→8, n≥20→4)
        self._update_std_dev_display()

        # Apply the mode-specific enabled/disabled field matrix after the
        # standard-specific visibility rules have been refreshed.
        self._apply_mode_state()

    def _update_exposure_wc_display(self) -> None:
        """Update the max free W/C ratio label based on exposure class and concrete type."""
        code = self.code_combo.currentData()
        if code != "is10262":
            return
        exposure = self.exposure_combo.currentData()
        concrete_type = self.concrete_type_combo.currentData()
        if not exposure:
            self.max_wc_label.setText("—")
            return
        try:
            from concrete_mix.codes.tables.is_tables import get_exposure_limits

            limits = get_exposure_limits(exposure, concrete_type)
            wc = limits["max_wc"]
            min_grade = limits.get("min_grade", "")
            ct_label = "Reinforced" if concrete_type == "reinforced" else "Plain"
            exp_label = exposure.replace("_", " ").title()
            grade_text = f"  |  Min Grade: {min_grade}" if min_grade else ""
            self.max_wc_label.setText(
                f"W/C ≤ {wc:.2f}  |  Min Grade: {min_grade or '—'}  ({ct_label} / {exp_label})"
            )
        except (KeyError, ValueError):
            self.max_wc_label.setText("—")

    # ── Calculation ──────────────────────────────────────────────────

    def _on_calculate(self) -> None:
        if self._worker.isRunning():
            return
        if self._is_target_strength_mode():
            self._calculate_target_strength()
            return

        self.calc_btn.setEnabled(False)
        self.mode_combo.setEnabled(False)
        self.calc_btn.setText("  Calculating...")
        self._result_panel.clear()
        self._target_strength_panel.clear()

        try:
            kwargs = self._build_kwargs()
        except Exception as e:
            QMessageBox.warning(self, "Input Error", str(e))
            self.calc_btn.setEnabled(True)
            self.mode_combo.setEnabled(True)
            self._update_calculate_button()
            return

        self._worker.set_params(kwargs)
        self._last_input_params = kwargs
        self._worker.start()

    def _calculate_target_strength(self) -> None:
        """Calculate and display only the selected standard's target strength."""
        self.calc_btn.setEnabled(False)
        self.mode_combo.setEnabled(False)
        self.calc_btn.setText("  Calculating...")
        self._result_panel.clear()
        self._target_strength_panel.clear()

        try:
            code = self.code_combo.currentData()
            num_test_cubes = self.n_cubes_spin.value() if code == "doe" else None
            result = calculate_target_strength(
                code,
                self.strength_spin.value(),
                has_production_data=self.prod_data_check.isChecked(),
                defective_percent=self.defective_pct_spin.value(),
                num_test_cubes=num_test_cubes,
            )
        except Exception as e:
            QMessageBox.warning(self, "Input Error", str(e))
            self.calc_btn.setEnabled(True)
            self.mode_combo.setEnabled(True)
            self._update_calculate_button()
            return

        self._last_target_result = result
        self._target_strength_panel.display_result(result)
        self.calc_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self._update_calculate_button()
        if hasattr(self.window(), "status_bar"):
            up = self.unit_prefs or get_unit_prefs()
            target = up.convert_strength_mpa(result.target_mean_strength_mpa)
            self.window().status_bar.showMessage(
                f"Done — {result.standard_name}  |  Target strength: "
                f"{target:.1f} {up.strength_unit()}"
            )

    def _on_clear(self) -> None:
        """Clear results and reset the form to the default mix-design mode."""
        self._result_panel.clear()
        self._target_strength_panel.clear()
        self._last_result = None
        self._last_target_result = None
        self.mode_combo.setEnabled(True)
        self.mode_combo.setCurrentIndex(self.mode_combo.findData("mix_design"))

        # Reset inputs
        self.code_combo.setCurrentIndex(self.code_combo.findData("is10262"))
        self.concrete_type_combo.setCurrentIndex(
            self.concrete_type_combo.findData("reinforced")
        )
        self.exposure_combo.setCurrentIndex(0)
        self.max_wc_label.setText("—")
        self.air_check.setChecked(False)
        self.sulfate_combo.setCurrentIndex(self.sulfate_combo.findData("S0"))
        self.prod_data_check.setChecked(True)

        self.defective_pct_spin.setValue(5.0)
        if hasattr(self, "n_cubes_spin"):
            self.n_cubes_spin.setValue(20)
        self.std_dev_spin.setValue(0.0)  # hidden, always Auto for DOE display-only
        if hasattr(self, "std_dev_display"):
            self._update_std_dev_display()
        self.age_combo.setCurrentIndex(self.age_combo.findData(28))
        self.min_cement_spin.setValue(0.0)
        self.max_cement_spin.setValue(0.0)
        self.max_wc_override_spin.setValue(0.00)

        self.strength_spin.setValue(25.0)
        self.slump_spin.setValue(75.0)
        self.nmsa_combo.setCurrentIndex(self.nmsa_combo.findData(20))
        self.volume_spin.setValue(1.0)

        self.cement_type_combo.setCurrentIndex(1)  # Default is 42.5R
        self.cement_sg_spin.setValue(3.15)

        self.fa_sg_spin.setValue(2.65)
        self.fm_spin.setValue(2.70)
        self.grading_combo.setCurrentIndex(self.grading_combo.findData("II"))
        self.pct_passing_600um_spin.setValue(60.0)
        self.fa_abs_spin.setValue(1.0)
        self.fa_moist_spin.setValue(0.0)
        self.ca_sg_spin.setValue(2.70)
        self.ca_abs_spin.setValue(0.5)
        self.ca_moist_spin.setValue(0.0)
        self.ca_bulk_spin.setValue(1600.0)
        self.agg_shape_combo.setCurrentIndex(self.agg_shape_combo.findData("angular"))
        self.ca_type_combo.setCurrentIndex(self.ca_type_combo.findData("uncrushed"))
        self.fa_type_combo.setCurrentIndex(self.fa_type_combo.findData("uncrushed"))

        self.scm_type_combo.setCurrentIndex(self.scm_type_combo.findData("fly_ash"))
        self.scm_pct_spin.setValue(0.0)
        self.scm_sg_spin.setValue(2.20)

        self.admix_type_combo.setCurrentIndex(0)  # None
        self.admix_dosage_spin.setValue(1.0)
        self.admix_spin.setValue(0.0)
        self.admix_sg_spin.setValue(1.15)

        # Trigger visibility update
        self._on_code_changed()

        if (
            hasattr(self.window(), "status_bar")
            and self.window().status_bar is not None
        ):
            self.window().status_bar.showMessage("Interface cleared", 3000)

    def on_unit_changed(self) -> None:
        """React to unit preference changes.

        Input spinboxes are UnitSpinBox instances that re-derive their own
        display from the stored metric value, so only the derived preview
        labels need refreshing here.
        """
        if self.unit_prefs is None:
            return
        self._refresh_slump_label()
        self._update_water_display()
        self._update_std_dev_display()
        if hasattr(self, "_target_strength_panel"):
            self._target_strength_panel.unit_prefs = self.unit_prefs
            self._target_strength_panel.on_unit_changed()

    def _fmt_water_content(self, kg_m3: float) -> str:
        """Format a per-m³ water content in the active unit system.

        Metric shows kg/m³ (IS 10262 Table 4 basis); imperial shows lb/yd³
        (ACI 211.1 Table 6.3.3 basis).
        """
        up = self.unit_prefs or get_unit_prefs()
        if up.is_imperial():
            return f"{kg_m3 * 1.68555:.0f} lb/yd\u00b3"
        return f"{kg_m3:.1f} kg/m\u00b3"

    def _build_kwargs(self) -> dict[str, Any]:
        """Collect all inputs from the form as a dictionary for calculation."""
        code = self.code_combo.currentData()
        cement_type_ghana = self.cement_type_combo.currentData()
        cement_type = map_cement_type(cement_type_ghana, code)
        scm_type = self.scm_type_combo.currentData() or "fly_ash"
        scm_pct = self.scm_pct_spin.value()
        ca_fraction = self.ca_fraction_combo.currentData()
        if ca_fraction is not None and ca_fraction != "":
            try:
                ca_fraction = float(ca_fraction)
            except (ValueError, TypeError):
                ca_fraction = None
        else:
            ca_fraction = None

        nmsa = self.nmsa_combo.currentData()
        if nmsa is not None and nmsa != "":
            try:
                nmsa = int(nmsa)
            except (ValueError, TypeError):
                nmsa = 20
        else:
            nmsa = 20

        grading = self.grading_combo.currentData()
        if not grading:
            grading = "II"

        kwargs: dict[str, Any] = {
            "code": code,
            "target_strength_mpa": self.strength_spin.value(),
            "characteristic_strength_mpa": self.strength_spin.value(),
            "slump_mm": self.slump_spin.value(),
            "nmsa": nmsa,
            "cement_type": cement_type,
            "cement_sg": self.cement_sg_spin.value(),
            "fine_agg_sg": self.fa_sg_spin.value(),
            "fine_agg_fm": self.fm_spin.value(),
            "fine_agg_grading_zone": grading,
            "fine_agg_absorption": self.fa_abs_spin.value(),
            "fine_agg_moisture": self.fa_moist_spin.value(),
            "coarse_agg_sg": self.ca_sg_spin.value(),
            "coarse_agg_absorption": self.ca_abs_spin.value(),
            "coarse_agg_moisture": self.ca_moist_spin.value(),
            "coarse_agg_bulk_density": self.ca_bulk_spin.value(),
            "air_entrained": self.air_check.isChecked(),
            "exposure_class": self.exposure_combo.currentData() or None,
            "scm_replacement_percent": scm_pct if scm_pct > 0 else 0.0,
            "scm_type": scm_type if scm_pct > 0 else "fly_ash",
            "scm_sg": self.scm_sg_spin.value(),
            "admixture_type": self.admix_type_combo.currentData() or "",
            "admixture_dosage": self.admix_dosage_spin.value(),
            "admixture_water_reduction": self.admix_spin.value(),
            "admixture_sg": self.admix_sg_spin.value(),
            "volume_m3": self.volume_spin.value(),
        }

        if code == "aci211":
            kwargs["has_production_data"] = self.prod_data_check.isChecked()
            kwargs["sulfate_exposure_class"] = self.sulfate_combo.currentData()
            kwargs["coarse_agg_bulk_density"] = self.ca_bulk_spin.value()
        elif code == "is10262":
            kwargs["aggregate_shape"] = self.agg_shape_combo.currentData()
            kwargs["ca_volume_fraction_override"] = ca_fraction
            kwargs["characteristic_strength_mpa"] = self.strength_spin.value()
            kwargs["concrete_type"] = self.concrete_type_combo.currentData()
        elif code == "doe":
            kwargs["aggregate_shape"] = self.ca_type_combo.currentData()
            kwargs["coarse_agg_type"] = self.ca_type_combo.currentData()
            kwargs["fine_agg_shape"] = self.fa_type_combo.currentData()
            kwargs["fine_agg_type"] = self.fa_type_combo.currentData()
            # DOE structural — ask for number of test cubes n
            # n < 20 → s = 8 MPa (Line A), n ≥ 20 → s = 4 MPa (Line B) per BRE 331 §4.4
            n_cubes = self.n_cubes_spin.value() if hasattr(self, "n_cubes_spin") else 20
            kwargs["num_test_cubes"] = int(n_cubes)
            kwargs["n_cubes"] = int(n_cubes)
            # Keep has_production_data for backwards compat (derived from n)
            kwargs["has_production_data"] = n_cubes >= 20
            kwargs["defective_percent"] = self.defective_pct_spin.value()
            # Std deviation is display-only for DOE: shows the s actually applied
            # (n<20→8 MPa Line A, n≥20→4 MPa Line B). No manual override — engine derives s from n.
            kwargs["std_deviation"] = None
            kwargs["age_days"] = self.age_combo.currentData()
            min_cement = self.min_cement_spin.value()
            kwargs["min_cement_kg"] = min_cement if min_cement > 0.0 else None
            max_cement = self.max_cement_spin.value()
            kwargs["max_cement_kg"] = max_cement if max_cement > 0.0 else None
            max_wc = self.max_wc_override_spin.value()
            kwargs["w_c_ratio"] = max_wc if max_wc > 0.0 else None
            kwargs["fine_agg_pct_passing_600um"] = self.pct_passing_600um_spin.value()

        return kwargs

    # ── PSD → Mix Design handoff ─────────────────────────────────────

    def _on_psd_apply(self, payload: dict) -> None:
        """Fill mix-design inputs from a PSD result and lock them.

        Each parameter fed here is the sieve-analysis-derived value a
        supported standard consumes (per AGENTS.md):
          - ACI 211.1-22 §4.3.5 fineness modulus → Table 5.3.6.
          - IS 10262:2019 Clause 5.4 / IS 383 Table 9 grading zone → Table 5.
          - BRE 331:1997 §1.2.5 % passing 600 µm → Figure 6.
          - Coarse PSD → NMSA (ASTM C33 Table 2 / IS 383 Table 7).
          - An ASTM C33 fine PSD additionally switches the design standard
            to ACI 211.1 before its FM is applied — FM is consumed only by
            the ACI engine (§4.3.5 → Table 5.3.6).

        Every affected field is recorded in ``self._psd_locked`` and disabled
        so it cannot be overridden in the form. Re-applying a new PSD updates
        the locked value; only the PSD Clear button (``clear_all_inputs``)
        unlocks and restores the snapshot.
        """
        kind = payload.get("aggregate_kind", "fine")
        applied: list[str] = []
        warnings = list(payload.get("warnings", []))

        if kind == "coarse":
            nominal = payload.get("nominal_size_mm")
            if nominal is not None:
                self._lock_nmsa(nominal)
                applied.append(
                    f"Nominal maximum size set to {nominal} mm "
                    f"(band reference: {payload.get('band_standard', '—')})"
                )
            else:
                warnings.append(
                    "Coarse-PSD conformance guides NMSA choice; no reference "
                    "band was selected, so no input was changed."
                )
        else:
            fm = payload.get("fineness_modulus")
            if fm is not None:
                # Fineness modulus is an ACI 211.1-22 §4.3.5 parameter,
                # consumed with NMSA via Table 5.3.6; the IS and DOE engines
                # never use it and keep the FM row hidden. An ASTM C33
                # grading therefore implies the ACI engine — switch the
                # design standard first so the transferred value lands in
                # a visible field that actually consumes it.
                switched_to_aci = False
                if (
                    payload.get("band_standard") == "astm_c33"
                    and self.code_combo.currentData() != "aci211"
                ):
                    aci_idx = self.code_combo.findData("aci211")
                    if aci_idx >= 0:
                        self.code_combo.setCurrentIndex(aci_idx)
                        switched_to_aci = True
                self._set_field("fm", self.fm_spin, round(float(fm), 2))
                if switched_to_aci:
                    applied.append(
                        "Design standard switched to ACI 211.1 — fineness "
                        "modulus is used by ACI (§4.3.5 → Table 5.3.6), "
                        "not by IS or DOE"
                    )
                applied.append(
                    f"Fineness Modulus = {fm:.2f} (ACI 211.1-22 §4.3.5; used "
                    "with NMSA in Table 5.3.6)"
                )
            zone = payload.get("grading_zone")
            if zone is not None:
                self._lock_zone(zone)
                applied.append(
                    f"Grading Zone {zone} (IS 383 Table 9; keys IS 10262:"
                    "2019 Table 5 CA volume fraction)"
                )
            p600 = payload.get("pct_passing_600um")
            if p600 is not None:
                self._set_field("p600", self.pct_passing_600um_spin,
                                round(float(p600), 1))
                applied.append(
                    f"FA passing 600 µm = {p600:.1f}% (BRE 331:1997 §1.2.5; "
                    "used by Figure 6)"
                )

        if not applied and not warnings:
            QMessageBox.warning(
                self,
                "Use in Mix Design",
                "This sieve analysis did not yield any parameter used by the "
                "selected standard.",
            )
            return

        lines = [
            "Sieve analysis results transferred and locked in the Mix "
            "Design form (fields stay disabled until cleared):",
            "",
        ]
        lines += [f"• {a}" for a in applied]
        if warnings:
            lines += ["", "Not determined from this analysis:"]
            lines += [f"• {w}" for w in warnings]
        if not payload.get("all_conform", True) and kind != "coarse":
            lines += [
                "",
                "⚠ Some sieves fall outside the selected band — see the PSD "
                "tab's suggested adjustments before relying on this grading.",
            ]
        QMessageBox.information(self, "Use in Mix Design", "\n".join(lines))

        if kind == "fine":
            self._left_tabs.setCurrentIndex(self._mixdesign_idx)

    def _on_psd_inputs_cleared(self) -> None:
        """Unlock and restore mix-design fields fed from a PSD result."""
        for key in list(self._psd_locked):
            self._unlock_field(key)
        self._psd_locked.clear()
        self._psd_snapshot.clear()

    # ── Lock primitives ────────────────────────────────────────────

    def _set_field(self, key: str, widget, value) -> None:
        """Snapshot, set, then disable a spin-type PSD-fed field."""
        if key not in self._psd_snapshot:
            self._psd_snapshot[key] = widget.value()
        widget.setValue(value)
        widget.setEnabled(False)
        self._psd_locked.add(key)

    def _lock_nmsa(self, nominal: int) -> None:
        """Lock NMSA to a nominal size and disable the combo."""
        for i in range(self.nmsa_combo.count()):
            if self.nmsa_combo.itemData(i) == nominal:
                if "nmsa" not in self._psd_snapshot:
                    self._psd_snapshot["nmsa"] = self.nmsa_combo.currentIndex()
                self.nmsa_combo.setCurrentIndex(i)
                self.nmsa_combo.setEnabled(False)
                self._psd_locked.add("nmsa")
                break

    def _lock_zone(self, zone: str) -> None:
        """Lock the grading-zone source active for the current standard.

        IS mode expresses the zone through the CA-fraction combo (Table 5
        'Zone X — frac'), from which ``_build_kwargs`` reverse-derives the
        zone. Non-IS modes use the plain Grading Zone combo. Snapshot both
        so Clear can restore either. The source is detected by code and
        combo content, not ``isVisible()`` (which is False for widgets in a
        stack whose page is not the active one).
        """
        self._psd_zone_value = zone
        if "zone" not in self._psd_snapshot:
            self._psd_snapshot["zone"] = (
                self.grading_combo.currentIndex(),
                self.ca_fraction_combo.currentIndex(),
            )
        self._psd_locked.add("zone")

        use_ca = (
            self.code_combo.currentData() == "is10262"
            and self.ca_fraction_combo.count() > 0
        )
        if use_ca:
            nmsa = self.nmsa_combo.currentData()
            target = CA_VOLUME_FRACTION.get(nmsa, {}).get(zone)
            for i in range(self.ca_fraction_combo.count()):
                frac = self.ca_fraction_combo.itemData(i)
                if isinstance(frac, float) and target is not None and \
                        abs(frac - target) < 1e-9:
                    self.ca_fraction_combo.setCurrentIndex(i)
                    break
            self.ca_fraction_combo.setEnabled(False)
        else:
            idx = self.grading_combo.findData(zone)
            if idx >= 0:
                self.grading_combo.setCurrentIndex(idx)
            self.grading_combo.setEnabled(False)

    def _unlock_field(self, key: str) -> None:
        """Re-enable a locked field and restore its snapshot default."""
        if key == "zone":
            (g_idx, c_idx) = self._psd_snapshot.get(
                "zone", (0, 0)
            )
            self.grading_combo.setEnabled(True)
            self.ca_fraction_combo.setEnabled(True)
            self.grading_combo.setCurrentIndex(g_idx)
            if self.ca_fraction_combo.count():
                self.ca_fraction_combo.setCurrentIndex(c_idx)
            return
        widgets = {"fm": self.fm_spin, "p600": self.pct_passing_600um_spin,
                   "nmsa": self.nmsa_combo}
        widget = widgets.get(key)
        if widget is None:
            return
        widget.setEnabled(True)
        if key in self._psd_snapshot:
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(self._psd_snapshot[key])
            else:
                widget.setValue(self._psd_snapshot[key])

    def _enforce_psd_locks(self) -> None:
        """Re-apply disabled state after standard/mode switches rebuild widgets.

        ``_apply_mode_state`` and ``_on_nmsa_changed`` re-enable form rows;
        this re-disables every currently locked PSD-fed field and, for the
        zone, re-targets whichever combo is the active zone source.
        """
        if not hasattr(self, "fm_spin"):
            return
        if "fm" in self._psd_locked:
            self.fm_spin.setEnabled(False)
        if "p600" in self._psd_locked:
            self.pct_passing_600um_spin.setEnabled(False)
        if "nmsa" in self._psd_locked:
            self.nmsa_combo.setEnabled(False)
        if "zone" in self._psd_locked:
            if (
                self.code_combo.currentData() == "is10262"
                and self.ca_fraction_combo.count() > 0
            ):
                self.ca_fraction_combo.setEnabled(False)
            else:
                self.grading_combo.setEnabled(False)

    def _on_result(self, result: MixDesignResult) -> None:
        self._last_result = result
        self._last_target_result = None
        self._result_panel.display_result(result)
        self._target_strength_panel.clear()
        self.calc_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self._update_calculate_button()
        if hasattr(self.window(), "status_bar"):
            up = self.unit_prefs or get_unit_prefs()
            self.window().status_bar.showMessage(
                f"Done \u2014 {result.code_used}  |  "
                f"Cement: {up.convert_mass_kg(result.cement_kg):.1f} {up.mass_unit()}  |  "
                f"W/C: {result.w_c_ratio:.3f}  |  "
                f"f'cr: {up.convert_strength_mpa(result.target_mean_strength_mpa):.1f} "
                f"{up.strength_unit()}"
            )
        # Auto-save to history
        self._auto_save_history(result)

    def _on_error(self, msg: str) -> None:
        self.calc_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self._update_calculate_button()
        QMessageBox.critical(self, "Calculation Error", msg)

    # ── History ──────────────────────────────────────────────────────

    _history_db = None  # Set by MainWindow

    def _auto_save_history(self, result: MixDesignResult) -> None:
        """Auto-save mix design result to history DB."""
        if self._history_db is None:
            return
        try:
            inp = getattr(result, "_input", None)
            if inp is not None:
                self._last_mix_input = inp
                code_name = (
                    "IS 10262"
                    if inp.code == "is10262"
                    else ("ACI 211" if inp.code == "aci211" else "DOE")
                )
                name = f"Mix {code_name} - {result.target_mean_strength_mpa:.1f} MPa"
                self._history_db.save_mix_design(inp, result, name=name)
        except Exception:
            pass  # Don't break the UI for history failures

    def load_from_history(self, calc_id: int) -> None:
        """Load a mix design record from history into this tab."""
        if self._history_db is None:
            return
        from history.serializers import deserialize_mix_result
        import json

        rec = self._history_db.get_calculation(calc_id)
        if rec is None:
            return
        result = deserialize_mix_result(json.loads(rec["result_json"]))
        self._last_result = result
        self._result_panel.display_result(result)

    # ── Export ────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._last_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "mix_design.csv", "CSV (*.csv)"
        )
        if path:
            content = export_to_csv(self._last_result)
            with open(path, "w", newline="") as f:
                f.write(content)
            self.window().status_bar.showMessage(f"Exported to {path}", 5000)

    def _generate_mix_report_html(self) -> str:
        """Generate HTML report for concrete mix design preview.

        Uses only inline CSS styles compatible with QTextBrowser.
        No external CSS, JS, fonts, or icon libraries.
        """
        result = self._last_result
        if not result:
            return ""

        params = self._last_input_params or {}
        is_aci = params.get("code") == "aci211"
        code_label = "ACI PRC-211.1-22 (American)" if is_aci else "IS 10262:2019 (Indian)"

        vol = result.volume_m3

        # ── Unit conversions for display ──
        up = self.unit_prefs or get_unit_prefs()
        vol_d = up.convert_volume_m3(vol)
        vu = up.volume_unit()
        mu = up.mass_unit()
        su = up.strength_unit()
        # Per-volume content unit: kg/m³ (IS basis) ↔ lb/yd³ (ACI basis)
        pvu = up.mass_per_volume_unit()

        def per_vol(kg_m3: float) -> float:
            return kg_m3 * 1.68555 if up.is_imperial() else kg_m3

        # ── Colour palette (reused throughout) ──
        PRIMARY = "#00288e"
        HEADER_BG = "#e8eef8"
        ROW_ALT = "#f0f4ff"
        BORDER = "#c4c5d5"
        TEXT = "#1a1b22"
        TEXT_DIM = "#444653"
        WHITE = "#ffffff"

        # ── Helper: section heading ──
        def section_heading(number: int, title: str) -> str:
            return (
                f'<div style="margin:0 0 10px 0; padding-bottom:6px; '
                f'border-bottom:2px solid {PRIMARY};">'
                f'<span style="display:inline-block; background:{PRIMARY}; color:{WHITE}; '
                f"font-weight:700; font-size:11px; padding:2px 7px; margin-right:8px; "
                f'vertical-align:middle;">{number}</span>'
                f'<span style="font-size:13px; font-weight:700; color:{TEXT_DIM}; '
                f'text-transform:uppercase; letter-spacing:0.08em; vertical-align:middle;">'
                f"{title}</span></div>"
            )

        # ── Helper: parameter cell (label + value) ──
        def param_cell(label: str, value: str, highlight: bool = False) -> str:
            val_color = PRIMARY if highlight else TEXT
            return (
                f'<td style="padding:8px 10px; vertical-align:top; '
                f'border-bottom:1px solid {BORDER}; width:33%;">'
                f'<div style="font-size:10px; font-weight:600; color:{TEXT_DIM}; '
                f'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:3px;">'
                f"{label}</div>"
                f'<div style="font-size:14px; font-weight:500; color:{val_color};">'
                f"{value}</div></td>"
            )

        # ── Helper: material card ──
        def material_card(label: str, value: str, unit: str) -> str:
            return (
                f'<td style="width:25%; padding:0; vertical-align:top;">'
                f'<div style="border:1px solid {BORDER}; border-left:4px solid {PRIMARY}; '
                f'padding:12px; background:{WHITE}; margin:0 6px;">'
                f'<div style="font-size:10px; font-weight:600; color:{TEXT_DIM}; '
                f'text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;">'
                f"{label}</div>"
                f'<div style="font-size:16px; font-weight:500; color:{PRIMARY}; margin-bottom:2px;">'
                f"{value}</div>"
                f'<div style="font-size:10px; font-weight:600; color:{TEXT_DIM}; text-align:right;">'
                f"{unit}</div>"
                f"</div></td>"
            )

        # ── Build steps rows ──
        steps_rows = ""
        for i, step in enumerate(result.steps):
            bg = f" background:{ROW_ALT};" if i % 2 == 0 else ""
            steps_rows += (
                f'<tr style="{bg}">'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; '
                f'font-weight:600; color:{TEXT_DIM}; width:50px; text-align:center;">'
                f"{step.step_number:g}</td>"
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; '
                f'color:{TEXT}; font-size:13px;">{step.description}</td>'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; '
                f'color:{TEXT_DIM}; font-style:italic; font-size:12px;">{step.formula}</td>'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; '
                f'text-align:right; font-weight:500; color:{TEXT}; white-space:nowrap;">'
                f"{step.result:.2f} {step.unit}</td>"
                f"</tr>"
            )

        # ── SCM section (only if present) ──
        scm_card = ""
        if result.scm_kg > 0:
            scm_card = material_card(
                "SCM (Suppl.)", f"{per_vol(result.scm_kg):.1f}", pvu
            )

        # ── Batch quantities (scaled) ──
        factor = vol  # result already stores per-m3; multiply by volume
        batch_cement = result.cement_kg * factor
        batch_water = result.water_kg * factor
        batch_fine = result.fine_aggregate_kg * factor
        batch_coarse = result.coarse_aggregate_kg * factor
        batch_scm = result.scm_kg * factor

        # ── Mix ratio ──
        ratio = result.mix_ratio
        ratio_str = result.mix_ratio_string

        # ── Warnings ──
        warnings_html = ""
        if result.warnings:
            warn_items = ""
            for w in result.warnings:
                warn_items += (
                    f'<li style="padding:6px 0; border-bottom:1px solid {BORDER}; '
                    f'color:{TEXT}; font-size:13px;">'
                    f'<span style="color:#b45309; font-weight:700; margin-right:6px;">&#9888;</span>'
                    f"{w}</li>"
                )
            warnings_html = (
                f"{section_heading(6, 'Warnings')}"
                f'<ul style="list-style:none; margin:0 0 20px 0; padding:0; '
                f'border:1px solid {BORDER}; background:{ROW_ALT};">{warn_items}</ul>'
            )

        # ── Glossary ──
        glossary_items = [
            (
                "W/C Ratio",
                "Water-to-Cementitious materials ratio by mass. Lower values generally produce stronger, more durable concrete.",
            ),
            (
                "NMSA",
                "Nominal Maximum Size of Aggregate. The largest aggregate size that will pass through a standard sieve and be retained on a smaller sieve.",
            ),
            (
                "Slump",
                "A measure of concrete workability/consistency, determined by the slump test (ASTM C143 / IS 1199).",
            ),
            (
                "Target Mean Strength",
                "The average compressive strength required so that a specified percentage of test results will meet or exceed the characteristic strength.",
            ),
            (
                "Fine Aggregate",
                "Natural sand or manufactured sand passing the 4.75 mm sieve (IS) or No. 4 sieve (ASTM).",
            ),
            (
                "Coarse Aggregate",
                "Gravel or crushed stone retained on the 4.75 mm sieve (IS) or No. 4 sieve (ASTM).",
            ),
            (
                "SCM",
                "Supplementary Cementitious Material \u2014 e.g., fly ash, ground granulated blast-furnace slag (GGBS), silica fume.",
            ),
            (
                "Air Content",
                "Volume of entrapped or entrained air in the concrete mix, expressed as a percentage of total volume.",
            ),
            (
                "Absolute Volume Method",
                "Proportioning method where the volume of each ingredient is computed from its mass and specific gravity, and the sum must equal the unit volume of concrete.",
            ),
        ]
        glossary_rows = ""
        for i, (term, definition) in enumerate(glossary_items):
            bg = f" background:{ROW_ALT};" if i % 2 == 0 else ""
            glossary_rows += (
                f'<tr style="{bg}">'
                f'<td style="padding:6px 10px; border-bottom:1px solid {BORDER}; '
                f'font-weight:600; color:{PRIMARY}; font-size:12px; width:160px; vertical-align:top;">'
                f"{term}</td>"
                f'<td style="padding:6px 10px; border-bottom:1px solid {BORDER}; '
                f'color:{TEXT_DIM}; font-size:12px;">{definition}</td>'
                f"</tr>"
            )

        # Formatted before the f-string blocks below: Python < 3.12 forbids
        # reusing the outer f-string delimiter inside an expression part.
        nmsa_raw = params.get("nmsa")
        nmsa_val = (
            "N/A" if nmsa_raw is None
            else f"{up.convert_length_mm(nmsa_raw):.0f} {up.length_unit()}"
        )
        slump_raw = params.get("slump_mm")
        slump_val = (
            "N/A" if slump_raw is None
            else f"{up.convert_length_mm(slump_raw):.0f} {up.length_unit()}"
        )

        water_pvu = pvu if up.is_imperial() else "liters/m³"

        # ── Assemble full HTML ──
        html = (
            "<!DOCTYPE html>"
            '<html lang="en"><head><meta charset="utf-8"/>'
            "<title>Concrete Mix Design Report</title></head>"
            f'<body style="margin:0; padding:20px; background:{WHITE}; '
            f"color:{TEXT}; font-family:Arial, Helvetica, sans-serif; "
            f'font-size:14px; line-height:1.5;">'
            # ── Main container ──
            f'<div style="max-width:800px; margin:0 auto; padding:30px; '
            f'border:1px solid {BORDER}; background:{WHITE};">'
            # ── Document header ──
            f'<table style="width:100%; border-collapse:collapse; margin-bottom:24px; '
            f'padding-bottom:12px; border-bottom:2px solid {PRIMARY};"><tr>'
            f'<td style="vertical-align:top;">'
            f'<div style="font-size:22px; font-weight:700; color:{PRIMARY}; text-transform:uppercase;">'
            f"CivilQntify</div>"
            f'<div style="font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f'text-transform:uppercase; letter-spacing:0.05em;">'
            f"Technical Systems &amp; Engineering</div>"
            f"</td>"
            f'<td style="text-align:right; vertical-align:top;">'
            f'<div style="font-size:18px; font-weight:600; color:{TEXT};">CONCRETE MIX DESIGN REPORT</div>'
            f'<div style="font-size:12px; color:{TEXT_DIM}; margin-top:4px;">'
            f"<b>Project:</b> {params.get('project_name', 'N/A')}</div>"
            f'<div style="font-size:12px; color:{TEXT_DIM};">'
            f"<b>Date:</b> {params.get('date', 'N/A')}</div>"
            f"</td></tr></table>"
            # ── Section 1: Design Parameters ──
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(1, 'Design Parameters')}"
            f'<table style="width:100%; border-collapse:collapse; border:1px solid {BORDER}; '
            f'background:{WHITE};"><tr>'
            f"{param_cell('Design Code', code_label)}"
            f"{param_cell('Target Strength', f'{up.convert_strength_mpa(result.target_mean_strength_mpa):.1f} {su}', highlight=True)}"
            f"{param_cell('W/C Ratio', f'{result.w_c_ratio:.3f}')}"
            f"</tr><tr>"
            f"{param_cell('Max Agg. Size (NMSA)', nmsa_val)}"
            f"{param_cell('Slump', slump_val)}"
            f"{param_cell('Air Content', f'{result.air_volume_percent:.1f}%')}"
            f"</tr><tr>"
            f"{param_cell('Volume', f'{vol_d:.2f} {vu}')}"
            f"{param_cell('Total Cementitious', f'{per_vol(result.total_cementitious_kg):.1f} {pvu}')}"
            f"{param_cell('', '')}"
            f"</tr></table></div>"
            # ── Section 2: Material Quantities per volume ──
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(2, f'Material Quantities per {vu}')}"
            f'<table style="width:100%; border-collapse:collapse;"><tr>'
            f"{material_card('Cement', f'{per_vol(result.cement_kg):.1f}', pvu)}"
            f"{material_card('Water', f'{per_vol(result.water_kg):.1f}', water_pvu)}"
            f"{material_card('Fine Aggregate', f'{per_vol(result.fine_aggregate_kg):.1f}', pvu)}"
            f"{material_card('Coarse Aggregate', f'{per_vol(result.coarse_aggregate_kg):.1f}', pvu)}"
            f"</tr></table>"
        )

        # Add SCM row if applicable
        if scm_card:
            html += (
                f'<table style="width:100%; border-collapse:collapse; margin-top:6px;"><tr>'
                f"{scm_card}"
                f'<td style="width:75%;"></td>'
                f"</tr></table>"
            )
        html += "</div>"

        # ── Section 3: Mix Ratio ──
        ratio_detail = f"{ratio['cement']} : {ratio['fine_aggregate']} : {ratio['coarse_aggregate']}"

        html += (
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(3, 'Mix Ratio')}"
            f'<div style="border:1px solid {BORDER}; padding:16px; background:{ROW_ALT}; text-align:center;">'
            f'<div style="font-size:20px; font-weight:600; color:{PRIMARY}; margin-bottom:4px;">'
            f"{ratio_detail} <span style=\"color:#6b7280;\">({result.w_c_ratio:.3f})</span></div>"
            f'<div style="font-size:11px; color:{TEXT_DIM}; margin-bottom:8px;">'
            f"(Cement : Fine Aggregate : Coarse Aggregate &mdash; by mass)</div>"
            f"</div></div>"
        )

        # ── Section 4: Calculation Steps ──
        html += (
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(4, 'Calculation Steps')}"
            f'<table style="width:100%; border-collapse:collapse; border:1px solid {BORDER};">'
            f'<thead><tr style="background:{HEADER_BG};">'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f"text-transform:uppercase; letter-spacing:0.05em; text-align:left; "
            f'border-bottom:2px solid {BORDER}; width:50px;">Step</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f"text-transform:uppercase; letter-spacing:0.05em; text-align:left; "
            f'border-bottom:2px solid {BORDER};">Description</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f"text-transform:uppercase; letter-spacing:0.05em; text-align:left; "
            f'border-bottom:2px solid {BORDER};">Formula</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f"text-transform:uppercase; letter-spacing:0.05em; text-align:right; "
            f'border-bottom:2px solid {BORDER};">Result</th>'
            f"</tr></thead>"
            f"<tbody>{steps_rows}</tbody></table></div>"
        )

        # ── Section 5: Batch Quantities ──
        html += (
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(5, f'Batch Quantities for {vol_d:.2f} {vu}')}"
            f'<table style="width:100%; border-collapse:collapse; border:1px solid {BORDER}; '
            f'background:{WHITE};">'
            f'<thead><tr style="background:{HEADER_BG};">'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f'text-transform:uppercase; text-align:left; border-bottom:2px solid {BORDER};">Material</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f'text-transform:uppercase; text-align:right; border-bottom:2px solid {BORDER};">Per {vu}</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f'text-transform:uppercase; text-align:right; border-bottom:2px solid {BORDER};">Unit</th>'
            f'<th style="padding:8px 10px; font-size:10px; font-weight:600; color:{TEXT_DIM}; '
            f"text-transform:uppercase; text-align:right; border-bottom:2px solid {BORDER}; "
            f'color:{PRIMARY};">Batch ({vol_d:.2f} {vu})</th>'
            f"</tr></thead><tbody>"
        )

        batch_materials = [
            ("Cement", result.cement_kg, "kg", batch_cement),
            ("Water", result.water_kg, "liters", batch_water),
            ("Fine Aggregate", result.fine_aggregate_kg, "kg", batch_fine),
            ("Coarse Aggregate", result.coarse_aggregate_kg, "kg", batch_coarse),
        ]
        if result.scm_kg > 0:
            batch_materials.append(("SCM", result.scm_kg, "kg", batch_scm))

        for i, (mat, per_m3, unit, batch_val) in enumerate(batch_materials):
            bg = f" background:{ROW_ALT};" if i % 2 == 0 else ""
            # Per-volume contents convert kg/m³ ↔ lb/yd³; batch totals are
            # plain masses converted kg ↔ lb (self-labelled).
            per_m3_disp = per_vol(per_m3)
            unit_disp = pvu if up.is_imperial() else unit
            batch_disp = up.convert_mass_kg(batch_val)
            html += (
                f'<tr style="{bg}">'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; font-weight:500;">{mat}</td>'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; text-align:right;">'
                f"{per_m3_disp:.1f}</td>"
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; text-align:right; '
                f'color:{TEXT_DIM};">{unit_disp}</td>'
                f'<td style="padding:7px 10px; border-bottom:1px solid {BORDER}; text-align:right; '
                f'font-weight:600; color:{PRIMARY};">{batch_disp:.1f} {mu}</td>'
                f"</tr>"
            )
        html += "</tbody></table></div>"

        # ── Section 6: Warnings ──
        html += warnings_html

        # ── Section 7: Glossary ──
        html += (
            f'<div style="margin-bottom:20px;">'
            f"{section_heading(7, 'Glossary')}"
            f'<table style="width:100%; border-collapse:collapse; border:1px solid {BORDER};">'
            f"<tbody>{glossary_rows}</tbody></table></div>"
        )

        # ── Footer ──
        html += (
            f'<table style="width:100%; border-collapse:collapse; margin-top:30px; '
            f'padding-top:12px; border-top:1px solid {BORDER};"><tr>'
            f'<td style="font-size:10px; font-weight:600; color:{TEXT_DIM}; vertical-align:bottom;">'
            f"&copy; 2024 CivilQntify Technical Systems</td>"
            f'<td style="text-align:right; vertical-align:bottom;">'
            f'<div style="font-size:10px; color:{TEXT_DIM};">Page 1 of 1</div>'
            f'<div style="font-size:9px; color:{PRIMARY};">Generated by CivilQntify Professional</div>'
            f"</td></tr></table>"
            f"</div>"  # end main container
            f"</body></html>"
        )

        return html

    def _show_preview(self) -> None:
        """Show the report preview dialog."""
        if not self._last_result:
            QMessageBox.warning(
                self,
                "No Data",
                "No mix design to preview. Please calculate a mix design first.",
            )
            return

        html = self._generate_mix_report_html()
        dialog = ReportPreviewDialog(self, title="Concrete Mix Design Report Preview")
        dialog.set_html(html)
        dialog.set_export_callback(self._do_export_pdf)
        dialog.exec()

    def _do_export_pdf(self) -> None:
        """Actually export the PDF after preview."""
        if not self._last_result:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", "mix_design_report.pdf", "PDF (*.pdf)"
        )
        if path:
            pdf_bytes = generate_pdf_report(self._last_result, self._last_input_params)
            with open(path, "wb") as f:
                f.write(pdf_bytes)
            self.window().status_bar.showMessage(f"PDF saved to {path}", 5000)
