"""Digitized ACI PRC-211.1-22 lookup tables for concrete mix design.

All values in metric (SI) units converted from US customary (lb/yd³ × 0.5933 = kg/m³).
Source: ACI PRC-211.1-22 Table 5.3.3 and Table 5.3.6.
"""

from __future__ import annotations

# Table 5.3.3: Approximate mixing water and air content requirements per ACI PRC-211.1-22
# Format: {nmsa_mm: {slump_mm: water_kg_m3}} — converted from lb/yd³ (× 0.5933)
# 10 mm ≈ 3/8", 19 mm ≈ 3/4", 40 mm ≈ 1-1/2"
# Slump classes: 1-2"→25/50 mm, 3-4"→75/100 mm, 5-6"→125/150 mm, 6-7"→175 mm
# (>7" slump is normally obtained with water-reducing admixtures.)
WATER_CONTENT_NON_AIR_ENTRAINED: dict[int, dict[int, float]] = {
    10: {
        25: 208,  # 350 lb/yd³ (1-2" slump)
        50: 208,
        75: 228,  # 385 (3-4")
        100: 228,
        150: 237,  # 400 (5-6")
        175: 243,  # 410 (6-7")
    },
    19: {
        25: 187,  # 315
        50: 187,
        75: 202,  # 340
        100: 202,
        150: 208,  # 350
        175: 214,  # 360
    },
    20: {
        25: 187,  # 315 (approx 19 mm)
        50: 187,
        75: 202,  # 340
        100: 202,
        150: 208,  # 350
        175: 214,  # 360
    },
    40: {
        25: 163,  # 275
        50: 163,
        75: 178,  # 300
        100: 178,
        150: 181,  # 305 (5-6")
        175: 187,  # 315 (6-7")
    },
}

# Table 5.3.3: Air-entrained concrete per ACI PRC-211.1-22
WATER_CONTENT_AIR_ENTRAINED: dict[int, dict[int, float]] = {
    10: {
        25: 181,  # 305 (1-2" slump)
        50: 181,
        75: 202,  # 340 (3-4")
        100: 202,
        150: 211,  # 355 (5-6")
        175: 217,  # 365 (6-7")
    },
    19: {
        25: 166,  # 280
        50: 166,
        75: 181,  # 305
        100: 181,
        150: 187,  # 315
        175: 193,  # 325
    },
    20: {
        25: 166,  # 280
        50: 166,
        75: 181,  # 305
        100: 181,
        150: 187,  # 315
        175: 193,  # 325
    },
    40: {
        25: 148,  # 250
        50: 148,
        75: 163,  # 275
        100: 163,
        150: 166,  # 280
        175: 172,  # 290
    },
}

# Table 5.3.3: Required total air content (%) by NMSA and ACI 318 exposure
# class — "mild" maps to F0 (no frost exposure: entrapped air only),
# "moderate" to F1, "severe" to F2/F3.
# F1:   3/8"→6.0, 3/4"→5.0, 1-1/2"→4.5
# F2/F3: 3/8"→7.5, 3/4"→6.0, 1-1/2"→5.5
AIR_CONTENT: dict[int, dict[str, float]] = {
    10: {"mild": 3.0, "moderate": 6.0, "severe": 7.5},
    20: {"mild": 2.0, "moderate": 5.0, "severe": 6.0},
    40: {"mild": 1.0, "moderate": 4.5, "severe": 5.5},
}

# Entrapped air (non-air-entrained concrete) per ACI PRC-211.1-22 Table 5.3.3
# Standard: 3/8" 3.0%, 1/2" 2.5%, 3/4" 2.0%, 1" 1.5%, 1-1/2" 1.0%, 2" 0.5%, 3" 0.3%
AIR_CONTENT_ENTRAPPED: dict[int, float] = {
    10: 3.0,  # 3/8"
    19: 2.0,  # 3/4"
    20: 2.0,  # 3/4" approx (20 mm)
    40: 1.0,  # 1-1/2"
}

