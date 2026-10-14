"""Audit C02/C04/C09/C10/C14/C15: BRE 331 §§5.1, 6, 9 and 10."""
from dataclasses import replace
import math

import pytest

from concrete_mix import design_mix_simple
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.doe_trial import calculate_doe_trial_batches, evaluate_doe_trial
from concrete_mix.codes.tables.doe_tables import get_fine_aggregate_proportion
from concrete_mix.engine.target_strength import calculate_target_strength
from concrete_mix.models.materials import Cement, CementType, FineAggregate
from concrete_mix.models.mix_input import MixDesignInput


def design(**kwargs):
    params = dict(code="doe", target_strength_mpa=30, slump_mm=20,
                  fine_agg_pct_passing_600um=60)
    params.update(kwargs)
    return design_mix_simple(**params)


@pytest.mark.parametrize("fc,n,s,expected_s", [
    (30, None, None, 8), (30, None, 1, 8), (30, 10, 1, 8),
    (30, 19, 12, 8), (30, 20, 1, 4), (30, 30, 1, 4),
    (30, 20, 6, 6), (15, 19, 1, 6), (15, 20, 1, 3),
])
@pytest.mark.parametrize("has_data", [False, True])
def test_statistical_minima_and_target_entry_points(fc, n, s, expected_s, has_data):
    """§5.1: record count governs, with ramps retained below fc=20."""
    result = design(target_strength_mpa=fc, num_test_cubes=n,
                    std_deviation=s, has_production_data=has_data)
    target = calculate_target_strength("doe", fc, num_test_cubes=n,
                                       std_deviation=s, has_production_data=has_data)
    direct = DOEMixDesign().calculate_target_mean_strength(fc, std_dev=s,
                                                          num_test_cubes=n)
    expected = math.ceil(fc + 1.64 * expected_s)
    assert target.standard_deviation_mpa == expected_s
    assert target.target_mean_strength_mpa == result.target_mean_strength_mpa == direct == expected
    assert next(step for step in result.steps if step.step_number == 1).result == expected_s


@pytest.mark.parametrize("n", [None, 10, 30])
def test_known_margin_has_same_rounding_in_both_paths(n):
    result = design(num_test_cubes=n, std_deviation=1, margin_mpa=10.25)
    target = calculate_target_strength("doe", 30, num_test_cubes=n,
                                       std_deviation=1, margin_mpa=10.25)
    assert result.target_mean_strength_mpa == target.target_mean_strength_mpa == 41
    assert target.standard_deviation_mpa is None


@pytest.mark.parametrize("scm", [None, "fly_ash", "ggbfs"])
@pytest.mark.parametrize("min_binder", [None, 450])
def test_matching_trial_preserves_binder_and_figure6_basis(scm, min_binder):
    params = dict(num_test_cubes=30, min_cement_kg=min_binder)
    if scm:
        params.update(scm_type=scm, scm_replacement_percent=30)
    result = design(**params)
    ev = evaluate_doe_trial(result, measurements={
        "cube_strength_mpa": result.target_mean_strength_mpa,
        "actual_water_per_m3": result.water_kg, "measured_slump_mm": 20,
    })
    revised = ev["revised"]["per_m3"]
    assert revised["cement"] == pytest.approx(result.cement_kg)
    assert revised["scm"] == pytest.approx(result.scm_kg)
    binder = result.cement_kg + (0.3 if scm == "fly_ash" else 1) * result.scm_kg
    assert ev["strength"]["B_prime"] == round(result.water_kg / binder, 2)
    assert ev["strength"]["D"] == ev["strength"]["B_prime"]
    assert ev["verdict"]["decision"] == "minor"
    if scm == "fly_ash":
        ratio = result.water_kg / (revised["cement"] + revised["scm"])
        expected_fine = get_fine_aggregate_proportion(
            nmsa=20, wc_ratio=ratio, pct_passing_600um=60, workability_class=1)
        assert ev["revised"]["figure6_ratio"] == pytest.approx(ratio)
        assert ev["revised"]["fine_proportion_pct"] == pytest.approx(expected_fine)


@pytest.mark.parametrize("scm", ["fly_ash", "ggbfs"])
def test_scm_feedback_uses_actual_free_water_and_strength_denominator(scm):
    result = design(scm_type=scm, scm_replacement_percent=30, num_test_cubes=30)
    actual = result.water_kg + 10
    weak = evaluate_doe_trial(result, measurements={
        "cube_strength_mpa": result.target_mean_strength_mpa - 8,
        "actual_water_per_m3": actual,
    })
    denominator = result.cement_kg + (0.3 if scm == "fly_ash" else 1) * result.scm_kg
    assert weak["strength"]["B_prime"] == round(actual / denominator, 2)
    assert weak["strength"]["D"] < weak["strength"]["B_prime"]


