"""BS 882:1992 single-sample grading and independently tested quality.

Table 4 classes overlap (also BRE 331 §1.2.5); no one sample establishes
§5.2.1's consecutive-sample condition or full BS 882 compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from concrete_mix.codes.tables.bs882 import get_bs_fine_band
from concrete_mix.engine.psd import PSDResult
from concrete_mix.validation.base import ClauseCheck, FAIL, NOT_EVALUATED, PASS


@dataclass
class BS882QualityInputs:
    """Independent laboratory quality inputs; None means not measured.

    source_type: uncrushed_gravel, partially_crushed_gravel, crushed_gravel,
        or crushed_rock. These source categories apply to both sand/coarse.
    washed_fines_pct: Washing-only 100(M1-M2)/M1 (§7.2.1), NOT dry pan plus
        washing loss and NOT PSD percent passing 75 µm (§8).
    flakiness_index_pct: Independently measured BS 812-105.1 shape index;
        PSD masses cannot supply the gauged flaky mass (clauses 3/7/8).
    """

    source_type: str = "unknown"
    heavy_duty_floor: bool = False
    washed_fines_pct: float | None = None
    flakiness_index_pct: float | None = None


def _valid_percent(value: float | None) -> bool:
    return value is not None and isfinite(value) and 0 <= value <= 100


def _validate_inputs(inputs: BS882QualityInputs) -> None:
    if inputs.source_type not in (
        "uncrushed_gravel", "partially_crushed_gravel",
        "crushed_gravel", "crushed_rock", "unknown",
    ):
        raise ValueError("Unknown BS 882 aggregate source_type")
    for value in (inputs.washed_fines_pct, inputs.flakiness_index_pct):
        if value is not None and not _valid_percent(value):
            raise ValueError("Quality percentages must be finite and within 0–100")


def _grading_check(
    passing: Mapping[float, float | None],
    band: dict[float, tuple[float, float]],
    clause: str,
    title: str,
) -> ClauseCheck:
    missing = [s for s in band if not _valid_percent(passing.get(s))]
    violations = [
        f"{s:g} mm: {passing[s]:g}% outside {lo:g}–{hi:g}%"
        for s, (lo, hi) in band.items()
        if _valid_percent(passing.get(s))
        and not lo - 1e-9 <= passing[s] <= hi + 1e-9
    ]
    # Missing controls never produce a pass; known failures remain failures.
    status = FAIL if violations else NOT_EVALUATED if missing or not band else PASS
    detail = "; ".join(violations)
    if missing:
        detail += "; missing/invalid measurements: " + ", ".join(
            f"{s:g} mm" for s in missing
        )
    return ClauseCheck(
        clause, title, status, "All specified grading controls within limits",
        "incomplete" if missing else "out of band" if violations else "in band",
        detail.strip("; "),
    )


def classify_bs882_sand(
    passing: Mapping[float, float | None],
    *,
    crushed_rock: bool = False,
    heavy_duty_floor: bool = False,
) -> tuple[str, ...]:
    """Return ALL complete matching C/M/F gradings, never interpolate gaps.

    Heavy-duty use affects the 150 µm exception, not the classification
    labels: an F-only sample remains classified F but fails §5.2.2.
    """
    return tuple(
        grade for grade in ("C", "M", "F")
        if _grading_check(
            passing, get_bs_fine_band(grade, crushed_rock=crushed_rock,
                                     heavy_duty_floor=heavy_duty_floor),
            "5.2.1, Table 4", grade,
        ).status == PASS
    )


def _max_check(
    value: float | None, limit: float | None, clause: str, title: str,
    test: str,
) -> ClauseCheck:
    status = NOT_EVALUATED if value is None or limit is None else (
        PASS if value <= limit + 1e-9 else FAIL
    )
    return ClauseCheck(
        clause, title, status,
        f"Not more than {limit:g}% ({test})" if limit is not None
        else "No explicit limit for this source category",
        "not tested" if value is None else f"{value:g}%",
    )


def _fines_check(kind: str, inputs: BS882QualityInputs) -> ClauseCheck:
    # BS 882 Table 6 (§5.4): washing-only §7.2.1, not §8 pan-combined PSD.
    if inputs.source_type == "unknown":
        return ClauseCheck(
            "5.4, Table 6", "Washed-out fines", NOT_EVALUATED,
            "Material source is required to select a Table 6 limit",
            "Material not provided",
        )
    rock = inputs.source_type == "crushed_rock"
    limit = (4 if rock else 2) if kind == "coarse" else (
        (9 if inputs.heavy_duty_floor else 16) if rock else 4
    )
    return _max_check(
        inputs.washed_fines_pct, limit, "5.4, Table 6", "Washed-out fines",
        "BS 812-103.1 §7.2.1; washing only",
    )


def evaluate_bs882_fine(
    result: PSDResult,
    inputs: BS882QualityInputs,
    *,
    grading: str = "Overall",
) -> list[ClauseCheck]:
    """Evaluate Table 4, floor-use eligibility and Table 6 for one sand."""
    _validate_inputs(inputs)
    passing = dict(zip(result.sieve_sizes, result.percent_passing))
    rock = inputs.source_type == "crushed_rock"
    band = get_bs_fine_band(grading, crushed_rock=rock,
                            heavy_duty_floor=inputs.heavy_duty_floor)
    checks = [_grading_check(passing, band, "5.2.1, Table 4",
                             f"Sand grading ({grading})")]
    checks.append(ClauseCheck(
        "5.2.1", "Ten consecutive samples", NOT_EVALUATED,
        "Not more than one in ten outside any one of C, M or F",
        "Single sample cannot establish consecutive-sample compliance",
    ))
    if inputs.heavy_duty_floor:
        grades = classify_bs882_sand(passing, crushed_rock=rock,
                                    heavy_duty_floor=True)
        complete = all(_valid_percent(passing.get(s)) for s in band)
        checks.append(ClauseCheck(
            "5.2.2", "Heavy duty floor finish sand",
            PASS if any(g in grades for g in ("C", "M")) else (
                FAIL if complete else NOT_EVALUATED
            ), "Sand must satisfy C or M", ", ".join(grades) or "No complete match",
        ))
    checks.append(_fines_check("fine", inputs))
    return checks


def evaluate_bs882_coarse(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    inputs: BS882QualityInputs,
) -> list[ClauseCheck]:
    """Evaluate Table 3, Table 6 and independent §4.2 flakiness index."""
    _validate_inputs(inputs)
    passing = dict(zip(result.sieve_sizes, result.percent_passing))
    # §4.2 gives no explicit limit for partially crushed gravel; do not
    # invent one or infer a shape index from particle-size distribution.
    fi_limit = {"uncrushed_gravel": 50, "crushed_gravel": 40,
                "crushed_rock": 40}.get(inputs.source_type)
    return [
        _grading_check(passing, band, "5.1, Table 3", "Coarse grading"),
        _fines_check("coarse", inputs),
        _max_check(inputs.flakiness_index_pct, fi_limit, "4.2",
                   "Flakiness index", "BS 812-105.1 independent shape test"),
    ]