# Table 5.3.4 — Relationship between w/cm and compressive strength of
# concrete (ACI PRC-211.1-22), converted from psi to MPa.
# Non-air-entrained concrete:
#   7000 psi (48.3 MPa) → 0.34;  6000 (41.4) → 0.41;  5000 (34.5) → 0.48
#   4000 (27.6) → 0.57;          3000 (20.7) → 0.68;  2000 (13.8) → 0.82
WC_RATIO_NON_AIR_ENTRAINED: dict[float, float] = {
    48.3: 0.34,
    41.4: 0.41,
    34.5: 0.48,
    27.6: 0.57,
    20.7: 0.68,
    13.8: 0.82,
}

# Table 5.3.4 — Air-entrained concrete:
#   7000 psi (48.3 MPa) → <0.33; 6000 (41.4) → 0.33; 5000 (34.5) → 0.40
#   4000 (27.6) → 0.48;            3000 (20.7) → 0.59; 2000 (13.8) → 0.74
# (Table note: w/cm < 0.33 for 7000 psi may require chemical admixtures,
#  SCMs and higher cementitious content.)
WC_RATIO_AIR_ENTRAINED: dict[float, float] = {
    48.3: 0.33,
    41.4: 0.33,
    34.5: 0.40,
    27.6: 0.48,
    20.7: 0.59,
    13.8: 0.74,
}

# Table 5.3.6 — Bulk volume of coarse aggregate per unit volume of concrete
# Key: (nmsa_mm, fineness_modulus) -> volume fraction (oven-dry-rodded basis)
# ACI PRC-211.1-22 Table 5.3.6: 3/8": 0.50-0.44; 3/4": 0.66-0.60;
# 1-1/2": 0.75-0.69 (2022 guide values)
CA_VOLUME_FRACTION: dict[tuple[int, float], float] = {
    # NMSA 10mm
    (10, 2.40): 0.50,
    (10, 2.60): 0.48,
    (10, 2.80): 0.46,
    (10, 3.00): 0.44,
    # NMSA 19mm (3/4")
    (19, 2.40): 0.66,
    (19, 2.60): 0.64,
    (19, 2.80): 0.62,
    (19, 3.00): 0.60,
    # NMSA 20mm
    (20, 2.40): 0.66,
    (20, 2.60): 0.64,
    (20, 2.80): 0.62,
    (20, 3.00): 0.60,
    # NMSA 40mm
    (40, 2.40): 0.75,
    (40, 2.60): 0.73,
    (40, 2.80): 0.71,
    (40, 3.00): 0.69,
}


def interpolate_water_content(
    nmsa: int, slump_mm: float, air_entrained: bool
) -> float:
    """Interpolate water content (kg/m³) from ACI Table 6.3.3.

    Handles intermediate slump values by linear interpolation.
    """
    table = WATER_CONTENT_AIR_ENTRAINED if air_entrained else WATER_CONTENT_NON_AIR_ENTRAINED
    if nmsa not in table:
        raise ValueError(f"NMSA {nmsa}mm not in ACI water content table")

    slump_values = sorted(table[nmsa].keys())

    # Clamp to table range
    if slump_mm <= slump_values[0]:
        return table[nmsa][slump_values[0]]
    if slump_mm >= slump_values[-1]:
        return table[nmsa][slump_values[-1]]

    # Linear interpolation between bracketing slump values
    for i in range(len(slump_values) - 1):
        s_lo, s_hi = slump_values[i], slump_values[i + 1]
        if s_lo <= slump_mm <= s_hi:
            w_lo = table[nmsa][s_lo]
            w_hi = table[nmsa][s_hi]
            fraction = (slump_mm - s_lo) / (s_hi - s_lo)
            return w_lo + fraction * (w_hi - w_lo)

    return table[nmsa][slump_values[-1]]


def interpolate_w_c_ratio(
    target_strength_mpa: float, air_entrained: bool
) -> float:
    """Interpolate W/C ratio from ACI Table 6.3.4(a)/(b).

    Input: target mean strength (f'cr) in MPa.
    Returns W/C ratio.
    """
    table = WC_RATIO_AIR_ENTRAINED if air_entrained else WC_RATIO_NON_AIR_ENTRAINED
    strengths = sorted(table.keys(), reverse=True)

    # Find bracketing entries
    if target_strength_mpa >= strengths[0]:
        return table[strengths[0]]
    if target_strength_mpa <= strengths[-1]:
        return table[strengths[-1]]

    for i in range(len(strengths) - 1):
        s_hi, s_lo = strengths[i], strengths[i + 1]
        if s_hi >= target_strength_mpa >= s_lo:
            wc_hi = table[s_hi]
            wc_lo = table[s_lo]
            fraction = (target_strength_mpa - s_hi) / (s_lo - s_hi)
            return wc_hi + fraction * (wc_lo - wc_hi)

    return table[strengths[-1]]


