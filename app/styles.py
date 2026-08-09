"""Centralized QSS stylesheet for CivilQntify.

Design tokens from Stitch "Civil Engineering Precision" design system.
Style: Corporate/Modern with Industrial lean. Precision-first.
Font: Inter. Radius: 4px. Depth via outlines, not shadows.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

def _get_resource_path(name: str) -> str:
    path = os.path.join(_HERE, "resources", name)
    return path.replace("\\", "/")

_DOWN_ARROW = _get_resource_path("down_arrow.svg")
_DOWN_ARROW_DISABLED = _get_resource_path("down_arrow_disabled.svg")
_UP_ARROW = _get_resource_path("up_arrow.svg")
_UP_ARROW_ACTIVE = _get_resource_path("up_arrow_active.svg")
_UP_ARROW_DISABLED = _get_resource_path("up_arrow_disabled.svg")

_STYLESHEET_RAW = """
/* ── Colors Reference (from Stitch design system) ──
    Background:     #f8fafc
    Surface:        #ffffff  border: #e2e8f0
    Primary:        #1e40af
    Focus/Accent:   #3b82f6
    On-Surface:     #0b1c30
    On-Surface-Var: #444653
    Outline:        #757684
    Outline-Var:    #c4c5d5
    Table Header:   #f1f5f9
    Error:          #ef4444
    Warning:        #f59e0b / #fef3c7
    Success:        #10b981
    Disabled:       #94a3b8
    Hover surface:  #eff4ff
    Font:           Inter
    Mono:           JetBrains Mono
    Radius:         4px
── */

/* ── Global ── */
QMainWindow, QWidget {
    background-color: #f8fafc;
    color: #0b1c30;
    font-family: "Inter", "Geist", "Satoshi", "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}
/* QSS uses JetBrains Mono for numeric values where tabular alignment is needed */

/* ── Tab Widget ── */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    background: #ffffff;
    border-radius: 4px;
    top: -1px;
}

QTabBar::tab {
    background: #f8fafc;
    color: #757684;
    padding: 10px 24px;
    margin-right: 1px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1e40af;
    border-bottom: 2px solid #1e40af;
}

QTabBar::tab:hover:!selected {
    background: #eff4ff;
    color: #0b1c30;
}

/* ── Labels ── */
QLabel {
    color: #0b1c30;
    font-size: 13px;
}

QLabel#section-title {
    color: #1e40af;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding: 6px 0 2px 0;
}

QLabel#warning-banner {
    background-color: #fef3c7;
    color: #92400e;
    border: 1px solid #f59e0b;
    border-radius: 4px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 13px;
}

QLabel#result-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 14px;
    color: #0b1c30;
    font-size: 13px;
}

QLabel#result-value {
    color: #1e40af;
    font-size: 22px;
    font-weight: 700;
}

QLabel#result-unit {
    color: #757684;
    font-size: 11px;
}

QLabel#result-label {
    color: #757684;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 8px 12px;
    color: #0b1c30;
    font-size: 13px;
    min-height: 20px;
    selection-background-color: #1e40af;
    selection-color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #1e40af;
}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border: 1px solid #94a3b8;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

QLineEdit[readOnly="true"], QSpinBox[readOnly="true"], QDoubleSpinBox[readOnly="true"] {
    background-color: #f8fafc;
    color: #444653;
}

/* ── Combo Box ── */
QComboBox::drop-down {
    border: none;
    width: 28px;
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
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    color: #0b1c30;
    selection-background-color: #1e40af;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 7px 12px;
    border-radius: 4px;
    color: #0b1c30;
    min-height: 18px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #1e40af;
    color: #ffffff;
}
QComboBox QAbstractItemView::item:hover:!selected {
    background-color: #eff4ff;
    color: #0b1c30;
}

/* ── Checkbox ── */
QCheckBox {
    color: #0b1c30;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #c4c5d5;
    background: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #3b82f6;
}

QCheckBox::indicator:checked {
    background: #1e40af;
    border-color: #1e40af;
}

/* ── Buttons ── */
QPushButton {
    background-color: #1e40af;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 10px 24px;
    font-weight: 700;
    font-size: 13px;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #00288e;
}

QPushButton:disabled {
    background-color: #e2e8f0;
    color: #94a3b8;
}

QPushButton#secondary {
    background-color: #ffffff;
    color: #0b1c30;
    border: 1px solid #cbd5e1;
    font-weight: 600;
}

