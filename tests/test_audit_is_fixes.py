"""Independent IS regressions for audit C03/C06/C07/C08.

Sources: IS 10262:2019 §§5.1.1–5.1.2, 5.4.1, 5.5.1–5.5.2,
5.7–5.8, 6.2.4–6.2.9, 9.6.1; Annexes B-7 and C-7.
"""

from dataclasses import replace

import pytest

from concrete_mix.codes.is10262 import IS10262MixDesign, calculate_is10262_trial_mixes
from concrete_mix.models.materials import Admixture, CoarseAggregate, SCM, SCMType
from concrete_mix.models.mix_input import MixDesignInput


def _input(**kwargs):
    defaults = dict(code="is10262", target_strength_mpa=30.0, w_c_ratio=0.45)
    defaults.update(kwargs)
    return MixDesignInput(**defaults)


def _step(result, description):
    return next(s for s in result.steps if s.description == description)


@pytest.mark.parametrize("selected_ratio", [0.49, 0.50, 0.60])
def test_effective_water_rejected_regardless_of_selection_branch(selected_ratio):
    """§5.1.1 note: below/equal/above initial cap must all check final water."""
    inp = _input(exposure_class="moderate", w_c_ratio=selected_ratio,
                 admixture_water_kg=5.0)
    with pytest.raises(ValueError, match="Effective water-cement ratio.*durability maximum"):
        IS10262MixDesign().design(inp)


@pytest.mark.parametrize("kwargs", [
    dict(target_strength_mpa=70.0, w_c_ratio=0.45, exposure_class="severe"),
    dict(coarse_aggregate=CoarseAggregate(nominal_max_size_mm=80),
         mass_concrete=True, w_c_ratio=0.45, exposure_class="severe"),
    dict(concrete_type="plain", w_c_ratio=0.60, exposure_class="moderate"),
])
def test_effective_water_check_covers_other_is_routes(kwargs):
    with pytest.raises(ValueError, match="Effective water-cement ratio"):
        IS10262MixDesign().design(_input(admixture_water_kg=5.0, **kwargs))


@pytest.mark.parametrize("scms", [(), (SCM(replacement_percent=30.0),)])
def test_effective_water_with_headroom_is_accepted(scms):
    inp = _input(exposure_class="moderate", admixture_water_kg=5.0, scms=scms)
    result = IS10262MixDesign().design(inp)
    effective = _step(result, "Effective water-cement ratio (incl. admixture water)")
    assert effective.result == pytest.approx(
        (effective.inputs["water"] + 5.0) / effective.inputs["cementitious"]
    )
    assert effective.result < 0.50


def test_effective_water_check_uses_final_raised_binder():
    """§5.4.1: the preliminary increase provides real durability headroom."""
    inp = _input(exposure_class="moderate", w_c_ratio=0.50,
                 admixture_water_kg=5.0, scms=(SCM(replacement_percent=30.0),))
    result = IS10262MixDesign().design(inp)
    assert _step(result, "Effective water-cement ratio (incl. admixture water)").result < 0.50


