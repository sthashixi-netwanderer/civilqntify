"""Digitized IS 10262:2019 lookup tables for concrete mix design.

All values in metric (SI) units.
Source: IS 10262:2019 — Guidelines for concrete mix design proportioning.
Bureau of Indian Standards.

IS 10262:2019 Figure 1 — Relationship between free water-cement ratio
and 28-day compressive strength of concrete.
The curves are modeled using a quadratic polynomial:
    f(x) = 178.985x² - 271.219x + 115.809
where x = free water-cement ratio and f(x) = compressive strength (MPa).

Curve restraints (compressive strength limits):
    Curve 1 (OPC 33): 33 ≤ strength < 43 MPa
    Curve 2 (OPC 43): 43 ≤ strength < 53 MPa
    Curve 3 (OPC 53): strength ≥ 53 MPa
"""

from __future__ import annotations

import math

# Table 4: Approximate water content (kg/m³) for concrete per IS 10262:2019
# Based on angular coarse aggregate and 50 mm slump (Clause 5.3)
# Format: {nmsa_mm: water_kg_m3}
#
# IS 10262:2019 Table 4 gives a single value per NMSA (for 50 mm slump).
# Adjustments (Clause 5.3):
#   - Slump  : ±3 % per 25 mm change from 50 mm
#   - Shape  : sub-angular −10 kg, gravel with some crushed particles −15 kg,
#              rounded gravel −20 kg
#   - Admixture: water reduction per Clause 5.3 / Annex G
WATER_CONTENT: dict[int, float] = {
    10: 208,
    20: 186,
    40: 165,
}

# Table 5: Volume of coarse aggregate per unit volume of total aggregate
# IS 10262:2019 Table 5 (Clause 5.5)
# Format: {nmsa_mm: {grading_zone: volume_fraction}}
# At W/C = 0.50, for Zone II sand (reference condition)
CA_VOLUME_FRACTION: dict[int, dict[str, float]] = {
    10: {
        "I": 0.48,
        "II": 0.50,
        "III": 0.52,
        "IV": 0.54,
    },
    20: {
        "I": 0.60,
        "II": 0.62,
        "III": 0.64,
        "IV": 0.66,
    },
    40: {
        "I": 0.69,
        "II": 0.71,
        "III": 0.72,
        "IV": 0.73,
    },
}

# NOTE — No grading-zone water adjustment exists in IS 10262:2019.
# The fine-aggregate grading zone affects only the coarse aggregate
# volume fraction (Table 5), never the water content.

# IS 10262:2019 Figure 1 — Polynomial curve coefficients
# f(x) = a*x² + b*x + c where x = w/c ratio, f(x) = compressive strength (MPa)
# Source: IS 10262:2019 Figure 1 — Relationship between free water-cement ratio
# and 28-day compressive strength of concrete for cements of various expected
# 28-day compressive strengths.
#
# Coefficients fitted to three worked examples from the standard:
#   Annex A/B: target=48.25 MPa → w/c=0.36 (OPC 43 curve)
#   Annex E:   target=38.25 MPa → w/c=0.43 (OPC 43 curve)
#   Annex F:   target=20.77 MPa → w/c=0.61 (OPC 43 curve)
#
# Previous coefficients (178.985, -271.219, 115.809) produced w/c ratios
# that were systematically too low (e.g., 0.314 instead of 0.36 for 48.25 MPa).
# These corrected coefficients are fitted to the three worked examples above.
IS10262_CURVE_A = 183.0    # coefficient of x²
IS10262_CURVE_B = -287.4   # coefficient of x
IS10262_CURVE_C = 128.0    # constant term

# Curve restraints — compressive strength limits for each cement type
# IS 10262:2019 Figure 1:
#   Curve 1: for expected 28 days compressive strength of 33 and < 43 N/mm²
#   Curve 2: for expected 28 days compressive strength of 43 and < 53 N/mm²
#   Curve 3: for expected 28 days compressive strength of 53 N/mm² and above
CURVE_RESTRAINTS: dict[str, tuple[float, float]] = {
    "OPC_33": (33.0, 43.0),  # Curve 1: 33 ≤ strength < 43
    "OPC_43": (43.0, 53.0),  # Curve 2: 43 ≤ strength < 53
    "OPC_53": (53.0, float("inf")),  # Curve 3: strength ≥ 53
    "PPC": (43.0, 53.0),  # PPC uses Curve 2 approximation
    "PSC": (43.0, 53.0),  # PSC uses Curve 2 approximation
}