QPushButton#secondary:hover {
    background-color: #eff4ff;
    border-color: #3b82f6;
    color: #1e40af;
}

QPushButton#danger-btn {
    background-color: #ffffff;
    color: #dc2626;
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
}

/* ── Group Boxes ── */
QGroupBox {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    margin-top: 16px;
    padding-top: 20px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #1e40af;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 8px;
}

/* ── Scroll Areas ── */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #f8fafc;
    width: 10px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #c4c5d5;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #757684;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #f8fafc;
    height: 10px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #c4c5d5;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #757684;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Tree & Table Widgets (Calculation Steps, Results) ── */
QTreeWidget, QTreeView, QTableWidget, QTableView {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    color: #0b1c30;
    font-size: 13px;
}

QTreeWidget::item, QTreeView::item, QTableWidget::item, QTableView::item {
    padding: 6px;
    border-bottom: 1px solid #f1f5f9;
}

QTreeWidget::item:selected, QTreeView::item:selected, QTableWidget::item:selected, QTableView::item:selected {
    background-color: #eff4ff;
    color: #1e40af;
}

QTreeWidget::item:hover, QTreeView::item:hover, QTableWidget::item:hover, QTableView::item:hover {
    background-color: #f8fafc;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #444653;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

/* ── Splitter ── */
QSplitter::handle {
    background: #e2e8f0;
    width: 6px;
    margin: 0 1px;
}
QSplitter::handle:hover {
    background: #1e40af;
}
QSplitter::handle:pressed {
    background: #1e3a8a;
}

/* ── Text Edit (Report) ── */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    color: #0b1c30;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 13px;
    padding: 12px;
}

/* ── Status Bar ── */
QStatusBar {
    background-color: #f8fafc;
    color: #757684;
    border-top: 1px solid #e2e8f0;
    font-size: 12px;
    padding: 2px 8px;
}

/* ── Spin Box Arrows ── */
QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #e2e8f0;
    border-bottom: 1px solid #f1f5f9;
    border-top-right-radius: 4px;
    background: #f8fafc;
}

QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #e2e8f0;
    border-top: 1px solid #f1f5f9;
    border-bottom-right-radius: 4px;
    background: #f8fafc;
}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: url(__UP_ARROW_PATH__);
    width: 10px;
    height: 6px;
}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: url(__DOWN_ARROW_PATH__);
    width: 10px;
    height: 6px;
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background: #eff4ff;
}

QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled {
    image: url(__UP_ARROW_DISABLED_PATH__);
}

QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {
    image: url(__DOWN_ARROW_DISABLED_PATH__);
}

/* ── Info Button ── */
QPushButton#info-btn {
    background-color: #e2e8f0;
    color: #444653;
    border: 1px solid #c4c5d5;
    border-radius: 9px;
    padding: 0px;
    font-size: 10px;
    font-weight: 700;
    font-style: italic;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
}

QPushButton#info-btn:hover {
    background-color: #1e40af;
    color: #ffffff;
    border-color: #1e40af;
}

QPushButton#info-btn:pressed {
    background-color: #00288e;
    color: #ffffff;
}

/* ── Tooltip ── */
QToolTip {
    background-color: #0b1c30;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ── Dialog ── */
QDialog {
    background-color: #f8fafc;
}

QMessageBox {
    background-color: #f8fafc;
}

QMessageBox QLabel {
    color: #0b1c30;
}

/* ── Toolbar ── */
QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    spacing: 8px;
    padding: 6px 12px;
}

QToolBar QLabel {
    font-size: 16px;
    font-weight: 700;
    color: #1e40af;
    padding: 0 8px;
}

QPushButton#settings-btn {
    border: none;
    border-radius: 4px;
    padding: 6px;
    background: transparent;
    icon-size: 22px;
}

QPushButton#settings-btn:hover {
    background-color: #eff4ff;
}

QPushButton#settings-btn:pressed {
    background-color: #dbeafe;
}
"""

STYLESHEET = (_STYLESHEET_RAW
    .replace("__DOWN_ARROW_PATH__", _DOWN_ARROW)
    .replace("__DOWN_ARROW_DISABLED_PATH__", _DOWN_ARROW_DISABLED)
    .replace("__UP_ARROW_PATH__", _UP_ARROW)
    .replace("__UP_ARROW_ACTIVE_PATH__", _UP_ARROW_ACTIVE)
    .replace("__UP_ARROW_DISABLED_PATH__", _UP_ARROW_DISABLED)
)
