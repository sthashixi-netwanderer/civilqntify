"""Grading analysis for fine and coarse aggregates.

Supports:
- Fineness Modulus (ACI 211.1 method)
- Grading Zone determination (IS 383 method)
"""

from __future__ import annotations

from concrete_mix.codes.tables.is_tables import GRADING_ZONE_LIMITS


def calculate_fineness_modulus(
    cumulative_retained_percent: list[float],
) -> float:
    """Calculate Fineness Modulus (FM) per ASTM C33 / ACI 211.1.

    FM = sum of cumulative % retained on standard sieves / 100

    Standard sieves (mm): 0.15, 0.30, 0.60, 1.18, 2.36, 4.75

    Args:
        cumulative_retained_percent: List of cumulative % retained on each sieve,
            from finest to coarsest (6 values for standard sieves).

    Returns:
        Fineness Modulus (typically 2.0-3.1 for fine aggregate)
    """
    if len(cumulative_retained_percent) != 6:
        raise ValueError(
            f"Expected 6 sieve values, got {len(cumulative_retained_percent)}"
        )
    return sum(cumulative_retained_percent) / 100.0


def fineness_modulus_from_passing(
    passing_percent: list[float],
) -> float:
    """Calculate FM from percent passing values.

    Args:
        passing_percent: % passing on sieves [0.15, 0.30, 0.60, 1.18, 2.36, 4.75] mm

    Returns:
        Fineness Modulus
    """
    retained = [100.0 - p for p in passing_percent]
    return calculate_fineness_modulus(retained)


def determine_grading_zone(
    passing_percent: dict[float, float],
) -> str:
    """Determine IS 383 grading zone from sieve analysis.

    Args:
        passing_percent: Dict of {sieve_size_mm: percent_passing}
            Expected sieves: 10.0, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150

    Returns:
        Grading zone string: "I", "II", "III", or "IV"
    """
    zone_scores = {"I": 0, "II": 0, "III": 0, "IV": 0}
    total_checks = 0

    for sieve_mm, (lower, upper) in GRADING_ZONE_LIMITS["II"].items():
        if sieve_mm not in passing_percent:
            continue
        value = passing_percent[sieve_mm]

        for zone in ("I", "II", "III", "IV"):
            bounds = GRADING_ZONE_LIMITS[zone][sieve_mm]
            if bounds[0] <= value <= bounds[1]:
                zone_scores[zone] += 1
        total_checks += 1

    if total_checks == 0:
        return "II"  # default

    # Return the zone with the highest match score
    best_zone = max(zone_scores, key=lambda z: zone_scores[z])

    # If no clear winner, default to Zone II
    if zone_scores[best_zone] < total_checks * 0.5:
        return "II"

    return best_zone


def validate_grading(
    passing_percent: dict[float, float],
    code: str,
    zone: str | None = None,
) -> list[str]:
    """Validate aggregate grading against code requirements.

    Args:
        passing_percent: Dict of {sieve_size_mm: percent_passing}
        code: "aci211" or "is10262"
        zone: Grading zone to check against (IS only)

    Returns:
        List of warning messages (empty if OK)
    """
    warnings: list[str] = []

    if code == "is10262":
        check_zone = zone or "II"
        if check_zone not in GRADING_ZONE_LIMITS:
            warnings.append(f"Unknown grading zone '{check_zone}'")
            return warnings

        for sieve_mm, (lower, upper) in GRADING_ZONE_LIMITS[check_zone].items():
            if sieve_mm in passing_percent:
                value = passing_percent[sieve_mm]
                if value < lower:
                    warnings.append(
                        f"Sieve {sieve_mm}mm: {value:.1f}% passing below "
                        f"Zone {check_zone} lower limit ({lower}%)"
                    )
                elif value > upper:
                    warnings.append(
                        f"Sieve {sieve_mm}mm: {value:.1f}% passing above "
                        f"Zone {check_zone} upper limit ({upper}%)"
                    )

    elif code == "aci211":
        # ACI uses FM range 2.3-3.1 for fine aggregate
        fm = fineness_modulus_from_passing(
            [passing_percent.get(s, 0) for s in [0.15, 0.30, 0.60, 1.18, 2.36, 4.75]]
        )
        if fm < 2.3:
            warnings.append(f"FM {fm:.2f} below ACI recommended minimum (2.3)")
        elif fm > 3.1:
            warnings.append(f"FM {fm:.2f} above ACI recommended maximum (3.1)")

    return warnings
