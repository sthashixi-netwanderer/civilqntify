"""ASTM C33 quality-requirement tables — deleterious substances, physical
properties and clause limits for the PSD compliance checks.

Source of truth: ``docs/ASTM-C33-99-Concrete-Aggregates.md`` (edition
C 33 – 99ae1). Clause/table numbering follows that -99 edition: the fine
grading limits live in the Clause 6.1 inline table, Table 1 covers
deleterious substances in fine aggregate, Table 2 coarse grading (bands
already in :mod:`concrete_mix.codes.tables.grading_bands`) and Table 3 the
deleterious/physical requirements of coarse aggregate. Later C33/C33M
editions renumber the §6.1 table as "Table 1"; the UI band labels keep the
project's established C33/C33M wording while every compliance message cites
the -99 clause numbers used in the markdown reference document.

All limits are inclusive maxima in mass percent unless stated otherwise.
``None`` reproduces a dash/ellipsis cell of the standard's tables and means
"no requirement" — such checks are reported as not applicable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Fine aggregate — Clause 6.2 grading restrictions
# ---------------------------------------------------------------------------

# Clause 6.2: not more than 45 % passing any sieve and retained on the next
# consecutive sieve of those shown in 6.1.
FINE_MAX_RETAINED_BETWEEN_SIEVES_PCT: float = 45.0

# Clause 6.2: fineness modulus shall be not less than 2.3 nor more than 3.1.
FINE_FM_MIN: float = 2.3
FINE_FM_MAX: float = 3.1

# Clause 6.4: continuing shipments — FM shall not vary more than 0.20 from
# the base fineness modulus of the source.
FINE_FM_VARIATION_MAX: float = 0.20

# ---------------------------------------------------------------------------
# Fine aggregate — Table 1 (Clause 7.1) deleterious substances, mass % max
# ---------------------------------------------------------------------------

FINE_CLAY_LUMPS_MAX: float = 3.0

# Material finer than 75-µm (No. 200) sieve. Defaults follow Clauses
# 4.2.4.3/4.3.2.3: if not stated, the 3.0 % (abrasion) limit applies.
# Table 1 footnote A: for manufactured sand whose fines are the dust of
# fracture, essentially free of clay or shale, the limits may be increased
# to 5 and 7 % respectively.
FINE_FINER_75UM_ABRASION_MAX: float = 3.0
FINE_FINER_75UM_OTHER_MAX: float = 5.0
FINE_FINER_75UM_MANUFACTURED_ABRASION_MAX: float = 5.0
FINE_FINER_75UM_MANUFACTURED_OTHER_MAX: float = 7.0

# Coal and lignite. Clauses 4.2.4.4/4.3.2.4: if not stated, the 1.0 % limit
# applies.
FINE_COAL_LIGNITE_APPEARANCE_MAX: float = 0.5
FINE_COAL_LIGNITE_OTHER_MAX: float = 1.0

# ---------------------------------------------------------------------------
# Fine aggregate — Clause 8.1 sulfate soundness (5 cycles, weighted average)
# ---------------------------------------------------------------------------

FINE_SOUNDNESS_MAX_BY_SALT: dict[str, float] = {
    "sodium": 10.0,
    "magnesium": 15.0,
}

# Clause 7.2.3: a fine aggregate failing the color test may still be used
# when the C 87 mortar 7-day relative strength is not less than 95 %.
FINE_C87_MIN_RELATIVE_STRENGTH_PCT: float = 95.0

# Clauses 7.3 / 11.2: reactive materials may be used with a cement
# containing less than 0.60 % alkalies (Na₂O + 0.658K₂O) or with a material
# shown to prevent harmful expansion.
LOW_ALKALI_CEMENT_MAX_PCT: float = 0.60

# ---------------------------------------------------------------------------
# Coarse aggregate — Table 3 (Clause 11.1)
# ---------------------------------------------------------------------------

# Table 3 column: abrasion loss, max % (all classes). Footnote A: crushed
# air-cooled blast-furnace slag is excluded from abrasion but must have a
# rodded/jigged unit weight not less than 1120 kg/m³.
COARSE_ABRASION_MAX: float = 50.0
COARSE_SLAG_MIN_UNIT_WEIGHT_KG_M3: float = 1120.0

# Table 3 footnote B: soundness limit is 12 % when sodium sulfate is used
# (magnesium sulfate column value is 18 %).
COARSE_SOUNDNESS_MAX_BY_SALT: dict[str, float] = {
    "magnesium": 18.0,
    "sodium": 12.0,
}

# Material finer than the 75-µm (No. 200) sieve in coarse aggregate.
# Footnote C relaxations: (1) 1.5 % when essentially free of clay or shale;
# (2) L = 1 + [P/(100 − P)]·(T − A) when the fine-aggregate source is known
# to contain less than its Table 1 maximum (A < T).
COARSE_FINER_75UM_DEFAULT_MAX: float = 1.0
COARSE_FINER_75UM_CLAY_FREE_MAX: float = 1.5

# Chert identification threshold (Table 3 column header).
CHERT_SP_GRAVITY_SSD: float = 2.40


@dataclass(frozen=True)
class CoarseClass:
    """One Table 3 class designation row.

    ``limits`` maps a check key to its Table 3 maximum (mass %). ``None``
    reproduces the table's dash — no requirement for that class.
    """

    designation: str
    region_code: str  # "S", "M" or "N"
    description: str
    limits: dict[str, float | None] = field(default_factory=dict)

    def limit(self, key: str) -> float | None:
        return self.limits.get(key)


# Table 3 (Clause 11.1) — every class row with its stated maxima.
# Keys: clay_lumps, chert, sum_deleterious, finer_75um, coal_lignite,
# abrasion, soundness. The finer_75um column carries footnote C on every
# row; soundness carries footnote B; abrasion carries footnote A.
_TABLE3_ROWS: list[CoarseClass] = [
    # Severe weathering region
    CoarseClass("1S", "S", "Footings, foundations, columns and beams not exposed to the weather, interior floor slabs to be given coverings",
                {"clay_lumps": 10.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 1.0, "abrasion": 50.0, "soundness": None}),
    CoarseClass("2S", "S", "Interior floors without coverings",
                {"clay_lumps": 5.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": None}),
    CoarseClass("3S", "S", "Foundation walls above grade, retaining walls, abutments, piers, girders, and beams exposed to the weather",
                {"clay_lumps": 5.0, "chert": 5.0, "sum_deleterious": 7.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    CoarseClass("4S", "S", "Pavements, bridge decks, driveways and curbs, walks, patios, garage floors, exposed floors and porches, or waterfront structures, subject to frequent wetting",
                {"clay_lumps": 3.0, "chert": 5.0, "sum_deleterious": 5.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    CoarseClass("5S", "S", "Exposed architectural concrete",
                {"clay_lumps": 2.0, "chert": 3.0, "sum_deleterious": 3.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    # Moderate weathering region
    CoarseClass("1M", "M", "Footings, foundations, columns, and beams not exposed to the weather, interior floor slabs to be given coverings",
                {"clay_lumps": 10.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 1.0, "abrasion": 50.0, "soundness": None}),
    CoarseClass("2M", "M", "Interior floors without coverings",
                {"clay_lumps": 5.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": None}),
    CoarseClass("3M", "M", "Foundation walls above grade, retaining walls, abutments, piers, girders, and beams exposed to the weather",
                {"clay_lumps": 5.0, "chert": 8.0, "sum_deleterious": 10.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    CoarseClass("4M", "M", "Pavements, bridge decks, driveways and curbs, walks, patios, garage floors, exposed floors and porches, or waterfront structures subject to frequent wetting",
                {"clay_lumps": 5.0, "chert": 5.0, "sum_deleterious": 7.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    CoarseClass("5M", "M", "Exposed architectural concrete",
                {"clay_lumps": 3.0, "chert": 3.0, "sum_deleterious": 5.0, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": 18.0}),
    # Negligible weathering region
    CoarseClass("1N", "N", "Slabs subject to traffic abrasion, bridge decks, floors, sidewalks, pavements",
                {"clay_lumps": 5.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 0.5, "abrasion": 50.0, "soundness": None}),
    CoarseClass("2N", "N", "All other classes of concrete",
                {"clay_lumps": 10.0, "chert": None, "sum_deleterious": None, "finer_75um": 1.0, "coal_lignite": 1.0, "abrasion": 50.0, "soundness": None}),
]

COARSE_CLASSES: dict[str, CoarseClass] = {c.designation: c for c in _TABLE3_ROWS}

# Display order: severe → moderate → negligible.
COARSE_CLASS_ORDER: list[str] = [c.designation for c in _TABLE3_ROWS]

# Clause 11.1: when the class is not specified, the requirements for Class
# 3S, 3M or 1N apply in the severe, moderate and negligible weathering
# regions respectively.
REGION_DEFAULT_CLASS: dict[str, str] = {"S": "3S", "M": "3M", "N": "1N"}

# Table 3 NOTE 1 — weathering-region definitions (used in tooltips and the
# compliance dialog so the user never needs the standard to hand).
WEATHERING_REGIONS: dict[str, str] = {
    "S": (
        "Severe Weathering Region — a cold climate where concrete is exposed "
        "to deicing chemicals or other aggressive agents, or where concrete "
        "may become saturated by continued contact with moisture or free "
        "water prior to repeated freezing and thawing."
    ),
    "M": (
        "Moderate Weathering Region — a climate where occasional freezing is "
        "expected, but where concrete in outdoor service will not be "
        "continually exposed to freezing and thawing in the presence of "
        "moisture or to deicing chemicals."
    ),
    "N": (
        "Negligible Weathering Region — a climate where concrete is rarely "
        "exposed to freezing in the presence of moisture."
    ),
}

REGION_LABELS: dict[str, str] = {
    "S": "Severe weathering",
    "M": "Moderate weathering",
    "N": "Negligible weathering",
}


def get_coarse_class(designation: str) -> CoarseClass:
    """Return the Table 3 class row for a designation such as ``"4S"``."""
    try:
        return COARSE_CLASSES[designation]
    except KeyError:
        raise KeyError(
            f"Unknown ASTM C33 Table 3 class '{designation}'. "
            f"Valid classes: {COARSE_CLASS_ORDER}"
        ) from None


def weighted_finer_75um_limit(
    p_sand_pct: float,
    t_fine_limit_pct: float,
    a_fine_actual_pct: float,
) -> float | None:
    """Table 3 Footnote C option (2) — weighted coarse-aggregate limit.

    L = 1 + [P / (100 − P)] · (T − A), where P is the percentage of sand in
    the concrete as a percent of total aggregate, T the Table 1 limit for
    the fine aggregate and A the actual amount in the fine aggregate.

    Returns ``None`` when the precondition A < T (fine-aggregate source
    known to contain less than its specified maximum) is not met — the
    relaxation does not apply.
    """
    if a_fine_actual_pct >= t_fine_limit_pct:
        return None
    if not 0.0 <= p_sand_pct < 100.0:
        return None
    return 1.0 + (p_sand_pct / (100.0 - p_sand_pct)) * (
        t_fine_limit_pct - a_fine_actual_pct
    )
