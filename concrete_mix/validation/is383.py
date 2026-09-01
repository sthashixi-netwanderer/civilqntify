"""IS 383:2016 compliance evaluation for sieve analyses.

Every requirement the standard places on a fine or coarse aggregate is
checked here and reported as a :class:`ClauseCheck` (from
:mod:`concrete_mix.validation.base`) that cites the clause or table the
limit comes from, so the UI can tell the user exactly which requirement of
IS 383:2016 the sample does not meet — mirroring the ASTM C33 evaluator.

Coverage (see ``docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md``,
IS 383:2016 Third Revision + Amendment No. 1):

Fine aggregate:
  - Clause 6.3 / Table 9 — grading zone limits, with the Clause 6.3
    tolerance (≤ 5 % on a single non-600-µm sieve, ≤ 10 % cumulative,
    never at 600 µm / the coarse limit of Zone I / the finer limit of
    Zone IV) and the crushed-stone-sand 150 µm relaxation (Table 9 Note 1)
  - Table 2 (Clause 5.2.1) — coal & lignite, clay lumps, material finer
    than 75 µm, shale, and the total-deleterious sum, each against the
    column of the declared source type
  - Table 2 Note 3 — mica content (1 / 3 / 5 % tiers) and the
    total-including-mica limit
  - Clause 5.2 Note 4 — organic impurities with the IS 2386 (Part 6)
    relative-strength relief (≥ 95 % at 7 and 28 days)
  - Clause 5.3 — combined flakiness and elongation index ≤ 40 %
  - Clause 5.5.1 — sulphate soundness (5 cycles; guide limits)
  - Clause 5.6 — alkali-aggregate reaction (mortar-bar 38/60 °C and
    accelerated 80 °C limits)
  - Clause 5.7 / Table 3 — additional requirements for manufactured
    sources, plus Table 1 (Clause 4.2.1) utilization advisories

Coarse aggregate:
  - Clauses 6.1/6.2 / Table 7 — grading for the selected single-sized or
    graded reference
  - Table 2 (Clause 5.2.1) — coal & lignite, clay lumps, material finer
    than 75 µm, soft fragments, total-deleterious sum
  - Clause 5.3 — combined flakiness and elongation index ≤ 40 %
  - Clause 5.4 — mechanical properties (crushing value / ten percent
    fines, impact value with the M65+ limit, Los Angeles abrasion) with
    the wearing-surface distinction
  - Clause 5.5.1 — sulphate soundness (12 % sodium / 18 % magnesium)
  - Clause 5.6 — alkali-aggregate reaction
  - Clause 5.7 / Table 3 + Table 1 — manufactured-source requirements and
    utilization advisories

No Qt dependency — pure functions and dataclasses, fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.codes.tables import is383_quality as q
from concrete_mix.engine.grading import classify_is383_zone
from concrete_mix.engine.psd import PSDResult, check_conformance
from concrete_mix.validation.base import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    ClauseCheck,
)

_EPS = 1e-9

# Fine-aggregate source types (UI) → Table 2 column keys. Crushed gravel
# sand shares the "Crushed / Mixed" column with crushed stone sand; the
# 75-µm limit distinguishes crushed sand (15 %) from mixed sand (12 %).
_FINE_SOURCE_COLUMN: dict[str, str] = {
    "uncrushed": "fine_uncrushed",
    "crushed_stone_sand": "fine_crushed_stone_sand",
    "crushed_gravel_sand": "fine_crushed_stone_sand",
    "mixed_sand": "fine_mixed_sand",
    "manufactured": "fine_manufactured",
}

_COARSE_SOURCE_COLUMN: dict[str, str] = {
    "uncrushed": "coarse_uncrushed",
    "crushed": "coarse_crushed",
    "manufactured": "coarse_manufactured",
}

# Table 2 SI (vi) summands per column (mica excluded).
_TOTAL_DELETERIOUS_SUMMANDS: dict[str, tuple[str, ...]] = {
    "fine_uncrushed": ("coal_lignite_pct", "clay_lumps_pct",
                       "finer_75um_pct", "shale_pct"),
    "fine_crushed_stone_sand": ("coal_lignite_pct", "clay_lumps_pct"),
    "fine_mixed_sand": ("coal_lignite_pct", "clay_lumps_pct"),
    "fine_manufactured": ("coal_lignite_pct", "clay_lumps_pct"),
    "coarse_uncrushed": ("coal_lignite_pct", "clay_lumps_pct",
                         "finer_75um_pct", "soft_fragments_pct"),
    "coarse_crushed": ("coal_lignite_pct", "clay_lumps_pct",
                       "finer_75um_pct", "soft_fragments_pct"),
    "coarse_manufactured": ("coal_lignite_pct", "clay_lumps_pct"),
}

# Table 2 SI labels for messages.
_SUBSTANCE_LABELS: dict[str, str] = {
    "coal_lignite_pct": "Coal and lignite",
    "clay_lumps_pct": "Clay lumps",
    "finer_75um_pct": "Materials finer than 75 µm IS Sieve",
    "soft_fragments_pct": "Soft fragments",
    "shale_pct": "Shale",
}


def _fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def _sieve_label(s: float) -> str:
    return f"{s:g} mm" if s >= 1.0 else f"{s * 1000:g} µm"


def _max_check(
    value: float | None,
    limit: float | None,
    clause: str,
    title: str,
    test_ref: str,
) -> ClauseCheck:
    """Table 2 style inclusive-maximum check. ``limit=None`` reproduces a
    dash cell of the standard (no requirement) → not applicable."""
    if limit is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement="No requirement in the standard's table (dash)",
            measured="not applicable",
        )
    if value is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement=f"Not more than {limit:g} % by mass ({test_ref})",
            measured="not tested",
        )
    ok = value <= limit + _EPS
    return ClauseCheck(
        clause=clause,
        title=title,
        status=PASS if ok else FAIL,
        requirement=f"Not more than {limit:g} % by mass ({test_ref})",
        measured=f"{_fmt(value)} %",
        detail="" if ok else (
            f"{_fmt(value)} % exceeds the {limit:g} % maximum of "
            "Table 2 (Clause 5.2.1). The engineer-in-charge may relax the "
            "limits on evidence of satisfactory performance."
        ),
    )


def _grading_check_coarse(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
) -> ClauseCheck:
    """Clauses 6.1/6.2 — Table 7 grading for the selected reference."""
    check_conformance(result, band)
    violations = []
    for s, p, ok in zip(result.sieve_sizes, result.percent_passing, result.conforms):
        if ok or s not in band:
            continue
        lo, hi = band[s]
        if lo == hi:
            limit_txt = f"{lo:g} %"
        else:
            limit_txt = f"{lo:g}–{hi:g} %"
        violations.append(
            f"{_sieve_label(s)}: {_fmt(p)} % passing vs {limit_txt} limit"
        )
    if violations:
        shown = "; ".join(violations[:6])
        if len(violations) > 6:
            shown += f"; … and {len(violations) - 6} more sieve(s)"
        return ClauseCheck(
            clause="6.1 / 6.2, Table 7",
            title="Grading requirements (sieve analysis)",
            status=FAIL,
            requirement=(
                "Coarse aggregate shall be supplied in the nominal sizes of "
                "Table 7 with the proportion of other sizes also in "
                "accordance with Table 7"
            ),
            measured=f"{len(violations)} sieve(s) out of band",
            detail=shown + ".",
        )
    if not band:
        return ClauseCheck(
            clause="6.1 / 6.2, Table 7",
            title="Grading requirements (sieve analysis)",
            status=NOT_EVALUATED,
            requirement="Grading shall be within the Table 7 limits",
            measured="no reference band selected",
        )
    return ClauseCheck(
        clause="6.1 / 6.2, Table 7",
        title="Grading requirements (sieve analysis)",
        status=PASS,
        requirement="Grading within the Table 7 limits",
        measured="all specified sieves in band",
    )


def _grading_check_fine(
    result: PSDResult,
    zone: str | None,
    crushed_sand: bool,
) -> ClauseCheck:
    """Clause 6.3 / Table 9 — zone grading with the Clause 6.3 tolerance.

    The zone is keyed by the 600 µm sieve; deviations on other sieves are
    tolerated per Clause 6.3 (≤ 5 % single sieve, ≤ 10 % cumulative) but
    never at 600 µm, on the coarse limit of Zone I or the finer limit of
    Zone IV. Crushed stone sands get the 150 µm relaxation of Table 9
    Note 1.
    """
    if zone is None:
        # The classifier keys the zone from the 600 µm sieve.
        zone = None
    passing = dict(zip(result.sieve_sizes, result.percent_passing))
    classification = classify_is383_zone(passing, crushed_sand=crushed_sand)
    if classification.zone is None:
        return ClauseCheck(
            clause="6.3, Table 9",
            title="Grading requirements (sieve analysis)",
            status=NOT_EVALUATED,
            requirement="Grading shall fall within a Table 9 zone",
            measured="600 µm sieve result not available",
        )
    zone_ref = zone or classification.zone
    if classification.violations:
        return ClauseCheck(
            clause="6.3, Table 9",
            title="Grading requirements (sieve analysis)",
            status=FAIL,
            requirement=(
                "The grading of fine aggregate shall be within the limits "
                f"of Grading Zone {zone_ref} (Table 9), allowing the "
                "Clause 6.3 tolerance on sieves other than 600 µm"
            ),
            measured=f"{len(classification.violations)} sieve(s) out of zone",
            detail="; ".join(classification.violations) + ".",
        )
    note_bits: list[str] = []
    if classification.deviations:
        note_bits.append(
            "within Zone " + zone_ref + " only through the Clause 6.3 "
            "tolerance: " + "; ".join(classification.deviations)
        )
    if classification.crushed_sand_relief_used:
        note_bits.append(
            "150 µm upper limit taken as 20 % per Table 9 Note 1 "
            "(crushed stone sand)"
        )
    return ClauseCheck(
        clause="6.3, Table 9",
        title="Grading requirements (sieve analysis)",
        status=PASS,
        requirement=(
            "Grading within the limits of Grading Zone "
            f"{zone_ref} (Table 9)"
        ),
        measured=(
            "Zone " + zone_ref + (" (with tolerance)" if classification.deviations else "")
        ),
        detail=(". ".join(note_bits) + ".") if note_bits else "",
    )


def _total_deleterious_check(
    inputs,
    column: str,
) -> ClauseCheck:
    """Table 2 SI (vi) — sum of the applicable deleterious components
    (mica excluded)."""
    summands = _TOTAL_DELETERIOUS_SUMMANDS[column]
    limit = q.TABLE2_TOTAL_DELETERIOUS_MAX[column]
    values = {name: getattr(inputs, name, None) for name in summands}
    entered = {k: v for k, v in values.items() if v is not None}
    if not entered:
        return ClauseCheck(
            clause="Table 2 SI (vi), Clause 5.2.1",
            title="Total deleterious materials (excluding mica)",
            status=NOT_EVALUATED,
            requirement=(
                "Total of all deleterious materials (except mica) not more "
                f"than {limit:g} % by mass"
            ),
            measured="not tested",
        )
    total = sum(entered.values())
    complete = len(entered) == len(summands)
    ok = total <= limit + _EPS
    measured = (
        f"{_fmt(total)} % = " + " + ".join(
            f"{_SUBSTANCE_LABELS[k]} {_fmt(v)}" for k, v in entered.items()
        )
    )
    if not complete:
        measured += " (partial — not every component tested)"
    return ClauseCheck(
        clause="Table 2 SI (vi), Clause 5.2.1",
        title="Total deleterious materials (excluding mica)",
        status=PASS if ok else FAIL,
        requirement=(
            "Total of all deleterious materials (except mica) not more "
            f"than {limit:g} % by mass"
        ),
        measured=measured,
        detail="" if ok else (
            f"Total {_fmt(total)} % exceeds the {limit:g} % maximum of "
            "Table 2 (Clause 5.2.1)."
        ),
    )


def _mica_check(inputs, column: str, total_deleterious: float | None) -> ClauseCheck:
    """Table 2 Note 3 — mica content tiers + total including mica."""
    mica = inputs.mica_pct
    if mica is None:
        return ClauseCheck(
            clause="Table 2 Note 3, Clause 5.2.1",
            title="Mica content of fine aggregate",
            status=NOT_EVALUATED,
            requirement=(
                "Mica limited to 1.00 % by mass where no workability/"
                "strength/durability tests are conducted; 3.00 % for "
                "muscovite and 5.00 % for muscovite + biotite with "
                "supporting tests"
            ),
            measured="not tested",
        )
    if inputs.mica_tests_conducted:
        limit = (
            q.MICA_MUSCOVITE_BIOTITE_WITH_TESTS_MAX
            if inputs.mica_type == "muscovite_biotite"
            else q.MICA_MUSCOVITE_WITH_TESTS_MAX
        )
        tier = "with supporting tests"
    else:
        limit = q.MICA_DEFAULT_MAX
        tier = "no supporting tests conducted"
    ok = mica <= limit + _EPS
    detail = "" if ok else (
        f"Mica {_fmt(mica)} % exceeds the {limit:g} % limit applicable "
        f"when {tier} (Table 2 Note 3)."
    )
    # Total including mica — only meaningful when both parts are known.
    total_limit = q.MICA_TOTAL_INCL_DELETERIOUS_MAX.get(column)
    if total_deleterious is not None and total_limit is not None:
        grand = mica + total_deleterious
        grand_ok = grand <= total_limit + _EPS
        if not grand_ok:
            return ClauseCheck(
                clause="Table 2 Note 3, Clause 5.2.1",
                title="Mica content of fine aggregate",
                status=FAIL,
                requirement=(
                    f"Mica ≤ {limit:g} % ({tier}); total deleterious "
                    f"including mica ≤ {total_limit:g} %"
                ),
                measured=(
                    f"Mica {_fmt(mica)} %; total incl. mica {_fmt(grand)} %"
                ),
                detail=(
                    f"Total deleterious including mica is {_fmt(grand)} %, "
                    f"above the {total_limit:g} % maximum of Table 2 "
                    "Note 3."
                ),
            )
        ok = ok and grand_ok
        detail = "" if ok else detail
        measured = (
            f"Mica {_fmt(mica)} % ({tier}); total incl. mica {_fmt(grand)} %"
        )
    else:
        measured = f"Mica {_fmt(mica)} % ({tier})"
    return ClauseCheck(
        clause="Table 2 Note 3, Clause 5.2.1",
        title="Mica content of fine aggregate",
        status=PASS if ok else FAIL,
        requirement=(
            f"Mica not more than {limit:g} % by mass ({tier})"
        ),
        measured=measured,
        detail=detail,
    )


def _organic_check(inputs) -> ClauseCheck:
    """Clause 5.2 Note 4 — organic impurities with the IS 2386 (Part 6)
    relative-strength relief."""
    status = inputs.organic_status
    if status == "not_tested":
        return ClauseCheck(
            clause="5.2 Note 4",
            title="Organic impurities (colour test)",
            status=NOT_EVALUATED,
            requirement=(
                "Aggregate shall not contain harmful organic impurities "
                "[IS 2386 (Part 2)] in quantities adversely affecting "
                "strength or durability"
            ),
            measured="not tested",
        )
    if status == "pass":
        return ClauseCheck(
            clause="5.2 Note 4",
            title="Organic impurities (colour test)",
            status=PASS,
            requirement=(
                "Colour of the test solution not darker than the "
                "standard [IS 2386 (Part 2)]"
            ),
            measured="colour not darker than the standard",
        )
    # Colour test failed — the Part 6 relative-strength relief applies.
    strength = inputs.organic_relative_strength_pct
    if strength is None:
        return ClauseCheck(
            clause="5.2 Note 4",
            title="Organic impurities (colour test)",
            status=FAIL,
            requirement=(
                "A fine aggregate failing the colour test may be used only "
                "when the IS 2386 (Part 6) relative strength at 7 and 28 "
                f"days is not less than {q.ORGANIC_RELATIVE_STRENGTH_MIN_PCT:g} %"
            ),
            measured="colour darker than the standard; no mortar-strength test",
            detail=(
                "The colour test failed and no IS 2386 (Part 6) mortar "
                "strength result was provided. Supply the relative "
                "strength at 7 and 28 days, or reject the aggregate."
            ),
        )
    ok = strength >= q.ORGANIC_RELATIVE_STRENGTH_MIN_PCT - _EPS
    return ClauseCheck(
        clause="5.2 Note 4",
        title="Organic impurities (colour test)",
        status=PASS if ok else FAIL,
        requirement=(
            "Colour test failing aggregate may be used when the IS 2386 "
            "(Part 6) relative strength at 7 and 28 days is not less than "
            f"{q.ORGANIC_RELATIVE_STRENGTH_MIN_PCT:g} %"
        ),
        measured=(
            f"colour darker; relative strength {strength:g} % "
            "(7 and 28 days)"
        ),
        detail="" if ok else (
            f"Relative strength {strength:g} % is below the "
            f"{q.ORGANIC_RELATIVE_STRENGTH_MIN_PCT:g} % minimum of "
            "Clause 5.2 Note 4 — the aggregate shall be rejected."
        ),
    )


def _flakiness_elongation_check(inputs) -> ClauseCheck:
    """Clause 5.3 — combined flakiness and elongation index ≤ 40 %."""
    fi = inputs.flakiness_index_pct
    ei = inputs.elongation_index_pct
    if fi is None and ei is None:
        return ClauseCheck(
            clause="5.3",
            title="Combined flakiness and elongation index",
            status=NOT_EVALUATED,
            requirement=(
                "Combined flakiness and elongation index (flakiness index "
                "+ elongation index on the same sample, IS 2386 Part 1) "
                f"not more than {q.FLAKINESS_ELONGATION_COMBINED_MAX:g} %"
            ),
            measured="not tested",
        )
    if fi is None or ei is None:
        missing = "Flakiness index" if fi is None else "Elongation index"
        return ClauseCheck(
            clause="5.3",
            title="Combined flakiness and elongation index",
            status=NOT_EVALUATED,
            requirement=(
                "Both indices are determined on the same sample per "
                "IS 2386 (Part 1) — flaky material is removed after the "
                "flakiness test and the remainder tested for elongation"
            ),
            measured=f"{missing} not entered",
            detail=(
                "Enter both indices; the combined index is their numerical "
                "sum (Clause 5.3)."
            ),
        )
    combined = fi + ei
    ok = combined <= q.FLAKINESS_ELONGATION_COMBINED_MAX + _EPS
    return ClauseCheck(
        clause="5.3",
        title="Combined flakiness and elongation index",
        status=PASS if ok else FAIL,
        requirement=(
            "Combined flakiness and elongation index not more than "
            f"{q.FLAKINESS_ELONGATION_COMBINED_MAX:g} % for uncrushed or "
            "crushed aggregate"
        ),
        measured=f"FI {_fmt(fi, 1)} % + EI {_fmt(ei, 1)} % = {_fmt(combined, 1)} %",
        detail="" if ok else (
            f"Combined index {_fmt(combined, 1)} % exceeds the "
            f"{q.FLAKINESS_ELONGATION_COMBINED_MAX:g} % limit. The "
            "engineer-in-charge may relax it based on availability and "
            "performance tests on concrete (Clause 5.3)."
        ),
    )


def _soundness_check(kind: str, loss: float | None, salt: str) -> ClauseCheck:
    """Clause 5.5.1 — sulphate soundness, 5 cycles (guide limits of the
    Note; the limits proper are by agreement)."""
    limits = q.SOUNDNESS_MAX_BY_SALT[kind]
    if loss is None or salt not in limits:
        limit_txt = " / ".join(
            f"{v:g} % ({k} sulphate)" for k, v in limits.items()
        )
        return ClauseCheck(
            clause="5.5.1",
            title="Soundness (5 cycles, average loss)",
            status=NOT_EVALUATED,
            requirement=(
                "For concrete liable to frost action the aggregate shall "
                "pass the IS 2386 (Part 5) accelerated soundness test; "
                f"guide limits: loss not more than {limit_txt}"
            ),
            measured="not tested" if loss is None else "salt not selected",
        )
    limit = limits[salt]
    ok = loss <= limit + _EPS
    return ClauseCheck(
        clause="5.5.1",
        title="Soundness (5 cycles, average loss)",
        status=PASS if ok else FAIL,
        requirement=(
            f"Average loss after 5 cycles not more than {limit:g} % with "
            f"{salt} sulphate (guide limit; exact limits by agreement)"
        ),
        measured=f"{_fmt(loss, 1)} % loss ({salt} sulphate)",
        detail="" if ok else (
            f"Loss {_fmt(loss, 1)} % exceeds the {limit:g} % guide limit "
            f"for {salt} sulphate (Clause 5.5.1 Note)."
        ),
    )


def _aar_check(inputs) -> ClauseCheck:
    """Clause 5.6 — alkali-aggregate reaction (IS 2386 Part 7)."""
    method = inputs.aar_method
    if method == "not_tested":
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=NOT_EVALUATED,
            requirement=(
                "Aggregate shall comply with the IS 2386 (Part 7) chemical "
                "or mortar-bar requirements when liable to alkali attack"
            ),
            measured="not tested",
        )
    if method == "not_reactive":
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=PASS,
            requirement="No alkali-reactive constituent in injurious amount",
            measured="declared non-reactive",
        )
    if method == "mitigated_low_alkali":
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=PASS,
            requirement="Reactive aggregates permitted with mitigating cement",
            measured="mitigated — low-alkali cement used",
        )
    if method == "mitigated_preventive":
        return ClauseCheck(
            clause="5.6",
            title="Alkari-aggregate reactivity",
            status=PASS,
            requirement="Reactive aggregates permitted with mitigating material",
            measured="mitigated — preventive material used",
        )
    if method == "reactive_unmitigated":
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=FAIL,
            requirement=(
                "Deleteriously reactive material shall not be used "
                "unmitigated (Clause 5.6)"
            ),
            measured="reactive — no mitigation",
            detail=(
                "Damage occurs when moisture, high-alkali cement and a "
                "reactive constituent are present together (Clause 5.6). "
                "Use mitigating measures (low-alkali cement or a proven "
                "preventive material) or select another aggregate."
            ),
        )
    # Numeric expansion methods.
    expansion = inputs.aar_expansion_pct
    age = inputs.aar_age_days
    if expansion is None or age is None:
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=NOT_EVALUATED,
            requirement="Report the expansion at the test age of the method",
            measured="expansion / age not entered",
        )
    if method == "mortar_bar_38c":
        limits = q.AAR_MORTAR_BAR_38C
        label = "mortar bar, 38 °C regime"
    elif method == "mortar_bar_60c":
        limits = q.AAR_MORTAR_BAR_60C
        label = "mortar bar, 60 °C regime (slowly reactive aggregates)"
    elif method == "ambt_80c":
        return _ambt_check(expansion, age)
    else:
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=NOT_EVALUATED,
            requirement="Unknown test method",
            measured=method,
        )
    limit = limits.get(int(age))
    if limit is None:
        return ClauseCheck(
            clause="5.6",
            title="Alkali-aggregate reactivity",
            status=NOT_EVALUATED,
            requirement=(
                f"Permissible expansion for the {label}: "
                + ", ".join(f"{v:g} % at {d} days" for d, v in limits.items())
            ),
            measured=f"expansion {expansion:g} % at {age:g} days (age has no limit)",
            detail=(
                "Limits are specified only at "
                + " and ".join(f"{d} days" for d in limits)
                + " (Clause 5.6)."
            ),
        )
    ok = expansion <= limit + 1e-12
    return ClauseCheck(
        clause="5.6",
        title="Alkali-aggregate reactivity",
        status=PASS if ok else FAIL,
        requirement=(
            f"Permissible mortar-bar expansion for the {label}: "
            f"{limit:g} % at {age:g} days"
        ),
        measured=f"{expansion:g} % at {age:g} days",
        detail="" if ok else (
            f"Expansion {expansion:g} % exceeds the {limit:g} % permissible "
            f"value at {age:g} days (Clause 5.6)."
        ),
    )


def _ambt_check(expansion: float, age: int) -> ClauseCheck:
    """Clause 5.6 (3) — accelerated mortar bar test at 80 °C, 1 N NaOH."""
    if int(age) != 16:
        return ClauseCheck(
            clause="5.6 (3)",
            title="Alkali-aggregate reactivity (accelerated mortar bar)",
            status=NOT_EVALUATED,
            requirement=(
                "The AMBT criterion is expansion at 16 days after casting "
                "at 80 °C in 1 N NaOH"
            ),
            measured=f"expansion {expansion:g} % at {age:g} days",
            detail="Enter the 16-day expansion (Clause 5.6 (3)).",
        )
    if expansion > q.AAR_AMBT_DELETERIOUS_MIN + 1e-12:
        return ClauseCheck(
            clause="5.6 (3)",
            title="Alkali-aggregate reactivity (accelerated mortar bar)",
            status=FAIL,
            requirement=(
                "Expansion of more than 0.20 % at 16 days indicates "
                "potentially deleterious expansion"
            ),
            measured=f"{expansion:g} % at 16 days",
            detail=(
                "Expansion above 0.20 % at 16 days after casting is "
                "indicative of potentially deleterious expansion "
                "(Clause 5.6 (3) ii)."
            ),
        )
    if expansion < q.AAR_AMBT_INNOCUOUS_MAX - 1e-12:
        return ClauseCheck(
            clause="5.6 (3)",
            title="Alkali-aggregate reactivity (accelerated mortar bar)",
            status=PASS,
            requirement=(
                "Expansion of less than 0.10 % at 16 days is indicative of "
                "innocuous behaviour in most cases"
            ),
            measured=f"{expansion:g} % at 16 days",
            detail=(
                "Some granitic gneisses and metabasalts have proven "
                "deleteriously expansive in the field even below 0.10 % "
                "(Clause 5.6 (3) Note) — investigate prior field "
                "performance where such aggregates are suspected."
            ),
        )
    return ClauseCheck(
        clause="5.6 (3)",
        title="Alkali-aggregate reactivity (accelerated mortar bar)",
        status=PASS,
        requirement=(
            "Expansions between 0.10 and 0.20 % at 16 days include both "
            "innocuous and deleterious aggregates — supplemental "
            "information is required"
        ),
        measured=f"{expansion:g} % at 16 days — inconclusive",
        detail=(
            "Between 0.10 and 0.20 % the result is inconclusive; develop "
            "supplemental information per IS 2386 (Part 7) 4.2.2, take "
            "comparator readings to 28 days, and support with the mortar "
            "bar method at 38 °C or 60 °C as applicable (Clause 5.6 (3) iii)."
        ),
    )


def _manufactured_checks(inputs, kind: str) -> list[ClauseCheck]:
    """Clause 5.7 / Table 3 — additional requirements for manufactured
    aggregates, with Table 1 (Clause 4.2.1) utilization advisories."""
    checks: list[ClauseCheck] = []

    def rng_check(value, lo, hi, title, req):
        if value is None:
            return ClauseCheck(
                clause="5.7, Table 3",
                title=title,
                status=NOT_EVALUATED,
                requirement=req,
                measured="not tested",
            )
        ok = lo - _EPS <= value <= hi + _EPS
        return ClauseCheck(
            clause="5.7, Table 3",
            title=title,
            status=PASS if ok else FAIL,
            requirement=req,
            measured=f"{value:g}",
            detail="" if ok else f"{value:g} is outside {lo:g}–{hi:g}.",
        )

    checks.append(rng_check(
        inputs.manufactured_specific_gravity,
        q.MANUFACTURED_SG_MIN, q.MANUFACTURED_SG_MAX,
        "Specific gravity of manufactured aggregate",
        f"Specific gravity {q.MANUFACTURED_SG_MIN:g} to "
        f"{q.MANUFACTURED_SG_MAX:g} (normal-weight concrete; copper slag "
        "up to 3.8 by part replacement so the blend average stays ≤ 3.2)",
    ))

    def max_check(value, limit, title):
        if value is None:
            return ClauseCheck(
                clause="5.7, Table 3",
                title=title,
                status=NOT_EVALUATED,
                requirement=f"Not more than {limit:g} %",
                measured="not tested",
            )
        ok = value <= limit + _EPS
        return ClauseCheck(
            clause="5.7, Table 3",
            title=title,
            status=PASS if ok else FAIL,
            requirement=f"Not more than {limit:g} %",
            measured=f"{value:g} %",
            detail="" if ok else f"{value:g} % exceeds {limit:g} %.",
        )

    checks.append(max_check(
        inputs.manufactured_alkali_pct, q.MANUFACTURED_ALKALI_NA2O_EQ_MAX,
        "Total alkali content (Na₂O equivalent)",
    ))
    checks.append(max_check(
        inputs.manufactured_sulphate_pct, q.MANUFACTURED_SULPHATE_SO3_MAX,
        "Total sulphate content (SO₃)",
    ))
    checks.append(max_check(
        inputs.manufactured_chloride_pct, q.MANUFACTURED_CHLORIDE_MAX,
        "Acid soluble chloride content",
    ))

    # Water absorption — 5 % generally, 10 % for RCA/RA subject to
    # pre-wetting before batching and mixing (Table 3 Note 1).
    absorption = inputs.manufactured_absorption_pct
    if absorption is None:
        checks.append(ClauseCheck(
            clause="5.7, Table 3",
            title="Water absorption of manufactured aggregate",
            status=NOT_EVALUATED,
            requirement=(
                f"Water absorption not more than "
                f"{q.MANUFACTURED_WATER_ABSORPTION_MAX:g} %"
            ),
            measured="not tested",
        ))
    else:
        is_recycled = inputs.manufactured_type in ("rca", "ra")
        limit = (
            q.MANUFACTURED_RCA_ABSORPTION_MAX
            if is_recycled and inputs.rca_prewetted
            else q.MANUFACTURED_WATER_ABSORPTION_MAX
        )
        ok = absorption <= limit + _EPS
        checks.append(ClauseCheck(
            clause="5.7, Table 3",
            title="Water absorption of manufactured aggregate",
            status=PASS if ok else FAIL,
            requirement=(
                f"Water absorption not more than {limit:g} %"
                + (
                    " (RCA/RA with pre-wetting before batching and mixing — "
                    "Table 3 Note 1)" if limit > q.MANUFACTURED_WATER_ABSORPTION_MAX else ""
                )
            ),
            measured=f"{absorption:g} %",
            detail="" if ok else (
                f"Absorption {absorption:g} % exceeds the {limit:g} % "
                "maximum of Table 3."
            ),
        ))

    # Table 1 (Clause 4.2.1) utilization advisories + Clause 4.2.2.
    if inputs.manufactured_type in q.TABLE1_UTILIZATION_MAX_PCT:
        caps = q.TABLE1_UTILIZATION_MAX_PCT[inputs.manufactured_type]
        kind_label = "coarse" if kind == "coarse" else "fine"
        checks.append(ClauseCheck(
            clause="4.2.1, Table 1",
            title=(
                f"Extent of utilization — {inputs.manufactured_type.replace('_', ' ')} "
                f"as {kind_label} aggregate (advisory)"
            ),
            status=PASS,
            requirement=(
                "Maximum utilization as percent of total mass of the "
                f"{kind_label} aggregate: plain "
                f"{caps['plain']}, reinforced {caps['reinforced']}, lean "
                f"({caps['lean']}) — confirm the concrete use-class in the "
                "Mix Design tab"
            ),
            measured="advisory — check the mix's concrete class and grade",
            detail=q.MANUFACTURED_PRESTRESSED_PROHIBITED,
        ))
    return checks


# ---------------------------------------------------------------------------
# Input bundles (None / unchecked ⇒ requirement not evaluated)
# ---------------------------------------------------------------------------


@dataclass
class IS383FineQualityInputs:
    """Laboratory results and options for the IS 383 fine-aggregate checks."""

    # Source classification — selects the Table 2 column and the 150 µm
    # relaxation. "uncrushed" | "crushed_stone_sand" | "crushed_gravel_sand"
    # | "mixed_sand" | "manufactured"
    source_type: str = "uncrushed"
    # Table 2 (Clause 5.2.1) — mass % of total sample; None = not tested.
    coal_lignite_pct: float | None = None
    clay_lumps_pct: float | None = None
    finer_75um_pct: float | None = None
    shale_pct: float | None = None
    # Table 2 Note 3 — mica.
    mica_pct: float | None = None
    mica_type: str = "muscovite"  # "muscovite" | "muscovite_biotite"
    mica_tests_conducted: bool = False
    # Clause 5.2 Note 4 — organic impurities.
    #   "not_tested" | "pass" | "fail_color_relieved" | "fail_color"
    organic_status: str = "not_tested"
    organic_relative_strength_pct: float | None = None  # IS 2386 (Part 6)
    # Clause 5.3 — IS 2386 (Part 1) indices on the same sample.
    flakiness_index_pct: float | None = None
    elongation_index_pct: float | None = None
    # Clause 5.5.1 — soundness, 5 cycles.
    soundness_loss_pct: float | None = None
    soundness_salt: str = ""  # "" | "sodium" | "magnesium"
    # Clause 5.6 — alkali-aggregate reaction.
    #   "not_tested" | "not_reactive" | "mitigated_low_alkali" |
    #   "mitigated_preventive" | "reactive_unmitigated" |
    #   "mortar_bar_38c" | "mortar_bar_60c" | "ambt_80c"
    aar_method: str = "not_tested"
    aar_expansion_pct: float | None = None
    aar_age_days: int | None = None
    # Clause 5.7 / Table 3 — manufactured sources only.
    manufactured_type: str = ""  # "iron_slag"|"steel_slag"|"rca"|"ra"|"bottom_ash"|"copper_slag"|""
    manufactured_alkali_pct: float | None = None
    manufactured_sulphate_pct: float | None = None
    manufactured_chloride_pct: float | None = None
    manufactured_absorption_pct: float | None = None
    manufactured_specific_gravity: float | None = None
    rca_prewetted: bool = False


@dataclass
class IS383CoarseQualityInputs:
    """Laboratory results and options for the IS 383 coarse-aggregate checks."""

    # "uncrushed" | "crushed" | "manufactured"
    source_type: str = "uncrushed"
    # Table 2 (Clause 5.2.1) — mass %; None = not tested.
    coal_lignite_pct: float | None = None
    clay_lumps_pct: float | None = None
    finer_75um_pct: float | None = None
    soft_fragments_pct: float | None = None
    # Clause 5.3 — IS 2386 (Part 1) indices on the same sample.
    flakiness_index_pct: float | None = None
    elongation_index_pct: float | None = None
    # Clause 5.4 — mechanical properties, IS 2386 (Part 4).
    wearing_surfaces: bool = False  # runways, roads, pavements, spillways…
    high_grade: bool = False        # concrete of grades M65 and above
    crushing_value_pct: float | None = None
    ten_pct_fines_load_kn: float | None = None
    impact_value_pct: float | None = None
    abrasion_loss_pct: float | None = None
    # Clause 5.5.1 — soundness, 5 cycles.
    soundness_loss_pct: float | None = None
    soundness_salt: str = ""  # "" | "sodium" | "magnesium"
    # Clause 5.6 — same method set as the fine bundle.
    aar_method: str = "not_tested"
    aar_expansion_pct: float | None = None
    aar_age_days: int | None = None
    # Clause 5.7 / Table 3 — manufactured sources only.
    manufactured_type: str = ""
    manufactured_alkali_pct: float | None = None
    manufactured_sulphate_pct: float | None = None
    manufactured_chloride_pct: float | None = None
    manufactured_absorption_pct: float | None = None
    manufactured_specific_gravity: float | None = None
    rca_prewetted: bool = False


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


def evaluate_is383_fine(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    inputs: IS383FineQualityInputs,
    *,
    zone: str | None = None,
) -> list[ClauseCheck]:
    """Run every IS 383:2016 fine-aggregate requirement (Clauses 4–6)."""
    checks: list[ClauseCheck] = []
    column = _FINE_SOURCE_COLUMN.get(inputs.source_type, "fine_uncrushed")
    crushed_sand = inputs.source_type == "crushed_stone_sand"

    # ── Clause 6.3 / Table 9 — grading zone with tolerance ──
    checks.append(_grading_check_fine(result, zone, crushed_sand))

    # ── Table 2 (Clause 5.2.1) — deleterious substances ──
    checks.append(_max_check(
        inputs.coal_lignite_pct, q.TABLE2_COAL_LIGNITE_MAX,
        "Table 2 SI (i), Clause 5.2.1", "Coal and lignite",
        "IS 2386 (Part 2)",
    ))
    checks.append(_max_check(
        inputs.clay_lumps_pct, q.TABLE2_CLAY_LUMPS_MAX,
        "Table 2 SI (ii), Clause 5.2.1", "Clay lumps",
        "IS 2386 (Part 2)",
    ))
    checks.append(_max_check(
        inputs.finer_75um_pct, q.TABLE2_FINER_75UM_MAX.get(column),
        "Table 2 SI (iii), Clause 5.2.1",
        "Materials finer than 75 µm IS Sieve", "IS 2386 (Part 1)",
    ))
    checks.append(_max_check(
        inputs.shale_pct, q.TABLE2_SHALE_MAX.get(column),
        "Table 2 SI (v), Clause 5.2.1", "Shale",
        "IS 2386 (Part 2)",
    ))
    total = _total_deleterious_check(inputs, column)
    checks.append(total)
    checks.append(_mica_check(
        inputs, column,
        (
            sum(v for v in (
                inputs.coal_lignite_pct, inputs.clay_lumps_pct,
                inputs.finer_75um_pct, inputs.shale_pct,
            ) if v is not None)
            or None
        ),
    ))

    # ── Clause 5.2 Note 4 — organic impurities ──
    checks.append(_organic_check(inputs))

    # ── Clause 5.3 — combined flakiness and elongation ──
    checks.append(_flakiness_elongation_check(inputs))

    # ── Clause 5.5.1 — soundness ──
    checks.append(_soundness_check(
        "fine", inputs.soundness_loss_pct, inputs.soundness_salt
    ))

    # ── Clause 5.6 — alkali-aggregate reaction ──
    checks.append(_aar_check(inputs))

    # ── Clause 5.7 / Table 3 — manufactured sources ──
    if inputs.source_type == "manufactured":
        checks.extend(_manufactured_checks(inputs, "fine"))

    return checks


def evaluate_is383_coarse(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    inputs: IS383CoarseQualityInputs,
) -> list[ClauseCheck]:
    """Run every IS 383:2016 coarse-aggregate requirement (Clauses 4–6)."""
    checks: list[ClauseCheck] = []
    column = _COARSE_SOURCE_COLUMN.get(inputs.source_type, "coarse_uncrushed")

    # ── Clauses 6.1 / 6.2 — Table 7 grading ──
    checks.append(_grading_check_coarse(result, band))

    # ── Table 2 (Clause 5.2.1) — deleterious substances ──
    checks.append(_max_check(
        inputs.coal_lignite_pct, q.TABLE2_COAL_LIGNITE_MAX,
        "Table 2 SI (i), Clause 5.2.1", "Coal and lignite",
        "IS 2386 (Part 2)",
    ))
    checks.append(_max_check(
        inputs.clay_lumps_pct, q.TABLE2_CLAY_LUMPS_MAX,
        "Table 2 SI (ii), Clause 5.2.1", "Clay lumps",
        "IS 2386 (Part 2)",
    ))
    checks.append(_max_check(
        inputs.finer_75um_pct, q.TABLE2_FINER_75UM_MAX.get(column),
        "Table 2 SI (iii), Clause 5.2.1",
        "Materials finer than 75 µm IS Sieve", "IS 2386 (Part 1)",
    ))
    checks.append(_max_check(
        inputs.soft_fragments_pct, q.TABLE2_SOFT_FRAGMENTS_MAX.get(column),
        "Table 2 SI (iv), Clause 5.2.1", "Soft fragments",
        "IS 2386 (Part 2)",
    ))
    checks.append(_total_deleterious_check(inputs, column))

    # ── Clause 5.3 — combined flakiness and elongation ──
    checks.append(_flakiness_elongation_check(inputs))

    # ── Clause 5.4 — mechanical properties (IS 2386 Part 4) ──
    checks.extend(_mechanical_checks(inputs))

    # ── Clause 5.5.1 — soundness ──
    checks.append(_soundness_check(
        "coarse", inputs.soundness_loss_pct, inputs.soundness_salt
    ))

    # ── Clause 5.6 — alkali-aggregate reaction ──
    checks.append(_aar_check(inputs))

    # ── Clause 5.7 / Table 3 — manufactured sources ──
    if inputs.source_type == "manufactured":
        checks.extend(_manufactured_checks(inputs, "coarse"))

    return checks


def _mechanical_checks(inputs: IS383CoarseQualityInputs) -> list[ClauseCheck]:
    """Clause 5.4 — crushing value / ten percent fines, impact value and
    Los Angeles abrasion, with the wearing-surface and M65+ distinctions."""
    checks: list[ClauseCheck] = []

    # ── 5.4.1 — aggregate crushing value / ten percent fines value ──
    acv = inputs.crushing_value_pct
    if acv is None:
        checks.append(ClauseCheck(
            clause="5.4.1",
            title="Aggregate crushing value / ten percent fines value",
            status=NOT_EVALUATED,
            requirement=(
                "Crushing value per IS 2386 (Part 4): ≤ 30 % for wearing "
                "surfaces; otherwise, when the crushing value exceeds "
                f"{q.ACV_THRESHOLD_FOR_TEN_PCT_FINES:g} %, the ten percent "
                f"fines load shall be at least {q.TEN_PCT_FINES_LOAD_MIN_KN:g} kN"
            ),
            measured="not tested",
        ))
    elif inputs.high_grade:
        limit = q.ACV_HIGH_GRADE_MAX
        ok = acv <= limit + _EPS
        checks.append(ClauseCheck(
            clause="5.4.1",
            title="Aggregate crushing value / ten percent fines value",
            status=PASS if ok else FAIL,
            requirement=(
                f"For grades {q.HIGH_GRADE} and above the crushing value "
                f"shall not exceed {limit:g} % (Clause 5.4.1 Note)"
            ),
            measured=f"{_fmt(acv, 1)} %",
            detail="" if ok else (
                f"Crushing value {_fmt(acv, 1)} % exceeds the {limit:g} % "
                "limit for higher-grade concrete."
            ),
        ))
    elif inputs.wearing_surfaces:
        limit = q.ACV_WEARING_MAX
        ok = acv <= limit + _EPS
        checks.append(ClauseCheck(
            clause="5.4.1",
            title="Aggregate crushing value / ten percent fines value",
            status=PASS if ok else FAIL,
            requirement=(
                "For concrete for wearing surfaces (runways, roads, "
                f"pavements, tunnel linings carrying water, spillways, "
                f"stilling basins) the crushing value shall not exceed "
                f"{limit:g} %"
            ),
            measured=f"{_fmt(acv, 1)} %",
            detail="" if ok else (
                f"Crushing value {_fmt(acv, 1)} % exceeds the {limit:g} % "
                "wearing-surface limit."
            ),
        ))
    else:
        # Other than wearing surfaces: ACV ≤ 30 % passes outright; above
        # that the ten percent fines load governs (≥ 50 kN).
        if acv <= q.ACV_THRESHOLD_FOR_TEN_PCT_FINES + _EPS:
            checks.append(ClauseCheck(
                clause="5.4.1",
                title="Aggregate crushing value / ten percent fines value",
                status=PASS,
                requirement=(
                    "For concrete other than for wearing surfaces, a "
                    "crushing value exceeding "
                    f"{q.ACV_THRESHOLD_FOR_TEN_PCT_FINES:g} % calls for the "
                    "ten percent fines test"
                ),
                measured=f"{_fmt(acv, 1)} %",
            ))
        else:
            load = inputs.ten_pct_fines_load_kn
            if load is None:
                checks.append(ClauseCheck(
                    clause="5.4.1",
                    title="Aggregate crushing value / ten percent fines value",
                    status=NOT_EVALUATED,
                    requirement=(
                        "Crushing value above "
                        f"{q.ACV_THRESHOLD_FOR_TEN_PCT_FINES:g} % requires "
                        "the ten percent fines test with a minimum load of "
                        f"{q.TEN_PCT_FINES_LOAD_MIN_KN:g} kN"
                    ),
                    measured=(
                        f"ACV {_fmt(acv, 1)} % — ten percent fines load "
                        "not entered"
                    ),
                    detail=(
                        "The crushing value exceeds "
                        f"{q.ACV_THRESHOLD_FOR_TEN_PCT_FINES:g} %; enter "
                        "the ten percent fines load to complete the check "
                        "(Clause 5.4.1(b))."
                    ),
                ))
            else:
                ok = load >= q.TEN_PCT_FINES_LOAD_MIN_KN - _EPS
                checks.append(ClauseCheck(
                    clause="5.4.1",
                    title="Aggregate crushing value / ten percent fines value",
                    status=PASS if ok else FAIL,
                    requirement=(
                        "Where the crushing value exceeds "
                        f"{q.ACV_THRESHOLD_FOR_TEN_PCT_FINES:g} %, the "
                        "minimum load for the ten percent fines shall be "
                        f"{q.TEN_PCT_FINES_LOAD_MIN_KN:g} kN"
                    ),
                    measured=(
                        f"ACV {_fmt(acv, 1)} %; ten percent fines load "
                        f"{load:g} kN"
                    ),
                    detail="" if ok else (
                        f"Ten percent fines load {load:g} kN is below the "
                        f"{q.TEN_PCT_FINES_LOAD_MIN_KN:g} kN minimum "
                        "(Clause 5.4.1(b))."
                    ),
                ))

    # ── 5.4.2 — aggregate impact value ──
    aiv = inputs.impact_value_pct
    if aiv is None:
        limit_txt = (
            f"{q.AIV_HIGH_GRADE_MAX:g} % (M65+) / "
            f"{q.AIV_WEARING_MAX:g} % (wearing) / "
            f"{q.AIV_OTHER_MAX:g} % (other)"
        )
        checks.append(ClauseCheck(
            clause="5.4.2",
            title="Aggregate impact value",
            status=NOT_EVALUATED,
            requirement=(
                "Impact value per IS 2386 (Part 4) shall not exceed "
                f"{limit_txt}"
            ),
            measured="not tested",
        ))
    else:
        if inputs.high_grade:
            limit, why = q.AIV_HIGH_GRADE_MAX, (
                f"grades {q.HIGH_GRADE} and above (Clause 5.4.1/5.4.2 Note)"
            )
        elif inputs.wearing_surfaces:
            limit, why = q.AIV_WEARING_MAX, "wearing surfaces"
        else:
            limit, why = q.AIV_OTHER_MAX, "concrete other than wearing surfaces"
        ok = aiv <= limit + _EPS
        checks.append(ClauseCheck(
            clause="5.4.2",
            title="Aggregate impact value",
            status=PASS if ok else FAIL,
            requirement=f"Impact value shall not exceed {limit:g} % for {why}",
            measured=f"{_fmt(aiv, 1)} %",
            detail="" if ok else (
                f"Impact value {_fmt(aiv, 1)} % exceeds the {limit:g} % "
                f"limit for {why}."
            ),
        ))

    # ── 5.4.3 — aggregate abrasion value (Los Angeles machine) ──
    abrasion = inputs.abrasion_loss_pct
    if abrasion is None:
        checks.append(ClauseCheck(
            clause="5.4.3",
            title="Aggregate abrasion value (Los Angeles)",
            status=NOT_EVALUATED,
            requirement=(
                "Abrasion value per IS 2386 (Part 4), Los Angeles machine: "
                f"≤ {q.ABRASION_WEARING_MAX:g} % wearing surfaces / "
                f"≤ {q.ABRASION_OTHER_MAX:g} % other"
            ),
            measured="not tested",
        ))
    else:
        limit = (q.ABRASION_WEARING_MAX if inputs.wearing_surfaces
                 else q.ABRASION_OTHER_MAX)
        why = "wearing surfaces" if inputs.wearing_surfaces else \
            "concrete other than wearing surfaces"
        ok = abrasion <= limit + _EPS
        checks.append(ClauseCheck(
            clause="5.4.3",
            title="Aggregate abrasion value (Los Angeles)",
            status=PASS if ok else FAIL,
            requirement=f"Abrasion value shall not exceed {limit:g} % for {why}",
            measured=f"{_fmt(abrasion, 1)} %",
            detail="" if ok else (
                f"Abrasion value {_fmt(abrasion, 1)} % exceeds the "
                f"{limit:g} % limit for {why}."
            ),
        ))

    return checks
