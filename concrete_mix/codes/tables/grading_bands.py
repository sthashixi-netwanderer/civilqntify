"""Grading-limit band data for particle-size-distribution plots.

Provides the standard passing-percent bands used as the shaded conformance
overlay on the PSD curve:

- **Fine aggregate** — IS 383 grading Zones I–IV (re-exported from
  ``is_tables.GRADING_ZONE_LIMITS``). Each zone gives ``(lower%, upper%)``
  passing for sieves 10, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150 mm.
- **Coarse aggregate** — IS 383 Table 7 / ASTM C33 size-number grading
  requirements for the common nominal maximum sizes (10, 20, 40 mm).

Source standards:
  - IS 383:2016 Table 7 — Coarse aggregate grading for single-sized and
    graded aggregates.
  - ASTM C33/C33M — Standard Specification for Concrete Aggregates, Table 2
    (coarse aggregate grading requirements).
  - ACI 211.1-22 §A.4.2 — aggregate grading determined by sieve analysis
    (ASTM C136); ASTM C33 provides suitable sizes and gradings.

All band entries are ``(lower_passing%, upper_passing%)`` for a given sieve
size in millimetres. ``100`` means 100 % passing (sieve larger than NMSA);
sieves smaller than the finest specified are omitted.
"""

from __future__ import annotations

# Re-export the fine-aggregate IS 383 zone limits so callers can import all
# band data from a single module.
from concrete_mix.codes.tables.is_tables import GRADING_ZONE_LIMITS

# ---------------------------------------------------------------------------
# IS 383:2016 Table 7 — Coarse aggregate grading requirements
# ---------------------------------------------------------------------------
# Percent passing by sieve size (mm) for graded aggregates of common nominal
# maximum sizes. Values are the (lower, upper) passing limits.
#
# Sources: IS 383:2016 Table 7; ASTM C33/C33M Table 2 (size numbers 7, 57, 6
# correspond approximately to 10, 20, 40 mm graded aggregates). Where the two
# standards differ slightly, the IS 383 value is used for the mm sizes.
#
# Sieve   10 mm graded   20 mm graded   40 mm graded
#  75 mm     100            100            100
#  37.5      100            100           90–100
#  19.0      85–100        90–100         35–70
#  9.5       0–25          40–85          10–40
#  4.75      0–5            0–10           0–5
#  2.36      —              0–5            0–5
# ---------------------------------------------------------------------------

COARSE_BANDS: dict[int, dict[float, tuple[float, float]]] = {
    # 10 mm nominal maximum size (IS 383 Table 7 / ASTM C33 size 7)
    10: {
        75.0: (100, 100),
        37.5: (100, 100),
        19.0: (85, 100),
        9.5: (0, 25),
        4.75: (0, 5),
    },
    # 20 mm nominal maximum size (IS 383 Table 7 / ASTM C33 size 57)
    20: {
        75.0: (100, 100),
        37.5: (100, 100),
        19.0: (90, 100),
        9.5: (40, 85),
        4.75: (0, 10),
        2.36: (0, 5),
    },
    # 40 mm nominal maximum size (IS 383 Table 7 / ASTM C33 size 6)
    40: {
        75.0: (100, 100),
        37.5: (90, 100),
        19.0: (35, 70),
        9.5: (10, 40),
        4.75: (0, 5),
        2.36: (0, 5),
    },
}

# Available choices for the UI combo boxes
FINE_ZONES: list[str] = ["I", "II", "III", "IV"]
COARSE_NOMINAL_SIZES: list[int] = [10, 20, 40]


def get_fine_band(zone: str) -> dict[float, tuple[float, float]]:
    """Return the IS 383 passing-percent band for a fine-aggregate grading zone.

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


def get_coarse_band(nominal_size_mm: int) -> dict[float, tuple[float, float]]:
    """Return the coarse-aggregate passing-percent band for a nominal max size.

    Args:
        nominal_size_mm: Nominal maximum size — 10, 20, or 40 mm.

    Returns:
        Dict of ``{sieve_mm: (lower_passing%, upper_passing%)}``.

    Raises:
        KeyError: if *nominal_size_mm* is not in ``COARSE_BANDS``.
    """
    if nominal_size_mm not in COARSE_BANDS:
        raise KeyError(
            f"Unsupported coarse nominal size {nominal_size_mm} mm. "
            f"Valid sizes: {list(COARSE_BANDS)}"
        )
    return COARSE_BANDS[nominal_size_mm]
