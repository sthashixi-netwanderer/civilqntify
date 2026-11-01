"""Centralized tokenized QSS stylesheet for CivilQntify.

Clean Studio Light desktop design system:
- High-legibility desktop typography with explicit font-size tokens.
- Strict 0px/2px/4px corner radii scale (no arbitrary 16px SaaS card rounding).
- Accessible contrast ratios (all text >= 4.5:1 against surfaces).
- Full interactive pseudo-states (:hover, :pressed, :disabled, :focus).
- Semantic desktop layout and container hierarchy.
"""

from __future__ import annotations

import os
import pathlib
import sys


import re


# Mixed-case abbreviations and unit symbols that keep their typed casing
# under sentence case. All-uppercase tokens (initialisms such as "IS",
# "PSD", "OPC", "NMSA", "W/C", "D10", "GH₵") are preserved automatically
# without needing an entry here.
_KEEP_CASE_TOKENS = frozenset({
    "MPa", "kPa", "kN",
    "Agg", "Qty", "Vol", "No", "Ref", "Fn", "Ch",
    "Cu", "Cc", "Vebe",
})

_WS_SPLIT = re.compile(r"(\s+)")
_LABEL_PUNCT = "()[]{},.:;'\"“”‘’"


def _sentence_case_subtoken(sub: str) -> str:
    """Sentence-case one slash-separated sub-token ("W", "C", "mm", "m³")."""
    if not sub or sub in _KEEP_CASE_TOKENS:
        return sub
    has_upper = any(ch.isupper() for ch in sub)
    has_lower = any(ch.islower() for ch in sub)
    if has_upper and not has_lower:
        return sub  # initialism: "IS", "PSD", "NMSA", "D10", "GH₵"
    if not has_upper:
        return sub  # already lowercase: "kg", "mm", "µm", digits
    return sub.lower()  # Title-case word → sentence-case word


def sentence_case_si_units(text: str) -> str:
    """Convert display text to sentence case, preserving abbreviations.

    Field names render in sentence case ("Target mean strength (MPa)"),
    while initialisms, abbreviations and unit symbols keep their typed or
    canonical casing ("IS 10262", "PSD", "OPC", "W/C", "NMSA", "MPa",
    "kg/m³", "75-µm"). Purely lowercase tokens are untouched, so the SI
    micro sign µ is never rewritten — unlike ``str.upper()`` and Qt's
    ``text-transform: uppercase``, which map µ to capital Greek Mu and
    would render "75-µm" as "75-MM".

    The operation is idempotent: applying it twice returns the same text.
    """
    if not text:
        return text
    parts = _WS_SPLIT.split(text)
    for i, part in enumerate(parts):
        if not part or part.isspace():
            continue
        core = part.strip(_LABEL_PUNCT)
        if not core:
            continue
        rebuilt = "/".join(
            _sentence_case_subtoken(sub) for sub in core.split("/")
        )
        if rebuilt != core:
            parts[i] = part.replace(core, rebuilt, 1)
    out = "".join(parts)
    # Capitalise the first ASCII letter only — uppercasing µ maps it to
    # capital Greek Mu, which reads as "M" (the reason Python-side casing
    # replaced Qt's text-transform in the first place).
    for j, ch in enumerate(out):
        if ch.isalpha():
            if "a" <= ch <= "z":
                out = out[:j] + ch.upper() + out[j + 1:]
            break
    return out


