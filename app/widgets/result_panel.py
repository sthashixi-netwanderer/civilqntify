"""Results panel for displaying concrete mix design output."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    - Responsive: shrinks gracefully, wraps text, never clips at narrow widths.
    """

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("result-card")
        # Responsive sizing: allow shrink, but keep readable minimum
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(132)
        self.setMinimumHeight(86)
        self.setStyleSheet(
            "QFrame#result-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setObjectName("result-label")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # Allow label to shrink and wrap instead of eliding
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._label.setStyleSheet(
            "color:#757684; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.04em;"
        )

        self._value = QLabel("\u2014")
        self._value.setObjectName("result-value")
        self._value.setWordWrap(True)
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._value.setStyleSheet(
            "color:#1e40af; font-family:'JetBrains Mono','Consolas',monospace; font-size:17px; font-weight:700;"
        )
        # Ensure long numbers can wrap or shrink without clipping
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._value.setMinimumWidth(0)

        self._unit = QLabel("")
        self._unit.setObjectName("result-unit")
        self._unit.setWordWrap(True)
        self._unit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._unit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._unit.setStyleSheet("color:#757684; font-size:10px;")

        layout.addWidget(self._label)
        layout.addWidget(self._value, stretch=1)
        layout.addWidget(self._unit)

        # Tooltip shows full value on hover if text is abbreviated
        self._value.setToolTip("")

    def set_value(self, value: float, unit: str = "kg/m\u00b3", fmt: str = ".1f") -> None:
        try:
            text = f"{value:{fmt}}"
        except Exception:
            text = str(value)
        self._value.setText(text)
        self._value.setToolTip(text + (f" {unit}" if unit else ""))
        self._unit.setText(unit)


class TargetStrengthResultPanel(QWidget):
    """Right-side panel for target mean strength only.

    This view deliberately contains no material quantities, W/C ratio, or mix
    ratio because those values belong to the full mix-design workflow.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result = None
        self.unit_prefs: UnitPreferences = get_unit_prefs()
        self._build_ui()
        self.unit_prefs.changed.connect(self.on_unit_changed)

    def _build_ui(self) -> None:
        # Wrap in scroll area so narrow windows can still see all cards
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        self._ts_scroll = scroll
        self._ts_container = container

        title = QLabel("Target Strength")
        title.setObjectName("section-title")
        title.setWordWrap(True)
        outer.addWidget(title)

        subtitle = QLabel(
            "Standard-based target mean strength. Mix proportions are not calculated in this mode."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 12px; color: #444653; padding-bottom: 4px;")
        subtitle.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        outer.addWidget(subtitle)

        # Responsive grid container
        self._ts_grid_container = QWidget()
        self._ts_grid_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._ts_grid = QGridLayout(self._ts_grid_container)
        self._ts_grid.setContentsMargins(0, 0, 0, 0)
        self._ts_grid.setSpacing(10)
        self._cards: dict[str, StatCard] = {}
        self._ts_card_order: list[str] = []
        for key, label in (
            ("characteristic", "Characteristic Strength"),
            ("std_dev", "Standard Deviation"),
            ("margin", "Strength Margin"),
            ("target", "Target Mean Strength"),
        ):
            card = StatCard(label)
            self._cards[key] = card
            self._ts_card_order.append(key)
        self._ts_current_cols = 2
        self._ts_last_width = -1
        self._reflow_ts_cards(force=True)
        outer.addWidget(self._ts_grid_container)

        self._formula_label = QLabel()
        self._formula_label.setWordWrap(True)
        self._formula_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._formula_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self._formula_label.setStyleSheet(
            "font-size: 13px; padding: 12px; background: #eff4ff; "
            "border: 1px solid #dbeafe; border-radius: 4px;"
        )
        outer.addWidget(self._formula_label)

        self._reference_label = QLabel()
        self._reference_label.setWordWrap(True)
        self._reference_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self._reference_label.setStyleSheet("font-size: 12px; color: #444653; padding: 4px 0;")
        outer.addWidget(self._reference_label)
        outer.addStretch()
        scroll.setWidget(container)
        main.addWidget(scroll)
        self.clear()

    def _ts_columns_for_width(self, width: int) -> int:
        if width >= 420:
            return 2
        return 1

    def _reflow_ts_cards(self, force: bool = False) -> None:
        try:
            avail = self._ts_scroll.viewport().width()
        except Exception:
            avail = self.width()
        if avail < 50:
            avail = self.width() or self._ts_grid_container.width() or 360
        avail -= 28
        cols = self._ts_columns_for_width(avail)
        if not force and cols == getattr(self, "_ts_current_cols", None) and avail == getattr(self, "_ts_last_width", None):
            return
        self._ts_current_cols = cols
        self._ts_last_width = avail
        while self._ts_grid.count():
            it = self._ts_grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
        for idx, key in enumerate(self._ts_card_order):
            card = self._cards[key]
            r = idx // cols
            c = idx % cols
            self._ts_grid.addWidget(card, r, c)
        for c in range(cols):
            self._ts_grid.setColumnStretch(c, 1)
        for c in range(cols, 2):
            self._ts_grid.setColumnStretch(c, 0)
        self._ts_grid_container.updateGeometry()
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        try:
            self._reflow_ts_cards()
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            self._reflow_ts_cards(force=True)
        except Exception:
            pass

    def display_result(self, result) -> None:
        """Display a :class:`TargetStrengthResult` in the active units."""
        self._result = result
        self._refresh_display()

    def _refresh_display(self) -> None:
        if self._result is None:
            return

        up = self.unit_prefs
        strength_unit = up.strength_unit()
        characteristic = up.convert_strength_mpa(
            self._result.characteristic_strength_mpa
        )
        target = up.convert_strength_mpa(self._result.target_mean_strength_mpa)
        margin = up.convert_strength_mpa(self._result.margin_mpa)
        self._cards["characteristic"].set_value(characteristic, strength_unit)
        self._cards["margin"].set_value(margin, strength_unit)
        self._cards["target"].set_value(target, strength_unit)

        if self._result.standard_deviation_mpa is None:
            self._cards["std_dev"].set_value(0.0, strength_unit)
            self._cards["std_dev"]._value.setText("—")
            self._cards["std_dev"]._unit.setText("not used")
        else:
            self._cards["std_dev"].set_value(
                up.convert_strength_mpa(self._result.standard_deviation_mpa),
                strength_unit,
            )

        self._formula_label.setText(
            f"<b>{self._result.standard_name}</b><br/>"
            f"{self._result.formula.replace(chr(10), '<br/>')}"
        )
        self._reference_label.setText(f"Reference: {self._result.reference}")

    def on_unit_changed(self) -> None:
        """Re-render strength values when the unit preference changes."""
        self._refresh_display()

    def clear(self) -> None:
        """Reset the target-strength result view."""
        self._result = None
        for card in self._cards.values():
            card.set_value(0.0)
            card._value.setText("—")
            card._unit.setText("")
        self._formula_label.setText("Calculate a target strength to see the result.")
        self._reference_label.setText("")


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
        # Outer wrapper is a scroll area so all content remains visible
        # when the window is narrowed or shortened. Inner container holds
        # the original vertical stack.
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("result-scroll-container")
        container.setMinimumWidth(0)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        outer.setSizeConstraint(outer.SizeConstraint.SetNoConstraint)
        self._outer_layout = outer  # keep ref for reflow tests
        self._scroll_container = container

        # Warnings banner (hidden by default)
        self._warning_banner = QLabel()
        self._warning_banner.setObjectName("warning-banner")
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setVisible(False)
        # allow banner to expand vertically when wrapping
        self._warning_banner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self._warning_banner.setMinimumWidth(0)
        outer.addWidget(self._warning_banner)

        # IS 10262:2019 Clause 5.8 Trial Mixes Prompt (hidden by default)
        self._is_trial_frame = QFrame()
        self._is_trial_frame.setObjectName("result-card")
        self._is_trial_frame.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px;"
        )
        self._is_trial_frame.setVisible(False)
        self._is_trial_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        trial_layout = QVBoxLayout(self._is_trial_frame)
        trial_layout.setContentsMargins(10, 8, 10, 8)
        trial_layout.setSpacing(6)

        trial_title = QLabel("IS 10262:2019 Clause 5.8 — Trial Mixes Protocol")
        trial_title.setWordWrap(True)
        trial_title.setMinimumWidth(0)
        trial_title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        trial_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 0.05em; color: #1e3a8a;"
        )
        trial_layout.addWidget(trial_title)

        self._is_trial_lbl = QLabel()
        self._is_trial_lbl.setWordWrap(True)
        self._is_trial_lbl.setMinimumWidth(0)
        self._is_trial_lbl.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.35;")
        self._is_trial_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        trial_layout.addWidget(self._is_trial_lbl)

        self._btn_view_trials = QPushButton("📋 View 4-Trial Batches Protocol & Reporting Guide (Clause 5.8)")
        self._btn_view_trials.setObjectName("secondary")
        self._btn_view_trials.setStyleSheet("font-size: 12px; font-weight: 600; padding: 6px 10px;")
        self._btn_view_trials.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_view_trials.clicked.connect(self._on_view_is_trials)
        trial_layout.addWidget(self._btn_view_trials)

        outer.addWidget(self._is_trial_frame)

        # Strength estimation from mix ratio (hidden by default)
        self._strength_est_frame = QFrame()
        self._strength_est_frame.setObjectName("result-card")
        self._strength_est_frame.setVisible(False)
        self._strength_est_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        est_layout = QVBoxLayout(self._strength_est_frame)
        est_layout.setContentsMargins(12, 10, 12, 10)
        est_layout.setSpacing(4)

        est_title = QLabel("Target Strength Estimation")
        est_title.setWordWrap(True)
        est_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; text-transform: uppercase; "
            "letter-spacing: 0.05em; color: #444653;"
        )
        est_layout.addWidget(est_title)

        self._strength_est_html = QLabel()
        self._strength_est_html.setWordWrap(True)
        self._strength_est_html.setStyleSheet("font-size: 12px; padding: 2px 0;")
        self._strength_est_html.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        est_layout.addWidget(self._strength_est_html)

        outer.addWidget(self._strength_est_frame)

        # Material quantities — responsive card grid
        self._cards_label = QLabel("Material Quantities (per m³)")
        self._cards_label.setObjectName("section-title")
        self._cards_label.setWordWrap(True)
        outer.addWidget(self._cards_label)

        # Container for the responsive grid — we keep the grid as an
        # attribute so resizeEvent can reflow it without touching logic.
        self._cards_container = QWidget()
        self._cards_container.setMinimumWidth(0)
        self._cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._grid = QGridLayout(self._cards_container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._grid.setRowStretch(0, 0)
        self._grid.setSizeConstraint(self._grid.SizeConstraint.SetNoConstraint)

        self._cards: dict[str, StatCard] = {}
        self._card_order: list[str] = []
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
        for key, label in card_defs:
            card = StatCard(label)
            self._cards[key] = card
            self._card_order.append(key)

        # Initial column count — will be corrected on first resize/show
        self._current_columns = 4
        self._reflow_cards(force=True)

        outer.addWidget(self._cards_container)

        # Mix ratio display
        self._mix_ratio_label = QLabel()
        self._mix_ratio_label.setObjectName("section-title")
        self._mix_ratio_label.setWordWrap(True)
        self._mix_ratio_label.setStyleSheet("font-size: 14px; padding: 6px;")
        self._mix_ratio_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self._mix_ratio_label.setVisible(False)
        outer.addWidget(self._mix_ratio_label)

        # Total volume section
        self._total_label = QLabel()
        self._total_label.setObjectName("section-title")
        self._total_label.setWordWrap(True)
        self._total_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        outer.addWidget(self._total_label)

        # Calculation steps tree — responsive header
        steps_label = QLabel("Calculation Steps")
        steps_label.setObjectName("section-title")
        steps_label.setWordWrap(True)
        outer.addWidget(steps_label)

        self._steps_tree = QTreeWidget()
        self._steps_tree.setHeaderLabels(["#", "Description", "Formula", "Result", "Unit", "Reference"])
        self._steps_tree.setAlternatingRowColors(True)
        self._steps_tree.setRootIsDecorated(False)
        self._steps_tree.setColumnCount(6)
        self._steps_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._steps_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._steps_tree.setMinimumWidth(0)
        self._steps_tree.setMinimumHeight(140)
        # Responsive column sizing: Description & Formula stretch, others adapt
        header = self._steps_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        # Keep Formula readable but not dominating at narrow widths
        header.resizeSection(2, 160)
        self._steps_tree.setWordWrap(True)
        outer.addWidget(self._steps_tree, stretch=1)

        # Export buttons — responsive: single row when spacious, two rows when narrow
        self._btn_container = QWidget()
        self._btn_container.setMinimumWidth(0)
        self._btn_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_grid = QGridLayout(self._btn_container)
        self._btn_grid.setContentsMargins(0, 0, 0, 0)
        self._btn_grid.setSpacing(8)
        self._btn_grid.setSizeConstraint(self._btn_grid.SizeConstraint.SetNoConstraint)
        self._btn_csv = QPushButton("Export CSV")
        self._btn_csv.setObjectName("secondary")
        self._btn_csv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_csv.setMinimumWidth(86)
        self._btn_report = QPushButton("Export PDF")
        self._btn_report.setObjectName("secondary")
        self._btn_report.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_report.setMinimumWidth(86)
        self._btn_csv.setEnabled(False)
        self._btn_report.setEnabled(False)
        self._btn_quant = QPushButton("Send to Quantification")
        self._btn_quant.setEnabled(False)
        self._btn_quant.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_quant.setMinimumWidth(148)
        self._btn_quant.clicked.connect(self._on_send_to_quant)
        # Initial placement (single row); will be corrected on first reflow
        self._btn_grid.addWidget(self._btn_csv, 0, 0)
        self._btn_grid.addWidget(self._btn_report, 0, 1)
        self._btn_grid.addWidget(self._btn_quant, 0, 2)
        for c in range(3):
            self._btn_grid.setColumnStretch(c, 1)
        self._btn_current_mode = "single"
        outer.addWidget(self._btn_container)

        outer.addStretch(1)

        self._scroll.setWidget(container)
        main.addWidget(self._scroll)

        # Export signal connections will be wired by the parent tab
        self.btn_csv = self._btn_csv
        self.btn_report = self._btn_report

        # Track last reflow width to avoid thrashing
        self._last_reflow_width = -1

    # ── Responsive grid helpers ─────────────────────────────────────
    def _columns_for_width(self, width: int) -> int:
        """Return column count for the material-cards grid.

        Thresholds keep each card ≥132 px + 8 px spacing readable:
        - ≥ 620 px → 4 columns ( spacious )
        - 440–619 → 3 columns
        - 300–439 → 2 columns
        -  < 300   → 1 column (stacked)
        """
        if width >= 620:
            return 4
        if width >= 440:
            return 3
        if width >= 300:
            return 2
        return 1

    def _reflow_cards(self, force: bool = False) -> None:
        """Re-layout StatCards into the optimal column count."""
        # Use the scroll viewport width if available, else the widget width
        try:
            avail = self._scroll.viewport().width()
        except Exception:
            avail = self.width()
        # Fallback when not yet shown (viewport 0)
        if avail < 50:
            avail = self.width() or self._cards_container.width() or 400
        # Account for outer margins (12+12) and container margins
        avail -= 28
        cols = self._columns_for_width(avail)
        if not force and cols == getattr(self, "_current_columns", None) and avail == self._last_reflow_width:
            return
        self._current_columns = cols
        self._last_reflow_width = avail

        # Clear existing items
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # Re-populate
        for idx, key in enumerate(self._card_order):
            card = self._cards[key]
            r = idx // cols
            c = idx % cols
            self._grid.addWidget(card, r, c)

        # Equal stretch across active columns
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        # Remove stretch from unused columns (keeps old stretch from polluting)
        for c in range(cols, 4):
            self._grid.setColumnStretch(c, 0)
        self._grid.setRowStretch(self._grid.rowCount(), 0)
        # Force layout update
        self._cards_container.updateGeometry()
        self.updateGeometry()

    def _reflow_buttons(self, force: bool = False) -> None:
        """Responsive export bar: 1 row when spacious, 2 rows when narrow."""
        try:
            avail = self._scroll.viewport().width()
        except Exception:
            avail = self.width()
        if avail < 50:
            avail = self.width() or self._btn_container.width() or 400
        avail -= 24  # outer margins
        # 380 is enough for 86+86+148+16 spacing ≈336 + margins; use 360 as threshold
        mode = "single" if avail >= 360 else "wrapped"
        if not force and mode == getattr(self, "_btn_current_mode", None):
            # Still need to check avail changed significantly? keep simple
            pass
        else:
            # Only re-layout when mode changes or forced
            if mode != getattr(self, "_btn_current_mode", None) or force:
                # Clear
                while self._btn_grid.count():
                    it = self._btn_grid.takeAt(0)
                    w = it.widget()
                    if w is not None:
                        w.setParent(None)
                for c in range(3):
                    self._btn_grid.setColumnStretch(c, 0)
                    self._btn_grid.setRowStretch(c, 0)
                if mode == "single":
                    self._btn_grid.addWidget(self._btn_csv, 0, 0)
                    self._btn_grid.addWidget(self._btn_report, 0, 1)
                    self._btn_grid.addWidget(self._btn_quant, 0, 2)
                    for c in range(3):
                        self._btn_grid.setColumnStretch(c, 1)
                else:
                    # Wrapped: CSV | PDF on row 0, Quant spans row 1
                    self._btn_grid.addWidget(self._btn_csv, 0, 0)
                    self._btn_grid.addWidget(self._btn_report, 0, 1)
                    self._btn_grid.addWidget(self._btn_quant, 1, 0, 1, 2)
                    self._btn_grid.setColumnStretch(0, 1)
                    self._btn_grid.setColumnStretch(1, 1)
                self._btn_current_mode = mode
                self._btn_container.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow_cards()
        self._reflow_buttons()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reflow_cards(force=True)
        self._reflow_buttons(force=True)

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

        # IS 10262:2019 Clause 5.8 Trial Mixes Prompt
        is_is_code = "is10262" in result.code_used.lower() or "is 10262" in result.code_used.lower()
        if is_is_code:
            wc = result.w_c_ratio
            wc3 = round(wc * 0.90, 2)
            wc4 = round(wc * 1.10, 2)
            html = (
                "<b>Mandatory Trial Mixes Procedure (IS 10262:2019 Clause 5.8):</b><br/>"
                "Calculated laboratory proportions must be verified and adjusted using 4 trial batches:<br/>"
                f"• <b>Trial 1</b>: Calculated proportions (W/C {wc:.2f}) — test slump/flow, observe bleeding/segregation & finish.<br/>"
                f"• <b>Trial 2</b>: Adjust water/admixture if slump deviates, holding free W/C constant at {wc:.2f}.<br/>"
                f"• <b>Trials 3 & 4</b>: Same water as Trial 2 with W/C varied by ±10% (<b>{wc3:.2f}</b> & <b>{wc4:.2f}</b>) to develop compressive strength vs. W/C curve.<br/>"
                "• <b>Final Proportions & §5.8.1 Reporting</b>: Select final mix satisfying strength & IS 456 Table 5 durability, perform site field trials, and document full trial records."
            )
            self._is_trial_lbl.setText(html)
            self._is_trial_frame.setVisible(True)
        else:
            self._is_trial_frame.setVisible(False)

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

        # Calculation steps — keep headers responsive (Description stretches)
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
            # Allow wrapping for long descriptions
            item.setToolTip(1, step.description)
            item.setToolTip(2, step.formula)
            self._steps_tree.addTopLevelItem(item)
        # Resize only compact columns; keep Description stretched
        for col in (0, 3, 4, 5):
            self._steps_tree.resizeColumnToContents(col)
        # Give Formula a sensible default without forcing overflow
        if self._steps_tree.topLevelItemCount() > 0:
            self._steps_tree.resizeColumnToContents(2)
            fm_w = self._steps_tree.columnWidth(2)
            # Cap Formula width so narrow windows don't force horizontal clip
            max_fm = max(120, min(220, int(self.width() * 0.30)))
            if fm_w > max_fm:
                self._steps_tree.setColumnWidth(2, max_fm)

        # Ensure grid is optimal for current width after new content
        self._reflow_cards()

        # Enable export buttons
        self._btn_csv.setEnabled(True)
        self._btn_report.setEnabled(True)
        self._btn_quant.setEnabled(True)

    def on_unit_changed(self) -> None:
        """Re-display results when unit preferences change."""
        if self._strength_estimate is not None:
            self._refresh_strength_estimate()
        self._refresh_display()

    def _on_view_is_trials(self) -> None:
        """Open the IS 10262 Clause 5.8 Trial Mixes protocol dialog."""
        if self._result is None:
            return
        from app.widgets.is_trial_mixes_dialog import ISTrialMixesDialog

        inp = getattr(self._result, "_input", None)
        dlg = ISTrialMixesDialog(self._result, inp=inp, parent=self)
        dlg.exec()

    def _on_send_to_quant(self) -> None:
        """Emit signal to transfer mix design data to quantification tab."""
        if self._result is not None:
            self.send_to_quantification.emit(self._result)

    def clear(self) -> None:
        """Reset the panel to empty state."""
        self._result = None
        self._strength_estimate = None
        self._strength_est_frame.setVisible(False)
        self._is_trial_frame.setVisible(False)
        self._warning_banner.setVisible(False)
        for card in self._cards.values():
            card.set_value(0)
            card._value.setText("—")
        self._total_label.setVisible(False)
        self._mix_ratio_label.setVisible(False)
        self._steps_tree.clear()
        self._btn_csv.setEnabled(False)
        self._btn_report.setEnabled(False)
        self._btn_quant.setEnabled(False)