def interpolate_ca_volume(nmsa: int, fineness_modulus: float) -> float:
    """Interpolate CA volume fraction from ACI Table 6.3.6.

    Returns volume of coarse aggregate (dry-rodded) per unit volume of concrete.
    """
    fm_values = sorted({fm for (n, fm) in CA_VOLUME_FRACTION.keys() if n == nmsa})
    if not fm_values:
        raise ValueError(f"NMSA {nmsa}mm not in CA volume table")

    # Clamp
    if fineness_modulus <= fm_values[0]:
        key = (nmsa, fm_values[0])
        return CA_VOLUME_FRACTION[key]
    if fineness_modulus >= fm_values[-1]:
        key = (nmsa, fm_values[-1])
        return CA_VOLUME_FRACTION[key]

    # Linear interpolation
    for i in range(len(fm_values) - 1):
        fm_lo, fm_hi = fm_values[i], fm_values[i + 1]
        if fm_lo <= fineness_modulus <= fm_hi:
            vol_lo = CA_VOLUME_FRACTION[(nmsa, fm_lo)]
            vol_hi = CA_VOLUME_FRACTION[(nmsa, fm_hi)]
            fraction = (fineness_modulus - fm_lo) / (fm_hi - fm_lo)
            return vol_lo + fraction * (vol_hi - vol_lo)

    return CA_VOLUME_FRACTION[(nmsa, fm_values[-1])]


def get_air_content(nmsa: int, exposure: str, air_entrained: bool) -> float:
    """Get target air content (%) from ACI Table 6.3.3.

    Args:
        nmsa: Nominal max aggregate size (mm)
        exposure: "mild", "moderate", or "severe"
        air_entrained: Whether air-entrained concrete is specified
    """
    if air_entrained:
        if nmsa not in AIR_CONTENT:
            raise ValueError(f"NMSA {nmsa}mm not in air content table")
        if exposure not in AIR_CONTENT[nmsa]:
            exposure = "moderate"  # default
        return AIR_CONTENT[nmsa][exposure]
    else:
        return AIR_CONTENT_ENTRAPPED.get(nmsa, 1.0)


# ACI 318 Table 19.3.2 — Maximum W/C ratio for durability (sulfate exposure)
# These are absolute limits that override the strength-based W/C ratio.
ACI_MAX_WC_FOR_EXPOSURE: dict[str, float] = {
    "S0": 0.99,  # No sulfate exposure — no limit (use strength-based)
    "S1": 0.50,  # Sulfate exposure
    "S2": 0.45,  # Severe sulfate exposure
    "S3": 0.40,  # Very severe sulfate exposure
}

# ACI 301-20 Table 4.2.2.6(c) / ACI 318 Chapter 19 — freezing-and-thawing
# exposure classes (PRC-211.1-22 Table 4.7.3b). max_wc of None means no
# durability cap beyond strength; min_fc_mpa is the required specified
# strength (psi values converted: 3500 → 24.1, 4500 → 31.0, 5000 → 34.5).
# F1–F3 additionally REQUIRE air entrainment (Table 4.2.2.6(c)).
F_CLASS_LIMITS: dict[str, dict[str, float | None]] = {
    "F0": {"max_wc": None, "min_fc_mpa": None},  # Not exposed to freezing
    "F1": {"max_wc": 0.55, "min_fc_mpa": 24.1},  # Exposed, no deicing salts
    "F2": {"max_wc": 0.45, "min_fc_mpa": 31.0},  # Exposed, deicing salts / seawater
    "F3": {"max_wc": 0.40, "min_fc_mpa": 34.5},  # Continuously wet + freezing + deicing
}

