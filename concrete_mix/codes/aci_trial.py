"""ACI PRC-211.1-22 trial-mix batch schedule and post-trial evaluation.

Source: "Selecting Proportions for Normal-Density and High-Density
Concrete — Guide" (ACI PRC-211.1-22):

- §5.3.9 Step 9 / Table 5.3.9.1 — batch weight summary with the moisture
  adjustment  w_batched = w_SSD × (1 + MC%) / (1 + A%)  and the water to
  batch (mixing water minus the free water on the aggregates); the total
  batch weight equals the total mixture weight.
- §5.3.10 Step 10 — post-trial batch adjustments from measurements per
  ASTM C192/C143/C138/C173/C231: Adjustment 1 re-estimates the mixing
  water from the net water of the trial and the slump difference;
  Adjustment 2 corrects for air content; Adjustment 3 uses cement
  efficiency (psi per lb/yd³) for strength; §5.3.10.4 recalculates the
  next-trial proportions from Step 5.
- Chapter 8 / Appendix A.5 — the trial batch series (three-point curve):
  mixtures above and below the design cement content at constant water
  establish the material-specific w/cm–strength relationship.
- §9.2.9 (Example 1) — the fully worked post-trial computation used as
  the test ground truth.

Units follow the app convention: all internal quantities are per cubic
metre in kg (the standard's lb/yd³ values convert at 1 lb = 0.45359237 kg,
1 yd³ = 0.76455486 m³).

App-policy notes (documented per AGENTS.md — the standard is silent or
the example simplifies):
  - Relative yield is reported per ASTM C138 as Ry = theoretical density
    ÷ measured density (§5.3.10 working tolerance 0.98–1.02). §9.2.9.2
    prints the reciprocal convention ("yield 26.75 ft³" = 27 × measured
    ÷ theoretical); both give the same Ry = 1.0095 for the example.
  - Adjustment 1 divides the net trial water by the measured yield;
    §9.2.9 treats the 1 ft³ trial as exactly 1 ft³ (yield ≈ 1), so the
    workbook's re-estimated water differs from the printed 342 lb/yd³ by
    the ~0.9 % yield correction.
  - When both slump and strength adjustments fire, the next-trial
    cementitious content is the Step-5 value (water ÷ w/cm) plus the
    Adjustment-3 cement delta; the standard treats the adjustments
    individually and gives no combination rule.
"""

from __future__ import annotations

from typing import Any

from concrete_mix.engine.moisture_correction import (
    adjust_water_for_aggregate_moisture,
    correct_for_moisture,
)
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult

# §5.3.10.1: ±10 lb/yd³ (5.93 kg/m³) per 1 in. (25.4 mm) of slump change.
SLUMP_WATER_KG_M3_PER_IN = 5.93
SLUMP_WATER_KG_M3_PER_MM = SLUMP_WATER_KG_M3_PER_IN / 25.4
# §5.3.10.2: ∓5 lb/yd³ (2.97 kg/m³) per 1 % air change.
AIR_WATER_KG_M3_PER_PCT = 2.97
# §4.7.9.3 / §5.3.10 working tolerance on relative yield.
RELATIVE_YIELD_TOLERANCE = (0.98, 1.02)

# §5.3.10 tests on trial batches (ASTM standards cited by the guide).
TEST_CHECKLIST = [
    ("Preparation of trial batches", "ASTM C192/C192M (ACI PRC-211.1-22 Ch. 8, §5.3.10)"),
    ("Temperature of fresh concrete", "ASTM C1064/C1064M (Ch. 8)"),
    ("Slump", "ASTM C143/C143M (Ch. 8, §5.3.10)"),
    ("Density (yield) of fresh concrete", "ASTM C138/C138M (§5.3.10, §4.7.9)"),
    ("Air content — volumetric", "ASTM C173/C173M (§5.3.10)"),
    ("Air content — pressure method", "ASTM C231/C231M (§5.3.10)"),
    ("Making and curing specimens", "ASTM C31/C31M (Ch. 8 curing guidance)"),
]

