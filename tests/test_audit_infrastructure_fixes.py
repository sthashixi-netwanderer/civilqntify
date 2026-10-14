"""Audit R01-R06/R08-R12 regressions; temp storage and mocked HTTP only."""
from __future__ import annotations

from dataclasses import asdict, fields, replace
import csv
import io
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(tmp_path):
    from history.db import HistoryDB
    database = HistoryDB(tmp_path / "fresh" / "history.db")
    yield database
    database.close()


@pytest.fixture
def result():
    from concrete_mix.models.mix_result import MixDesignResult, CalculationStep
    return MixDesignResult(
        code_used="ACI 211.1-22", target_mean_strength_mpa=35, w_c_ratio=0.5,
        water_kg=180, cement_kg=300, scm_kg=60, fine_aggregate_kg=700,
        coarse_aggregate_kg=1100, volume_m3=2.5, adjusted_water_kg=145,
        field_fine_aggregate_kg=728, field_coarse_aggregate_kg=1107,
        admixture_kg=3.6, admixture_type="superplasticizer", admixture_dosage_percent=1,
        water_reduction_percent=20, ca_split_kg={"10 mm": 400, "20 mm": 700},
        warnings=("Verify site moisture",),
        steps=(CalculationStep(1, "Water", "W = C × w/c", {"C": 360}, 180, "kg/m³"),),
    )


@pytest.mark.parametrize("standard", ["1", "2", "3"])
def test_cli_full_default_workflow(standard, tmp_path):
    # Real executable path, prompts, engine, text report AND quantification.
    env = dict(os.environ, HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path))
    proc = subprocess.run([sys.executable, str(ROOT / "main_cli.py")],
                          input=standard + "\n" + "\n" * 100, text=True,
                          capture_output=True, cwd=tmp_path, env=env, timeout=25)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "MATERIAL BILL OF QUANTITIES" in proc.stdout
    assert "CivilQntify — Done" in proc.stdout
    assert not (tmp_path / ".civilqntify/history.db").exists()


@pytest.mark.parametrize("code", ["aci211", "is10262", "doe"])
def test_all_mix_input_fields_round_trip(code):
    from concrete_mix.models.mix_input import MixDesignInput
    from concrete_mix.models.materials import Cement, FineAggregate, CoarseAggregate, SCM, Admixture
    from history.serializers import serialize_mix_input, deserialize_mix_input
    inp = MixDesignInput(
        code=code, target_strength_mpa=40, characteristic_strength_mpa=30,
        ca_volume_fraction_override=0.61, slump_mm=90,
        cement=Cement(specific_gravity=3.12),
        fine_aggregate=FineAggregate(moisture_content_percent=4, grading_zone="III"),
        coarse_aggregate=CoarseAggregate(moisture_content_percent=2, bulk_density_kg_m3=1550),
        scms=(SCM(replacement_percent=15),), admixture=Admixture(water_reduction_percent=20),
        exposure_class="moderate", concrete_type="plain", air_entrained=True,
        w_c_ratio=0.45, volume_m3=3.5, has_production_data=False,
        sulfate_exposure_class="S1", freezing_exposure_class="F1",
        water_exposure_class="W1", corrosion_exposure_class="C1",
        form_width_mm=500, slab_depth_mm=200, bar_spacing_mm=80,
        concrete_temp_c=30, manufactured_sand=True, prestressed=True,
        num_strength_tests=20, apply_rounded_aggregate_reduction=True,
        target_paste_volume_pct=30, trial_density_kg_m3=2350,
        trial_slump_mm=80, trial_air_pct=3, trial_strength_mpa=37,
        air_pct=3, vebe_s=5, ca_split="10+20", placing_method="pump",
        pump_ca_reduction_percent=4, site_control="fair", admixture_water_kg=1,
        mass_concrete=True, scc_class="SF2", scc_slump_flow_mm=700,
        scc_lbox_ratio=0.9, scc_segregation_pct=10, scc_vfunnel_s=8,
        defective_percent=2.5, age_days=91, min_cement_kg=250, max_cement_kg=500,
        std_deviation=5, margin_mpa=10, num_test_cubes=30, aggregate_relative_density_ssd=2.6,
    )
    data = json.loads(serialize_mix_input(inp))
    assert data["schema_version"] == 2
    assert {f.name for f in fields(inp)} <= data.keys()
    restored = deserialize_mix_input(data)
    assert asdict(restored) == asdict(inp)
    assert restored.cement.type.value == inp.cement.type.value
    assert restored.fine_aggregate.shape.value == inp.fine_aggregate.shape.value