def _resource_base() -> pathlib.Path:
    """Return the directory that contains ``app/resources``.

    In a PyInstaller bundle ``_MEIPASS`` points to the extraction temp
    directory (onefile) or the distribution folder already contains the
    resources. Falling back to ``__file__`` covers the normal dev run.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = pathlib.Path(meipass) / "app" / "resources"
        if p.is_dir():
            return p
        p2 = pathlib.Path(meipass) / "resources"
        if p2.is_dir():
            return p2
    return pathlib.Path(__file__).resolve().parent / "resources"


_HERE = os.path.dirname(os.path.abspath(__file__))
_RESOURCE_BASE = _resource_base()


def _get_resource_path(name: str) -> str:
    path = os.path.join(str(_RESOURCE_BASE), name)
    return path.replace("\\", "/")


_DOWN_ARROW = _get_resource_path("down_arrow.svg")
_DOWN_ARROW_DISABLED = _get_resource_path("down_arrow_disabled.svg")
_UP_ARROW = _get_resource_path("up_arrow.svg")
_UP_ARROW_ACTIVE = _get_resource_path("up_arrow_active.svg")
_UP_ARROW_DISABLED = _get_resource_path("up_arrow_disabled.svg")
_CHECK_MARK = _get_resource_path("checkmark.svg")

# ── Clean Studio Light Design Tokens ──────────────────────────────────────────
# Surface & Canvas:
#   Window background:  #f3f4f6 (clean neutral desktop canvas)
#   Panel background:   #ffffff (crisp white content area & inputs)
#   Subdued panel:      #f9fafb (table alternating rows, header well)
#   Sunken well:        #edf0f2 (read-only fields, recessed inspector)
# Borders:
#   Standard border:    #d1d5db (crisp 1px desktop boundary, >3:1 contrast)
#   Subtle border:      #e5e7eb (interior dividers, gridlines)
#   Focus ring:         #1d4ed8 (accessible focus outline)
# Typography & Contrast:
#   Text primary:       #111827 (high-contrast deep charcoal, 16:1 against white)
#   Text secondary:     #374151 (labels and headers, 9:1 against white)
#   Text muted:         #4b5563 (metadata, captions, units, >4.5:1 WCAG AA)
#   Text disabled:      #9ca3af (inactive controls)
# Accent Colors:
#   Primary:            #1d4ed8 (cobalt blue)
#   Primary hover:      #1e40af
#   Primary pressed:    #1e3a8a
#   Primary tint:       #eff6ff (active tab/row selection background)
# Semantic Colors:
#   Success:            #047857 / #ecfdf5 / #10b981
#   Warning:            #b45309 / #fef3c7 / #f59e0b
#   Danger:             #b91c1c / #fef2f2 / #ef4444
# Radii scale:
#   Windows & Panes:    0px
#   Inputs & Buttons:   4px
#   Badges & Pills:     4px

_STYLESHEET_RAW = """
/* ── Global Desktop Canvas ──
 * Keep the neutral canvas on window surfaces only. Painting it on every
 * QWidget (as this rule previously did) also painted QLabel and form-row
 * containers, producing a grey chip behind every field name on the white
 * tab panels. Child widgets stay transparent so they inherit their panel.
 */
QWidget {
    background: transparent;
    color: #111827;
    font-family: "Inter", "Segoe UI", -apple-system, "SF Pro Text", "Roboto", "Noto Sans", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #f3f4f6;
}

/* ── Tab Navigation ── */
QTabWidget::pane {
    border: 1px solid #d1d5db;
    background: #ffffff;
    border-radius: 0px;
    top: -1px;
}

QTabBar::tab {
    background: #e5e7eb;
    color: #374151;
    padding: 7px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #d1d5db;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1d4ed8;
    border-top: 2px solid #1d4ed8;
    border-bottom: 1px solid #ffffff;
}

QTabBar::tab:hover:!selected {
    background: #f9fafb;
    color: #111827;
}

QTabBar::tab:disabled {
    color: #9ca3af;
    background: #f3f4f6;
}

/* ── Typography & Labels ── */
QLabel {
    background: transparent;
    color: #111827;
    font-size: 13px;
}

QLabel#section-title {
    color: #111827;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 8px 0 3px 0;
    border-bottom: 1px solid #e5e7eb;
}

QLabel#form-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: #374151;
}

QLabel#dialog-title {
    font-size: 15px;
    font-weight: 700;
    color: #111827;
}

QLabel#dialog-desc {
    font-size: 12px;
    color: #4b5563;
    line-height: 1.4;
}

QLabel#dialog-note {
    font-size: 11px;
    color: #4b5563;
}

QLabel#stat-highlight {
    font-weight: 600;
    color: #1d4ed8;
    font-size: 13px;
}

QLabel#form-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #4b5563;
}

QLabel#warning-text {
    color: #b45309;
    font-weight: 500;
    font-size: 12px;
}

/* ── Banners & Status Badges ── */
QLabel#warning-banner {
    /* Inline caution note: text only on the app background — no badge
       background, border or padding. */
    color: #92400e;
    font-weight: 600;
    font-size: 12px;
}

QLabel#info-banner {
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
}

QLabel#success-banner {
    background-color: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
}

QLabel#danger-banner, QLabel#compliance-failure-banner {
    background-color: #fef2f2;
    color: #991b1b;
    border: 1px solid #ef4444;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: 700;
    font-size: 12px;
}

QLabel#callout-panel, QFrame#callout-panel {
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}

QLabel#callout-panel:disabled, QFrame#callout-panel:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border: 1px solid #d1d5db;
}

QLabel#callout-warning, QFrame#callout-warning {
    background-color: #fef3c7;
    color: #92400e;
    border: 1px solid #f59e0b;
    border-radius: 4px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}

