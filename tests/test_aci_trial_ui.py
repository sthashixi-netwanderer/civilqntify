"""Tests for the ACI PRC-211.1-22 trial mixes dialog and panel wiring."""

from __future__ import annotations

import os
import tempfile

import pytest

_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_aci_trial_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

from concrete_mix import design_mix_simple
from app.widgets.aci_trial_mixes_dialog import ACITrialMixesDialog
from app.widgets.result_panel import ResultPanel
from history.db import HistoryDB


qapp = None


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


def _aci_design():
    return design_mix_simple(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )


def test_aci_result_panel_shows_trial_prompt(qt):
    """When an ACI result is displayed, the §5.3.9 trial frame is visible."""
    panel = ResultPanel()
    panel.display_result(_aci_design())

    assert panel._aci_trial_frame.isHidden() is False
    assert "ACI PRC-211.1-22" in panel._aci_trial_lbl.text()
    assert "5.3.9" in panel._aci_trial_lbl.text()


def test_aci_trial_frame_hidden_for_other_codes(qt):
    """IS and DOE results show their own prompts, not the ACI one."""
    panel = ResultPanel()

    is_res = design_mix_simple(
        code="is10262",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )
    panel.display_result(is_res)
    assert panel._aci_trial_frame.isHidden() is True
    assert panel._is_trial_frame.isHidden() is False

    doe_res = design_mix_simple(
        code="doe",
        target_strength_mpa=30.0,
        characteristic_strength_mpa=30.0,
        slump_mm=20.0,
        nmsa=20,
        fine_agg_pct_passing_600um=70.0,
    )
    panel.display_result(doe_res)
    assert panel._aci_trial_frame.isHidden() is True
    assert panel._doe_trial_frame.isHidden() is False


def test_dialog_populates_schedule(qt):
    """Default schedule = the designed mix; the series adds two rows."""
    res = _aci_design()
    dlg = ACITrialMixesDialog(res)
    assert dlg._table.rowCount() == 1
    assert dlg._table.columnCount() == 7
    assert "Designed mix" in dlg._table.item(0, 0).text()

    dlg._series_chk.setChecked(True)
    assert dlg._table.rowCount() == 3
    # Series mixtures keep the design water content.
    base_water = res.water_kg * dlg._volume_spin.value()
    for row in (1, 2):
        col_water = float(dlg._table.item(row, 2).text())
        assert col_water == pytest.approx(base_water, rel=0.02)


def test_dialog_evaluation_renders_adjustments(qt):
    """Entering measurements renders the §5.3.10 assessment."""
    dlg = ACITrialMixesDialog(_aci_design())
    dlg._volume_spin.setValue(0.05)
    dlg._density_spin.setValue(2350.0)
    dlg._slump_spin.setValue(50.0)
    dlg._on_calculate()

    assert not dlg._eval_result.isHidden()
    text = dlg._eval_result.text()
    assert "Free-water reversal" in text
    assert "relative yield" in text.lower()
    assert "Adjustment 1" in text
    assert "Next-trial proportions" in text
    # Without a strength result the next trial holds the design w/cm
    # (§5.3.10.4 / §9.2.9.3: cement = water ÷ w/cm).
    assert dlg._evaluation["next_trial"]["w_c_ratio"] == pytest.approx(
        _aci_design().w_c_ratio, abs=0.005
    )

    # With a low strength result, Adjustment 3 adds cementitious on top
    # of the Step-5 recalculation (documented app policy), tightening
    # the next-trial w/cm.
    dlg._strength_spin.setValue(20.0)
    dlg._on_calculate()
    a3 = dlg._evaluation["adjustment_3"]
    assert a3["delta_cement_kg_m3"] > 0
    assert dlg._evaluation["next_trial"]["w_c_ratio"] < _aci_design().w_c_ratio
    assert "Adjustment 3" in dlg._eval_result.text()


def test_save_trial_record_links_to_design(qt, monkeypatch):
    """Save writes an aci_trial record chained to the parent design."""
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    db = HistoryDB()  # lands in the temp HOME set above
    res = _aci_design()
    design_id = db.save_mix_design(
        getattr(res, "_input"), res, name="Parent ACI design",
    )

    dlg = ACITrialMixesDialog(res, design_calc_id=design_id)
    dlg._density_spin.setValue(2350.0)
    dlg._on_calculate()
    dlg._save_trial_record()

    recs = db.list_calculations(tab_type="aci_trial")
    assert len(recs) == 1
    rec = db.get_calculation(recs[0]["id"])
    assert rec["parent_id"] == design_id
