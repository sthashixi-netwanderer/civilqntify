"""Dialog body fill / overflow / resize-flexibility policy.

Pins the app-wide dialog layout contract: every ``FramelessDialog`` body
*fills* the window (a designated stretchable child absorbs spare height —
no dead gap between the last panel and the footer), never *overflows*
(dense or word-wrapped bodies live in ``widgetResizable`` scroll areas, so
a long failure report scrolls instead of forcing the window huge), and
stays *flexible* when the window shrinks (fixed heights on primary content
are minimums; the scroll areas take over below them).
"""

from __future__ import annotations

import os
import tempfile

# Isolate QSettings storage BEFORE any Qt/app import so tests never touch
# the developer's real CivilQntify settings.
_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_layout_flex_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

import pytest  # noqa: E402
from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QApplication, QScrollArea, QTableWidget  # noqa: E402

from app.styles import STYLESHEET  # noqa: E402
from app.widgets.aci_trial_mixes_dialog import ACITrialMixesDialog  # noqa: E402
from app.widgets.astm_c33_compliance_dialog import (  # noqa: E402
    ASTM_C33ComplianceDialog,
)
from app.widgets.doe_trial_mixes_dialog import DOETrialMixesDialog  # noqa: E402
from app.widgets.is_trial_mixes_dialog import ISTrialMixesDialog  # noqa: E402
from app.widgets.report_preview_dialog import ReportPreviewDialog  # noqa: E402
from concrete_mix import design_mix_simple  # noqa: E402
from concrete_mix.validation.base import FAIL, ClauseCheck  # noqa: E402


@pytest.fixture(scope="module")
def qt():
    app = QApplication.instance() or QApplication([])
    previous = app.styleSheet()
    app.setStyleSheet(STYLESHEET)
    yield app
    app.setStyleSheet(previous)


def _is_design():
    return design_mix_simple(
        code="is10262",
        target_strength_mpa=30.0,
        slump_mm=100.0,
        nmsa=20,
    )


def _aci_design():
    return design_mix_simple(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )


def _doe_design():
    return design_mix_simple(
        code="doe",
        target_strength_mpa=30.0,
        characteristic_strength_mpa=30.0,
        slump_mm=20.0,
        nmsa=20,
        fine_agg_pct_passing_600um=70.0,
        fine_agg_absorption=2.0,
        coarse_agg_absorption=1.0,
        defective_percent=2.5,
        std_deviation=8.0,
    )


def _settle(app) -> None:
    """Run the layout to a stable state after a resize."""
    for _ in range(3):
        app.processEvents()


def _dialog_height_grows_into_table(app, dlg, table, grow_height: int) -> None:
    """Enlarge the window and require the body table to absorb the space.

    The grow height must clear the scroll content's own minimum (while the
    body is scrolling there is no spare height to distribute); past that
    point the stretchable child must take every extra pixel.
    """
    dlg.resize(880, 680)
    _settle(app)
    base = table.height()
    assert base > 0

    dlg.resize(880, grow_height)
    _settle(app)
    try:
        assert table.height() > base + 100, (
            f"table did not fill the enlarged window: {base} → {table.height()}"
        )
    finally:
        dlg.resize(880, 680)
        _settle(app)


# ── Trial workbooks: table fills, dialog scrolls when shrunk ────────────


@pytest.mark.parametrize(
    "dialog_cls, design",
    [
        (ISTrialMixesDialog, _is_design),
        (ACITrialMixesDialog, _aci_design),
        (DOETrialMixesDialog, _doe_design),
    ],
    ids=["is", "aci", "doe"],
)
def test_trial_dialog_table_fills_enlarged_window(qt, dialog_cls, design):
    dlg = dialog_cls(design())
    try:
        dlg.show()
        _dialog_height_grows_into_table(qt, dlg, dlg._table, grow_height=1500)
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


def test_is_trial_dialog_shrinks_with_scrollbars(qt):
    """Below the content's minimum the outer scroll area takes over —
    the window still obeys the requested size and the body scrolls
    instead of clipping."""
    dlg = ISTrialMixesDialog(_is_design())
    try:
        dlg.show()
        dlg.resize(700, 520)  # the dialog's declared minimum size
        _settle(qt)
        assert dlg.height() == 520
        scroll = dlg.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.verticalScrollBar().maximum() > 0, (
            "body content exceeds the viewport but no scrollbar range exists"
        )
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


