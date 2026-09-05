"""Tests for DOE (BRE 331:1997 §6) trial-mix batch schedule and evaluation."""

from __future__ import annotations

import math

import pytest

from concrete_mix import design_mix_simple
from concrete_mix.codes.doe_trial import (
    MINOR_ADJUSTMENT_WC_LIMIT,
    calculate_doe_trial_batches,
    evaluate_doe_trial,
)
from concrete_mix.codes.tables.doe_tables import wc_ratio_from_strength


def _make_design(**overrides):
    """BRE 331:1997 §7.1 Example 1 basis (unrestricted design).

    fc 30 N/mm², 2.5% defectives (k=1.96), s=8 → target mean 46;
    class 42.5 cement, uncrushed aggregates, SG 2.6, 20 mm NMSA,
    slump 10–30 mm (class 1), 70% passing 600 µm.
    The app's digitised Figure 6 reads 27.7% fine (standard: 27%), so
    the fine/coarse split differs from the printed example by that read;
    the C1–C4 chain must match the standard exactly.
    """
    params = dict(
        code="doe",
        target_strength_mpa=30.0,
        characteristic_strength_mpa=30.0,
        slump_mm=20.0,
        nmsa=20,
        cement_type="OPC_43",
        fine_agg_sg=2.6,
        coarse_agg_sg=2.6,
        aggregate_shape="gravel",
        coarse_agg_type="uncrushed",
        fine_agg_type="uncrushed",
        fine_agg_pct_passing_600um=70.0,
        defective_percent=2.5,
        std_deviation=8.0,
    )
    params.update(overrides)
    return design_mix_simple(**params)


# ----------------------------------------------------------------------
# §6.1 batch schedule
# ----------------------------------------------------------------------

def test_s71_stage123_chain_reproduces_standard():
    """C1–C3: target 46, w/c 0.47, water 160, cement 340 (BRE §7.1)."""
    res = _make_design()
    assert res.target_mean_strength_mpa == 46.0
    assert res.w_c_ratio == pytest.approx(0.47)
    assert res.water_kg == pytest.approx(160.0)
    assert res.cement_kg == pytest.approx(340.0)


def test_batch_scaling_matches_s71_example():
    """0.05 m³ batch: cement 17.0 and water 8.0 exactly (§7.1); the
    aggregate split sums to the C4 total scaled, with the standard's
    half-down rounding convention at the first decimal."""
    res = _make_design()
    sched = calculate_doe_trial_batches(res, volume_m3=0.05)
    assert len(sched["batches"]) == 1
    b = sched["batches"][0]
    assert b["batch"]["cement"] == pytest.approx(17.0, abs=0.05)
    assert b["batch"]["water"] == pytest.approx(8.0, abs=0.05)
    # C4 total aggregate 1900 kg/m³ → 95.0 kg at 0.05 m³ (±0.1 from the
    # independent 1-dp rounding of the two aggregate rows, exactly like
    # the standard's own example: 25.7 + 69.2 = 94.9).
    total_agg_batch = b["batch"]["fine_agg"] + b["batch"]["coarse_agg"]
    assert total_agg_batch == pytest.approx(95.0, abs=0.1)
    assert b["per_m3"]["cement"] == pytest.approx(res.cement_kg, abs=0.1)


def test_oven_dry_batching_matches_s71_procedure():
    """Oven-dry batching: ×100/(100+A) and absorption water added (§6.1).

    With fine A=2% and coarse A=1% the §7.1 example reports absorption
    water 1.2 kg for a 50-litre batch; the app follows the same
    mass-chain from the reported batch masses.
    """
    res = _make_design(
        fine_agg_absorption=2.0,
        coarse_agg_absorption=1.0,
    )
    sched = calculate_doe_trial_batches(
        res, volume_m3=0.05, moisture_condition="oven_dry",
    )
    b = sched["batches"][0]
    dry = b["dry_aggregate_kg"]
    # Dry masses below SSD masses, on the ×100/(100+A) chain.
    assert 0 < dry["fine_agg"] < b["batch"]["fine_agg"]
    assert 0 < dry["coarse_agg"] < b["batch"]["coarse_agg"]
    assert dry["fine_agg"] == pytest.approx(
        b["batch"]["fine_agg"] * 100.0 / 102.0, abs=0.06
    )
    assert dry["coarse_agg"] == pytest.approx(
        b["batch"]["coarse_agg"] * 100.0 / 101.0, abs=0.06
    )
    # Water added at the mixer = design water + absorption water.
    assert b["absorption_water_kg"] == pytest.approx(1.2, abs=0.1)
    assert b["added_water_kg"] == pytest.approx(8.0 + 1.2, abs=0.1)
    # Pre-soak guidance is surfaced.
    assert any("soak" in n.lower() for n in b["notes"])


