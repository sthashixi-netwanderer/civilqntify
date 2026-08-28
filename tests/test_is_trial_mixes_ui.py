"""Tests for IS 10262:2019 Section 5.8 Trial Mixes UI and Dialog components."""

from __future__ import annotations

import os
import tempfile
import pytest

_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_trial_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

from concrete_mix import design_mix_simple
from app.widgets.is_trial_mixes_dialog import ISTrialMixesDialog
from app.widgets.result_panel import ResultPanel


qapp = None


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


def test_is10262_result_panel_shows_trial_mix_prompt(qt):
    """When IS 10262 result is displayed, _is_trial_frame is visible."""
    panel = ResultPanel()

    # Calculate IS 10262 mix
    is_res = design_mix_simple(
        code="is10262",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )
    panel.display_result(is_res)

    assert panel._is_trial_frame.isHidden() is False
    assert "IS 10262:2019 Clause 5.8" in panel._is_trial_lbl.text()
    assert "Trial 1" in panel._is_trial_lbl.text()
    assert "Trial 2" in panel._is_trial_lbl.text()
    assert "Trials 3 & 4" in panel._is_trial_lbl.text()


def test_aci_result_panel_hides_is_trial_mix_prompt(qt):
    """When ACI 211 result is displayed, _is_trial_frame is hidden."""
    panel = ResultPanel()

    aci_res = design_mix_simple(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )
    panel.display_result(aci_res)

    assert panel._is_trial_frame.isHidden() is True


def test_is_trial_mixes_dialog_initialization(qt):
    """ISTrialMixesDialog populates 4-trial table and checklist items."""
    is_res = design_mix_simple(
        code="is10262",
        target_strength_mpa=30.0,
        slump_mm=100.0,
        nmsa=20,
    )
    dlg = ISTrialMixesDialog(is_res)

    assert dlg._table.rowCount() == 4
    assert dlg._table.columnCount() == 8

    # Row 0: Trial 1
    assert "Trial 1" in dlg._table.item(0, 0).text()
    assert float(dlg._table.item(0, 1).text()) == is_res.w_c_ratio
    assert float(dlg._table.item(0, 2).text()) == is_res.water_kg
    assert float(dlg._table.item(0, 3).text()) == is_res.cement_kg

    # Row 2: Trial 3 (-10% W/C)
    assert "Trial 3" in dlg._table.item(2, 0).text()
    assert float(dlg._table.item(2, 1).text()) == pytest.approx(round(is_res.w_c_ratio * 0.90, 2))
    assert float(dlg._table.item(2, 3).text()) > is_res.cement_kg

    # Row 3: Trial 4 (+10% W/C)
    assert "Trial 4" in dlg._table.item(3, 0).text()
    assert float(dlg._table.item(3, 1).text()) == pytest.approx(round(is_res.w_c_ratio * 1.10, 2))
    assert float(dlg._table.item(3, 3).text()) < is_res.cement_kg