# ── ASTM C33 / IS 383 compliance: bounded minimum, table fills ──────────


def _failing_checks(count: int) -> list[ClauseCheck]:
    return [
        ClauseCheck(
            clause=f"6.1.{i}",
            title=f"Requirement {i}",
            status=FAIL,
            requirement="x" * 90,
            measured="measured value",
            detail="y" * 70,
        )
        for i in range(count)
    ]


def test_compliance_dialog_shrinks_despite_many_failures(qt):
    """Regression: the wrapped failure-details block once reported its full
    text height as the layout minimum, so a 30-failure report could not be
    resized below its own height. Inside a scroll area the window must
    obey the requested size."""
    dlg = ASTM_C33ComplianceDialog(_failing_checks(30), "fine")
    try:
        dlg.show()
        dlg.resize(680, 420)  # the dialog's declared minimum size
        _settle(qt)
        assert dlg.height() == 420
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


def test_compliance_dialog_table_fills_enlarged_window(qt):
    # A handful of failures keeps the scroll content's minimum below the
    # enlarged viewport, so the spare height is genuinely distributable
    # (the 30-failure shrinkability case is covered separately).
    dlg = ASTM_C33ComplianceDialog(_failing_checks(3), "fine")
    try:
        dlg.show()
        table = dlg.findChild(QTableWidget)
        assert table is not None
        _dialog_height_grows_into_table(qt, dlg, table, grow_height=1200)
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


# ── Report preview: flexible minimum, browser fills ─────────────────────


def test_report_preview_minimum_allows_shrinking(qt):
    """The browser reflows and scrolls internally, so the old 900×700
    minimum was an artificial floor on small screens."""
    from PyQt6.QtCore import QSize

    dlg = ReportPreviewDialog()
    try:
        assert dlg.minimumSize() == QSize(600, 420)
        dlg.set_html("<p>" + "lorem ipsum " * 400 + "</p>")
        dlg.show()
        dlg.resize(600, 420)
        _settle(qt)
        assert dlg.height() == 420

        base = dlg._browser.height()
        dlg.resize(600, 900)
        _settle(qt)
        assert dlg._browser.height() > base + 100
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


# ── History detail: steps table fills (mix-design records) ──────────────


def test_history_detail_steps_table_fills_enlarged_window(qt):
    import json

    from app.widgets.history_detail_dialog import HistoryDetailDialog

    record = {
        "id": 7,
        "tab_type": "mix_design",
        "name": "M30 pump mix",
        "created_at": "2026-01-01T10:00:00",
        "input_json": "{}",
        "result_json": json.dumps(
            {
                "cement_kg": 380.0,
                "steps": [
                    {
                        "step_number": i,
                        "description": f"Step {i}",
                        "formula_latex": "W = C \\times 0.5",
                        "result": "190.0",
                        "unit": "kg/m\u00b3",
                        "clause_ref": "Cl. 5.3",
                    }
                    for i in range(1, 9)
                ],
            }
        ),
    }
    dlg = HistoryDetailDialog(record)
    try:
        dlg.show()
        table = dlg.findChild(QTableWidget)
        assert table is not None
        _dialog_height_grows_into_table(qt, dlg, table, grow_height=1500)
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)


# ── Settings: footer pinned, no dead space under the buttons ────────────


def test_settings_buttons_pinned_to_bottom(qt):
    import app.unit_preferences as up_mod

    prefs = up_mod.get_unit_prefs()
    from app.widgets.settings_dialog import SettingsDialog

    dlg = SettingsDialog(prefs)
    try:
        dlg.show()
        dlg.resize(440, 900)
        _settle(qt)
        btn = dlg._btn_apply
        bottom = btn.mapTo(dlg, QPoint(0, btn.height())).y()
        assert bottom >= 900 - 40, (
            f"Apply button floats at y={bottom} instead of the bottom edge"
        )
    finally:
        dlg.close()
        dlg.deleteLater()
        _settle(qt)