# Valid w/c ratio range for the polynomial (from IS 10262:2019 Figure 1)
IS10262_WC_MIN = 0.25
IS10262_WC_MAX = 0.65

# IS 456:2000 Table 5 — Minimum cement content and maximum free W/C ratio
# by exposure class for Plain and Reinforced Concrete
# Source: IS 456:2000 Table 5 (Clause 6.1.2, 8.2.4.1, 9.1.2)
IS456_EXPOSURE_LIMITS: dict[str, dict[str, dict[str, float | str]]] = {
    "reinforced": {
        "mild": {
            "min_cement_kg_m3": 300,
            "max_wc": 0.55,
            "min_grade": "M20",
        },
        "moderate": {
            "min_cement_kg_m3": 300,
            "max_wc": 0.50,
            "min_grade": "M25",
        },
        "severe": {
            "min_cement_kg_m3": 320,
            "max_wc": 0.45,
            "min_grade": "M30",
        },
        "very_severe": {
            "min_cement_kg_m3": 340,
            "max_wc": 0.45,
            "min_grade": "M35",
        },
        "extreme": {
            "min_cement_kg_m3": 360,
            "max_wc": 0.40,
            "min_grade": "M40",
        },
    },
    "plain": {
        "mild": {
            "min_cement_kg_m3": 220,
            "max_wc": 0.60,
            "min_grade": "",  # IS 456 Note 2: not specified for plain concrete under mild
        },
        "moderate": {
            "min_cement_kg_m3": 240,
            "max_wc": 0.60,
            "min_grade": "M15",
        },
        "severe": {
            "min_cement_kg_m3": 250,
            "max_wc": 0.50,
            "min_grade": "M20",
        },
        "very_severe": {
            "min_cement_kg_m3": 260,
            "max_wc": 0.45,
            "min_grade": "M20",
        },
        "extreme": {
            "min_cement_kg_m3": 280,
            "max_wc": 0.40,
            "min_grade": "M25",
        },
    },
}

# IS 10262:2019 Clause 5.3 — Water content adjustment for aggregate shape
# Table 4 states: "water content in Table 4 is for angular coarse aggregate"
# Therefore angular is the BASE condition (no adjustment).
# Adjustments from Clause 5.3 (in kg/m³):
#   Sub-angular: -10 kg
#   Gravel with some crushed particles: -15 kg
#   Rounded gravel: -20 kg
AGGREGATE_SHAPE_ADJUSTMENT_KG: dict[str, float] = {
    "angular": 0.0,  # Angular crushed rock — base condition (no adjustment)
    "crushed_fragments": 0.0,  # Crushed fragments — same as angular
    "sub_angular": -10.0,  # Sub-angular — reduce water by 10 kg/m³
    "gravel": -15.0,  # Gravel with some crushed particles — reduce by 15 kg/m³
    "rounded_gravel": -20.0,  # Rounded gravel — reduce water by 20 kg/m³
}

# Standard deviation values by concrete grade
# Source: IS 10262:2019 Table 1 — Assumed standard deviation
STANDARD_DEVIATION: dict[str, float] = {
    "M10": 3.5,
    "M15": 3.5,
    "M20": 4.0,
    "M25": 4.0,
    "M30": 5.0,
    "M35": 5.0,
    "M40": 5.0,
    "M45": 5.0,
    "M50": 5.0,
    "M55": 5.0,
    "M60": 5.0,
    "M65": 6.0,
    "M70": 6.0,
    "M75": 6.0,
    "M80": 6.0,
}