QFrame#separator {
    background-color: #e5e7eb;
    max-height: 1px;
    border: none;
}

/* ── Info Overlay ── */
QLabel#info-overlay-label {
    background-color: #1f2937;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 10px 14px;
    font-size: 12px;
    line-height: 1.4;
}

QScrollArea#info-overlay-scroll {
    background-color: transparent;
    border: none;
}

/* ── PSD Badges & Cards ── */
QFrame#psd-stat-card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-left: 3px solid #1d4ed8;
    border-radius: 4px;
}

QLabel#psd-stat-label {
    font-size: 10px;
    font-weight: 700;
    color: #4b5563;
    letter-spacing: 0.05em;
}

QLabel#psd-stat-val {
    font-size: 15px;
    font-weight: 600;
    color: #1d4ed8;
    font-family: "JetBrains Mono", "SF Mono", "Consolas", monospace;
}

QLabel#psd-badge-pass {
    color: #ffffff;
    background-color: #047857;
    padding: 8px 14px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 12px;
}

QLabel#psd-badge-fail {
    color: #ffffff;
    background-color: #b91c1c;
    padding: 8px 14px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 12px;
}

QLabel#psd-badge-neutral {
    color: #ffffff;
    background-color: #4b5563;
    padding: 8px 14px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 12px;
}

QLabel#cell-warning {
    color: #b45309;
    font-weight: 600;
}

QLabel#cell-dim {
    color: #4b5563;
}

QLabel#cell-primary {
    color: #1d4ed8;
    font-weight: 700;
}

QLabel#cell-success {
    color: #047857;
    font-weight: 700;
}

QLabel#cell-error {
    color: #b91c1c;
    font-weight: 700;
}

/* ── Structured Metric & Result Cards ── */
QFrame#result-card, QFrame#stat-card, QFrame#metric-card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 8px;
}

QLabel#result-label, QLabel#stat-label {
    color: #4b5563;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
}

QLabel#result-value, QLabel#stat-value {
    color: #111827;
    font-family: "JetBrains Mono", "SF Mono", "Consolas", monospace;
    font-size: 18px;
    font-weight: 700;
}

QLabel#result-unit, QLabel#stat-unit {
    color: #4b5563;
    font-size: 11px;
    font-weight: 500;
}

QLabel#summary-total-label {
    font-size: 15px;
    font-weight: 700;
    color: #1d4ed8;
}

QLabel#summary-total-amt {
    font-size: 15px;
    font-weight: 700;
    color: #1d4ed8;
    font-family: "JetBrains Mono", monospace;
}

QLabel#summary-subtotal-label {
    font-weight: 600;
    color: #111827;
}

QLabel#summary-subtotal-amt {
    font-weight: 600;
    color: #111827;
    font-family: "JetBrains Mono", monospace;
}

QLabel#summary-row-label {
    color: #374151;
}

QLabel#summary-row-amt {
    color: #111827;
    font-family: "JetBrains Mono", monospace;
}

QFrame#summary-frame {
    background-color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 4px;
    padding: 12px;
}

QFrame#trial-frame {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 8px;
}

QFrame#trial-frame[active="true"], QFrame#trial-frame-active {
    background-color: #eff6ff;
    border: 2px solid #1d4ed8;
    border-radius: 4px;
    padding: 8px;
}

/* ── Form Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 6px 10px;
    color: #111827;
    font-size: 13px;
    min-height: 20px;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border: 1px solid #9ca3af;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #1d4ed8;
}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border: 1px solid #e5e7eb;
}

QLineEdit[readOnly="true"], QSpinBox[readOnly="true"], QDoubleSpinBox[readOnly="true"] {
    background-color: #f9fafb;
    color: #374151;
}

/* ── Combo Box ── */
QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-position: center right;
}

QComboBox::down-arrow {
    image: url(__DOWN_ARROW_PATH__);
    width: 10px;
    height: 6px;
}

QComboBox::down-arrow:on {
    image: url(__UP_ARROW_ACTIVE_PATH__);
    width: 10px;
    height: 6px;
}

QComboBox::down-arrow:disabled {
    image: url(__DOWN_ARROW_DISABLED_PATH__);
    width: 10px;
    height: 6px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 2px;
    color: #111827;
    selection-background-color: #eff6ff;
    selection-color: #1d4ed8;
    outline: none;
    padding: 2px;
}

QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 2px;
    color: #111827;
    min-height: 18px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #eff6ff;
    color: #1d4ed8;
    font-weight: 600;
}

QComboBox QAbstractItemView::item:hover:!selected {
    background-color: #f3f4f6;
    color: #111827;
}

