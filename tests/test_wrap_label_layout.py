"""Regression tests: wrapped labels must never clip at any width or font.

Root cause (v1.0.12 GUI fix): ``QLabel.heightForWidth()`` reports the wrapped
*text* height only; labels styled with a QSS box (``callout-*``, ``*-banner``,
``section-title``, ``info-overlay-label`` in ``app/styles.py``) were laid out
rows short by exactly the box height, clipping the last wrapped line. A
second defect let read-only value fields (water content, applied std-dev) be
squeezed to ~41 px beside their info-button labels, and dynamic retxt inside
a ``QScrollArea`` left rows solved inside the stale content height.

The sweep below builds the real ``ConcreteMixTab`` per standard (IS 10262,
ACI 211.1, BRE 331) at narrow sidebar widths and enlarged fonts — including
the dynamic-retext ordering (long water text applied *after* the layout has
settled, the exact path in the field screenshot) — and asserts every visible
word-wrapped label is at least as tall as its text requires.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_wrap_label_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

from PyQt6.QtWidgets import QApplication, QLabel, QSplitter

from app.styles import STYLESHEET
from app.widgets.concrete_tab import ConcreteMixTab


qapp = None


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        qapp = QApplication.instance() or QApplication([])
    yield qapp


def _required_height(label: QLabel) -> int:
    """Ground-truth height the label's text needs at its current width.

    Calls ``QLabel.heightForWidth`` explicitly so the measurement stays
    valid for subclasses (``WrapLabel``) that override it.
    """
    box = label.contentsMargins()  # QSS padding + border; 0 for plain labels
    inner = max(1, label.width() - box.left() - box.right())
    return QLabel.heightForWidth(label, inner) + box.top() + box.bottom()


def _assert_no_clipped_labels(tab) -> None:
    problems = []
    for label in tab.findChildren(QLabel):
        if not label.isVisible() or not label.wordWrap():
            continue
        need = _required_height(label)
        if need > label.height() + 1:
            problems.append(
                f"{label.objectName() or 'plain'}: h={label.height()} "
                f"need={need} w={label.width()} text={label.text()[:60]!r}"
            )
    assert not problems, "clipped word-wrapped labels:\n" + "\n".join(problems)


def _build_tab(qt, code: str, sidebar_w: int, font_pt: int) -> tuple[ConcreteMixTab, QWidget]:
    """Build the real tab; the host widget must be kept referenced for the
    tab's C++ object to stay alive, hence the tuple return."""
    font = qt.font()
    font.setPointSize(font_pt)
    qt.setFont(font)

    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    host = QWidget()
    host.setStyleSheet(STYLESHEET)
    tab = ConcreteMixTab()
    (host.layout() or QVBoxLayout(host)).addWidget(tab)
    index = tab.code_combo.findData(code)
    assert index >= 0, f"standard {code} missing from the form"
    tab.code_combo.setCurrentIndex(index)
    tab._left_tabs.setCurrentIndex(tab._mixdesign_idx)
    host.resize(sidebar_w + 820, 900)
    host.show()
    qt.processEvents()
    tab.findChildren(QSplitter)[0].setSizes([sidebar_w, 820])
    qt.processEvents()
    qt.processEvents()
    return tab, host


def _set_mixed_aggregate_types(tab) -> None:
    """Trigger the long '2/3 Wf + 1/3 Wc' Table 3 note (DOE water row)."""
    ca = tab.ca_type_combo.findData("crushed")
    fa = tab.fa_type_combo.findData("uncrushed")
    if ca >= 0 and fa >= 0:
        tab.ca_type_combo.setCurrentIndex(ca)
        tab.fa_type_combo.setCurrentIndex(fa)


@pytest.mark.parametrize("code", ["is10262", "aci211", "doe"])
@pytest.mark.parametrize("sidebar_w", [460, 340])
def test_no_clipped_labels_static_layout(qt, code, sidebar_w):
    """Every wrapped label fits at default values, any sidebar width."""
    tab, host = _build_tab(qt, code, sidebar_w, font_pt=13)
    try:
        _assert_no_clipped_labels(tab)
    finally:
        host.deleteLater()


@pytest.mark.parametrize("code", ["is10262", "aci211", "doe"])
def test_no_clipped_labels_after_dynamic_retext(qt, code):
    """Retext after the layout settled must grow the rows, not clip them.

    This is the field-reported path: the water-content note was set while
    the window was already laid out at its final (narrow) width.
    """
    tab, host = _build_tab(qt, code, sidebar_w=440, font_pt=13)
    try:
        _set_mixed_aggregate_types(tab)
        qt.processEvents()
        qt.processEvents()
        _assert_no_clipped_labels(tab)
    finally:
        host.deleteLater()


@pytest.mark.parametrize("code", ["is10262", "aci211", "doe"])
def test_no_clipped_labels_large_font(qt, code):
    """Large text (15 pt) must reflow the padded notes, not clip a line."""
    tab, host = _build_tab(qt, code, sidebar_w=440, font_pt=15)
    try:
        _set_mixed_aggregate_types(tab)
        qt.processEvents()
        qt.processEvents()
        _assert_no_clipped_labels(tab)
    finally:
        host.deleteLater()


def test_value_fields_keep_readable_width(qt):
    """Read-only value rows must not be starved next to info-button labels.

    Pre-fix the reduced-water field received a 41 px column at narrow
    sidebars; the 140 px floor plus WrapLongRows stacking prevents that.
    """
    tab, host = _build_tab(qt, "doe", sidebar_w=380, font_pt=13)
    try:
        assert tab.water_content_label.width() >= 100
        assert tab.reduced_water_label.width() >= 100
    finally:
        host.deleteLater()