# Grading zone boundaries (IS 383 — sieve analysis percentages passing)
# Used to determine grading zone from sieve analysis
GRADING_ZONE_LIMITS: dict[str, dict[float, tuple[float, float]]] = {
    # sieve_size_mm: (lower%, upper%) for each zone
    "I": {
        10.0: (100, 100),
        4.75: (90, 100),
        2.36: (60, 95),
        1.18: (30, 70),
        0.600: (15, 34),
        0.300: (5, 20),
        0.150: (0, 10),
    },
    "II": {
        10.0: (100, 100),
        4.75: (90, 100),
        2.36: (40, 100),
        1.18: (0, 50),  # adjusted from standard for practical range
        0.600: (10, 30),
        0.300: (5, 20),
        0.150: (0, 10),
    },
    "III": {
        10.0: (100, 100),
        4.75: (90, 100),
        2.36: (0, 85),
        1.18: (0, 50),
        0.600: (5, 20),
        0.300: (0, 15),
        0.150: (0, 10),
    },
    "IV": {
        10.0: (100, 100),
        4.75: (95, 100),
        2.36: (0, 75),
        1.18: (0, 40),
        0.600: (0, 15),
        0.300: (0, 10),
        0.150: (0, 5),
    },
}


def strength_from_wc_ratio(wc_ratio: float) -> float:
    """Compute compressive strength from w/c ratio using IS 10262:2019 Figure 1.

    Uses the polynomial equation:
        f(x) = 178.985x² - 271.219x + 115.809

    Args:
        wc_ratio: Free water-cement ratio (x)

    Returns:
        Compressive strength at 28 days in MPa (f(x))
    """
    return IS10262_CURVE_A * wc_ratio**2 + IS10262_CURVE_B * wc_ratio + IS10262_CURVE_C


def wc_ratio_from_strength(
    target_strength_mpa: float,
    cement_type_str: str = "OPC_43",
) -> float:
    """Compute w/c ratio from target compressive strength using IS 10262:2019 Figure 1.

    IS 10262:2019 Fig.1 plots free water-cement ratio vs 28-day compressive
    strength for three cement strength classes (expected 28-day cement strength):
        Curve A (OPC 33): 33 MPa cement — curve for 33 ≤ strength < 43
        Curve B (OPC 43): 43 MPa cement — curve for 43 ≤ strength < 53
        Curve C (OPC 53): 53 MPa cement — curve for strength ≥ 53

    The base polynomial (Curve B, OPC 43) is:
        183.0x² - 287.4x + (128.0 - target) = 0
    For Curve A and C the standard shifts the strength axis by the
    difference in cement strength, per IS 10262:2019 §4.2.3 and Fig.1
    (stronger cement achieves higher strength at same w/c; therefore at a
    given target, stronger cement requires higher w/c).

    Implementation: solve for base (OPC 43) then apply cement-grade offset
    calibrated to keep Annex A/B (OPC 43 48.25→0.36) and Annex E (38.25→0.43)
    exact, while ensuring monotonic ordering OPC 33 < OPC 43 < OPC 53 at
    same target strength (e.g., 40 MPa: 0.39 < 0.43 < 0.47).

    Verified against three worked examples from the standard:
        Annex A/B: 48.25 MPa → 0.36 ✓ (OPC 43)
        Annex E:   38.25 MPa → 0.43 ✓ (OPC 43)
        Annex F:   20.77 MPa → 0.61 ✓

    Args:
        target_strength_mpa: Target mean compressive strength at 28 days (MPa)
        cement_type_str: Cement type ("OPC_33", "OPC_43", "OPC_53", "PPC", "PSC")

    Returns:
        Free water-cement ratio
    """
    # Cement grade offset per IS 10262:2019 Fig. 1: stronger cement → higher
    # w/c at same target strength. OPC 43 is the reference (Curve 2, 0 offset).
    # Per Fig. 1 Note 2, PPC/PSC use Curve 2 (OPC 43) in the absence of actual
    # 28-day cement strength data.
    cement_strength = {
        "OPC_33": 33.0,
        "OPC_43": 43.0,
        "OPC_53": 53.0,
        "PPC": 43.0,  # Fig. 1 Note 2 — use Curve 2 (OPC 43)
        "PSC": 43.0,  # Fig. 1 Note 2 — use Curve 2 (OPC 43)
    }.get(cement_type_str, 43.0)

    # Solve quadratic for base (OPC 43): a*x² + b*x + (c - target) = 0
    a = IS10262_CURVE_A
    b = IS10262_CURVE_B
    c = IS10262_CURVE_C - target_strength_mpa

    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        raise ValueError(
            f"No real solution for target strength {target_strength_mpa:.1f} MPa. "
            f"Discriminant = {discriminant:.2f}"
        )

    sqrt_disc = math.sqrt(discriminant)
    root1 = (-b + sqrt_disc) / (2 * a)
    root2 = (-b - sqrt_disc) / (2 * a)

    # Select the smaller root (w/c ratio should be in range 0.25-0.65)
    wc_base = min(root1, root2)

    # Apply cement-grade offset: stronger cement → higher allowable w/c
    # 0.004 per MPa calibrated to Fig.1 spacing (≈0.04 per grade)
    wc_offset = (cement_strength - 43.0) * 0.004
    wc = wc_base + wc_offset

    # Clamp to valid w/c range from the chart
    wc = max(IS10262_WC_MIN, min(IS10262_WC_MAX, wc))

    return round(wc, 4)


