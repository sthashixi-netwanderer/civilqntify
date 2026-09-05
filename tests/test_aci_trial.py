"""Tests for ACI PRC-211.1-22 trial-mix batches and §5.3.10 adjustments.

Ground truth: §9.2.9 (Example 1, Chapter 9) — the fully worked
post-trial batch computation for a 1 ft³ trial batch, converted to the
app's kg/m³ convention (1 lb = 0.45359237 kg, 1 ft³ = 0.028316846592 m³,
1 yd³ = 27 ft³).
"""

from __future__ import annotations

import pytest

from concrete_mix.codes.aci_trial import (
    calculate_aci_trial_batches,
    evaluate_aci_trial,
)
from concrete_mix.models.materials import (
    Cement,
    CoarseAggregate,
    FineAggregate,
)
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult

LB_YD3_TO_KG_M3 = 0.45359237 / 0.764554857984  # 0.5932764
LB_FT3_TO_KG = 0.45359237
FT3_TO_M3 = 0.028316846592
LB_FT3_TO_KG_M3 = 0.45359237 / FT3_TO_M3  # 16.0185


def _example1_input() -> MixDesignInput:
    """§9.2 Example 1 materials (Step 9.2.9 moisture state)."""
    return MixDesignInput(
        code="aci211",
        target_strength_mpa=24.13,  # f'cr 3500 psi
        slump_mm=88.9,  # 3.5 in. (mid of the 3–4 in. target)
        cement=Cement(specific_gravity=3.15),
        fine_aggregate=FineAggregate(
            specific_gravity=2.64, absorption_percent=0.7,
            moisture_content_percent=6.0,
        ),
        coarse_aggregate=CoarseAggregate(
            specific_gravity=2.68, nominal_max_size_mm=40,
            absorption_percent=0.5, moisture_content_percent=2.0,
        ),
        air_entrained=False,
    )
    # Note: Example 1's NMSA is 1.5 in. (38.1 mm); the app's aggregate
    # model admits only tabulated sizes, and NMSA does not enter any of
    # the trial arithmetic under test, so 40 mm stands in.


def _example1_result() -> MixDesignResult:
    """§9.2.8 design per yd³ → kg/m³: water 300, cement 300/0.62,
    CA SSD 1927, FA SSD 1308.2, entrapped air 1%."""
    water = 300.0 * LB_YD3_TO_KG_M3
    cement = (300.0 / 0.62) * LB_YD3_TO_KG_M3
    ca = 1927.0 * LB_YD3_TO_KG_M3
    fa = 1308.2 * LB_YD3_TO_KG_M3
    res = MixDesignResult(
        code_used="ACI PRC-211.1-22",
        target_mean_strength_mpa=24.13,
        w_c_ratio=0.62,
        water_kg=round(water, 2),
        cement_kg=round(cement, 2),
        fine_aggregate_kg=round(fa, 2),
        coarse_aggregate_kg=round(ca, 2),
        air_volume_percent=1.0,
        volume_m3=1.0,
    )
    object.__setattr__(res, "_input", _example1_input())
    return res


# ----------------------------------------------------------------------
# §5.3.9 batch weight summary
# ----------------------------------------------------------------------

def test_batch_summary_free_water_matches_example():
    """§9.2.8: free water ≈ 98 lb/yd³ (28.8 CA + 69.0 FA); water to
    batch = 300 − 98 = 202 lb/yd³ = 7.48 lb/ft³."""
    res = _example1_result()
    sched = calculate_aci_trial_batches(res, volume_m3=FT3_TO_M3)
    b = sched["batches"][0]
    pm = b["per_m3"]
    # Free water on the aggregates (lb/yd³ equivalents).
    total_free = (pm["free_water_fine"] + pm["free_water_coarse"]) / LB_YD3_TO_KG_M3
    assert total_free == pytest.approx(97.6, abs=1.0)  # example rounds to 98
    water_to_batch = pm["water_to_batch"] / LB_YD3_TO_KG_M3
    assert water_to_batch == pytest.approx(202.4, abs=1.0)
    assert water_to_batch == pytest.approx(7.48 * 27, rel=0.01)


def test_batched_aggregate_weights_match_example():
    """§9.2.9.1: CA 72.44 lb/ft³ moist (SSD 71.37), FA 51.00 lb/ft³
    moist (SSD 48.45)."""
    res = _example1_result()
    vol = FT3_TO_M3  # 1 ft³
    sched = calculate_aci_trial_batches(res, volume_m3=vol)
    b = sched["batches"][0]["batch"]
    assert (b["coarse_agg_batched"] / LB_FT3_TO_KG) == pytest.approx(72.44, rel=0.002)
    assert (b["fine_agg_batched"] / LB_FT3_TO_KG) == pytest.approx(51.00, rel=0.002)


