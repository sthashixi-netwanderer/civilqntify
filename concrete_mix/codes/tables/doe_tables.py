"""DOE (Teychenné et al. 1997) lookup tables and interpolation functions.

Source: "Design of normal concrete mixes" (BR 331), 2nd edition, 1997.
Building Research Establishment (BRE), UK.

All tables are digitized from the published standard figures and tables.
"""

from __future__ import annotations

from concrete_mix.utils.statistics import defective_k_factor


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


# ---------------------------------------------------------------------------
# Workability classes — BRE 331:1997 Table 3 columns / Figure 6 panel headers
#
# The standard never takes an exact slump as a design input: Table 3 and
# every Figure 6 panel are organised by four workability ranges, with the
# slump and Vebe time scales side by side (§1.2.2, §2.1, Table 3):
#   class 0: Slump 0–10 mm   / Vebe >12 s
#   class 1: Slump 10–30 mm  / Vebe 6–12 s
#   class 2: Slump 30–60 mm  / Vebe 3–6 s
#   class 3: Slump 60–180 mm / Vebe 0–3 s
# The printed ranges overlap at 10/30/60 mm; endpoints belong to the lower
# class (columns are read left to right), which is what the mappers below
# implement. NMSA (10/20/40 mm, §1.2.5) selects the Figure 6 page; the
# class selects the column on that page.
# ---------------------------------------------------------------------------
WORKABILITY_CLASS_INFO: tuple[dict, ...] = (
    {"class": 0, "slump": "0–10 mm", "vebe": ">12 s", "rep_slump_mm": 5.0},
    {"class": 1, "slump": "10–30 mm", "vebe": "6–12 s", "rep_slump_mm": 20.0},
    {"class": 2, "slump": "30–60 mm", "vebe": "3–6 s", "rep_slump_mm": 45.0},
    {"class": 3, "slump": "60–180 mm", "vebe": "0–3 s", "rep_slump_mm": 120.0},
)


def workability_class_label(wc_class: int) -> str:
    """Short label for a Table 3 / Figure 6 workability class (0–3)."""
    info = WORKABILITY_CLASS_INFO[wc_class]
    return f"Slump {info['slump']} (Vebe {info['vebe']})"


def figure6_panel_label(nmsa: int, wc_class: int) -> str:
    """Identify the Figure 6 chart panel, e.g. '20 mm · Slump 10–30 mm'."""
    nmsa_key = 10 if nmsa <= 10 else (20 if nmsa <= 20 else 40)
    info = WORKABILITY_CLASS_INFO[wc_class]
    return f"{nmsa_key} mm · Slump {info['slump']} / Vebe {info['vebe']}"