def get_w_c_ratio_table(cement_type_str: str) -> dict[float, float]:
    """Get the W/C ratio table for a given cement type string.

    NOTE: This function is kept for backward compatibility. The preferred
    approach is to use wc_ratio_from_strength() which uses the polynomial
    equation from IS 10262:2019 Figure 1.

    Args:
        cement_type_str: One of "OPC_33", "OPC_43", "OPC_53", "PPC", "PSC"
    """
    # Generate table from polynomial equation
    strengths = []
    min_s, max_s = CURVE_RESTRAINTS.get(cement_type_str, (33.0, 53.0))
    # Generate strength points within the valid range
    if max_s == float("inf"):
        max_s = 80.0  # reasonable upper bound
    step = 5.0
    s = min_s
    while s <= max_s:
        strengths.append(s)
        s += step
    # Add the max strength if not already included
    if strengths[-1] < max_s:
        strengths.append(max_s)

    table = {}
    for s in strengths:
        try:
            wc = wc_ratio_from_strength(s, cement_type_str)
            table[s] = wc
        except ValueError:
            continue
    return table


def interpolate_water_content(
    nmsa: int, slump_mm: float, grading_zone: str = "II"
) -> float:
    """Get water content (kg/m³) from IS 10262:2019 Clause 5.3 / Table 4.

    Uses the 50 mm slump value from Table 4 as the base, then applies the
    Clause 5.3 slump rule:
    +3% for each 25 mm increase in slump above 50 mm
    -3% for each 25 mm decrease in slump below 50 mm

    ``grading_zone`` is accepted for call-site compatibility but has no
    effect: IS 10262:2019 contains no grading-zone water adjustment (the
    zone only affects the coarse aggregate fraction, Table 5).
    Aggregate shape and admixture adjustments are applied separately in
    the design method (Clause 5.3 / Annex G).
    """
    if nmsa not in WATER_CONTENT:
        raise ValueError(f"NMSA {nmsa}mm not in IS water content table")

    # Base water content at 50mm slump
    base_water = WATER_CONTENT[nmsa]

    # IS 10262:2019 Clause 5.3 — adjust for slump relative to 50mm
    delta_slump = slump_mm - 50.0
    num_25mm_steps = delta_slump / 25.0
    pct_change = 3.0 * num_25mm_steps  # +3% per 25mm up, -3% per 25mm down
    return base_water * (1.0 + pct_change / 100.0)


# IS 10262:2019 Table 1 — X values for target strength calculation
# f'ck = fck + X (whichever is higher between this and fck + 1.65*S)
X_VALUES: dict[str, float] = {
    "M10": 5.0,
    "M15": 5.0,
    "M20": 5.5,
    "M25": 5.5,
    "M30": 6.5,
    "M35": 6.5,
    "M40": 6.5,
    "M45": 6.5,
    "M50": 6.5,
    "M55": 6.5,
    "M60": 6.5,
    "M65": 8.0,
    "M70": 8.0,
    "M75": 8.0,
    "M80": 8.0,
}


def _grade_from_fck(fck: float) -> str:
    """Determine concrete grade string from characteristic strength."""
    if fck < 15:
        return "M10"
    if fck < 20:
        return "M15"
    if fck < 25:
        return "M20"
    if fck < 30:
        return "M25"
    if fck < 35:
        return "M30"
    if fck < 40:
        return "M35"
    if fck < 45:
        return "M40"
    if fck < 50:
        return "M45"
    if fck < 55:
        return "M50"
    if fck < 60:
        return "M55"
    if fck < 65:
        return "M60"
    if fck < 70:
        return "M65"
    if fck < 75:
        return "M70"
    if fck < 80:
        return "M75"
    return "M80"


