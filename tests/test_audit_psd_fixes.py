"""Regression evidence for validation report P01–P08.

Limits: IS 383:2016 clauses 6.1–6.3, Tables 7/9 (including Note 1),
ASTM C33 clauses 6.1/6.2/10.1. BS behavior remains governed by BS 882 and
BS 812-103.1; no grading tables or reporting policies are changed here.
"""
from __future__ import annotations

import math

import pytest

from concrete_mix.codes.tables.grading_bands import (
    get_astm_coarse_band, get_astm_fine_band, get_fine_band, get_is_coarse_band,
)
from concrete_mix.engine.grading import classify_is383_zone
from concrete_mix.engine.psd import (
    IS_FINE_SIEVES, check_conformance, compute_psd,
)
from concrete_mix.engine.psd_link import derive_mix_design_params
from concrete_mix.validation.astm_c33 import (
    CoarseQualityInputs, FineQualityInputs,
    evaluate_astm_c33_coarse, evaluate_astm_c33_fine,
)
from concrete_mix.validation.is383 import (
    IS383CoarseQualityInputs, IS383FineQualityInputs,
    evaluate_is383_coarse, evaluate_is383_fine,
)


MASSES = [0, 20, 80, 200, 250, 250, 150]  # p600=45, total=1000 with pan=50


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, "oops", None])
@pytest.mark.parametrize("where", ["mass", "pan", "sieve"])
def test_p02_engine_rejects_invalid_evidence(bad, where):
    masses, sieves, pan = [0, 100], [10, 5], 0
    if where == "mass":
        masses[0] = bad
    elif where == "pan":
        pan = bad
    else:
        sieves[0] = bad
    with pytest.raises(ValueError):
        compute_psd(masses, sieves, pan)


@pytest.mark.parametrize("sieves", [[10, 10], [5, 10], [10, 0], [10, -5]])
def test_p02_engine_rejects_invalid_sieve_stack(sieves):
    with pytest.raises(ValueError):
        compute_psd([0, 100], sieves)


def test_p02_engine_rejects_overflowed_total():
    with pytest.raises(ValueError, match="Total mass"):
        compute_psd([1e308, 1e308], [10, 5])


@pytest.mark.parametrize("standard", ["is383", "astm_c33"])
def test_p03_missing_coarse_controls_are_not_assessed(standard):
    result = compute_psd([0], [100], 100)
    if standard == "is383":
        band = get_is_coarse_band("graded", 20)
        checks = evaluate_is383_coarse(result, band, IS383CoarseQualityInputs())
    else:
        band = get_astm_coarse_band(20)
        checks = evaluate_astm_c33_coarse(result, band, CoarseQualityInputs())
    assert checks[0].status == "not_evaluated"
    assert "Missing" in checks[0].detail
    assert not result.all_conform
    check_conformance(result, {})
    assert not result.all_conform


def test_p03_missing_fine_controls_cannot_pass_zone_or_astm_intervals():
    result = compute_psd([50], [.6], 50)
    classification = classify_is383_zone({.6: 50})
    assert classification.zone == "II"  # identification is not conformance
    assert not classification.conforms
    check = evaluate_is383_fine(
        result, get_fine_band("II"), IS383FineQualityInputs(), zone="II",
    )[0]
    assert check.status == "not_evaluated"
    checks = evaluate_astm_c33_fine(result, get_astm_fine_band(), FineQualityInputs())
    assert checks[0].status == "not_evaluated"
    assert checks[1].status == "not_evaluated"


def test_p03_zero_sample_is_not_passing_evidence():
    result = compute_psd([0] * len(IS_FINE_SIEVES), IS_FINE_SIEVES)
    check_conformance(result, get_fine_band("II"))
    assert not result.all_conform
    assert evaluate_is383_fine(
        result, get_fine_band("II"), IS383FineQualityInputs(), zone="II",
    )[0].status == "not_evaluated"


def test_p04_selected_zone_is_assessed_not_just_inserted_in_success_text():
    result = compute_psd(MASSES, IS_FINE_SIEVES, 50)
    passing = dict(zip(result.sieve_sizes, result.percent_passing))
    assert classify_is383_zone(passing).zone == "II"
    checks = evaluate_is383_fine(
        result, get_fine_band("III"), IS383FineQualityInputs(), zone="III",
    )
    assert checks[0].status == "fail"
    assert "600" in checks[0].detail
    assert "Zone III" in checks[0].requirement
    assert evaluate_is383_fine(
        result, get_fine_band("II"), IS383FineQualityInputs(), zone="II",
    )[0].status == "pass"


