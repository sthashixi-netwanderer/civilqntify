"""Tests for standard-based target-strength calculations and form modes."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from concrete_mix.engine.target_strength import (
    TargetStrengthResult,
    calculate_target_strength,
)


def test_is10262_uses_higher_target_strength_formula():
    result = calculate_target_strength("is10262", 30.0)

    assert isinstance(result, TargetStrengthResult)
    # max(30 + 1.65×5, 30 + 6.5) = 38.25 → 39 MPa (ceiled, IS 10262 Cl. 4.2)
    assert result.target_mean_strength_mpa == pytest.approx(39)
    assert result.standard_deviation_mpa == pytest.approx(5.0)
    assert result.margin_mpa == pytest.approx(9.0)
    assert "Higher value" in result.formula
    assert "Tables 1" in result.reference


def test_aci_with_production_data_uses_statistical_formula():
    result = calculate_target_strength(
        "aci211",
        25.0,
        has_production_data=True,
    )

    # max(25 + 1.34×4, 25 + 2.33×4 − 3.45) = 30.87 → 31 (up to whole MPa)
    assert result.target_mean_strength_mpa == pytest.approx(31, abs=0.01)
    assert result.standard_deviation_mpa == pytest.approx(4.0)
    assert result.margin_mpa == pytest.approx(6.0, abs=0.01)
    assert "1.34" in result.formula


def test_aci_without_production_data_uses_table():
    result = calculate_target_strength(
        "aci211",
        25.0,
        has_production_data=False,
    )

    # ACI 318 Table 26.4.3.1(b): 33.27 → 34 (up to whole MPa, app policy)
    assert result.target_mean_strength_mpa == pytest.approx(34, abs=0.01)
    assert result.standard_deviation_mpa is None
    assert "Table 26.4.3.1" in result.formula


def test_doe_uses_defectives_and_number_of_test_cubes():
    line_a = calculate_target_strength(
        "doe",
        25.0,
        defective_percent=5.0,
        num_test_cubes=19,
    )
    line_b = calculate_target_strength(
        "doe",
        25.0,
        defective_percent=5.0,
        num_test_cubes=20,
    )

    assert line_a.standard_deviation_mpa == pytest.approx(8.0)
    # 25 + 1.64×8 = 38.12 → 39 (C2 target mean rounded up to whole N/mm²)
    assert line_a.target_mean_strength_mpa == pytest.approx(39.0)
    assert line_b.standard_deviation_mpa == pytest.approx(4.0)
    # 25 + 1.64×4 = 31.56 → 32 (C2 rounded up)
    assert line_b.target_mean_strength_mpa == pytest.approx(32.0)
    assert "Line A" in line_a.formula
    assert "Line B" in line_b.formula


def test_doe_known_margin_bypasses_k_s_n():
    """Margin M known → fm = fc + M rounded up; no k/s/n needed."""
    result = calculate_target_strength("doe", 30.0, margin_mpa=10.0)

    assert result.target_mean_strength_mpa == pytest.approx(40.0)
    assert result.standard_deviation_mpa is None
    assert result.margin_mpa == pytest.approx(10.0)
    assert "user-specified M" in result.formula


def test_doe_known_margin_rounds_up():
    """15.68 → ceil(30 + 15.68) = 46, like the C2 convention."""
    result = calculate_target_strength("doe", 30.0, margin_mpa=15.68)

    assert result.target_mean_strength_mpa == pytest.approx(46.0)


def test_doe_known_margin_must_be_positive():
    """A zero/negative margin is rejected instead of silently used."""
    with pytest.raises(ValueError, match="positive"):
        calculate_target_strength("doe", 30.0, margin_mpa=0.0)


def test_no_app_floor_any_standard():
    """No 25 MPa floor in any code; low grades design with standard rules."""
    is20 = calculate_target_strength("is10262", 20.0)
    assert is20.standard_deviation_mpa == pytest.approx(4.0)
    # max(20 + 1.65×4, 20 + 5.5) = 26.6 → 27 MPa (ceiled, IS 10262 Cl. 4.2)
    assert is20.target_mean_strength_mpa == pytest.approx(27)
    aci20 = calculate_target_strength("aci211", 20.0)
    # max(20 + 1.34×4, 20 + 2.33×4 − 3.45) = 25.87 → 26 (up to whole MPa)
    assert aci20.target_mean_strength_mpa == pytest.approx(26)
    # DOE M20: Line B by default (n=20) → s = 0.2×20 = 4.0, M = 6.56,
    # fm = 26.56 → 27 (C2 rounded up).
    doe20 = calculate_target_strength("doe", 20.0)
    assert doe20.standard_deviation_mpa == pytest.approx(4.0)
    assert doe20.target_mean_strength_mpa == pytest.approx(27.0)


def test_exposure_gates_still_guard_low_grades():
    """The real durability gates (not the removed floor) block bad combos."""
    from concrete_mix.codes.aci211 import ACI211MixDesign
    from concrete_mix.codes.is10262 import IS10262MixDesign
    from concrete_mix.models.mix_input import MixDesignInput

    # IS M20 under severe exposure violates the M30 minimum (IS 456 Table 5).
    with pytest.raises(ValueError, match="minimum grade M30"):
        IS10262MixDesign().design(MixDesignInput(
            code="is10262", target_strength_mpa=20.0, slump_mm=75.0,
            exposure_class="severe", concrete_type="reinforced"))
    # ACI M20 under F2 violates the 31.0 MPa minimum (Table 4.7.3b).
    with pytest.raises(ValueError, match="minimum 31.0 MPa"):
        ACI211MixDesign().design(MixDesignInput(
            code="aci211", target_strength_mpa=20.0, slump_mm=75.0,
            air_entrained=True, freezing_exposure_class="F2"))


def test_target_result_contains_no_mix_proportions():
    result = calculate_target_strength("is10262", 25.0)

    assert not hasattr(result, "mix_ratio")
    assert not hasattr(result, "cement_kg")
    assert not hasattr(result, "water_kg")


@pytest.fixture()
def qt_app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_mix_design_tab_contains_mode_dropdown_and_no_target_subtab(qt_app):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()

    # PSD runs FIRST — its derived parameters feed the mix-design form.
    assert tab._left_tabs.tabText(0) == "PSD"
    assert tab._left_tabs.tabText(1) == "Mix Design"
    assert tab._left_tabs.count() == 2
    assert tab._left_tabs.currentIndex() == 0  # PSD is the default view
    assert tab._result_stack.currentWidget() is tab._psd_result_panel
    assert tab.mode_combo.currentData() == "mix_design"
    assert tab.calc_btn.text().strip() == "Calculate Mix Design"


def test_target_mode_disables_mix_inputs_and_shows_strength_result(qt_app):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))
    # The right panel follows the active left subtab; assert on Mix Design.
    tab._left_tabs.setCurrentIndex(tab._mixdesign_idx)

    assert tab.code_combo.isEnabled()
    assert tab.mode_combo.isEnabled()
    assert tab.strength_spin.isEnabled()
    assert not tab.slump_spin.isEnabled()
    assert not tab.nmsa_combo.isEnabled()
    assert not tab.volume_spin.isEnabled()
    assert not tab._grp_step2.isEnabled()
    assert not tab._grp_step3.isEnabled()
    assert not tab.prod_data_check.isEnabled()  # IS has no extra target input
    assert tab._result_stack.currentWidget() is tab._target_strength_panel
    assert tab.calc_btn.text().strip() == "Calculate Target Strength"


def test_target_mode_enables_only_standard_specific_variability_inputs(qt_app):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))

    tab.code_combo.setCurrentIndex(tab.code_combo.findData("aci211"))
    assert tab.prod_data_check.isEnabled()
    assert not tab.defective_pct_spin.isEnabled()
    assert not tab.n_cubes_spin.isEnabled()

    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    assert tab.defective_pct_spin.isEnabled()
    assert tab.n_cubes_spin.isEnabled()
    assert tab.std_dev_display.isEnabled()
    assert not tab.age_combo.isEnabled()


def test_switching_back_to_mix_design_reenables_mix_inputs(qt_app):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("mix_design"))
    tab._left_tabs.setCurrentIndex(tab._mixdesign_idx)

    assert tab._grp_step2.isEnabled()
    assert tab._grp_step3.isEnabled()
    assert tab.slump_spin.isEnabled()
    assert tab.volume_spin.isEnabled()
    assert tab._result_stack.currentWidget() is tab._result_panel
    assert tab.calc_btn.text().strip() == "Calculate Mix Design"


def test_margin_known_checkbox_grays_out_k_s_n(qt_app):
    """Checking 'Margin is known' deactivates defectives/n/std-dev (DOE)."""
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))

    assert tab.defective_pct_spin.isEnabled()
    assert tab.n_cubes_spin.isEnabled()
    assert not tab.margin_spin.isEnabled()

    tab.margin_known_check.setChecked(True)
    assert not tab.defective_pct_spin.isEnabled()
    assert not tab.n_cubes_spin.isEnabled()
    assert not tab.std_dev_display.isEnabled()
    assert tab.margin_spin.isEnabled()

    tab.margin_known_check.setChecked(False)
    assert tab.defective_pct_spin.isEnabled()
    assert tab.n_cubes_spin.isEnabled()
    assert not tab.margin_spin.isEnabled()


def test_margin_known_checkbox_hidden_for_other_codes(qt_app):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("is10262"))
    assert not tab.margin_known_check.isVisible()
    assert not tab.margin_spin.isVisible()


def test_target_strength_uses_known_margin(qt_app):
    """With the box checked, the target is fc + M (DOE §4.4, C2)."""
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))
    tab.strength_spin.setValue(30.0)
    tab.margin_known_check.setChecked(True)
    tab.margin_spin.setValue(12.0)
    tab._calculate_target_strength()

    assert tab._last_target_result.target_mean_strength_mpa == pytest.approx(42.0)
    assert tab._last_target_result.standard_deviation_mpa is None