# ACI 301-20 Table 4.2.2.6(d) (PRC-211.1-22 Table 4.7.3c) — exposure to
# water where permeability matters. max_wc of None means no durability cap
# beyond strength; min_fc_mpa None means the 2500 psi floor, which the app's
# structural minimum (≥ 25 MPa) already exceeds. W1/W2 additionally invoke
# ACI 301 4.2.2.6(a) low-permeability provisions (surfaced as guidance: they
# concern curing/testing practice, not proportioning numbers).
W_CLASS_LIMITS: dict[str, dict[str, float | None]] = {
    "W0": {"max_wc": None, "min_fc_mpa": None},  # Dry / protected from water
    "W1": {"max_wc": None, "min_fc_mpa": None},  # In contact, permeability a concern
    "W2": {"max_wc": 0.50, "min_fc_mpa": 27.6},  # Water barrier / 4000 psi
}

# ACI 301-20 Table 4.2.2.6(e) (PRC-211.1-22 Table 4.7.3d) — corrosion
# protection of reinforcement. Chloride caps below are % water-soluble Cl⁻ by
# mass of cementitious material for NON-prestressed concrete (the app's scope;
# prestressed limits are stricter — 0.06% throughout — and need a
# prestressing input the tab does not collect). Chloride content cannot be
# computed from mix proportions, so caps are surfaced as guidance; w/c and
# minimum strength are enforced.
C_CLASS_LIMITS: dict[str, dict[str, float | None]] = {
    "C0": {"max_wc": None, "min_fc_mpa": None, "max_chloride_pct": 1.00},
    "C1": {"max_wc": None, "min_fc_mpa": None, "max_chloride_pct": 0.30},
    "C2": {"max_wc": 0.40, "min_fc_mpa": 34.5, "max_chloride_pct": 0.15},
}

# ACI 301-20 Table 4.2.2.6(b) (PRC-211.1-22 Table 4.7.3a) — sulfate exposure.
# min_fc_mpa converts the table's psi floors (S1: 4000 → 27.6; S2: 4500 →
# 31.0; S3 Option 2: 5000 → 34.5). S3 offers two compliance options; the
# engine enforces Option 2 (w/c ≤ 0.40, the tighter cap) — Option 1
# (w/c ≤ 0.45 with Type V + pozzolan/slag) needs an explicit w/c override
# plus trial evidence per Table 4.2.2.6(b)1. Cement-type and calcium-chloride
# rules cannot be derived from proportions, so they are surfaced as guidance.
S_CLASS_LIMITS: dict[str, dict[str, float | None]] = {
    "S0": {"max_wc": None, "min_fc_mpa": None},
    "S1": {"max_wc": 0.50, "min_fc_mpa": 27.6},
    "S2": {"max_wc": 0.45, "min_fc_mpa": 31.0},
    "S3": {"max_wc": 0.40, "min_fc_mpa": 34.5},
}

S_CLASS_CEMENT_GUIDANCE: dict[str, str] = {
    "S1": "Type II (MS) cement; Type I/III acceptable only if C3A < 8% "
          "(Table 4.7.3a). No restriction on calcium chloride admixture.",
    "S2": "Type V or HS-designation cement; Type I/III only if C3A < 5%. "
          "Calcium chloride admixture NOT permitted.",
    "S3": "Type V + pozzolan/slag cement or HS + pozzolan/slag "
          "(Option 2 applied). Calcium chloride NOT permitted. Option 1 "
          "(w/c ≤ 0.45) needs an explicit w/c override plus trial evidence.",
}

# ACI 301-20 Table 4.2.2.6(c)1 (PRC-211.1-22 Table 4.7.3.1) — required total
# air content (%) for freezing-and-thawing exposure, by NMSA. Field tolerance
# is ±1.5%; at f'c ≥ 5000 psi a 1.0-point reduction is acceptable (surfaced
# as guidance, not applied silently).
F_CLASS_AIR_CONTENT: dict[int, dict[str, float]] = {
    10: {"F1": 6.0, "F2": 7.5, "F3": 7.5},
    19: {"F1": 5.0, "F2": 6.0, "F3": 6.0},  # 3/4 in. (same as 20 mm)
    20: {"F1": 5.0, "F2": 6.0, "F3": 6.0},
    40: {"F1": 4.5, "F2": 5.5, "F3": 5.5},
}