@pytest.mark.parametrize("route", ["ordinary", "high_strength", "mass"])
@pytest.mark.parametrize("scm_type,percent,sg", [
    (SCMType.FLY_ASH, 30.0, 2.2),
    (SCMType.GGBFS, 40.0, 2.9),
])
@pytest.mark.parametrize("with_input", [True, False])
def test_trial_variants_deliver_labelled_binder_ratio(route, scm_type, percent, sg, with_input):
    """§5.8: never reapply §5.4.1's preliminary bump to an actual trial ratio."""
    kwargs = dict(scms=(SCM(type=scm_type, replacement_percent=percent,
                           specific_gravity=sg),))
    if route == "high_strength":
        kwargs.update(target_strength_mpa=70.0, w_c_ratio=0.30)
    elif route == "mass":
        kwargs.update(mass_concrete=True,
                      coarse_aggregate=CoarseAggregate(nominal_max_size_mm=80))
    inp = _input(**kwargs)
    result = IS10262MixDesign().design(inp)
    # Preserve base-design policy: Annex B increases fly-ash binder once;
    # ordinary GGBS Annex C does not; high-strength/mass keep their own rule.
    bumps = [s for s in result.steps if s.description ==
             "Cementitious increase (high mineral dosage)"]
    expected_bump = route != "ordinary" or scm_type == SCMType.FLY_ASH
    assert len(bumps) == int(expected_bump)
    if bumps:
        assert bumps[0].result == pytest.approx(
            bumps[0].inputs["cementitious_before"] * 1.10
        )
    trials = calculate_is10262_trial_mixes(result, inp if with_input else None)["trials"]
    for trial, factor in zip(trials[2:], (0.90, 1.10)):
        requested = round(result.w_c_ratio * factor, 2)
        binder = trial["cement_kg"] + trial["scm_kg"]
        assert trial["water_kg"] == trials[1]["water_kg"]
        assert trial["w_c_ratio"] == requested
        # Two independently rounded 0.1 kg constituent masses: ≤0.1 kg error.
        assert binder == pytest.approx(trial["water_kg"] / requested, abs=0.100001)
        assert trial["water_kg"] / binder == pytest.approx(requested, abs=0.0002)
        # Without material inputs only the whole-kg reported split is known.
        expected_share = (percent / 100.0 if with_input else
                          result.scm_kg / result.total_cementitious_kg)
        assert trial["scm_kg"] / binder == pytest.approx(expected_share, abs=0.0002)


@pytest.mark.parametrize("high_strength,base_fraction", [(False, 0.62), (True, 0.66)])
@pytest.mark.parametrize("placing,reduction", [
    ("chute", None), ("pump", None), ("pump", 0.0), ("pump", 3.0),
])
@pytest.mark.parametrize("override", [None, 0.60])
def test_trial_variants_preserve_placement_and_fraction_override(
    high_strength, base_fraction, placing, reduction, override
):
    """Independent §5.5.1 slope and §5.5.2/§6.2.7 pump readout."""
    inp = _input(target_strength_mpa=70.0 if high_strength else 30.0,
                 w_c_ratio=0.30 if high_strength else 0.45,
                 placing_method=placing, pump_ca_reduction_percent=reduction,
                 ca_volume_fraction_override=override)
    result = IS10262MixDesign().design(inp)
    base = override if override is not None else base_fraction
    base_ratio = 0.30 if high_strength else 0.50
    cut = (5.0 if high_strength else 10.0) if reduction is None else reduction
    trials = calculate_is10262_trial_mixes(result, inp)["trials"]
    for trial in trials[2:]:
        expected = round(base + (base_ratio - trial["w_c_ratio"]) * 0.2, 3)
        if placing == "pump":
            expected = round(expected * (1.0 - cut / 100.0), 3)
        coarse_volume = trial["coarse_agg_kg"] / (inp.coarse_aggregate.specific_gravity * 1000)
        fine_volume = trial["fine_agg_kg"] / (inp.fine_aggregate.specific_gravity * 1000)
        assert coarse_volume / (coarse_volume + fine_volume) == pytest.approx(expected, abs=0.00005)


@pytest.mark.parametrize("reduction", [None, 0.0, 3.0])
def test_mass_trial_pump_uses_only_explicit_reduction(reduction):
    """§9: no tabulated pump cut; preserve an explicit project assumption."""
    inp = _input(mass_concrete=True, placing_method="pump",
                 coarse_aggregate=CoarseAggregate(nominal_max_size_mm=80),
                 pump_ca_reduction_percent=reduction)
    result = IS10262MixDesign().design(inp)
    baseline = _step(result, "Coarse aggregate proportion").inputs["ca_fraction_base"]
    for trial in calculate_is10262_trial_mixes(result, inp)["trials"][2:]:
        expected = round(baseline + (0.50 - trial["w_c_ratio"]) * 0.2, 3)
        if reduction is not None:
            expected = round(expected * (1 - reduction / 100), 3)
        coarse = trial["coarse_agg_kg"] / inp.coarse_aggregate.specific_gravity
        fine = trial["fine_agg_kg"] / inp.fine_aggregate.specific_gravity
        assert coarse / (coarse + fine) == pytest.approx(expected, abs=0.00005)


