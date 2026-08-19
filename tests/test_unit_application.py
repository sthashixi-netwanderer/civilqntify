"""Unit-application integration tests.

Verifies that unit preferences are actually applied to inputs and outputs:
- Inputs typed in display units must reach the SI-metric backend converted.
- Unit switches must not corrupt or clamp field values.
- Unit preferences persisted at startup must be applied to labels on launch.
- Result panels must re-render in the active unit system.
"""

from __future__ import annotations

import os
import tempfile

# Isolate QSettings storage BEFORE any Qt/app import so tests never touch
# the developer's real CivilQntify settings.
_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_units_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

import pytest

qapp = None  # set in fixture


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


@pytest.fixture()
def fresh_prefs(qt):
    """Reset the UnitPreferences singleton against a clean QSettings store."""
    import app.unit_preferences as up_mod

    settings = up_mod.get_unit_prefs()._settings
    settings.clear()
    up_mod._instance = None
    yield up_mod.get_unit_prefs()
    up_mod._instance = None


def _set(prefs, system: str = "metric") -> None:
    from app.unit_preferences import UnitSystem

    prefs.set_system(UnitSystem(system))


# ── Concrete mix tab ────────────────────────────────────────────────────


def test_concrete_backend_receives_metric_for_imperial_input(fresh_prefs):
    """Imperial user input must be converted before hitting the SI backend."""
    from app.widgets.concrete_tab import ConcreteMixTab

    _set(fresh_prefs, "imperial")
    tab = ConcreteMixTab()
    tab.unit_prefs = fresh_prefs

    tab.strength_spin.set_display_value(4000.0)  # psi
    tab.slump_spin.set_display_value(4.0)  # inches
    tab.volume_spin.set_display_value(5.0)  # yd³
    tab.ca_bulk_spin.set_display_value(100.0)  # lb/ft³

    kwargs = tab._build_kwargs()
    assert kwargs["target_strength_mpa"] == pytest.approx(4000.0 / 145.038, rel=1e-3)
    assert kwargs["slump_mm"] == pytest.approx(4.0 * 25.4, rel=1e-3)
    assert kwargs["volume_m3"] == pytest.approx(5.0 / 1.30795, rel=1e-3)
    assert kwargs["coarse_agg_bulk_density"] == pytest.approx(100.0 / 0.062428, rel=1e-3)


def test_concrete_startup_applies_persisted_units(fresh_prefs):
    """App launched with imperial persisted must show imperial suffixes immediately."""
    from app.widgets.concrete_tab import ConcreteMixTab

    _set(fresh_prefs, "imperial")
    tab = ConcreteMixTab()
    tab.unit_prefs = fresh_prefs

    assert "psi" in tab.strength_spin.suffix()
    assert "yd" in tab.volume_spin.suffix()


def test_concrete_unit_toggle_round_trip_preserves_metric(fresh_prefs):
    """Toggling unit systems must preserve the underlying metric value."""
    from app.widgets.concrete_tab import ConcreteMixTab

    _set(fresh_prefs, "metric")
    tab = ConcreteMixTab()
    tab.unit_prefs = fresh_prefs
    tab.strength_spin.setValue(30.0)  # MPa (metric programmatic set)

    _set(fresh_prefs, "imperial")
    assert tab.strength_spin.value() == pytest.approx(30.0, rel=1e-6)
    assert tab.strength_spin.display_value() == pytest.approx(30.0 * 145.038, rel=1e-3)

    tab.strength_spin.set_display_value(4351.0)  # user edits in psi
    _set(fresh_prefs, "metric")
    assert tab.strength_spin.value() == pytest.approx(4351.0 / 145.038, rel=1e-3)


