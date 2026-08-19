"""Results panel for displaying concrete mix design output."""

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

from concrete_mix import MixDesignResult
from app.unit_preferences import UnitPreferences, get_unit_prefs


class StatCard(QFrame):
    """A single metric card with label, value, and unit.

    Follows Stitch design system card pattern:
    - White background, 1px #e2e8f0 border, 4px radius
    - Label in uppercase bold (label-bold style)
    - Value in monospace (data-mono style)
    - Header separated by bottom border
    """

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

    def set_value(self, value: float, unit: str = "kg/m\u00b3", fmt: str = ".1f") -> None:
        self._value.setText(f"{value:{fmt}}")
        self._unit.setText(unit)


class ResultPanel(QWidget):
    """Right-side panel showing calculation results."""

    send_to_quantification = pyqtSignal(object)  # MixDesignResult

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: MixDesignResult | None = None
        self._strength_estimate: dict | None = None
        self.unit_prefs: UnitPreferences = get_unit_prefs()
        self._build_ui()
        self.unit_prefs.changed.connect(self.on_unit_changed)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Warnings banner (hidden by default)
        self._warning_banner = QLabel()
        self._warning_banner.setObjectName("warning-banner")
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setVisible(False)
        outer.addWidget(self._warning_banner)

        # Strength estimation from mix ratio (hidden by default)
        self._strength_est_frame = QFrame()
        self._strength_est_frame.setObjectName("result-card")
        self._strength_est_frame.setVisible(False)
        est_layout = QVBoxLayout(self._strength_est_frame)
        est_layout.setContentsMargins(12, 10, 12, 10)
        est_layout.setSpacing(4)

        est_title = QLabel("Target Strength Estimation")
        est_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 0.05em; color: #444653;"
        )
        est_layout.addWidget(est_title)

        self._strength_est_html = QLabel()
        self._strength_est_html.setWordWrap(True)
        self._strength_est_html.setStyleSheet("font-size: 12px; padding: 2px 0;")
        est_layout.addWidget(self._strength_est_html)

        outer.addWidget(self._strength_est_frame)

        # Material quantities — card grid
        self._cards_label = QLabel("Material Quantities (per m³)")
        self._cards_label.setObjectName("section-title")
        outer.addWidget(self._cards_label)

        grid = QGridLayout()
        grid.setSpacing(10)

        self._cards: dict[str, StatCard] = {}
        card_defs = [
            ("cement", "Cement"),
            ("water", "Water"),
            ("fine_agg", "Fine Aggregate"),
            ("coarse_agg", "Coarse Aggregate"),
            ("scm", "SCM"),
            ("admix", "Admixture"),
            ("wc_ratio", "W/C Ratio"),
            ("air", "Air Content"),
            ("target", "Target Strength"),
        ]
        for i, (key, label) in enumerate(card_defs):
            card = StatCard(label)
            self._cards[key] = card
            grid.addWidget(card, i // 4, i % 4)

        outer.addLayout(grid)

        # Mix ratio display
        self._mix_ratio_label = QLabel()
        self._mix_ratio_label.setObjectName("section-title")
        self._mix_ratio_label.setWordWrap(True)
        self._mix_ratio_label.setStyleSheet("font-size: 14px; padding: 6px;")
        self._mix_ratio_label.setVisible(False)
        outer.addWidget(self._mix_ratio_label)

        # Total volume section
        self._total_label = QLabel()
        self._total_label.setObjectName("section-title")
        outer.addWidget(self._total_label)

        # Calculation steps tree
        steps_label = QLabel("Calculation Steps")
        steps_label.setObjectName("section-title")
        outer.addWidget(steps_label)

        self._steps_tree = QTreeWidget()
        self._steps_tree.setHeaderLabels(["#", "Description", "Formula", "Result", "Unit", "Reference"])
        self._steps_tree.setAlternatingRowColors(True)
        self._steps_tree.setRootIsDecorated(False)
        self._steps_tree.setColumnCount(6)
        outer.addWidget(self._steps_tree, stretch=1)

        # Export buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_csv = QPushButton("Export CSV")
        self._btn_csv.setObjectName("secondary")
        self._btn_json = QPushButton("Export JSON")
        self._btn_json.setObjectName("secondary")
        self._btn_report = QPushButton("Export PDF")
        self._btn_report.setObjectName("secondary")
        self._btn_csv.setEnabled(False)
        self._btn_json.setEnabled(False)
        self._btn_report.setEnabled(False)
        btn_row.addWidget(self._btn_csv)
        btn_row.addWidget(self._btn_json)
        btn_row.addWidget(self._btn_report)

        # Send to Quantification button (primary action)
        btn_row.addSpacing(16)
        self._btn_quant = QPushButton("  Send to Quantification")
        self._btn_quant.setEnabled(False)
        self._btn_quant.clicked.connect(self._on_send_to_quant)
        btn_row.addWidget(self._btn_quant)

        btn_row.addStretch()
        outer.addLayout(btn_row)

        # Export signal connections will be wired by the parent tab
        self.btn_csv = self._btn_csv
        self.btn_json = self._btn_json
        self.btn_report = self._btn_report

    def display_result(self, result: MixDesignResult) -> None:
        """Update the panel with a new mix design result."""
        self._result = result
        # Hide any previous strength estimation when showing a full result
        self._strength_estimate = None
        self._strength_est_frame.setVisible(False)
        self._refresh_display()

    def display_strength_estimate(
        self,
        fck: float,
        f_target: float,
        std_dev: float,
        margin: str,
        wc_ratio: float,
        method: str,
        cement_kg: float = 0.0,
        water_kg: float = 0.0,
        fine_agg_kg: float = 0.0,
        coarse_agg_kg: float = 0.0,
    ) -> None:
        """Show the target strength estimation result from the ratio subtab.

        Populates the stat cards with estimated material quantities and
        displays the strength formula in the estimation frame.  Values are
        stored metric and converted at render time.
        """
        self._strength_estimate = {
            "fck": fck,
            "f_target": f_target,
            "std_dev": std_dev,
            "margin": margin,
            "wc_ratio": wc_ratio,
            "method": method,
            "cement_kg": cement_kg,
            "water_kg": water_kg,
            "fine_agg_kg": fine_agg_kg,
            "coarse_agg_kg": coarse_agg_kg,
        }
        self._refresh_strength_estimate()

    def _refresh_strength_estimate(self) -> None:
        """Render the stored strength estimate in the active unit system."""
        est = self._strength_estimate
        if est is None:
            return
        up = self.unit_prefs
        su = up.strength_unit()
        fck = up.convert_strength_mpa(est["fck"])
        f_target = up.convert_strength_mpa(est["f_target"])
        margin = est["margin"]
        wc_ratio = est["wc_ratio"]
        method = est["method"]

        self._strength_est_frame.setVisible(True)
        if method == "is10262":
            html = (
                f"<b>f<sub>ck</sub>:</b> {fck:.1f} {su}<br/>"
                f"<b>f'<sub>ck</sub></b> = max(f<sub>ck</sub> + 1.65·S, "
                f"f<sub>ck</sub> + X)<br/>"
                f"<b>Margin:</b> {margin}<br/>"
                f"<b>Target Mean Strength:</b> "
                f"<span style='color:#047857;font-weight:700;'>"
                f"{f_target:.1f} {su}</span>"
            )
        elif method == "aci211":
            html = (
                f"<b>f'<sub>c</sub>:</b> {fck:.1f} {su}<br/>"
                f"<b>Margin:</b> {margin}<br/>"
                f"<b>Target Mean Strength (f'<sub>cr</sub>):</b> "
                f"<span style='color:#047857;font-weight:700;'>"
                f"{f_target:.1f} {su}</span><br/>"
                f"<small>Margin derived from ACI 318 overdesign method.</small>"
            )
        elif method == "doe":
            html = (
                f"<b>f<sub>c</sub>:</b> {fck:.1f} {su}<br/>"
                f"<b>Margin:</b> {margin}<br/>"
                f"<b>Target Mean Strength (f<sub>m</sub>):</b> "
                f"<span style='color:#047857;font-weight:700;'>"
                f"{f_target:.1f} {su}</span><br/>"
                f"<small>Margin = k × std_dev (DOE method).</small>"
            )
        else:
            html = (
                f"<b>Target Mean Strength:</b> "
                f"<span style='color:#047857;font-weight:700;'>"
                f"{f_target:.1f} {su}</span>"
            )
        html += f"<br/><b>Implied W/C:</b> {wc_ratio:.2f}"
        self._strength_est_html.setText(html)

        # Populate stat cards with estimated material quantities (converted)
        mu = up.mass_unit()
        self._cards["cement"].set_value(up.convert_mass_kg(est["cement_kg"]), mu)
        self._cards["water"].set_value(up.convert_mass_kg(est["water_kg"]), mu)
        self._cards["fine_agg"].set_value(up.convert_mass_kg(est["fine_agg_kg"]), mu)
        self._cards["coarse_agg"].set_value(up.convert_mass_kg(est["coarse_agg_kg"]), mu)
        self._cards["wc_ratio"].set_value(wc_ratio, "", ".3f")
        self._cards["target"].set_value(f_target, su)
        self._cards["scm"].set_value(0.0, mu)
        self._cards["air"].set_value(1.0, "%")

        # Show mix ratio in the ratio label
        ratio_parts = (
            f"1 : {est['fine_agg_kg'] / est['cement_kg']:.1f} : "
            f"{est['coarse_agg_kg'] / est['cement_kg']:.1f}"
        )
        label_text = (
            f"<b>Mix Ratio</b><br>"
            f"<span style='font-size:16px;'>{ratio_parts} "
            f"<span style='color:#6b7280;'>({wc_ratio:.3f})</span></span>"
        )
        self._mix_ratio_label.setText(label_text)
        self._mix_ratio_label.setVisible(True)

        # Create a MixDesignResult so the send-to-quantification button works
        self._result = MixDesignResult(
            code_used=method,
            target_mean_strength_mpa=est["f_target"],
            w_c_ratio=wc_ratio,
            water_kg=est["water_kg"],
            cement_kg=est["cement_kg"],
            scm_kg=0.0,
            fine_aggregate_kg=est["fine_agg_kg"],
            coarse_aggregate_kg=est["coarse_agg_kg"],
            air_volume_percent=1.0,
        )

        # Enable export and send buttons
        self._btn_csv.setEnabled(True)
        self._btn_json.setEnabled(True)
        self._btn_report.setEnabled(True)
        self._btn_quant.setEnabled(True)

    def _refresh_display(self) -> None:
        """Re-render the current result with active unit conversions."""
        result = self._result
        if result is None:
            return

        up = self.unit_prefs
        vol = result.volume_m3

        # Warnings
        if result.warnings:
            self._warning_banner.setText("Warnings:\n" + "\n".join(result.warnings))
            self._warning_banner.setVisible(True)
        else:
            self._warning_banner.setVisible(False)

        # Update header to show volume
        vol_display = up.convert_volume_m3(vol)
        self._cards_label.setText(f"Material Quantities (for {vol_display:.3f} {up.volume_unit()})")

        # Material cards — scale by volume and convert mass values
        self._cards["cement"].set_value(
            up.convert_mass_kg(result.cement_kg * vol), unit=up.mass_unit())
        self._cards["water"].set_value(
            up.convert_mass_kg(result.water_kg * vol), unit=up.mass_unit())
        self._cards["fine_agg"].set_value(
            up.convert_mass_kg(result.fine_aggregate_kg * vol), unit=up.mass_unit())
        self._cards["coarse_agg"].set_value(
            up.convert_mass_kg(result.coarse_aggregate_kg * vol), unit=up.mass_unit())
        self._cards["scm"].set_value(
            up.convert_mass_kg(result.scm_kg * vol), unit=up.mass_unit())
        if result.admixture_kg is not None and result.admixture_kg > 0:
            self._cards["admix"].set_value(
                up.convert_mass_kg(result.admixture_kg * vol), unit=up.mass_unit())
        else:
            self._cards["admix"].set_value(0.0, unit=up.mass_unit())
        self._cards["wc_ratio"].set_value(result.w_c_ratio, unit="", fmt=".3f")
        self._cards["air"].set_value(result.air_volume_percent, unit="%")
        self._cards["target"].set_value(
            up.convert_strength_mpa(result.target_mean_strength_mpa),
            unit=up.strength_unit())

        # Mix ratio: Cement : Fine Aggregate : Coarse Aggregate (W/C)
        ratio = result.mix_ratio
        wc = result.w_c_ratio
        ratio_parts = f"{ratio['cement']:.1f} : {ratio['fine_aggregate']:.1f} : {ratio['coarse_aggregate']:.1f}"
        label_text = (
            f"<b>Mix Ratio</b><br>"
            f"<span style='font-size:16px;'>{ratio_parts} <span style='color:#6b7280;'>({wc:.3f})</span></span>"
        )
        self._mix_ratio_label.setText(label_text)
        self._mix_ratio_label.setVisible(True)

        # Show per-volume reference when volume != 1.0
        if vol != 1.0:
            vol_display = up.convert_volume_m3(vol)
            if up.is_imperial():
                cement_pv = result.cement_kg * 1.68555
                water_pv = result.water_kg * 1.68555
            else:
                cement_pv = result.cement_kg
                water_pv = result.water_kg
            self._total_label.setText(
                f"Quantities shown for {vol_display:.3f} {up.volume_unit()} "
                f"(per {up.volume_unit()}: Cement {cement_pv:.0f} "
                f"{up.mass_per_volume_unit()}, "
                f"Water {water_pv:.0f} {up.mass_per_volume_unit()})"
            )
            self._total_label.setVisible(True)
        else:
            self._total_label.setVisible(False)

        # Calculation steps
        self._steps_tree.clear()
        for step in result.steps:
            item = QTreeWidgetItem([
                str(step.step_number),
                step.description,
                step.formula,
                f"{step.result:.2f}",
                step.unit,
                step.clause_ref,
            ])
            self._steps_tree.addTopLevelItem(item)
        for col in range(6):
            self._steps_tree.resizeColumnToContents(col)

        # Enable export buttons
        self._btn_csv.setEnabled(True)
        self._btn_json.setEnabled(True)
        self._btn_report.setEnabled(True)
        self._btn_quant.setEnabled(True)

    def on_unit_changed(self) -> None:
        """Re-display results when unit preferences change."""
        if self._strength_estimate is not None:
            self._refresh_strength_estimate()
        self._refresh_display()

    def _on_send_to_quant(self) -> None:
        """Emit signal to transfer mix design data to quantification tab."""
        if self._result is not None:
            self.send_to_quantification.emit(self._result)

    def clear(self) -> None:
        """Reset the panel to empty state."""
        self._result = None
        self._warning_banner.setVisible(False)
        for card in self._cards.values():
            card.set_value(0)
            card._value.setText("—")
        self._total_label.setVisible(False)
        self._mix_ratio_label.setVisible(False)
        self._steps_tree.clear()
        self._btn_csv.setEnabled(False)
        self._btn_json.setEnabled(False)
        self._btn_report.setEnabled(False)
        self._btn_quant.setEnabled(False)