@pytest.mark.parametrize("p600", [14.9, 34.5, 59.5, 79.5, 100.1])
def test_p07_no_clause_63_tolerance_at_600um(p600):
    passing = dict(zip(IS_FINE_SIEVES, [100, 98, 90, 80, p600, 25, 5]))
    classification = classify_is383_zone(passing)
    assert not classification.conforms
    assert any("600" in violation or "0.6 mm" in violation
               for violation in classification.violations)
    assert not any("600" in deviation for deviation in classification.deviations)


def test_p05_linkage_uses_explicit_crushed_stone_sand_context():
    result = compute_psd([0, 20, 80, 200, 250, 250, 40], IS_FINE_SIEVES, 160)
    assert not derive_mix_design_params(result).zone_conforms
    link = derive_mix_design_params(result, crushed_sand=True)
    assert link.zone_conforms
    assert link.zone_crushed_sand_relief
    assert not link.zone_deviations
    assert evaluate_is383_fine(
        result, get_fine_band("II"),
        IS383FineQualityInputs(source_type="crushed_stone_sand"), zone="II",
    )[0].status == "pass"


@pytest.fixture
def qt(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from app.widgets import psd_widget as psdmod
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(psdmod.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(psdmod.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(psdmod.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.widgets.psd_widget.ParticleSizeDistributionTab._show_astm_compliance_dialog",
        lambda *a: None,
    )
    yield app


@pytest.fixture
def tab(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    widget = ParticleSizeDistributionTab()
    yield widget
    widget._result_panel.close()
    widget._result_panel.deleteLater()
    widget.close()
    widget.deleteLater()
    qt.processEvents()


def fill(tab, masses=MASSES, pan=50):
    for row, mass in enumerate([*masses, pan]):
        tab.table.item(row, 1).setText(str(mass))
    tab._on_compute_plot()
    assert tab._last_result is not None


@pytest.mark.parametrize("standard", ["is383", "astm_c33"])
@pytest.mark.parametrize("change", ["sieve", "pan", "quality", "source", "band"])
def test_p01_any_input_edit_invalidates_is_astm_analysis(tab, standard, change):
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData(standard))
    if change == "band" and standard == "astm_c33":
        tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))
        masses = [0] * len(tab._current_sieves())
        masses[-1] = 950
        fill(tab, masses)
    else:
        fill(tab)
    panel = tab._result_panel
    assert panel._btn_apply.isEnabled()
    emitted = []
    panel.apply_to_mix_design.connect(emitted.append)
    if change == "sieve":
        tab.table.item(tab._current_sieves().index(.6), 1).setText("0")
        assert float(tab.table.item(tab._current_sieves().index(.6), 4).text()) != 45
    elif change == "pan":
        tab.table.item(len(tab._current_sieves()), 1).setText("60")
    elif change == "quality":
        spin = tab.is_fine_coal_spin if standard == "is383" else tab.fine_coal_spin
        spin.setValue(.2)
    elif change == "source":
        if standard == "is383":
            tab.is_fine_source_combo.setCurrentIndex(1)
        else:
            tab.fine_organic_combo.setCurrentIndex(1)
    else:
        tab.band_combo.setCurrentIndex(0)
    assert tab._last_result is None
    assert panel._last_result is None
    assert not tab._astm_checks
    assert not panel._btn_apply.isEnabled()
    assert not panel._btn_csv.isEnabled()
    assert not panel._btn_img.isEnabled()
    panel._on_apply_to_mix()
    assert not emitted
    tab._on_compute_plot()
    assert tab._last_result is not None  # valid new evidence can be computed again


@pytest.mark.parametrize("standard", ["is383", "astm_c33", "bs882"])
@pytest.mark.parametrize("text", ["oops", "NaN", "inf", "-inf", "-1", ""])
def test_p02_invalid_cells_never_become_zero(tab, monkeypatch, standard, text):
    from app.widgets import psd_widget as psdmod
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData(standard))
    if standard == "bs882":
        tab.bs_quality.m1_spin.setValue(1000)
    fill(tab)
    input_background = tab.table.item(0, 1).background()
    warnings = []
    monkeypatch.setattr(psdmod.QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    tab.table.item(0, 1).setText(text)
    assert tab.table.item(0, 1).toolTip()
    assert tab.table.item(0, 4).text() == "—"
    assert tab.table.item(tab.table.rowCount() - 1, 1).text() == "—"
    tab._on_compute_plot()
    assert warnings and "finite, nonnegative" in warnings[-1]
    assert tab._last_result is None
    assert not tab._result_panel._btn_apply.isEnabled()
    with pytest.raises(ValueError):
        tab._gather_history_input()
    tab.table.item(0, 1).setText("0")
    assert not tab.table.item(0, 1).toolTip()
    assert tab.table.item(0, 1).background() == input_background
    tab._on_compute_plot()
    assert tab._last_result is not None


def test_p05_crushed_context_consistent_in_limits_plot_checks_and_payload(tab):
    tab.is_fine_source_combo.setCurrentIndex(
        tab.is_fine_source_combo.findData("crushed_stone_sand")
    )
    fill(tab, [0, 20, 80, 200, 250, 250, 40], 160)
    panel = tab._result_panel
    assert get_fine_band("II")[.15] == (0, 10)  # shared table was not mutated
    assert tab._current_band(tab.band_combo.currentData())[.15] == (0, 20)
    assert tab.table.item(tab._current_sieves().index(.15), 5).text() == "0–20"
    assert panel._last_band[.15] == (0, 20)
    assert panel._last_result.all_conform
    assert tab._astm_checks[0].status == "pass"
    emitted = []
    panel.apply_to_mix_design.connect(emitted.append)
    panel._on_apply_to_mix()
    assert emitted[-1]["zone_conforms"]
    assert emitted[-1]["zone_crushed_sand_relief"]
    assert emitted[-1]["all_conform"]
    tab.is_fine_source_combo.setCurrentIndex(
        tab.is_fine_source_combo.findData("uncrushed")
    )
    assert tab._last_result is None
    assert tab._current_band(tab.band_combo.currentData())[.15] == (0, 10)
    tab._on_compute_plot()
    assert tab._astm_checks[0].status == "fail"


def test_p06_fractional_nominal_size_survives_payload_and_receiver(tab, qt):
    from app.widgets.concrete_tab import ConcreteMixTab
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))
    key = ("is383", "coarse", "graded", 12.5)
    tab.band_combo.setCurrentIndex(next(
        i for i in range(tab.band_combo.count()) if tab.band_combo.itemData(i) == key
    ))
    assert tab.band_combo.currentData() == key
    masses = [0] * len(tab._current_sieves())
    masses[tab._current_sieves().index(10)] = 950
    fill(tab, masses)
    receiver = ConcreteMixTab()
    # Pin what this test depends on rather than patching around it. The
    # default standard is IS 10262, whose NMSA list includes 12.5 mm; the
    # ACI and DOE rebuilds do not. Assert the precondition so a future change
    # to the default standard fails here as a stated failure, rather than
    # silently exercising a different receiver.
    assert receiver.code_combo.currentData() == "is10262"
    assert receiver.nmsa_combo.findData(12.5) >= 0, (
        "IS 10262 no longer offers a 12.5 mm nominal maximum aggregate "
        "size; this test's receiver precondition no longer holds"
    )
    emitted = []
    tab._result_panel.apply_to_mix_design.connect(emitted.append)
    tab._result_panel._on_apply_to_mix()
    assert emitted[-1]["nominal_size_mm"] == 12.5
    receiver._on_psd_apply(emitted[-1])
    assert receiver.nmsa_combo.currentData() == 12.5
    assert not receiver.nmsa_combo.isEnabled()
    receiver.close()
    receiver.deleteLater()
    qt.processEvents()


