"""Particle Size Distribution subtab — sieve analysis input + gradation curve.

The widget is split in two:

* :class:`ParticleSizeDistributionTab` — the left sidebar page where the user
  enters the **raw mass retained on each sieve** (g) from the lab test.
* :class:`PSDResultPanel` — the right-hand results panel (mirroring the mix
  design ``ResultPanel``) that shows the computed stat cards, the conformance
  badge and the **semi-log gradation curve** rendered with matplotlib,
  overlaid with the selected IS 383 or ASTM C33/C33M grading band for
  conformance checking.

``ConcreteMixTab`` stacks the PSD result panel with the mix-design result
panel and shows whichever matches the active left subtab, so the right side
always displays the result type belonging to the inputs being edited.

When **ASTM C33** is the selected standard, "Compute & Plot" additionally
runs every fine- or coarse-aggregate requirement of the standard (edition
C 33 – 99ae1, extracted in ``docs/ASTM-C33-99-Concrete-Aggregates.md``) —
grading, the Clause 6.2 restrictions, Table 1 / Table 3 deleterious
substances and physical properties, organic impurities, reactivity and
soundness — and opens :class:`ASTM_C33ComplianceDialog` citing the exact
clause whenever a requirement is not met. The laboratory results that the
grading sieve analysis cannot supply are entered in the "Quality
Requirements" group below the sieve table, so the user never has to consult
the standard for a limit or condition.

Reference standards (per AGENTS.md):
  - ACI 211.1-22 §4.3.5 — Fineness modulus and standard sieve series.
  - IS 383:2016 — fine-aggregate grading zones (Table 9) and coarse-aggregate
    grading (Table 7).
  - ASTM C33/C33M — Table 1 fine and Table 2 coarse grading requirements;
    quality requirements per ASTM C 33 – 99ae1 Clauses 6–8 (fine) and 9–11
    (coarse), Tables 1 and 3.
"""

from __future__ import annotations

import csv
import io
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Matplotlib — use the QtAgg backend so the canvas embeds in PyQt6.
import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.styles import uppercase_preserving_si_units
from app.widgets.astm_c33_compliance_dialog import ASTM_C33ComplianceDialog
from app.widgets.info_button import InfoButton
from concrete_mix.codes.tables import astm_c33_quality as astm_q
from concrete_mix.codes.tables.grading_bands import (
    ASTM_COARSE_NOMINAL_SIZES,
    FINE_ZONES,
    IS_GRADED_NOMINAL_SIZES,
    IS_SINGLE_SIZED_NOMINAL_SIZES,
    get_astm_coarse_band,
    get_astm_fine_band,
    get_fine_band,
    get_is_coarse_band,
)
from concrete_mix.engine.grading import (
    GradationCorrection,
    recommend_gradation_corrections,
)
from concrete_mix.engine.psd_link import derive_mix_design_params
from concrete_mix.engine.psd import (
    FM_SIEVES,
    STANDARD_SIEVES_BY_CODE,
    PSDResult,
    check_conformance,
    compute_psd,
)
from concrete_mix.validation.astm_c33 import (
    CoarseQualityInputs,
    FineQualityInputs,
    evaluate_astm_c33_coarse,
    evaluate_astm_c33_fine,
)
from concrete_mix.validation.is383 import (
    IS383CoarseQualityInputs,
    IS383FineQualityInputs,
    evaluate_is383_coarse,
    evaluate_is383_fine,
)
from history.serializers import deserialize_psd_result
# Coarsest→finest order for presenting the FM working table (ACI 211.1-22
# §4.3.5 / ASTM C136). Derived from the shared constant so both can't drift.
FM_SIEVE_SERIES: list[float] = sorted(FM_SIEVES, reverse=True)

# Stitch "Civil Engineering Precision" palette (matches app/styles.py)
_PRIMARY = "#1e40af"
_ACCENT = "#3b82f6"
_BORDER = "#e2e8f0"
_TEXT_DIM = "#444653"
_SUCCESS = "#10b981"
_WARNING = "#b45309"
_ERROR = "#ef4444"
_BAND_FILL = "#3b82f6"
_BAND_EDGE = "#1e40af"

# Sentinel value for the optional ASTM C33 laboratory-result spin boxes:
# the spin sits at its minimum and shows "not tested", meaning the
# corresponding clause is reported as not evaluated (never as a failure).
_NOT_TESTED = -1.0


def _fmt_size(mm: float) -> str:
    """Format a sieve size for display: 0.150 mm → '0.150 mm', 600 µm, etc."""
    if mm >= 1.0:
        # Drop trailing .0 for whole numbers
        return f"{mm:g} mm"
    return f"{mm * 1000:g} µm"


def _fmt_passing_limit(limit: tuple[float, float] | None) -> str:
    """Format a selected standard's inclusive percentage-passing limit."""
    if limit is None:
        return "—"
    lower, upper = limit
    if lower == upper:
        return f"{lower:g}"
    return f"{lower:g}–{upper:g}"


def _smooth_band_boundary(
    sizes: list[float],
    values: list[float],
    samples_per_interval: int = 32,
) -> tuple[list[float], list[float]]:
    """Interpolate a grading curve smoothly in log-sieve space.

    Shared by the standard-band boundaries and the user's measured
    gradation. A shape-preserving cubic Hermite interpolation is used
    rather than an unconstrained spline. Control points remain exact,
    monotonic data does not overshoot, and no curve is drawn outside the
    first and last sieves supplied.
    """
    if len(sizes) != len(values):
        raise ValueError("sizes and values must have the same length")
    if not sizes:
        return [], []
    if len(sizes) == 1:
        return list(sizes), list(values)
    if samples_per_interval < 1:
        raise ValueError("samples_per_interval must be at least 1")
    if any(size <= 0 for size in sizes):
        raise ValueError("sieve sizes must be positive for log interpolation")
    if any(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1)):
        raise ValueError("sieve sizes must be strictly increasing")

    x = [math.log(size) for size in sizes]
    y = [float(value) for value in values]
    h = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    delta = [(y[i + 1] - y[i]) / h[i] for i in range(len(h))]

    if len(x) == 2:
        slopes = [delta[0], delta[0]]
    else:
        slopes = [0.0] * len(x)
        for i in range(1, len(x) - 1):
            if delta[i - 1] == 0.0 or delta[i] == 0.0 or delta[i - 1] * delta[i] < 0:
                slopes[i] = 0.0
            else:
                w1 = 2.0 * h[i] + h[i - 1]
                w2 = h[i] + 2.0 * h[i - 1]
                slopes[i] = (w1 + w2) / (
                    w1 / delta[i - 1] + w2 / delta[i]
                )

        def endpoint_slope(
            h_near: float,
            h_next: float,
            delta_near: float,
            delta_next: float,
        ) -> float:
            slope = (
                (2.0 * h_near + h_next) * delta_near
                - h_near * delta_next
            ) / (h_near + h_next)
            if slope * delta_near <= 0.0:
                return 0.0
            if delta_near * delta_next < 0.0 and abs(slope) > 3.0 * abs(delta_near):
                return 3.0 * delta_near
            return slope

        slopes[0] = endpoint_slope(h[0], h[1], delta[0], delta[1])
        slopes[-1] = endpoint_slope(
            h[-1], h[-2], delta[-1], delta[-2]
        )

    smooth_sizes: list[float] = []
    smooth_values: list[float] = []
    for i in range(len(x) - 1):
        for sample in range(samples_per_interval):
            t = sample / samples_per_interval
            t2 = t * t
            t3 = t2 * t
            h00 = 2.0 * t3 - 3.0 * t2 + 1.0
            h10 = t3 - 2.0 * t2 + t
            h01 = -2.0 * t3 + 3.0 * t2
            h11 = t3 - t2
            interpolated = (
                h00 * y[i]
                + h10 * h[i] * slopes[i]
                + h01 * y[i + 1]
                + h11 * h[i] * slopes[i + 1]
            )
            smooth_sizes.append(
                sizes[i] if sample == 0 else math.exp(x[i] + t * h[i])
            )
            smooth_values.append(min(100.0, max(0.0, interpolated)))

    smooth_sizes.append(sizes[-1])
    smooth_values.append(min(100.0, max(0.0, y[-1])))
    return smooth_sizes, smooth_values


def _fmt_d_size(mm: float) -> str:
    """Format characteristic diameter (D10, D30, D60) matching standard sieve precision.

    - >= 10 mm (e.g. 75, 37.5, 19, 10 mm): 1 decimal place
    - 1.0 to 10 mm (e.g. 9.5, 4.75, 2.36, 1.18 mm): 2 decimal places
    - < 1.0 mm: micrometres with the µ symbol (e.g. 600 µm, 153 µm),
      matching the sieve-size display convention of :func:`_fmt_size`.
    """
    if mm >= 10.0:
        return f"{mm:.1f} mm"
    if mm >= 1.0:
        return f"{mm:.2f} mm"
    return f"{mm * 1000:.0f} µm"


def _shrinkable_combo(combo: QComboBox) -> QComboBox:
    """Let a sidebar combo shrink below its widest item's width.

    A QComboBox's minimum-size hint otherwise equals its widest item,
    which forces the input column wider than the sidebar's 360 px floor
    and pushes neighbouring fields off-screen when the pane is narrowed.
    With this policy the closed field may shrink (the dropdown popup
    still sizes itself to the full item texts).
    """
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(12)
    return combo


# ────────────────────────────────────────────────────────────────────────────
# Right-hand results panel (gradation curve + stat cards)
# ────────────────────────────────────────────────────────────────────────────


