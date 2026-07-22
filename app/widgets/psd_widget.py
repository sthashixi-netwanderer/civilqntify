"""Particle Size Distribution subtab — sieve analysis input + gradation curve.

The user enters the **raw mass retained on each sieve** (g) from the lab test.
The app computes the full gradation table (%retained, cumulative %retained,
%passing), Fineness Modulus, D-values and uniformity/curvature coefficients,
and renders a **semi-log gradation curve** with matplotlib, overlaid with the
relevant standard grading band (IS 383 zone for fine aggregate, IS 383 Table 7
/ ASTM C33 nominal-size band for coarse aggregate) for conformance checking.

Reference standards (per AGENTS.md):
  - ACI 211.1-22 §4.3.5 — Fineness modulus and standard sieve series.
  - IS 383:2016 — fine-aggregate grading zones (Table 4) and coarse-aggregate
    grading (Table 7).
  - ASTM C33/C33M — coarse aggregate grading requirements.
"""

from __future__ import annotations

import csv
import io

from PyQt6.QtCore import Qt
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
    COARSE_NOMINAL_SIZES,
    FINE_ZONES,
    get_coarse_band,
    get_fine_band,
)
from concrete_mix.engine.psd import (
    COARSE_SIEVES,
    FINE_SIEVES,
    PSDResult,
    check_conformance,
    compute_psd,
)

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