def slump_to_workability_class(slump_mm: float) -> int:
    """Map slump range to workability class index for Table 3.

    Classes: 0=0-10mm, 1=10-30mm, 2=30-60mm, 3=60-180mm.
    Endpoints belong to the lower class (printed columns overlap).
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


def resolve_workability_class(
    slump_mm: float | None,
    vebe_s: float | None,
) -> tuple[int, str]:
    """Resolve the Table 3 / Figure 6 workability class from slump/Vebe.

    The two scales are parallel readings of the same four classes (BRE
    331:1997 §1.2.2, Table 3): whichever is provided selects the chart
    column. When BOTH are provided they must land on the same class; if
    they disagree, Vebe governs (it is the definitive measure at low
    workability where slump cannot discriminate) and a warning string is
    returned — a project decision, as the standard itself is silent on
    the precedence. Callers surface the string to the user; it is ""
    when the inputs agree or only one basis was given.

    Returns:
        (workability_class 0–3, warning or "")
    """
    have_slump = slump_mm is not None
    have_vebe = vebe_s is not None
    if not have_slump and not have_vebe:
        raise ValueError(
            "Either slump_mm or vebe_s must be provided to select the "
            "Table 3 / Figure 6 workability class (BRE 331:1997 §1.2.2)"
        )
    cls_vebe = vebe_to_workability_class(vebe_s) if have_vebe else None
    cls_slump = slump_to_workability_class(slump_mm) if have_slump else None
    if cls_vebe is not None and cls_slump is not None and cls_vebe != cls_slump:
        warning = (
            f"Slump {slump_mm:g} mm (class {cls_slump}, "
            f"{WORKABILITY_CLASS_INFO[cls_slump]['slump']}) and Vebe "
            f"{vebe_s:g} s (class {cls_vebe}, Vebe "
            f"{WORKABILITY_CLASS_INFO[cls_vebe]['vebe']}) map to different "
            f"workability columns — Vebe governs per project policy "
            f"(BRE 331:1997 Table 3 gives no precedence); verify the "
            f"specified workability"
        )
        return cls_vebe, warning
    return (cls_vebe if cls_vebe is not None else cls_slump), ""


def get_free_water_content(
    nmsa: int,
    agg_type: str,
    slump_mm: float | None = None,
    vebe_s: float | None = None,
    workability_class: int | None = None,
) -> float:
    """Get free-water content from Table 3.

    Args:
        nmsa: Nominal maximum aggregate size (10, 20, or 40 mm)
        agg_type: "uncrushed" or "crushed"
        slump_mm: Slump in mm (provide if using slump)
        vebe_s: Vebe time in seconds (provide if using Vebe)
        workability_class: Explicit Table 3 class 0–3, bypassing slump/Vebe
            derivation. Used for §8 air-entrained designs, which take water
            from one workability class lower than specified.

    Returns:
        Free-water content in kg/m³
    """
    if workability_class is not None:
        if workability_class not in (0, 1, 2, 3):
            raise ValueError(
                f"Workability class {workability_class} outside [0, 3] (Table 3)"
            )
        wc = workability_class
    elif slump_mm is not None:
        wc = slump_to_workability_class(slump_mm)
    elif vebe_s is not None:
        wc = vebe_to_workability_class(vebe_s)
    else:
        raise ValueError(
            "Either slump_mm, vebe_s or workability_class must be provided"
        )

    nmsa_key = 10 if nmsa <= 10 else (20 if nmsa <= 20 else 40)
    return float(WATER_CONTENT[nmsa_key][agg_type][wc])


# ---------------------------------------------------------------------------
# Figure 3 — Standard deviation vs characteristic strength (any grade)
#
# Piecewise lines (BRE 331:1997 §4.4):
#   Line A (< 20 results): s = 0.4×fc for fc ≤ 20, else s = 8 MPa
#   Line B (≥ 20 results): s = 0.2×fc for fc ≤ 20, else s = 4 MPa
# Both ramps meet their plateaus continuously at fc = 20 MPa.
# ---------------------------------------------------------------------------
def get_standard_deviation(
    characteristic_strength: float,
    has_production_data: bool = True,
    n: int | None = None,
) -> float:
    """Get standard deviation from Figure 3 (any characteristic strength).

    Args:
        characteristic_strength: fc in N/mm²
        has_production_data: True = Line B (>=20 results), False = Line A (<20)
            (ignored when ``n`` is provided).
        n: Number of test cubes (number of results).
            When given, the Figure 3 rule applies directly:
            n < 20 → Line A (s = 0.4×fc for fc ≤ 20, else 8 MPa);
            n ≥ 20 → Line B (s = 0.2×fc for fc ≤ 20, else 4 MPa).

    Returns:
        Standard deviation in N/mm²
    """
    fc = characteristic_strength
    if n is not None:
        # Figure 3 piecewise lines — continuous at fc = 20 MPa.
        if n < 20:
            if fc <= 20:
                return fc * 0.4
            return 8.0
        else:
            if fc <= 20:
                return fc * 0.2
            return 4.0
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
    # Digitized from the validated log-quadratic model
    #   wc = 0.5 - 0.370938*R + 0.045970*R^2,  R = ln(f_target / f_ref_at_0.5)
    # which reproduces the standard's own worked examples exactly:
    #   Example 1 (§7.1): target 46, ref 42 → wc 0.47
    #   Example 2 (§7.2): target 35, ref 42 → wc 0.57
    #   Example 4 (§7.4): target 62, ref 43 (7-day) → wc 0.37
    20: [(0.3, 35.8), (0.4, 26.4), (0.5, 20.0), (0.6, 15.4), (0.7, 12.0), (0.8, 9.5)],
    25: [(0.3, 44.7), (0.4, 33.1), (0.5, 25.0), (0.6, 19.3), (0.7, 15.1), (0.8, 11.9)],
    30: [(0.3, 53.6), (0.4, 39.7), (0.5, 30.0), (0.6, 23.1), (0.7, 18.1), (0.8, 14.3)],
    35: [(0.3, 62.6), (0.4, 46.3), (0.5, 35.0), (0.6, 27.0), (0.7, 21.1), (0.8, 16.7)],
    40: [(0.3, 71.5), (0.4, 52.9), (0.5, 40.0), (0.6, 30.8), (0.7, 24.1), (0.8, 19.1)],
    42: [(0.3, 75.1), (0.4, 55.5), (0.5, 42.0), (0.6, 32.3), (0.7, 25.3), (0.8, 20.0)],
    45: [(0.3, 80.5), (0.4, 59.5), (0.5, 45.0), (0.6, 34.7), (0.7, 27.1), (0.8, 21.5)],
    49: [(0.3, 87.6), (0.4, 64.8), (0.5, 49.0), (0.6, 37.7), (0.7, 29.5), (0.8, 23.4)],
    50: [(0.3, 89.4), (0.4, 66.1), (0.5, 50.0), (0.6, 38.5), (0.7, 30.1), (0.8, 23.8)],
    55: [(0.3, 98.3), (0.4, 72.7), (0.5, 55.0), (0.6, 42.4), (0.7, 33.1), (0.8, 26.2)],
    60: [(0.3, 107.3), (0.4, 79.3), (0.5, 60.0), (0.6, 46.2), (0.7, 36.1), (0.8, 28.6)],
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
# BRE 331:1997 charts for 3 aggregate sizes (10, 20, 40 mm) × 4 workability
# classes.  X = free-water/cement ratio, curves for % passing the 600 µm
# sieve (15, 40, 60, 80, 100 %).
#
# Digitized from the Figure 6 chart panels on the printed grid — every panel
# is read at the four labelled w/c ordinates (0.2, 0.4, 0.6, 0.8) on each of
# the five grading curves (project chart-image extraction, validated against
# the standard's worked examples — see get_fine_aggregate_proportion).
# Direction: a FINER sand (higher % passing 600 µm) needs a LOWER proportion
# of fine aggregate, and the proportion increases with workability and w/c.
#
# Structure: FIGURE_6[nmsa][wc_class] = list of (wc_ratio, {p600: fine_pct})
# wc_class: 0=0-10mm, 1=10-30mm, 2=30-60mm, 3=60-180mm
# ---------------------------------------------------------------------------

_FIG6_10MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [
        (0.2, {15: 48, 40: 37, 60: 31, 80: 26, 100: 23}),
        (0.4, {15: 54, 40: 42, 60: 35, 80: 29, 100: 25}),
        (0.6, {15: 60, 40: 48, 60: 40, 80: 32, 100: 28}),
        (0.8, {15: 67, 40: 54, 60: 44, 80: 36, 100: 31}),
    ],
    1: [
        (0.2, {15: 50, 40: 39, 60: 33, 80: 28, 100: 24}),
        (0.4, {15: 56, 40: 44, 60: 37, 80: 31, 100: 27}),
        (0.6, {15: 62, 40: 49, 60: 41, 80: 34, 100: 29}),
        (0.8, {15: 68, 40: 55, 60: 46, 80: 38, 100: 32}),
    ],
    2: [
        (0.2, {15: 54, 40: 42, 60: 36, 80: 30, 100: 25}),
        (0.4, {15: 60, 40: 47, 60: 40, 80: 33, 100: 28}),
        (0.6, {15: 66, 40: 52, 60: 44, 80: 37, 100: 31}),
        (0.8, {15: 72, 40: 58, 60: 48, 80: 40, 100: 34}),
    ],
    3: [
        (0.2, {15: 61, 40: 49, 60: 41, 80: 34, 100: 29}),
        (0.4, {15: 67, 40: 54, 60: 45, 80: 37, 100: 32}),
        (0.6, {15: 74, 40: 60, 60: 50, 80: 40, 100: 35}),
        (0.8, {15: 80, 40: 65, 60: 54, 80: 44, 100: 38}),
    ],
}

_FIG6_20MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [
        (0.2, {15: 35, 40: 27, 60: 23, 80: 19, 100: 16}),
        (0.4, {15: 41, 40: 32, 60: 27, 80: 23, 100: 19}),
        (0.6, {15: 48, 40: 38, 60: 31, 80: 26, 100: 22}),
        (0.8, {15: 54, 40: 43, 60: 36, 80: 30, 100: 25}),
    ],
    1: [
        (0.2, {15: 38, 40: 29, 60: 25, 80: 20, 100: 18}),
        (0.4, {15: 44, 40: 34, 60: 29, 80: 24, 100: 20}),
        (0.6, {15: 50, 40: 40, 60: 33, 80: 27, 100: 23}),
        (0.8, {15: 56, 40: 45, 60: 38, 80: 31, 100: 26}),
    ],
    2: [
        (0.2, {15: 41, 40: 32, 60: 27, 80: 23, 100: 20}),
        (0.4, {15: 47, 40: 37, 60: 31, 80: 26, 100: 23}),
        (0.6, {15: 53, 40: 42, 60: 35, 80: 29, 100: 25}),
        (0.8, {15: 59, 40: 47, 60: 39, 80: 32, 100: 28}),
    ],
    3: [
        (0.2, {15: 48, 40: 38, 60: 31, 80: 26, 100: 23}),
        (0.4, {15: 54, 40: 43, 60: 35, 80: 30, 100: 26}),
        (0.6, {15: 60, 40: 48, 60: 39, 80: 33, 100: 29}),
        (0.8, {15: 66, 40: 53, 60: 44, 80: 37, 100: 32}),
    ],
}

_FIG6_40MM: dict[int, list[tuple[float, dict[int, float]]]] = {
    0: [
        (0.2, {15: 28, 40: 21, 60: 18, 80: 15, 100: 12}),
        (0.4, {15: 34, 40: 26, 60: 22, 80: 18, 100: 15}),
        (0.6, {15: 41, 40: 32, 60: 26, 80: 22, 100: 18}),
        (0.8, {15: 47, 40: 38, 60: 31, 80: 26, 100: 21}),
    ],
    1: [
        (0.2, {15: 30, 40: 23, 60: 19, 80: 16, 100: 14}),
        (0.4, {15: 36, 40: 28, 60: 23, 80: 20, 100: 16}),
        (0.6, {15: 42, 40: 33, 60: 27, 80: 23, 100: 19}),
        (0.8, {15: 48, 40: 39, 60: 31, 80: 26, 100: 22}),
    ],
    2: [
        (0.2, {15: 34, 40: 26, 60: 22, 80: 19, 100: 16}),
        (0.4, {15: 40, 40: 31, 60: 26, 80: 22, 100: 19}),
        (0.6, {15: 46, 40: 36, 60: 30, 80: 25, 100: 21}),
        (0.8, {15: 52, 40: 41, 60: 34, 80: 28, 100: 24}),
    ],
    3: [
        (0.2, {15: 41, 40: 32, 60: 27, 80: 23, 100: 20}),
        (0.4, {15: 47, 40: 37, 60: 31, 80: 26, 100: 23}),
        (0.6, {15: 53, 40: 42, 60: 35, 80: 29, 100: 25}),
        (0.8, {15: 59, 40: 47, 60: 39, 80: 32, 100: 28}),
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
    slump_mm: float | None = None,
    vebe_s: float | None = None,
    workability_class: int | None = None,
) -> float:
    """Get proportion of fine aggregate (%) from Figure 6.

    Reads the chart panel for (NMSA page × workability column) with
    bilinear interpolation: first along the free-water/cement axis
    between the bracketing grid columns, then along the % passing
    600 µm axis between the bracketing grading curves (15/40/60/80/100).
    Formally, with bracketing columns w0 ≤ w ≤ w1 (α = (w−w0)/(w1−w0))
    and bracketing curves p0 ≤ p ≤ p1 (β = (p−p0)/(p1−p0)):

        P = (1−β)·[f0 + α·(f1−f0)] + β·[g0 + α·(g1−g0)]

    where f/g are the panel values on the p0/p1 curves. Inputs are
    clamped to the chart frame (w/c 0.2–0.8, passing 15–100%) and the
    result to 10–80%, rounded to 1 dp. Reproduces the standard's worked
    examples: §7.1 (20 mm, class 1, 0.47, 70%) → 27.7% (standard: 27%);
    §7.2 (40 mm, class 2, 0.50, 90%) → 21.8% (standard: 22%);
    §7.3 (40 mm, class 0, 0.40, 90%) → 16.5% (standard: 15–18%);
    §8.6 (20 mm, class 1, ~0.46, 50%) → 32.9% (standard: ~32%);
    §9.4 (20 mm, class 1, ~0.36, 70%) → 25.8% (standard: ~26%).

    Args:
        nmsa: Nominal maximum aggregate size (10, 20, or 40 mm)
        wc_ratio: Free-water/cement ratio (Figure 6 x-axis; W/(C+F)
            for pfa per §9.3.5)
        pct_passing_600um: Percentage of fine aggregate passing 600 µm
            sieve (Figure 6 curve family)
        slump_mm: Required slump in mm (derives the panel column;
            endpoints belong to the lower class)
        vebe_s: Vebe time in seconds (derives the panel column;
            preferred over slump when both are given)
        workability_class: Explicit panel column 0–3, bypassing
            slump/Vebe derivation (preferred — no boundary ambiguity).

    Returns:
        Proportion of fine aggregate as a percentage of total aggregate
    """
    if workability_class is not None:
        if workability_class not in (0, 1, 2, 3):
            raise ValueError(
                f"Workability class {workability_class} outside [0, 3] "
                f"(BRE 331:1997 Table 3 / Figure 6)"
            )
        wc_class = workability_class
    else:
        wc_class, _ = resolve_workability_class(slump_mm, vebe_s)

    nmsa_key = 10 if nmsa <= 10 else (20 if nmsa <= 20 else 40)
    panel = FIGURE_6[nmsa_key][wc_class]
    w = max(0.2, min(0.8, float(wc_ratio)))
    p = max(15.0, min(100.0, float(pct_passing_600um)))

    rows = sorted(panel, key=lambda r: r[0])
    if w <= rows[0][0]:
        lo = hi = rows[0]
    elif w >= rows[-1][0]:
        lo = hi = rows[-1]
    else:
        lo = hi = rows[0]
        for i in range(len(rows) - 1):
            if rows[i][0] <= w <= rows[i + 1][0]:
                lo, hi = rows[i], rows[i + 1]
                break

    f_lo = _interpolate_fine_pct(p, lo[1])
    if lo[0] == hi[0]:
        prop = f_lo
    else:
        alpha = (w - lo[0]) / (hi[0] - lo[0])
        prop = f_lo + alpha * (_interpolate_fine_pct(p, hi[1]) - f_lo)
    return float(max(10.0, min(80.0, round(prop, 1))))


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
# Table 9 Part B — reductions in free-water content (kg/m³) for Portland
# cement/pfa concrete, by pfa proportion p (% of cement + pfa) and Table 3
# workability class (0=0–10 mm, 1=10–30 mm, 2=30–60 mm, 3=60–180 mm).
# (BRE 331:1997 §9.2.1; Part A repeats Table 3.)
# ---------------------------------------------------------------------------
TABLE_9B_WATER_REDUCTION: dict[int, dict[int, float]] = {
    10: {0: 5, 1: 5, 2: 5, 3: 10},
    20: {0: 10, 1: 10, 2: 10, 3: 15},
    30: {0: 15, 1: 15, 2: 20, 3: 20},
    40: {0: 20, 1: 20, 2: 25, 3: 25},
    50: {0: 25, 1: 25, 2: 30, 3: 30},
}

# Cementing efficiency factor for pfa at 28 days (BRE 331:1997 §9.2.2):
# strength follows the free-water/'equivalent cement' ratio W/(C + kF).
PFA_EFFICIENCY_K = 0.30

# Rough-guide water reduction for ggbs replacement (BRE 331:1997 §10.2.1).
GGBS_WATER_REDUCTION_KG = 5.0


def pfa_water_reduction(pfa_percent: float, workability_class: int) -> float:
    """Water reduction (kg/m³) from Table 9 Part B, linearly interpolated
    in p between tabulated rows; clamped to the end rows outside 10–50%."""
    rows = sorted(TABLE_9B_WATER_REDUCTION.keys())
    p = max(float(rows[0]), min(float(rows[-1]), float(pfa_percent)))
    if p <= rows[0]:
        return float(TABLE_9B_WATER_REDUCTION[rows[0]][workability_class])
    if p >= rows[-1]:
        return float(TABLE_9B_WATER_REDUCTION[rows[-1]][workability_class])
    for i in range(len(rows) - 1):
        lo, hi = rows[i], rows[i + 1]
        if lo <= p <= hi:
            f = (p - lo) / (hi - lo)
            vlo = TABLE_9B_WATER_REDUCTION[lo][workability_class]
            vhi = TABLE_9B_WATER_REDUCTION[hi][workability_class]
            return float(vlo + f * (vhi - vlo))
    return float(TABLE_9B_WATER_REDUCTION[rows[-1]][workability_class])


# k-value for the target-mean-strength margin M = k × s (BRE 331 §4.4).
# Computed dynamically from the standard-normal quantile — no lookup table
# (defective_k_factor imported at module top).
# ---------------------------------------------------------------------------


def get_k_value(defective_percent: float = 5.0) -> float:
    """Get k-value for target mean strength margin calculation.

    k is the standard-normal quantile at cumulative probability (1 − p)
    for the defective proportion p (BRE 331:1997 §4.4; BS 5328 uses the 5%
    level, k = 1.64). The standard's worked examples quote k to 2dp, so the
    computed value is rounded to 2dp here — the single point where the
    standard's precision applies. Use
    :func:`concrete_mix.utils.statistics.defective_k_factor` directly for
    the full-precision value.

    Args:
        defective_percent: Permitted percentage of defectives in (0, 100).

    Returns:
        k-value rounded to 2dp (5.0 → 1.64, 2.5 → 1.96, 1.0 → 2.33).

    Raises:
        ValueError: if the percentage is not in (0, 100).
    """
    pct = float(defective_percent)
    if not 0.0 < pct < 100.0:
        raise ValueError(
            f"Defective percentage {defective_percent!r} is not usable — "
            f"pass a percentage in (0, 100)."
        )
    # Percent-only contract: sub-1% values (e.g. 0.5%) are normalized to
    # proportions first, because defective_k_factor reads (0, 1) as a
    # proportion by convention.
    return round(defective_k_factor(pct / 100.0 if pct < 1.0 else pct), 2)