# ACI 301-20 Table 4.2.1.1(b) (PRC-211.1-22 Table 4.7.3.2) — maximum SCM
# replacement (% of total cementitious mass) for Exposure Class F3.
# "ash" covers Class F/C fly ash AND natural pozzolans (incl. metakaolin,
# an ASTM C618 Class N pozzolan); slag cement and silica fume have their
# own buckets. Total and ash-plus-silica combination caps also apply.
F3_SCM_MAX_PERCENT: dict[str, float] = {
    "ash": 25.0,            # fly ash or natural pozzolans (ASTM C618)
    "slag": 50.0,           # slag cement (ASTM C989)
    "silica": 10.0,         # silica fume (ASTM C1240)
    "total": 50.0,          # all SCMs combined
    "ash_plus_silica": 35.0,
}

# SCM type strings (concrete_mix.models.materials.SCMType values) bucketed
# into the Table 4.7.3.2 rows above.
F3_SCM_BUCKETS: dict[str, str] = {
    "fly_ash": "ash",
    "fly_ash_c": "ash",
    "metakaolin": "ash",
    "ggbfs": "slag",
    "silica_fume": "silica",
}


# ACI PRC-211.1-22 Table 5.3.3.1 — adjustments to the estimated water content
# for conditions other than the Table 5.3.3 baseline (standard laboratory
# 68–77 °F, 3–4 in. slump, well-shaped aggregates, natural sand FM 2.75).
# Positive values ADD water, negative values REDUCE it; applied as a summed
# percentage of the Table 5.3.3 estimate (Bureau of Reclamation practice).
#
# IMPORTANT SCOPE NOTE: slump and air-entrainment rows are NOT auto-applied
# by the engine — Table 5.3.3 interpolation already encodes slump and the
# air-entrained/non-air-entrained split, and the standard's own Example 1
# uses unadjusted Table 5.3.3 water for rounded gravel. They live here for
# explicit trial-batch refinement (§5.3.10) only.
WATER_ADJUST_531_ROUNDED_AGG_PCT = -8.0      # rounded (vs angular) aggregate
WATER_ADJUST_531_PER_PCT_AIR_PCT = -3.0      # per 1% increase in air content
WATER_ADJUST_531_PER_INCH_SLUMP_PCT = 3.0    # per 1 in. slump increase
WATER_ADJUST_531_WRA_MIN_PCT = -5.0          # conventional WRA expectation
WATER_ADJUST_531_HRWRA_MIN_PCT = -12.0       # HRWRA expectation (§4.7.6)
WATER_ADJUST_531_PER_10F_TEMP_PCT = 2.0      # per 10 °F concrete-temp rise
WATER_ADJUST_531_PER_10PCT_FLYASH_PCT = -3.0  # per 10% fly-ash replacement
WATER_ADJUST_531_PER_10PCT_SLAG_PCT = -5.0    # per 10% slag replacement
WATER_ADJUST_531_MANUFACTURED_SAND_PCT = 5.0
TABLE_531_BASELINE_TEMP_C = 22.5  # midpoint of 68–77 °F (20–25 °C)


