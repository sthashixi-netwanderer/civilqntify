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
    assert result.target_mean_strength_mpa == pytest.approx(38.25)
    assert result.standard_deviation_mpa == pytest.approx(5.0)
    assert result.margin_mpa == pytest.approx(8.25)
    assert "Higher value" in result.formula
    assert "Tables 1" in result.reference


def test_aci_with_production_data_uses_statistical_formula():
    result = calculate_target_strength(
        "aci211",
        25.0,
        has_production_data=True,
    )

    assert result.target_mean_strength_mpa == pytest.approx(30.9, abs=0.1)
    assert result.standard_deviation_mpa == pytest.approx(4.0)
    assert result.margin_mpa == pytest.approx(5.9, abs=0.1)
    assert "1.34" in result.formula


def test_aci_without_production_data_uses_table():
    result = calculate_target_strength(
        "aci211",
        25.0,
        has_production_data=False,
    )

    assert result.target_mean_strength_mpa == pytest.approx(33.5, abs=0.1)
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
    assert line_a.target_mean_strength_mpa == pytest.approx(38.12)
    assert line_b.standard_deviation_mpa == pytest.approx(4.0)
    assert line_b.target_mean_strength_mpa == pytest.approx(31.56)
    assert "Line A" in line_a.formula
    assert "Line B" in line_b.formula


def test_structural_strength_minimum_enforced_across_standards():
    """Verify all standards reject non-structural characteristic strength < 25 MPa."""
    for standard in ("is10262", "aci211", "doe"):
        with pytest.raises(ValueError, match="fc ≥ 25 MPa"):
            calculate_target_strength(standard, 20.0)


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