def test_old_mix_inputs_warn_about_defaults():
    from concrete_mix.models.mix_input import MixDesignInput
    from history.serializers import serialize_mix_input, deserialize_mix_input
    data = json.loads(serialize_mix_input(MixDesignInput(code="aci211", target_strength_mpa=30)))
    data.pop("schema_version")
    for key in ("target_paste_volume_pct", "num_strength_tests", "pump_ca_reduction_percent",
                "ca_volume_fraction_override", "apply_rounded_aggregate_reduction"):
        data.pop(key)
    with pytest.warns(UserWarning, match="model defaults.*target_paste_volume_pct"):
        inp = deserialize_mix_input(data)
    assert inp.target_paste_volume_pct is None
    with pytest.raises(ValueError, match="schema version"):
        deserialize_mix_input(dict(data, schema_version=999))


def test_result_bill_and_transfer_round_trip(result):
    from history.serializers import (serialize_mix_result, deserialize_mix_result, serialize_bill,
                                     deserialize_bill, serialize_transfer_data)
    from material_quantify.models.transfer_data import MixDesignTransferData
    from material_quantify.engine.quantifier import MaterialQuantifier
    assert deserialize_mix_result(json.loads(serialize_mix_result(result))) == result
    transfer = MixDesignTransferData.from_mix_design_result(result)
    transfer_json = json.loads(serialize_transfer_data(transfer))
    assert transfer_json == asdict(transfer)
    bill = MaterialQuantifier(transfer).quantify_by_volume(2, 5)
    assert asdict(deserialize_bill(json.loads(serialize_bill(bill)))) == asdict(bill)


def record(id=10, parent=None, **overrides):
    return dict(id=id, parent_id=parent, tab_type="mix_design", name="Imported",
                input_json="{}", result_json="{}", **overrides)


@pytest.mark.parametrize("occupied", [False, True])
def test_import_remaps_out_of_order_graph(db, occupied):
    if occupied:
        db.import_records(json.dumps(record(id=1)))
    rows = [record(id=20, parent=10), record(id=30, parent=20), record(id=10)]
    assert db.import_records(json.dumps(rows)) == 3
    imported = db.list_calculations(limit=-1)[-3:]
    # Locate by inserted IDs, not pinned/date ordering.
    start = 2 if occupied else 1
    child, grandchild, root = [db.get_calculation(i) for i in range(start, start + 3)]
    assert child["parent_id"] == root["id"]
    assert grandchild["parent_id"] == child["id"]
    assert root["parent_id"] is None


@pytest.mark.parametrize("rows", [
    [record(), record()], [record(parent=999)], [record(parent=10)],
    [record(id=10, parent=20), record(id=20, parent=10)],
    [record(), 7], [record(), dict(input_json="[")],
    [record(), dict(result_json="[]")], [record(), dict(pinned="yes")],
])
def test_invalid_import_never_leaks_into_later_save(db, rows):
    with pytest.raises(ValueError):
        db.import_records(json.dumps(rows))
    db.import_records(json.dumps(record(id=99)))
    assert db.count_calculations() == 1


