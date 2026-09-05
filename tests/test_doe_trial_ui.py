"""Tests for the DOE (BRE 331:1997 §6) trial mixes dialog and panel wiring."""

from __future__ import annotations

import os
import tempfile

import pytest

_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_doe_trial_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

from concrete_mix import design_mix_simple
from app.widgets.doe_trial_mixes_dialog import DOETrialMixesDialog
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


def _doe_design():
    """§7.1 chain: target 46, w/c 0.47, water 160, cement 340 kg/m³."""
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


def test_doe_result_panel_shows_trial_prompt(qt):
    """When a DOE result is displayed, the §6 trial frame is visible."""
    panel = ResultPanel()
    panel.display_result(_doe_design())

    assert panel._doe_trial_frame.isHidden() is False
    assert "BRE 331:1997 §6" in panel._doe_trial_lbl.text()
    assert "Figure 7" in panel._doe_trial_lbl.text()


def test_doe_trial_frame_hidden_for_other_codes(qt):
    """ACI and IS results show their own prompts, not the DOE one."""
    panel = ResultPanel()

    aci_res = design_mix_simple(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )
    panel.display_result(aci_res)
    assert panel._doe_trial_frame.isHidden() is True

    is_res = design_mix_simple(
        code="is10262",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
    )
    panel.display_result(is_res)
    assert panel._doe_trial_frame.isHidden() is True
    assert panel._is_trial_frame.isHidden() is False

    panel.display_result(_doe_design())
    assert panel._doe_trial_frame.isHidden() is False
    assert panel._is_trial_frame.isHidden() is True


def test_dialog_populates_schedule(qt):
    """Default schedule = the designed mix; variants add two rows."""
    res = _doe_design()
    dlg = DOETrialMixesDialog(res)
    assert dlg._table.rowCount() == 1
    assert dlg._table.columnCount() == 7
    assert "Designed mix" in dlg._table.item(0, 0).text()
    assert float(dlg._table.item(0, 1).text()) == pytest.approx(res.w_c_ratio)
    # 0.05 m³ of the §7.1-chain design: cement 340 → 17.0 kg, water 8.0 kg.
    assert float(dlg._table.item(0, 2).text()) == pytest.approx(17.0, abs=0.05)
    assert float(dlg._table.item(0, 3).text()) == pytest.approx(8.0, abs=0.05)

    dlg._variants_chk.setChecked(True)
    assert dlg._table.rowCount() == 3
    # Variants share the design water content.
    for row in (1, 2):
        assert float(dlg._table.item(row, 3).text()) == pytest.approx(8.0, abs=0.05)


def test_dialog_dry_condition_adjusts_water(qt):
    """Oven-dry batching: dry aggregate masses replace SSD ones and the
    absorption water is added to the mixer water (§6.1)."""
    res = _doe_design()  # fine A=2%, coarse A=1%
    dlg = DOETrialMixesDialog(res)
    dlg._moisture_combo.setCurrentIndex(1)  # oven-dry
    # §7.1 chain at 0.05 m³: FA 27.2 / CA 71.5 SSD → dry 26.7 / 70.8,
    # absorption water 1.2 kg → added water 9.2 kg.
    assert float(dlg._table.item(0, 3).text()) == pytest.approx(9.2, abs=0.05)
    note = dlg._schedule_note.text().lower()
    assert "soak" in note


def test_dialog_evaluation_renders_feedback(qt):
    """Entering measurements renders the §6.3 assessment."""
    dlg = DOETrialMixesDialog(_doe_design())
    dlg._density_spin.setValue(2385.0)
    dlg._strength_spin.setValue(50.0)
    dlg._slump_spin.setValue(20.0)
    dlg._on_calculate()

    assert not dlg._eval_result.isHidden()
    text = dlg._eval_result.text()
    assert "§6.3.1" in text and "§6.3.2" in text and "Figure 7" in text
    assert "Verdict" in dlg._evaluation or dlg._evaluation["verdict"]["decision"] in ("minor", "re_trial")


def test_save_trial_record_links_to_design(qt, monkeypatch):
    """Save writes a doe_trial record chained to the parent design."""
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    db = HistoryDB()  # lands in the temp HOME set above
    res = _doe_design()
    design_id = db.save_mix_design(
        getattr(res, "_input"), res, name="Parent design",
    )

    dlg = DOETrialMixesDialog(res, design_calc_id=design_id)
    dlg._strength_spin.setValue(50.0)
    dlg._on_calculate()
    dlg._save_trial_record()

    recs = db.list_calculations(tab_type="doe_trial")
    assert len(recs) == 1
    rec = db.get_calculation(recs[0]["id"])
    assert rec["parent_id"] == design_id