MULTI_SCMS = (
    SCM(type=SCMType.FLY_ASH, replacement_percent=20.0, specific_gravity=2.2),
    SCM(type=SCMType.GGBFS, replacement_percent=40.0, specific_gravity=2.9),
)


@pytest.mark.parametrize("minimum_governs", [False, True])
def test_multiple_scm_design_is_order_independent_and_closes_yield(minimum_governs):
    """§5.7: sum each constituent's mass/(SG×1000), not the first SG."""
    inp = _input(scms=MULTI_SCMS, admixture=Admixture(dosage_percent=1.0))
    if minimum_governs:
        inp = replace(inp, w_c_ratio=0.55, exposure_class="mild",
                      admixture=Admixture(dosage_percent=1.0, water_reduction_percent=35.0))
    result = IS10262MixDesign().design(inp)
    if minimum_governs:
        assert _step(result, "Minimum cementitious check (IS 456 Tables 5–6)").result == 300.0
    reversed_result = IS10262MixDesign().design(replace(inp, scms=tuple(reversed(inp.scms))))
    assert result.cement_kg == reversed_result.cement_kg
    assert result.scm_kg == reversed_result.scm_kg
    assert result.fine_aggregate_kg == reversed_result.fine_aggregate_kg
    assert result.coarse_aggregate_kg == reversed_result.coarse_aggregate_kg

    cement = _step(result, "Cement content").result
    scm = _step(result, "SCM content").result
    water = _step(result, "Water content (before admixture reduction)").result
    if inp.admixture.water_reduction_percent > 0:
        water = _step(result, "Admixture water reduction").result
    fine = _step(result, "Fine aggregate proportion").result
    coarse = _step(result, "Coarse aggregate proportion").result
    admixture = _step(result, "Admixture content").result
    # Independent weighted constituent volumes, using the ledger's unrounded masses.
    volume = (cement / (inp.cement.specific_gravity * 1000)
              + scm * (1/3) / (2.2 * 1000)
              + scm * (2/3) / (2.9 * 1000)
              + water / 1000
              + fine / (inp.fine_aggregate.specific_gravity * 1000)
              + coarse / (inp.coarse_aggregate.specific_gravity * 1000)
              + admixture / (inp.admixture.specific_gravity * 1000)
              + result.air_volume_percent / 100)
    assert volume == pytest.approx(1.0, abs=1e-12)
    assert not any("Total absolute volume" in warning for warning in result.warnings)


def test_multiple_scm_trial_variants_close_yield_and_are_order_independent():
    inp = _input(scms=MULTI_SCMS, admixture=Admixture(dosage_percent=1.0),
                 placing_method="pump")
    designer = IS10262MixDesign()
    result = designer.design(inp)
    trials = calculate_is10262_trial_mixes(result, inp)["trials"]
    reversed_inp = replace(inp, scms=tuple(reversed(inp.scms)))
    reversed_trials = calculate_is10262_trial_mixes(
        designer.design(reversed_inp), reversed_inp
    )["trials"]
    assert trials == reversed_trials
    for trial in trials[2:]:
        volume = (trial["cement_kg"] / (inp.cement.specific_gravity * 1000)
                  + trial["scm_kg"] / 3 / (2.2 * 1000)
                  + trial["scm_kg"] * 2 / 3 / (2.9 * 1000)
                  + trial["water_kg"] / 1000
                  + trial["fine_agg_kg"] / (inp.fine_aggregate.specific_gravity * 1000)
                  + trial["coarse_agg_kg"] / (inp.coarse_aggregate.specific_gravity * 1000)
                  + trial["admixture_kg"] / (inp.admixture.specific_gravity * 1000)
                  + result.air_volume_percent / 100)
        # Four 0.1 kg masses and a 0.01 kg admixture mass are reported.
        assert volume == pytest.approx(1.0, abs=0.0001)