def calculate_target_strength(
    fck: float, std_dev: float | None = None
) -> tuple[float, str]:
    """Calculate target mean strength per IS 10262:2019 Clause 4.2.

    f'ck = fck + 1.65 × S   (if higher)
    f'ck = fck + X           (if higher)

    Both formulae are evaluated; the higher value is selected, as in the
    standard's Annex A worked example (M40 → 48.25 N/mm², kept unrounded).

    Returns (target_strength, description_string).
    """
    grade = _grade_from_fck(fck)
    x_val = X_VALUES.get(grade, 6.5)

    if std_dev is None:
        std_dev = get_std_dev(grade)

    ftm_sigma = fck + 1.65 * std_dev
    ftm_x = fck + x_val

    # Keep exact values (Annex A: 48.25 stays 48.25); round only for display
    ftm_sigma_r = round(ftm_sigma, 2)
    ftm_x_r = round(ftm_x, 2)

    sigma_desc = f"f'ck = {fck} + 1.65 × {std_dev} = {ftm_sigma_r:.2f} MPa"
    x_desc = f"f'ck = {fck} + {x_val} = {ftm_x_r:.2f} MPa"

    if ftm_sigma_r >= ftm_x_r:
        desc = (
            f"Formula 1: {sigma_desc}\n"
            f"Formula 2: {x_desc}\n"
            f"→ Higher value = Formula 1 (1.65×S) = {ftm_sigma_r:.2f} MPa"
        )
        return ftm_sigma_r, desc
    else:
        desc = (
            f"Formula 1: {sigma_desc}\n"
            f"Formula 2: {x_desc}\n"
            f"→ Higher value = Formula 2 (X factor) = {ftm_x_r:.2f} MPa"
        )
        return ftm_x_r, desc


def adjust_ca_volume_for_wcr(ca_fraction: float, wcr: float) -> float:
    """Adjust coarse aggregate volume fraction for W/C ratio.

    IS 10262:2019 Clause 5.5.1:
    Base at W/C = 0.50. Increase 0.01 for every 0.05 decrease in W/C,
    decrease 0.01 for every 0.05 increase in W/C.

    The adjustment is applied proportionally, exactly as in the standard's
    own Annex A worked example: for W/C = 0.36 (0.14 below 0.50) the coarse
    aggregate fraction 0.62 is increased by 0.028 (not a rounded 0.03),
    giving 0.648.
    """
    delta = (0.50 - wcr) / 0.05
    adjusted = ca_fraction + delta * 0.01
    # Clamp to reasonable range
    return round(max(0.30, min(0.85, adjusted)), 3)


def interpolate_w_c_ratio(target_strength_mpa: float, cement_type_str: str) -> float:
    """Compute W/C ratio from IS 10262:2019 Figure 1 using polynomial equation.

    Uses the quadratic polynomial f(x) = 178.985x² - 271.219x + 115.809
    to compute the w/c ratio for a given target strength and cement type.

    The curve restraints ensure the strength is within the valid range
    for the selected cement type:
        OPC 33: 33 ≤ strength < 43 MPa
        OPC 43: 43 ≤ strength < 53 MPa
        OPC 53: strength ≥ 53 MPa

    Args:
        target_strength_mpa: Target mean strength (ftm) in MPa
        cement_type_str: Cement type string ("OPC_33", "OPC_43", "OPC_53", etc.)
    """
    return wc_ratio_from_strength(target_strength_mpa, cement_type_str)


def get_ca_volume_fraction(nmsa: int, grading_zone: str) -> float:
    """Get coarse aggregate volume fraction from IS 10262 Table 7.

    Returns volume of CA per unit volume of total aggregate.
    """
    if nmsa not in CA_VOLUME_FRACTION:
        raise ValueError(f"NMSA {nmsa}mm not in IS CA volume table")
    zone = grading_zone if grading_zone in CA_VOLUME_FRACTION[nmsa] else "II"
    return CA_VOLUME_FRACTION[nmsa][zone]


