"""Grading analysis for fine and coarse aggregates.

Supports:
- Fineness Modulus (ACI 211.1 method)
- Grading Zone determination (IS 383 method)
"""

from __future__ import annotations

from dataclasses import dataclass

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
    # IS 383:2016 Clause 6.3 / Table 9: the 600 µm sieve discriminates the
    # zone; classify_is383_zone keys on it (with the 6.3 tolerance on the
    # other sieves).
    classification = classify_is383_zone(passing_percent)
    if classification.zone is not None:
        return classification.zone

    # Fallback for partial stacks without the 600 µm sieve: best-score
    # match against the Table 9 limits.
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
        raise ValueError(
            "No usable sieves for zone classification — supply the IS 383 "
            "fine stack including the 600 µm result (IS 383:2016 Table 9)"
        )

    # Return the zone with the highest match score
    best_zone = max(zone_scores, key=lambda z: zone_scores[z])

    # If no clear winner, default to Zone II
    if zone_scores[best_zone] < total_checks * 0.5:
        return "II"

    return best_zone


# ── IS 383:2016 Clause 6.3 — tolerance-aware zone classification ─────────


@dataclass(frozen=True)
class ZoneClassification:
    """Outcome of classifying a fine-aggregate grading per IS 383:2016
    Clause 6.3 / Table 9.

    The zone is keyed by the 600 µm sieve (the discriminating sieve of
    Table 9). Deviations on other sieves are tolerated per Clause 6.3
    (not more than 5 % on a single sieve, subject to a cumulative 10 %)
    but never at the 600 µm sieve, on the coarse limit of Grading Zone I
    (its lower bounds) or on the finer limit of Grading Zone IV (its
    upper bounds).
    """

    zone: str | None                 # "I"–"IV", from the 600 µm sieve
    conforms: bool                    # every sieve in limits or in tolerance
    deviations: tuple[str, ...] = ()  # tolerated out-of-limit sieves (6.3)
    violations: tuple[str, ...] = ()  # out-of-limit sieves beyond tolerance
    tolerance_used: bool = False      # any deviation absorbed by 6.3
    crushed_sand_relief_used: bool = False  # Table 9 Note 1 at 150 µm


def classify_is383_zone(
    passing_percent: dict[float, float],
    crushed_sand: bool = False,
) -> ZoneClassification:
    """Classify a fine-aggregate grading per IS 383:2016 Clause 6.3.

    Args:
        passing_percent: ``{sieve_mm: percent_passing}`` — the IS 383 fine
            stack (10 mm … 150 µm); missing sieves are simply skipped.
        crushed_sand: the sample is a crushed stone sand, for which the
            permissible limit on the 150 µm sieve is increased to 20 %
            (Table 9 Note 1).

    Returns:
        A :class:`ZoneClassification`. ``zone`` is ``None`` when the 600 µm
        sieve result is absent (the zone cannot be determined without it).
    """
    from concrete_mix.codes.tables.is383_quality import (
        ZONE_150UM_CRUSHED_STONE_SAND_MAX,
        ZONE_TOLERANCE_CUMULATIVE_PCT,
        ZONE_TOLERANCE_EXEMPT_SIEVE_MM,
        ZONE_TOLERANCE_SINGLE_SIEVE_PCT,
    )

    p600 = passing_percent.get(ZONE_TOLERANCE_EXEMPT_SIEVE_MM)
    if p600 is None:
        return ZoneClassification(zone=None, conforms=False, violations=(
            "600 µm sieve result not available — the grading zone cannot "
            "be determined (IS 383:2016 Table 9)",
        ))

    zone = None
    for candidate, limits in GRADING_ZONE_LIMITS.items():
        lo, hi = limits[ZONE_TOLERANCE_EXEMPT_SIEVE_MM]
        if lo <= p600 <= hi:
            zone = candidate
            break
    if zone is None:
        # Non-integer 600 µm results can land in the 34–35 / 59–60 / 79–80
        # gaps between the published integer ranges; assign the nearest
        # range (sieve percentages are reported to whole percent per
        # IS 2 : 1960 rounding). Exact ties (e.g. 34.5) resolve to the
        # coarser zone by GRADING_ZONE_LIMITS order (I first) — deterministic;
        # at whole-percent reporting the gap values never occur.
        def _dist(limits):
            lo, hi = limits[ZONE_TOLERANCE_EXEMPT_SIEVE_MM]
            return 0 if lo <= p600 <= hi else min(abs(p600 - lo), abs(p600 - hi))
        zone = min(GRADING_ZONE_LIMITS, key=lambda z: _dist(GRADING_ZONE_LIMITS[z]))

    deviations: list[str] = []
    violations: list[str] = []
    relief_used = False
    cumulative = 0.0

    for sieve_mm, (lo, hi) in GRADING_ZONE_LIMITS[zone].items():
        p = passing_percent.get(sieve_mm)
        if p is None:
            continue

        hi_eff = hi
        relief_here = False
        if (
            crushed_sand
            and abs(sieve_mm - 0.150) < 1e-6
            and hi < ZONE_150UM_CRUSHED_STONE_SAND_MAX
        ):
            hi_eff = ZONE_150UM_CRUSHED_STONE_SAND_MAX
            relief_used = True
            relief_here = True

        if lo - 1e-9 <= p <= hi_eff + 1e-9:
            continue

        label = f"{sieve_mm:g} mm" if sieve_mm >= 1.0 else f"{sieve_mm * 1000:g} µm"
        too_fine = p > hi_eff
        amount = (p - hi_eff) if too_fine else (lo - p)

        # Clause 6.3: the tolerance applies to sieves other than 600 µm,
        # and never on the coarse limit of Zone I or the finer limit of
        # Zone IV — i.e. only on the "inner" side of each extreme zone.
        # Table 9 Note 1: the crushed-stone-sand 20 % limit at 150 µm
        # replaces the tolerance at that sieve ("… does not affect the
        # 5 percent allowance … applying to other sieve sizes").
        tolerable_side = not (
            (zone == "I" and not too_fine) or (zone == "IV" and too_fine)
        )
        if (
            not relief_here
            and tolerable_side
            and amount <= ZONE_TOLERANCE_SINGLE_SIEVE_PCT + 1e-9
        ):
            cumulative += amount
            if cumulative <= ZONE_TOLERANCE_CUMULATIVE_PCT + 1e-9:
                deviations.append(
                    f"{label} {p:.1f} % passing vs {lo:g}–{hi:g} % "
                    f"({amount:.1f} % out, within the Clause 6.3 tolerance)"
                )
                continue

        bound = f"{hi:g}" if too_fine else f"{lo:g}"
        which = "above" if too_fine else "below"
        violations.append(
            f"{label} {p:.1f} % passing is {which} the Zone {zone} limit "
            f"of {bound} %"
        )

    return ZoneClassification(
        zone=zone,
        conforms=not violations,
        deviations=tuple(deviations),
        violations=tuple(violations),
        tolerance_used=bool(deviations),
        crushed_sand_relief_used=relief_used,
    )


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