def test_total_batch_weight_preserved():
    """§5.3.9.1: total batch weight equals total mixture weight."""
    res = _example1_result()
    sched = calculate_aci_trial_batches(res, volume_m3=0.05)
    pm = sched["batches"][0]["per_m3"]
    assert pm["total_batched"] == pytest.approx(pm["total_design"], rel=1e-6)


def test_batch_scales_linearly_to_volume():
    res = _example1_result()
    sched = calculate_aci_trial_batches(res, volume_m3=0.05)
    b = sched["batches"][0]
    assert b["batch"]["coarse_agg_batched"] == pytest.approx(
        b["per_m3"]["coarse_agg_batched"] * 0.05, rel=1e-3
    )


# ----------------------------------------------------------------------
# §5.3.10 evaluation — §9.2.9 worked example
# ----------------------------------------------------------------------

def _example929_measurements() -> dict:
    """The §9.2.9 1 ft³ trial: 8.50 lb/ft³ water added (7.48 + 1.02),
    2 in. slump, measured density 147.5 lb/ft³."""
    return {
        "volume_m3": FT3_TO_M3,
        "actual_water_kg": 8.50 * LB_FT3_TO_KG,
        "batched_fine_kg": 51.00 * LB_FT3_TO_KG,
        "batched_coarse_kg": 72.44 * LB_FT3_TO_KG,
        "measured_slump_mm": 50.8,  # 2 in.
        "measured_density_kg_m3": 147.5 * LB_FT3_TO_KG_M3,
    }


def test_free_water_reversal_matches_9291():
    """§9.2.9.1: free water 1.07 (CA) + 2.55 (FA); net mixing water
    12.12 lb/ft³ = 327 lb/yd³."""
    res = _example1_result()
    ev = evaluate_aci_trial(res, measurements=_example929_measurements())
    fw = ev["free_water"]
    assert (fw["free_water_coarse_kg"] / LB_FT3_TO_KG) == pytest.approx(1.07, abs=0.02)
    assert (fw["free_water_fine_kg"] / LB_FT3_TO_KG) == pytest.approx(2.55, abs=0.02)
    net_lb_ft3 = fw["net_water_batch_kg"] / LB_FT3_TO_KG
    assert net_lb_ft3 == pytest.approx(12.12, abs=0.02)
    assert (fw["net_water_kg_m3"] / LB_YD3_TO_KG_M3) == pytest.approx(327.0, rel=0.01)


def test_relative_yield_and_gravimetric_air():
    """§9.2.9.2: Ry = 148.9/147.5 ≈ 1.009 (ASTM C138 convention);
    gravimetric air = (150.4 − 147.5)/150.4 = 1.9%."""
    res = _example1_result()
    ev = evaluate_aci_trial(res, measurements=_example929_measurements())
    y = ev["yield"]
    assert y["relative_yield"] == pytest.approx(1.009, abs=0.002)
    assert y["in_tolerance"] is True
    assert y["gravimetric_air_pct"] == pytest.approx(1.9, abs=0.1)


def test_adjustment1_water_reestimate():
    """§5.3.10.1: net water ÷ yield, then +10 lb/yd³ per inch of slump
    (2 → 3.5 in. = +1.5 in. ≈ +15 lb/yd³). The example's printed 342
    lb/yd³ skips the 0.9% yield division (see module docstring)."""
    res = _example1_result()
    ev = evaluate_aci_trial(res, measurements=_example929_measurements())
    a1 = ev["adjustment_1"]
    re_lb_yd3 = a1["re_estimated_water_kg_m3"] / LB_YD3_TO_KG_M3
    assert re_lb_yd3 == pytest.approx(339.0, abs=4.0)  # example: 342
    slump_lb = a1["slump_correction_kg_m3"] / LB_YD3_TO_KG_M3
    assert slump_lb == pytest.approx(15.0, abs=0.5)
    assert any("water-reducing" in n for n in a1.get("notes", []))


def test_adjustment2_air_water_correction():
    res = _example1_result()
    meas = _example929_measurements()
    meas["measured_air_pct"] = 2.0  # 1% above the 1% design air
    meas["air_entrained_check"] = True
    ev = evaluate_aci_trial(res, measurements=meas)
    a2 = ev["adjustment_2"]
    # ∓5 lb/yd³ (2.97 kg/m³) per 1% air: −2.97 kg/m³ for +1% air.
    assert a2["water_correction_kg_m3"] == pytest.approx(-2.97, abs=0.05)


