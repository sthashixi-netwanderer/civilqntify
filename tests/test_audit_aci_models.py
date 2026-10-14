"""Audit regressions: independent mass/volume and adjustment invariants."""

from dataclasses import replace

import pytest

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.aci_trial import calculate_aci_trial_batches, evaluate_aci_trial
from concrete_mix.codes.tables.aci_tables import interpolate_w_c_ratio
from concrete_mix.models.materials import Admixture, CoarseAggregate, FineAggregate, SCM, SCMType
from concrete_mix.models.mix_input import MixDesignInput


def _input(**kwargs):
    return MixDesignInput(code="aci211", target_strength_mpa=30, **kwargs)


def _design(inp):
    return ACI211MixDesign().design(inp)


def _scm_volume(mass, inp):
    total = sum(s.replacement_percent for s in inp.scms)
    return sum(mass * s.replacement_percent / total / (s.specific_gravity * 1000)
               for s in inp.scms) if total else 0.0


def _volume(pm, inp, air):
    return (pm["water"] / 1000
            + pm["cement"] / (inp.cement.specific_gravity * 1000)
            + _scm_volume(pm["scm"], inp)
            + pm["fine_agg_ssd"] / (inp.fine_aggregate.specific_gravity * 1000)
            + pm["coarse_agg_ssd"] / (inp.coarse_aggregate.specific_gravity * 1000)
            + (pm["admixture"] / (inp.admixture.specific_gravity * 1000)
               if inp.admixture else 0)
            + air / 100)


def _result_masses(result):
    return dict(water=result.water_kg, cement=result.cement_kg, scm=result.scm_kg,
                fine_agg_ssd=result.fine_aggregate_kg,
                coarse_agg_ssd=result.coarse_aggregate_kg,
                admixture=result.admixture_kg or 0)


def _blend():
    return (SCM(type=SCMType.FLY_ASH, specific_gravity=2.2, replacement_percent=30),
            SCM(type=SCMType.GGBFS, specific_gravity=2.9, replacement_percent=30))


@pytest.mark.parametrize("target_paste", [None, 30.0])
def test_multi_scm_order_independent_and_absolute_volume_closes(target_paste):
    inp = _input(scms=_blend(), target_paste_volume_pct=target_paste,
                 admixture=Admixture(dosage_percent=1.5, water_reduction_percent=20))
    result = _design(inp)
    reversed_result = _design(replace(inp, scms=tuple(reversed(inp.scms))))
    assert _result_masses(result) == _result_masses(reversed_result)
    assert _volume(_result_masses(result), inp, result.air_volume_percent) == pytest.approx(1, abs=0.00015)
    expected_paste = (result.water_kg / 1000
                      + result.cement_kg / (inp.cement.specific_gravity * 1000)
                      + _scm_volume(result.scm_kg, inp)) * 100
    paste_step = next(s for s in result.steps if s.step_number == (8.2 if target_paste else 8.1))
    assert paste_step.result == pytest.approx(expected_paste, abs=0.06)
    if target_paste:
        assert expected_paste == pytest.approx(target_paste, abs=0.02)


@pytest.mark.parametrize("air_delta", [-2.0, 0.0, 2.0])
def test_air_direction_both_paths_and_target_air_yield(air_delta):
    inp = _input(air_entrained=True, exposure_class="moderate")
    result = _design(inp)
    measured = result.air_volume_percent + air_delta
    evaluation = evaluate_aci_trial(result, inp, {"measured_air_pct": measured})
    correction = 2.97 * air_delta
    assert evaluation["adjustment_2"]["water_correction_kg_m3"] == pytest.approx(correction, abs=0.05)
    nt = evaluation["next_trial"]
    assert nt["per_m3"]["water"] == pytest.approx(result.water_kg + correction, abs=0.06)
    assert nt["air_basis_pct"] == result.air_volume_percent
    assert _volume(nt["per_m3"], inp, nt["air_basis_pct"]) == pytest.approx(1, abs=0.00015)
    inline = _design(replace(inp, trial_air_pct=measured))
    step = next(s for s in inline.steps if s.step_number == 10.3)
    assert step.inputs["water_correction"] == pytest.approx(correction)