# ── Gradation correction recommendations ────────────────────────────────
# NOTE (deviation documentation, per project AGENTS.md): IS 383 / ASTM C33
# define the grading *limits* only — they do not prescribe a correction
# method. The adjustment predicted here is the standard two-component
# blending mass balance used in combined-gradation practice:
#   adding a corrective fraction that (a) fully passes the offending sieve
#   raises %passing:  x = (T - P) / (100 - P)
#   (b) is fully retained on it, lowers %passing:  x = (P - T) / P
# where P = current %passing and T = target (band midpoint). The fraction x
# is expressed as a share of the final blended mass.


@dataclass(frozen=True)
class GradationCorrection:
    """A single out-of-band sieve with a predicted corrective adjustment."""

    sieve_mm: float
    percent_passing: float
    lower: float
    upper: float
    target: float
    too_coarse: bool
    deviation_pp: float
    blend_fraction: float
    action: str


def recommend_gradation_corrections(
    sieve_sizes: list[float],
    percent_passing: list[float],
    band: dict[float, tuple[float, float]],
) -> list[GradationCorrection]:
    """Predict the adjustment needed to bring out-of-band sieves in band.

    For each sieve whose %passing falls outside ``band`` (IS 383 Table 9
    fine zones / Table 7 coarse bands, ASTM C33 Tables 1 and 2), a target at the band
    midpoint and the corrective blend fraction are computed via the
    two-component blending mass balance (see module note above).

    Args:
        sieve_sizes: Sieve sizes in mm (any order).
        percent_passing: %passing aligned with ``sieve_sizes``.
        band: {sieve_mm: (lower_limit, upper_limit)}.

    Returns:
        One GradationCorrection per violating sieve (empty if conforming).
    """
    corrections: list[GradationCorrection] = []

    for s, p in zip(sieve_sizes, percent_passing):
        if s not in band:
            continue
        lo, hi = band[s]
        if lo <= p <= hi:
            continue

        target = (lo + hi) / 2.0
        if p < lo:
            # Too coarse — needs material that passes this sieve.
            too_coarse = True
            deviation = lo - p
            denom = 100.0 - p
            frac = (target - p) / denom if denom > 0 else 1.0
            base = (
                f"blend in \u2248{frac * 100:.0f}% (of final blend) material "
                f"that passes the {s:g} mm sieve \u2014 e.g. the next finer "
                f"stockpile fraction \u2014 or reduce the +{s:g} mm oversize"
            )
            if frac > 0.5:
                base = (
                    f"grading is far off spec: re-screen / re-crush the "
                    f"oversize stock before blending ({base})"
                )
        else:
            # Too fine — needs material retained on this sieve.
            too_coarse = False
            deviation = p - hi
            frac = (p - target) / p if p > 0 else 0.0
            base = (
                f"blend in \u2248{frac * 100:.0f}% (of final blend) coarse "
                f"material retained on the {s:g} mm sieve, or wash out the "
                f"excess fines passing {s:g} mm"
            )
            if frac > 0.5:
                base = (
                    f"excess fines are severe: washing or replacing the fine "
                    f"stock is more practical than blending ({base})"
                )

        corrections.append(
            GradationCorrection(
                sieve_mm=s,
                percent_passing=p,
                lower=lo,
                upper=hi,
                target=target,
                too_coarse=too_coarse,
                deviation_pp=deviation,
                blend_fraction=min(max(frac, 0.0), 1.0),
                action=base + f", to bring passing to \u2248{target:.0f}%.",
            )
        )

    return corrections