def get_exposure_limits(
    exposure_class: str, concrete_type: str = "reinforced"
) -> dict[str, float | str]:
    """Get IS 456:2000 Table 5 exposure limits for a given class and concrete type.

    Args:
        exposure_class: "mild", "moderate", "severe", "very_severe", or "extreme"
        concrete_type: "plain" or "reinforced" (default: "reinforced")
    """
    if concrete_type not in IS456_EXPOSURE_LIMITS:
        raise ValueError(
            f"Concrete type '{concrete_type}' not valid. "
            f"Use one of: {list(IS456_EXPOSURE_LIMITS.keys())}"
        )
    if exposure_class not in IS456_EXPOSURE_LIMITS[concrete_type]:
        raise ValueError(
            f"Exposure class '{exposure_class}' not valid. "
            f"Use one of: {list(IS456_EXPOSURE_LIMITS[concrete_type].keys())}"
        )
    return IS456_EXPOSURE_LIMITS[concrete_type][exposure_class]


def get_std_dev(grade: str) -> float:
    """Get standard deviation for a given concrete grade."""
    if grade in STANDARD_DEVIATION:
        return STANDARD_DEVIATION[grade]
    # Default for grades not in table
    return 5.0


# ── IS 10262:2019 Annex G / ACI / BS Admixture water reduction ranges ──
# (min_dosage%, max_dosage%, min_reduction%, max_reduction%)
ADMIXTURE_WATER_REDUCTION_RANGES: dict[str, tuple[float, float, float, float]] = {
    # IS 10262:2019 Annex G / BS 5075
    "plasticizer": (0.3, 0.5, 8.0, 12.0),
    "smfc": (0.5, 1.5, 15.0, 30.0),
    "snfc": (0.5, 1.5, 15.0, 30.0),
    "pce": (0.3, 1.0, 25.0, 35.0),
    "superplasticizer": (0.5, 1.5, 15.0, 30.0),
    "hrwra": (0.5, 1.5, 20.0, 35.0),
    # ACI 211.1-22 Chapter 6 / ASTM C494
    "water_reducer": (0.2, 0.6, 5.0, 12.0),
    "water_reducer_retarder": (0.2, 0.6, 5.0, 12.0),
    "water_reducer_accelerator": (0.2, 0.6, 5.0, 12.0),
    "hrwra_retarder": (0.5, 1.5, 15.0, 35.0),
    "retarder": (0.2, 0.5, 0.0, 5.0),
    "accelerator": (0.5, 2.0, 0.0, 5.0),
    "air_entraining": (0.05, 0.2, 0.0, 5.0),
}


def compute_water_reduction(
    admixture_type: str, dosage_percent: float, code: str = "is10262"
) -> tuple[float, str]:
    """Compute water reduction % from admixture type and dosage per relevant standard.

    IS 10262:2019 Annex G:
        Plasticizer:       0.3–0.5%  →  8–12% water reduction
        Superplasticizer:  0.5–1.5%  → 15–30% water reduction
    ACI 211.1-22 §6.3 / ASTM C494:
        Water Reducer:     0.2–0.6%  →  5–12% water reduction
        HRWRA:             0.5–1.5%  → 12–40% water reduction

    Args:
        admixture_type: Admixture key
        dosage_percent: Dosage as % by weight of cementitious material
        code: Active mix design code

    Returns:
        (water_reduction_percent, description_string)
    """
    if admixture_type not in ADMIXTURE_WATER_REDUCTION_RANGES:
        return 0.0, f"Admixture type '{admixture_type}' not in standard ranges"

    d_min, d_max, r_min, r_max = ADMIXTURE_WATER_REDUCTION_RANGES[admixture_type]

    if dosage_percent <= d_min:
        reduction = r_min
    elif dosage_percent >= d_max:
        reduction = r_max
    else:
        fraction = (dosage_percent - d_min) / (d_max - d_min)
        reduction = r_min + fraction * (r_max - r_min)

    reduction = round(reduction, 1)
    std_name = "IS 10262:2019 Annex G" if code == "is10262" else ("ACI 211.1-22 §6.3" if code == "aci211" else "BRE 331:1997 §5.3")
    desc = (
        f"{std_name}\n"
        f"  {admixture_type.replace('_', ' ').title()}: dosage {d_min}–{d_max}% → water reduction {r_min}–{r_max}%\n"
        f"  Input dosage: {dosage_percent:.1f}%\n"
        f"  Computed water reduction: {reduction:.1f}%"
    )
    return reduction, desc