def water_adjustment_531(
    rounded_aggregate: bool = False,
    air_delta_pct: float = 0.0,
    slump_delta_in: float = 0.0,
    temp_c: float | None = None,
    fly_ash_pct: float = 0.0,
    slag_pct: float = 0.0,
    manufactured_sand: bool = False,
) -> tuple[float, list[str]]:
    """Sum Table 5.3.3.1 water-content adjustments (percent of base water).

    Only non-baseline arguments contribute. Silica fume / metakaolin carry
    no table rate (silica usually *increases* demand, §4.7.6) and are handled
    as guidance warnings by the caller, not here.

    Returns (total_percent, [applied rule descriptions]).
    """
    total = 0.0
    applied: list[str] = []
    if rounded_aggregate:
        total += WATER_ADJUST_531_ROUNDED_AGG_PCT
        applied.append(f"rounded aggregate {WATER_ADJUST_531_ROUNDED_AGG_PCT:+.0f}%")
    if air_delta_pct:
        adj = WATER_ADJUST_531_PER_PCT_AIR_PCT * air_delta_pct
        total += adj
        if adj:
            applied.append(f"air {air_delta_pct:+.1f}% → water {adj:+.1f}%")
    if slump_delta_in:
        adj = WATER_ADJUST_531_PER_INCH_SLUMP_PCT * slump_delta_in
        total += adj
        if adj:
            applied.append(f"slump {slump_delta_in:+.1f} in → water {adj:+.1f}%")
    if temp_c is not None:
        delta_f = (temp_c - TABLE_531_BASELINE_TEMP_C) * 9.0 / 5.0
        adj = WATER_ADJUST_531_PER_10F_TEMP_PCT * delta_f / 10.0
        total += adj
        if adj:
            applied.append(f"concrete {temp_c:.1f} °C → water {adj:+.1f}%")
    if fly_ash_pct:
        adj = WATER_ADJUST_531_PER_10PCT_FLYASH_PCT * fly_ash_pct / 10.0
        total += adj
        if adj:
            applied.append(f"fly ash {fly_ash_pct:.0f}% → water {adj:+.1f}%")
    if slag_pct:
        adj = WATER_ADJUST_531_PER_10PCT_SLAG_PCT * slag_pct / 10.0
        total += adj
        if adj:
            applied.append(f"slag {slag_pct:.0f}% → water {adj:+.1f}%")
    if manufactured_sand:
        total += WATER_ADJUST_531_MANUFACTURED_SAND_PCT
        applied.append(
            f"manufactured sand {WATER_ADJUST_531_MANUFACTURED_SAND_PCT:+.0f}%"
        )
    return round(total, 2), applied


def check_nmsa_limits(
    nmsa_mm: float,
    form_width_mm: float | None = None,
    slab_depth_mm: float | None = None,
    bar_spacing_mm: float | None = None,
) -> list[str]:
    """Check NMSA against structural-dimension limits.

    Returns a list of violation messages (empty when compliant or when no
    dimension was supplied).
    """
    violations: list[str] = []
    if form_width_mm is not None and nmsa_mm > form_width_mm / 5.0:
        violations.append(
            f"NMSA {nmsa_mm:g} mm exceeds 1/5 of the narrowest form dimension "
            f"({form_width_mm:g} mm → max {form_width_mm / 5.0:g} mm) "
            f"per ACI 318 26.4.2.1(a)(5)"
        )
    if slab_depth_mm is not None and nmsa_mm > slab_depth_mm / 3.0:
        violations.append(
            f"NMSA {nmsa_mm:g} mm exceeds 1/3 of the slab depth "
            f"({slab_depth_mm:g} mm → max {slab_depth_mm / 3.0:g} mm) "
            f"per ACI 318 26.4.2.1(a)(5)"
        )
    if bar_spacing_mm is not None and nmsa_mm > bar_spacing_mm * 0.75:
        violations.append(
            f"NMSA {nmsa_mm:g} mm exceeds 3/4 of the minimum clear bar spacing "
            f"({bar_spacing_mm:g} mm → max {bar_spacing_mm * 0.75:g} mm) "
            f"per ACI 318 26.4.2.1(a)(5)"
        )
    return violations