/* ── Checkbox & Radio Buttons ── */
QCheckBox, QRadioButton {
    color: #111827;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox:disabled, QRadioButton:disabled {
    color: #9ca3af;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #d1d5db;
    background: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #1d4ed8;
}

QCheckBox::indicator:disabled {
    background: #f3f4f6;
    border-color: #e5e7eb;
}

QCheckBox::indicator:checked {
    background: #1d4ed8;
    border-color: #1d4ed8;
    image: url(__CHECK_MARK_PATH__);
}

QCheckBox::indicator:checked:hover {
    background: #1e40af;
    border-color: #1e40af;
    image: url(__CHECK_MARK_PATH__);
}

QCheckBox::indicator:checked:disabled {
    background: #9ca3af;
    border-color: #9ca3af;
    image: url(__CHECK_MARK_PATH__);
}

QCheckBox::indicator:indeterminate {
    background: #1d4ed8;
    border-color: #1d4ed8;
    image: url(__CHECK_MARK_PATH__);
}

/* ── Action Buttons ── */
QPushButton {
    background-color: #1d4ed8;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 13px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #1e40af;
    border-color: #1e40af;
}

QPushButton:pressed {
    background-color: #1e3a8a;
    border-color: #1e3a8a;
}

QPushButton:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border-color: #e5e7eb;
}

QPushButton#secondary {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #d1d5db;
    font-weight: 500;
}

QPushButton#secondary:hover {
    background-color: #f9fafb;
    border-color: #9ca3af;
    color: #111827;
}

QPushButton#secondary:pressed {
    background-color: #f3f4f6;
    border-color: #6b7280;
}

QPushButton#secondary:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border-color: #e5e7eb;
}

QPushButton#danger-btn {
    background-color: #ffffff;
    color: #b91c1c;
    border: 1px solid #fca5a5;
    font-weight: 600;
}

QPushButton#danger-btn:hover {
    background-color: #fef2f2;
    border-color: #dc2626;
    color: #991b1b;
}

QPushButton#danger-btn:pressed {
    background-color: #fee2e2;
    border-color: #b91c1c;
}

QPushButton#danger-btn:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
    border-color: #e5e7eb;
}

QPushButton#weather-btn {
    background-color: #1d4ed8;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#weather-btn:hover {
    background-color: #1e40af;
    border-color: #1e40af;
}

QPushButton#weather-btn:pressed {
    background-color: #1e3a8a;
    border-color: #1e3a8a;
}

QPushButton#settings-btn {
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    background: transparent;
}

QPushButton#settings-btn:hover {
    background-color: #e5e7eb;
    border-color: #d1d5db;
}

QPushButton#settings-btn:pressed {
    background-color: #d1d5db;
}

QPushButton#info-btn {
    background-color: #e5e7eb;
    color: #374151;
    border: 1px solid #d1d5db;
    border-radius: 9px;
    padding: 0px;
    font-size: 10px;
    font-weight: 700;
    font-style: normal;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
}

QPushButton#info-btn:hover {
    background-color: #1d4ed8;
    color: #ffffff;
    border-color: #1d4ed8;
}

QPushButton#info-btn:pressed {
    background-color: #1e3a8a;
    color: #ffffff;
    border-color: #1e3a8a;
}

/* ── Group Boxes ── */
QGroupBox {
    border: 1px solid #d1d5db;
    border-radius: 2px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.04em;
    color: #111827;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 6px;
    background-color: #ffffff;
}

/* ── Desktop Splitters ── */
QSplitter::handle {
    background: #d1d5db;
    width: 4px;
    margin: 0 1px;
}

QSplitter::handle:hover {
    background: #1d4ed8;
}

QSplitter::handle:pressed {
    background: #1e3a8a;
}

/* ── Scroll Areas & Bars ── */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #f3f4f6;
    width: 10px;
    border-left: 1px solid #e5e7eb;
}

QScrollBar::handle:vertical {
    background: #d1d5db;
    border-radius: 4px;
    min-height: 24px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #9ca3af;
}

QScrollBar::handle:vertical:pressed {
    background: #6b7280;
}

QScrollBar:horizontal {
    background: #f3f4f6;
    height: 10px;
    border-top: 1px solid #e5e7eb;
}

QScrollBar::handle:horizontal {
    background: #d1d5db;
    border-radius: 4px;
    min-width: 24px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #9ca3af;
}