class PSDResultPanel(QWidget):
    """Results panel for the PSD subtab — stat cards + gradation curve.

    Displayed on the right side of the Concrete Mix Design tab (in a
    QStackedWidget next to the mix-design ResultPanel) whenever the PSD
    input subtab is active.

    Signals:
        apply_to_mix_design: Emitted by "Use in Mix Design" with a dict of
            PSD-derived parameters (fineness modulus, IS 383 grading zone,
            DOE %passing 600 µm, band identity and warnings) for the parent
            :class:`ConcreteMixTab` to fill into the mix-design form.
        clear_all_inputs: Emitted when the user clears the PSD tab, so the
            parent can unlock and reset the mix-design fields that were fed
            from this sieve analysis (per the handoff lock contract).
    """

    apply_to_mix_design = pyqtSignal(dict)
    clear_all_inputs = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_result: PSDResult | None = None
        self._last_band_key = None
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Scroll area for content + fixed action bar at bottom
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self._title_label = QLabel("Gradation Analysis")
        self._title_label.setObjectName("section-title")
        outer.addWidget(self._title_label)

        # ── Results summary (stat cards + conformance badge) ──
        self._results_group = QGroupBox("Results Summary")
        self._results_group.setVisible(False)
        self._results_grid = QGridLayout(self._results_group)
        self._results_grid.setContentsMargins(12, 16, 12, 12)
        self._results_grid.setSpacing(10)
        outer.addWidget(self._results_group)

        # ── Plot ──
        self._plot_group = QGroupBox("Gradation Curve (Semi-Log)")
        v = QVBoxLayout(self._plot_group)
        v.setContentsMargins(12, 16, 12, 12)

        self._fig = Figure(figsize=(7, 4.5), tight_layout=True)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self._canvas.setMinimumHeight(340)
        v.addWidget(self._canvas)

        outer.addWidget(self._plot_group)

        # Out-of-band warning banner — lives BELOW the plot so the
        # summary text never covers the curve or markers.
        self._band_warning = QLabel("")
        self._band_warning.setWordWrap(True)
        self._band_warning.setVisible(False)
        self._band_warning.setStyleSheet(
            "QLabel {"
            "  background-color: #fef2f2;"
            "  color: #7f1d1d;"
            "  border: 1px solid #dc2626;"
            "  border-radius: 6px;"
            "  padding: 10px 14px;"
            "  font-size: 12px;"
            "}"
        )
        outer.addWidget(self._band_warning)

        # Predicted corrective adjustments for out-of-band sieves
        self._corrections_label = QLabel("")
        self._corrections_label.setWordWrap(True)
        self._corrections_label.setTextFormat(Qt.TextFormat.RichText)
        self._corrections_label.setVisible(False)
        self._corrections_label.setStyleSheet(
            "QLabel {"
            "  background-color: #fffbeb;"
            "  color: #444653;"
            "  border: 1px solid #f59e0b;"
            "  border-radius: 6px;"
            "  padding: 10px 14px;"
            "  font-size: 12px;"
            "}"
        )
        outer.addWidget(self._corrections_label)

        # ── Fineness-modulus derivation (ACI 211.1-22 §4.3.5) ──
        # Shows exactly how the FM handed to ACI mix design is obtained
        # from this sieve analysis: cumulative % retained on each of the
        # six standard sieves, their sum, and FM = Σ / 100.
        self._fm_group = QGroupBox(
            "Fineness Modulus — from Sieve Analysis (ACI 211.1-22 §4.3.5)"
        )
        self._fm_group.setVisible(False)
        fm_v = QVBoxLayout(self._fm_group)
        fm_v.setContentsMargins(12, 16, 12, 12)
        fm_v.setSpacing(6)
        self._fm_grid = QGridLayout()
        self._fm_grid.setHorizontalSpacing(18)
        self._fm_grid.setVerticalSpacing(4)
        fm_v.addLayout(self._fm_grid)
        self._fm_note = QLabel("")
        self._fm_note.setWordWrap(True)
        self._fm_note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        fm_v.addWidget(self._fm_note)
        outer.addWidget(self._fm_group)

        outer.addStretch(1)

        scroll.setWidget(container)

        # ── Fixed action bar at bottom (outside scroll area) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(12, 8, 12, 8)
        # Handoff button — pushes the sieve-analysis-derived parameters that
        # each standard's mix-design engine consumes (ACI FM → Table 5.3.6;
        # IS zone → Table 5; DOE %p600 → Figure 6).
        self._btn_apply = QPushButton("Use in Mix Design")
        self._btn_apply.setObjectName("primary")
        self._btn_apply.setEnabled(False)
        self._btn_apply.setToolTip(
            "Fill the mix-design form with the parameters derived from this "
            "sieve analysis.\n\n"
            "ACI 211.1-22 §4.3.5: fineness modulus → Table 5.3.6\n"
            "IS 10262:2019 Clause 5.4: grading zone → Table 5\n"
            "BRE 331:1997 §1.2.5: % passing 600 µm → Figure 6"
        )
        self._btn_apply.clicked.connect(self._on_apply_to_mix)
        btn_row.addWidget(self._btn_apply)
        self._btn_csv = QPushButton("Export CSV")
        self._btn_csv.setObjectName("secondary")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_export_csv)
        self._btn_img = QPushButton("Export Image")
        self._btn_img.setObjectName("secondary")
        self._btn_img.setEnabled(False)
        self._btn_img.clicked.connect(self._on_export_image)
        btn_row.addWidget(self._btn_csv)
        btn_row.addWidget(self._btn_img)
        btn_row.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(scroll, 1)
        root_layout.addLayout(btn_row)

        self._draw_placeholder()

    # ── Public API ───────────────────────────────────────────────────

    def display_psd(
        self,
        result: PSDResult,
        band: dict[float, tuple[float, float]],
        band_key,
        fm_required: bool = True,
    ) -> None:
        """Show a computed gradation: stat cards + curve with the band.

        *fm_required* tells whether the selected standard consumes a
        fineness modulus for this aggregate; when it does not (IS 383, or
        ASTM C33 coarse) the FM derivation group is hidden entirely.
        """
        self._last_result = result
        self._last_band_key = band_key
        self._update_results_cards(result)
        self._fill_fm_derivation(result, fm_required)
        self._draw_curve(result, band, band_key)
        self._btn_csv.setEnabled(True)
        self._btn_img.setEnabled(True)
        self._btn_apply.setEnabled(True)

    def clear(self) -> None:
        """Reset the panel to its empty placeholder state."""
        self._last_result = None
        self._last_band_key = None
        self._results_group.setVisible(False)
        self._set_band_warning("")
        self._set_corrections([])
        self._draw_placeholder()
        self._fm_group.setVisible(False)
        self._btn_csv.setEnabled(False)
        self._btn_img.setEnabled(False)
        self._btn_apply.setEnabled(False)

    # ── Mix-design handoff ───────────────────────────────────────────

    def _on_apply_to_mix(self) -> None:
        """Emit PSD-derived parameters for the mix-design form.

        The payload carries every parameter the three supported standards
        consume from a sieve analysis (ACI 211.1-22 §4.3.5 FM, IS 383
        Table 9 zone → IS 10262 Table 5, BRE 331 %passing 600 µm), the
        band identity that tells fine vs coarse aggregate and, for coarse
        analyses, the reference nominal size.
        """
        if self._last_result is None:
            return
        linkage = derive_mix_design_params(self._last_result)

        aggregate_kind = "fine"
        nominal_size_mm = None
        key = self._last_band_key
        if key:
            # Fine keys start with ("is383"/"astm_c33", "fine", ...);
            # coarse keys end with the nominal size instead.
            aggregate_kind = "coarse" if key[1] != "fine" else "fine"
            if aggregate_kind == "coarse":
                nominal_size_mm = int(key[-1])

        self.apply_to_mix_design.emit(
            {
                "aggregate_kind": aggregate_kind,
                "band_standard": key[0] if key else None,
                "nominal_size_mm": nominal_size_mm,
                "fineness_modulus": linkage.fineness_modulus,
                "grading_zone": linkage.grading_zone,
                "pct_passing_600um": linkage.pct_passing_600um,
                "all_conform": self._last_result.all_conform,
                "warnings": list(linkage.warnings),
                # IS 383 Clause 6.3 outcome for the transferred zone.
                "zone_conforms": linkage.zone_conforms,
                "zone_deviations": list(linkage.zone_deviations),
                "zone_crushed_sand_relief": linkage.zone_crushed_sand_relief,
            }
        )

    # ── Results cards ────────────────────────────────────────────────

    def _update_results_cards(self, result: PSDResult) -> None:
        # Clear previous cards
        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards: list[tuple[str, str]] = []
        if result.fineness_modulus is not None:
            cards.append(("Fineness Modulus", f"{result.fineness_modulus:.2f}"))
        if result.d10 is not None:
            cards.append(("D10", _fmt_d_size(result.d10)))
        if result.d30 is not None:
            cards.append(("D30", _fmt_d_size(result.d30)))
        if result.d60 is not None:
            cards.append(("D60", _fmt_d_size(result.d60)))
        if result.uniformity_coefficient is not None:
            cards.append(("Cu (Uniformity)", f"{result.uniformity_coefficient:.2f}"))
        if result.coefficient_of_curvature is not None:
            cards.append(("Cc (Curvature)", f"{result.coefficient_of_curvature:.2f}"))
        if result.pct_passing_600um is not None:
            cards.append(("% Passing 600 µm (DOE)", f"{result.pct_passing_600um:.1f}%"))
        cards.append(("Total Mass", f"{result.total_mass:.1f} g"))

        # Conformance badge
        if result.conforms:
            if result.all_conform:
                badge_text = "✓ Conforms to selected band"
                badge_color = _SUCCESS
            else:
                n_bad = sum(1 for c in result.conforms if not c)
                badge_text = f"✗ {n_bad} sieve(s) out of band"
                badge_color = _ERROR
        else:
            badge_text = "— No band to check"
            badge_color = _TEXT_DIM

        cols = 4
        for i, (label, value) in enumerate(cards):
            self._results_grid.addWidget(
                self._stat_card(label, value), i // cols, i % cols
            )

        # Conformance badge spans the full width
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"color: #ffffff; "
            f"background: {badge_color}; "
            "padding: 8px 14px; border-radius: 4px; font-weight: 700; "
            "font-size: 12px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = (len(cards) + cols - 1) // cols
        self._results_grid.addWidget(badge, row, 0, 1, cols)

        self._results_group.setVisible(True)

    # ── Fineness-modulus derivation (ACI 211.1-22 §4.3.5 / ASTM C136) ──

    def _fill_fm_derivation(self, result: PSDResult, fm_required: bool = True) -> None:
        """Render exactly how the FM handed to ACI mix design is obtained.

        Hidden entirely when the selected standard carries no FM
        requirement (IS 383:2016 grades by zone; ASTM C33 coarse has no
        FM clause) — in that case the FM is not even calculated.

        Working shown step by step, mirroring ACI PRC-211.1-22 §4.3.5 and
        the ASTM C136 procedure implemented in :func:`compute_psd`:

            FM = Σ(cumulative % retained on 4.75, 2.36, 1.18, 0.600,
                   0.300 and 0.150 mm sieves) ÷ 100

        Rows follow the shared ``FM_SIEVE_SERIES`` derived from
        ``engine.psd.FM_SIEVES`` so the display can never drift from the
        computation. When any standard sieve is missing, the group shows
        which ones are needed instead of a misleading partial sum.
        """
        if not fm_required:
            self._fm_group.setVisible(False)
            return

        grid = self._fm_grid
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cum = dict(
            zip(result.sieve_sizes, result.cumulative_percent_retained)
        )

        # Header row
        header_style = f"color: {_PRIMARY}; font-weight: 700;"
        lbl = QLabel("Sieve")
        lbl.setStyleSheet(header_style)
        grid.addWidget(lbl, 0, 0)
        lbl = QLabel("Cumulative % Retained")
        lbl.setStyleSheet(header_style)
        grid.addWidget(lbl, 0, 1)

        total = 0.0
        complete = True
        missing: list[float] = []
        row = 1
        for sieve in FM_SIEVE_SERIES:
            grid.addWidget(QLabel(_fmt_size(sieve)), row, 0)
            val = cum.get(sieve)
            if val is None:
                complete = False
                missing.append(sieve)
                cell = QLabel("— not included")
                cell.setStyleSheet(f"color: {_WARNING};")
            else:
                total += val
                cell = QLabel(f"{val:.2f}")
                cell.setStyleSheet(f"color: {_TEXT_DIM};")
            grid.addWidget(cell, row, 1)
            row += 1

        bold_primary = f"color: {_PRIMARY}; font-weight: 700;"
        grid.addWidget(QLabel("Σ  sum of cumulative % retained"), row, 0)
        sum_cell = QLabel(f"{total:.2f}" + ("" if complete else " *"))
        sum_cell.setStyleSheet(bold_primary)
        grid.addWidget(sum_cell, row, 1)

        grid.addWidget(QLabel("FM = Σ ÷ 100"), row + 1, 0)
        if result.fineness_modulus is not None and complete:
            fm_cell = QLabel(f"{result.fineness_modulus:.2f}")
            fm_cell.setStyleSheet(f"color: {_SUCCESS}; font-weight: 800;")
        else:
            fm_cell = QLabel("—")
            fm_cell.setStyleSheet(f"color: {_ERROR}; font-weight: 700;")
        grid.addWidget(fm_cell, row + 1, 1)

        if result.fineness_modulus is not None and complete:
            note = (
                "FM is used with NMSA in ACI Table 5.3.6 to set the bulk "
                "volume of coarse aggregate. Press “Use in Mix Design” to "
                "transfer it — the Fineness Modulus field in the form is "
                "then locked to this value."
            )
        elif missing:
            note = (
                "FM cannot be computed from this analysis: the standard "
                "series requires cumulative % retained on "
                + ", ".join(_fmt_size(s) for s in missing)
                + ". Include these sieves and recompute."
            )
        else:
            note = ""
        self._fm_note.setText(note)
        self._fm_group.setVisible(True)

    def _stat_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #ffffff; border: 1px solid {_BORDER}; "
            f"border-left: 3px solid {_PRIMARY}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {_TEXT_DIM}; "
            "letter-spacing: 0.05em;"
        )
        val = QLabel(value)
        val.setStyleSheet(
            f"font-size: 15px; font-weight: 500; color: {_PRIMARY}; "
            "font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        v.addWidget(lbl)
        v.addWidget(val)
        return card

    # ── Plotting ─────────────────────────────────────────────────────

    def _draw_placeholder(self) -> None:
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_xlabel("Sieve Size (mm)  —  log scale")
        ax.set_ylabel("Percent Passing (%)")
        ax.set_title("Enter sieve masses, then click Compute & Plot")
        ax.text(
            0.5, 0.5, "No data", transform=ax.transAxes,
            ha="center", va="center", fontsize=14, color=_TEXT_DIM,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        self._canvas.draw()

    def _draw_curve(
        self,
        result: PSDResult,
        band: dict[float, tuple[float, float]],
        band_key,
    ) -> None:
        self._fig.clear()
        ax = self._fig.add_subplot(111)

        # ── Standard band (smooth shaded region) ──
        # Blank standard-table cells are absent from ``band``. Smooth only
        # between specified control points so the visual envelope does not
        # imply requirements outside the selected row's stated sieve range.
        if band:
            band_sizes = sorted(band.keys())
            lower = [band[s][0] for s in band_sizes]
            upper = [band[s][1] for s in band_sizes]
            smooth_sizes, smooth_lower = _smooth_band_boundary(band_sizes, lower)
            _, smooth_upper = _smooth_band_boundary(band_sizes, upper)
            # Independent shape-preserving boundaries should not cross, but
            # guard the rendered section against floating-point edge cases.
            ordered_boundaries = [
                (min(lo, hi), max(lo, hi))
                for lo, hi in zip(smooth_lower, smooth_upper)
            ]
            smooth_lower = [lo for lo, _ in ordered_boundaries]
            smooth_upper = [hi for _, hi in ordered_boundaries]
            ax.fill_between(
                smooth_sizes, smooth_lower, smooth_upper,
                color=_BAND_FILL, alpha=0.15, label="Standard band",
                edgecolor="none", zorder=1,
            )
            ax.plot(
                smooth_sizes, smooth_lower, color=_BAND_EDGE,
                linewidth=0.9, linestyle="--", alpha=0.85, zorder=2,
            )
            ax.plot(
                smooth_sizes, smooth_upper, color=_BAND_EDGE,
                linewidth=0.9, linestyle="--", alpha=0.85, zorder=2,
            )

        # ── User's gradation curve ──
        # Smoothed with the same log-space shape-preserving interpolation
        # as the band, so the measured line renders as one continuous
        # curve instead of polyline segments between sieves (PSDResult
        # lists sieves coarsest → finest, so sort ascending for the
        # helper). The curve passes exactly through every measured
        # %passing, stays within 0–100 %, and is not extended past the
        # finest/coarsest sieve of the analysis; the measured points
        # remain visible as markers drawn on top of the curve.
        sizes = result.sieve_sizes
        passing = result.percent_passing
        pts = sorted(zip(sizes, passing))
        smooth_sizes, smooth_passing = _smooth_band_boundary(
            [s for s, _ in pts], [p for _, p in pts]
        )
        ax.plot(
            smooth_sizes, smooth_passing, color=_PRIMARY, linewidth=2.2,
            label="Your gradation", zorder=5,
        )
        ax.plot(
            sizes, passing, linestyle="none", marker="o", color=_PRIMARY,
            markersize=6, zorder=6,
        )

        # ── Out-of-band markers + summary for the banner below the plot
        # (IS 383 grading tables / ASTM C33 Tables 1 and 2) ──
        self._set_band_warning(self._annotate_band_violations(ax, result, band))
        self._set_corrections(
            recommend_gradation_corrections(sizes, passing, band)
        )

        # ── Axes: x = log scale (sieve size), y = linear %passing ──
        ax.set_xscale("log")
        ax.set_xlabel("Sieve Size (mm)  —  log scale", fontsize=11)
        ax.set_ylabel("Percent Passing (%)", fontsize=11)

        # Y axis 0–100
        ax.set_ylim(0, 105)
        ax.set_yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

        # X ticks at the standard sieve sizes actually present
        ax.set_xticks(sizes)
        ax.set_xticklabels([_fmt_size(s) for s in sizes], rotation=35, ha="right")
        ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)

        # X limits with a small padding margin so end data points are not clipped on the border
        ax.set_xlim(min(sizes) * 0.75, max(sizes) * 1.3)

        # ── Characteristic sizes D10, D30, D60 (ACI 211.1-22 §4.3.5 / ASTM D6913 / IS 383) ──
        # Straight reference lines to both axes with annotated size values
        self._plot_characteristic_diameters(ax, result)

        # Title with the selected standard and reference band.
        if not band_key:
            title = "Particle Size Distribution"
        elif band_key[0] == "is383" and band_key[1] == "fine":
            title = f"Fine Aggregate Gradation — IS 383 Zone {band_key[2]}"
        elif band_key[0] == "astm_c33" and band_key[1] == "fine":
            title = "Fine Aggregate Gradation — ASTM C33/C33M Table 1"
        elif band_key[0] == "is383":
            _, _, grading_type, nominal_size = band_key
            title = (
                f"Coarse Aggregate Gradation — {_fmt_size(nominal_size)} "
                f"{grading_type}\n(IS 383:2016 Table 7)"
            )
        else:
            _, _, nominal_size = band_key
            title = (
                f"Coarse Aggregate Gradation — {_fmt_size(nominal_size)} reference\n"
                f"(ASTM C33/C33M Table 2)"
            )
        ax.set_title(title, fontsize=11, fontweight="bold", color=_PRIMARY, pad=8)

        # Legend pinned to the top-left corner so it never covers the
        # gradation curve or the out-of-band markers.
        ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
        self._fig.tight_layout()
        self._canvas.draw()

    def _plot_characteristic_diameters(self, ax, result: PSDResult) -> None:
        """Plot D10, D30, D60 characteristic sizes with straight lines to both axes.

        Per ACI 211.1-22 §4.3.5 / ASTM D6913 / IS 383:
        - D10: 10% passing effective diameter (used for Cu and Cc)
        - D30: 30% passing diameter (used for Cc)
        - D60: 60% passing diameter (used for Cu)

        Draws horizontal straight lines from the % passing axis to the curve
        and vertical drop lines down to the sieve size axis, annotated with the
        characteristic diameter formatted to match standard sieve precision.
        """
        d_items = []
        if result.d10 is not None and result.d10 > 0:
            d_items.append((result.d10, 10.0, "$D_{10}$", "#059669"))  # emerald
        if result.d30 is not None and result.d30 > 0:
            d_items.append((result.d30, 30.0, "$D_{30}$", "#d97706"))  # amber
        if result.d60 is not None and result.d60 > 0:
            d_items.append((result.d60, 60.0, "$D_{60}$", "#7c3aed"))  # purple

        if not d_items:
            return

        xlim = ax.get_xlim()
        xmin = xlim[0]

        for d_val, pct, name, color in d_items:
            d_str = _fmt_d_size(d_val)
            # Horizontal straight line from Y-axis (% passing) to curve
            ax.plot(
                [xmin, d_val], [pct, pct],
                linestyle="--", linewidth=1.1, color=color, alpha=0.85, zorder=6,
            )
            # Vertical drop line from curve to X-axis (sieve size)
            ax.plot(
                [d_val, d_val], [0, pct],
                linestyle="--", linewidth=1.1, color=color, alpha=0.85, zorder=6,
            )
            # Intersection point marker on curve
            ax.plot(
                d_val, pct, marker="o", markersize=5.5, color=color,
                markeredgecolor="#ffffff", markeredgewidth=1.0, zorder=7,
            )
            # Annotation box noting the size
            ax.annotate(
                f"{name} = {d_str}",
                xy=(d_val, pct),
                xytext=(8, -6 if pct >= 50 else 6),
                textcoords="offset points",
                fontsize=8.5,
                fontweight="bold",
                color=color,
                bbox=dict(
                    boxstyle="round,pad=0.22",
                    facecolor="#ffffff",
                    edgecolor=color,
                    alpha=0.92,
                    linewidth=0.8,
                ),
                zorder=8,
            )

    def _annotate_band_violations(
        self,
        ax,
        result: PSDResult,
        band: dict[float, tuple[float, float]],
    ) -> str:
        """Mark sieves whose %passing falls outside the band.

        Draws a red × on each offending point and returns a
        plain-language summary for the warning banner below the plot
        (kept off the axes so it never covers the curve).

        %passing above the upper limit means excess fines at that sieve
        (curve too fine); below the lower limit means deficit fines
        (too coarse). Limits come only from the selected IS 383 or ASTM C33/
        C33M reference table.

        Returns:
            The summary text, or "" when everything conforms.
        """
        if not band or not result.conforms:
            return ""

        violations: list[tuple[float, float, float, str]] = []
        for s, p, ok in zip(result.sieve_sizes, result.percent_passing,
                            result.conforms):
            if ok or s not in band:
                continue
            lo, hi = band[s]
            if p > hi:
                violations.append((s, p, hi, "upper"))
            else:
                violations.append((s, p, lo, "lower"))
        if not violations:
            return ""

        # Red × on each offending data point
        ax.scatter(
            [s for s, _, _, _ in violations],
            [p for _, p, _, _ in violations],
            marker="x", s=80, color=_ERROR, linewidths=2.2,
            label="Out of band", zorder=6,
        )

        # Plain-language summary for the banner below the plot
        lines = []
        for s, p, limit, which in violations[:4]:
            arrow = ">" if which == "upper" else "<"
            direction = "too fine" if which == "upper" else "too coarse"
            lines.append(
                f"• {_fmt_size(s)}: {p:.1f}% {arrow} {limit:.0f}% "
                f"limit — {direction}"
            )
        if len(violations) > 4:
            lines.append(f"… and {len(violations) - 4} more sieve(s)")
        return "⚠ Outside the standard band\n" + "\n".join(lines)

    def _set_band_warning(self, text: str) -> None:
        """Show or hide the out-of-band warning banner below the plot."""
        if text:
            self._band_warning.setText(text)
            self._band_warning.setVisible(True)
        else:
            self._band_warning.clear()
            self._band_warning.setVisible(False)

    def _set_corrections(
        self, corrections: list[GradationCorrection]
    ) -> None:
        """Show predicted adjustments for out-of-band sieves, or hide."""
        if not corrections:
            self._corrections_label.clear()
            self._corrections_label.setVisible(False)
            return

        lines = [
            "<b>Suggested adjustments to bring the gradation in band</b>"
        ]
        for c in corrections:
            direction = "too coarse" if c.too_coarse else "too fine"
            band_txt = (
                f"{c.lower:.0f}%"
                if c.lower == c.upper
                else f"{c.lower:.0f}\u2013{c.upper:.0f}%"
            )
            lines.append(
                f"<br>\u2022 <b>{_fmt_size(c.sieve_mm)}</b> — "
                f"{c.percent_passing:.1f}% passing vs "
                f"{band_txt} band ({direction}, "
                f"{c.deviation_pp:.1f} pts): {c.action}"
            )
        self._corrections_label.setText("".join(lines))
        self._corrections_label.setVisible(True)

    # ── Export ───────────────────────────────────────────────────────

    def _on_export_csv(self) -> None:
        if self._last_result is None:
            QMessageBox.information(
                self, "No Data", "Compute a gradation before exporting."
            )
            return
        r = self._last_result
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PSD CSV", "particle_size_distribution.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Sieve Size (mm)", "Mass Retained (g)",
                         "% Retained", "Cumulative % Retained", "% Passing"])
        for s, m, pr, c, p in zip(
            r.sieve_sizes, r.mass_retained, r.percent_retained,
            r.cumulative_percent_retained, r.percent_passing,
        ):
            writer.writerow([f"{s:g}", f"{m:.1f}", f"{pr:.2f}",
                             f"{c:.2f}", f"{p:.2f}"])
        writer.writerow(["Pan", f"{r.pan_mass:.1f}", "", "", ""])
        writer.writerow(["Total", f"{r.total_mass:.1f}", "", "", ""])
        if r.fineness_modulus is not None:
            writer.writerow(["Fineness Modulus", f"{r.fineness_modulus:.2f}"])
        if r.d10 is not None:
            writer.writerow(["D10 (mm)", f"{r.d10:.3f}"])
        if r.d30 is not None:
            writer.writerow(["D30 (mm)", f"{r.d30:.3f}"])
        if r.d60 is not None:
            writer.writerow(["D60 (mm)", f"{r.d60:.3f}"])
        if r.uniformity_coefficient is not None:
            writer.writerow(["Cu", f"{r.uniformity_coefficient:.2f}"])
        if r.coefficient_of_curvature is not None:
            writer.writerow(["Cc", f"{r.coefficient_of_curvature:.2f}"])
        with open(path, "w", newline="") as f:
            f.write(buf.getvalue())
        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            self.window().status_bar.showMessage(f"Exported to {path}", 5000)

    def _on_export_image(self) -> None:
        """Save the current gradation-curve plot as an image file.

        Supports PNG (raster, high-res) and SVG (vector).  A file dialog
        lets the user choose the destination; 300 dpi is used for PNG.
        """
        if self._last_result is None:
            QMessageBox.information(
                self, "No Data", "Compute a gradation before exporting."
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Gradation Curve Image",
            "gradation_curve.png",
            "PNG Image (*.png);;SVG Vector (*.svg)",
        )
        if not path:
            return
        # Default to PNG if the user didn't pick a filter
        if selected_filter and "SVG" in selected_filter:
            path = path if path.endswith(".svg") else path + ".svg"
            self._fig.savefig(path, format="svg", bbox_inches="tight",
                              facecolor=self._fig.get_facecolor(), dpi=150)
        else:
            path = path if path.endswith(".png") else path + ".png"
            self._fig.savefig(path, format="png", bbox_inches="tight",
                              facecolor=self._fig.get_facecolor(), dpi=300)
        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            self.window().status_bar.showMessage(
                f"Plot saved to {path}", 5000,
            )