def test_surface_wet_deducts_free_water():
    res = _make_design(
        fine_agg_absorption=1.0, fine_agg_moisture=3.0,
        coarse_agg_absorption=0.5, coarse_agg_moisture=1.5,
    )
    sched = calculate_doe_trial_batches(
        res, volume_m3=0.05, moisture_condition="surface_wet",
    )
    b = sched["batches"][0]
    assert b["free_water_kg"] > 0
    assert b["added_water_kg"] < 8.0


def test_variant_batches_hold_water_constant():
    """§6 intro: variants share the water content, cement = W ÷ w/c on
    the 5-kg grid (C3), aggregates recomputed via C4/C5."""
    res = _make_design()
    sched = calculate_doe_trial_batches(
        res, volume_m3=0.05, include_variants=True, wc_step=0.05,
    )
    assert len(sched["batches"]) == 3
    lo, hi = sched["batches"][1], sched["batches"][2]
    assert lo["w_c_ratio"] == pytest.approx(round(res.w_c_ratio - 0.05, 2))
    assert hi["w_c_ratio"] == pytest.approx(round(res.w_c_ratio + 0.05, 2))
    for b in (lo, hi):
        assert b["per_m3"]["water"] == pytest.approx(res.water_kg)
        assert b["per_m3"]["cement"] == pytest.approx(
            round(res.water_kg / b["w_c_ratio"] / 5.0) * 5.0
        )
        # C4 holds: cementitious + water + aggregate = design density.
        assert (
            b["per_m3"]["cement"] + b["per_m3"]["water"]
            + b["per_m3"]["fine_agg"] + b["per_m3"]["coarse_agg"]
        ) == pytest.approx(2400.0, abs=0.5)


def test_variant_outside_figure4_range_is_skipped():
    res = _make_design()  # w/c 0.47 → both ±0.05 variants in range.
    sched = calculate_doe_trial_batches(
        res, include_variants=True, wc_step=0.05,
    )
    assert len(sched["batches"]) == 3
    # A very low grade with a tight margin pushes the Figure 4 read to
    # its 0.90 clamp, so the +0.05 variant (0.95) lies outside the chart
    # and is skipped.
    res_low = _make_design(
        target_strength_mpa=8.0, characteristic_strength_mpa=8.0,
        std_deviation=1.0,
    )
    assert res_low.w_c_ratio == pytest.approx(0.89)
    sched2 = calculate_doe_trial_batches(
        res_low, include_variants=True, wc_step=0.05,
    )
    names = [b["name"] for b in sched2["batches"]]
    assert len(names) == 2  # designed + low variant only
    assert any("0.94" in w and "skipped" in w for w in sched2["warnings"])


def test_scm_variants_rejected():
    res = _make_design(
        scm_replacement_percent=30.0, scm_type="fly_ash",
    )
    with pytest.raises(ValueError, match="plain"):
        calculate_doe_trial_batches(res, include_variants=True)


def test_non_ssd_without_input_record_rejected():
    res = _make_design()
    bare = res.__class__(**{f: getattr(res, f) for f in res.__dataclass_fields__})
    # Remove the attached input record.
    try:
        delattr(bare, "_input")
    except AttributeError:
        pass
    with pytest.raises(ValueError, match="input record"):
        calculate_doe_trial_batches(bare, moisture_condition="oven_dry")


# ----------------------------------------------------------------------
# §6.3 evaluation
# ----------------------------------------------------------------------

def test_density_correction_factor():
    """§6.3.2: corrected unit proportions = design × measured/assumed."""
    res = _make_design()
    assumed = evaluate_doe_trial(
        res, measurements={"measured_density_kg_m3": 2400.0,
                           "measured_slump_mm": 20.0},
    )
    # Measured = assumed → factor 1.0, proportions unchanged.
    dn = assumed["density"]
    assert dn["assumed"] == pytest.approx(2400.0)
    assert dn["factor"] == pytest.approx(1.0)
    assert dn["corrected_per_m3"]["cement"] == pytest.approx(res.cement_kg, abs=0.1)

    ev = evaluate_doe_trial(
        res, measurements={"measured_density_kg_m3": 2380.0,
                           "measured_slump_mm": 20.0},
    )
    assert ev["density"]["factor"] == pytest.approx(2380.0 / 2400.0, abs=1e-3)
    assert ev["density"]["corrected_per_m3"]["cement"] == pytest.approx(
        res.cement_kg * 2380.0 / 2400.0, abs=0.1
    )


def test_figure7_inversion_is_self_consistent():
    """D must be the w/c where the trial's shifted Figure 4 curve hits
    the target mean: wc(C, ref50′) = B′ and wc(target, ref50′) = D."""
    res = _make_design()
    ev = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 50.0, "test_age_days": 28},
    )
    st = ev["strength"]
    assert st["A"] == pytest.approx(42.0)  # Table 2, 42.5/uncrushed/28d
    assert st["B"] == pytest.approx(res.w_c_ratio)
    assert st["C"] == pytest.approx(50.0)
    # Round-trip: the shifted curve passes through the trial point.
    assert wc_ratio_from_strength(st["C"], st["ref50_prime"]) == pytest.approx(
        st["B_prime"], abs=0.005
    )
    # ...and D sits at the target mean on that same curve.
    assert wc_ratio_from_strength(
        res.target_mean_strength_mpa, st["ref50_prime"]
    ) == pytest.approx(st["D"], abs=0.005)