QScrollBar::handle:horizontal:pressed {
    background: #6b7280;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}

/* ── Tables & Trees ── */
QTreeWidget, QTreeView, QTableWidget, QTableView {
    background-color: #ffffff;
    alternate-background-color: #f9fafb;
    border: 1px solid #d1d5db;
    border-radius: 0px;
    color: #111827;
    font-size: 13px;
    gridline-color: #e5e7eb;
}

QTreeWidget::item, QTreeView::item, QTableWidget::item, QTableView::item {
    padding: 5px 8px;
    border-bottom: 1px solid #f3f4f6;
}

QTreeWidget::item:selected, QTreeView::item:selected,
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #eff6ff;
    color: #1d4ed8;
}

QTreeWidget::item:hover, QTreeView::item:hover,
QTableWidget::item:hover, QTableView::item:hover {
    background-color: #f3f4f6;
}

QHeaderView::section {
    background-color: #f3f4f6;
    color: #374151;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #d1d5db;
    border-right: 1px solid #e5e7eb;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.03em;
}

/* ── Spin Box Up/Down Controls ── */
QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #d1d5db;
    border-bottom: 1px solid #e5e7eb;
    border-top-right-radius: 4px;
    background: #f9fafb;
}

QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #d1d5db;
    border-top: 1px solid #e5e7eb;
    border-bottom-right-radius: 4px;
    background: #f9fafb;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: url(__UP_ARROW_PATH__);
    width: 9px;
    height: 5px;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: url(__DOWN_ARROW_PATH__);
    width: 9px;
    height: 5px;
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background: #eff6ff;
}

QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled {
    image: url(__UP_ARROW_DISABLED_PATH__);
}

QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {
    image: url(__DOWN_ARROW_DISABLED_PATH__);
}

/* ── Custom Window Chrome ── */
QWidget#titlebar {
    background-color: #ffffff;
    border-bottom: 1px solid #d1d5db;
}

QWidget#titlebar-brand {
    background: transparent;
}

QLabel#titlebar-logo,
QLabel#titlebar-title,
QLabel#titlebar-subtitle {
    background: transparent;
}

QLabel#titlebar-title {
    font-size: 14px;
    font-weight: 700;
    color: #111827;
    letter-spacing: 0.01em;
}

QLabel#titlebar-subtitle {
    font-size: 9px;
    font-weight: 600;
    color: #6b7280;
    letter-spacing: 0.14em;
}

QLabel#titlebar-version {
    font-size: 10px;
    font-weight: 600;
    color: #1e40af;
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 1px 6px;
}

QFrame#titlebar-divider {
    background-color: #e5e7eb;
    border: none;
}

QAbstractButton#titlebar-control {
    background: transparent;
    border: none;
    padding: 0;
}

/* ── Status Bars ── */
QStatusBar {
    background-color: #f3f4f6;
    color: #4b5563;
    border-top: 1px solid #d1d5db;
    font-size: 12px;
    padding: 2px 8px;
}

/* ── Dialogs & Tooltips ── */
QDialog, QMessageBox {
    background-color: #f3f4f6;
}

QWidget#dialog-action-bar {
    background-color: #ffffff;
    border-bottom: 1px solid #d1d5db;
    padding: 8px 16px;
}

QFrame#dialog-header {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 10px 14px;
}

QFrame#dialog-header-info {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 10px 14px;
}

QFrame#dialog-header-danger {
    background-color: #fef2f2;
    border: 1px solid #ef4444;
    border-radius: 4px;
    padding: 10px 14px;
}

QMenu {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: #eff6ff;
    color: #1d4ed8;
}

QMenu::item:disabled {
    color: #9ca3af;
}

QMenu::separator {
    height: 1px;
    background-color: #e5e7eb;
    margin: 4px 8px;
}

QToolTip {
    background-color: #111827;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ── Weather Widget Elements ── */
QFrame#weather-metric-card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 10px 12px;
}

QFrame#weather-hourly-card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 8px;
}

QFrame#weather-conditions-card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 12px;
}

/* ── Text Edit (Reports) ── */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    color: #111827;
    font-family: "JetBrains Mono", "SF Mono", "Consolas", monospace;
    font-size: 13px;
    padding: 8px;
}
"""

STYLESHEET = (
    _STYLESHEET_RAW.replace("__DOWN_ARROW_PATH__", _DOWN_ARROW)
    .replace("__DOWN_ARROW_DISABLED_PATH__", _DOWN_ARROW_DISABLED)
    .replace("__UP_ARROW_PATH__", _UP_ARROW)
    .replace("__UP_ARROW_ACTIVE_PATH__", _UP_ARROW_ACTIVE)
    .replace("__UP_ARROW_DISABLED_PATH__", _UP_ARROW_DISABLED)
    .replace("__CHECK_MARK_PATH__", _CHECK_MARK)
)