def test_pfa_durability_cap_is_on_combined_binder():
    result = design(scm_type="fly_ash", scm_replacement_percent=30,
                    w_c_ratio=0.4, num_test_cubes=30)
    ev = evaluate_doe_trial(result, measurements={"cube_strength_mpa": 70})
    assert ev["revised"]["combined_water_binder_ratio"] <= 0.4 + 0.005
    # Equivalent strength ratio may exceed the combined-ratio cap.
    assert ev["strength"]["D"] > 0.4


@pytest.mark.parametrize("rd", [None, 2.4])
@pytest.mark.parametrize("air", [0, 4])
def test_density_uses_design_item42_including_combined_rd_and_air(rd, air):
    result = design(fine_agg_sg=2.4, coarse_agg_sg=2.8,
                    aggregate_relative_density_ssd=rd, air_pct=air)
    density = next(step.result for step in reversed(result.steps)
                   if step.step_number in (9, 9.1))
    for candidate in (result, replace(result, steps=())):
        ev = evaluate_doe_trial(candidate, inp=result._input,
                                measurements={"measured_density_kg_m3": density})
        assert ev["density"]["assumed"] == density
        assert ev["density"]["factor"] == 1
        assert ev["density"]["corrected_per_m3"]["cement"] == result.cement_kg


def test_surface_wet_schedule_increases_masses_and_preserves_free_water():
    result = design(fine_agg_absorption=2, fine_agg_moisture=7,
                    coarse_agg_absorption=1, coarse_agg_moisture=3)
    ssd = calculate_doe_trial_batches(result)["batches"][0]
    wet = calculate_doe_trial_batches(result, moisture_condition="surface_wet")["batches"][0]
    for key, absorption, moisture in (("fine_agg", 2, 7), ("coarse_agg", 1, 3)):
        expected = ssd["per_m3"][key] * (100 + moisture) / (100 + absorption)
        assert wet["per_m3"][key] == pytest.approx(expected, abs=0.06)
        assert wet["batch"][key] == pytest.approx(expected * 0.05, abs=0.06)
    extra_mass = sum(wet["batch"][k] - ssd["batch"][k] for k in ("fine_agg", "coarse_agg"))
    assert wet["added_water_kg"] + extra_mass == pytest.approx(ssd["added_water_kg"])
    assert wet["batch"]["water"] == wet["added_water_kg"]


def test_air_dried_mass_uses_oven_dry_moisture_basis():
    result = design(fine_agg_absorption=10, fine_agg_moisture=5,
                    coarse_agg_absorption=5, coarse_agg_moisture=2)
    entry = calculate_doe_trial_batches(result, moisture_condition="air_dried")["batches"][0]
    for key, absorption, moisture in (("fine_agg", 10, 5), ("coarse_agg", 5, 2)):
        expected = entry["batch"][key] * (100 + moisture) / (100 + absorption)
        assert entry["dry_aggregate_kg"][key] == pytest.approx(expected, abs=0.06)


def test_surface_wet_schedule_rejects_unremovable_excess_water():
    result = design(fine_agg_absorption=1, fine_agg_moisture=90,
                    coarse_agg_absorption=1, coarse_agg_moisture=90)
    with pytest.raises(ValueError, match="exceeds design free water"):
        calculate_doe_trial_batches(result, moisture_condition="surface_wet")


@pytest.mark.parametrize("n", [0, -1, 19.5, float("nan")])
def test_target_record_count_must_be_positive_integer(n):
    with pytest.raises(ValueError, match="positive integer"):
        calculate_target_strength("doe", 30, num_test_cubes=n)


def test_variants_use_combined_design_density():
    result = design(aggregate_relative_density_ssd=2.4, coarse_agg_sg=2.8)
    expected = next(step.result for step in result.steps if step.step_number == 9)
    batches = calculate_doe_trial_batches(result, include_variants=True)["batches"]
    assert len(batches) == 3
    for batch in batches:
        assert sum(batch["per_m3"][key] for key in
                   ("cement", "scm", "water", "fine_agg", "coarse_agg")) == pytest.approx(expected)


@pytest.mark.parametrize("cement,expected", [
    (CementType.GRADE_32_5R, "42.5"), (CementType.GRADE_42_5R, "42.5"),
    (CementType.GRADE_42_5N, "42.5"), (CementType.GRADE_52_5N, "52.5"),
    (CementType.OPC_53, "52.5"),
])
def test_explicit_ghana_cement_class_mapping(cement, expected):
    inp = MixDesignInput(code="doe", target_strength_mpa=30, slump_mm=20,
                         cement=Cement(type=cement),
                         fine_aggregate=FineAggregate(pct_passing_600um=60))
    assert DOEMixDesign._map_cement_class(inp) == expected
    result = DOEMixDesign().design(inp)
    ref = next(step for step in result.steps if step.step_number == 4)
    assert ref.result == (48 if expected == "52.5" else 42)
    if cement == CementType.GRADE_32_5R:
        assert any("not a conservative" in warning for warning in result.warnings)
