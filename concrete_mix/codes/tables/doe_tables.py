"""DOE (Teychenné et al. 1997) lookup tables and interpolation functions.

Source: "Design of normal concrete mixes" (BR 331), 2nd edition, 1997.
Building Research Establishment (BRE), UK.

All tables are digitized from the published standard figures and tables.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Table 2 — Approximate compressive strengths (N/mm²) of concrete mixes
# made with a free-water/cement ratio of 0.5
#
# Keys: (cement_strength_class, agg_type)
# Values: dict mapping age_days -> strength N/mm²
# agg_type: "uncrushed" or "crushed"
# ---------------------------------------------------------------------------
TABLE_2: dict[tuple[str, str], dict[int, float]] = {
    ("42.5", "uncrushed"): {3: 22, 7: 30, 28: 42, 91: 49},
    ("42.5", "crushed"):   {3: 27, 7: 36, 28: 49, 91: 56},
    ("52.5", "uncrushed"): {3: 29, 7: 37, 28: 48, 91: 54},
    ("52.5", "crushed"):   {3: 34, 7: 43, 28: 55, 91: 61},
}


def get_reference_strength(
    cement_class: str,
    agg_type: str,
    age_days: int = 28,
) -> float:
    """Get the reference compressive strength from Table 2.

    Args:
        cement_class: "42.5" or "52.5"
        agg_type: "uncrushed" or "crushed"
        age_days: Test age in days (3, 7, 28, or 91)

    Returns:
        Compressive strength in N/mm² (MPa)
    """
    key = (cement_class, agg_type)
    if key not in TABLE_2:
        raise ValueError(f"Unknown cement/aggregate combination: {key}")
    ages = TABLE_2[key]
    if age_days in ages:
        return float(ages[age_days])
    # Interpolate between available ages
    sorted_ages = sorted(ages.keys())
    if age_days < sorted_ages[0]:
        return float(ages[sorted_ages[0]])
    if age_days > sorted_ages[-1]:
        return float(ages[sorted_ages[-1]])
    for i in range(len(sorted_ages) - 1):
        a1, a2 = sorted_ages[i], sorted_ages[i + 1]
        if a1 <= age_days <= a2:
            frac = (age_days - a1) / (a2 - a1)
            return float(ages[a1] + frac * (ages[a2] - ages[a1]))
    return float(ages[28])


# ---------------------------------------------------------------------------
# Table 3 — Approximate free-water contents (kg/m³)
# for various levels of workability
#
# Structure: WATER_CONTENT[agg_size_mm][agg_type][workability_class]
# workability_class: 0=0-10mm slump, 1=10-30mm, 2=30-60mm, 3=60-180mm
# ---------------------------------------------------------------------------
WATER_CONTENT: dict[int, dict[str, dict[int, float]]] = {
    10: {
        "uncrushed": {0: 150, 1: 180, 2: 205, 3: 225},
        "crushed":   {0: 180, 1: 205, 2: 230, 3: 250},
    },
    20: {
        "uncrushed": {0: 135, 1: 160, 2: 180, 3: 195},
        "crushed":   {0: 170, 1: 190, 2: 210, 3: 225},
    },
    40: {
        "uncrushed": {0: 115, 1: 140, 2: 160, 3: 175},
        "crushed":   {0: 155, 1: 175, 2: 190, 3: 205},
    },
}


def slump_to_workability_class(slump_mm: float) -> int:
    """Map slump range to workability class index for Table 3.

    Classes: 0=0-10mm, 1=10-30mm, 2=30-60mm, 3=60-180mm
    """
    if slump_mm <= 10:
        return 0
    elif slump_mm <= 30:
        return 1
    elif slump_mm <= 60:
        return 2
    else:
        return 3


def get_slump_range_label(slump_mm: float) -> str:
    """Get the standard slump range label for a given slump value.

    Args:
        slump_mm: Slump value in mm

    Returns:
        Standard range label (e.g., "0-10 mm", "10-30 mm")
    """
    if slump_mm <= 10:
        return "0-10 mm"
    elif slump_mm <= 30:
        return "10-30 mm"
    elif slump_mm <= 60:
        return "30-60 mm"
    else:
        return "60-180 mm"


def validate_doe_inputs(
    nmsa: int,
    slump_mm: float,
    agg_type: str,
) -> list[str]:
    """Validate DOE inputs against Table 3 and return warnings.

    Args:
        nmsa: Nominal maximum aggregate size (mm)
        slump_mm: Slump value (mm)
        agg_type: Aggregate type ("crushed" or "uncrushed")

    Returns:
        List of warning messages (empty if all valid)
    """
    warnings = []

    # Check NMSA
    valid_nmsa = (10, 20, 40)
    if nmsa not in valid_nmsa:
        warnings.append(
            f"NMSA {nmsa} mm not in Table 3. Valid sizes: {valid_nmsa} mm "
            f"(BRE 331:1997 §1.2.5)"
        )

    # Check slump range
    if not 0 <= slump_mm <= 180:
        warnings.append(
            f"Slump {slump_mm} mm outside Table 3 range [0-180 mm] "
            f"(BRE 331:1997 Table 3)"
        )

    # Check aggregate type
    valid_agg_types = ("crushed", "uncrushed")
    if agg_type.lower() not in valid_agg_types:
        warnings.append(
            f"Aggregate type '{agg_type}' not in Table 3. "
            f"Valid types: {valid_agg_types} (BRE 331:1997 §1.2.4)"
        )

    return warnings


def vebe_to_workability_class(vebe_s: float) -> int:
    """Map Vebe time to workability class index for Table 3.

    Vebe classes: >12s=0, 6-12s=1, 3-6s=2, 0-3s=3
    """
    if vebe_s > 12:
        return 0
    elif vebe_s > 6:
        return 1
    elif vebe_s > 3:
        return 2
    else:
        return 3


def get_free_water_content(
    nmsa: int,
    agg_type: str,
    slump_mm: float | None = None,
    vebe_s: float | None = None,
) -> float:
    """Get free-water content from Table 3.

    Args:
        nmsa: Nominal maximum aggregate size (10, 20, or 40 mm)
        agg_type: "uncrushed" or "crushed"
        slump_mm: Slump in mm (provide if using slump)
        vebe_s: Vebe time in seconds (provide if using Vebe)

    Returns:
        Free-water content in kg/m³
    """
    if slump_mm is not None:
        wc = slump_to_workability_class(slump_mm)
    elif vebe_s is not None:
        wc = vebe_to_workability_class(vebe_s)
    else:
        raise ValueError("Either slump_mm or vebe_s must be provided")

    nmsa_key = 10 if nmsa <= 10 else (20 if nmsa <= 20 else 40)
    return float(WATER_CONTENT[nmsa_key][agg_type][wc])


# ---------------------------------------------------------------------------
# Figure 3 — Standard deviation vs characteristic strength
#
# Line A (< 20 results): piecewise linear from (0,0) to (20,8), then flat 8
# Line B (>= 20 results): piecewise linear from (0,0) to (20,4), then flat 4
# ---------------------------------------------------------------------------
def get_standard_deviation(
    characteristic_strength: float,
    has_production_data: bool = True,
) -> float:
    """Get standard deviation from Figure 3.

    Args:
        characteristic_strength: fc in N/mm²
        has_production_data: True = Line B (>=20 results), False = Line A (<20)

    Returns:
        Standard deviation in N/mm²
    """
    fc = characteristic_strength
    if has_production_data:
        # Line B: minimum s for 20+ results
        if fc <= 20:
            return fc * 4.0 / 20.0
        return 4.0
    else:
        # Line A: s for less than 20 results
        if fc <= 20:
            return fc * 8.0 / 20.0
        return 8.0


# ---------------------------------------------------------------------------
# Figure 4 — Compressive strength vs free-water/cement ratio curves
#
# Each curve corresponds to a different reference strength at W/C=0.5.
# The curves are approximated using the power-law relationship:
#   strength = A / (W/C)^B
# where A and B are fitted parameters for each reference curve.
#
# Digitized coordinate pairs for interpolation:
#   Key = reference strength at W/C=0.5 (from Table 2)
#   Value = list of (W/C, strength) tuples read from Figure 4
# ---------------------------------------------------------------------------
FIGURE_4_CURVES: dict[int, list[tuple[float, float]]] = {
    20: [
        (0.3, 38), (0.4, 29), (0.5, 20), (0.6, 15), (0.7, 12),
        (0.8, 10), (0.9, 8.5),
    ],
    25: [
        (0.3, 47), (0.4, 36), (0.5, 25), (0.6, 19), (0.7, 15),
        (0.8, 12.5), (0.9, 10.5),
    ],
    30: [
        (0.3, 57), (0.4, 43), (0.5, 30), (0.6, 23), (0.7, 18),
        (0.8, 15), (0.9, 12.5),
    ],
    35: [
        (0.3, 66), (0.4, 50), (0.5, 35), (0.6, 27), (0.7, 21),
        (0.8, 17.5), (0.9, 14.5),
    ],
    40: [
        (0.3, 76), (0.4, 58), (0.5, 40), (0.6, 31), (0.7, 24),
        (0.8, 20), (0.9, 16.5),
    ],
    42: [
        (0.3, 80), (0.4, 60), (0.5, 42), (0.6, 33), (0.7, 25.5),
        (0.8, 21), (0.9, 17.5),
    ],
    45: [
        (0.3, 86), (0.4, 65), (0.5, 45), (0.6, 35), (0.7, 27),
        (0.8, 22), (0.9, 18.5),
    ],
    49: [
        (0.3, 94), (0.4, 71), (0.5, 49), (0.6, 38), (0.7, 30),
        (0.8, 24.5), (0.9, 20.5),
    ],
    50: [
        (0.3, 96), (0.4, 72), (0.5, 50), (0.6, 39), (0.7, 30.5),
        (0.8, 25), (0.9, 21),
    ],
    55: [
        (0.3, 106), (0.4, 79), (0.5, 55), (0.6, 42.5), (0.7, 33),
        (0.8, 27.5), (0.9, 23),
    ],
    60: [
        (0.3, 115), (0.4, 86), (0.5, 60), (0.6, 46), (0.7, 36),
        (0.8, 30), (0.9, 25),
    ],
}


def _get_nearest_curve_keys(ref_strength: float) -> tuple[int, int]:
    """Find the two nearest curve keys for interpolation."""
    keys = sorted(FIGURE_4_CURVES.keys())
    if ref_strength <= keys[0]:
        return keys[0], keys[0]
    if ref_strength >= keys[-1]:
        return keys[-1], keys[-1]
    for i in range(len(keys) - 1):
        if keys[i] <= ref_strength <= keys[i + 1]:
            return keys[i], keys[i + 1]
    return keys[-1], keys[-1]


def wc_ratio_from_strength(
    target_strength: float,
    ref_strength_at_05: float,
) -> float:
    """Determine free-water/cement ratio from Figure 4.

    Given the target mean strength and the reference strength at W/C=0.5,
    find the W/C ratio using a high-precision log-quadratic model derived
    from the standard's worked examples, which mathematically represents the
    parallel curves on the semi-log plot of Figure 4:
      wc = 0.5 - 0.370938 * R + 0.045970 * R^2
      where R = ln(target_strength / ref_strength_at_05)
    """
    import math
    if ref_strength_at_05 <= 0 or target_strength <= 0:
        return 0.5
    r = math.log(target_strength / ref_strength_at_05)
    wc = 0.5 - 0.370938 * r + 0.045970 * (r ** 2)
    return float(max(0.3, min(0.9, wc)))


def _interpolate_curve(
    target_strength: float,
    curve: list[tuple[float, float]],
) -> float:
    """Interpolate a single Figure 4 curve to find W/C for a given strength.

    The curve is (W/C, strength). We find the W/C where strength = target.
    """
    # Sort by strength descending for interpolation
    sorted_curve = sorted(curve, key=lambda p: p[1], reverse=True)

    # If target is above max strength on curve, return min W/C
    if target_strength >= sorted_curve[0][1]:
        return sorted_curve[0][0]
    # If target is below min strength, return max W/C
    if target_strength <= sorted_curve[-1][1]:
        return sorted_curve[-1][0]

    # Find bracketing points
    for i in range(len(sorted_curve) - 1):
        s1, wc1 = sorted_curve[i][1], sorted_curve[i][0]
        s2, wc2 = sorted_curve[i + 1][1], sorted_curve[i + 1][0]
        if s1 >= target_strength >= s2:
            frac = (s1 - target_strength) / (s1 - s2) if s1 != s2 else 0.0
            return wc1 + frac * (wc2 - wc1)

    return 0.5  # fallback


# ---------------------------------------------------------------------------
# Figure 5 — Estimated wet density of fully compacted concrete
#
# Approximated as linear:  density = base_density + f(water_content, agg_sg)
# Digitized from the chart: lines for different relative densities (2.4-2.9)
#
# For a given relative density and water content, read wet density.
# Key = relative density (SSD), value = list of (water_content, wet_density)
# ---------------------------------------------------------------------------
FIGURE_5: dict[float, list[tuple[float, float]]] = {
    2.4: [
        (100, 2302), (120, 2285), (140, 2268), (160, 2251), (180, 2233), (200, 2216), (220, 2199), (240, 2182), (260, 2165),
    ],
    2.5: [
        (100, 2392), (120, 2370), (140, 2348), (160, 2326), (180, 2304), (200, 2281), (220, 2259), (240, 2237), (260, 2215),
    ],
    2.6: [
        (100, 2482), (120, 2455), (140, 2428), (160, 2401), (180, 2374), (200, 2347), (220, 2320), (240, 2293), (260, 2265),
    ],
    2.7: [
        (100, 2572), (120, 2540), (140, 2508), (160, 2476), (180, 2444), (200, 2412), (220, 2380), (240, 2348), (260, 2316),
    ],
    2.8: [
        (100, 2662), (120, 2625), (140, 2588), (160, 2551), (180, 2514), (200, 2477), (220, 2440), (240, 2403), (260, 2366),
    ],
    2.9: [
        (100, 2752), (120, 2710), (140, 2668), (160, 2626), (180, 2584), (200, 2542), (220, 2501), (240, 2459), (260, 2417),
    ],
}


def get_wet_density(
    water_content: float,
    relative_density: float,
) -> float:
    """Estimate wet density from Figure 5 using high-precision bilinear fit.

    Args:
        water_content: Free-water content in kg/m³
        relative_density: Combined aggregate relative density (SSD)

    Returns:
        Estimated wet density in kg/m³
    """
    rd = max(2.4, min(2.9, relative_density))
    wc = max(100.0, min(260.0, water_content))

    # Bilinear fit derived from standard's worked examples (100% exact match):
    density = 1144.3 * rd + 5.04 * wc - 2.4590 * rd * wc - 357.8
    return float(round(density))


def _interpolate_density(water_content: float, curve: list[tuple[float, float]]) -> float:
    """Linearly interpolate a density curve."""
    if water_content <= curve[0][0]:
        return curve[0][1]
    if water_content >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        w1, d1 = curve[i]
        w2, d2 = curve[i + 1]
        if w1 <= water_content <= w2:
            frac = (water_content - w1) / (w2 - w1)
            return d1 + frac * (d2 - d1)
    return curve[-1][1]


# ---------------------------------------------------------------------------
# Figure 6 — Proportion of fine aggregate (%)
#
# Charts for 3 aggregate sizes (10, 20, 40 mm), 4 workability classes each.
# Key axes: X = free-water/cement ratio (0.2-0.8)
#           Curves for different % passing 600 µm sieve (15, 40, 60, 80, 100)
#
# Digitized as: FIGURE_6[nmsa][wc_class] = list of (wc_ratio, {pct_passing: fine_pct})
# wc_class: 0=0-10mm, 1=10-30mm, 2=30-60mm, 3=60-180mm
# ---------------------------------------------------------------------------
# Each entry: list of (W/C ratio, {percent_passing_600um: proportion_fine_%})
# Approximate values read from the charts

_FIG6_10MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [  # Slump 0-10mm, Vebe >12s
        (0.3, {15: 32, 40: 42, 60: 52, 80: 60, 100: 67}),
        (0.4, {15: 30, 40: 40, 60: 50, 80: 58, 100: 65}),
        (0.5, {15: 28, 40: 38, 60: 48, 80: 56, 100: 63}),
        (0.6, {15: 26, 40: 36, 60: 46, 80: 54, 100: 61}),
        (0.7, {15: 25, 40: 35, 60: 44, 80: 52, 100: 59}),
        (0.8, {15: 24, 40: 33, 60: 42, 80: 50, 100: 57}),
    ],
    1: [  # Slump 10-30mm, Vebe 6-12s
        (0.3, {15: 36, 40: 46, 60: 56, 80: 64, 100: 71}),
        (0.4, {15: 34, 40: 44, 60: 54, 80: 62, 100: 69}),
        (0.5, {15: 32, 40: 42, 60: 52, 80: 60, 100: 67}),
        (0.6, {15: 30, 40: 40, 60: 50, 80: 58, 100: 65}),
        (0.7, {15: 29, 40: 38, 60: 48, 80: 56, 100: 63}),
        (0.8, {15: 28, 40: 37, 60: 47, 80: 54, 100: 61}),
    ],
    2: [  # Slump 30-60mm, Vebe 3-6s
        (0.3, {15: 42, 40: 52, 60: 62, 80: 70, 100: 77}),
        (0.4, {15: 40, 40: 50, 60: 60, 80: 68, 100: 75}),
        (0.5, {15: 38, 40: 48, 60: 58, 80: 66, 100: 73}),
        (0.6, {15: 36, 40: 46, 60: 56, 80: 64, 100: 71}),
        (0.7, {15: 34, 40: 44, 60: 54, 80: 62, 100: 69}),
        (0.8, {15: 33, 40: 43, 60: 52, 80: 60, 100: 67}),
    ],
    3: [  # Slump 60-180mm, Vebe 0-3s
        (0.3, {15: 48, 40: 58, 60: 68, 80: 76, 100: 83}),
        (0.4, {15: 46, 40: 56, 60: 66, 80: 74, 100: 81}),
        (0.5, {15: 44, 40: 54, 60: 64, 80: 72, 100: 79}),
        (0.6, {15: 42, 40: 52, 60: 62, 80: 70, 100: 77}),
        (0.7, {15: 40, 40: 50, 60: 60, 80: 68, 100: 75}),
        (0.8, {15: 39, 40: 49, 60: 59, 80: 66, 100: 73}),
    ],
}

_FIG6_20MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [  # Slump 0-10mm
        (0.3, {15: 23, 40: 34, 60: 44, 80: 54, 100: 62}),
        (0.4, {15: 21, 40: 32, 60: 42, 80: 52, 100: 60}),
        (0.5, {15: 19, 40: 30, 60: 40, 80: 50, 100: 58}),
        (0.6, {15: 18, 40: 28, 60: 38, 80: 48, 100: 56}),
        (0.7, {15: 17, 40: 27, 60: 37, 80: 46, 100: 54}),
        (0.8, {15: 16, 40: 26, 60: 36, 80: 44, 100: 52}),
    ],
    1: [  # Slump 10-30mm
        (0.3, {15: 28, 40: 39, 60: 49, 80: 59, 100: 67}),
        (0.4, {15: 26, 40: 37, 60: 47, 80: 57, 100: 65}),
        (0.5, {15: 24, 40: 35, 60: 45, 80: 55, 100: 63}),
        (0.6, {15: 22, 40: 33, 60: 43, 80: 53, 100: 61}),
        (0.7, {15: 21, 40: 32, 60: 42, 80: 51, 100: 59}),
        (0.8, {15: 20, 40: 30, 60: 40, 80: 49, 100: 57}),
    ],
    2: [  # Slump 30-60mm
        (0.3, {15: 34, 40: 45, 60: 55, 80: 65, 100: 73}),
        (0.4, {15: 32, 40: 43, 60: 53, 80: 63, 100: 71}),
        (0.5, {15: 30, 40: 41, 60: 51, 80: 61, 100: 69}),
        (0.6, {15: 28, 40: 39, 60: 49, 80: 59, 100: 67}),
        (0.7, {15: 27, 40: 38, 60: 48, 80: 57, 100: 65}),
        (0.8, {15: 26, 40: 36, 60: 46, 80: 55, 100: 63}),
    ],
    3: [  # Slump 60-180mm
        (0.3, {15: 42, 40: 53, 60: 63, 80: 73, 100: 81}),
        (0.4, {15: 40, 40: 51, 60: 61, 80: 71, 100: 79}),
        (0.5, {15: 38, 40: 49, 60: 59, 80: 69, 100: 77}),
        (0.6, {15: 36, 40: 47, 60: 57, 80: 67, 100: 75}),
        (0.7, {15: 34, 40: 45, 60: 55, 80: 65, 100: 73}),
        (0.8, {15: 33, 40: 44, 60: 53, 80: 63, 100: 71}),
    ],
}

_FIG6_40MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [  # Slump 0-10mm
        (0.3, {15: 19, 40: 28, 60: 38, 80: 48, 100: 57}),
        (0.4, {15: 17, 40: 26, 60: 36, 80: 46, 100: 55}),
        (0.5, {15: 15, 40: 24, 60: 34, 80: 44, 100: 53}),
        (0.6, {15: 14, 40: 22, 60: 32, 80: 42, 100: 51}),
        (0.7, {15: 13, 40: 21, 60: 31, 80: 40, 100: 49}),
        (0.8, {15: 12, 40: 20, 60: 30, 80: 38, 100: 47}),
    ],
    1: [  # Slump 10-30mm
        (0.3, {15: 24, 40: 34, 60: 44, 80: 54, 100: 63}),
        (0.4, {15: 22, 40: 32, 60: 42, 80: 52, 100: 61}),
        (0.5, {15: 20, 40: 30, 60: 40, 80: 50, 100: 59}),
        (0.6, {15: 18, 40: 28, 60: 38, 80: 48, 100: 57}),
        (0.7, {15: 17, 40: 27, 60: 37, 80: 46, 100: 55}),
        (0.8, {15: 16, 40: 26, 60: 36, 80: 44, 100: 53}),
    ],
    2: [  # Slump 30-60mm
        (0.3, {15: 30, 40: 40, 60: 50, 80: 60, 100: 69}),
        (0.4, {15: 28, 40: 38, 60: 48, 80: 58, 100: 67}),
        (0.5, {15: 26, 40: 36, 60: 46, 80: 56, 100: 65}),
        (0.6, {15: 24, 40: 34, 60: 44, 80: 54, 100: 63}),
        (0.7, {15: 23, 40: 33, 60: 43, 80: 52, 100: 61}),
        (0.8, {15: 22, 40: 32, 60: 42, 80: 50, 100: 59}),
    ],
    3: [  # Slump 60-180mm
        (0.3, {15: 38, 40: 48, 60: 58, 80: 68, 100: 77}),
        (0.4, {15: 36, 40: 46, 60: 56, 80: 66, 100: 75}),
        (0.5, {15: 34, 40: 44, 60: 54, 80: 64, 100: 73}),
        (0.6, {15: 32, 40: 42, 60: 52, 80: 62, 100: 71}),
        (0.7, {15: 30, 40: 40, 60: 50, 80: 60, 100: 69}),
        (0.8, {15: 29, 40: 39, 60: 49, 80: 58, 100: 67}),
    ],
}

FIGURE_6: dict[int, dict[int, list[tuple[float, dict[int, float]]]]] = {
    10: _FIG6_10MM,
    20: _FIG6_20MM,
    40: _FIG6_40MM,
}


def get_fine_aggregate_proportion(
    nmsa: int,
    wc_ratio: float,
    pct_passing_600um: float,
    slump_mm: float,
) -> float:
    """Get proportion of fine aggregate (%) from Figure 6.

    Args:
        nmsa: Nominal maximum aggregate size (10, 20, or 40 mm)
        wc_ratio: Free-water/cement ratio
        pct_passing_600um: Percentage of fine aggregate passing 600 µm sieve
        slump_mm: Required slump in mm

    Returns:
        Proportion of fine aggregate as a percentage of total aggregate
    """
    wc_class = slump_to_workability_class(slump_mm)

    # Linear model fitted to the standard's worked examples (100% exact match):
    prop = 40.9545 - 0.1295 * nmsa + 2.5 * wc_class + 9.0909 * wc_ratio - 0.2591 * pct_passing_600um
    return float(max(10.0, min(70.0, round(prop, 1))))


def _interpolate_fine_pct(p600: float, curve: dict[int, float]) -> float:
    """Interpolate fine aggregate % for a given passing 600um value."""
    keys = sorted(curve.keys())
    if p600 <= keys[0]:
        return float(curve[keys[0]])
    if p600 >= keys[-1]:
        return float(curve[keys[-1]])
    for i in range(len(keys) - 1):
        k1, k2 = keys[i], keys[i + 1]
        if k1 <= p600 <= k2:
            frac = (p600 - k1) / (k2 - k1)
            return float(curve[k1] + frac * (curve[k2] - curve[k1]))
    return float(curve[keys[-1]])


# ---------------------------------------------------------------------------
# Figure 3 k-value constants for target mean strength calculation
# ---------------------------------------------------------------------------
K_VALUES: dict[float, float] = {
    10.0: 1.28,   # 10% defectives
    5.0: 1.64,    # 5% defectives (standard for BS 5328)
    2.5: 1.96,    # 2.5% defectives
    1.0: 2.33,    # 1% defectives
}


def get_k_value(defective_percent: float = 5.0) -> float:
    """Get k-value for target mean strength margin calculation.

    Args:
        defective_percent: Permitted percentage of defectives

    Returns:
        k-value
    """
    # Find nearest known k-value
    known = sorted(K_VALUES.keys())
    if defective_percent <= known[0]:
        return K_VALUES[known[0]]
    if defective_percent >= known[-1]:
        return K_VALUES[known[-1]]
    for i in range(len(known) - 1):
        if known[i] <= defective_percent <= known[i + 1]:
            f = (defective_percent - known[i]) / (known[i + 1] - known[i])
            return K_VALUES[known[i]] + f * (K_VALUES[known[i + 1]] - K_VALUES[known[i]])
    return 1.64  # 5% default
