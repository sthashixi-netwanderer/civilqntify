"""DOE (BRE 331:1997 §6) trial-mix batch schedule and feedback evaluation.

Source: "Design of normal concrete mixes" (BR 331), 2nd edition, 1997,
§6 "Trial mixes" (production §6.1, tests §6.2, adjustments §6.3).

Two pure functions serve the DOE trial-mixes dialog:

``calculate_doe_trial_batches``
    Scales the design quantities to a trial volume (§6.1 — typically
    0.05 m³ for six 150 mm cubes plus slump/Vebe and density tests),
    optionally adds w/c variant batches at the same water content (§6
    intro: "it may be expedient to prepare two or more initial trial
    mixes with the same water content but with different water/cement
    ratios"), and converts the schedule to the selected BS 1881 Part 125
    moisture condition (SSD basis by design; oven-dry/air-dried batching
    scales aggregates by 100/(100+A) and adds the absorption water).

``evaluate_doe_trial``
    Applies the §6.3 feedback loop to measured trial results: workability
    assessment (§6.3.1, Table 3), density correction of the unit
    proportions (§6.3.2), and the Figure 7 strength adjustment that
    re-estimates the free-water/cement ratio (§6.3.3) via the app's
    Figure 4 model, ending in a minor-adjustment / re-trial verdict.

App-policy items (documented per AGENTS.md — the standard is silent):
  - The "minor vs large adjustment" boundary is |D − B′| ≤ 0.05 on the
    free-water/cement ratio; beyond it a second trial mix is advised.
  - Figure 7's curve-through-the-trial-point (A/B/B′/C/D) is implemented
    as a shift of the app's log-quadratic Figure 4 curve family
    (``wc_ratio_from_strength``) so the trial curve and the design curve
    share one shape model.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_DOWN, Decimal
from typing import Any

from concrete_mix.codes.doe import DOEMixDesign, _round_to_5
from concrete_mix.codes.tables.doe_tables import (
    PFA_EFFICIENCY_K,
    figure6_panel_label,
    get_free_water_content,
    get_fine_aggregate_proportion,
    get_reference_strength,
    get_wet_density,
    resolve_workability_class,
    workability_class_label,
    wc_ratio_from_strength,
)
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult

# Figure 4 model coefficients (see wc_ratio_from_strength): the same
# curve family is inverted through the trial point for Figure 7.
_WC_LIN = 0.370938
_WC_QUAD = 0.045970
_WC_CENTER = 0.5

# App policy: minor adjustment (production mixes without further trials)
# vs large adjustment (second trial mix advised) — BRE 331:1997 §6.3.3
# distinguishes "minor" from "large" without a numeric boundary.
MINOR_ADJUSTMENT_WC_LIMIT = 0.05

# §6.2 tests on trial mixes (BS 1881 parts cited by BRE 331:1997 §6.2),
# plus §6.1's preparation standard.
TEST_CHECKLIST = [
    ("Preparation of trial mixes", "BS 1881:Part 125 (BRE 331:1997 §6.1)"),
    ("Slump test", "BS 1881:Part 102 (BRE 331:1997 §6.2)"),
    ("Vebe time test", "BS 1881:Part 104 (BRE 331:1997 §6.2)"),
    ("Density (fresh concrete)", "BS 1881:Part 107 (BRE 331:1997 §6.2)"),
    ("Making test cubes", "BS 1881:Part 108 (BRE 331:1997 §6.2)"),
    ("Normal curing", "BS 1881:Part 111 (BRE 331:1997 §6.2)"),
    ("Compression testing of cubes", "BS 1881:Part 116 (BRE 331:1997 §6.2)"),
]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _round1_half_down(value: float) -> float:
    """Round to 1 dp, halves going down (§7.1: 25.75 → 25.7, 69.25 → 69.2).

    The standard's 50-litre example prints 25.7 and 69.2 where exact
    scaling gives 25.75 and 69.25, so batch masses are rounded half-down
    at the first decimal.
    """
    return float(Decimal(repr(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_DOWN))


def _design_wet_density(result: MixDesignResult, inp: MixDesignInput) -> float:
    """Recompute the design's Item 4.2 wet density (nearest 5 kg).

    Mirrors doe.design() exactly: Figure 5 at (water, coarse SG), then the
    §8.3 air deduction for air-entrained mixes.
    """
    sg = inp.coarse_aggregate.specific_gravity
    density = _round_to_5(get_wet_density(result.water_kg, sg))
    air_pct = result.air_volume_percent or 0.0
    if air_pct > 0:
        density = float(_round_to_5(density - 10.0 * air_pct * sg))
    return density


def _design_workability_class(inp: MixDesignInput) -> int:
    """Table 3 / Figure 6 workability class used by the design."""
    vebe_s = getattr(inp, "vebe_s", None)
    cls, _ = resolve_workability_class(inp.slump_mm, vebe_s)
    return cls


def _table3_water(inp: MixDesignInput, workability_class: int) -> float:
    """Table 3 free-water content at a class, honouring mixed agg types.

    Same weighting as the design stage (BRE 331:1997 Note to Table 3):
    W = 2/3·Wf + 1/3·Wc when fine and coarse aggregates differ in type.
    """
    nmsa = int(inp.nmsa) if inp.nmsa <= 10 else (20 if inp.nmsa <= 20 else 40)
    coarse_type = DOEMixDesign._map_agg_type(inp)
    fine_type = DOEMixDesign._map_fine_agg_type(inp)
    if coarse_type != fine_type:
        w_f = get_free_water_content(nmsa, fine_type, workability_class=workability_class)
        w_c = get_free_water_content(nmsa, coarse_type, workability_class=workability_class)
        return (2.0 / 3.0) * w_f + (1.0 / 3.0) * w_c
    return float(get_free_water_content(nmsa, coarse_type, workability_class=workability_class))


def _scm_mode(result: MixDesignResult) -> str | None:
    """'pfa' / 'ggbs' when the design carries an SCM, else None."""
    if result.scm_kg and result.scm_kg > 0:
        # The DOE engine supports only pfa (§9) or ggbs (§10); the split
        # mode matters only for the cementitious recomputation, and both
        # branch on which addition is present.
        return "scm"
    return None


def _batch_constituents(
    result: MixDesignResult,
    cement: float,
    scm: float,
    water: float,
    fine: float,
    coarse: float,
) -> dict[str, float]:
    """Per-m³ constituent dict for a batch (SSD basis)."""
    return {
        "cement": cement,
        "scm": scm,
        "water": water,
        "fine_agg": fine,
        "coarse_agg": coarse,
        "admixture": float(result.admixture_kg or 0.0),
    }


def _scale_masses(per_m3: dict[str, float], volume_m3: float) -> dict[str, float]:
    """Scale per-m³ constituents to the trial volume (§6.1), 1 dp half-down.

    ``_round_to_5`` yields ints for whole-5-kg contents, so the numeric
    check must accept both int and float.
    """
    out: dict[str, float] = {}
    for key, val in per_m3.items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out[key] = _round1_half_down(float(val) * volume_m3)
        else:
            out[key] = val
    return out


# ----------------------------------------------------------------------
# §6.1 — batch schedule
# ----------------------------------------------------------------------

def calculate_doe_trial_batches(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
    volume_m3: float = 0.05,
    wc_step: float = 0.05,
    include_variants: bool = False,
    moisture_condition: str = "ssd",
) -> dict[str, Any]:
    """Build the §6.1 trial-batch schedule from a DOE design result.

    Args:
        result: DOE MixDesignResult (``result._input`` used when *inp* is
            omitted).
        inp: The design input record. Required for variant batches and
            for non-SSD moisture conditions (absorption / grading data).
        volume_m3: Trial volume; §6.1's reference batch is 0.05 m³
            (six 150 mm cubes + slump/Vebe/density tests).
        wc_step: w/c offset of the optional variant batches.
        include_variants: Generate the ±wc_step variant batches at the
            same water content (§6 intro). Plain mixes only.
        moisture_condition: "ssd" | "oven_dry" | "air_dried" |
            "surface_wet" (BS 1881 Part 125 conditions a–d, §6.1).

    Returns:
        Dict with ``batches`` (per-m³ and trial-volume masses), the
        §6.2 ``test_checklist`` and any ``warnings``.
    """
    if volume_m3 <= 0:
        raise ValueError("Trial volume must be positive")
    if not 0.01 <= wc_step <= 0.10:
        raise ValueError("w/c variant step must be between 0.01 and 0.10")
    if moisture_condition not in ("ssd", "oven_dry", "air_dried", "surface_wet"):
        raise ValueError(
            f"Unknown moisture condition '{moisture_condition}' — use "
            f"'ssd', 'oven_dry', 'air_dried' or 'surface_wet' "
            f"(BS 1881 Part 125 conditions a–d)"
        )
    if inp is None:
        inp = getattr(result, "_input", None)
    if inp is None and (include_variants or moisture_condition != "ssd"):
        raise ValueError(
            "Variant batches and moisture-condition batching need the "
            "design input record (aggregate absorption/grading) — open "
            "the dialog from a DOE design result"
        )
    if include_variants and _scm_mode(result):
        raise ValueError(
            "w/c variant batches are limited to plain (non-SCM) DOE "
            "designs — for pfa (§9) / ggbs (§10) designs batch the "
            "designed mix and adjust at the trial (project policy)"
        )

    warnings: list[str] = []
    cementitious = result.cement_kg + result.scm_kg
    base = _batch_constituents(
        result,
        cement=result.cement_kg,
        scm=result.scm_kg,
        water=result.water_kg,
        fine=result.fine_aggregate_kg,
        coarse=result.coarse_aggregate_kg,
    )
    if result.air_volume_percent and result.air_volume_percent > 0:
        warnings.append(
            "Air-entrained trial mix: measure the air content first (BS "
            "1881:Part 106) — workability and strength readings depend on "
            "it (BRE 331:1997 §8.5)"
        )

    batches: list[dict[str, Any]] = []

    def _emit(name: str, wc: float, per_m3: dict[str, float], notes: list[str]) -> None:
        entry: dict[str, Any] = {
            "name": name,
            "w_c_ratio": round(wc, 2),
            "per_m3": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in per_m3.items()},
            "batch": _scale_masses(per_m3, volume_m3),
            "added_water_kg": _round1_half_down(per_m3["water"] * volume_m3),
            "dry_aggregate_kg": None,
            "absorption_water_kg": None,
            "free_water_kg": None,
            "notes": notes,
        }
        batches.append(entry)

    _emit(f"Designed mix (w/c {result.w_c_ratio:.2f})", result.w_c_ratio, base, [])

    # --- Optional w/c variants at the same water content (§6 intro) ---
    if include_variants and inp is not None:
        wc_class = _design_workability_class(inp)
        pct_600 = DOEMixDesign._get_pct_passing_600um(inp)
        nmsa = int(inp.nmsa) if inp.nmsa <= 10 else (20 if inp.nmsa <= 20 else 40)
        density = _design_wet_density(result, inp)
        for sign, label in ((-1.0, "low"), (1.0, "high")):
            wc_v = round(result.w_c_ratio + sign * wc_step, 2)
            if not 0.30 <= wc_v <= 0.90:
                warnings.append(
                    f"Variant w/c {wc_v:.2f} outside the Figure 4 range "
                    f"[0.30, 0.90] — variant skipped"
                )
                continue
            cement_v = _round_to_5(result.water_kg / wc_v)  # C3, nearest 5 kg
            max_c = getattr(inp, "max_cement_kg", None)
            min_c = getattr(inp, "min_cement_kg", None)
            if max_c is not None and cement_v > max_c:
                warnings.append(
                    f"Variant w/c {wc_v:.2f} needs {cement_v:.0f} kg/m³ "
                    f"cement, above the specified maximum {max_c:.0f} — "
                    f"variant skipped (Item 3.2)"
                )
                continue
            if min_c is not None and cement_v < min_c:
                cement_v = float(min_c)
            total_v = density - cement_v - result.water_kg  # C4
            if total_v <= 0:
                warnings.append(
                    f"Variant w/c {wc_v:.2f} leaves no aggregate content "
                    f"— variant skipped"
                )
                continue
            fine_prop_v = get_fine_aggregate_proportion(
                nmsa=nmsa, wc_ratio=wc_v, pct_passing_600um=pct_600,
                workability_class=wc_class,
            )  # Figure 6 at the variant ratio, Item 5.2
            fine_v = _round_to_5(total_v * fine_prop_v / 100.0)  # C5
            coarse_v = total_v - fine_v
            panel = figure6_panel_label(nmsa, wc_class)
            _emit(
                f"Variant {label} (w/c {wc_v:.2f}, "
                f"{'−' if sign < 0 else '+'}{wc_step:.2f})",
                wc_v,
                _batch_constituents(
                    result, cement=cement_v, scm=0.0, water=result.water_kg,
                    fine=fine_v, coarse=coarse_v,
                ),
                [
                    f"Same water content as the designed mix (§6 intro); "
                    f"Cement {result.water_kg:.0f} ÷ {wc_v:.2f} = "
                    f"{cement_v:.0f} kg/m³ (C3, nearest 5 kg)",
                    f"Figure 6 [{panel}] at w/c {wc_v:.2f} gives fine "
                    f"proportion {fine_prop_v:.1f}% → {fine_v:.0f} kg/m³ "
                    f"(C5)",
                ],
            )

    # --- Moisture-condition batching (§6.1, BS 1881 Part 125) ---
    if moisture_condition != "ssd":
        fa_abs = inp.fine_aggregate.absorption_percent
        ca_abs = inp.coarse_aggregate.absorption_percent
        fa_mc = inp.fine_aggregate.moisture_content_percent
        ca_mc = inp.coarse_aggregate.moisture_content_percent
        for entry in batches:
            pm = entry["per_m3"]
            bt = entry["batch"]
            if moisture_condition in ("oven_dry", "air_dried"):
                # Water still to be absorbed from SSD state:
                #   oven-dry  → A = absorption
                #   air-dried → A = absorption − existing moisture
                # (§6.1: batch mass × 100/(100+A), mixing water increased
                # by the absorbed mass; A is the water needed to bring the
                # aggregate to SSD.)
                a_fa = fa_abs if moisture_condition == "oven_dry" else max(0.0, fa_abs - fa_mc)
                a_ca = ca_abs if moisture_condition == "oven_dry" else max(0.0, ca_abs - ca_mc)
                dry_fa = bt["fine_agg"] * 100.0 / (100.0 + a_fa) if (100.0 + a_fa) else bt["fine_agg"]
                dry_ca = bt["coarse_agg"] * 100.0 / (100.0 + a_ca) if (100.0 + a_ca) else bt["coarse_agg"]
                dry_fa = _round1_half_down(dry_fa)
                dry_ca = _round1_half_down(dry_ca)
                # §7.1 works the absorption water from the reported
                # batch masses: (25.7 − 25.2) + (69.2 − 68.5) = 1.2 kg.
                abs_water = (bt["fine_agg"] - dry_fa) + (bt["coarse_agg"] - dry_ca)
                entry["dry_aggregate_kg"] = {
                    "fine_agg": dry_fa,
                    "coarse_agg": dry_ca,
                    "coarse_split": {
                        sz: _round1_half_down(m * 100.0 / (100.0 + a_ca))
                        for sz, m in (bt.get("ca_split") or {}).items()
                    } or None,
                }
                entry["absorption_water_kg"] = _round1_half_down(abs_water)
                entry["added_water_kg"] = _round1_half_down(
                    entry["added_water_kg"] + abs_water
                )
                entry["notes"].append(
                    "Dry batching (BS 1881 Part 125): soak the aggregates "
                    "with about half the mixing water and let them stand "
                    "before adding cement, to avoid false workability and "
                    "strength readings (§6.1)"
                )
            else:  # surface_wet — condition (d)
                free_fa = bt["fine_agg"] * max(0.0, fa_mc - fa_abs) / 100.0
                free_ca = bt["coarse_agg"] * max(0.0, ca_mc - ca_abs) / 100.0
                free_water = _round1_half_down(free_fa + free_ca)
                entry["free_water_kg"] = free_water
                entry["added_water_kg"] = _round1_half_down(
                    max(0.0, entry["added_water_kg"] - free_water)
                )
                entry["notes"].append(
                    "Surface-wet aggregates carry free water: it is "
                    "deducted from the water added at the mixer (§6.1)"
                )

    if moisture_condition in ("oven_dry", "air_dried"):
        warnings.append(
            "Dry aggregates must pre-soak with about half the mixing "
            "water before cement is added (BRE 331:1997 §6.1, BS 1881 "
            "Part 125)"
        )

    return {
        "volume_m3": volume_m3,
        "wc_step": wc_step,
        "moisture_condition": moisture_condition,
        "batches": batches,
        "test_checklist": [
            {"test": t, "standard": s} for t, s in TEST_CHECKLIST
        ],
        "warnings": warnings,
    }


# ----------------------------------------------------------------------
# §6.3 — trial evaluation
# ----------------------------------------------------------------------

def evaluate_doe_trial(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
    measurements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the §6.3 feedback loop to measured trial-mix results.

    Args:
        result: DOE MixDesignResult.
        inp: Design input record (``result._input`` used when omitted).
        measurements: Measured trial observations. Recognised keys:
            ``actual_water_kg`` (batch water actually added; per-m³ basis
            derived with ``volume_m3``), ``actual_water_per_m3``,
            ``volume_m3`` (trial batch volume, default 0.05),
            ``measured_slump_mm`` / ``measured_vebe_s``,
            ``measured_density_kg_m3``, ``cube_strength_mpa``,
            ``test_age_days`` (default = design age, else 28).

    Returns:
        Dict with ``workability`` (§6.3.1), ``density`` (§6.3.2),
        ``strength`` (§6.3.3 Figure 7 A/B/B′/C/D chain), ``verdict``
        and ``revised`` proportions.
    """
    measurements = dict(measurements or {})
    if not measurements:
        raise ValueError("No trial measurements supplied")
    if inp is None:
        inp = getattr(result, "_input", None)
    if inp is None:
        raise ValueError(
            "Trial evaluation needs the design input record — open the "
            "dialog from a DOE design result"
        )

    warnings: list[str] = []
    volume_m3 = float(measurements.get("volume_m3", 0.05) or 0.05)
    if volume_m3 <= 0:
        raise ValueError("Trial volume must be positive")

    # ------------------------------------------------------------------
    # §6.3.1 Workability
    # ------------------------------------------------------------------
    design_cls = _design_workability_class(inp)
    measured_slump = measurements.get("measured_slump_mm")
    measured_vebe = measurements.get("measured_vebe_s")
    workability: dict[str, Any] = {
        "design_class": design_cls,
        "design_label": workability_class_label(design_cls),
        "measured_class": None,
        "measured_label": None,
        "water_delta_kg_m3": None,
        "provided": bool(measured_slump or measured_vebe),
        "guidance": [],
    }
    water_delta = 0.0
    if measured_slump or measured_vebe:
        try:
            measured_cls, _ = resolve_workability_class(measured_slump, measured_vebe)
        except ValueError:
            measured_cls = None
        workability["measured_class"] = measured_cls
        if measured_cls is not None:
            workability["measured_label"] = workability_class_label(measured_cls)
            if measured_cls != design_cls:
                # §6.3.1: estimate the water change by reference to
                # Table 3 — the difference between the designed class and
                # the class the trial actually produced.
                water_delta = _table3_water(inp, design_cls) - _table3_water(inp, measured_cls)
                workability["water_delta_kg_m3"] = round(water_delta, 1)
                direction = "add" if water_delta > 0 else "deduct"
                workability["guidance"].append(
                    f"Trial workability is one class "
                    f"{'below' if measured_cls < design_cls else 'above'} "
                    f"the specified {workability['design_label']} range — "
                    f"Table 3 suggests {direction} about "
                    f"{abs(water_delta):.0f} kg/m³ of free water "
                    f"(BRE 331:1997 §6.3.1)"
                )
            else:
                workability["guidance"].append(
                    "Trial workability matches the specified class — no "
                    "water change indicated (BRE 331:1997 §6.3.1)"
                )
        workability["guidance"].append(
            "At mixing, withhold about 10% of the water until the "
            "technician confirms it is needed for workability (§6.3.1)"
        )

    # ------------------------------------------------------------------
    # §6.3.2 Density correction
    # ------------------------------------------------------------------
    measured_density = measurements.get("measured_density_kg_m3")
    density: dict[str, Any] = {
        "assumed": None,
        "measured": None,
        "factor": None,
        "provided": bool(measured_density),
        "corrected_per_m3": None,
    }
    density_factor = None
    assumed = _design_wet_density(result, inp)
    density["assumed"] = assumed
    if measured_density:
        density_factor = float(measured_density) / assumed
        density["measured"] = float(measured_density)
        density["factor"] = round(density_factor, 4)
        density["corrected_per_m3"] = {
            "cement": round(result.cement_kg * density_factor, 1),
            "scm": round(result.scm_kg * density_factor, 1),
            "water": round(result.water_kg * density_factor, 1),
            "fine_agg": round(result.fine_aggregate_kg * density_factor, 1),
            "coarse_agg": round(result.coarse_aggregate_kg * density_factor, 1),
            "admixture": round(float(result.admixture_kg or 0.0) * density_factor, 2),
        }
        density["corrected_per_m3"]["ca_split"] = {
            sz: round(m * density_factor, 1)
            for sz, m in (result.ca_split_kg or {}).items()
        } or None

    # ------------------------------------------------------------------
    # §6.3.3 Strength — Figure 7 (A, B, B′, C, D)
    # ------------------------------------------------------------------
    cube_strength = measurements.get("cube_strength_mpa")
    age_days = int(measurements.get("test_age_days") or getattr(inp, "age_days", 28) or 28)
    strength: dict[str, Any] = {
        "provided": bool(cube_strength),
        "age_days": age_days,
        "A": None,
        "B": None,
        "B_prime": None,
        "C": None,
        "D": None,
        "ref50_prime": None,
        "target_mean": result.target_mean_strength_mpa,
    }
    # Actual water used in the trial (per m³): batch water ÷ batch volume,
    # or the per-m³ value directly. Defaults to the design water (B′ = B).
    actual_water = measurements.get("actual_water_per_m3")
    if actual_water is None and measurements.get("actual_water_kg") is not None:
        actual_water = float(measurements["actual_water_kg"]) / volume_m3
    if actual_water is None:
        actual_water = result.water_kg

    revised_wc = result.w_c_ratio
    if cube_strength:
        cement_class = DOEMixDesign._map_cement_class(inp)
        agg_type = DOEMixDesign._map_agg_type(inp)
        ref50 = get_reference_strength(cement_class, agg_type, age_days)  # A
        b_design = result.w_c_ratio  # B
        b_prime = round(actual_water / result.cement_kg, 4) if result.cement_kg > 0 else b_design  # B′
        c_meas = float(cube_strength)  # C

        # Invert the Figure 4 curve family through the trial point
        # (B′, C): solve 0.5 − k1·R + k2·R² = B′ for R = ln(C/ref50′)
        # and take the root on the design branch (|R| minimal).
        _a, _b, _c = _WC_QUAD, -_WC_LIN, (_WC_CENTER - b_prime)
        disc = _b * _b - 4.0 * _a * _c
        if disc < 0:
            raise ValueError(
                f"Actual trial w/c {b_prime:.2f} lies outside the Figure 4 "
                f"model range [0.30, 0.90] — check the water and cement "
                f"actually used"
            )
        r = (-_b - math.sqrt(disc)) / (2.0 * _a)
        ref50_prime = c_meas * math.exp(-r)  # shifted reference strength

        d_new = wc_ratio_from_strength(result.target_mean_strength_mpa, ref50_prime)

        # Durability cap (Item 1.8) re-checked on D.
        max_wc = inp.w_c_ratio
        cap_note = None
        if max_wc is not None and d_new > max_wc:
            d_new = float(max_wc)
            cap_note = (
                f"The strength-adjusted w/c {wc_ratio_from_strength(result.target_mean_strength_mpa, ref50_prime):.2f} "
                f"exceeds the specified maximum {max_wc:.2f} — capped at "
                f"{max_wc:.2f}; the target mean strength may not be "
                f"reachable within the durability limit (Item 1.8)"
            )
            warnings.append(cap_note)

        strength.update({
            "A": ref50,
            "B": b_design,
            "B_prime": round(b_prime, 2),
            "C": c_meas,
            "D": round(d_new, 2),
            "ref50_prime": round(ref50_prime, 1),
        })
        if result.air_volume_percent and result.air_volume_percent > 0:
            warnings.append(
                "Air-entrained mix: compare the cube result against the "
                "air-corrected expectation and confirm the measured air "
                "content (BRE 331:1997 §8.5)"
            )
        revised_wc = d_new

    # ------------------------------------------------------------------
    # Verdict + revised proportions (§6.3.3)
    # ------------------------------------------------------------------
    verdict: dict[str, Any] = {"decision": None, "delta_wc": None, "text": None}
    revised: dict[str, Any] | None = None
    if strength["provided"] and strength["D"] is not None:
        delta = round(strength["D"] - strength["B_prime"], 3)
        verdict["delta_wc"] = delta
        if abs(delta) <= MINOR_ADJUSTMENT_WC_LIMIT:
            verdict["decision"] = "minor"
            verdict["text"] = (
                f"Minor adjustment (Δw/c = {delta:+.2f}): the revised "
                f"proportions may be used in production mixes without "
                f"further trials (BRE 331:1997 §6.3.3)"
            )
        else:
            verdict["decision"] = "re_trial"
            verdict["text"] = (
                f"Large adjustment (Δw/c = {delta:+.2f} > "
                f"{MINOR_ADJUSTMENT_WC_LIMIT:.2f}, app policy): prepare a "
                f"second trial mix at w/c {strength['D']:.2f} with batch "
                f"quantities recalculated on the measured density "
                f"(BRE 331:1997 §6.3.3)"
            )

        # Recomputed unit proportions at the new w/c (C3/C4/C5 chain,
        # carried on the measured density when available — §6.3.3).
        water_new = result.water_kg + water_delta
        density_basis = density["measured"] or density["assumed"]
        scm_mode = _scm_mode(result)
        if scm_mode:
            # Recompute the cementitious contents at the new equivalent
            # ratio D exactly as the design stage does (§9.3.3 / §10.3).
            _scm_type = None
            if inp.scms:
                _t = inp.scms[0].type.value if hasattr(inp.scms[0].type, "value") else str(inp.scms[0].type)
                _scm_type = "pfa" if _t in ("fly_ash", "fly_ash_c") else ("ggbs" if _t == "ggbfs" else None)
            p_pct = float(inp.total_scm_replacement_percent)
            if _scm_type == "pfa":
                # C6 inversion: C = (100−p)·W / ((100−(1−k)p)·R), k = 0.30;
                # C7: F = p·C/(100−p); combined total re-rounded to 5 kg
                # and split back (§9.4 reports C+F on the 5-kg grid).
                _k = PFA_EFFICIENCY_K
                cement_new = (100.0 - p_pct) * water_new / (
                    (100.0 - (1.0 - _k) * p_pct) * strength["D"]
                )
                scm_new = p_pct * cement_new / (100.0 - p_pct)
                total_new = _round_to_5(cement_new + scm_new)
                cement_new = total_new * (100.0 - p_pct) / 100.0
                scm_new = total_new * p_pct / 100.0
            else:  # ggbs: C3 on the combined total, mass-for-mass split
                total_new = _round_to_5(water_new / strength["D"])
                scm_new = total_new * p_pct / 100.0
                cement_new = total_new - scm_new
            if (max_c := getattr(inp, "max_cement_kg", None)) and total_new > max_c:
                warnings.append(
                    f"Revised cementitious content {total_new:.0f} "
                    f"kg/m³ exceeds the specified maximum "
                    f"{max_c:.0f} (Item 3.2)"
                )
            if (min_c := getattr(inp, "min_cement_kg", None)) and total_new < min_c:
                total_new = float(min_c)
        else:
            cement_new = _round_to_5(water_new / strength["D"])  # C3
            if (max_c := getattr(inp, "max_cement_kg", None)) and cement_new > max_c:
                warnings.append(
                    f"Revised cement content {cement_new:.0f} kg/m³ "
                    f"exceeds the specified maximum {max_c:.0f} "
                    f"(Item 3.2)"
                )
            if (min_c := getattr(inp, "min_cement_kg", None)) and cement_new < min_c:
                cement_new = float(min_c)
            scm_new = 0.0

        total_agg_new = density_basis - (cement_new + scm_new) - water_new  # C4
        if total_agg_new <= 0:
            raise ValueError(
                "Revised proportions leave no aggregate content — the "
                "w/c and workability requirements cannot be met "
                "simultaneously (BRE 331:1997 §5.3)"
            )
        wc_class = _design_workability_class(inp)
        pct_600 = DOEMixDesign._get_pct_passing_600um(inp)
        nmsa = int(inp.nmsa) if inp.nmsa <= 10 else (20 if inp.nmsa <= 20 else 40)
        fine_prop_new = get_fine_aggregate_proportion(
            nmsa=nmsa, wc_ratio=strength["D"], pct_passing_600um=pct_600,
            workability_class=wc_class,
        )
        fine_new = _round_to_5(total_agg_new * fine_prop_new / 100.0)  # C5
        coarse_new = total_agg_new - fine_new
        adm_dose = float(result.admixture_dosage_percent or 0.0)
        adm_new = (cement_new + scm_new) * adm_dose / 100.0 if adm_dose > 0 else 0.0
        revised = {
            "basis": "production" if verdict["decision"] == "minor" else "second_trial",
            "density_basis": density_basis,
            "water_delta_kg_m3": round(water_delta, 1) if water_delta else 0.0,
            "per_m3": {
                "cement": cement_new,
                "scm": scm_new,
                "water": round(water_new, 1),
                "fine_agg": fine_new,
                "coarse_agg": coarse_new,
                "admixture": round(adm_new, 2),
                "ca_split": None,
            },
            "w_c_ratio": strength["D"],
            "fine_proportion_pct": fine_prop_new,
        }
        if result.ca_split_kg:
            # Keep the §5.5 single-size ratios; re-round with the
            # remainder on the largest fraction (as doe.design does).
            ratios = {sz: m / result.coarse_aggregate_kg
                      for sz, m in result.ca_split_kg.items()}
            parts: dict[str, float] = {}
            assigned = 0.0
            items = list(ratios.items())
            for i, (sz, frac) in enumerate(items):
                if i < len(items) - 1:
                    parts[sz] = _round_to_5(coarse_new * frac)
                    assigned += parts[sz]
                else:
                    parts[sz] = coarse_new - assigned
            revised["per_m3"]["ca_split"] = parts
        if verdict["decision"] == "re_trial":
            revised["batch"] = _scale_masses(revised["per_m3"], volume_m3)

    if not workability["provided"] and not density["provided"] and not strength["provided"]:
        raise ValueError(
            "No usable measurements found — provide at least one of: "
            "measured slump/Vebe, fresh density, or cube strength"
        )

    return {
        "workability": workability,
        "density": density,
        "strength": strength,
        "verdict": verdict,
        "revised": revised,
        "test_checklist": [
            {"test": t, "standard": s} for t, s in TEST_CHECKLIST
        ],
        "warnings": warnings,
    }