def test_adjustment3_cement_efficiency():
    """§5.3.10.3: efficiency = strength ÷ cementitious; Δcement closes
    the gap to f'cr (500 psi / 6.2 psi·yd³/lb ≈ 80.7 lb/yd³)."""
    res = _example1_result()
    meas = _example929_measurements()
    meas["cube_strength_mpa"] = 20.684  # 3000 psi
    ev = evaluate_aci_trial(res, measurements=meas)
    a3 = ev["adjustment_3"]
    assert a3["provided"] is True
    eff_psi_lb = a3["efficiency_mpa_per_kg"] / 0.00689476 * (1.0 / LB_YD3_TO_KG_M3) * 0.593276
    # 6.2 psi per lb/yd³ (unit-equivalent of MPa per kg/m³).
    assert a3["efficiency_mpa_per_kg"] == pytest.approx(
        20.684 / (300.0 / 0.62 * LB_YD3_TO_KG_M3), rel=0.01
    )
    delta_lb = a3["delta_cement_kg_m3"] / LB_YD3_TO_KG_M3
    assert delta_lb == pytest.approx(80.7, rel=0.02)


def test_next_trial_proportions_match_929():
    """§9.2.9.3–9.2.9.6: w/cm held at 0.62, CA unchanged, air at the
    measured content, fine aggregate fills the absolute volume. The
    example prints 342/552/1100 lb/yd³; the workbook's yield-corrected
    water gives ≈1% less water/cement and ≈1% more fine aggregate."""
    res = _example1_result()
    ev = evaluate_aci_trial(res, measurements=_example929_measurements())
    nt = ev["next_trial"]
    pm = nt["per_m3"]
    assert nt["w_c_ratio"] == pytest.approx(0.62, abs=0.005)
    assert (pm["water"] / LB_YD3_TO_KG_M3) == pytest.approx(342.0, rel=0.02)
    assert (pm["cement"] / LB_YD3_TO_KG_M3) == pytest.approx(552.0, rel=0.02)
    assert (pm["coarse_agg_ssd"] / LB_YD3_TO_KG_M3) == pytest.approx(1927.0, rel=0.001)
    assert (pm["fine_agg_ssd"] / LB_YD3_TO_KG_M3) == pytest.approx(1100.0, rel=0.02)
    # Absolute-volume closure at the measured air content.
    inp = _example1_input()
    vol = (pm["water"] / 1000.0
           + pm["cement"] / (3.15 * 1000.0)
           + pm["coarse_agg_ssd"] / (2.68 * 1000.0)
           + pm["fine_agg_ssd"] / (2.64 * 1000.0)
           + 1.9 / 100.0)
    assert vol == pytest.approx(1.0, abs=0.001)


def test_next_trial_scales_to_batch_volume():
    res = _example1_result()
    ev = evaluate_aci_trial(res, measurements=_example929_measurements())
    nt = ev["next_trial"]
    assert nt["batch"]["water"] == pytest.approx(
        nt["per_m3"]["water"] * FT3_TO_M3, rel=1e-3
    )


def test_no_measurements_rejected():
    res = _example1_result()
    with pytest.raises(ValueError, match="measurements"):
        evaluate_aci_trial(res, measurements={})


# ----------------------------------------------------------------------
# Appendix A.5 trial series
# ----------------------------------------------------------------------

def test_series_variants_hold_water_constant():
    res = _example1_result()
    sched = calculate_aci_trial_batches(
        res, volume_m3=0.05, include_series=True, cement_step_pct=10.0,
    )
    assert len(sched["series"]) == 2
    low, high = sched["series"]
    for s in (low, high):
        assert s["per_m3"]["water"] == pytest.approx(res.water_kg, rel=0.001)
    # Cement contents ±10% and the resulting w/cm.
    cem = res.cement_kg
    assert low["per_m3"]["cementitious"] == pytest.approx(cem * 0.9, rel=0.001)
    assert high["per_m3"]["cementitious"] == pytest.approx(cem * 1.1, rel=0.001)
    assert low["w_c_ratio"] == pytest.approx(res.water_kg / (cem * 0.9), abs=0.001)
    # Absolute volume closes for each series mixture.
    inp = _example1_input()
    for s in (low, high):
        pm = s["per_m3"]
        vol = (pm["water"] / 1000.0
               + pm["cementitious"] / (3.15 * 1000.0)
               + pm["coarse_agg_ssd"] / (2.68 * 1000.0)
               + pm["fine_agg_ssd"] / (2.64 * 1000.0)
               + 0.01)
        assert vol == pytest.approx(1.0, abs=0.001)


def test_series_step_bounds_enforced():
    res = _example1_result()
    with pytest.raises(ValueError, match="Cement step"):
        calculate_aci_trial_batches(res, include_series=True, cement_step_pct=60.0)


def test_missing_input_record_rejected():
    res = _example1_result()
    object.__delattr__(res, "_input") if hasattr(res, "_input") else None
    with pytest.raises(ValueError, match="input record"):
        calculate_aci_trial_batches(res)