# Table 8 (Kosmatka and Wilson 2016) qualitative adjustment guide. The
# extracted document's arrow grid is garbled, so only the properties the
# table covers are listed with the guide's general rule (Ch. 8): an
# adjustment that improves one property may degrade another — re-test
# after every change rather than applying tabulated directions blindly.
TABLE_8_GUIDANCE = (
    "Table 8 (Kosmatka and Wilson 2016) guides constituent adjustments "
    "by their effect on: water demand, workability, air content, "
    "bleeding and segregation, finishability, time of setting, heat of "
    "hydration, strength, permeability and cracking. Chapter 8 cautions "
    "that an adjustment improving one property can cause another to "
    "become deficient — change one constituent at a time and re-trial "
    "until all requirements are within tolerance."
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _round1(value: float) -> float:
    return round(value, 1)


def _constituents(result: MixDesignResult) -> dict[str, float]:
    """Per-m³ design constituents (SSD aggregates)."""
    return {
        "water": result.water_kg,
        "cementitious": result.cement_kg + result.scm_kg,
        "fine_agg_ssd": result.fine_aggregate_kg,
        "coarse_agg_ssd": result.coarse_aggregate_kg,
        "admixture": float(result.admixture_kg or 0.0),
    }


def _scale(per_m3: dict[str, float], volume_m3: float) -> dict[str, float]:
    return {k: (round(v * volume_m3, 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
            for k, v in per_m3.items()}


def _moisture_params(inp: MixDesignInput) -> dict[str, float]:
    return {
        "fa_absorption": inp.fine_aggregate.absorption_percent,
        "fa_moisture": inp.fine_aggregate.moisture_content_percent,
        "ca_absorption": inp.coarse_aggregate.absorption_percent,
        "ca_moisture": inp.coarse_aggregate.moisture_content_percent,
    }


def _free_water(fa_ssd: float, ca_ssd: float, mp: dict[str, float]) -> dict[str, float]:
    """Free water carried by each aggregate at the stockpile moisture.

    free = w_SSD × [(1 + MC%) / (1 + A%) − 1]  (§5.3.9.1); negative when
    the aggregate is drier than SSD (absorption deficit).
    """
    free_fa = fa_ssd * ((1.0 + mp["fa_moisture"] / 100.0) / (1.0 + mp["fa_absorption"] / 100.0) - 1.0)
    free_ca = ca_ssd * ((1.0 + mp["ca_moisture"] / 100.0) / (1.0 + mp["ca_absorption"] / 100.0) - 1.0)
    return {"fine_agg": free_fa, "coarse_agg": free_ca}


def _absolute_volume(mass_kg: float, sg: float) -> float:
    """Absolute volume of a constituent in m³ per m³ of concrete."""
    return mass_kg / (sg * 1000.0)


def _fine_fill(
    inp: MixDesignInput,
    water: float,
    cementitious: float,
    scm: float,
    coarse: float,
    air_pct: float,
) -> tuple[float, float]:
    """Fine aggregate (SSD) that fills the remaining absolute volume.

    Absolute-volume method (§5.3.7 Step 7; §9.2.9.5 reapplies it for the
    next trial). Returns (fine mass kg/m³, resulting total volume m³).
    """
    sg_c = inp.cement.specific_gravity
    sg_f = inp.fine_aggregate.specific_gravity
    sg_ca = inp.coarse_aggregate.specific_gravity
    sg_s = inp.scms[0].specific_gravity if inp.scms else 3.15
    vol = (
        _absolute_volume(water, 1.0)
        + _absolute_volume(cementitious - scm, sg_c)
        + (_absolute_volume(scm, sg_s) if scm > 0 else 0.0)
        + _absolute_volume(coarse, sg_ca)
        + air_pct / 100.0
    )
    v_fine = max(0.0, 1.0 - vol)
    return v_fine * sg_f * 1000.0, v_fine


# ----------------------------------------------------------------------
# §5.3.9 — batch weight summary (Table 5.3.9.1)
# ----------------------------------------------------------------------

def calculate_aci_trial_batches(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
    volume_m3: float = 0.05,
    include_series: bool = False,
    cement_step_pct: float = 10.0,
) -> dict[str, Any]:
    """Build the Table 5.3.9.1 batch weight summary for a trial volume.

    Args:
        result: ACI MixDesignResult (``result._input`` used when *inp*
            is omitted).
        inp: The design input record (aggregate moisture/absorption,
            specific gravities). Required.
        volume_m3: Trial batch volume; §9.2.9's reference trial is 1 ft³
            (0.0283 m³), DOE-style 0.05 m³ also works.
        include_series: Append the Appendix A.5 trial-series mixtures
            (cement contents above and below the design value at
            constant water).
        cement_step_pct: Cement-content step of the series, ± %.

    Returns:
        Dict with the ``batches`` list (design vs batched weights per
        §5.3.9.1), the optional A.5 ``series``, the ``test_checklist``
        and ``warnings``.
    """
    if inp is None:
        inp = getattr(result, "_input", None)
    if inp is None:
        raise ValueError(
            "The ACI trial workbook needs the design input record "
            "(aggregate moisture and specific gravities)"
        )
    if volume_m3 <= 0:
        raise ValueError("Trial volume must be positive")
    if not 1.0 <= cement_step_pct <= 50.0:
        raise ValueError("Cement step must be between 1% and 50%")

    mp = _moisture_params(inp)
    c = _constituents(result)

    # §5.3.9.1 — batched weights and the water to batch at the mixer.
    fa_batched = correct_for_moisture(c["fine_agg_ssd"], mp["fa_absorption"], mp["fa_moisture"])
    ca_batched = correct_for_moisture(c["coarse_agg_ssd"], mp["ca_absorption"], mp["ca_moisture"])
    free = _free_water(c["fine_agg_ssd"], c["coarse_agg_ssd"], mp)
    water_to_batch = adjust_water_for_aggregate_moisture(
        c["water"],
        c["fine_agg_ssd"], mp["fa_absorption"], mp["fa_moisture"],
        c["coarse_agg_ssd"], mp["ca_absorption"], mp["ca_moisture"],
    )
    design_total = sum(c[k] for k in ("water", "cementitious", "fine_agg_ssd", "coarse_agg_ssd", "admixture"))
    batch_total = (water_to_batch + c["cementitious"] + fa_batched + ca_batched
                   + c["admixture"])

    per_m3 = {
        "water": c["water"],
        "water_to_batch": water_to_batch,
        "cementitious": c["cementitious"],
        "fine_agg_ssd": c["fine_agg_ssd"],
        "fine_agg_batched": fa_batched,
        "coarse_agg_ssd": c["coarse_agg_ssd"],
        "coarse_agg_batched": ca_batched,
        "admixture": c["admixture"],
        "free_water_fine": free["fine_agg"],
        "free_water_coarse": free["coarse_agg"],
        "total_design": design_total,
        "total_batched": batch_total,
    }
    batches = [{
        "name": f"Designed mix (w/c {result.w_c_ratio:.2f})",
        "w_c_ratio": result.w_c_ratio,
        "per_m3": {k: round(v, 2) for k, v in per_m3.items()},
        "batch": _scale(per_m3, volume_m3),
        "notes": [
            "Batch weight summary per Table 5.3.9.1: w_batched = "
            "w_SSD × (1 + MC%) / (1 + A%) (§5.3.9.1)",
            "Water to batch = mixing water − free water on the "
            "aggregates; total batch weight equals total mixture weight",
        ],
    }]

    warnings: list[str] = []
    # §5.3.9.1: the moisture adjustment is not a mixture redesign.
    if abs(batch_total - design_total) > 0.01 * design_total:
        warnings.append(
            "Batched total deviates from the mixture total by more than "
            "1% — check the moisture and absorption entries (§5.3.9.1)"
        )

    # Appendix A.5 / three-point curve — cement variants at constant
    # water (CA unchanged, fine fills the volume).
    series: list[dict[str, Any]] = []
    if include_series:
        scm = result.scm_kg
        for sign, label in ((-1.0, "low"), (1.0, "high")):
            cementitious_v = round(c["cementitious"] * (1.0 + sign * cement_step_pct / 100.0), 1)
            wc_v = c["water"] / cementitious_v if cementitious_v > 0 else 0.0
            fine_v, _vol = _fine_fill(
                inp, c["water"], cementitious_v, scm,
                c["coarse_agg_ssd"], result.air_volume_percent,
            )
            adm_v = c["admixture"] * (cementitious_v / c["cementitious"]) if c["cementitious"] > 0 else 0.0
            series.append({
                "name": f"Series {label} (cementitious "
                        f"{'−' if sign < 0 else '+'}{cement_step_pct:.0f}%)",
                "w_c_ratio": round(wc_v, 3),
                "per_m3": {
                    "water": round(c["water"], 1),
                    "cementitious": cementitious_v,
                    "fine_agg_ssd": round(fine_v, 1),
                    "coarse_agg_ssd": round(c["coarse_agg_ssd"], 1),
                    "admixture": round(adm_v, 2),
                },
                "batch": _scale({
                    "water": c["water"], "cementitious": cementitious_v,
                    "fine_agg_ssd": fine_v, "coarse_agg_ssd": c["coarse_agg_ssd"],
                    "admixture": adm_v,
                }, volume_m3),
                "notes": [
                    "A.5 trial series: cement contents above and below "
                    "the design value at the same water establish the "
                    "w/cm–strength relationship for the project materials",
                ],
            })

    return {
        "volume_m3": volume_m3,
        "cement_step_pct": cement_step_pct,
        "moisture": {
            **mp,
            "free_water_fine_kg_m3": round(free["fine_agg"], 2),
            "free_water_coarse_kg_m3": round(free["coarse_agg"], 2),
        },
        "batches": batches,
        "series": series,
        "test_checklist": [{"test": t, "standard": s} for t, s in TEST_CHECKLIST],
        "table8_guidance": TABLE_8_GUIDANCE,
        "warnings": warnings,
    }


# ----------------------------------------------------------------------
# §5.3.10 — post-trial batch adjustments
# ----------------------------------------------------------------------

def evaluate_aci_trial(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
    measurements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the §5.3.10 post-trial adjustments to measured results.

    Args:
        result: ACI MixDesignResult.
        inp: Design input record (``result._input`` used when omitted).
        measurements: Recognised keys:
            ``volume_m3`` (trial batch volume), ``actual_water_kg``
            (water actually added to the batch), ``batched_fine_kg`` /
            ``batched_coarse_kg`` (moist aggregate masses actually
            batched — defaults to the §5.3.9.1 schedule),
            ``measured_slump_mm``, ``measured_density_kg_m3``,
            ``measured_air_pct``, ``cube_strength_mpa``,
            ``test_age_days``.

    Returns:
        Dict with the free-water reversal, yield/air section, the three
        §5.3.10 adjustments, the §5.3.10.4 next-trial proportions, and
        warnings.
    """
    measurements = dict(measurements or {})
    if not measurements:
        raise ValueError("No trial measurements supplied")
    if inp is None:
        inp = getattr(result, "_input", None)
    if inp is None:
        raise ValueError(
            "Trial evaluation needs the design input record — open the "
            "dialog from an ACI design result"
        )
    volume_m3 = float(measurements.get("volume_m3", 0.05) or 0.05)
    if volume_m3 <= 0:
        raise ValueError("Trial volume must be positive")

    mp = _moisture_params(inp)
    c = _constituents(result)
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Free-water reversal (§9.2.9.1) — the net mixing water of the trial.
    # ------------------------------------------------------------------
    fa_batched = float(measurements.get("batched_fine_kg") or 0.0) or \
        correct_for_moisture(c["fine_agg_ssd"], mp["fa_absorption"], mp["fa_moisture"]) * volume_m3
    ca_batched = float(measurements.get("batched_coarse_kg") or 0.0) or \
        correct_for_moisture(c["coarse_agg_ssd"], mp["ca_absorption"], mp["ca_moisture"]) * volume_m3
    fa_ssd_equiv = fa_batched * (1.0 + mp["fa_absorption"] / 100.0) / (1.0 + mp["fa_moisture"] / 100.0)
    ca_ssd_equiv = ca_batched * (1.0 + mp["ca_absorption"] / 100.0) / (1.0 + mp["ca_moisture"] / 100.0)
    free_fa = fa_batched - fa_ssd_equiv
    free_ca = ca_batched - ca_ssd_equiv
    water_added = float(measurements.get("actual_water_kg") or 0.0) or \
        adjust_water_for_aggregate_moisture(
            c["water"],
            c["fine_agg_ssd"], mp["fa_absorption"], mp["fa_moisture"],
            c["coarse_agg_ssd"], mp["ca_absorption"], mp["ca_moisture"],
        ) * volume_m3
    net_water_batch = water_added + free_fa + free_ca
    net_water_m3 = net_water_batch / volume_m3
    free_water_section = {
        "batched_fine_kg": round(fa_batched, 2),
        "batched_coarse_kg": round(ca_batched, 2),
        "ssd_equiv_fine_kg": round(fa_ssd_equiv, 2),
        "ssd_equiv_coarse_kg": round(ca_ssd_equiv, 2),
        "free_water_fine_kg": round(free_fa, 2),
        "free_water_coarse_kg": round(free_ca, 2),
        "water_added_kg": round(water_added, 2),
        "net_water_batch_kg": round(net_water_batch, 2),
        "net_water_kg_m3": round(net_water_m3, 1),
    }

    # ------------------------------------------------------------------
    # Yield and gravimetric air (§5.3.10 / ASTM C138; §9.2.9.2)
    # ------------------------------------------------------------------
    design_total = sum(c[k] for k in ("water", "cementitious", "fine_agg_ssd",
                                      "coarse_agg_ssd", "admixture"))
    theoretical = design_total  # per 1 m³ of design concrete (kg/m³)
    air_design = result.air_volume_percent or 0.0
    air_free_density = theoretical / (1.0 - air_design / 100.0) if air_design < 100 else theoretical
    measured_density = measurements.get("measured_density_kg_m3")
    yield_section: dict[str, Any] = {
        "theoretical_density_kg_m3": round(theoretical, 1),
        "air_free_density_kg_m3": round(air_free_density, 1),
        "measured_density_kg_m3": measured_density,
        "relative_yield": None,
        "gravimetric_air_pct": None,
        "in_tolerance": None,
    }
    yield_m3 = None
    if measured_density:
        # Yield of the design batch mass at the measured density.
        yield_m3 = theoretical / float(measured_density)
        ry = yield_m3 / 1.0
        grav_air = (air_free_density - float(measured_density)) / air_free_density * 100.0
        yield_section.update({
            "relative_yield": round(ry, 4),
            "gravimetric_air_pct": round(grav_air, 2),
            "in_tolerance": RELATIVE_YIELD_TOLERANCE[0] <= ry <= RELATIVE_YIELD_TOLERANCE[1],
        })
        if not yield_section["in_tolerance"]:
            warnings.append(
                f"Relative yield {ry:.3f} is outside the 0.98–1.02 working "
                f"tolerance (§4.7.9.3) — check batch weights, specific "
                f"gravities, moisture and air before adjusting proportions"
            )

    # ------------------------------------------------------------------
    # Adjustment 1 (§5.3.10.1) — re-estimate the mixing water.
    # ------------------------------------------------------------------
    adj1: dict[str, Any] = {
        "provided": True,
        "net_water_kg_m3": round(net_water_m3, 1),
        "yield_corrected_kg_m3": None,
        "slump_correction_kg_m3": None,
        "re_estimated_water_kg_m3": round(net_water_m3, 1),
    }
    if yield_m3 is not None:
        # §5.3.10.1 text: net water × design volume ÷ yield. (§9.2.9
        # skips the 0.9 % division for its 1 ft³ trial — see module doc.)
        re_water = net_water_m3 / yield_m3
        adj1["yield_corrected_kg_m3"] = round(re_water, 1)
    else:
        re_water = net_water_m3
    slump_meas = measurements.get("measured_slump_mm")
    slump_corr = 0.0
    if slump_meas is not None:
        slump_corr = SLUMP_WATER_KG_M3_PER_MM * (float(inp.slump_mm) - float(slump_meas))
        adj1["slump_correction_kg_m3"] = round(slump_corr, 1)
        re_water += slump_corr
        if slump_corr > 0:
            adj1.setdefault("notes", []).append(
                "If adding water is undesirable, consider a "
                "water-reducing admixture (§5.3.10.1)"
            )
    adj1["re_estimated_water_kg_m3"] = round(re_water, 1)

    # ------------------------------------------------------------------
    # Adjustment 2 (§5.3.10.2) — air content.
    # ------------------------------------------------------------------
    adj2: dict[str, Any] = {
        "provided": measurements.get("measured_air_pct") is not None,
        "measured_air_pct": measurements.get("measured_air_pct"),
        "target_air_pct": air_design,
        "water_correction_kg_m3": None,
        "note": None,
    }
    air_corr = 0.0
    if adj2["provided"]:
        air_corr = AIR_WATER_KG_M3_PER_PCT * (air_design - float(measurements["measured_air_pct"]))
        adj2["water_correction_kg_m3"] = round(air_corr, 1)
        adj2["note"] = (
            "Re-estimate the air-entrainer dosage for the required air "
            "content (§5.3.10.2)"
        )

    # ------------------------------------------------------------------
    # Adjustment 3 (§5.3.10.3) — strength via cement efficiency.
    # ------------------------------------------------------------------
    adj3: dict[str, Any] = {
        "provided": measurements.get("cube_strength_mpa") is not None,
        "measured_strength_mpa": measurements.get("cube_strength_mpa"),
        "fcr_mpa": result.target_mean_strength_mpa,
        "efficiency_mpa_per_kg": None,
        "delta_cement_kg_m3": None,
        "delta_water_kg_m3": None,
    }
    delta_cem = 0.0
    if adj3["provided"]:
        strength = float(measurements["cube_strength_mpa"])
        if c["cementitious"] > 0:
            eff = strength / c["cementitious"]
            delta_cem = (result.target_mean_strength_mpa - strength) / eff if eff > 0 else 0.0
            adj3["efficiency_mpa_per_kg"] = round(eff, 4)
            adj3["delta_cement_kg_m3"] = round(delta_cem, 1)
            adj3["delta_water_kg_m3"] = round(delta_cem * result.w_c_ratio, 1)

    # ------------------------------------------------------------------
    # §5.3.10.4 — next-trial proportions (recalculate from Step 5).
    # ------------------------------------------------------------------
    water_next = re_water + air_corr
    cementitious_next = water_next / result.w_c_ratio if result.w_c_ratio > 0 else c["cementitious"]
    if adj3["provided"]:
        cementitious_next += delta_cem
    scm_next = (
        result.scm_kg / c["cementitious"] * cementitious_next
        if c["cementitious"] > 0 else 0.0
    )
    cement_next = cementitious_next - scm_next
    air_next = (float(measurements["measured_air_pct"])
                if measurements.get("measured_air_pct") is not None
                else (yield_section["gravimetric_air_pct"]
                      if yield_section["gravimetric_air_pct"] is not None
                      else air_design))
    coarse_next = c["coarse_agg_ssd"]  # unchanged when workability is OK
    fine_next, _ = _fine_fill(
        inp, water_next, cementitious_next, scm_next, coarse_next, air_next,
    )
    adm_dose = (result.admixture_dosage_percent or 0.0)
    adm_next = cementitious_next * adm_dose / 100.0 if adm_dose > 0 else 0.0
    next_per_m3 = {
        "water": round(water_next, 1),
        "cement": round(cement_next, 1),
        "scm": round(scm_next, 1),
        "fine_agg_ssd": round(fine_next, 1),
        "coarse_agg_ssd": round(coarse_next, 1),
        "admixture": round(adm_next, 2),
    }
    next_trial = {
        "per_m3": next_per_m3,
        "w_c_ratio": round(water_next / cementitious_next, 3) if cementitious_next > 0 else None,
        "air_basis_pct": air_next,
        "batch": _scale(next_per_m3, volume_m3),
        "note": (
            "§5.3.10.4: new batch weights calculated from Step 5; coarse "
            "aggregate held unless workability requires a Table 5.3.6 "
            "adjustment; air uses the measured content where available"
        ),
    }

    if not any([
        measurements.get("measured_slump_mm") is not None,
        measured_density is not None,
        measurements.get("measured_air_pct") is not None,
        measurements.get("cube_strength_mpa") is not None,
    ]):
        raise ValueError(
            "No usable measurements found — provide at least one of: "
            "slump, fresh density (yield), air content, or strength"
        )

    return {
        "free_water": free_water_section,
        "yield": yield_section,
        "adjustment_1": adj1,
        "adjustment_2": adj2,
        "adjustment_3": adj3,
        "next_trial": next_trial,
        "test_checklist": [{"test": t, "standard": s} for t, s in TEST_CHECKLIST],
        "table8_guidance": TABLE_8_GUIDANCE,
        "warnings": warnings,
    }