@pytest.mark.parametrize("strength_factor", [0.9, 1.0, 1.1])
@pytest.mark.parametrize("slump_delta", [0, -10])
def test_strength_ledger_applied_at_constant_wcm_with_yield_closure(strength_factor, slump_delta):
    inp = _input(scms=_blend(), admixture=Admixture(dosage_percent=1.5, water_reduction_percent=20))
    result = _design(inp)
    measurements = dict(cube_strength_mpa=result.target_mean_strength_mpa * strength_factor,
                        measured_slump_mm=inp.slump_mm + slump_delta)
    ev = evaluate_aci_trial(result, inp, measurements)
    nt, a1, a3 = ev["next_trial"], ev["adjustment_1"], ev["adjustment_3"]
    pm = nt["per_m3"]
    assert pm["water"] == pytest.approx(a1["re_estimated_water_kg_m3"] + a3["delta_water_kg_m3"], abs=0.11)
    binder = pm["cement"] + pm["scm"]
    assert binder == pytest.approx(a1["re_estimated_water_kg_m3"] / result.w_c_ratio + a3["delta_cement_kg_m3"], abs=0.25)
    assert pm["water"] / binder == pytest.approx(result.w_c_ratio, abs=0.0004)
    assert nt["w_c_ratio"] == pytest.approx(result.w_c_ratio, abs=0.0005)
    assert pm["scm"] / binder == pytest.approx(0.6, abs=0.0003)
    assert _volume(pm, inp, nt["air_basis_pct"]) == pytest.approx(1, abs=0.00015)
    for key, mass in pm.items():
        assert nt["batch"][key] == pytest.approx(mass * 0.05, abs=0.0051)


def test_series_includes_admixture_and_each_scm_volume():
    inp = _input(scms=_blend(), admixture=Admixture(dosage_percent=1.5, water_reduction_percent=20))
    result = _design(inp)
    schedule = calculate_aci_trial_batches(result, inp, include_series=True)
    for series in schedule["series"]:
        pm = series["per_m3"]
        assert pm["water"] == result.water_kg
        assert pm["cement"] + pm["scm"] == pytest.approx(pm["cementitious"], abs=0.11)
        assert pm["scm"] / pm["cementitious"] == pytest.approx(0.6, abs=0.0003)
        assert _volume(pm, inp, result.air_volume_percent) == pytest.approx(1, abs=0.00015)


@pytest.mark.parametrize("strength", [50, 70, 90])
def test_high_strength_boundary_is_explicitly_unverified(strength):
    inp = replace(_input(), target_strength_mpa=strength)
    with pytest.warns(UserWarning, match="Material-specific strength data"):
        result = _design(inp)
    assert any("attainable strength is not established" in w for w in result.warnings)
    assert result.w_c_ratio == 0.34  # Backward-compatible preliminary estimate.


def test_table_boundary_itself_is_valid_and_above_warns():
    assert interpolate_w_c_ratio(48.3, False) == 0.34
    with pytest.warns(UserWarning, match="exceeds"):
        assert interpolate_w_c_ratio(48.31, False) == 0.34
    # An explicit material-specific ratio does not claim a table lookup.
    result = _design(replace(_input(w_c_ratio=0.3), target_strength_mpa=70))
    assert not any("boundary w/cm" in w for w in result.warnings)


@pytest.mark.parametrize("percentages", [(70, 70), (50, 50), (60, 50)])
def test_total_scm_replacement_rejected_before_design(percentages):
    with pytest.raises(ValueError, match="Total SCM replacement"):
        _input(scms=tuple(SCM(replacement_percent=p) for p in percentages))


def test_valid_large_blend_keeps_positive_cement():
    result = _design(_input(scms=(SCM(replacement_percent=49), SCM(replacement_percent=50))))
    assert result.cement_kg > 0
    assert result.scm_kg > 0


@pytest.mark.parametrize("model", [FineAggregate, CoarseAggregate])
@pytest.mark.parametrize("field", ["absorption_percent", "moisture_content_percent"])
@pytest.mark.parametrize("value", [-100, -0.01, float("nan"), float("inf"), -float("inf")])
def test_aggregate_water_rejects_nonphysical_or_nonfinite(model, field, value):
    with pytest.raises(ValueError, match="finite and non-negative"):
        model(**{field: value})


@pytest.mark.parametrize("value", [-1, 0, float("nan"), float("inf"), -float("inf"), 2700])
def test_bulk_density_rejects_nonphysical_or_nonfinite(value):
    with pytest.raises(ValueError, match="bulk density"):
        CoarseAggregate(bulk_density_kg_m3=value)


def test_bulk_density_checks_dry_not_ssd_particle_density():
    with pytest.raises(ValueError, match="dry particle density"):
        CoarseAggregate(absorption_percent=10, bulk_density_kg_m3=2500)
    assert CoarseAggregate(specific_gravity=5, bulk_density_kg_m3=3500).bulk_density_kg_m3 == 3500


@pytest.mark.parametrize("sg", [0, -1, float("nan"), float("inf")])
def test_scm_density_rejected_at_model_boundary(sg):
    with pytest.raises(ValueError, match="SCM specific gravity"):
        SCM(specific_gravity=sg)


def test_dry_ssd_and_surface_wet_moisture_remain_valid_and_mass_conserving():
    for moisture in (0, 1, 6):
        inp = _input(fine_aggregate=FineAggregate(absorption_percent=1, moisture_content_percent=moisture),
                     coarse_aggregate=CoarseAggregate(absorption_percent=1, moisture_content_percent=moisture))
        result = _design(inp)
        pm = calculate_aci_trial_batches(result, inp)["batches"][0]["per_m3"]
        assert pm["total_batched"] == pytest.approx(pm["total_design"], abs=0.02)
