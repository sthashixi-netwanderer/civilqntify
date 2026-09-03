"""History save/load round-trip tests.

Loading a record from the History tab must refill the tab the record was
generated from with the same entries, so the user can re-run or adjust the
calculation — for every record type (Mix Design, Quantification, Cost
Estimation, PSD).
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_hist_test_")
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["HOME"] = _TMP

_qapp = None


@pytest.fixture()
def qt():
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication

        _qapp = QApplication.instance() or QApplication([])
    yield _qapp


@pytest.fixture()
def db(tmp_path):
    from history.db import HistoryDB

    return HistoryDB(tmp_path / "history.db")


def _mix_result(**overrides):
    """Run a real mix design so the saved input/result match the engine."""
    from concrete_mix import design_mix_simple

    kwargs = dict(
        code="is10262",
        target_strength_mpa=30.0,
        slump_mm=100.0,
        nmsa=20,
        exposure_class="moderate",
        scm_replacement_percent=20.0,
        admixture_type="superplasticizer",
        admixture_dosage=1.0,
        admixture_water_reduction=18.0,
        volume_m3=2.0,
    )
    kwargs.update(overrides)
    return design_mix_simple(**kwargs)


# ---------------------------------------------------------------------------
# PSD history
# ---------------------------------------------------------------------------


def test_psd_history_round_trip_restores_entries(qt, db, monkeypatch):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab._history_db = db
    # The compliance dialog is modal; loading must recompute checks
    # without opening it.
    monkeypatch.setattr(tab, "_show_astm_compliance_dialog", lambda checks: None)

    masses = [0, 5, 45, 210, 60, 70, 105]  # IS 383 fine stack, 7 sieves
    for i, m in enumerate(masses):
        tab.table.item(i, 1).setText(str(m))
    tab.table.item(len(masses), 1).setText("5")
    tab._on_compute_plot()

    recs = db.list_calculations(tab_type="psd")
    assert len(recs) == 1
    calc_id = recs[0]["id"]

    # Dirty the form: another standard, aggregate type and band
    tab.standard_combo.setCurrentIndex(1)  # ASTM C33
    assert tab.standard_combo.currentData() == "astm_c33"

    tab.load_from_history(calc_id)

    assert tab.standard_combo.currentData() == "is383"
    assert tab.agg_combo.currentData() == "fine"
    assert tab.band_combo.currentData() == ("is383", "fine", "II")
    sieves = tab._current_sieves()
    restored = [float(tab.table.item(i, 1).text()) for i in range(len(sieves))]
    assert restored == [float(m) for m in masses]
    assert float(tab.table.item(len(sieves), 1).text()) == 5.0
    assert tab._last_result is not None
    assert tab._result_panel._last_result is not None


def test_psd_history_restores_astm_quality_inputs(qt, db, monkeypatch):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab._history_db = db
    # The compliance dialog is modal; loading must recompute checks
    # without opening it.
    monkeypatch.setattr(tab, "_show_astm_compliance_dialog", lambda checks: None)

    tab.standard_combo.setCurrentIndex(1)  # ASTM C33, fine
    sieves = tab._current_sieves()
    masses = [0.0] * len(sieves)
    masses[2] = 120.0
    masses[3] = 180.0
    masses[4] = 200.0
    masses[5] = 150.0
    masses[6] = 100.0
    for i, m in enumerate(masses):
        tab.table.item(i, 1).setText(str(m))
    tab.table.item(len(sieves), 1).setText("50")

    tab.fine_clay_spin.setValue(2.0)
    idx = tab.fine_organic_combo.findData("darker_c87")
    tab.fine_organic_combo.setCurrentIndex(idx)
    tab.fine_c87_spin.setValue(97.0)
    tab._on_compute_plot()

    recs = db.list_calculations(tab_type="psd")
    assert len(recs) == 1
    calc_id = recs[0]["id"]

    tab.fine_clay_spin.setValue(-1.0)  # back to "not tested"
    tab.fine_c87_spin.setValue(95.0)
    tab.load_from_history(calc_id)

    assert tab.standard_combo.currentData() == "astm_c33"
    assert tab.fine_clay_spin.value() == pytest.approx(2.0)
    assert tab.fine_organic_combo.currentData() == "darker_c87"
    assert tab.fine_c87_spin.value() == pytest.approx(97.0)
    # checks were recomputed for the loaded analysis without a dialog
    assert tab._astm_checks


# ---------------------------------------------------------------------------
# Mix design history
# ---------------------------------------------------------------------------


def test_mix_design_history_load_restores_is_form(qt, db):
    from app.widgets.concrete_tab import ConcreteMixTab

    result = _mix_result()
    calc_id = db.save_mix_design(result._input, result, name="IS mix")

    tab = ConcreteMixTab()
    tab._history_db = db
    tab.load_from_history(calc_id)

    assert tab.code_combo.currentData() == "is10262"
    assert tab.strength_spin.value() == pytest.approx(30.0)
    assert tab.slump_spin.value() == pytest.approx(100.0)
    assert tab.nmsa_combo.currentData() == 20
    assert tab.cement_type_combo.currentData() == "GRADE_42_5R"
    assert tab.exposure_combo.currentData() == "moderate"
    assert tab.grading_combo.currentData() == "II"
    assert tab.scm_type_combo.currentData() == "fly_ash"
    assert tab.scm_pct_spin.value() == pytest.approx(20.0)
    assert tab.admix_type_combo.currentData() == "superplasticizer"
    assert tab.admix_spin.value() == pytest.approx(18.0)
    assert tab.volume_spin.value() == pytest.approx(2.0)
    assert tab._last_result is not None
    assert tab._left_tabs.currentIndex() == tab._mixdesign_idx


def test_mix_design_history_load_restores_doe_form(qt, db):
    from app.widgets.concrete_tab import ConcreteMixTab

    result = _mix_result(
        code="doe",
        exposure_class=None,
        scm_replacement_percent=0.0,
        admixture_type="",
        num_test_cubes=25,
        min_cement_kg=350.0,
        fine_agg_pct_passing_600um=55.0,
    )
    calc_id = db.save_mix_design(result._input, result, name="DOE mix")

    tab = ConcreteMixTab()
    tab._history_db = db
    tab.load_from_history(calc_id)

    assert tab.code_combo.currentData() == "doe"
    assert tab.n_cubes_spin.value() == 25
    assert tab.min_cement_spin.value() == pytest.approx(350.0)
    assert tab.pct_passing_600um_spin.value() == pytest.approx(55.0)
    assert tab.scm_type_combo.currentIndex() == 0  # None
    assert tab.scm_pct_spin.value() == pytest.approx(0.0)


def test_mix_design_loaded_form_recalculates_same_cement(qt, db):
    """The restored entries must reproduce the saved result on Calculate."""
    from app.widgets.concrete_tab import ConcreteMixTab

    result = _mix_result()
    calc_id = db.save_mix_design(result._input, result, name="IS mix")

    tab = ConcreteMixTab()
    tab._history_db = db
    tab.load_from_history(calc_id)

    kwargs = tab._build_kwargs()
    assert kwargs["code"] == "is10262"
    assert kwargs["scm_replacement_percent"] == pytest.approx(20.0)
    assert kwargs["admixture_water_reduction"] == pytest.approx(18.0)


# ---------------------------------------------------------------------------
# Quantification history
# ---------------------------------------------------------------------------


def test_quantification_ratio_history_round_trip(qt, db):
    from app.widgets.material_quantify_tab import MaterialQuantifyTab
    from material_quantify.engine.ratio_quantifier import MixRatioQuantifier

    tab = MaterialQuantifyTab()
    tab._history_db = db

    tab._left_tabs.setCurrentIndex(1)  # Mix Ratio subtab
    tab.ratio_cement_spin.setValue(1.0)
    tab.ratio_sand_spin.setValue(2.0)
    tab.ratio_gravel_spin.setValue(4.0)
    tab.ratio_volume_spin.setValue(7.5)
    tab.ratio_wastage_spin.setValue(8.0)

    bill = MixRatioQuantifier(
        cement_ratio=1.0, sand_ratio=2.0, gravel_ratio=4.0,
    ).quantify_by_volume(7.5, wastage_percent=8.0)
    tab._last_bill = bill
    tab._auto_save_history(bill)

    recs = db.list_calculations(tab_type="quantification")
    assert len(recs) == 1
    calc_id = recs[0]["id"]

    # Dirty the ratio entries, then load the record back
    tab.ratio_cement_spin.setValue(1.0)
    tab.ratio_sand_spin.setValue(1.5)
    tab.ratio_gravel_spin.setValue(3.0)
    tab.ratio_wastage_spin.setValue(5.0)

    tab.load_from_history(calc_id)

    assert tab._left_tabs.currentIndex() == 1
    assert tab.ratio_sand_spin.value() == pytest.approx(2.0)
    assert tab.ratio_gravel_spin.value() == pytest.approx(4.0)
    assert tab.ratio_volume_spin.value() == pytest.approx(7.5)
    assert tab.ratio_wastage_spin.value() == pytest.approx(8.0)


def test_quantification_design_elements_history_round_trip(qt, db):
    from app.widgets.material_quantify_tab import MaterialQuantifyTab
    from material_quantify.engine.ratio_quantifier import MixRatioQuantifier

    tab = MaterialQuantifyTab()
    tab._history_db = db

    tab.mode_combo.setCurrentIndex(
        tab.mode_combo.findData("elements")
    )
    tab._add_element()
    row = tab._elem_table.rowCount() - 1
    tab._elem_table.cellWidget(row, 1).setValue(6.0)  # length
    tab._elem_table.cellWidget(row, 2).setValue(0.3)  # width
    tab._elem_table.cellWidget(row, 3).setValue(0.4)  # depth
    tab._elem_table.cellWidget(row, 4).setValue(10)   # qty

    # A ratio-produced bill exercises the same save/load plumbing; the
    # design-mix UI state (mode + element rows) is what must come back.
    bill = MixRatioQuantifier().quantify_by_volume(7.2, wastage_percent=5.0)
    from dataclasses import asdict

    extra = {
        "design_ui": {
            "mode": "elements",
            "elements": [asdict(e) for e in tab._get_elements()],
        }
    }
    tab._last_bill = bill
    tab._history_db.save_quantification(
        bill.transfer_data, bill, name="elements", extra_input=extra
    )
    calc_id = db.list_calculations(tab_type="quantification")[0]["id"]

    tab._elem_table.selectRow(0)
    tab._remove_element()
    assert tab._elem_table.rowCount() == 0
    tab.load_from_history(calc_id)

    assert tab.mode_combo.currentData() == "elements"
    assert tab._elem_table.rowCount() == 1
    assert tab._elem_table.cellWidget(0, 1).value() == pytest.approx(6.0)
    assert tab._elem_table.cellWidget(0, 4).value() == 10


# ---------------------------------------------------------------------------
# Cost estimation history
# ---------------------------------------------------------------------------


def test_cost_history_restores_options_and_project(qt, db):
    from app.widgets.cost_estimation_tab import CostEstimationTab

    tab = CostEstimationTab()
    tab._history_db = db

    tab._proj_name.setText("Ridge Residence")
    tab._addl_spins["labour_count"].setValue(12)
    tab._addl_spins["contingency_pct"].setValue(7.5)

    cost_data = {
        "material_cost_per_m3": 1200.0,
        "total_material_cost": 6000.0,
        "total_project_cost": 9000.0,
        "cost_per_bag": 90.0,
        "material_breakdown": [],
        "summary_rows": [],
        "project_info": {
            "name": "Ridge Residence",
            "location": "Accra",
            "client": "CRC",
            "date": "2026-01-15",
        },
    }
    tab._auto_save_history(cost_data)
    calc_id = db.list_calculations(tab_type="cost_estimation")[0]["id"]

    tab._proj_name.setText("")
    tab._addl_spins["labour_count"].setValue(3)
    tab.load_from_history(calc_id)

    assert tab._proj_name.text() == "Ridge Residence"
    assert tab._proj_location.text() == "Accra"
    assert tab._addl_spins["labour_count"].value() == pytest.approx(12)
    assert tab._addl_spins["contingency_pct"].value() == pytest.approx(7.5)
    assert tab._volume_spin.value() == pytest.approx(6000.0 / 1200.0)


# ---------------------------------------------------------------------------
# History tab behaviour
# ---------------------------------------------------------------------------


class _Row:
    """Minimal QModelIndex stand-in for double-click tests."""

    def __init__(self, row: int) -> None:
        self._row = row

    def row(self) -> int:
        return self._row


def _make_psd_record(db, tag: str) -> int:
    from concrete_mix.engine.psd import compute_psd

    result = compute_psd([0, 5, 45, 210, 60, 70, 105], [10.0, 4.75, 2.36, 1.18, 0.6, 0.3, 0.15])
    inp = {
        "standard": "is383",
        "aggregate_type": "fine",
        "band_key": ["is383", "fine", "II"],
        "masses": [0, 5, 45, 210, 60, 70, 105],
        "pan_mass": 5.0,
    }
    return db.save_psd(inp, result, name=f"PSD {tag}")


def test_history_tab_load_selected_and_double_click(qt, db):
    from app.widgets.history_tab import HistoryTab

    mix = _mix_result()
    db.save_mix_design(mix._input, mix, name="mix old")
    psd_id = _make_psd_record(db, "new")  # newest → row 0

    tab = HistoryTab(db=db)
    assert tab._table.rowCount() == 2

    got: list[tuple[str, int]] = []
    tab.load_psd.connect(lambda i: got.append(("psd", i)))
    tab.load_mix_design.connect(lambda i: got.append(("mix", i)))

    # Double-clicking the newest row loads that record
    tab._on_double_click(_Row(0))
    assert got == [("psd", psd_id)]

    # Single checked row loads just that record
    got.clear()
    tab._table.cellWidget(1, 0).setChecked(True)
    tab._on_load()
    assert got == [("mix", got[0][1])]

    # Select-all then Load: every record loads; the topmost row's tab is
    # loaded last so the window navigates to the newest record's tab.
    got.clear()
    tab._select_all_cb.setChecked(True)
    assert len(tab._selected_ids()) == 2
    tab._on_load()
    assert [t for t, _ in got] == ["mix", "psd"]


def test_history_tab_export_selected_imports_back(qt, db, tmp_path, monkeypatch):
    from app.widgets import history_tab as ht
    from app.widgets.history_tab import HistoryTab
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    psd_id = _make_psd_record(db, "exp")
    rec = db.get_calculation(psd_id)
    assert json.loads(rec["input_json"])["masses"]

    tab = HistoryTab(db=db)
    tab._table.cellWidget(0, 0).setChecked(True)

    path = str(tmp_path / "selected.json")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (path, ""))
    )
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: None),
    )
    tab._on_export_selected()

    from history.db import HistoryDB

    db2 = HistoryDB(tmp_path / "imported.db")
    count = db2.import_records(open(path).read())
    assert count == 1
    imported = db2.get_calculation(psd_id)
    # Input and result blobs survive the export/import round trip
    assert json.loads(imported["input_json"])["masses"]
    assert json.loads(imported["result_json"])["total_mass"]


def test_history_tab_pagination(qt, db):
    from app.widgets.history_tab import HistoryTab

    for i in range(5):
        _make_psd_record(db, f"r{i}")

    tab = HistoryTab(db=db)
    tab._page_size = 2
    tab.refresh()

    assert tab._table.rowCount() == 2
    assert "Page 1 / 3" in tab._page_label.text()
    assert not tab._btn_prev.isEnabled()
    assert tab._btn_next.isEnabled()

    tab._on_next_page()
    assert tab._table.rowCount() == 2
    assert "Page 2 / 3" in tab._page_label.text()

    tab._on_next_page()
    assert tab._table.rowCount() == 1
    assert not tab._btn_next.isEnabled()

    tab._on_prev_page()
    assert "Page 2 / 3" in tab._page_label.text()


def test_history_tab_delete_specific_record(qt, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from app.widgets import history_tab as ht
    from app.widgets.history_tab import HistoryTab

    id1 = _make_psd_record(db, "keep")
    id2 = _make_psd_record(db, "drop")

    tab = HistoryTab(db=db)
    monkeypatch.setattr(
        ht.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    tab._delete_records([id2])

    remaining = [r["id"] for r in db.list_calculations()]
    assert remaining == [id1]
    tab.refresh()
    assert tab._table.rowCount() == 1


def test_history_tab_filter_and_search(qt, db):
    from app.widgets.history_tab import HistoryTab

    mix = _mix_result()
    db.save_mix_design(mix._input, mix, name="Site Beam Mix")
    _make_psd_record(db, "graded")

    tab = HistoryTab(db=db)
    assert tab._table.rowCount() == 2

    idx = tab._type_combo.findData("psd")
    tab._type_combo.setCurrentIndex(idx)
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 3).text() == "PSD Analysis"

    tab._type_combo.setCurrentIndex(0)  # reset to "All Types"
    tab._search_input.setText("Site Beam")
    tab._on_search()
    assert tab._table.rowCount() == 1


def test_history_detail_dialog_load_button(qt, db):
    from app.widgets.history_detail_dialog import HistoryDetailDialog

    psd_id = _make_psd_record(db, "dlg")
    rec = db.get_calculation_parsed(psd_id)

    dlg = HistoryDetailDialog(rec)
    got: list[int] = []
    dlg.load_requested.connect(got.append)
    dlg._load_btn.click()
    assert got == [psd_id]