def test_concrete_min_max_cement_value_matches_label(fresh_prefs):
    """min/max cement content must convert with the same factor as its unit label."""
    from app.widgets.concrete_tab import ConcreteMixTab

    _set(fresh_prefs, "imperial")
    tab = ConcreteMixTab()
    tab.unit_prefs = fresh_prefs
    tab.min_cement_spin.setValue(300.0)  # kg/m³ metric programmatic set

    shown = tab.min_cement_spin.display_value()
    # 300 kg/m³ -> lb/yd³ (1.68555), the unit the suffix must display
    assert shown == pytest.approx(300.0 * 1.68555, rel=1e-3)
    assert "yd" in tab.min_cement_spin.suffix()


# ── Material quantification tab ─────────────────────────────────────────


def test_quant_element_dims_metric_metres(fresh_prefs):
    """Element dimensions are entered in metres in metric mode and reach the
    backend unchanged."""
    from app.widgets.material_quantify_tab import MaterialQuantifyTab

    _set(fresh_prefs, "metric")
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs

    tab.mode_combo.setCurrentIndex(max(tab.mode_combo.findData("elements"), 0))
    tab._add_element()
    row = tab._elem_table.cellWidget(0, 1)  # L spin of first element row
    # The 1.0 m default displays as 1.000 m
    assert row.display_value() == pytest.approx(1.0, rel=1e-6)
    assert tab._elem_table.horizontalHeaderItem(1).text() == "L (m)"
    row.set_display_value(3.0)

    elements = tab._get_elements()
    assert elements[0].length_m == pytest.approx(3.0, rel=1e-6)


def test_quant_volume_and_strength_converted(fresh_prefs):
    from app.widgets.material_quantify_tab import MaterialQuantifyTab

    _set(fresh_prefs, "imperial")
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs

    tab.volume_spin.set_display_value(10.0)  # yd³
    tab._strength_spin.set_display_value(3626.0)  # psi
    tab._bag_weight_spin.set_display_value(110.23)  # lb (50 kg)

    assert tab.volume_spin.value() == pytest.approx(10.0 / 1.30795, rel=1e-3)
    assert tab._strength_spin.value() == pytest.approx(25.0, rel=1e-3)
    assert tab._bag_weight_spin.value() == pytest.approx(50.0, rel=1e-3)


# ── Cost estimation tab ─────────────────────────────────────────────────


def test_cost_volume_converted_to_metric(fresh_prefs):
    from app.widgets.cost_estimation_tab import CostEstimationTab

    _set(fresh_prefs, "imperial")
    tab = CostEstimationTab()
    tab.unit_prefs = fresh_prefs

    tab._volume_spin.set_display_value(10.0)  # yd³
    bill = tab._build_bill_from_inputs()
    assert bill.gross_concrete_volume_m3 == pytest.approx(10.0 / 1.30795, rel=1e-3)


# ── Result panels ───────────────────────────────────────────────────────


def test_result_panel_rerenders_on_unit_change(fresh_prefs):
    """Displayed mix results must switch units when preferences change."""
    from PyQt6.QtWidgets import QLabel

    from app.widgets.result_panel import ResultPanel

    _set(fresh_prefs, "metric")
    panel = ResultPanel()
    panel.display_strength_estimate(
        fck=25.0,
        f_target=31.49,
        std_dev=4.0,
        margin="IS 10262: f'ck = fck + 1.65·s",
        wc_ratio=0.5,
        method="is10262",
        cement_kg=350.0,
        water_kg=175.0,
        fine_agg_kg=700.0,
        coarse_agg_kg=1100.0,
    )

    metric_text = " ".join(lbl.text() for lbl in panel.findChildren(QLabel))
    assert "MPa" in metric_text
    assert "31.5" in metric_text  # 31.49 MPa target

    _set(fresh_prefs, "imperial")
    imperial_text = " ".join(lbl.text() for lbl in panel.findChildren(QLabel))
    assert "psi" in imperial_text, "panel did not re-render in imperial units"
    assert f"{31.49 * 145.038:.1f}" in imperial_text  # converted target
