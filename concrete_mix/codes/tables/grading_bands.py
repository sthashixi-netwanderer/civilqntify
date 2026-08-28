"""Standard-specific grading-limit bands for PSD plots.

IS 383:2016 fine grading zones and Table 7 coarse bands are kept separate from
ASTM C33/C33M Table 1 and Table 2 bands. All values are inclusive percentage-
passing limits keyed by sieve opening in millimetres.

A dash, ellipsis, or blank standard-table cell means no grading requirement.
Such sieves remain available for laboratory input but are deliberately absent
from the band mapping and therefore excluded from conformance checking.
"""

from __future__ import annotations

# Re-export the fine-aggregate IS 383 zone limits so callers can import all
# band data from a single module.
from concrete_mix.codes.tables.is_tables import GRADING_ZONE_LIMITS

FINE_ZONES: list[str] = ["I", "II", "III", "IV"]

# ASTM C33/C33M Table 1 — Fine aggregate grading requirements.
ASTM_FINE_BAND: dict[float, tuple[float, float]] = {
    9.5: (100, 100),
    4.75: (95, 100),
    2.36: (80, 100),
    1.18: (50, 85),
    0.600: (25, 60),
    0.300: (5, 30),
    0.150: (0, 10),
}

# IS 383:2016 Table 7 — single-sized coarse aggregate.
IS_COARSE_SINGLE_SIZED_BANDS: dict[
    int | float, dict[float, tuple[float, float]]
] = {
    63: {80.0: (100, 100), 63.0: (85, 100), 40.0: (0, 30), 20.0: (0, 5), 10.0: (0, 5)},
    40: {63.0: (100, 100), 40.0: (85, 100), 20.0: (0, 20), 10.0: (0, 5)},
    20: {40.0: (100, 100), 20.0: (85, 100), 10.0: (0, 20), 4.75: (0, 5)},
    16: {20.0: (100, 100), 16.0: (85, 100), 10.0: (0, 30), 4.75: (0, 5)},
    12.5: {16.0: (100, 100), 12.5: (85, 100), 10.0: (0, 45), 4.75: (0, 10)},
    10: {12.5: (100, 100), 10.0: (85, 100), 4.75: (0, 20), 2.36: (0, 5)},
}

# IS 383:2016 Table 7 — graded coarse aggregate.
IS_COARSE_GRADED_BANDS: dict[
    int | float, dict[float, tuple[float, float]]
] = {
    40: {80.0: (100, 100), 40.0: (90, 100), 20.0: (30, 70), 10.0: (10, 35), 4.75: (0, 5)},
    20: {40.0: (100, 100), 20.0: (90, 100), 10.0: (25, 55), 4.75: (0, 10)},
    16: {20.0: (100, 100), 16.0: (90, 100), 10.0: (30, 70), 4.75: (0, 10)},
    12.5: {20.0: (100, 100), 12.5: (90, 100), 10.0: (40, 85), 4.75: (0, 10)},
}

IS_SINGLE_SIZED_NOMINAL_SIZES: list[int | float] = [63, 40, 20, 16, 12.5, 10]
IS_GRADED_NOMINAL_SIZES: list[int | float] = [40, 20, 16, 12.5]

# ---------------------------------------------------------------------------
# ASTM C33/C33M Table 2 — Coarse aggregate grading requirements
# ---------------------------------------------------------------------------
# Percent passing by sieve size (mm). Values are inclusive (lower, upper)
# limits copied from the indicated ASTM size-number row. Only specified cells
# are represented; Table 2 ellipses mean "no requirement".
#
# App reference   ASTM size no.   Nominal size range
# 10 mm           8               9.5 to 2.36 mm (3/8 in. to No. 8)
# 20 mm           67              19.0 to 4.75 mm (3/4 in. to No. 4)
# 40 mm           467             37.5 to 4.75 mm (1-1/2 in. to No. 4)
# ---------------------------------------------------------------------------

ASTM_COARSE_BANDS: dict[int, dict[float, tuple[float, float]]] = {
    # ASTM C33/C33M Table 2, Size 8
    10: {
        12.5: (100, 100),
        9.5: (85, 100),
        4.75: (10, 30),
        2.36: (0, 10),
        1.18: (0, 5),
    },
    # ASTM C33/C33M Table 2, Size 67
    20: {
        25.0: (100, 100),
        19.0: (90, 100),
        9.5: (20, 55),
        4.75: (0, 10),
        2.36: (0, 5),
    },
    # ASTM C33/C33M Table 2, Size 467
    40: {
        50.0: (100, 100),
        37.5: (95, 100),
        19.0: (35, 70),
        9.5: (10, 30),
        4.75: (0, 5),
    },
}

# Project-supported ASTM coarse references. Do not add other ASTM size rows.
ASTM_COARSE_NOMINAL_SIZES: list[int] = [10, 20, 40]

# Backward-compatible names used by existing callers and tests.
COARSE_BANDS = ASTM_COARSE_BANDS
COARSE_NOMINAL_SIZES = ASTM_COARSE_NOMINAL_SIZES


def get_fine_band(zone: str) -> dict[float, tuple[float, float]]:
    """Return an IS 383 fine-aggregate grading-zone band.

    Args:
        zone: One of "I", "II", "III", "IV" (IS 383 grading zones).

    Returns:
        Dict of ``{sieve_mm: (lower_passing%, upper_passing%)}``.

    Raises:
        KeyError: if *zone* is not a recognised IS 383 zone.
    """
    if zone not in GRADING_ZONE_LIMITS:
        raise KeyError(
            f"Unknown fine-aggregate grading zone '{zone}'. "
            f"Valid zones: {list(GRADING_ZONE_LIMITS)}"
        )
    return GRADING_ZONE_LIMITS[zone]


def get_astm_fine_band() -> dict[float, tuple[float, float]]:
    """Return ASTM C33/C33M Table 1 fine-aggregate limits."""
    return ASTM_FINE_BAND


def _normalise_size_key(
    nominal_size_mm: int | float,
    bands: dict[int | float, dict[float, tuple[float, float]]],
) -> int | float:
    if nominal_size_mm in bands:
        return nominal_size_mm
    if isinstance(nominal_size_mm, float) and nominal_size_mm.is_integer():
        integer_size = int(nominal_size_mm)
        if integer_size in bands:
            return integer_size
    raise KeyError(
        f"Unsupported nominal size {nominal_size_mm} mm. "
        f"Valid sizes: {list(bands)}"
    )


def get_is_coarse_band(
    grading_type: str,
    nominal_size_mm: int | float,
) -> dict[float, tuple[float, float]]:
    """Return an IS 383:2016 Table 7 coarse aggregate band."""
    if grading_type == "single":
        bands = IS_COARSE_SINGLE_SIZED_BANDS
    elif grading_type == "graded":
        bands = IS_COARSE_GRADED_BANDS
    else:
        raise KeyError("grading_type must be 'single' or 'graded'")
    return bands[_normalise_size_key(nominal_size_mm, bands)]


def get_astm_coarse_band(
    nominal_size_mm: int | float,
) -> dict[float, tuple[float, float]]:
    """Return a supported ASTM C33/C33M Table 2 coarse aggregate band."""
    key = _normalise_size_key(nominal_size_mm, ASTM_COARSE_BANDS)
    return ASTM_COARSE_BANDS[key]


def get_coarse_band(
    nominal_size_mm: int | float,
) -> dict[float, tuple[float, float]]:
    """Backward-compatible alias for :func:`get_astm_coarse_band`."""
    return get_astm_coarse_band(nominal_size_mm)