def check_f3_scm_limits(scm_types: list[str], scm_percents: list[float]) -> list[str]:
    """Check SCM replacements against ACI 301 Table 4.2.1.1(b) (F3).

    Args:
        scm_types: SCMType values (e.g. "fly_ash", "ggbfs", "silica_fume").
        scm_percents: Replacement % of total cementitious mass, aligned.

    Returns:
        List of violation messages (empty when compliant). Unknown SCM
        types are conservatively counted toward the total cap only.
    """
    buckets: dict[str, float] = {"ash": 0.0, "slag": 0.0, "silica": 0.0}
    total = 0.0
    for t, p in zip(scm_types, scm_percents):
        total += p
        bucket = F3_SCM_BUCKETS.get(t)
        if bucket in buckets:
            buckets[bucket] += p
    violations: list[str] = []
    if buckets["ash"] > F3_SCM_MAX_PERCENT["ash"]:
        violations.append(
            f"Fly ash/natural pozzolan {buckets['ash']:.1f}% exceeds the F3 "
            f"maximum {F3_SCM_MAX_PERCENT['ash']:.0f}% (ACI 301 Table 4.2.1.1(b))"
        )
    if buckets["slag"] > F3_SCM_MAX_PERCENT["slag"]:
        violations.append(
            f"Slag cement {buckets['slag']:.1f}% exceeds the F3 "
            f"maximum {F3_SCM_MAX_PERCENT['slag']:.0f}% (ACI 301 Table 4.2.1.1(b))"
        )
    if buckets["silica"] > F3_SCM_MAX_PERCENT["silica"]:
        violations.append(
            f"Silica fume {buckets['silica']:.1f}% exceeds the F3 "
            f"maximum {F3_SCM_MAX_PERCENT['silica']:.0f}% (ACI 301 Table 4.2.1.1(b))"
        )
    if total > F3_SCM_MAX_PERCENT["total"]:
        violations.append(
            f"Total SCM {total:.1f}% exceeds the F3 "
            f"maximum {F3_SCM_MAX_PERCENT['total']:.0f}% (ACI 301 Table 4.2.1.1(b))"
        )
    if buckets["ash"] + buckets["silica"] > F3_SCM_MAX_PERCENT["ash_plus_silica"]:
        violations.append(
            f"Fly ash/pozzolan + silica fume {buckets['ash'] + buckets['silica']:.1f}% "
            f"exceeds the F3 maximum {F3_SCM_MAX_PERCENT['ash_plus_silica']:.0f}% "
            f"(ACI 301 Table 4.2.1.1(b))"
        )
    return violations

# ACI 318 Table 26.4.3.1(b) / PRC-211.1-22 Table 4.7.4.1 — Required average
# compressive strength f'cr when NO data are available to establish a
# standard deviation. Exact piecewise metric form of the psi table
# (1 psi = 0.00689476 MPa):
#   f'c < 3000 psi (< 20.68 MPa):   f'cr = f'c + 1000 psi  (+6.895 MPa)
#   3000 ≤ f'c ≤ 5000 psi:          f'cr = f'c + 1200 psi  (+8.274 MPa)
#   f'c > 5000 psi (> 34.47 MPa):   f'cr = 1.10·f'c + 700 psi
# (PRC-211.1-22 Appendix B.6.1.3 illustrates the table path: 3500 psi
# specified → 4700 psi required average.)
ACI_NO_DATA_BREAK_3000PSI_MPA = 3000 * 0.00689476   # 20.68 MPa
ACI_NO_DATA_BREAK_5000PSI_MPA = 5000 * 0.00689476   # 34.47 MPa
ACI_NO_DATA_ADD_1000PSI_MPA = 1000 * 0.00689476     # 6.895 MPa
ACI_NO_DATA_ADD_1200PSI_MPA = 1200 * 0.00689476     # 8.274 MPa
ACI_NO_DATA_5000PSI_INTERCEPT_MPA = 700 * 0.00689476  # 4.826 MPa


def get_no_data_overdesign(specified_fc_mpa: float) -> float:
    """f'cr from ACI 318 Table 26.4.3.1(b) / PRC-211.1-22 Table 4.7.4.1.

    Exact piecewise formulas (no interpolation between breakpoints —
    each band carries its own rule, per the table).
    """
    fc = float(specified_fc_mpa)
    if fc < ACI_NO_DATA_BREAK_3000PSI_MPA:
        return round(fc + ACI_NO_DATA_ADD_1000PSI_MPA, 2)
    if fc <= ACI_NO_DATA_BREAK_5000PSI_MPA:
        return round(fc + ACI_NO_DATA_ADD_1200PSI_MPA, 2)
    return round(1.10 * fc + ACI_NO_DATA_5000PSI_INTERCEPT_MPA, 2)


# ACI PRC-211.1-22 Table 4.7.4.3 (ACI 301-20 Table 4.2.3.3(a)2) — k-factor
# for increasing the sample standard deviation when it is calculated from
# fewer than 30 strength tests. The table note permits linear interpolation
# for intermediate numbers of tests.
ACI_K_MODIFICATION_FACTORS: dict[int, float] = {
    15: 1.16,
    20: 1.08,
    25: 1.03,
    30: 1.00,
}


