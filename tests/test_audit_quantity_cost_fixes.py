"""Regression coverage for audit Q01–Q10 and cost PDF portability R07."""
from __future__ import annotations

from dataclasses import asdict, replace
import json
import time

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QFileDialog

from app.unit_preferences import UnitPreferences, UnitSystem
from app.widgets.cost_estimation_tab import CostEstimationTab
from app.widgets.material_quantify_tab import MaterialQuantifyTab
from app.widgets.unit_spin import UnitSpinBox
from material_quantify.cost import ProjectMaterialPrices, estimate_project_cost
from material_quantify.engine.quantifier import MaterialQuantifier
from material_quantify.models.transfer_data import MixDesignTransferData


@pytest.fixture(scope="module")
def qt():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def prefs(qt, monkeypatch, tmp_path):
    import app.unit_preferences as module
    prefs = UnitPreferences()
    prefs._settings = QSettings(str(tmp_path / "units.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(module, "_instance", prefs)
    return prefs


@pytest.fixture
def tabs(prefs, qt):
    created = []

    def make(cls):
        tab = cls()
        tab.unit_prefs = prefs
        created.append(tab)
        return tab

    yield make
    for tab in created:
        if isinstance(tab, MaterialQuantifyTab):
            tab._debounce.stop()
            tab._pending_quantification = False
            tab._worker.blockSignals(True)
            assert tab._worker.wait(3000)
        tab.close()
        tab.deleteLater()
    qt.processEvents()


def transfer(**changes):
    data = MixDesignTransferData(
        code_used="ACI 211.1-22", cement_kg_per_m3=350,
        water_kg_per_m3=175, fine_aggregate_kg_per_m3=700,
        coarse_aggregate_kg_per_m3=1100, scm_kg_per_m3=0,
        admixture_kg_per_m3=0, air_volume_percent=2,
        w_c_ratio=.5, target_mean_strength_mpa=35,
        field_water_kg_per_m3=170, field_fine_aggregate_kg_per_m3=700,
        field_coarse_aggregate_kg_per_m3=1100,
        cement_bag_weight_kg=42.64, coarse_agg_bulk_density_kg_m3=1800,
        fine_agg_specific_gravity=2.8, coarse_agg_specific_gravity=2.75,
    )
    return replace(data, **changes)


def wait_for(qt, condition, seconds=4):
    end = time.monotonic() + seconds
    while not condition() and time.monotonic() < end:
        qt.processEvents()
        time.sleep(.005)
    qt.processEvents()
    assert condition(), "Timed out waiting for bounded quantification request"


@pytest.mark.parametrize("kind,metric,display", [
    ("rate_volume", 350., 350. / 1.30795),
    ("rate_mass", 12., 12. / 2.20462),
    ("rate_water", 15., 15. / .264172),
])
def test_q01_typed_rates_identity_reciprocal_and_toggles(prefs, kind, metric, display):
    spin = UnitSpinBox(kind, 0, 0, 10000, decimals=4)
    spin.set_display_value(metric)
    assert spin.value() == pytest.approx(metric)
    assert spin.display_value() == pytest.approx(metric)
    if kind == "rate_water":
        assert spin.unit_label() == "per 1000 L"
    prefs.set_system(UnitSystem.IMPERIAL)
    assert spin.display_value() == pytest.approx(display, abs=.0001)
    spin.set_display_value(display * 2)
    assert spin.value() == pytest.approx(metric * 2, abs=.001)
    before = spin.value()
    for _ in range(5):
        prefs.set_system(UnitSystem.METRIC)
        prefs.set_system(UnitSystem.IMPERIAL)
    assert spin.value() == before


def test_q01_water_control_panel_and_report_agree(tabs, prefs):
    tab = tabs(CostEstimationTab)
    prefs.set_system(UnitSystem.IMPERIAL)
    row = {"qty": 1000., "unit_price": 15., "kind": "water"}
    report = tab._convert_breakdown_row(row, prefs)
    panel = tab._result_panel._convert_breakdown_row(row)
    assert panel == report
    qty, unit, price = panel
    assert qty == pytest.approx(264.172)
    assert price == pytest.approx(56.7812, rel=1e-5)
    assert qty / 1000 * price == pytest.approx(15.)
    assert "1000" in unit


def test_q02_purchasing_bulk_is_not_ssd_absolute_volume():
    td = transfer(fine_agg_bulk_density_kg_m3=1600,
                  fine_agg_bulk_density_basis="Measured as-delivered loose bulk density")
    bill = MaterialQuantifier(td).quantify_by_volume(1, 0)
    assert bill.total_fine_aggregate_bulk_m3 == .4375
    assert bill.total_fine_aggregate_absolute_m3 == .25  # SSD SG 2.8
    assert "Measured" in bill.fine_aggregate_volume_basis
    # Field moisture changes purchase mass, but not SSD particle volume.
    wet = MaterialQuantifier(replace(td, field_fine_aggregate_kg_per_m3=770)).quantify_by_volume(1, 0)
    assert wet.total_fine_aggregate_bulk_m3 == 770 / 1600
    assert wet.total_fine_aggregate_absolute_m3 == .25
    assert "Project assumption" in transfer().fine_agg_bulk_density_basis
    with pytest.raises(ValueError, match="density"):
        MaterialQuantifier(replace(td, fine_agg_bulk_density_kg_m3=0)).quantify_by_volume(1)


def test_q03_scm_unpriced_incomplete_and_priced_in_total():
    bill = MaterialQuantifier(transfer(scm_kg_per_m3=308, scm_type="GGBS")).quantify_by_volume(1, 0)
    incomplete = estimate_project_cost(bill)
    assert incomplete["is_complete"] is False
    assert any("INCOMPLETE" in warning for warning in incomplete["warnings"])
    assert "PARTIAL" in incomplete["summary_rows"][-1]["label"]
    priced = estimate_project_cost(bill, ProjectMaterialPrices(scm_per_kg=2))
    assert priced["is_complete"] is True
    assert priced["total_material_cost"] - incomplete["total_material_cost"] == 616
    scm_row = next(row for row in priced["material_breakdown"] if row["name"] == "SCM")
    assert scm_row["material_type"] == "GGBS"
    assert scm_row["total"] == 616
    assert estimate_project_cost(bill, ProjectMaterialPrices(scm_per_kg=0))["is_complete"]


def test_q04_q05_q06_transfer_preserves_properties_and_resets_overrides(tabs, qt):
    tab = tabs(MaterialQuantifyTab)
    tab.load_transfer_data(transfer(cement_kg_per_m3=400))
    wait_for(qt, lambda: tab._last_bill is not None and not tab._worker.isRunning())
    override = tab._override_spins["cement_kg_per_m3"]
    assert override.value() == 400
    override.setReadOnly(False)
    override.setValue(500)
    tab.load_transfer_data(transfer(code_used="IS 10262:2019", cement_kg_per_m3=600, scm_kg_per_m3=308))
    wait_for(qt, lambda: tab._last_bill is not None and not tab._worker.isRunning())
    td = tab._last_bill.transfer_data
    assert td.cement_kg_per_m3 == 600
    assert td.scm_kg_per_m3 == 308
    assert tab._data_spins["scm"].value() == 308
    assert override.isReadOnly() and override.value() == 600
    assert td.coarse_agg_bulk_density_kg_m3 == 1800
    assert td.fine_agg_specific_gravity == 2.8
    assert td.air_volume_percent == 2
    assert td.code_used == "IS 10262:2019"
    assert tab._code_combo.currentData() == "is10262"
    tab.load_transfer_data(transfer())
    wait_for(qt, lambda: tab._last_bill is not None and not tab._worker.isRunning())
    assert tab._last_bill.transfer_data.code_used == "ACI 211.1-22"
    assert tab._code_combo.currentData() == "aci211"


def test_q05_main_handoff_uses_calculated_properties(tabs):
    from types import SimpleNamespace
    from app.main import MainWindow
    from concrete_mix.models.mix_result import MixDesignResult
    quant = SimpleNamespace(load_transfer_data=lambda td: received.append(td))
    received = []
    window = SimpleNamespace(
        concrete_tab=SimpleNamespace(_last_input_params={"coarse_agg_bulk_density": 1800,
            "fine_agg_sg": 2.8, "coarse_agg_sg": 2.75, "scm_type": "GGBS"}),
        quant_tab=quant, tabs=SimpleNamespace(setCurrentWidget=lambda widget: None),
        unit_prefs=UnitPreferences(), status_bar=SimpleNamespace(showMessage=lambda *args: None),
    )
    result = MixDesignResult("ACI 211.1-22", 35, .5, 175, 350)
    MainWindow._on_send_to_quant(window, result)
    assert received[0].fine_agg_specific_gravity == 2.8
    assert received[0].coarse_agg_bulk_density_kg_m3 == 1800
    assert received[0].scm_type == "GGBS"


def test_q07_cost_replacement_and_typed_change_invalidate(tabs):
    tab = tabs(CostEstimationTab)
    bill = MaterialQuantifier(transfer()).quantify_by_volume(10)
    tab.load_bill(bill)
    tab._on_estimate()
    assert tab._last_cost_data is not None
    tab.load_bill(MaterialQuantifier(transfer()).quantify_by_volume(100))
    assert tab._last_cost_data is None
    assert not tab._result_panel.btn_pdf.isEnabled()
    tab._on_estimate()
    tab._price_spins["fine_agg_per_m3"].set_display_value(500)
    assert tab._last_cost_data is None
    assert tab._result_panel._cost_data is None


def test_q07_invalid_element_mode_disables_send(tabs, qt, monkeypatch):
    from app.widgets import material_quantify_tab as qmod
    monkeypatch.setattr(qmod.QMessageBox, "warning", lambda *args: None)
    tab = tabs(MaterialQuantifyTab)
    tab._run_quantification()
    wait_for(qt, lambda: tab._last_bill is not None and not tab._worker.isRunning())
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("elements"))
    tab._elem_table.setRowCount(0)
    tab._run_quantification()
    assert tab._last_bill is None
    assert tab._result_panel._bill is None
    assert not tab._result_panel._btn_cost.isEnabled()


@pytest.mark.parametrize("ratio", [False, True])
def test_q08_worker_queues_latest_and_rejects_obsolete(tabs, qt, monkeypatch, ratio):
    from material_quantify.engine.ratio_quantifier import MixRatioQuantifier
    cls = MixRatioQuantifier if ratio else MaterialQuantifier
    original = cls.quantify_by_volume
    calls = []

    def slow(self, volume, wastage):
        calls.append(volume)
        time.sleep(.40)
        return original(self, volume, wastage)

    monkeypatch.setattr(cls, "quantify_by_volume", slow)
    tab = tabs(MaterialQuantifyTab)
    if ratio:
        tab._left_tabs.setCurrentIndex(1)
    volume = tab.ratio_volume_spin if ratio else tab.volume_spin
    volume.setValue(10)
    tab._run_quantification()
    volume.set_display_value(20)
    # Let the 300 ms debounce expire while the first 400 ms request runs.
    # The pending revision must be scheduled without another click.
    assert tab._last_bill is None
    wait_for(qt, lambda: tab._last_bill is not None and not tab._worker.isRunning())
    assert calls == [10, 20]
    assert tab._last_bill.net_concrete_volume_m3 == 20
    assert tab._result_panel._bill.net_concrete_volume_m3 == 20


def test_q08_queued_old_signal_cannot_match_new_running_revision(tabs):
    tab = tabs(MaterialQuantifyTab)
    tab._input_revision = 8
    tab._running_revision = 8  # New request already started before delivery.
    old_bill = MaterialQuantifier(transfer()).quantify_by_volume(10)
    tab._on_request_result(7, old_bill)
    tab._on_worker_error(7, "obsolete error")
    assert tab._last_bill is None
    assert tab._result_panel._bill is None


class RecordDB:
    def __init__(self, result, inputs=None):
        self.record = {"result_json": json.dumps(result), "input_json": json.dumps(inputs or {})}

    def get_calculation(self, calc_id):
        return self.record


@pytest.mark.parametrize("ratio", [False, True])
def test_q09_restored_element_labels_refreshed(tabs, ratio):
    tab = tabs(MaterialQuantifyTab)
    bill = MaterialQuantifier(transfer()).quantify_by_volume(.72)
    element = {"element_type": "beam", "length_m": 6, "width_m": .3, "depth_m": .4, "quantity": 1}
    key = "ratio_ui" if ratio else "design_ui"
    tab._history_db = RecordDB(asdict(bill), {key: {"mode": "elements", "elements": [element]}})
    tab.load_from_history(1)
    table = tab._ratio_elem_table if ratio else tab._elem_table
    label = tab._ratio_elem_total_label if ratio else tab._elem_total_label
    assert "0.720" in table.item(0, 5).text()
    assert "0.720" in label.text()
    assert tab._last_bill.net_concrete_volume_m3 == .72


def test_q10_zero_material_explicit_volume_round_trip(tabs):
    tab = tabs(CostEstimationTab)
    tab._volume_spin.setValue(20)
    tab._on_estimate()
    result = tab._last_cost_data
    assert result["gross_concrete_volume_m3"] == 20
    assert result["total_material_cost"] == 0
    restored = tabs(CostEstimationTab)
    restored._history_db = RecordDB(result)
    restored.load_from_history(1)
    assert restored._volume_spin.value() == 20
    restored._on_estimate()
    assert restored._last_cost_data["total_project_cost"] == result["total_project_cost"]


def test_cost_history_preserves_scm_type_price_and_bag_weight(tabs):
    source = tabs(CostEstimationTab)
    source.load_bill(MaterialQuantifier(transfer(scm_kg_per_m3=308, scm_type="GGBS")).quantify_by_volume(20))
    source._price_spins["scm_per_kg"].setValue(2)
    source._scm_priced.setChecked(True)
    source._on_estimate()
    saved = source._last_cost_data
    restored = tabs(CostEstimationTab)
    restored._history_db = RecordDB(saved)
    restored.load_from_history(1)
    restored._on_estimate()
    scm = next(row for row in restored._last_cost_data["material_breakdown"] if row["name"] == "SCM")
    assert scm["material_type"] == "GGBS"
    assert scm["priced"] and scm["unit_price"] == 2
    assert restored._last_cost_data["cement_bag_weight_kg"] == 42.64
    assert restored._last_cost_data["total_project_cost"] == saved["total_project_cost"]


def test_defaulted_dataclass_fields_legacy_history_and_new_round_trip():
    from history.serializers import deserialize_bill, serialize_bill
    bill = MaterialQuantifier(transfer(scm_type="GGBS")).quantify_by_volume(1)
    restored = deserialize_bill(json.loads(serialize_bill(bill)))
    assert restored == bill
    legacy = asdict(bill)
    legacy.pop("total_fine_aggregate_absolute_m3")
    legacy.pop("fine_aggregate_volume_basis")
    for name in ("fine_agg_bulk_density_kg_m3", "fine_agg_bulk_density_basis", "scm_type"):
        legacy["transfer_data"].pop(name)
    assert "unverified" in deserialize_bill(legacy).fine_aggregate_volume_basis


@pytest.mark.parametrize("fallback", [False, True])
def test_r07_cost_pdf_portable_resources_and_fallback(tabs, monkeypatch, tmp_path, fallback):
    from pathlib import Path
    tab = tabs(CostEstimationTab)
    tab._qty_spins["scm_kg"].setValue(308)
    tab._on_estimate()
    path = tmp_path / "estimate.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), "PDF"))
    errors = []
    from app.widgets import cost_estimation_tab as cmod
    monkeypatch.setattr(cmod.QMessageBox, "warning", lambda *args: errors.append(args))
    if fallback:
        original = Path.is_file
        monkeypatch.setattr(Path, "is_file", lambda p: False if p.suffix == ".ttf" else original(p))
    tab._do_export_pdf()
    assert not errors
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1000


def test_scm_gui_supplied_rate_and_incomplete_reports(tabs):
    tab = tabs(CostEstimationTab)
    tab._qty_spins["scm_kg"].set_display_value(10000)
    tab._on_estimate()
    assert not tab._last_cost_data["is_complete"]
    assert "INCOMPLETE" in tab._generate_cost_report_html()
    tab._price_spins["scm_per_kg"].set_display_value(2)
    tab._scm_priced.setChecked(True)
    tab._on_estimate()
    assert tab._last_cost_data["total_material_cost"] == 20000
    assert tab._last_cost_data["is_complete"]