class ParticleSizeDistributionTab(QWidget):
    """Subtab for sieve analysis input and gradation-curve plotting."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_result: PSDResult | None = None
        self._build_ui()

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

        # ── Results summary (stat cards) ──
        self._results_group = self._build_results_group()
        layout.addWidget(self._results_group)

        # ── Plot ──
        layout.addWidget(self._build_plot())

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

        # Aggregate type
        self.agg_combo = QComboBox()
        self.agg_combo.addItem("Fine Aggregate (sand)", "fine")
        self.agg_combo.addItem("Coarse Aggregate (gravel/stone)", "coarse")
        self.agg_combo.currentIndexChanged.connect(self._on_agg_type_changed)
        form.addWidget(self._label("Aggregate Type"), 0, 0)
        form.addWidget(self.agg_combo, 0, 1)

        # Reference band selector — depends on aggregate type
        self.band_combo = QComboBox()
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)
        self._lbl_band = self._label_with_info(
            "Reference Band",
            "Standard grading limits drawn as a shaded band behind your curve.\n\n"
            "Fine aggregate → IS 383 grading zones I–IV.\n"
            "Coarse aggregate → IS 383 Table 7 / ASTM C33 nominal-size bands.",
        )
        form.addWidget(self._lbl_band, 1, 0)
        form.addWidget(self.band_combo, 1, 1)

        form.setColumnStretch(2, 1)
        return grp

    def _build_table(self) -> QGroupBox:
        grp = QGroupBox("Input — Mass Retained on Each Sieve")
        v = QVBoxLayout(grp)
        v.setContentsMargins(12, 16, 12, 12)

        hint = QLabel(
            "Enter the mass retained (g) on each sieve as measured during the "
            "test. All other columns are computed automatically."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        v.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Sieve Size", "Mass Retained (g)", "% Retained",
             "Cumulative % Retained", "% Passing"]
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

        self.export_csv_btn = QPushButton("  Export CSV")
        self.export_csv_btn.setObjectName("secondary")
        self.export_csv_btn.setMinimumHeight(40)
        self.export_csv_btn.clicked.connect(self._on_export_csv)
        lay.addWidget(self.export_csv_btn, 1)

        self.export_img_btn = QPushButton("  Export Image")
        self.export_img_btn.setObjectName("secondary")
        self.export_img_btn.setMinimumHeight(40)
        self.export_img_btn.clicked.connect(self._on_export_image)
        lay.addWidget(self.export_img_btn, 1)

        lay.addStretch(3)
        return w

    def _build_results_group(self) -> QGroupBox:
        grp = QGroupBox("Results Summary")
        grp.setVisible(False)
        self._results_grid = QGridLayout(grp)
        self._results_grid.setContentsMargins(12, 16, 12, 12)
        self._results_grid.setSpacing(10)
        return grp

    def _build_plot(self) -> QGroupBox:
        grp = QGroupBox("Gradation Curve (Semi-Log)")
        v = QVBoxLayout(grp)
        v.setContentsMargins(12, 16, 12, 12)

        self._fig = Figure(figsize=(7, 4.2), tight_layout=True)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas.setMinimumHeight(340)
        v.addWidget(self._canvas)

        # Draw an empty placeholder
        self._draw_placeholder()
        return grp

    # ── Dynamic table rebuild ────────────────────────────────────────

    def _current_sieves(self) -> list[float]:
        agg = self.agg_combo.currentData()
        return FINE_SIEVES if agg == "fine" else COARSE_SIEVES

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

            # Computed columns (read-only)
            for col in (2, 3, 4):
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
        for col in (2, 3, 4):
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
        for col in (2, 3, 4):
            item = QTableWidgetItem("—")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(total_row, col, item)

        self.table.blockSignals(False)
        self._recompute_table()

    def _rebuild_band_combo(self) -> None:
        """Populate the reference-band combo for the current aggregate type."""
        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        agg = self.agg_combo.currentData()
        if agg == "fine":
            for z in FINE_ZONES:
                self.band_combo.addItem(f"IS 383 Zone {z}", ("fine", z))
            self.band_combo.setCurrentIndex(FINE_ZONES.index("II"))
        else:
            for n in COARSE_NOMINAL_SIZES:
                self.band_combo.addItem(
                    f"{n} mm graded (IS 383 Table 7 / ASTM C33)", ("coarse", n)
                )
            self.band_combo.setCurrentIndex(COARSE_NOMINAL_SIZES.index(20))
        self.band_combo.blockSignals(False)

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

    def _on_agg_type_changed(self) -> None:
        self._rebuild_band_combo()
        self._rebuild_table()
        self._draw_placeholder()
        self._results_group.setVisible(False)

    def _on_band_changed(self) -> None:
        # If a result already exists, re-evaluate conformance and redraw.
        if self._last_result is not None:
            self._evaluate_and_plot(self._last_result)

    def _on_clear(self) -> None:
        self._rebuild_table()
        self._last_result = None
        self._results_group.setVisible(False)
        self._draw_placeholder()
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
        """Check conformance against the selected band, update cards, redraw."""
        band_key = self.band_combo.currentData()
        band = self._current_band(band_key)
        check_conformance(result, band)
        self._update_results_cards(result)
        self._draw_curve(result, band, band_key)

    def _current_band(self, band_key) -> dict[float, tuple[float, float]]:
        if band_key is None:
            return {}
        kind, val = band_key
        if kind == "fine":
            return get_fine_band(val)
        return get_coarse_band(int(val))

    # ── Results cards ────────────────────────────────────────────────

    def _update_results_cards(self, result: PSDResult) -> None:
        # Clear previous cards
        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        agg = self.agg_combo.currentData()
        cards: list[tuple[str, str]] = []

        if agg == "fine" and result.fineness_modulus is not None:
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
            f"color: {_BORDER if False else '#ffffff'}; "
            f"background: {badge_color}; "
            "padding: 8px 14px; border-radius: 4px; font-weight: 700; "
            "font-size: 12px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = (len(cards) + cols - 1) // cols
        self._results_grid.addWidget(badge, row, 0, 1, cols)

        self._results_group.setVisible(True)

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

        # ── Standard band (shaded region) ──
        if band:
            band_sizes = sorted(band.keys())
            lower = [band[s][0] for s in band_sizes]
            upper = [band[s][1] for s in band_sizes]
            ax.fill_between(
                band_sizes, lower, upper,
                color=_BAND_FILL, alpha=0.15, label="Standard band",
                edgecolor=_BAND_EDGE, linewidth=0.8, linestyle="--",
            )

        # ── User's gradation curve ──
        sizes = result.sieve_sizes
        passing = result.percent_passing
        ax.plot(
            sizes, passing, marker="o", color=_PRIMARY, linewidth=2,
            markersize=6, label="Your gradation", zorder=5,
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

        # Title with band name
        if band_key:
            kind, val = band_key
            if kind == "fine":
                title = f"Fine Aggregate Gradation — IS 383 Zone {val}"
            else:
                title = (
                    f"Coarse Aggregate Gradation — {val} mm graded "
                    f"(IS 383 Table 7 / ASTM C33)"
                )
        else:
            title = "Particle Size Distribution"
        ax.set_title(title, fontsize=12, fontweight="bold", color=_PRIMARY)

        ax.legend(loc="lower left", fontsize=9, framealpha=0.9)
        self._fig.tight_layout()
        self._canvas.draw()

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

    # ── Shared label helpers (match concrete_tab.py style) ───────────

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            f"letter-spacing: 0.05em; color: {_TEXT_DIM};"
        )
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