def modification_factor_k(num_tests: int) -> float:
    """Table 4.7.4.3 k-factor for a sample standard deviation from n tests.

    Args:
        num_tests: Number of strength tests the standard deviation is
            calculated from.

    Returns:
        k (1.00 at ≥ 30 tests; interpolated between 15 and 29).

    Raises:
        ValueError: for n < 15 — ACI 318 does not permit establishing s
            from fewer than 15 tests; use the no-data table instead
            (``get_no_data_overdesign`` / ``has_production_data=False``).
    """
    n = int(num_tests)
    if n < 15:
        raise ValueError(
            f"A sample standard deviation needs at least 15 strength tests "
            f"(ACI 301 Table 4.2.3.3(a)2 / PRC-211.1-22 Table 4.7.4.3); got "
            f"{n}. With fewer tests use the no-data required-average table "
            f"(Table 4.7.4.1 — has_production_data=False)."
        )
    if n >= 30:
        return 1.00
    ns = sorted(ACI_K_MODIFICATION_FACTORS)
    for lo, hi in zip(ns, ns[1:]):
        if lo <= n <= hi:
            k_lo = ACI_K_MODIFICATION_FACTORS[lo]
            k_hi = ACI_K_MODIFICATION_FACTORS[hi]
            return k_lo + (n - lo) / (hi - lo) * (k_hi - k_lo)
    return 1.00


# ACI 301 Table 4.2.2.6(c) — Exposure Class F3 assigned to PLAIN concrete
# carries its own row: max w/cm 0.45 and minimum f'c 4500 psi (31.0 MPa)
# instead of the reinforced-concrete F3 limits (PRC-211.1-22 Table 4.7.3b,
# last row).
F3_PLAIN_LIMITS: dict[str, float | None] = {
    "max_wc": 0.45,
    "min_fc_mpa": 31.0,
}


def get_f_class_limits(
    f_class: str, concrete_type: str = "reinforced"
) -> dict[str, float | None]:
    """F-class durability limits, honouring the F3 plain-concrete row."""
    if f_class == "F3" and concrete_type == "plain":
        return dict(F3_PLAIN_LIMITS)
    return dict(F_CLASS_LIMITS[f_class])


# PRC-211.1-22 §9.5 (Example 4) — paste volume PV is the sum of the
# cementitious and water absolute volumes as a percentage of the concrete
# volume. Example 4 Step 2 solves the cementitious contents that hit a
# target PV at a fixed w/cm and SCM proportion (metric restatement of the
# guide's Example-4 equation, which yields 288 lb cement for PV = 25 %,
# w/cm = 0.40 and 50 % slag at RD 2.90):
#   cement = PV_m3 × 1000 × (1 − p) / (wcm + (1 − p)/RD_c + p/RD_scm)
# where p is the SCM fraction of total cementitious by mass.
def paste_volume_percent(
    cement_kg: float,
    scm_kg: float,
    water_kg: float,
    cement_sg: float,
    scm_sg: float,
) -> float:
    """Paste volume (%) of the 1 m³ design volume (§9.5 Step 1)."""
    vol = (
        cement_kg / (cement_sg * 1000.0)
        + (scm_kg / (scm_sg * 1000.0) if scm_kg > 0 else 0.0)
        + water_kg / 1000.0
    )
    return round(vol * 100.0, 1)


def cementitious_for_target_paste_volume(
    target_pv_percent: float,
    wcm: float,
    scm_fraction: float,
    cement_sg: float,
    scm_sg: float,
) -> tuple[float, float, float]:
    """(cement, scm, water) kg/m³ hitting a target paste volume (Ex. 4).

    Keeps the w/cm and the SCM fraction p of total cementitious constant
    and solves the Example-4 Step-2 equation for the cement mass; water
    then follows as w/cm × total cementitious (Step 2 tail).

    For multiple SCMs pass their replacement-weighted mean specific
    gravity as ``scm_sg`` (single-value restatement of the guide's binary
    formula).
    """
    p = float(scm_fraction)
    pv_m3 = float(target_pv_percent) / 100.0
    denominator = wcm + (1.0 - p) / cement_sg + p / scm_sg
    cement = pv_m3 * 1000.0 * (1.0 - p) / denominator
    scm = cement * p / (1.0 - p) if p < 1.0 else 0.0
    water = wcm * (cement + scm)
    return cement, scm, water