def test_over_strength_relaxes_wc_and_under_strength_tightens():
    res = _make_design()
    ev_low = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 50.0},
    )
    ev_high = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 54.0},
    )
    # Stronger trial → higher w/c estimate; weaker trial → lower.
    assert ev_low["strength"]["D"] < ev_high["strength"]["D"]
    # Below target mean: C < 46 must pull w/c down (stronger mix needed).
    ev_weak = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 42.0},
    )
    assert ev_weak["strength"]["D"] < res.w_c_ratio


def test_verdict_thresholds():
    """App policy: |D − B′| ≤ 0.05 → minor; larger → second trial."""
    res = _make_design()
    # C = 50 → D = 0.50 (see §6.3.3 walk-through), Δ ≈ 0.03 → minor.
    ev_minor = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 50.0},
    )
    assert ev_minor["verdict"]["decision"] == "minor"
    assert abs(ev_minor["verdict"]["delta_wc"]) <= MINOR_ADJUSTMENT_WC_LIMIT

    # C = 54 → D ≈ 0.53, Δ ≈ 0.06 → re-trial.
    ev_retrial = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 54.0},
    )
    assert ev_retrial["verdict"]["decision"] == "re_trial"
    assert abs(ev_retrial["verdict"]["delta_wc"]) > MINOR_ADJUSTMENT_WC_LIMIT
    assert "second trial mix" in ev_retrial["verdict"]["text"]


def test_minor_verdict_emits_revised_production_proportions():
    res = _make_design()
    ev = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 50.0,
                           "measured_slump_mm": 20.0},
    )
    rv = ev["revised"]
    assert rv is not None
    assert rv["basis"] == "production"
    pm = rv["per_m3"]
    # C3 at the revised w/c, nearest 5 kg; C4 holds on the design density.
    assert pm["cement"] == pytest.approx(
        round(pm["water"] / rv["w_c_ratio"] / 5.0) * 5.0
    )
    assert (
        pm["cement"] + pm["water"] + pm["fine_agg"] + pm["coarse_agg"]
    ) == pytest.approx(2400.0, abs=0.5)
    assert pm["cement"] > 0 and pm["fine_agg"] > 0 and pm["coarse_agg"] > 0


def test_retrial_verdict_scales_second_trial_batches():
    res = _make_design()
    ev = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 54.0,
                           "measured_density_kg_m3": 2385.0},
    )
    rv = ev["revised"]
    assert rv["basis"] == "second_trial"
    # §6.3.3: recalculated on the updated (measured) density.
    assert rv["density_basis"] == pytest.approx(2385.0)
    assert rv["batch"] is not None
    assert rv["batch"]["cement"] == pytest.approx(
        rv["per_m3"]["cement"] * 0.05, abs=0.1
    )


def test_workability_water_delta_direction():
    """Trial stiffer than specified → Table 3 says add water."""
    res = _make_design()  # class 1 (10–30 mm)
    ev = evaluate_doe_trial(
        res, measurements={"measured_slump_mm": 5.0},  # class 0
    )
    assert ev["workability"]["measured_class"] == 0
    assert ev["workability"]["water_delta_kg_m3"] > 0
    assert any("Table 3" in g for g in ev["workability"]["guidance"])


def test_durability_cap_applied_to_D():
    res = _make_design(w_c_ratio=0.45)  # Item 1.8 max w/c
    # Very strong trial would relax w/c past the durability cap.
    ev = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 60.0},
    )
    assert ev["strength"]["D"] <= 0.45
    assert any("maximum" in w for w in ev["warnings"])


def test_actual_water_shifts_B_prime():
    res = _make_design()
    ev = evaluate_doe_trial(
        res, measurements={"actual_water_kg": 9.0, "volume_m3": 0.05,
                           "cube_strength_mpa": 50.0},
    )
    # 9.0 kg in a 0.05 m³ batch = 180 kg/m³ → B′ = 180/340 ≈ 0.53.
    assert ev["strength"]["B_prime"] == pytest.approx(0.53, abs=0.005)


def test_empty_measurements_rejected():
    res = _make_design()
    with pytest.raises(ValueError, match="measurements"):
        evaluate_doe_trial(res, measurements={})


def test_age_selects_table2_reference():
    res = _make_design()
    ev7 = evaluate_doe_trial(
        res, measurements={"cube_strength_mpa": 35.0, "test_age_days": 7},
    )
    assert ev7["strength"]["A"] == pytest.approx(30.0)  # Table 2 @7d
