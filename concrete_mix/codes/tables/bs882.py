"""BS 882:1992 grading tables — verified transcriptions (see
``BS-882-1992-Aggregates-for-Concrete.md``, Tables 3–6, §5.1–§5.4, §4.2).

All coarse values are inclusive percentage-passing ``(lower, upper)`` limits
keyed by sieve opening in millimetres. Column labels of the standard are
nominal sizes; the sieve keys below use the actual BS 410 apertures named by
the table rows (50.0, 37.5, 20.0, 14.0, 10.0, 5.0, 2.36 mm).

A dash (—) in the standard's tables means no requirement: such sieves are
deliberately absent from these band mappings and from conformance checking
(per AGENTS.md PSD-tab rules).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Table 3 (§5.1) — Coarse aggregate, percentage by mass passing
# ---------------------------------------------------------------------------

BS_COARSE_GRADED_BANDS: dict[int, dict[float, tuple[float, float]]] = {
    # "40mm to 5 mm"
    40: {
        50.0: (100, 100),
        37.5: (90, 100),
        20.0: (35, 70),
        14.0: (25, 55),
        10.0: (10, 40),
        5.0: (0, 5),
    },
    # "20mm to 5 mm"
    20: {
        37.5: (100, 100),
        20.0: (90, 100),
        14.0: (40, 80),
        10.0: (30, 60),
        5.0: (0, 10),
    },
    # "14mm to 5 mm"
    14: {
        20.0: (100, 100),
        14.0: (90, 100),
        10.0: (50, 85),
        5.0: (0, 10),
    },
}

BS_COARSE_SINGLE_SIZED_BANDS: dict[int, dict[float, tuple[float, float]]] = {
    40: {
        50.0: (100, 100),
        37.5: (85, 100),
        20.0: (0, 25),
        10.0: (0, 5),
    },
    20: {
        37.5: (100, 100),
        20.0: (85, 100),
        14.0: (0, 70),
        10.0: (0, 25),
        5.0: (0, 5),
    },
    14: {
        20.0: (100, 100),
        14.0: (85, 100),
        10.0: (0, 50),
        5.0: (0, 10),
    },
    10: {
        14.0: (100, 100),
        10.0: (85, 100),
        5.0: (0, 25),
        2.36: (0, 5),
    },
    5: {
        10.0: (100, 100),
        5.0: (45, 100),
        2.36: (0, 30),
    },
}

BS_COARSE_NOMINAL_SIZES: list[int] = [40, 20, 14, 10, 5]
BS_GRADED_NOMINAL_SIZES: list[int] = [40, 20, 14]
BS_SINGLE_SIZED_NOMINAL_SIZES: list[int] = [40, 20, 14, 10, 5]


def get_bs_coarse_band(
    grading_type: str,
    nominal_size_mm: int | float,
) -> dict[float, tuple[float, float]]:
    """Return a BS 882:1992 Table 3 coarse-aggregate band.

    Args:
        grading_type: ``"graded"`` or ``"single"``.
        nominal_size_mm: Nominal size: 40/20/14 graded; 40/20/14/10/5
            single-sized. ``5`` single size is used mainly in precast
            concrete products (Table 3 footnote).

    Raises:
        KeyError: if the grading type or nominal size is not in Table 3.
    """
    if grading_type == "graded":
        bands = BS_COARSE_GRADED_BANDS
    elif grading_type == "single":
        bands = BS_COARSE_SINGLE_SIZED_BANDS
    else:
        raise KeyError("grading_type must be 'graded' or 'single'")
    if nominal_size_mm in bands:
        return bands[nominal_size_mm]
    if isinstance(nominal_size_mm, float) and nominal_size_mm.is_integer():
        if int(nominal_size_mm) in bands:
            return bands[int(nominal_size_mm)]
    raise KeyError(
        f"Unsupported BS 882 coarse nominal size {nominal_size_mm} mm for "
        f"grading_type={grading_type!r}. Valid sizes: {list(bands)}"
    )


# ---------------------------------------------------------------------------
# Table 4 (§5.2) — Sand, percentage by mass passing
# ---------------------------------------------------------------------------
# The 2.36/1.18/600 µm/300 µm rows carry BOTH overall limits and the
# additional C/M/F limits; a compliant sand must satisfy the overall limits
# AND one additional grading (§5.2.1). The classification helpers in
# :mod:`concrete_mix.validation.bs882` therefore combine each additional
# column with the overall limits (intersection) rather than using the
# additional column alone.

# Sieves that carry additional C/M/F limits (the 10 mm, 5 mm and 150 µm
# rows are overall-only).
BS_SAND_ADDITIONAL_SIEVES: tuple[float, ...] = (2.36, 1.18, 0.600, 0.300)

# Overall limits for the additional sieves, aligned with
# BS_SAND_ADDITIONAL_SIEVES.
BS_SAND_OVERALL_LIMITS: tuple[tuple[float, float], ...] = (
    (60, 100), (30, 100), (15, 100), (5, 70),
)

# Additional limits for gradings C, M and F, aligned with
# BS_SAND_ADDITIONAL_SIEVES.
BS_SAND_ADDITIONAL_LIMITS: dict[str, tuple[tuple[float, float], ...]] = {
    "C": ((60, 100), (30, 90), (15, 54), (5, 40)),
    "M": ((65, 100), (45, 100), (25, 80), (5, 48)),
    "F": ((80, 100), (70, 100), (55, 100), (5, 70)),
}

# Overall-only rows: 10 mm is fixed at 100, 5 mm at 89–100.
BS_SAND_OVERALL_FIXED: dict[float, tuple[float, float]] = {
    10.0: (100, 100),
    5.0: (89, 100),
}

# Table 4 footnote 1: the 150 µm overall upper limit is 15 % and increases
# to 20 % for crushed rock fines, except when they are used for heavy duty
# floors (which keep 15 %).
BS_SAND_150UM_BASE_MAX: float = 15.0
BS_SAND_150UM_CRUSHED_ROCK_MAX: float = 20.0

# §5.2.2 — heavy duty concrete floor finishes require grading C or M.
BS_SAND_HEAVY_DUTY_GRADINGS: tuple[str, ...] = ("C", "M")


def get_bs_fine_band(
    grading: str = "Overall",
    *,
    crushed_rock: bool = False,
    heavy_duty_floor: bool = False,
) -> dict[float, tuple[float, float]]:
    """Return a BS 882:1992 Table 4 sand band.

    Args:
        grading: ``"Overall"`` or one of the additional gradings
            ``"C"``, ``"M"``, ``"F"``. The additional gradings are returned
            combined with the overall limits (§5.2.1: the sand shall comply
            with the overall limits and additionally with C, M or F).
        crushed_rock: Apply the Table 4 footnote 150 µm relaxation
            (15 % → 20 %) for crushed rock fines.
        heavy_duty_floor: Heavy duty floor finish use — the footnote
            explicitly *excepts* heavy duty floors from the crushed-rock
            relaxation, so the 150 µm upper limit stays 15 %.

    Returns:
        Dict of ``{sieve_mm: (lower_passing%, upper_passing%)}``.

    Raises:
        KeyError: if *grading* is not ``Overall``/``C``/``M``/``F``.
    """
    band: dict[float, tuple[float, float]] = dict(BS_SAND_OVERALL_FIXED)
    for sieve, overall in zip(BS_SAND_ADDITIONAL_SIEVES, BS_SAND_OVERALL_LIMITS):
        band[sieve] = overall
    if grading != "Overall":
        try:
            additional = BS_SAND_ADDITIONAL_LIMITS[grading]
        except KeyError:
            raise KeyError(
                f"Unknown BS 882 sand grading {grading!r}. "
                f"Valid: ['Overall', 'C', 'M', 'F']"
            ) from None
        # §5.2.1: overall limits AND the additional grading — the effective
        # envelope of a named grading is the intersection with Overall.
        for sieve, additional_limits in zip(
            BS_SAND_ADDITIONAL_SIEVES, additional
        ):
            lo_o, hi_o = band[sieve]
            lo_a, hi_a = additional_limits
            band[sieve] = (max(lo_o, lo_a), min(hi_o, hi_a))
    # 150 µm row (overall-only): 0–15 %, footnote 1 raises to 20 % for
    # crushed rock fines EXCEPT heavy duty floors.
    if crushed_rock and not heavy_duty_floor:
        band[0.150] = (0, BS_SAND_150UM_CRUSHED_ROCK_MAX)
    else:
        band[0.150] = (0, BS_SAND_150UM_BASE_MAX)
    return band
