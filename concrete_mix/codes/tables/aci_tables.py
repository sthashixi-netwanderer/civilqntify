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

# ACI 318 Table 26.4.3.1(b) — Required average compressive strength (f'cr)
# when NO prior test data is available (less than 30 tests).
# Metric: f'c < 21 MPa → +7;  21 ≤ f'c ≤ 35 → +8.5;  f'c > 35 → +10.
ACI_NO_DATA_OVERDESIGN: dict[float, float] = {
    # f'c (MPa) : f'cr (MPa)
    17.0: 24.0,   # < 21 MPa: f'c + 7 MPa
    20.0: 27.0,   # still < 21 MPa → +7 (3000 psi = 20.7 MPa breakpoint)
    25.0: 33.5,   # 21-35 MPa: f'c + 8.5 MPa
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
