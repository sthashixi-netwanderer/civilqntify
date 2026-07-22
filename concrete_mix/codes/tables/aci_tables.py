"""Digitized ACI 211.1-91 lookup tables for concrete mix design.

All values in metric (SI) units. Original tables are in US customary units.
Source: ACI 211.1-91 Standard Practice for Selecting Proportions for Normal,
Heavyweight, and Mass Concrete.
"""

from __future__ import annotations

# Table 6.3.3: Approximate mixing water and air content requirements
# Format: {nmsa_mm: {slump_mm: water_kg_m3}}
# For non-air-entrained concrete
WATER_CONTENT_NON_AIR_ENTRAINED: dict[int, dict[int, float]] = {
    10: {
        25: 207,
        50: 225,
        75: 243,
        100: 253,
        150: 268,
    },
    20: {
        25: 183,
        50: 193,
        75: 208,
        100: 216,
        150: 228,
    },
    40: {
        25: 160,
        50: 175,
        75: 185,
        100: 193,
        150: 205,
    },
}

# Table 6.3.3: Air-entrained concrete
WATER_CONTENT_AIR_ENTRAINED: dict[int, dict[int, float]] = {
    10: {
        25: 181,
        50: 199,
        75: 216,
        100: 225,
        150: 240,
    },
    20: {
        25: 163,
        50: 179,
        75: 190,
        100: 199,
        150: 210,
    },
    40: {
        25: 145,
        50: 160,
        75: 172,
        100: 181,
        150: 192,
    },
}

# Table 6.3.3: Target air content (%) by NMSA and exposure level
# Exposure: "mild", "moderate", "severe"
AIR_CONTENT: dict[int, dict[str, float]] = {
    10: {"mild": 3.0, "moderate": 5.0, "severe": 7.0},
    20: {"mild": 2.0, "moderate": 4.5, "severe": 6.0},
    40: {"mild": 1.0, "moderate": 3.5, "severe": 5.0},
}

# Entrapped air (non-air-entrained concrete) by NMSA
AIR_CONTENT_ENTRAPPED: dict[int, float] = {
    10: 1.5,
    20: 1.0,
    40: 0.5,
}

# Table 6.3.4(a): Water-cementitious ratio for non-air-entrained concrete
# Key: compressive strength at 28 days (MPa), Value: w/cm ratio
# ACI 211.1 Table 6.3.4(a) — metric converted
WC_RATIO_NON_AIR_ENTRAINED: dict[float, float] = {
    70.0: 0.29,
    60.0: 0.32,
    50.0: 0.37,
    45.0: 0.40,
    40.0: 0.42,
    35.0: 0.47,
    30.0: 0.52,
    28.0: 0.55,
    25.0: 0.58,
    21.0: 0.63,
    17.0: 0.69,
    14.0: 0.75,
}

# Table 6.3.4(b): Water-cementitious ratio for air-entrained concrete
WC_RATIO_AIR_ENTRAINED: dict[float, float] = {
    70.0: 0.29,
    60.0: 0.32,
    50.0: 0.37,
    45.0: 0.40,
    40.0: 0.42,
    35.0: 0.47,
    30.0: 0.52,
    28.0: 0.55,
    25.0: 0.58,
    21.0: 0.63,
    17.0: 0.69,
    14.0: 0.75,
    10.0: 0.82,
}

# Table 6.3.6: Volume of coarse aggregate per unit volume of concrete
# Key: (nmsa_mm, fineness_modulus) -> volume fraction
# Based on ACI 211.1 Table 6.3.6 — dry-rodded CA volume per m³ of concrete
CA_VOLUME_FRACTION: dict[tuple[int, float], float] = {
    # NMSA 10mm
    (10, 2.40): 0.50,
    (10, 2.60): 0.48,
    (10, 2.80): 0.46,
    (10, 3.00): 0.44,
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

# ACI 318 Table 26.4.3.1(b) — Required average compressive strength (f'cr)
# when NO prior test data is available (less than 30 tests).
# Key: specified f'c (MPa), Value: required f'cr (MPa)
# Metric conversion of the PSI table values.
ACI_NO_DATA_OVERDESIGN: dict[float, float] = {
    # f'c (MPa) : f'cr (MPa)
    17.0: 24.0,   # < 20 MPa: f'c + 7 MPa
    20.0: 28.5,   # 20-35 MPa: f'c + 8.5 MPa
    25.0: 33.5,
    28.0: 36.5,
    30.0: 38.5,
    35.0: 43.5,
    40.0: 50.0,   # > 35 MPa: f'c + 10 MPa
    50.0: 60.0,
    60.0: 70.0,
    70.0: 80.0,
}


def get_no_data_overdesign(specified_fc_mpa: float) -> float:
    """Get f'cr from ACI 318 Table 26.4.3.1(b) for producers without test data.

    Interpolates between table entries.
    """
    strengths = sorted(ACI_NO_DATA_OVERDESIGN.keys())
    if specified_fc_mpa <= strengths[0]:
        return ACI_NO_DATA_OVERDESIGN[strengths[0]]
    if specified_fc_mpa >= strengths[-1]:
        return ACI_NO_DATA_OVERDESIGN[strengths[-1]]

    for i in range(len(strengths) - 1):
        s_lo, s_hi = strengths[i], strengths[i + 1]
        if s_lo <= specified_fc_mpa <= s_hi:
            fcr_lo = ACI_NO_DATA_OVERDESIGN[s_lo]
            fcr_hi = ACI_NO_DATA_OVERDESIGN[s_hi]
            fraction = (specified_fc_mpa - s_lo) / (s_hi - s_lo)
            return fcr_lo + fraction * (fcr_hi - fcr_lo)

    return ACI_NO_DATA_OVERDESIGN[strengths[-1]]