def test_p02_invalid_pan_marks_pan_and_blocks_compute(tab):
    fill(tab)
    pan = tab.table.item(len(tab._current_sieves()), 1)
    pan.setText("NaN")
    assert "Pan:" in pan.toolTip()
    assert tab.table.item(0, 4).text() == "—"
    tab._on_compute_plot()
    assert tab._last_result is None
    assert not tab._result_panel._btn_apply.isEnabled()


def test_p08_exact_report_reproduction_three_pass_seven_not_assessed(tab):
    from concrete_mix.validation.base import ClauseCheck
    checks = [ClauseCheck("test", "test", status, "test", "test")
              for status in [*(["pass"] * 3), *(["not_evaluated"] * 7)]]
    message = tab._checks_summary("ASTM C33", checks)
    assert "3 passed, 0 failed, 7 not assessed" in message
    checks.append(ClauseCheck("test", "test", "fail", "test", "test"))
    assert "3 passed, 1 failed, 7 not assessed" in tab._checks_summary("ASTM C33", checks)


def test_p08_status_counts_pass_fail_and_unassessed_honestly(tab):
    from PyQt6.QtWidgets import QStatusBar
    tab.status_bar = QStatusBar(tab)
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData("astm_c33"))
    fill(tab)
    checks = tab._astm_checks
    message = tab.status_bar.currentMessage()
    assert f"{sum(c.status == 'pass' for c in checks)} passed" in message
    assert f"{sum(c.status == 'fail' for c in checks)} failed" in message
    assert f"{sum(c.status == 'not_evaluated' for c in checks)} not assessed" in message
    assert "all 10 applicable" not in message
    assert "not a full-standard" in message
    assert tab._checks_summary("ASTM C33", checks) == message
