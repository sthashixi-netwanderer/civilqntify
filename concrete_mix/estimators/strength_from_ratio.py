"""Estimate concrete compressive strength from a user-defined mix ratio.

Uses an empirical Abrams'-law-based curve to derive characteristic strength
from the implied W/C ratio, then applies the selected design standard's
official target-strength margin to produce the target mean strength.

References:
    IS 10262:2019 Clause 4.2, Table 2 — target mean strength margin (f'ck = fck + 1.65·S)
    ACI 318 §26.4.3.1 — f'cr = max(f'c + 1.34·s, f'c + 2.33·s − 3.45)
    BRE 331:1997 §4 — f_m = f_c + k·s  (k = 1.64 for 5% defectives)
"""

from __future__ import annotations


# ── Manual standard-deviation tiers (user spec) ──────────────────────
def _manual_std_dev(f_ck: float) -> float:
    """Tiered standard deviation for the Manual code path."""
    if f_ck < 15.0:
        return 3.5
    if f_ck <= 25.0:
        return 4.0
    return 5.0


def _manual_target(f_ck: float, s_d: float) -> float:
    """f_target = f_ck + 1.65 × s_d."""
    return f_ck + 1.65 * s_d


# ── IS 10262 target margin (f'ck = fck + 1.65·S, max vs fck + X) ───
_X_VALUES: dict[str, float] = {
    "M10": 5.0, "M15": 5.0,
    "M20": 5.5, "M25": 5.5,
    "M30": 6.5, "M35": 6.5, "M40": 6.5,
    "M45": 6.5, "M50": 6.5, "M55": 6.5, "M60": 6.5,
    "M65": 8.0, "M70": 8.0, "M75": 8.0, "M80": 8.0,
}

_STANDARD_DEVIATION_IS: dict[str, float] = {
    "M10": 3.5, "M15": 3.5,
    "M20": 4.0, "M25": 4.0,
    "M30": 5.0, "M35": 5.0, "M40": 5.0, "M45": 5.0,
    "M50": 5.0, "M55": 5.0, "M60": 5.0,
    "M65": 6.0, "M70": 6.0, "M75": 6.0, "M80": 6.0,
}


def _grade_from_fck(fck: float) -> str:
    """Map characteristic strength to IS grade label."""
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


def _is10262_target(fck: float) -> tuple[float, float, str]:
    """Return (target, std_dev, description) per IS 10262:2019 Clause 4.2."""
    grade = _grade_from_fck(fck)
    s = _STANDARD_DEVIATION_IS.get(grade, 5.0)
    x_val = _X_VALUES.get(grade, 6.5)
    ftm_sigma = fck + 1.65 * s
    ftm_x = fck + x_val
    target = max(ftm_sigma, ftm_x)
    if ftm_sigma >= ftm_x:
        desc = f"1.65 × {s}"
    else:
        desc = f"X = {x_val}"
    return round(target, 2), round(s, 2), desc


# ── ACI 318 target margin ───────────────────────────────────────────
def _aci_target(fck: float, s: float = 4.0) -> tuple[float, float, str]:
    """Return (target, std_dev, description) per ACI 318 §26.4.3.1.

    f'cr = max(f'c + 1.34·s,  f'c + 2.33·s − 3.45)
    Floor: f'cr ≥ f'c + 2.4
    """
    fcr_stat = fck + 1.34 * s
    fcr_lim = fck + 2.33 * s - 3.45
    fcr = max(fcr_stat, fcr_lim, fck + 2.4)
    return round(fcr, 2), round(s, 2), f"1.34 × {s}"


# ── DOE / BRE 331 target margin ─────────────────────────────────────
def _doe_target(fck: float) -> tuple[float, float, str]:
    """Return (target, std_dev, description) per BRE 331:1997 §4.

    k = 1.64 (5% defective level).
    Standard deviation from DOE Figure 3 Line B (≥20 results).
    """
    k = 1.64
    # DOE Figure 3 Line B approximation (conservative, ≥20 results)
    if fck <= 20:
        s = round(fck * 4.0 / 20.0, 2)
    else:
        s = 4.0
    margin = round(k * s, 2)
    return round(fck + margin, 2), s, f"{k} × {s}"


# ── Public API ───────────────────────────────────────────────────────
def estimate_strength_from_ratio(
    cement: float,
    sand: float,
    gravel: float,
    fck: float,
    code: str = "manual",
) -> dict[str, float]:
    """Estimate target mean strength from a mix ratio and user-entered f_ck.

    The user supplies the characteristic strength (f_ck).  The mix ratio
    is used only to derive the implied W/C ratio.  The selected design
    standard's official margin formula is then applied to the user's f_ck
    to produce the target mean strength.

    Parameters
    ----------
    cement : float
        Cement proportion (normalized to 1.0).
    sand : float
        Fine aggregate proportion.
    gravel : float
        Coarse aggregate proportion.
    fck : float
        User-entered characteristic compressive strength at 28 days (MPa).
    code : str
        Design standard: ``"manual"`` | ``"is10262"`` | ``"aci211"`` | ``"doe"``

    Returns
    -------
    dict
        ``implied_wc_ratio``            — estimated W/C from aggregate ratio
        ``characteristic_strength_fck`` — the user's f_ck (MPa), unchanged
        ``standard_deviation``          — safety-factor s_d used
        ``target_strength_f_target``    — final target mean strength (MPa)
        ``margin_formula``              — human-readable margin formula

    All numeric values rounded to 2 decimal places.

    Empirical steps
    ---------------
    1. total_aggregate = sand + gravel
    2. implied W/C = 0.30 + 0.03 × total_aggregate
    3. target margin applied per selected standard to the user's f_ck
    """
    total_aggregate = sand + gravel
    wc_ratio = 0.30 + 0.03 * total_aggregate

    if code == "is10262":
        target, s_d, margin_desc = _is10262_target(fck)
    elif code == "aci211":
        target, s_d, margin_desc = _aci_target(fck)
    elif code == "doe":
        target, s_d, margin_desc = _doe_target(fck)
    else:
        s_d = _manual_std_dev(fck)
        target = _manual_target(fck, s_d)
        margin_desc = f"1.65 × {s_d}"

    # ── Material quantities per m³ (absolute volume method) ────────
    # Use typical specific gravities for the estimation
    SG_CEMENT = 3.15
    SG_WATER = 1.00
    SG_FINE = 2.65
    SG_COARSE = 2.70
    AIR_CONTENT = 0.01  # 1% entrapped air

    # For ratio 1 : sand : gravel, let cement = C kg
    # C × [1/(SG_C×1000) + wc/(SG_W×1000) + sand/(SG_F×1000) + gravel/(SG_CA×1000)] = 1 - AIR
    denom = (
        1.0 / (SG_CEMENT * 1000)
        + wc_ratio / (SG_WATER * 1000)
        + sand / (SG_FINE * 1000)
        + gravel / (SG_COARSE * 1000)
    )
    cement_mass = (1.0 - AIR_CONTENT) / denom
    water_mass = cement_mass * wc_ratio
    sand_mass = cement_mass * sand
    gravel_mass = cement_mass * gravel

    return {
        "implied_wc_ratio": round(wc_ratio, 2),
        "characteristic_strength_fck": round(fck, 2),
        "standard_deviation": round(s_d, 2),
        "target_strength_f_target": round(target, 2),
        "margin_formula": margin_desc,
        "cement_kg": round(cement_mass, 1),
        "water_kg": round(water_mass, 1),
        "fine_aggregate_kg": round(sand_mass, 1),
        "coarse_aggregate_kg": round(gravel_mass, 1),
    }
