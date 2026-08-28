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

Reference standards (per AGENTS.md):
  - ACI 211.1-22 §4.3.5 — Fineness modulus and standard sieve series.
  - IS 383:2016 — fine-aggregate grading zones (Table 9) and coarse-aggregate
    grading (Table 7).
  - ASTM C33/C33M — Table 1 fine and Table 2 coarse grading requirements.
"""

from __future__ import annotations

import csv
import io
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
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

from app.widgets.info_button import InfoButton
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
    """Interpolate a grading-band boundary smoothly in log-sieve space.

    A shape-preserving cubic Hermite interpolation is used rather than an
    unconstrained spline. Standard control points remain exact, monotonic
    grading limits do not overshoot, and no curve is drawn outside the first
    and last sieves specified by the selected reference row.
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
    - < 1.0 mm (e.g. 0.600, 0.300, 0.150 mm): 2-3 decimal places
    """
    if mm >= 10.0:
        return f"{mm:.1f} mm"
    elif mm >= 1.0:
        return f"{mm:.2f} mm"
    elif mm >= 0.01:
        return f"{mm:.2f} mm"
    return f"{mm:.3f} mm"


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

        # ── Export buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
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
        outer.addLayout(btn_row)

        scroll.setWidget(container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

        self._draw_placeholder()

    # ── Public API ───────────────────────────────────────────────────

    def display_psd(
        self,
        result: PSDResult,
        band: dict[float, tuple[float, float]],
        band_key,
    ) -> None:
        """Show a computed gradation: stat cards + curve with the band."""
        self._last_result = result
        self._last_band_key = band_key
        self._update_results_cards(result)
        self._fill_fm_derivation(result)
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
            cards.append(("D10", f"{result.d10:.3f} mm"))
        if result.d30 is not None:
            cards.append(("D30", f"{result.d30:.3f} mm"))
        if result.d60 is not None:
            cards.append(("D60", f"{result.d60:.3f} mm"))
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

    def _fill_fm_derivation(self, result: PSDResult) -> None:
        """Render exactly how the FM handed to ACI mix design is obtained.

        Working shown step by step, mirroring ACI PRC-211.1-22 §4.3.5 and
        the ASTM C136 procedure implemented in :func:`compute_psd`:

            FM = Σ(cumulative % retained on 4.75, 2.36, 1.18, 0.600,
                   0.300 and 0.150 mm sieves) ÷ 100

        Rows follow the shared ``FM_SIEVE_SERIES`` derived from
        ``engine.psd.FM_SIEVES`` so the display can never drift from the
        computation. When any standard sieve is missing, the group shows
        which ones are needed instead of a misleading partial sum.
        """
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
        sizes = result.sieve_sizes
        passing = result.percent_passing
        ax.plot(
            sizes, passing, marker="o", color=_PRIMARY, linewidth=2,
            markersize=6, label="Your gradation", zorder=5,
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

        # ── Buttons ──
        layout.addWidget(self._build_buttons())

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Initial table + band combo build for fine aggregate
        self._rebuild_band_combo()
        self._rebuild_table()

    def _build_controls(self) -> QGroupBox:
        grp = QGroupBox("Sieve Analysis — Setup")
        form = QGridLayout(grp)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(8)

        # PSD standard — controls both sieve designations and grading limits.
        self.standard_combo = QComboBox()
        self.standard_combo.addItem("IS 383:2016", "is383")
        self.standard_combo.addItem("ASTM C33/C33M", "astm_c33")
        self.standard_combo.setMinimumWidth(150)
        self.standard_combo.currentIndexChanged.connect(self._on_standard_changed)
        form.addWidget(self._label("Standard"), 0, 0)
        form.addWidget(self.standard_combo, 0, 1)

        # Aggregate type
        self.agg_combo = QComboBox()
        self.agg_combo.addItem("Fine Aggregate (sand)", "fine")
        self.agg_combo.addItem("Coarse Aggregate (gravel/stone)", "coarse")
        # Floor the width so the combo's minimumSizeHint (widest item) does
        # not force the sidebar wider than its 360px floor; text elides.
        self.agg_combo.setMinimumWidth(150)
        self.agg_combo.currentIndexChanged.connect(self._on_agg_type_changed)
        form.addWidget(self._label("Aggregate Type"), 1, 0)
        form.addWidget(self.agg_combo, 1, 1)

        # Reference band selector — depends on standard and aggregate type
        self.band_combo = QComboBox()
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
        lay.setContentsMargins(0, 0, 0, 0)
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
        self._result_panel.clear()
        self._last_result = None

    def _on_agg_type_changed(self) -> None:
        self._rebuild_band_combo()
        self._rebuild_table()
        self._result_panel.clear()
        self._last_result = None

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
            result = compute_psd(masses, sieves, pan_mass=pan)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
            return

        self._last_result = result
        self._evaluate_and_plot(result)

        if hasattr(self.window(), "status_bar") and self.window().status_bar:
            self.window().status_bar.showMessage(
                f"PSD computed — Total {result.total_mass:.1f} g"
                + (f"  |  FM {result.fineness_modulus:.2f}"
                   if result.fineness_modulus is not None else ""),
                5000,
            )

    def _evaluate_and_plot(self, result: PSDResult) -> None:
        """Check conformance against the selected band and show on the panel."""
        band_key = self.band_combo.currentData()
        band = self._current_band(band_key)
        check_conformance(result, band)
        self._result_panel.display_psd(result, band, band_key)

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

    # ── Shared label helpers (match concrete_tab.py style) ───────────

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
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
