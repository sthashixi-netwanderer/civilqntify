"""IS 383:2016 quality-requirement tables — deleterious substances,
mechanical properties, soundness and clause limits for the PSD compliance
checks.

Source of truth: ``docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md``
(IS 383:2016 Third Revision incorporating Amendment No. 1, August 2017).
Every constant carries the clause/table citation used in the compliance
messages shown to the user.

All limits are inclusive maxima in mass percent unless stated otherwise.
``None`` (or a missing dict entry) reproduces a dash/blank cell of the
standard's tables and means "no requirement" — such checks are reported as
not applicable.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Table 2 (Clause 5.2.1) — deleterious substances, mass % max
# ---------------------------------------------------------------------------
# Columns of Table 2 are keyed by aggregate kind × source type:
#   fine:    "uncrushed" | "crushed_stone_sand" | "mixed_sand" | "manufactured"
#   coarse:  "uncrushed" | "crushed" | "manufactured"
# A value of None reproduces the standard's dash (no requirement).

# SI (i) — Coal and lignite, IS 2386 (Part 2): 1.00 % in every column.
TABLE2_COAL_LIGNITE_MAX: float = 1.00

# SI (ii) — Clay lumps, IS 2386 (Part 2): 1.00 % in every column.
TABLE2_CLAY_LUMPS_MAX: float = 1.00

# SI (iii) — Materials finer than 75 µm IS Sieve, IS 2386 (Part 1).
TABLE2_FINER_75UM_MAX: dict[str, float | None] = {
    "fine_uncrushed": 3.00,
    "fine_crushed_stone_sand": 15.00,
    "fine_mixed_sand": 12.00,
    "fine_manufactured": 10.00,
    # Coarse aggregate: 1.00 % in all three source columns.
    "coarse_uncrushed": 1.00,
    "coarse_crushed": 1.00,
    "coarse_manufactured": 1.00,
}

# SI (iv) — Soft fragments, IS 2386 (Part 2) — coarse aggregate only.
# Uncrushed 3.00 %, crushed: no requirement (dash), manufactured 3.00 %.
TABLE2_SOFT_FRAGMENTS_MAX: dict[str, float | None] = {
    "coarse_uncrushed": 3.00,
    "coarse_crushed": None,
    "coarse_manufactured": 3.00,
}

# SI (v) — Shale, IS 2386 (Part 2) — fine aggregate only.
# Uncrushed 1.00 %, crushed/mixed: dash, manufactured 1.00 %.
TABLE2_SHALE_MAX: dict[str, float | None] = {
    "fine_uncrushed": 1.00,
    "fine_crushed_stone_sand": None,
    "fine_mixed_sand": None,
    "fine_manufactured": 1.00,
}

# SI (vi) — Total of all deleterious materials (except mica).
# The summands are SI (i)–(v) for the columns that list them (cols 4, 7, 8)
# and SI (i)–(ii) for the remaining columns (5, 6, 9); the numeric limits
# follow the same doc column map (col 8 Coarse-Crushed = 2.00, NOT the
# col-7 uncrushed 5.00).
TABLE2_TOTAL_DELETERIOUS_MAX: dict[str, float] = {
    "fine_uncrushed": 5.00,
    "fine_crushed_stone_sand": 2.00,
    "fine_mixed_sand": 2.00,
    "fine_manufactured": 2.00,
    "coarse_uncrushed": 5.00,
    "coarse_crushed": 2.00,
    "coarse_manufactured": 2.00,
}

# Table 2 Note 3 — mica content of fine aggregate (mass % max). Without
# supporting workability/strength/permeability/abrasion tests the limit is
# 1.00 %; with tests, 3.00 % for muscovite alone and 5.00 % when both
# muscovite and biotite are present.
MICA_DEFAULT_MAX: float = 1.00
MICA_MUSCOVITE_WITH_TESTS_MAX: float = 3.00
MICA_MUSCOVITE_BIOTITE_WITH_TESTS_MAX: float = 5.00

# Table 2 Note 3 — total deleterious materials *including* mica.
MICA_TOTAL_INCL_DELETERIOUS_MAX: dict[str, float] = {
    "fine_uncrushed": 8.00,
    "fine_crushed_stone_sand": 5.00,
    "fine_mixed_sand": 5.00,
}

# Table 2 Note 1 — the uncrushed sand blended into mixed sand shall itself
# not have more than 3.00 % finer than 75 µm (advisory for mixed sand).
MIXED_SAND_BLEND_UNCRUSHED_75UM_MAX: float = 3.00

# ---------------------------------------------------------------------------
# Clause 5.2 Note 4 — organic impurities (fine aggregate)
# ---------------------------------------------------------------------------
# A fine aggregate failing the colour test [IS 2386 (Part 2)] may still be
# used when the effect of organic impurities on mortar strength, tested per
# IS 2386 (Part 6), gives a relative strength of not less than 95 % at
# 7 and 28 days.
ORGANIC_RELATIVE_STRENGTH_MIN_PCT: float = 95.0

# ---------------------------------------------------------------------------
# Clause 5.3 — combined flakiness and elongation index
# ---------------------------------------------------------------------------
# Determined per IS 2386 (Part 1) on the same sample: flaky material is
# removed after the flakiness test and the remainder is used for the
# elongation index; the two indices are added numerically. The combined
# index shall not exceed 40 % for uncrushed or crushed aggregate
# (engineer-in-charge may relax).
FLAKINESS_ELONGATION_COMBINED_MAX: float = 40.0

# ---------------------------------------------------------------------------
# Clause 5.4 — mechanical properties (IS 2386 Part 4)
# ---------------------------------------------------------------------------

# 5.4.1 — Aggregate crushing value (ACV) for wearing surfaces (runways,
# roads, pavements, tunnel lining carrying water, spillways, stilling
# basins).
ACV_WEARING_MAX: float = 30.0

# 5.4.1(b) — for other-than-wearing concrete, when ACV exceeds 30 % the
# ten percent fines load must be at least 50 kN.
ACV_THRESHOLD_FOR_TEN_PCT_FINES: float = 30.0
TEN_PCT_FINES_LOAD_MIN_KN: float = 50.0

# 5.4.2 — Aggregate impact value (AIV).
AIV_WEARING_MAX: float = 30.0
AIV_OTHER_MAX: float = 45.0

# 5.4.1/5.4.2 Note — for grades M65 and above the stronger-aggregate
# limits apply to both crushing and impact values.
HIGH_GRADE = "M65"
ACV_HIGH_GRADE_MAX: float = 22.0
AIV_HIGH_GRADE_MAX: float = 22.0

# 5.4.3 — Aggregate abrasion value (Los Angeles machine).
ABRASION_WEARING_MAX: float = 30.0
ABRASION_OTHER_MAX: float = 50.0

# ---------------------------------------------------------------------------
# Clause 5.5.1 — soundness (IS 2386 Part 5, 5 cycles)
# ---------------------------------------------------------------------------
# The limits proper are set by agreement between purchaser and supplier;
# the Note gives these guide values for the average loss after 5 cycles.
SOUNDNESS_MAX_BY_SALT: dict[str, dict[str, float]] = {
    "fine": {"sodium": 10.0, "magnesium": 15.0},
    "coarse": {"sodium": 12.0, "magnesium": 18.0},
}

# ---------------------------------------------------------------------------
# Clause 5.6 — alkali-aggregate reaction (IS 2386 Part 7)
# ---------------------------------------------------------------------------
# Mortar bar method, 38 °C regime.
AAR_MORTAR_BAR_38C: dict[int, float] = {90: 0.05, 180: 0.10}

# Mortar bar method, 60 °C regime — for slowly reactive aggregates
# (more than 20 % strained quartz, undulatory extinction > 15°).
AAR_MORTAR_BAR_60C: dict[int, float] = {90: 0.05, 180: 0.06}

# Accelerated mortar bar test (AMBT) at 80 °C in 1 N NaOH, 16 days after
# casting: < 0.10 % innocuous in most cases, > 0.20 % potentially
# deleterious, 0.10–0.20 % inconclusive (supplemental information needed).
AAR_AMBT_INNOCUOUS_MAX: float = 0.10
AAR_AMBT_DELETERIOUS_MIN: float = 0.20

# ---------------------------------------------------------------------------
# Clause 5.7 / Table 3 — additional requirements for ALL manufactured
# aggregates (RCA, RA, slag, bottom ash, copper slag families).
# ---------------------------------------------------------------------------
MANUFACTURED_ALKALI_NA2O_EQ_MAX: float = 0.3
MANUFACTURED_SULPHATE_SO3_MAX: float = 0.5
MANUFACTURED_CHLORIDE_MAX: float = 0.04
MANUFACTURED_WATER_ABSORPTION_MAX: float = 5.0
# Note 1: RCA/RA may go up to 10 % absorption subject to pre-wetting.
MANUFACTURED_RCA_ABSORPTION_MAX: float = 10.0
# Note 3: copper slag up to SG 3.8 is allowed for part replacement such
# that the average fine-aggregate SG stays ≤ 3.2.
MANUFACTURED_SG_MIN: float = 2.1
MANUFACTURED_SG_MAX: float = 3.2

# ---------------------------------------------------------------------------
# Clause 4.2.1 / Table 1 — extent of utilization of manufactured
# aggregates, percent of total mass of fine or coarse aggregate (max).
# Strings are advisory: the concrete use-class lives in the Mix Design tab,
# so these surface as warnings, not gates.
# ---------------------------------------------------------------------------
TABLE1_UTILIZATION_MAX_PCT: dict[str, dict[str, str]] = {
    "iron_slag": {"plain": "50 %", "reinforced": "25 %", "lean": "100 %"},
    "steel_slag": {"plain": "25 %", "reinforced": "Nil", "lean": "100 %"},
    "rca": {
        "plain": "25 %",
        "reinforced": "20 % (only up to M25 grade)",
        "lean": "100 %",
    },
    "ra": {"plain": "Nil", "reinforced": "Nil", "lean": "100 %"},
    "bottom_ash": {"plain": "Nil", "reinforced": "Nil", "lean": "25 %"},
    "copper_slag": {"plain": "40 %", "reinforced": "35 %", "lean": "50 %"},
}

# Clause 4.2.2 — manufactured aggregates shall not be permitted for use in
# prestressed concrete (advisory warning only).
MANUFACTURED_PRESTRESSED_PROHIBITED = (
    "Manufactured aggregates shall not be permitted for use in prestressed "
    "concrete (IS 383:2016 Clause 4.2.2)."
)

# ---------------------------------------------------------------------------
# Clause 6.3 — zone-classification tolerance on the fine grading
# ---------------------------------------------------------------------------
# Where the grading falls outside the limits of a zone on sieves OTHER than
# the 600 µm sieve by not more than 5 % for a single sieve (subject to a
# cumulative total of 10 %), it is still regarded as within that zone. The
# tolerance shall NOT be applied to:
#   - the percentage passing the 600 µm sieve, or
#   - the coarse limit of Grading Zone I (lower bounds of Zone I), or
#   - the finer limit of Grading Zone IV (upper bounds of Zone IV).
ZONE_TOLERANCE_SINGLE_SIEVE_PCT: float = 5.0
ZONE_TOLERANCE_CUMULATIVE_PCT: float = 10.0
ZONE_TOLERANCE_EXEMPT_SIEVE_MM: float = 0.600

# Table 9 Note 1 — for crushed stone sands the permissible limit on the
# 150 µm sieve is increased to 20 percent. The note adds that this "does
# not affect the 5 percent allowance permitted in 6.3 applying to other
# sieve sizes", so the raised limit is a hard limit at 150 µm for crushed
# stone sand (no Clause 6.3 tolerance stacked on it), while natural sand
# keeps the plain 10 % limit with the Clause 6.3 tolerance available.
ZONE_150UM_CRUSHED_STONE_SAND_MAX: float = 20.0

# Table 9 Note 4 — Zone IV fine aggregate should not be used in reinforced
# concrete unless tests have been made to ascertain the suitability of the
# proposed mix proportions (advisory).
ZONE_IV_RC_CAUTION = (
    "Fine aggregate conforming to Grading Zone IV should not be used in "
    "reinforced concrete unless tests have been made to ascertain the "
    "suitability of the proposed mix proportions (IS 383:2016 Table 9 "
    "Note 4)."
)

# Table 9 Note 3 — as the grading becomes finer (Zone I → IV) the ratio of
# fine to coarse aggregate should be progressively reduced (advisory; the
# IS 10262 engine already accounts for this through Table 5).
ZONE_FINER_RATIO_NOTE = (
    "As the fine-aggregate grading becomes progressively finer (Zones I to "
    "IV), the ratio of fine to coarse aggregate should be progressively "
    "reduced (IS 383:2016 Table 9 Note 3)."
)