def test_import_database_failure_rolls_back(db):
    db._conn.execute("CREATE TRIGGER reject_bad BEFORE INSERT ON calculations "
                     "WHEN NEW.name='bad' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    rows = [record(id=1), dict(record(id=2), name="bad")]
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        db.import_records(json.dumps(rows))
    assert not db._conn.in_transaction
    db.import_records(json.dumps(record(id=3)))
    assert db.count_calculations() == 1


def test_export_all_exceeds_old_cap(db):
    rows = [record(id=i) for i in range(1, 10002)]
    assert db.import_records(json.dumps(rows)) == 10001
    assert len(json.loads(db.export_all())) == 10001
    assert len(json.loads(db.export_all("mix_design"))) == 10001
    assert json.loads(db.export_all("psd")) == []


def test_structured_exports_include_batch_schedule(result):
    from concrete_mix.export.json_export import export_to_json
    from concrete_mix.export.csv_export import export_to_csv
    exported = json.loads(export_to_json(result))
    assert exported["volume_m3"] == 2.5
    schedule = exported["batching"]
    assert schedule["design_ssd_per_m3"]["water_kg"] == 180
    assert schedule["field_per_m3"]["water_kg"] == 145
    assert schedule["field_batch_kg"]["water_kg"] == 362.5
    assert schedule["field_batch_kg"]["admixture_kg"] == 9
    assert schedule["field_batch_kg"]["fine_aggregate_kg"] == 1820
    assert schedule["field_batch_kg"]["coarse_aggregate_kg"] == 2767.5
    assert schedule["design_ca_split_batch_kg"] == {"10 mm": 1000, "20 mm": 1750}
    rows = {row[0]: row[1:] for row in csv.reader(io.StringIO(export_to_csv(result)))}
    assert rows["field_batch_kg: admixture_kg"] == ["9.0", "kg"]
    assert rows["Warning"] == ["Verify site moisture", ""]
    missing = json.loads(export_to_json(replace(result, adjusted_water_kg=None)))
    assert missing["batching"]["field_batch_kg"]["water_kg"] is None
    zero = json.loads(export_to_json(replace(result, adjusted_water_kg=0)))
    assert zero["batching"]["field_batch_kg"]["water_kg"] == 0


def test_latex_text_is_not_executable_and_unicode_survives(result):
    from concrete_mix.export.pdf_report import _sanitize_latex, generate_latex_source
    hostile = r"\input{/etc/passwd} $\write18{touch bad}$ %&#_^~ __LATEXUNI0__"
    expected = r"\textbackslash{}input\{/etc/passwd\}"
    escaped = _sanitize_latex(hostile)
    assert expected in escaped
    assert r"\input{" not in escaped
    assert r"\write18{" not in escaped
    assert r"\$" in escaped
    assert _sanitize_latex("m³ ≥ σ") == r"m$^{3}$ $\geq$ $\sigma$"
    assert _sanitize_latex("Accra café") == "Accra café"
    step = replace(result.steps[0], description=hostile, formula=hostile, unit=hostile,
                   clause_ref=hostile, inputs={hostile: hostile})
    source = generate_latex_source(replace(result, steps=(step,), warnings=(hostile,)),
                                   {"project_name": hostile, "date": hostile})
    assert source.count(expected) >= 7
    assert r"\input{" not in source
    assert r"\write18{" not in source


def test_latex_subprocess_is_hardened(result, monkeypatch):
    import concrete_mix.export.pdf_report as pdf
    monkeypatch.setattr(pdf, "_find_latex_engine", lambda: "/fake/pdflatex")
    monkeypatch.setenv("TEXINPUTS", "/unsafe")
    calls = []
    def compile_fake(command, **kwargs):
        calls.append((command, kwargs))
        (Path(kwargs["cwd"]) / "report.pdf").write_bytes(b"%PDF-test")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
    monkeypatch.setattr(pdf.subprocess, "run", compile_fake)
    assert pdf.generate_pdf_report(result) == b"%PDF-test"
    assert len(calls) == 2
    for command, kwargs in calls:
        assert "-no-shell-escape" in command
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 30
        assert kwargs["env"]["openin_any"] == "p"
        assert kwargs["env"]["openout_any"] == "p"
        assert "TEXINPUTS" not in kwargs["env"]
        assert not Path(kwargs["cwd"]).exists()


def test_package_version_and_runtime_dependencies():
    from scripts.build_deb import DEFAULT_VERSION, runtime_dependencies
    from app.version import __version__
    assert DEFAULT_VERSION == __version__
    deps = runtime_dependencies()
    for package in ("python3-fpdf2", "python3-scipy", "python3-docx", "python3-requests"):
        assert package in deps
    assert "pytest" not in deps and "pyinstaller" not in deps


def test_desktop_install_fresh_home(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path))
    proc = subprocess.run(["bash", str(ROOT / "scripts/install_linux_desktop.sh")],
                          env=env, capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stderr
    desktop = tmp_path / ".local/share/applications/civilqntify.desktop"
    assert desktop.exists()
    assert "@APPDIR@" not in desktop.read_text()
    assert list((tmp_path / ".local/share/icons/hicolor").rglob("*.png"))


@pytest.fixture
def qt(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_history_import_errors_are_actionable(qt, db, monkeypatch, tmp_path):
    import app.widgets.history_tab as history_tab
    monkeypatch.setattr(history_tab, "get_db", lambda: db)
    widget = history_tab.HistoryTab()
    path = tmp_path / "missing.json"
    monkeypatch.setattr(history_tab.QFileDialog, "getOpenFileName", lambda *a: (str(path), ""))
    errors = []
    monkeypatch.setattr(history_tab.QMessageBox, "critical", lambda *a: errors.append(a[-1]))
    widget._on_import()
    assert errors and "Could not import" in errors[-1]
    path.write_text("{}")
    def fail(*a):
        raise sqlite3.IntegrityError("simulated database failure")
    monkeypatch.setattr(db, "import_records", fail)
    widget._on_import()
    assert "simulated database failure" in errors[-1]
    widget.close()


def mock_forecasts(monkeypatch):
    from app.weather.weather_service import WeatherService
    from app.weather.weatherapi_service import WeatherAPIService
    monkeypatch.setattr(WeatherService, "get_hourly_forecast", lambda **kw: {"hourly": []})
    monkeypatch.setattr(WeatherService, "get_forecast", lambda **kw: {"forecasts": []})
    monkeypatch.setattr(WeatherAPIService, "get_hourly_forecast", lambda **kw: {"hourly": []})
    monkeypatch.setattr(WeatherAPIService, "get_daily_forecast", lambda **kw: {"forecasts": []})
    monkeypatch.setattr(WeatherAPIService, "get_current_weather", lambda **kw: {"temperature": 33})


def pump(qt, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.005)
    assert predicate()


@pytest.mark.parametrize("old_error", [False, True])
def test_weather_city_switch_rejects_stale_responses(qt, monkeypatch, old_error):
    from app.weather.weather_service import WeatherService
    from app.widgets.weather_widget import WeatherWidget
    mock_forecasts(monkeypatch)
    started, release = threading.Event(), threading.Event()
    calls = []
    def current(**kw):
        calls.append(kw)
        if len(calls) == 1:
            started.set()
            assert release.wait(3)
            if old_error:
                raise RuntimeError("stale failure")
            return {"temperature": 11}
        return {"temperature": 31}
    monkeypatch.setattr(WeatherService, "get_current_weather", current)
    widget = WeatherWidget()
    try:
        assert started.wait(2)
        old = widget._openmeteo_worker
        widget._openmeteo_city_combo.setCurrentIndex(1)
        pump(qt, lambda: widget._temp_card._value.text() == "31.0°C")
        release.set()
        assert old.wait(2000)
        qt.processEvents()
        assert widget._temp_card._value.text() == "31.0°C"
        assert widget._status_label.text() == "Weather data loaded"
        assert len(calls) == 2
        assert calls[0] != calls[1]
    finally:
        release.set()
        widget.shutdown()
        widget.close()


def test_weather_api_switch_and_single_request_inputs(qt, monkeypatch):
    from app.weather.weather_worker import WeatherWorker
    from app.weather.weather_service import WeatherService
    from app.widgets.weather_widget import WeatherWidget
    mock_forecasts(monkeypatch)
    monkeypatch.setattr(WeatherService, "get_current_weather", lambda **kw: {"temperature": 22})
    worker = WeatherWorker()
    worker.set_params(1, 2, "A")
    with pytest.raises(RuntimeError, match="single-request"):
        worker.set_params(3, 4, "B")
    widget = WeatherWidget()
    try:
        widget.set_api_key("mock-key")
        widget._current_api = "weatherapi"
        widget._on_city_changed()
        pump(qt, lambda: widget._temp_card._value.text() == "33.0°C")
    finally:
        widget.shutdown()
        widget.close()


@pytest.mark.parametrize("destroy", ["sip.delete(widget)", "sip.delete(parent)",
                                     "widget.close()", "app.aboutToQuit.emit()"])
def test_weather_shutdown_no_running_qthread_abort(tmp_path, destroy):
    # An abort would kill pytest; isolate all teardown paths in bounded children.
    script = '''
import time
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QWidget
from app.weather.weather_service import WeatherService
from app.widgets.weather_widget import WeatherWidget
app = QApplication([])
def slow(**kwargs):
    time.sleep(0.1)
    return {"temperature": 20, "hourly": [], "forecasts": []}
WeatherService.get_current_weather = slow
WeatherService.get_hourly_forecast = slow
WeatherService.get_forecast = slow
parent = QWidget()
widget = WeatherWidget(parent)
workers = list(widget._worker_group.workers)
time.sleep(0.02)
''' + destroy + '''
assert all(not worker.isRunning() for worker in workers)
app.processEvents()
print("clean shutdown")
'''
    env = dict(os.environ, HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path),
               QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "clean shutdown" in proc.stdout