# ────────────────────────────────────────────────────────────────────────────
# Left sidebar input tab (sieve analysis entry)
# ────────────────────────────────────────────────────────────────────────────


class ParticleSizeDistributionTab(QWidget):
    """Left sidebar subtab for sieve analysis input.

    Results are rendered into *result_panel* (a :class:`PSDResultPanel` on
    the right side of the Concrete Mix Design tab).  If no panel is passed,
    a standalone one is created so the tab remains functional in isolation
    (tests, embedding).
    """

    def __init__(self, parent=None, result_panel: PSDResultPanel | None = None) -> None:
        super().__init__(parent)
        self._last_result: PSDResult | None = None
        # Clause-by-clause compliance checks from the last compute (empty
        # when the standard carries no compliance evaluator or nothing has
        # been computed yet). Holds ASTM C33 or IS 383 checks.
        self._astm_checks: list = []
        # Manufactured-source sub-groups of the two IS 383 quality pages,
        # toggled by each page's source-type combo.
        self._is_mfd_groups: dict[str, QGroupBox] = {}
        self._result_panel = result_panel if result_panel is not None else PSDResultPanel()
        self._build_ui()

    # Back-compat: the gradation figure lives on the result panel now.
    @property
    def _fig(self) -> Figure:
        return self._result_panel._fig

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 12, 16)
        layout.setSpacing(12)

        # ── Header / controls ──
        layout.addWidget(self._build_controls())

        # ── Input table ──
        layout.addWidget(self._build_table())

        # ── ASTM C33 quality requirements (visible only for ASTM C33) ──
        self._quality_group = self._build_quality_group()
        layout.addWidget(self._quality_group)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)

        # ── Buttons ──
        # Pinned below the scroll area instead of inside it, so Compute &
        # Plot stays visible without scrolling past the sieve table and
        # the ASTM C33 quality inputs.
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            f"QFrame {{ background-color: {_BORDER}; border: none; }}"
        )
        outer.addWidget(separator)
        outer.addWidget(self._build_buttons())

        # Initial table + band combo build for fine aggregate
        self._rebuild_band_combo()
        self._rebuild_table()
        self._update_quality_visibility()

    def _build_controls(self) -> QGroupBox:
        grp = QGroupBox("Sieve Analysis — Setup")
        form = QGridLayout(grp)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(8)

        # PSD standard — controls both sieve designations and grading limits.
        self.standard_combo = _shrinkable_combo(QComboBox())
        self.standard_combo.addItem("IS 383:2016", "is383")
        self.standard_combo.addItem("ASTM C33/C33M", "astm_c33")
        self.standard_combo.setMinimumWidth(150)
        self.standard_combo.currentIndexChanged.connect(self._on_standard_changed)
        form.addWidget(self._label("Standard"), 0, 0)
        form.addWidget(self.standard_combo, 0, 1)

        # Aggregate type
        self.agg_combo = _shrinkable_combo(QComboBox())
        self.agg_combo.addItem("Fine Aggregate (sand)", "fine")
        self.agg_combo.addItem("Coarse Aggregate (gravel/stone)", "coarse")
        # Floor the width so the combo's minimumSizeHint (widest item) does
        # not force the sidebar wider than its 360px floor; text elides.
        self.agg_combo.setMinimumWidth(150)
        self.agg_combo.currentIndexChanged.connect(self._on_agg_type_changed)
        form.addWidget(self._label("Aggregate Type"), 1, 0)
        form.addWidget(self.agg_combo, 1, 1)

        # Reference band selector — depends on standard and aggregate type
        self.band_combo = _shrinkable_combo(QComboBox())
        self.band_combo.setMinimumWidth(150)
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)
        self._lbl_band = self._label_with_info(
            "Reference Band",
            "Limits and sieve rows always follow the selected standard.\n\n"
            "IS 383 → fine Zones I–IV; Table 7 single-sized and graded coarse "
            "references.\n"
            "ASTM C33/C33M → Table 1 fine envelope; Table 2 coarse references "
            "10 mm (Size 8), 20 mm (Size 67), and 40 mm (Size 467).",
        )
        form.addWidget(self._lbl_band, 2, 0)
        form.addWidget(self.band_combo, 2, 1)

        form.setColumnStretch(2, 1)
        return grp

    def _build_table(self) -> QGroupBox:
        grp = QGroupBox("Input — Mass Retained on Each Sieve")
        v = QVBoxLayout(grp)
        v.setContentsMargins(12, 16, 12, 12)

        hint = QLabel(
            "Enter the mass retained (g) on each sieve as measured during the "
            "test. Results appear in the panel on the right."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        v.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Sieve Size",
                "Mass Retained (g)",
                "% Retained",
                "Cumulative % Retained",
                "% Passing",
                "Standard % Passing",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self._on_cell_changed)

        # Style the header and input column so it visually stands out
        self._style_input_column()
        v.addWidget(self.table)
        return grp

    def _style_input_column(self) -> None:
        """Style the Mass Retained column (1) to stand out visually.

        Sets a neutral header stylesheet and widens column 1 slightly.
        Per-cell backgrounds (light blue tint) are applied in
        :meth:`_rebuild_table` each time rows are created.
        """
        hdr = self.table.horizontalHeader()
        hdr.setMinimumSectionSize(24)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(1, 160)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #e2e8f0; }"
            "QTableWidget::item { padding: 2px 4px; }"
            "QHeaderView::section {"
            "  background-color: #f1f5f9;"
            "  color: #444653;"
            "  font-weight: 700;"
            "  font-size: 11px;"
            "  padding: 6px;"
            "  border-bottom: 2px solid #e2e8f0;"
            "}"
        )

    def _build_buttons(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        # Margins match the scrolling content above (16/12) so the pinned
        # row reads as the bottom of the same column.
        lay.setContentsMargins(16, 8, 12, 12)
        lay.setSpacing(12)

        self.plot_btn = QPushButton("  Compute & Plot")
        self.plot_btn.setMinimumHeight(40)
        self.plot_btn.clicked.connect(self._on_compute_plot)
        lay.addWidget(self.plot_btn, 2)

        self.clear_btn = QPushButton("  Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.clicked.connect(self._on_clear)
        lay.addWidget(self.clear_btn, 1)

        lay.addStretch(1)
        return w

    # ── ASTM C33 quality requirements ────────────────────────────────

    def _pct_spin(
        self, hi: float = 100.0, step: float = 0.1, decimals: int = 1
    ) -> QDoubleSpinBox:
        """Mass-percent spin box that can sit at "not tested".

        The minimum is the :data:`_NOT_TESTED` sentinel; while the spin
        shows it, the matching clause is reported as not evaluated.
        """
        spin = QDoubleSpinBox()
        spin.setRange(_NOT_TESTED, hi)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setSuffix(" %")
        spin.setSpecialValueText("not tested")
        spin.setValue(_NOT_TESTED)
        # Wide enough for the full "not tested" special-value text plus
        # the spin controls, so it never renders clipped.
        spin.setMinimumWidth(130)
        return spin

    def _build_quality_group(self) -> QGroupBox:
        """Laboratory results the sieve analysis cannot supply.

        Shown for both grading standards (ASTM C33/C33M and IS 383:2016);
        the stacked pages carry the fields of the selected standard ×
        aggregate type. Every field carries the clause and limit in its
        label or tooltip so the user never needs the standard document to
        complete or interpret a check. Fields left at "not tested" simply
        skip their clause.
        """
        grp = QGroupBox("Quality Requirements")
        v = QVBoxLayout(grp)
        v.setContentsMargins(12, 16, 12, 12)
        v.setSpacing(8)

        self._quality_hint = QLabel("")
        self._quality_hint.setWordWrap(True)
        self._quality_hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        hint_row.setSpacing(4)
        hint_row.addWidget(self._quality_hint, 1)
        hint_row.addWidget(InfoButton(
            "What this section checks\n\n"
            "The sieve analysis above already checks the grading against "
            "the selected standard's table (ASTM C33 Table 1/Table 2; "
            "IS 383:2016 Table 9/Table 7). This group covers everything "
            "else the selected standard asks for — deleterious substances, "
            "organic impurities, particle shape, mechanical properties, "
            "soundness and alkali-aggregate reactivity.\n\n"
            "Enter the laboratory results you have; anything left at "
            "“not tested” is simply skipped — never counted as a failure. "
            "After Compute & Plot, every unmet requirement is listed with "
            "the exact clause of the standard."
        ))
        v.addLayout(hint_row)

        # Pages: 0 ASTM-fine, 1 ASTM-coarse, 2 IS-fine, 3 IS-coarse.
        self._quality_stack = QStackedWidget()
        self._quality_stack.addWidget(self._build_fine_quality_page())
        self._quality_stack.addWidget(self._build_coarse_quality_page())
        self._quality_stack.addWidget(self._build_is_fine_quality_page())
        self._quality_stack.addWidget(self._build_is_coarse_quality_page())
        v.addWidget(self._quality_stack)

        grp.setVisible(False)
        return grp

    # ── Fine-aggregate quality page ──────────────────────────────────

    def _build_fine_quality_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Grading restrictions (Clause 6.2 checked automatically; 6.4 needs
        # the source's base fineness modulus).
        g1 = QGroupBox("Grading Restrictions (6.2 / 6.4)")
        f1 = QGridLayout(g1)
        f1.setContentsMargins(12, 16, 12, 12)
        f1.setSpacing(8)
        auto_note = QLabel(
            "Clause 6.2 is checked automatically from the sieve analysis: "
            "≤ 45 % passing any sieve and retained on the next consecutive "
            "sieve, and fineness modulus between 2.3 and 3.1."
        )
        auto_note.setWordWrap(True)
        auto_note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        f1.addWidget(auto_note, 0, 0, 1, 2)
        self.fine_fm_variation_check = QCheckBox("Continuing shipment (6.4)")
        self.fine_fm_variation_check.setToolTip(
            "Clause 6.4: for continuing shipments of fine aggregate from a "
            "given source, the fineness modulus shall not vary more than "
            "0.20 from the base fineness modulus typical of that source."
        )
        self.fine_fm_variation_check.toggled.connect(
            self._on_fine_fm_variation_toggled
        )
        # The checkbox spans both columns (like every other option here)
        # so its no-wrap label never sits beside the spin in one row —
        # that pair otherwise exceeds the sidebar's 360 px floor.
        f1.addWidget(self._field_with_info(
            self.fine_fm_variation_check,
            "Continuing shipment — FM variation (Clause 6.4)\n\n"
            "Tick this only when sand keeps arriving from the same source "
            "over time. The fineness modulus (a single number saying how "
            "coarse or fine the sand is) of each shipment must not differ "
            "by more than 0.20 from the base FM — the value typical of "
            "that source. A bigger swing means the concrete mix may need "
            "re-proportioning (Note 5).\n\n"
            "Enter the source's base FM in the row below; the app compares "
            "it with the FM computed from your sieve analysis.",
        ), 1, 0, 1, 2)
        self.fine_base_fm_spin = QDoubleSpinBox()
        self.fine_base_fm_spin.setRange(0.10, 10.0)
        self.fine_base_fm_spin.setDecimals(2)
        self.fine_base_fm_spin.setSingleStep(0.05)
        self.fine_base_fm_spin.setValue(2.60)
        self.fine_base_fm_spin.setSuffix(" FM")
        self.fine_base_fm_spin.setEnabled(False)
        self.fine_base_fm_spin.setToolTip(
            "Base fineness modulus of the source (Clause 6.4). The shipment "
            "FM may not differ from it by more than 0.20."
        )
        f1.addWidget(self._label_with_info(
            "Base FM",
            "Base fineness modulus (Clause 6.4)\n\n"
            "The FM typical of the source — usually the average of past "
            "tests, or of the first ten samples if the source is new "
            "(Note 5). The shipment FM from your sieve analysis must stay "
            "within 0.20 of this number.",
        ), 2, 0)
        f1.addWidget(self.fine_base_fm_spin, 2, 1)
        f1.setColumnStretch(2, 1)
        v.addWidget(g1)

        # Deleterious substances — Table 1 (Clause 7.1).
        g2 = QGroupBox("Deleterious Substances — Table 1")
        f2 = QGridLayout(g2)
        f2.setContentsMargins(12, 16, 12, 12)
        f2.setSpacing(8)

        f2.addWidget(self._label_with_info(
            "Clay lumps & friable particles (max 3.0 %)",
            "Clay lumps and friable particles (Table 1, Clause 7.1)\n\n"
            "Soft clay lumps and crumbly particles that break up during "
            "mixing. They soak up mixing water and leave weak spots in "
            "the concrete. Measured by Test Method C 142.\n\n"
            "Limit: 3.0 % of the total sample mass. Leave at “not tested” "
            "to skip the check.",
        ), 0, 0)
        self.fine_clay_spin = self._pct_spin()
        self.fine_clay_spin.setToolTip(
            "Table 1: clay lumps and friable particles shall not exceed "
            "3.0 % of the total sample (Test Method C 142)."
        )
        f2.addWidget(self.fine_clay_spin, 0, 1)

        # Label kept short so the checkbox's no-wrap hint stays inside the
        # sidebar's 360 px floor; the limits live in the tooltip.
        self.fine_abrasion_check = QCheckBox("Concrete subject to abrasion")
        self.fine_abrasion_check.setChecked(True)
        self.fine_abrasion_check.setToolTip(
            "Table 1 selects the material-finer-than-75-µm limit by "
            "exposure: 3.0 % for concrete subject to abrasion, 5.0 % for "
            "all other concrete. Clauses 4.2.4.3/4.3.2.3: if not stated, the "
            "3.0 % limit applies."
        )
        f2.addWidget(self._field_with_info(
            self.fine_abrasion_check,
            "Concrete subject to abrasion (Table 1)\n\n"
            "Tick this when the concrete surface will be worn — floors, "
            "pavements, driveways. It selects the stricter limit for "
            "material finer than the 75-µm sieve: 3.0 % instead of "
            "5.0 %.\n\n"
            "If the order does not say, the 3.0 % limit applies "
            "(Clauses 4.2.4.3 / 4.3.2.3).",
        ), 1, 0, 1, 2)

        self.fine_manufactured_check = QCheckBox(
            "Manufactured sand (limits 5.0 / 7.0 %)"
        )
        self.fine_manufactured_check.setToolTip(
            "Table 1 Footnote A: for manufactured sand whose material "
            "finer than the 75-µm (No. 200) sieve is the dust of fracture, "
            "essentially free of clay or shale, the 3.0/5.0 % limits are "
            "permitted to be increased to 5 and 7 % respectively."
        )
        f2.addWidget(self._field_with_info(
            self.fine_manufactured_check,
            "Manufactured sand (Table 1 Footnote A)\n\n"
            "Tick this when the sand is crushed rock AND its material "
            "finer than the 75-µm (No. 200) sieve is dust of fracture — "
            "essentially free of clay or shale.\n\n"
            "The standard then relaxes the 75-µm limits from 3.0/5.0 % to "
            "5.0/7.0 %, because clean rock dust is far less harmful than "
            "clay or silt.",
        ), 2, 0, 1, 2)

        f2.addWidget(self._label_with_info(
            "Material finer than 75-µm (No. 200) sieve",
            "Material finer than the 75-µm sieve (Table 1)\n\n"
            "The very finest fraction — silt and clay, measured by washing "
            "through the No. 200 sieve (Test Method C 117). Too much of "
            "it makes concrete weak, sticky and water-demanding.\n\n"
            "Limits: 3.0 % for concrete subject to abrasion, 5.0 % "
            "otherwise — or 5.0/7.0 % with the manufactured-sand "
            "relaxation ticked above.",
        ), 3, 0)
        self.fine_finer_75um_spin = self._pct_spin()
        self.fine_finer_75um_spin.setToolTip(
            "Test Method C 117 result. The applicable Table 1 limit is "
            "chosen from the two options above (3.0/5.0 %, or 5.0/7.0 % "
            "with the manufactured-sand relaxation)."
        )
        f2.addWidget(self.fine_finer_75um_spin, 3, 1)

        self.fine_appearance_check = QCheckBox("Surface appearance important")
        self.fine_appearance_check.setToolTip(
            "Table 1: coal and lignite shall not exceed 0.5 % where the "
            "surface appearance of the concrete is of importance, 1.0 % for "
            "all other concrete. Clauses 4.2.4.4/4.3.2.4: if not stated, the "
            "1.0 % limit applies."
        )
        f2.addWidget(self._field_with_info(
            self.fine_appearance_check,
            "Surface appearance important (Table 1)\n\n"
            "Tick this for concrete that will be seen — architectural or "
            "exposed surfaces. Coal and lignite particles later show as "
            "dark stains and pop-outs, so their limit tightens from "
            "1.0 % to 0.5 %.",
        ), 4, 0, 1, 2)

        f2.addWidget(self._label_with_info(
            "Coal and lignite",
            "Coal and lignite (Table 1, Clause 7.1)\n\n"
            "Light, dark particles separated by floating them off in a "
            "liquid of 2.0 specific gravity (Test Method C 123 — only "
            "brownish-black or black material counts; coke excluded).\n\n"
            "Limits: 0.5 % where surface appearance matters, otherwise "
            "1.0 %.",
        ), 5, 0)
        self.fine_coal_spin = self._pct_spin()
        self.fine_coal_spin.setToolTip(
            "Test Method C 123 result (liquid of 2.0 specific gravity; only "
            "brownish-black or black material counts; coke excluded)."
        )
        f2.addWidget(self.fine_coal_spin, 5, 1)
        f2.setColumnStretch(2, 1)
        v.addWidget(g2)

        # Organic impurities (7.2) and soundness (8.1).
        g3 = QGroupBox("Organic Impurities (7.2) and Soundness (8.1)")
        f3 = QGridLayout(g3)
        f3.setContentsMargins(12, 16, 12, 12)
        f3.setSpacing(8)

        f3.addWidget(self._label_with_info(
            "Organic impurities color test (7.2)",
            "Organic impurities color test (Clause 7.2)\n\n"
            "A quick screening test (Test Method C 40): the sand is soaked "
            "in sodium hydroxide and the colour of the liquid is compared "
            "with a standard. Darker normally means harmful organic "
            "matter, and the sand is rejected.\n\n"
            "Two exceptions let a darker sand pass: the colour comes "
            "mainly from coal or lignite (7.2.2), or the mortar strength "
            "test in the next row gives at least 95 % (7.2.3).",
        ), 0, 0)
        self.fine_organic_combo = _shrinkable_combo(QComboBox())
        self.fine_organic_combo.addItem("Not tested", "not_tested")
        self.fine_organic_combo.addItem(
            "Color not darker than the standard — passes", "not_darker"
        )
        self.fine_organic_combo.addItem(
            "Darker — discoloration from coal/lignite (7.2.2)",
            "darker_coal_lignite",
        )
        self.fine_organic_combo.addItem(
            "Darker — verified by Test Method C 87 strength (7.2.3)",
            "darker_c87",
        )
        self.fine_organic_combo.addItem(
            "Darker — no exemption applies", "darker_no_exemption"
        )
        self.fine_organic_combo.setMinimumWidth(150)
        self.fine_organic_combo.currentIndexChanged.connect(
            self._on_fine_organic_changed
        )
        self.fine_organic_combo.setToolTip(
            "Clause 7.2: aggregates producing a color darker than the "
            "standard shall be rejected, unless the discoloration is due "
            "principally to coal/lignite (7.2.2) or the C 87 mortar 7-day "
            "relative strength is at least 95 % (7.2.3)."
        )
        f3.addWidget(self.fine_organic_combo, 0, 1)

        f3.addWidget(self._label_with_info(
            "C 87 7-day relative strength",
            "Relative strength by Test Method C 87 (Clause 7.2.3)\n\n"
            "Used when the colour test is darker but the sand may still "
            "be good. Mortar cubes made with the suspect sand are "
            "compared with cubes made from the same sand after washing.\n\n"
            "If the 7-day relative strength is at least 95 %, the sand is "
            "accepted despite the colour.",
        ), 1, 0)
        self.fine_c87_spin = QDoubleSpinBox()
        self.fine_c87_spin.setRange(0.0, 200.0)
        self.fine_c87_spin.setDecimals(1)
        self.fine_c87_spin.setSingleStep(0.5)
        self.fine_c87_spin.setValue(95.0)
        self.fine_c87_spin.setSuffix(" %")
        self.fine_c87_spin.setEnabled(False)
        self.fine_c87_spin.setToolTip(
            "Clause 7.2.3: use of the aggregate is not prohibited when the "
            "relative strength at 7 days, calculated per Test Method C 87, "
            "is not less than 95 %."
        )
        f3.addWidget(self.fine_c87_spin, 1, 1)

        f3.addWidget(self._label_with_info(
            "Soundness salt used (8.1)",
            "Soundness salt (Clause 8.1)\n\n"
            "The soundness test (Test Method C 88) soaks the aggregate in "
            "a salt solution, dries it, and repeats — five cycles imitate "
            "many years of freezing and thawing weathering.\n\n"
            "Pick the salt your laboratory used: the weight-loss limit is "
            "10 % with sodium sulfate or 15 % with magnesium sulfate.",
        ), 2, 0)
        self.fine_soundness_salt_combo = _shrinkable_combo(QComboBox())
        self.fine_soundness_salt_combo.addItem("Not tested", "")
        self.fine_soundness_salt_combo.addItem("Sodium sulfate (max 10 %)", "sodium")
        self.fine_soundness_salt_combo.addItem(
            "Magnesium sulfate (max 15 %)", "magnesium"
        )
        self.fine_soundness_salt_combo.setToolTip(
            "Clause 8.1: five cycles of the soundness test (Test Method "
            "C 88); weighted average loss not greater than 10 % with sodium "
            "sulfate or 15 % with magnesium sulfate."
        )
        f3.addWidget(self.fine_soundness_salt_combo, 2, 1)

        f3.addWidget(self._label_with_info(
            "Soundness loss (5 cycles)",
            "Soundness loss (Clause 8.1)\n\n"
            "The weighted average mass lost after the five cycles (finer "
            "size fractions count proportionally more).\n\n"
            "Must not exceed 10 % with sodium sulfate or 15 % with "
            "magnesium sulfate, per the salt chosen above.",
        ), 3, 0)
        self.fine_soundness_spin = self._pct_spin()
        self.fine_soundness_spin.setToolTip(
            "Weighted average loss after five soundness cycles; the limit "
            "follows the salt selected above."
        )
        f3.addWidget(self.fine_soundness_spin, 3, 1)
        f3.setColumnStretch(2, 1)
        v.addWidget(g3)

        # Reactive materials (7.3).
        g4 = QGroupBox("Deleteriously Reactive Materials (Clause 7.3)")
        f4 = QGridLayout(g4)
        f4.setContentsMargins(12, 16, 12, 12)
        f4.setSpacing(8)
        self.fine_reactivity_combo = self._reactivity_combo()
        f4.addWidget(self._field_with_info(
            self.fine_reactivity_combo,
            "Deleteriously reactive materials (Clause 7.3)\n\n"
            "Some sands contain minerals (certain silicas, for example) "
            "that slowly react with the alkalis in cement. The reaction "
            "makes concrete swell and crack (alkali-aggregate reaction). "
            "It matters when concrete stays damp: in contact with the "
            "ground, rain, or humid air.\n\n"
            "• No injuriously reactive materials → passes.\n"
            "• Reactive, but used with low-alkali cement (below 0.60 % "
            "Na₂O equivalent) or with a proven preventive material → "
            "accepted.\n"
            "• Reactive with no mitigation → fails the standard.\n\n"
            "“Not applicable” covers concrete never exposed to wetting "
            "or moisture.",
        ), 0, 0, 1, 2)
        f4.setColumnStretch(2, 1)
        v.addWidget(g4)

        # The stack sizes every page to the tallest (coarse) page; without
        # this stretch the surplus height inflates the group boxes instead
        # of sitting below them.
        v.addStretch(1)

        return page

    # ── Coarse-aggregate quality page ────────────────────────────────

    # Short Table 3 construction-type descriptions for the class combo.
    _CLASS_SHORT_DESCRIPTIONS = {
        "1S": "Footings, foundations, interior slabs with coverings",
        "2S": "Interior floors without coverings",
        "3S": "Walls, abutments, piers, girders exposed to weather",
        "4S": "Pavements, bridge decks, waterfront structures",
        "5S": "Exposed architectural concrete",
        "1M": "Footings, foundations, interior slabs with coverings",
        "2M": "Interior floors without coverings",
        "3M": "Walls, abutments, piers, girders exposed to weather",
        "4M": "Pavements, bridge decks, waterfront structures",
        "5M": "Exposed architectural concrete",
        "1N": "Slabs subject to traffic abrasion",
        "2N": "All other classes of concrete",
    }

    def _build_coarse_quality_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Class designation — Table 3 (Clause 11.1).
        g1 = QGroupBox("Class Designation — Table 3 (11.1)")
        f1 = QGridLayout(g1)
        f1.setContentsMargins(12, 16, 12, 12)
        f1.setSpacing(8)

        self.coarse_class_combo = _shrinkable_combo(QComboBox())
        for designation in astm_q.COARSE_CLASS_ORDER:
            region = designation[-1]
            self.coarse_class_combo.addItem(
                f"{designation} — "
                f"{self._CLASS_SHORT_DESCRIPTIONS[designation]} "
                f"({astm_q.REGION_LABELS[region]})",
                designation,
            )
        self.coarse_class_combo.setCurrentIndex(
            astm_q.COARSE_CLASS_ORDER.index("3S")
        )
        self.coarse_class_combo.setMinimumWidth(150)
        self.coarse_class_combo.setToolTip(
            "Table 3 limits depend on the class designation and weathering "
            "region.\n\nClause 11.1: if the class is not specified, the "
            "requirements for Class 3S, 3M or 1N apply in the severe, "
            "moderate and negligible weathering regions respectively."
        )
        lbl = self._label_with_info(
            "Class designation",
            "Table 3 (Clause 11.1) limits by class:\n\n"
            + "\n\n".join(
                f"{astm_q.WEATHERING_REGIONS[code]}"
                for code in ("S", "M", "N")
            )
            + "\n\nClause 11.1 default when the class is not specified: "
            "3S / 3M / 1N by weathering region.",
        )
        f1.addWidget(lbl, 0, 0)
        f1.addWidget(self.coarse_class_combo, 0, 1)
        f1.setColumnStretch(2, 1)
        v.addWidget(g1)

        # Deleterious substances — Table 3.
        g2 = QGroupBox("Deleterious Substances — Table 3")
        f2 = QGridLayout(g2)
        f2.setContentsMargins(12, 16, 12, 12)
        f2.setSpacing(8)

        f2.addWidget(self._label_with_info(
            "Clay lumps & friable particles",
            "Clay lumps and friable particles (Table 3, Clause 11.1)\n\n"
            "Soft clay lumps and crumbly particles (Test Method C 142) "
            "that break down in mixing and weaken the concrete.\n\n"
            "The maximum depends on the class chosen above — for "
            "example 5.0 % for 3S/3M, 3.0 % for 4S, 2.0 % for 5S and "
            "10.0 % for 1S/1M/2N.",
        ), 0, 0)
        self.coarse_clay_spin = self._pct_spin()
        self.coarse_clay_spin.setToolTip(
            "Table 3, class limit (Test Method C 142); e.g. 3S/3M = 5.0 %, "
            "4S = 3.0 %, 5S = 2.0 %, 1S/1M/2N = 10.0 %."
        )
        f2.addWidget(self.coarse_clay_spin, 0, 1)

        f2.addWidget(self._label_with_info(
            "Chert (lighter than 2.40 sp gr SSD)",
            "Chert lighter than 2.40 sp gr SSD (Table 3)\n\n"
            "Chert is a porous, lightweight rock. Particles with a "
            "saturated-surface-dry specific gravity under 2.40 soak up "
            "water and can pop out of the surface after freezing.\n\n"
            "Separated by Test Method C 123 (heavy liquid) and identified "
            "with Guide C 295. Limited only for exposed classes "
            "(3S = 5.0 %, 4S = 5.0 %, 5S = 3.0 %…); no requirement for "
            "1S/2S/1M/2M/1N/2N.",
        ), 1, 0)
        self.coarse_chert_spin = self._pct_spin()
        self.coarse_chert_spin.setToolTip(
            "Table 3, class limit; identified with Test Method C 123 "
            "(lighter than 2.40 specific gravity) and Guide C 295. No "
            "requirement for Classes 1S/2S/1M/2M/1N/2N."
        )
        f2.addWidget(self.coarse_chert_spin, 1, 1)

        f2.addWidget(self._label_with_info(
            "Sum of clay lumps + friable + chert",
            "Combined limit (Table 3)\n\n"
            "Table 3 caps the TOTAL of clay lumps + friable particles + "
            "light chert as well as each item separately — e.g. 7.0 % "
            "for class 3S and 5.0 % for 4S.\n\n"
            "This row shows the sum of the two entries above; the app "
            "checks it against your class limit automatically.",
        ), 2, 0)
        self.coarse_sum_label = QLabel("—")
        self.coarse_sum_label.setStyleSheet(
            f"color: {_PRIMARY}; font-weight: 600;"
        )
        f2.addWidget(self.coarse_sum_label, 2, 1)
        self.coarse_clay_spin.valueChanged.connect(
            self._update_coarse_sum_label
        )
        self.coarse_chert_spin.valueChanged.connect(
            self._update_coarse_sum_label
        )

        f2.addWidget(self._label_with_info(
            "Coal and lignite",
            "Coal and lignite (Table 3, Clause 11.1)\n\n"
            "Same light, dark particles as for sand — floated off in a "
            "liquid of 2.0 specific gravity (Test Method C 123).\n\n"
            "Class limits: 0.5 % for most exposed classes, 1.0 % for "
            "1S/1M/2N.",
        ), 3, 0)
        self.coarse_coal_spin = self._pct_spin()
        self.coarse_coal_spin.setToolTip(
            "Table 3, class limit (Test Method C 123 with a liquid of 2.0 "
            "specific gravity): 0.5 % for most exposed classes, 1.0 % for "
            "1S/1M/2N."
        )
        f2.addWidget(self.coarse_coal_spin, 3, 1)
        f2.setColumnStretch(2, 1)
        v.addWidget(g2)

        # Material finer than 75 µm — Table 3 Footnote C.
        g3 = QGroupBox("Finer than 75-µm — Table 3 Fn C")
        f3 = QGridLayout(g3)
        f3.setContentsMargins(12, 16, 12, 12)
        f3.setSpacing(8)

        f3.addWidget(self._label_with_info(
            "Material finer than 75-µm (No. 200)",
            "Material finer than the 75-µm sieve (Table 3 Footnote C)\n\n"
            "Silt and clay in the coarse aggregate, measured by washing "
            "through the No. 200 sieve (Test Method C 117). Too much of "
            "it increases water demand and weakens concrete.\n\n"
            "The base limit is 1.0 % for every class. Footnote C offers "
            "two relaxations — tick the matching option below.",
        ), 0, 0)
        self.coarse_finer_75um_spin = self._pct_spin()
        self.coarse_finer_75um_spin.setToolTip(
            "Test Method C 117 result. Base Table 3 limit 1.0 % for every "
            "class; the relaxations below follow Footnote C."
        )
        f3.addWidget(self.coarse_finer_75um_spin, 0, 1)

        self.coarse_clay_free_check = QCheckBox(
            "Clay/shale free — 1.5 % (Footnote C)"
        )
        self.coarse_clay_free_check.setToolTip(
            "Table 3 Footnote C (1): the 1.0 % limit is permitted to be "
            "increased to 1.5 % when the material is essentially free of "
            "clay or shale."
        )
        f3.addWidget(self._field_with_info(
            self.coarse_clay_free_check,
            "Clay/shale free — 1.5 % (Footnote C)\n\n"
            "Tick when the material finer than the 75-µm sieve is "
            "essentially free of clay or shale — clean rock dust, not "
            "plastic fines.\n\n"
            "Footnote C (1) then raises the 1.0 % limit to 1.5 %.",
        ), 1, 0, 1, 2)

        self.coarse_weighted_check = QCheckBox("Weighted limit L (Footnote C)")
        self.coarse_weighted_check.setToolTip(
            "Table 3 Footnote C (2): when the fine-aggregate source is "
            "known to contain less than its Table 1 maximum passing the "
            "75-µm sieve (A < T), the coarse-aggregate limit may be "
            "increased to L = 1 + [P/(100 − P)]·(T − A), with P the sand "
            "percentage of total aggregate."
        )
        self.coarse_weighted_check.toggled.connect(
            self._on_coarse_weighted_toggled
        )
        f3.addWidget(self._field_with_info(
            self.coarse_weighted_check,
            "Apply weighted limit L (Footnote C)\n\n"
            "When the concrete's sand is cleaner than its own Table 1 "
            "maximum, the coarse aggregate is allowed to carry more "
            "fines. Footnote C (2) raises the limit to\n\n"
            "L = 1 + [P / (100 − P)] × (T − A)\n\n"
            "P = sand as a percentage of total aggregate, T = the sand's "
            "Table 1 limit, A = the sand's actual 75-µm content (must be "
            "below T). Enter the three values below; the app computes and "
            "applies L.",
        ), 2, 0, 1, 2)

        self.coarse_p_spin = QDoubleSpinBox()
        self.coarse_p_spin.setRange(0.0, 99.0)
        self.coarse_p_spin.setDecimals(1)
        self.coarse_p_spin.setSingleStep(1.0)
        self.coarse_p_spin.setValue(35.0)
        self.coarse_p_spin.setSuffix(" %")
        self.coarse_p_spin.setEnabled(False)
        self.coarse_p_spin.setToolTip("P — percentage of sand as a percent of total aggregate.")
        self.coarse_t_spin = QDoubleSpinBox()
        self.coarse_t_spin.setRange(0.5, 7.0)
        self.coarse_t_spin.setDecimals(1)
        self.coarse_t_spin.setSingleStep(0.5)
        self.coarse_t_spin.setValue(3.0)
        self.coarse_t_spin.setSuffix(" %")
        self.coarse_t_spin.setEnabled(False)
        self.coarse_t_spin.setToolTip(
            "T — Table 1 limit for the fine aggregate (3.0 % default per "
            "Clause 4.2.4.3 when not otherwise stated)."
        )
        self.coarse_a_spin = QDoubleSpinBox()
        self.coarse_a_spin.setRange(0.0, 7.0)
        self.coarse_a_spin.setDecimals(1)
        self.coarse_a_spin.setSingleStep(0.1)
        self.coarse_a_spin.setValue(1.0)
        self.coarse_a_spin.setSuffix(" %")
        self.coarse_a_spin.setEnabled(False)
        self.coarse_a_spin.setToolTip(
            "A — actual amount passing the 75-µm sieve in the fine "
            "aggregate. Must be less than T for the relaxation to apply."
        )
        f3.addWidget(self._label_with_info(
            "P — sand % of total aggregate",
            "P in the weighted limit (Footnote C)\n\n"
            "The fine aggregate (sand) as a percentage of the TOTAL "
            "aggregate in the concrete — e.g. 35 % means the mix uses "
            "35 % sand and 65 % coarse aggregate by mass.",
        ), 3, 0)
        f3.addWidget(self.coarse_p_spin, 3, 1)
        f3.addWidget(self._label_with_info(
            "T — Table 1 fine-aggregate limit",
            "T in the weighted limit (Footnote C)\n\n"
            "The Table 1 limit for material passing the 75-µm sieve in "
            "the fine aggregate — 3.0 % when the concrete is subject to "
            "abrasion, otherwise 5.0 % (the default 3.0 % applies when "
            "the order does not say, per Clause 4.2.4.3).",
        ), 4, 0)
        f3.addWidget(self.coarse_t_spin, 4, 1)
        f3.addWidget(self._label_with_info(
            "A — actual in fine aggregate",
            "A in the weighted limit (Footnote C)\n\n"
            "The actual percentage passing the 75-µm sieve in the fine "
            "aggregate (Test Method C 117). It must be less than T for "
            "the relaxation to apply — cleaner sand buys room for the "
            "coarse aggregate.",
        ), 5, 0)
        f3.addWidget(self.coarse_a_spin, 5, 1)
        f3.setColumnStretch(2, 1)
        v.addWidget(g3)

        # Physical properties — abrasion (Footnote A) and soundness (fn B).
        g4 = QGroupBox("Abrasion & Soundness — Table 3 (Fn A/B)")
        f4 = QGridLayout(g4)
        f4.setContentsMargins(12, 16, 12, 12)
        f4.setSpacing(8)

        f4.addWidget(self._label_with_info(
            "Los Angeles abrasion loss (max 50 %)",
            "Los Angeles abrasion loss (Table 3, Footnote A)\n\n"
            "The Los Angeles machine tumbles the aggregate with steel "
            "balls and measures how much wears away (Test Method C 131 "
            "or C 535). It predicts resistance to wear — important for "
            "pavements and floors.\n\n"
            "The loss must not exceed 50 % for every class, tested on "
            "the grading that will actually be used in the concrete.",
        ), 0, 0)
        self.coarse_abrasion_spin = self._pct_spin()
        self.coarse_abrasion_spin.setToolTip(
            "Table 3: abrasion loss (Test Method C 131 or C 535) shall not "
            "exceed 50 % for every class."
        )
        f4.addWidget(self.coarse_abrasion_spin, 0, 1)

        self.coarse_slag_check = QCheckBox(
            "Blast-furnace slag (abrasion exempt)"
        )
        self.coarse_slag_check.setToolTip(
            "Table 3 Footnote A: crushed air-cooled blast-furnace slag is "
            "excluded from the abrasion requirements, but its rodded or "
            "jigged unit weight shall be not less than 1120 kg/m³ "
            "(70 lb/ft³) at the grading used in the concrete."
        )
        self.coarse_slag_check.toggled.connect(self._on_coarse_slag_toggled)
        f4.addWidget(self._field_with_info(
            self.coarse_slag_check,
            "Blast-furnace slag (Footnote A)\n\n"
            "Air-cooled blast-furnace slag is excluded from the abrasion "
            "test — but to ensure it is not too weak or porous, its "
            "rodded or jigged unit weight must be at least 1120 kg/m³ "
            "(70 lb/ft³), measured at the grading used in the concrete.\n\n"
            "Tick this and enter the measured unit weight below.",
        ), 1, 0, 1, 2)

        self.coarse_slag_weight_spin = QDoubleSpinBox()
        self.coarse_slag_weight_spin.setRange(0.0, 5000.0)
        self.coarse_slag_weight_spin.setDecimals(0)
        self.coarse_slag_weight_spin.setSingleStep(10.0)
        self.coarse_slag_weight_spin.setValue(1120)
        self.coarse_slag_weight_spin.setSuffix(" kg/m³")
        self.coarse_slag_weight_spin.setEnabled(False)
        self.coarse_slag_weight_spin.setToolTip(
            "Rodded or jigged unit weight of the slag (Test Method "
            "C 29/C 29M) — minimum 1120 kg/m³ (70 lb/ft³)."
        )
        f4.addWidget(self._label_with_info(
            "Slag unit weight",
            "Slag unit weight (Footnote A)\n\n"
            "Rodded or jigged unit weight of the slag by Test Method "
            "C 29/C 29M — at least 1120 kg/m³ (70 lb/ft³), on the "
            "grading to be used in the concrete.",
        ), 2, 0)
        f4.addWidget(self.coarse_slag_weight_spin, 2, 1)

        f4.addWidget(self._label_with_info(
            "Soundness salt used (Footnote B)",
            "Soundness salt (Table 3, Footnote B)\n\n"
            "Same five-cycle weathering test as for sand (Test Method "
            "C 88). Pick the salt your laboratory used: the weight-loss "
            "limit is 18 % with magnesium sulfate or 12 % with sodium "
            "sulfate (Footnote B).\n\n"
            "Only required for the exposed classes (3S/4S/5S, "
            "3M/4M/5M) — Table 3 shows no requirement for the others.",
        ), 3, 0)
        self.coarse_soundness_salt_combo = _shrinkable_combo(QComboBox())
        self.coarse_soundness_salt_combo.addItem("Not tested", "")
        self.coarse_soundness_salt_combo.addItem(
            "Magnesium sulfate (max 18 %)", "magnesium"
        )
        self.coarse_soundness_salt_combo.addItem(
            "Sodium sulfate (max 12 %)", "sodium"
        )
        self.coarse_soundness_salt_combo.setToolTip(
            "Table 3 Footnote B: five soundness cycles (Test Method C 88); "
            "loss not greater than 18 % with magnesium sulfate or 12 % with "
            "sodium sulfate."
        )
        f4.addWidget(self.coarse_soundness_salt_combo, 3, 1)

        f4.addWidget(self._label_with_info(
            "Soundness loss (5 cycles)",
            "Soundness loss (Table 3, Footnote B)\n\n"
            "The weighted average mass lost after the five soundness "
            "cycles. Compared against 18 % (magnesium sulfate) or 12 % "
            "(sodium sulfate) per the salt chosen above.",
        ), 4, 0)
        self.coarse_soundness_spin = self._pct_spin()
        self.coarse_soundness_spin.setToolTip(
            "Weighted average loss after five soundness cycles; the limit "
            "follows the salt selected above."
        )
        f4.addWidget(self.coarse_soundness_spin, 4, 1)
        f4.setColumnStretch(2, 1)
        v.addWidget(g4)

        # Reactive materials (11.2).
        g5 = QGroupBox("Deleteriously Reactive Materials (Clause 11.2)")
        f5 = QGridLayout(g5)
        f5.setContentsMargins(12, 16, 12, 12)
        f5.setSpacing(8)
        self.coarse_reactivity_combo = self._reactivity_combo()
        f5.addWidget(self._field_with_info(
            self.coarse_reactivity_combo,
            "Deleteriously reactive materials (Clause 11.2)\n\n"
            "Some rocks contain minerals that slowly react with the "
            "alkalis in cement and make concrete swell and crack "
            "(alkali-aggregate reaction). It matters when the concrete "
            "stays damp — contact with ground, rain, or humid air.\n\n"
            "• No injuriously reactive materials → passes.\n"
            "• Reactive, but used with low-alkali cement (below 0.60 % "
            "Na₂O equivalent) or with a proven preventive material → "
            "accepted.\n"
            "• Reactive with no mitigation → fails the standard.\n\n"
            "“Not applicable” covers concrete never exposed to wetting "
            "or moisture.",
        ), 0, 0, 1, 2)
        f5.setColumnStretch(2, 1)
        v.addWidget(g5)

        v.addStretch(1)

        return page

    # ── IS 383:2016 quality pages ────────────────────────────────────

    _IS_FINE_SOURCES = [
        ("Natural sand (uncrushed)", "uncrushed"),
        ("Crushed stone sand", "crushed_stone_sand"),
        ("Crushed gravel sand", "crushed_gravel_sand"),
        ("Mixed sand (natural + crushed)", "mixed_sand"),
        ("Manufactured sand (RCA / slag / bottom ash)", "manufactured"),
    ]
    _IS_COARSE_SOURCES = [
        ("Uncrushed gravel or stone", "uncrushed"),
        ("Crushed gravel or stone", "crushed"),
        ("Manufactured (RCA / RA / slag / bottom ash)", "manufactured"),
    ]
    _IS_MANUFACTURED_TYPES = [
        ("—", ""),
        ("Iron slag aggregate", "iron_slag"),
        ("Steel slag aggregate", "steel_slag"),
        ("Copper slag aggregate", "copper_slag"),
        ("Recycled concrete aggregate (RCA)", "rca"),
        ("Recycled aggregate (RA)", "ra"),
        ("Bottom ash from thermal power plants", "bottom_ash"),
    ]
    _IS_AAR_METHODS = [
        ("Not tested", "not_tested"),
        ("Declared non-reactive", "not_reactive"),
        ("Reactive — mitigated (low-alkali cement)", "mitigated_low_alkali"),
        ("Reactive — mitigated (preventive material)", "mitigated_preventive"),
        ("Reactive — no mitigation", "reactive_unmitigated"),
        ("Mortar bar method, 38 °C", "mortar_bar_38c"),
        ("Mortar bar method, 60 °C (slowly reactive)", "mortar_bar_60c"),
        ("Accelerated mortar bar, 80 °C in 1 N NaOH", "ambt_80c"),
    ]
    _IS_AAR_AGES = [("90 days", 90), ("180 days", 180), ("16 days", 16)]

    def _build_is_fine_quality_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        v.addWidget(self._build_is_source_group("is_fine", fine=True))
        v.addWidget(self._build_is_table2_group("is_fine", fine=True))
        v.addWidget(self._build_is_organic_group("is_fine"))
        v.addWidget(self._build_is_shape_group("is_fine"))
        v.addWidget(self._build_is_soundness_group("is_fine"))
        v.addWidget(self._build_is_aar_group("is_fine"))
        mfd = self._build_is_manufactured_group("is_fine")
        mfd.setVisible(False)
        self._is_mfd_groups["is_fine"] = mfd
        v.addWidget(mfd)

        v.addStretch(1)
        return page

    def _build_is_coarse_quality_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        v.addWidget(self._build_is_source_group("is_coarse", fine=False))
        v.addWidget(self._build_is_table2_group("is_coarse", fine=False))
        v.addWidget(self._build_is_shape_group("is_coarse"))
        v.addWidget(self._build_is_mechanical_group())
        v.addWidget(self._build_is_soundness_group("is_coarse"))
        v.addWidget(self._build_is_aar_group("is_coarse"))
        mfd = self._build_is_manufactured_group("is_coarse")
        mfd.setVisible(False)
        self._is_mfd_groups["is_coarse"] = mfd
        v.addWidget(mfd)

        v.addStretch(1)
        return page

    def _build_is_source_group(self, prefix: str, fine: bool) -> QGroupBox:
        """Source classification — selects the Table 2 column."""
        grp = QGroupBox("Source Classification (Table 2 / Clause 3)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)

        combo = _shrinkable_combo(QComboBox())
        for label, data in (self._IS_FINE_SOURCES if fine else self._IS_COARSE_SOURCES):
            combo.addItem(label, data)
        combo.setMinimumWidth(150)
        setattr(self, f"{prefix}_source_combo", combo)
        combo.currentIndexChanged.connect(
            lambda *_: self._on_is_source_changed(prefix)
        )

        fine_col_info = (
            "Source classification (Clause 3 / Table 2)\n\n"
            "Table 2's deleterious-substance limits depend on the source:\n"
            "• Uncrushed (natural sand) — e.g. material finer than 75 µm "
            "≤ 3.0 %, total deleterious ≤ 5.0 %\n"
            "• Crushed sand (crushed stone / crushed gravel) — 75 µm "
            "≤ 15.0 %, total ≤ 2.0 %\n"
            "• Mixed sand — 75 µm ≤ 12.0 %, total ≤ 2.0 %\n"
            "• Manufactured sand — 75 µm ≤ 10.0 %, total ≤ 2.0 %\n\n"
            "Crushed stone sand also raises the 150 µm grading limit of "
            "Table 9 from 10 % to 20 % (Table 9 Note 1). Manufactured "
            "sources add the Table 3 (Clause 5.7) requirements below."
        )
        coarse_col_info = (
            "Source classification (Clause 3 / Table 2)\n\n"
            "Table 2's deleterious-substance limits depend on the source:\n"
            "• Uncrushed — total deleterious ≤ 5.0 %\n"
            "• Crushed — total deleterious ≤ 5.0 %\n"
            "• Manufactured — total ≤ 2.0 %, plus the Table 3 (Clause 5.7) "
            "requirements below\n\n"
            "Soft fragments (Table 2 SI iv) carry a 3.0 % limit for "
            "uncrushed and manufactured aggregate and no requirement for "
            "crushed aggregate."
        )
        f.addWidget(self._label_with_info("Source Type", fine_col_info if fine else coarse_col_info), 0, 0)
        f.addWidget(combo, 0, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_table2_group(self, prefix: str, fine: bool) -> QGroupBox:
        """Table 2 (Clause 5.2.1) deleterious substances (+ mica if fine)."""
        kind = "Fine" if fine else "Coarse"
        grp = QGroupBox(f"Deleterious Substances — Table 2 ({kind})")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)
        row = 0

        def add_pct(name: str, label: str, info: str, hi: float = 30.0) -> None:
            nonlocal row
            spin = self._pct_spin(hi=hi)
            setattr(self, f"{prefix}_{name}_spin", spin)
            spin.valueChanged.connect(lambda _=None: self._update_is_totals(prefix))
            f.addWidget(self._label_with_info(label, info), row, 0)
            f.addWidget(spin, row, 1)
            row += 1

        add_pct(
            "coal", "Coal and lignite (max 1.0 %)",
            "Coal and lignite (Table 2 SI (i), Clause 5.2.1)\n\n"
            "Soft, light particles that weaken concrete and can cause "
            "surface defects. Measured per IS 2386 (Part 2).\n\n"
            "Limit: 1.00 % by mass, maximum, for every source type.",
        )
        add_pct(
            "clay", "Clay lumps (max 1.0 %)",
            "Clay lumps and friable particles (Table 2 SI (ii), 5.2.1)\n\n"
            "Soft lumps that break up in mixing, absorb water and leave "
            "weak spots. Measured per IS 2386 (Part 2).\n\n"
            "Limit: 1.00 % by mass, maximum, for every source type.",
        )
        add_pct(
            "finer75", "Materials finer than 75 µm",
            "Material finer than the 75 µm IS Sieve (Table 2 SI (iii), "
            "5.2.1; IS 2386 Part 1)\n\n"
            "Limit depends on the declared source:\n"
            "• Fine uncrushed: 3.00 %\n"
            "• Fine crushed stone sand: 15.00 %\n"
            "• Mixed sand: 12.00 %\n"
            "• Fine manufactured: 10.00 %\n"
            "• Coarse (all sources): 1.00 %",
        )
        if fine:
            add_pct(
                "shale", "Shale",
                "Shale (Table 2 SI (v), Clause 5.2.1)\n\n"
                "Harder, platy and fissile clay stones. Determined by "
                "petrography at selection/change of source (Note 2).\n\n"
                "Fine aggregate only: 1.00 % for uncrushed and "
                "manufactured sand; no requirement for crushed / mixed "
                "sand (dash in Table 2).",
            )
            add_pct(
                "mica", "Mica",
                "Mica content (Table 2 Note 3, Clause 5.2.1)\n\n"
                "Mica harms workability, strength, abrasion resistance "
                "and durability.\n\n"
                "• No supporting tests: 1.00 % by mass\n"
                "• With workability/strength/permeability/abrasion tests: "
                "3.00 % (muscovite) or 5.00 % (muscovite + biotite)\n"
                "• Total deleterious including mica: 8.00 % (uncrushed) / "
                "5.00 % (crushed-mixed)",
            )
        else:
            add_pct(
                "soft", "Soft fragments",
                "Soft fragments (Table 2 SI (iv), Clause 5.2.1; "
                "IS 2386 Part 2)\n\n"
                "Coarse aggregate only. Limit 3.00 % for uncrushed and "
                "manufactured aggregate; no requirement for crushed "
                "aggregate (dash in Table 2).",
            )

        if fine:
            mica_type = _shrinkable_combo(QComboBox())
            mica_type.addItem("Muscovite", "muscovite")
            mica_type.addItem("Muscovite + biotite", "muscovite_biotite")
            mica_type.setMinimumWidth(150)
            setattr(self, f"{prefix}_mica_type_combo", mica_type)
            f.addWidget(self._label_with_info(
                "Mica type",
                "Table 2 Note 3: with supporting tests the limit is 3.00 % "
                "for muscovite mica alone, 5.00 % when both muscovite and "
                "biotite varieties are present.",
            ), row, 0)
            f.addWidget(mica_type, row, 1)
            row += 1

            tests = QCheckBox(
                "Supporting tests conducted (Note 3)"
            )
            setattr(self, f"{prefix}_mica_tests_check", tests)
            f.addWidget(self._field_with_info(tests,
                "Table 2 Note 3: ticking this applies the higher mica "
                "limits (3.00 % muscovite / 5.00 % muscovite + biotite) "
                "instead of the default 1.00 %, on the evidence of tests "
                "for workability, strength, permeability and abrasion.",
            ), row, 0, 1, 2)
            row += 1

        total = QLabel("Total deleterious (excl. mica): —")
        total.setWordWrap(True)
        total.setStyleSheet(
            "font-weight: 600; color: #1e40af; font-size: 12px; "
            "padding: 6px 10px; background-color: #eff4ff; "
            "border: 1px solid #dbeafe; border-radius: 4px;"
        )
        setattr(self, f"{prefix}_total_label", total)
        f.addWidget(self._label_with_info(
            "Total deleterious (Table 2 SI (vi))",
            "Total of all deleterious materials, excluding mica "
            "(Table 2 SI (vi), Clause 5.2.1).\n\n"
            "5.00 % for uncrushed aggregate (and crushed coarse); "
            "2.00 % for crushed / mixed / manufactured sand and "
            "manufactured coarse aggregate. Computed live from the "
            "components entered above.",
        ), row, 0)
        f.addWidget(total, row, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_organic_group(self, prefix: str) -> QGroupBox:
        """Clause 5.2 Note 4 — organic impurities (fine aggregate)."""
        grp = QGroupBox("Organic Impurities (Clause 5.2 Note 4)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)

        combo = _shrinkable_combo(QComboBox())
        combo.addItem("Not tested", "not_tested")
        combo.addItem("Colour not darker than the standard — passes", "pass")
        combo.addItem(
            "Darker — verified by IS 2386 (Part 6) mortar strength",
            "fail_color_relieved",
        )
        combo.addItem("Darker — no relief applies", "fail_color")
        combo.setMinimumWidth(150)
        setattr(self, f"{prefix}_organic_combo", combo)

        strength = QDoubleSpinBox()
        strength.setRange(0.0, 200.0)
        strength.setDecimals(1)
        strength.setSingleStep(0.5)
        strength.setValue(95.0)
        strength.setSuffix(" %")
        strength.setEnabled(False)
        setattr(self, f"{prefix}_organic_strength_spin", strength)

        combo.currentIndexChanged.connect(
            lambda *_: strength.setEnabled(
                combo.currentData() == "fail_color_relieved"
            )
        )

        f.addWidget(self._label_with_info(
            "Colour test [IS 2386 (Part 2)]",
            "Organic impurities (Clause 5.2 Note 4)\n\n"
            "Aggregate shall not contain harmful organic impurities in "
            "quantities that adversely affect strength or durability.\n\n"
            "A fine aggregate failing the colour test may still be used "
            "when the relative strength of mortar made with it, tested "
            "per IS 2386 (Part 6), is not less than 95 % at 7 and 28 days.",
        ), 0, 0)
        f.addWidget(combo, 0, 1)
        f.addWidget(self._label_with_info(
            "Relative strength (7 & 28 days)",
            "IS 2386 (Part 6) mortar relative strength, entered when the "
            "colour test is darker but the aggregate may still be "
            "accepted. Minimum 95 % (Clause 5.2 Note 4).",
        ), 1, 0)
        f.addWidget(strength, 1, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_shape_group(self, prefix: str) -> QGroupBox:
        """Clause 5.3 — combined flakiness and elongation index."""
        grp = QGroupBox("Flakiness & Elongation (Clause 5.3)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)

        def idx_spin(name: str) -> QDoubleSpinBox:
            spin = self._pct_spin(hi=100.0)
            setattr(self, f"{prefix}_{name}_spin", spin)
            return spin

        combined = QLabel("Combined FI + EI: —")
        combined.setWordWrap(True)
        combined.setStyleSheet(
            "font-weight: 600; color: #1e40af; font-size: 12px; "
            "padding: 6px 10px; background-color: #eff4ff; "
            "border: 1px solid #dbeafe; border-radius: 4px;"
        )
        setattr(self, f"{prefix}_combined_shape_label", combined)

        fi = idx_spin("fi")
        ei = idx_spin("ei")
        fi.valueChanged.connect(lambda _=None: self._update_is_totals(prefix))
        ei.valueChanged.connect(lambda _=None: self._update_is_totals(prefix))

        f.addWidget(self._label_with_info(
            "Flakiness index (FI)",
            "Flakiness index per IS 2386 (Part 1) — the mass percentage of "
            "particles whose least dimension is less than 0.6 times their "
            "mean size.",
        ), 0, 0)
        f.addWidget(fi, 0, 1)
        f.addWidget(self._label_with_info(
            "Elongation index (EI)",
            "Elongation index per IS 2386 (Part 1) — determined on the "
            "SAME sample after removing the flaky material (Clause 5.3): "
            "the mass percentage of particles whose greatest length "
            "exceeds 1.8 times their mean size.",
        ), 1, 0)
        f.addWidget(ei, 1, 1)
        f.addWidget(self._label_with_info(
            "Combined index (max 40 %)",
            "Combined flakiness and elongation index (Clause 5.3): the "
            "two indices are added numerically and shall not exceed "
            "40 % for uncrushed or crushed aggregate. The "
            "engineer-in-charge may relax the limit on evidence of "
            "performance.",
        ), 2, 0)
        f.addWidget(combined, 2, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_soundness_group(self, prefix: str) -> QGroupBox:
        """Clause 5.5.1 — soundness, 5 cycles (guide limits of the Note)."""
        fine = prefix == "is_fine"
        grp = QGroupBox("Soundness (Clause 5.5.1, 5 Cycles)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)

        salt = _shrinkable_combo(QComboBox())
        salt.addItem("Not tested", "")
        salt.addItem("Sodium sulphate", "sodium")
        salt.addItem("Magnesium sulphate", "magnesium")
        salt.setMinimumWidth(150)
        setattr(self, f"{prefix}_soundness_salt_combo", salt)

        loss = self._pct_spin(hi=100.0)
        setattr(self, f"{prefix}_soundness_spin", loss)

        limits = (
            "fine: 10 % sodium / 15 % magnesium"
            if fine else
            "coarse: 12 % sodium / 18 % magnesium"
        )
        f.addWidget(self._label_with_info(
            "Salt used [IS 2386 (Part 5)]",
            f"Clause 5.5.1 Note — guide limits for average loss after "
            f"5 cycles ({limits}). Required for concrete liable to frost "
            "action; exact limits by agreement between purchaser and "
            "supplier.",
        ), 0, 0)
        f.addWidget(salt, 0, 1)
        f.addWidget(self._label_with_info(
            "Average loss after 5 cycles",
            f"Average loss of mass after five soundness cycles "
            f"({limits}, Clause 5.5.1 Note).",
        ), 1, 0)
        f.addWidget(loss, 1, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_aar_group(self, prefix: str) -> QGroupBox:
        """Clause 5.6 — alkali-aggregate reaction."""
        grp = QGroupBox("Alkali-Aggregate Reaction (Clause 5.6)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)

        combo = _shrinkable_combo(QComboBox())
        for label, data in self._IS_AAR_METHODS:
            combo.addItem(label, data)
        combo.setMinimumWidth(150)
        setattr(self, f"{prefix}_aar_combo", combo)

        expansion = QDoubleSpinBox()
        expansion.setRange(0.0, 5.0)
        expansion.setDecimals(3)
        expansion.setSingleStep(0.005)
        expansion.setValue(0.050)
        expansion.setSuffix(" %")
        expansion.setEnabled(False)
        setattr(self, f"{prefix}_aar_expansion_spin", expansion)

        age = _shrinkable_combo(QComboBox())
        for label, data in self._IS_AAR_AGES:
            age.addItem(label, data)
        age.setMinimumWidth(150)
        age.setEnabled(False)
        setattr(self, f"{prefix}_aar_age_combo", age)

        numeric = ("mortar_bar_38c", "mortar_bar_60c", "ambt_80c")

        def _on_method_change() -> None:
            is_numeric = combo.currentData() in numeric
            expansion.setEnabled(is_numeric)
            age.setEnabled(is_numeric)
        combo.currentIndexChanged.connect(lambda *_: _on_method_change())

        f.addWidget(self._label_with_info(
            "Test outcome / method",
            "Alkali-aggregate reactivity (Clause 5.6, IS 2386 Part 7)\n\n"
            "Damage needs moisture + high-alkali cement + a reactive "
            "constituent together. Limits:\n"
            "• Mortar bar 38 °C: 0.05 % at 90 days / 0.10 % at 180 days\n"
            "• Mortar bar 60 °C (slowly reactive): 0.05 % at 90 days / "
            "0.06 % at 180 days\n"
            "• Accelerated mortar bar 80 °C (1 N NaOH): < 0.10 % at 16 "
            "days innocuous; > 0.20 % deleterious; between is "
            "inconclusive.",
        ), 0, 0)
        f.addWidget(combo, 0, 1)
        f.addWidget(self._label_with_info(
            "Expansion",
            "Measured expansion of the selected method.",
        ), 1, 0)
        f.addWidget(expansion, 1, 1)
        f.addWidget(self._label_with_info(
            "Test age",
            "Limits are fixed to the ages of Clause 5.6: 90 / 180 days "
            "for the mortar-bar methods, 16 days after casting for the "
            "accelerated mortar-bar test.",
        ), 2, 0)
        f.addWidget(age, 2, 1)
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_mechanical_group(self) -> QGroupBox:
        """Clause 5.4 — crushing value, impact value, abrasion."""
        grp = QGroupBox("Mechanical Properties (Clause 5.4)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)
        row = 0

        wearing = QCheckBox(
            "Wearing surfaces (roads, pavements, spillways…)"
        )
        self.is_coarse_wearing_check = wearing
        f.addWidget(self._field_with_info(wearing,
            "Clause 5.4: stricter limits apply to wearing surfaces — "
            "crushing value and impact value ≤ 30 %, abrasion ≤ 30 %. "
            "For other concrete the limits are: impact ≤ 45 %, abrasion "
            "≤ 50 %, and a crushing value above 30 % calls for the ten "
            "percent fines test (minimum load 50 kN).",
        ), row, 0, 1, 2)
        row += 1

        high_grade = QCheckBox("Concrete of grade M65 or above")
        self.is_coarse_high_grade_check = high_grade
        f.addWidget(self._field_with_info(high_grade,
            "Clause 5.4 Note: for grades M65 and above stronger "
            "aggregates are required — crushing value and impact value "
            "shall not exceed 22 %.",
        ), row, 0, 1, 2)
        row += 1

        def add_pct(name: str, label: str, info: str, hi: float = 100.0,
                    suffix: str = " %") -> None:
            nonlocal row
            spin = self._pct_spin(hi=hi)
            spin.setSuffix(suffix)
            setattr(self, f"is_coarse_{name}_spin", spin)
            f.addWidget(self._label_with_info(label, info), row, 0)
            f.addWidget(spin, row, 1)
            row += 1

        add_pct(
            "acv", "Aggregate crushing value (ACV)",
            "Aggregate crushing value per IS 2386 (Part 4), Clause "
            "5.4.1:\n"
            "• Wearing surfaces: ≤ 30 %\n"
            "• Other concrete: if ACV > 30 %, the ten percent fines load "
            "must be at least 50 kN\n"
            "• Grades M65+: ≤ 22 % (Clause 5.4 Note)",
        )
        fines = QDoubleSpinBox()
        fines.setRange(_NOT_TESTED, 1000.0)
        fines.setDecimals(0)
        fines.setSingleStep(5)
        fines.setValue(_NOT_TESTED)
        fines.setSuffix(" kN")
        fines.setSpecialValueText("not tested")
        fines.setMinimumWidth(130)
        self.is_coarse_ten_pct_fines_spin = fines
        f.addWidget(self._label_with_info(
            "Ten percent fines load",
            "Ten percent fines value, IS 2386 (Part 4), Clause 5.4.1(b): "
            "required when the crushing value exceeds 30 % for concrete "
            "other than wearing surfaces — the minimum load shall be "
            "50 kN.",
        ), row, 0)
        f.addWidget(fines, row, 1)
        row += 1
        add_pct(
            "aiv", "Aggregate impact value (AIV)",
            "Aggregate impact value per IS 2386 (Part 4), Clause 5.4.2 "
            "(may replace the crushing-value test):\n"
            "• Wearing surfaces: ≤ 30 %\n"
            "• Other concrete: ≤ 45 %\n"
            "• Grades M65+: ≤ 22 % (Clause 5.4 Note)",
        )
        add_pct(
            "abrasion", "Abrasion value (Los Angeles)",
            "Aggregate abrasion value per IS 2386 (Part 4) with the Los "
            "Angeles machine, Clause 5.4.3:\n"
            "• Wearing surfaces: ≤ 30 %\n"
            "• Other concrete: ≤ 50 %",
        )
        f.setColumnStretch(2, 1)
        return grp

    def _build_is_manufactured_group(self, prefix: str) -> QGroupBox:
        """Clause 5.7 / Table 3 — additional requirements for manufactured
        aggregates (shown only when the source is manufactured)."""
        grp = QGroupBox("Manufactured Aggregate (Clause 5.7, Table 3)")
        f = QGridLayout(grp)
        f.setContentsMargins(12, 16, 12, 12)
        f.setSpacing(8)
        row = 0

        mtype = _shrinkable_combo(QComboBox())
        for label, data in self._IS_MANUFACTURED_TYPES:
            mtype.addItem(label, data)
        mtype.setMinimumWidth(150)
        setattr(self, f"{prefix}_mfd_type_combo", mtype)
        f.addWidget(self._label_with_info(
            "Manufactured type",
            "Table 1 (Clause 4.2.1) caps utilization as a percent of the "
            "total aggregate mass — e.g. iron slag 50 % plain / 25 % "
            "reinforced; steel slag 25 % plain / Nil reinforced; RCA 25 % "
            "plain / 20 % reinforced (up to M25 only); RA Nil except lean "
            "concrete; bottom ash 25 % lean; copper slag 40 / 35 %. "
            "Manufactured aggregates are not permitted in prestressed "
            "concrete (Clause 4.2.2).",
        ), row, 0)
        f.addWidget(mtype, row, 1)
        row += 1

        def add_pct(name: str, label: str, info: str, hi: float) -> None:
            nonlocal row
            # decimals=2 so the 0.3 / 0.5 / 0.04 % limits of Table 3 are
            # enterable exactly.
            spin = self._pct_spin(hi=hi, step=0.01, decimals=2)
            setattr(self, f"{prefix}_mfd_{name}_spin", spin)
            f.addWidget(self._label_with_info(label, info), row, 0)
            f.addWidget(spin, row, 1)
            row += 1

        add_pct(
            "alkali", "Total alkali (Na₂O equivalent, max 0.3 %)",
            "Table 3 (Clause 5.7): total alkali content as Na₂O "
            "equivalent, maximum 0.3 %.",
            hi=5.0,
        )
        add_pct(
            "sulphate", "Total sulphate (SO₃, max 0.5 %)",
            "Table 3 (Clause 5.7): total sulphate content as SO₃, "
            "maximum 0.5 %.",
            hi=10.0,
        )
        add_pct(
            "chloride", "Acid soluble chloride (max 0.04 %)",
            "Table 3 (Clause 5.7): acid soluble chloride content, "
            "maximum 0.04 % (tested per IS 14959 Part 2).",
            hi=5.0,
        )
        add_pct(
            "absorption", "Water absorption (max 5 %)",
            "Table 3 (Clause 5.7): water absorption, maximum 5 %. For RCA "
            "and RA up to 10 % may be permitted subject to pre-wetting "
            "(saturation) before batching and mixing (Note 1).",
            hi=20.0,
        )
        sg = QDoubleSpinBox()
        sg.setRange(0.0, 5.0)
        sg.setDecimals(2)
        sg.setSingleStep(0.05)
        sg.setValue(2.60)
        sg.setSpecialValueText("not tested")
        setattr(self, f"{prefix}_mfd_sg_spin", sg)
        f.addWidget(self._label_with_info(
            "Specific gravity (2.1 – 3.2)",
            "Table 3 (Clause 5.7): specific gravity 2.1 to 3.2 for "
            "normal-weight concrete. Copper slag up to 3.8 is permitted "
            "for part replacement provided the blend average stays "
            "≤ 3.2 (Note 3).",
        ), row, 0)
        f.addWidget(sg, row, 1)
        row += 1

        prewet = QCheckBox(
            "RCA / RA pre-wetted (Table 3 Note 1)"
        )
        setattr(self, f"{prefix}_mfd_prewetted_check", prewet)
        f.addWidget(self._field_with_info(prewet,
            "Table 3 Note 1: for recycled concrete aggregate and recycled "
            "aggregate the absorption limit rises to 10 % subject to "
            "pre-wetting (saturation) of the aggregate before batching "
            "and mixing.",
        ), row, 0, 1, 2)
        f.setColumnStretch(2, 1)
        return grp

    # ── IS 383 quality: dynamic behaviour and gathering ──────────────

    def _on_is_source_changed(self, prefix: str) -> None:
        """React to a source-type change: manufactured block + live totals."""
        combo = getattr(self, f"{prefix}_source_combo", None)
        if combo is not None:
            group = self._is_mfd_groups.get(prefix)
            if group is not None:
                group.setVisible(combo.currentData() == "manufactured")
        self._update_is_totals(prefix)

    def _update_is_totals(self, prefix: str) -> None:
        """Live total-deleterious and combined FI + EI labels."""
        label = getattr(self, f"{prefix}_total_label", None)
        if label is not None:
            names = (
                ("coal", "clay", "finer75", "shale")
                if prefix == "is_fine"
                else ("coal", "clay", "finer75", "soft")
            )
            total = 0.0
            for name in names:
                spin = getattr(self, f"{prefix}_{name}_spin", None)
                if spin is not None and spin.value() >= 0.0:
                    total += spin.value()
            label.setText(f"Total deleterious (excl. mica): {total:.2f} %")

        shape = getattr(self, f"{prefix}_combined_shape_label", None)
        if shape is not None:
            fi = getattr(self, f"{prefix}_fi_spin", None)
            ei = getattr(self, f"{prefix}_ei_spin", None)
            if fi is not None and ei is not None:
                fiv = fi.value() if fi.value() >= 0.0 else 0.0
                eiv = ei.value() if ei.value() >= 0.0 else 0.0
                shape.setText(
                    f"Combined FI + EI: {fiv + eiv:.1f} % (max 40 %)"
                )

    def _gather_is_fine_quality_inputs(self) -> IS383FineQualityInputs:
        def optional(spin: QDoubleSpinBox) -> float | None:
            value = spin.value()
            return None if value == _NOT_TESTED else value

        combo = self.is_fine_organic_combo
        relieved = combo.currentData() == "fail_color_relieved"
        aar = self.is_fine_aar_combo.currentData()
        numeric_aar = aar in ("mortar_bar_38c", "mortar_bar_60c", "ambt_80c")
        return IS383FineQualityInputs(
            source_type=self.is_fine_source_combo.currentData(),
            coal_lignite_pct=optional(self.is_fine_coal_spin),
            clay_lumps_pct=optional(self.is_fine_clay_spin),
            finer_75um_pct=optional(self.is_fine_finer75_spin),
            shale_pct=optional(self.is_fine_shale_spin),
            mica_pct=optional(self.is_fine_mica_spin),
            mica_type=self.is_fine_mica_type_combo.currentData(),
            mica_tests_conducted=self.is_fine_mica_tests_check.isChecked(),
            organic_status=combo.currentData(),
            organic_relative_strength_pct=(
                self.is_fine_organic_strength_spin.value() if relieved else None
            ),
            flakiness_index_pct=optional(self.is_fine_fi_spin),
            elongation_index_pct=optional(self.is_fine_ei_spin),
            soundness_loss_pct=optional(self.is_fine_soundness_spin),
            soundness_salt=self.is_fine_soundness_salt_combo.currentData(),
            aar_method=aar,
            aar_expansion_pct=(
                self.is_fine_aar_expansion_spin.value() if numeric_aar else None
            ),
            aar_age_days=(
                self.is_fine_aar_age_combo.currentData() if numeric_aar else None
            ),
            manufactured_type=self.is_fine_mfd_type_combo.currentData(),
            manufactured_alkali_pct=optional(self.is_fine_mfd_alkali_spin),
            manufactured_sulphate_pct=optional(self.is_fine_mfd_sulphate_spin),
            manufactured_chloride_pct=optional(self.is_fine_mfd_chloride_spin),
            manufactured_absorption_pct=optional(self.is_fine_mfd_absorption_spin),
            manufactured_specific_gravity=(
                self.is_fine_mfd_sg_spin.value()
                if self.is_fine_mfd_sg_spin.value() > 0.0 else None
            ),
            rca_prewetted=self.is_fine_mfd_prewetted_check.isChecked(),
        )

    def _gather_is_coarse_quality_inputs(self) -> IS383CoarseQualityInputs:
        def optional(spin: QDoubleSpinBox) -> float | None:
            value = spin.value()
            return None if value == _NOT_TESTED else value

        aar = self.is_coarse_aar_combo.currentData()
        numeric_aar = aar in ("mortar_bar_38c", "mortar_bar_60c", "ambt_80c")
        fines = self.is_coarse_ten_pct_fines_spin
        return IS383CoarseQualityInputs(
            source_type=self.is_coarse_source_combo.currentData(),
            coal_lignite_pct=optional(self.is_coarse_coal_spin),
            clay_lumps_pct=optional(self.is_coarse_clay_spin),
            finer_75um_pct=optional(self.is_coarse_finer75_spin),
            soft_fragments_pct=optional(self.is_coarse_soft_spin),
            flakiness_index_pct=optional(self.is_coarse_fi_spin),
            elongation_index_pct=optional(self.is_coarse_ei_spin),
            wearing_surfaces=self.is_coarse_wearing_check.isChecked(),
            high_grade=self.is_coarse_high_grade_check.isChecked(),
            crushing_value_pct=optional(self.is_coarse_acv_spin),
            ten_pct_fines_load_kn=(
                fines.value() if fines.value() != _NOT_TESTED else None
            ),
            impact_value_pct=optional(self.is_coarse_aiv_spin),
            abrasion_loss_pct=optional(self.is_coarse_abrasion_spin),
            soundness_loss_pct=optional(self.is_coarse_soundness_spin),
            soundness_salt=self.is_coarse_soundness_salt_combo.currentData(),
            aar_method=aar,
            aar_expansion_pct=(
                self.is_coarse_aar_expansion_spin.value() if numeric_aar else None
            ),
            aar_age_days=(
                self.is_coarse_aar_age_combo.currentData() if numeric_aar else None
            ),
            manufactured_type=self.is_coarse_mfd_type_combo.currentData(),
            manufactured_alkali_pct=optional(self.is_coarse_mfd_alkali_spin),
            manufactured_sulphate_pct=optional(self.is_coarse_mfd_sulphate_spin),
            manufactured_chloride_pct=optional(self.is_coarse_mfd_chloride_spin),
            manufactured_absorption_pct=optional(self.is_coarse_mfd_absorption_spin),
            manufactured_specific_gravity=(
                self.is_coarse_mfd_sg_spin.value()
                if self.is_coarse_mfd_sg_spin.value() > 0.0 else None
            ),
            rca_prewetted=self.is_coarse_mfd_prewetted_check.isChecked(),
        )

    def _run_is383_checks(self, result: PSDResult) -> list:
        """Evaluate every IS 383:2016 clause for the current analysis."""
        band_key = self.band_combo.currentData()
        band = self._current_band(band_key)
        if self.agg_combo.currentData() == "fine":
            zone = band_key[2] if band_key is not None and len(band_key) > 2 else None
            return evaluate_is383_fine(
                result, band, self._gather_is_fine_quality_inputs(), zone=zone
            )
        return evaluate_is383_coarse(
            result, band, self._gather_is_coarse_quality_inputs()
        )

    def _reactivity_combo(self) -> QComboBox:
        """Shared Clause 7.3 / 11.2 reactive-materials selector."""
        combo = _shrinkable_combo(QComboBox())
        combo.addItem("Not tested", "not_tested")
        combo.addItem(
            "Not applicable — concrete not exposed to wetting or moisture",
            "not_exposed",
        )
        combo.addItem("No injuriously reactive materials present", "not_reactive")
        combo.addItem(
            "Reactive — used with low-alkali cement (< 0.60 % Na₂O eq)",
            "low_alkali_cement",
        )
        combo.addItem(
            "Reactive — used with a proven preventive material",
            "preventive_material",
        )
        combo.addItem("Reactive — no mitigation", "reactive_unmitigated")
        combo.setMinimumWidth(150)
        combo.setToolTip(
            "Clause 7.3 / 11.2: for concrete subject to wetting, extended "
            "exposure to humid atmosphere or contact with moist ground, "
            "deleteriously reactive materials are only permitted with a "
            "cement containing less than 0.60 % alkalies (Na₂O + 0.658K₂O) "
            "or with a material shown to prevent harmful expansion "
            "(Appendix X1 lists evaluation methods)."
        )
        return combo

    # ── Quality-page behaviour ───────────────────────────────────────

    def _on_fine_fm_variation_toggled(self, checked: bool) -> None:
        self.fine_base_fm_spin.setEnabled(checked)

    def _on_fine_organic_changed(self) -> None:
        self.fine_c87_spin.setEnabled(
            self.fine_organic_combo.currentData() == "darker_c87"
        )

    def _on_coarse_weighted_toggled(self, checked: bool) -> None:
        for spin in (
            self.coarse_p_spin,
            self.coarse_t_spin,
            self.coarse_a_spin,
        ):
            spin.setEnabled(checked)

    def _on_coarse_slag_toggled(self, checked: bool) -> None:
        self.coarse_slag_weight_spin.setEnabled(checked)

    def _update_coarse_sum_label(self) -> None:
        """Live 'sum of deleterious substances' (Table 3 column 3)."""
        clay = self.coarse_clay_spin.value()
        chert = self.coarse_chert_spin.value()
        if clay == _NOT_TESTED or chert == _NOT_TESTED:
            self.coarse_sum_label.setText("—")
            self.coarse_sum_label.setToolTip(
                "Sum of clay lumps, friable particles and chert; enter both "
                "components above to evaluate the Table 3 sum limit."
            )
            return
        total = clay + chert
        self.coarse_sum_label.setText(f"{total:.1f} %")
        self.coarse_sum_label.setToolTip(
            "Table 3 column 'Sum of Clay Lumps, Friable Particles, and "
            "Chert (Less Than 2.40 sp gr SSD)' — computed as the sum of the "
            "two entries above."
        )

    def _update_quality_visibility(self) -> None:
        """Show the quality group for either standard and match the page."""
        standard = self.standard_combo.currentData()
        show = standard in ("astm_c33", "is383")
        self._quality_group.setVisible(show)
        if not show:
            return
        fine = self.agg_combo.currentData() == "fine"
        if standard == "astm_c33":
            self._quality_group.setTitle("ASTM C33 Quality Requirements")
            self._quality_hint.setText(
                "Enter the laboratory results for the clauses you want "
                "checked; fields left at “not tested” are skipped. Limits "
                "and conditions are applied automatically per the cited "
                "clause of ASTM C 33 – 99."
            )
            self._quality_stack.setCurrentIndex(0 if fine else 1)
        else:
            self._quality_group.setTitle("IS 383 Quality Requirements")
            self._quality_hint.setText(
                "Enter the laboratory results for the clauses you want "
                "checked; fields left at “not tested” are skipped. Limits "
                "and conditions are applied automatically per the cited "
                "clause of IS 383 : 2016."
            )
            self._quality_stack.setCurrentIndex(2 if fine else 3)

    def _gather_fine_quality_inputs(self) -> FineQualityInputs:
        def optional(spin: QDoubleSpinBox) -> float | None:
            value = spin.value()
            return None if value == _NOT_TESTED else value

        c87 = (
            self.fine_c87_spin.value()
            if self.fine_organic_combo.currentData() == "darker_c87"
            else None
        )
        return FineQualityInputs(
            check_fm_variation=self.fine_fm_variation_check.isChecked(),
            base_fineness_modulus=(
                self.fine_base_fm_spin.value()
                if self.fine_fm_variation_check.isChecked()
                else None
            ),
            clay_lumps_pct=optional(self.fine_clay_spin),
            finer_75um_pct=optional(self.fine_finer_75um_spin),
            coal_lignite_pct=optional(self.fine_coal_spin),
            concrete_subject_to_abrasion=self.fine_abrasion_check.isChecked(),
            surface_appearance_important=self.fine_appearance_check.isChecked(),
            manufactured_sand_dust_of_fracture=(
                self.fine_manufactured_check.isChecked()
            ),
            organic_status=self.fine_organic_combo.currentData(),
            c87_relative_strength_pct=c87,
            soundness_loss_pct=optional(self.fine_soundness_spin),
            soundness_salt=self.fine_soundness_salt_combo.currentData(),
            reactivity_status=self.fine_reactivity_combo.currentData(),
        )

    def _gather_coarse_quality_inputs(self) -> CoarseQualityInputs:
        def optional(spin: QDoubleSpinBox) -> float | None:
            value = spin.value()
            return None if value == _NOT_TESTED else value

        return CoarseQualityInputs(
            class_designation=self.coarse_class_combo.currentData() or "",
            clay_lumps_pct=optional(self.coarse_clay_spin),
            chert_pct=optional(self.coarse_chert_spin),
            finer_75um_pct=optional(self.coarse_finer_75um_spin),
            coal_lignite_pct=optional(self.coarse_coal_spin),
            abrasion_loss_pct=optional(self.coarse_abrasion_spin),
            soundness_loss_pct=optional(self.coarse_soundness_spin),
            soundness_salt=self.coarse_soundness_salt_combo.currentData(),
            is_slag=self.coarse_slag_check.isChecked(),
            slag_unit_weight_kg_m3=(
                self.coarse_slag_weight_spin.value()
                if self.coarse_slag_check.isChecked()
                else None
            ),
            essentially_clay_free=self.coarse_clay_free_check.isChecked(),
            weighted_limit_enabled=self.coarse_weighted_check.isChecked(),
            p_sand_pct=(
                self.coarse_p_spin.value()
                if self.coarse_weighted_check.isChecked()
                else None
            ),
            t_fine_limit_pct=(
                self.coarse_t_spin.value()
                if self.coarse_weighted_check.isChecked()
                else None
            ),
            a_fine_actual_pct=(
                self.coarse_a_spin.value()
                if self.coarse_weighted_check.isChecked()
                else None
            ),
            reactivity_status=self.coarse_reactivity_combo.currentData(),
        )

    def _run_astm_c33_checks(self, result: PSDResult) -> list:
        """Evaluate every ASTM C33 clause for the current analysis."""
        band_key = self.band_combo.currentData()
        band = self._current_band(band_key)
        if self.agg_combo.currentData() == "fine":
            return evaluate_astm_c33_fine(
                result, band, self._gather_fine_quality_inputs()
            )
        return evaluate_astm_c33_coarse(
            result, band, self._gather_coarse_quality_inputs()
        )

    def _show_astm_compliance_dialog(self, checks: list) -> None:
        """Open the clause-cited non-conformance dialog (user request).

        Works for either grading standard; the title and footnote follow
        the standard currently selected on the PSD tab.
        """
        aggregate_kind = self.agg_combo.currentData() or "fine"
        standard_name = (
            "IS 383" if self.standard_combo.currentData() == "is383"
            else "ASTM C33"
        )
        dialog = ASTM_C33ComplianceDialog(
            checks, aggregate_kind, self, standard_name=standard_name
        )
        dialog.exec()

    # ── Dynamic table rebuild ────────────────────────────────────────

    def _current_sieves(self) -> list[float]:
        standard = self.standard_combo.currentData()
        aggregate_type = self.agg_combo.currentData()
        return STANDARD_SIEVES_BY_CODE[standard][aggregate_type]

    def _rebuild_table(self) -> None:
        """Rebuild the input table rows for the current aggregate type."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        sieves = self._current_sieves()
        self.table.setRowCount(len(sieves) + 2)  # +pan +total

        for i, s in enumerate(sieves):
            # Sieve size (read-only)
            size_item = QTableWidgetItem(_fmt_size(s))
            size_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            size_item.setData(Qt.ItemDataRole.UserRole, s)
            self.table.setItem(i, 0, size_item)

            # Mass retained (editable) — styled to stand out as the input column
            mass_item = QTableWidgetItem("0")
            mass_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
            )
            mass_item.setBackground(QColor("#eff6ff"))
            mass_item.setForeground(QColor("#1e40af"))
            self.table.setItem(i, 1, mass_item)

            # Computed and selected-standard columns (read-only)
            for col in (2, 3, 4, 5):
                item = QTableWidgetItem("—")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, col, item)

        # Pan row
        pan_row = len(sieves)
        pan_size = QTableWidgetItem("Pan (passing finest)")
        pan_size.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(pan_row, 0, pan_size)
        pan_mass = QTableWidgetItem("0")
        pan_mass.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
        pan_mass.setBackground(QColor("#eff6ff"))
        pan_mass.setForeground(QColor("#1e40af"))
        self.table.setItem(pan_row, 1, pan_mass)
        for col in (2, 3, 4, 5):
            item = QTableWidgetItem("—")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(pan_row, col, item)

        # Total row
        total_row = len(sieves) + 1
        total_lbl = QTableWidgetItem("Total Mass")
        total_lbl.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(total_row, 0, total_lbl)
        total_val = QTableWidgetItem("0 g")
        total_val.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(total_row, 1, total_val)
        for col in (2, 3, 4, 5):
            item = QTableWidgetItem("—")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(total_row, col, item)

        self.table.blockSignals(False)
        self._update_standard_limit_column()
        self._recompute_table()

    def _rebuild_band_combo(self) -> None:
        """Populate references for the selected standard and aggregate type."""
        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        standard = self.standard_combo.currentData()
        aggregate_type = self.agg_combo.currentData()

        if standard == "is383" and aggregate_type == "fine":
            for zone in FINE_ZONES:
                self.band_combo.addItem(
                    f"IS 383 Grading Zone {zone}",
                    ("is383", "fine", zone),
                )
            self.band_combo.setCurrentIndex(FINE_ZONES.index("II"))
        elif standard == "astm_c33" and aggregate_type == "fine":
            self.band_combo.addItem(
                "ASTM C33 Fine Aggregate (Table 1)",
                ("astm_c33", "fine", "table1"),
            )
        elif standard == "is383":
            for nominal_size in IS_GRADED_NOMINAL_SIZES:
                self.band_combo.addItem(
                    f"Graded — {nominal_size:g} mm nominal (IS Table 7)",
                    ("is383", "coarse", "graded", nominal_size),
                )
            for nominal_size in IS_SINGLE_SIZED_NOMINAL_SIZES:
                self.band_combo.addItem(
                    f"Single-sized — {nominal_size:g} mm nominal (IS Table 7)",
                    ("is383", "coarse", "single", nominal_size),
                )
            # Default to the common 20 mm graded aggregate.
            self.band_combo.setCurrentIndex(IS_GRADED_NOMINAL_SIZES.index(20))
        else:
            for nominal_size in ASTM_COARSE_NOMINAL_SIZES:
                astm_size = {10: 8, 20: 67, 40: 467}[nominal_size]
                self.band_combo.addItem(
                    f"{nominal_size:g} mm reference (ASTM Size {astm_size})",
                    ("astm_c33", "coarse", nominal_size),
                )
            self.band_combo.setCurrentIndex(
                ASTM_COARSE_NOMINAL_SIZES.index(20)
            )
        self.band_combo.blockSignals(False)

    def _update_standard_limit_column(self) -> None:
        """Show selected-code passing limits and dashes for unchecked sieves."""
        band = self._current_band(self.band_combo.currentData())
        self.table.blockSignals(True)
        for row, sieve_size in enumerate(self._current_sieves()):
            self.table.item(row, 5).setText(
                _fmt_passing_limit(band.get(sieve_size))
            )
        self.table.blockSignals(False)

    # ── Live recompute of the table's derived columns ────────────────

    def _on_cell_changed(self) -> None:
        self._recompute_table()

    def _recompute_table(self) -> None:
        """Recompute %retained / cumulative / %passing from the mass column."""
        self.table.blockSignals(True)
        sieves = self._current_sieves()
        masses: list[float] = []
        for i in range(len(sieves)):
            item = self.table.item(i, 1)
            try:
                masses.append(float(item.text()) if item and item.text() else 0.0)
            except ValueError:
                masses.append(0.0)

        pan_item = self.table.item(len(sieves), 1)
        try:
            pan = float(pan_item.text()) if pan_item and pan_item.text() else 0.0
        except ValueError:
            pan = 0.0

        result = compute_psd(masses, sieves, pan_mass=pan)

        for i in range(len(sieves)):
            self.table.item(i, 2).setText(f"{result.percent_retained[i]:.2f}")
            self.table.item(i, 3).setText(
                f"{result.cumulative_percent_retained[i]:.2f}"
            )
            self.table.item(i, 4).setText(f"{result.percent_passing[i]:.2f}")

        # Pan row: show pan mass % of total
        pan_pct = pan / result.total_mass * 100 if result.total_mass > 0 else 0.0
        self.table.item(len(sieves), 2).setText(f"{pan_pct:.2f}")
        self.table.item(len(sieves), 3).setText("—")
        self.table.item(len(sieves), 4).setText(f"{pan_pct:.2f}")

        # Total row
        self.table.item(len(sieves) + 1, 1).setText(f"{result.total_mass:.1f} g")

        self.table.blockSignals(False)

    # ── Event handlers ───────────────────────────────────────────────

    def _on_standard_changed(self) -> None:
        self._rebuild_band_combo()
        self._rebuild_table()
        self._update_quality_visibility()
        self._result_panel.clear()
        self._last_result = None
        self._astm_checks = []

    def _on_agg_type_changed(self) -> None:
        self._rebuild_band_combo()
        self._rebuild_table()
        self._update_quality_visibility()
        self._result_panel.clear()
        self._last_result = None
        self._astm_checks = []

    def _on_band_changed(self) -> None:
        self._update_standard_limit_column()
        # If a result already exists, re-evaluate conformance and redraw.
        if self._last_result is not None:
            self._evaluate_and_plot(self._last_result)

    def _on_clear(self) -> None:
        # Contract: clearing this tab also unlocks and resets every
        # mix-design field that was fed from a PSD result.
        self._result_panel.clear_all_inputs.emit()
        self._rebuild_table()
        self._last_result = None
        self._astm_checks = []
        self._result_panel.clear()
        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            self.window().status_bar.showMessage("PSD cleared", 3000)

    def _on_compute_plot(self) -> None:
        sieves = self._current_sieves()
        masses: list[float] = []
        for i in range(len(sieves)):
            item = self.table.item(i, 1)
            try:
                masses.append(float(item.text()) if item and item.text() else 0.0)
            except ValueError:
                masses.append(0.0)
        pan_item = self.table.item(len(sieves), 1)
        try:
            pan = float(pan_item.text()) if pan_item and pan_item.text() else 0.0
        except ValueError:
            pan = 0.0

        if sum(masses) + pan <= 0:
            QMessageBox.information(
                self,
                "No Data",
                "Please enter the mass retained on at least one sieve.",
            )
            return

        try:
            result = compute_psd(
                masses, sieves, pan_mass=pan,
                compute_fineness_modulus=self._fm_required(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
            return

        self._last_result = result
        self._evaluate_and_plot(result)
        self._auto_save_history(result)

        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            self.window().status_bar.showMessage(
                f"PSD computed — Total {result.total_mass:.1f} g"
                + (f"  |  FM {result.fineness_modulus:.2f}"
                   if result.fineness_modulus is not None else ""),
                5000,
            )

        # Selected standard: run every clause of that standard against the
        # analysis and tell the user — with the exact clause citation —
        # whenever a requirement is not met (user-requested compliance
        # gate). Supported: ASTM C33 and IS 383:2016.
        self._astm_checks = []
        standard = self.standard_combo.currentData()
        if standard == "astm_c33":
            self._astm_checks = self._run_astm_c33_checks(result)
            failures = [c for c in self._astm_checks if c.failed]
            if failures:
                self._show_astm_compliance_dialog(self._astm_checks)
            elif hasattr(self.window(), "status_bar") and self.window().status_bar:
                self.window().status_bar.showMessage(
                    f"ASTM C33: all {len(self._astm_checks)} applicable "
                    "requirement(s) checked — no non-conformance found",
                    5000,
                )
        elif standard == "is383":
            self._astm_checks = self._run_is383_checks(result)
            failures = [c for c in self._astm_checks if c.failed]
            if failures:
                self._show_astm_compliance_dialog(self._astm_checks)
            elif hasattr(self.window(), "status_bar") and self.window().status_bar:
                self.window().status_bar.showMessage(
                    f"IS 383: all {len(self._astm_checks)} applicable "
                    "requirement(s) checked — no non-conformance found",
                    5000,
                )

    def _evaluate_and_plot(self, result: PSDResult) -> None:
        """Check conformance against the selected band and show on the panel."""
        band_key = self.band_combo.currentData()
        band = self._current_band(band_key)
        check_conformance(result, band)
        self._result_panel.display_psd(
            result, band, band_key, fm_required=self._fm_required()
        )

    def _fm_required(self) -> bool:
        """Whether the selected standard carries an FM requirement here.

        ASTM C33/C33M restricts the fine-aggregate fineness modulus
        (Clause 6.2: FM 2.3–3.1; Clause 6.4: shipment variation ≤ 0.20),
        so the FM is calculated for that combination and feeds the
        compliance checks. IS 383:2016 grades fine aggregate by zone
        (Table 9) and sets no fineness-modulus requirement for either
        aggregate type, and ASTM C33 coarse aggregate has none — for
        those selections the FM is not calculated at all.
        """
        return (
            self.standard_combo.currentData() == "astm_c33"
            and self.agg_combo.currentData() == "fine"
        )

    def _current_band(self, band_key) -> dict[float, tuple[float, float]]:
        if band_key is None:
            return {}
        standard, aggregate_type, *reference = band_key
        if standard == "is383" and aggregate_type == "fine":
            return get_fine_band(reference[0])
        if standard == "astm_c33" and aggregate_type == "fine":
            return get_astm_fine_band()
        if standard == "is383":
            grading_type, nominal_size = reference
            return get_is_coarse_band(grading_type, nominal_size)
        return get_astm_coarse_band(reference[0])

    # ── History ──────────────────────────────────────────────────────

    _history_db = None  # Set by MainWindow

    def _gather_history_input(self) -> dict:
        """Snapshot every PSD-tab entry that produced the last analysis."""
        from dataclasses import asdict

        sieves = self._current_sieves()
        masses: list[float] = []
        for i in range(len(sieves)):
            item = self.table.item(i, 1)
            try:
                masses.append(float(item.text()) if item and item.text() else 0.0)
            except ValueError:
                masses.append(0.0)
        pan_item = self.table.item(len(sieves), 1)
        try:
            pan = float(pan_item.text()) if pan_item and pan_item.text() else 0.0
        except ValueError:
            pan = 0.0

        band_key = self.band_combo.currentData()
        inp = {
            "standard": self.standard_combo.currentData(),
            "aggregate_type": self.agg_combo.currentData(),
            "band_key": list(band_key) if band_key is not None else None,
            "sieves": sieves,
            "masses": masses,
            "pan_mass": pan,
        }
        if inp["standard"] == "astm_c33":
            if inp["aggregate_type"] == "fine":
                inp["fine_quality"] = asdict(
                    self._gather_fine_quality_inputs()
                )
            else:
                inp["coarse_quality"] = asdict(
                    self._gather_coarse_quality_inputs()
                )
        elif inp["standard"] == "is383":
            if inp["aggregate_type"] == "fine":
                inp["is383_fine_quality"] = asdict(
                    self._gather_is_fine_quality_inputs()
                )
            else:
                inp["is383_coarse_quality"] = asdict(
                    self._gather_is_coarse_quality_inputs()
                )
        return inp

    def _auto_save_history(self, result: PSDResult) -> None:
        """Auto-save the sieve analysis to the history DB."""
        if self._history_db is None:
            return
        try:
            inp = self._gather_history_input()
            std = "ASTM C33" if inp["standard"] == "astm_c33" else "IS 383"
            agg = "Fine" if inp["aggregate_type"] == "fine" else "Coarse"
            name = f"PSD {std} {agg} — {result.total_mass:.1f} g"
            self._history_db.save_psd(inp, result, name=name)
        except Exception:
            pass  # Don't break the UI for history failures

    def load_from_history(self, calc_id: int) -> None:
        """Restore a PSD record's entries and result into this tab."""
        if self._history_db is None:
            return
        import json

        rec = self._history_db.get_calculation(calc_id)
        if rec is None or rec["tab_type"] != "psd":
            return
        try:
            inp = json.loads(rec["input_json"])
            result = deserialize_psd_result(json.loads(rec["result_json"]))
        except (json.JSONDecodeError, TypeError, KeyError):
            return

        # 1) Standard and aggregate type — each change rebuilds the band
        #    combo, the sieve table and the quality pages' visibility.
        idx = self.standard_combo.findData(inp.get("standard", "is383"))
        if idx >= 0:
            self.standard_combo.setCurrentIndex(idx)
        idx = self.agg_combo.findData(inp.get("aggregate_type", "fine"))
        if idx >= 0:
            self.agg_combo.setCurrentIndex(idx)

        # 2) Reference band (stored as a JSON list, combos hold tuples)
        band_key = inp.get("band_key")
        if isinstance(band_key, list):
            band_key = tuple(band_key)
        if band_key is not None:
            idx = self.band_combo.findData(band_key)
            if idx >= 0:
                self.band_combo.setCurrentIndex(idx)

        # 3) Sieve masses — rows exist for this stack after step 1
        sieves = self._current_sieves()
        masses = inp.get("masses") or []
        for i in range(len(sieves)):
            m = masses[i] if i < len(masses) else 0.0
            item = self.table.item(i, 1)
            if item is not None:
                item.setText(f"{float(m):g}")
        pan_item = self.table.item(len(sieves), 1)
        if pan_item is not None:
            pan_item.setText(f"{float(inp.get('pan_mass', 0.0)):g}")

        # 4) Quality inputs of the saved standard
        if inp.get("standard") == "astm_c33":
            self._restore_quality_inputs(
                inp.get("fine_quality"), inp.get("coarse_quality")
            )
        elif inp.get("standard") == "is383":
            self._restore_is_quality_inputs(
                inp.get("is383_fine_quality"), inp.get("is383_coarse_quality")
            )

        # 5) Result → conformance check + panel (compliance dialog is not
        #    re-opened on load; checks are recomputed for the button state)
        self._last_result = result
        self._evaluate_and_plot(result)
        self._astm_checks = []
        std_now = self.standard_combo.currentData()
        if std_now == "astm_c33":
            self._astm_checks = self._run_astm_c33_checks(result)
        elif std_now == "is383":
            self._astm_checks = self._run_is383_checks(result)

    def _restore_is_quality_inputs(
        self, fine: dict | None, coarse: dict | None
    ) -> None:
        """Put saved IS 383 laboratory results back into their fields."""

        def set_pct(spin: QDoubleSpinBox, value) -> None:
            # None or the sentinel means "not tested" — the spin minimum.
            spin.setValue(_NOT_TESTED if value is None else float(value))

        def set_combo(combo: QComboBox, value) -> None:
            if value is None:
                return
            idx = combo.findData(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        def set_check(check: QCheckBox, value) -> None:
            check.setChecked(bool(value))

        if fine:
            set_combo(self.is_fine_source_combo, fine.get("source_type"))
            set_pct(self.is_fine_coal_spin, fine.get("coal_lignite_pct"))
            set_pct(self.is_fine_clay_spin, fine.get("clay_lumps_pct"))
            set_pct(self.is_fine_finer75_spin, fine.get("finer_75um_pct"))
            set_pct(self.is_fine_shale_spin, fine.get("shale_pct"))
            set_pct(self.is_fine_mica_spin, fine.get("mica_pct"))
            set_combo(self.is_fine_mica_type_combo, fine.get("mica_type"))
            set_check(
                self.is_fine_mica_tests_check, fine.get("mica_tests_conducted")
            )
            set_combo(self.is_fine_organic_combo, fine.get("organic_status"))
            if fine.get("organic_relative_strength_pct") is not None:
                self.is_fine_organic_strength_spin.setValue(
                    float(fine["organic_relative_strength_pct"])
                )
            set_pct(self.is_fine_fi_spin, fine.get("flakiness_index_pct"))
            set_pct(self.is_fine_ei_spin, fine.get("elongation_index_pct"))
            set_pct(self.is_fine_soundness_spin, fine.get("soundness_loss_pct"))
            set_combo(
                self.is_fine_soundness_salt_combo, fine.get("soundness_salt")
            )
            set_combo(self.is_fine_aar_combo, fine.get("aar_method"))
            if fine.get("aar_expansion_pct") is not None:
                self.is_fine_aar_expansion_spin.setValue(
                    float(fine["aar_expansion_pct"])
                )
            if fine.get("aar_age_days") is not None:
                set_combo(self.is_fine_aar_age_combo, int(fine["aar_age_days"]))
            self._restore_is_manufactured("is_fine", fine)

        if coarse:
            set_combo(self.is_coarse_source_combo, coarse.get("source_type"))
            set_pct(self.is_coarse_coal_spin, coarse.get("coal_lignite_pct"))
            set_pct(self.is_coarse_clay_spin, coarse.get("clay_lumps_pct"))
            set_pct(self.is_coarse_finer75_spin, coarse.get("finer_75um_pct"))
            set_pct(self.is_coarse_soft_spin, coarse.get("soft_fragments_pct"))
            set_pct(self.is_coarse_fi_spin, coarse.get("flakiness_index_pct"))
            set_pct(self.is_coarse_ei_spin, coarse.get("elongation_index_pct"))
            set_check(
                self.is_coarse_wearing_check, coarse.get("wearing_surfaces")
            )
            set_check(
                self.is_coarse_high_grade_check, coarse.get("high_grade")
            )
            set_pct(self.is_coarse_acv_spin, coarse.get("crushing_value_pct"))
            if coarse.get("ten_pct_fines_load_kn") is not None:
                self.is_coarse_ten_pct_fines_spin.setValue(
                    float(coarse["ten_pct_fines_load_kn"])
                )
            set_pct(self.is_coarse_aiv_spin, coarse.get("impact_value_pct"))
            set_pct(self.is_coarse_abrasion_spin, coarse.get("abrasion_loss_pct"))
            set_pct(
                self.is_coarse_soundness_spin, coarse.get("soundness_loss_pct")
            )
            set_combo(
                self.is_coarse_soundness_salt_combo,
                coarse.get("soundness_salt"),
            )
            set_combo(self.is_coarse_aar_combo, coarse.get("aar_method"))
            if coarse.get("aar_expansion_pct") is not None:
                self.is_coarse_aar_expansion_spin.setValue(
                    float(coarse["aar_expansion_pct"])
                )
            if coarse.get("aar_age_days") is not None:
                set_combo(
                    self.is_coarse_aar_age_combo, int(coarse["aar_age_days"])
                )
            self._restore_is_manufactured("is_coarse", coarse)

        self._update_is_totals("is_fine")
        self._update_is_totals("is_coarse")

    def _restore_is_manufactured(self, prefix: str, data: dict) -> None:
        """Restore the Clause 5.7 / Table 3 block of one IS page."""
        def set_pct(name: str, value) -> None:
            spin = getattr(self, f"{prefix}_mfd_{name}_spin", None)
            if spin is not None:
                spin.setValue(_NOT_TESTED if value is None else float(value))

        combo = getattr(self, f"{prefix}_mfd_type_combo", None)
        mtype = data.get("manufactured_type")
        if combo is not None and mtype is not None:
            idx = combo.findData(mtype)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        set_pct("alkali", data.get("manufactured_alkali_pct"))
        set_pct("sulphate", data.get("manufactured_sulphate_pct"))
        set_pct("chloride", data.get("manufactured_chloride_pct"))
        set_pct("absorption", data.get("manufactured_absorption_pct"))
        sg = getattr(self, f"{prefix}_mfd_sg_spin", None)
        if sg is not None:
            sg.setValue(float(data.get("manufactured_specific_gravity") or 0.0))
        prewet = getattr(self, f"{prefix}_mfd_prewetted_check", None)
        if prewet is not None:
            prewet.setChecked(bool(data.get("rca_prewetted")))

    def _restore_quality_inputs(self, fine: dict | None, coarse: dict | None) -> None:
        """Put saved ASTM C33 laboratory results back into their fields."""

        def set_pct(spin: QDoubleSpinBox, value) -> None:
            # None or the sentinel means "not tested" — the spin minimum.
            spin.setValue(_NOT_TESTED if value is None else float(value))

        def set_combo(combo: QComboBox, value) -> None:
            if value is None:
                return
            idx = combo.findData(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        if fine:
            if "check_fm_variation" in fine:
                self.fine_fm_variation_check.setChecked(
                    bool(fine["check_fm_variation"])
                )
            if fine.get("base_fineness_modulus") is not None:
                self.fine_base_fm_spin.setValue(
                    float(fine["base_fineness_modulus"])
                )
            set_pct(self.fine_clay_spin, fine.get("clay_lumps_pct"))
            set_pct(self.fine_finer_75um_spin, fine.get("finer_75um_pct"))
            set_pct(self.fine_coal_spin, fine.get("coal_lignite_pct"))
            self.fine_abrasion_check.setChecked(
                bool(fine.get("concrete_subject_to_abrasion", True))
            )
            self.fine_appearance_check.setChecked(
                bool(fine.get("surface_appearance_important", False))
            )
            self.fine_manufactured_check.setChecked(
                bool(fine.get("manufactured_sand_dust_of_fracture", False))
            )
            set_combo(self.fine_organic_combo, fine.get("organic_status"))
            if fine.get("c87_relative_strength_pct") is not None:
                self.fine_c87_spin.setValue(
                    float(fine["c87_relative_strength_pct"])
                )
            set_pct(self.fine_soundness_spin, fine.get("soundness_loss_pct"))
            set_combo(self.fine_soundness_salt_combo, fine.get("soundness_salt"))
            set_combo(self.fine_reactivity_combo, fine.get("reactivity_status"))

        if coarse:
            set_combo(self.coarse_class_combo, coarse.get("class_designation"))
            set_pct(self.coarse_clay_spin, coarse.get("clay_lumps_pct"))
            set_pct(self.coarse_chert_spin, coarse.get("chert_pct"))
            set_pct(self.coarse_finer_75um_spin, coarse.get("finer_75um_pct"))
            set_pct(self.coarse_coal_spin, coarse.get("coal_lignite_pct"))
            set_pct(self.coarse_abrasion_spin, coarse.get("abrasion_loss_pct"))
            set_pct(self.coarse_soundness_spin, coarse.get("soundness_loss_pct"))
            set_combo(
                self.coarse_soundness_salt_combo, coarse.get("soundness_salt")
            )
            self.coarse_slag_check.setChecked(bool(coarse.get("is_slag", False)))
            if coarse.get("slag_unit_weight_kg_m3") is not None:
                self.coarse_slag_weight_spin.setValue(
                    float(coarse["slag_unit_weight_kg_m3"])
                )
            self.coarse_clay_free_check.setChecked(
                bool(coarse.get("essentially_clay_free", False))
            )
            self.coarse_weighted_check.setChecked(
                bool(coarse.get("weighted_limit_enabled", False))
            )
            if coarse.get("p_sand_pct") is not None:
                self.coarse_p_spin.setValue(float(coarse["p_sand_pct"]))
            if coarse.get("t_fine_limit_pct") is not None:
                self.coarse_t_spin.setValue(float(coarse["t_fine_limit_pct"]))
            if coarse.get("a_fine_actual_pct") is not None:
                self.coarse_a_spin.setValue(float(coarse["a_fine_actual_pct"]))
            set_combo(
                self.coarse_reactivity_combo, coarse.get("reactivity_status")
            )

    # ── Shared label helpers (match concrete_tab.py style) ───────────

    def _label(self, text: str) -> QLabel:
        # Cased in Python rather than by Qt's text-transform (which maps
        # µ to a capital Mu that reads as "M") so unit-bearing labels
        # like "75-µm" keep their micro symbol under the uppercase style.
        lbl = QLabel(uppercase_preserving_si_units(text))
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; "
            f"letter-spacing: 0.05em; color: {_TEXT_DIM};"
        )
        # Wrap so labels reflow when the sidebar is narrowed instead of
        # forcing the form wider than the sidebar's 360px floor.
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return lbl

    def _label_with_info(self, text: str, info: str) -> QWidget:
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self._label(text))
        lay.addWidget(InfoButton(info))
        lay.addStretch()
        w = QWidget()
        w.setLayout(lay)
        return w

    def _field_with_info(self, field: QWidget, info: str) -> QWidget:
        """Any input widget (checkbox, combo) + 'i' button beside it.

        Same pattern as :meth:`_label_with_info`, for rows whose control
        carries its own text (checkboxes, the single-combo reactivity
        sections) so every ASTM C33 field explains itself on click.
        """
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(field)
        lay.addWidget(InfoButton(info))
        lay.addStretch()
        w = QWidget()
        w.setLayout(lay)
        return w
