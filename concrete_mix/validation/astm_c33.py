"""ASTM C33 (edition C 33 – 99ae1) compliance evaluation for sieve analyses.

Every requirement the standard places on a fine or coarse aggregate is
checked here and reported as a :class:`ClauseCheck` that cites the clause
(or table) the limit comes from, so the UI can tell the user exactly which
clause of the standard the sample does not meet.

Coverage (see ``docs/ASTM-C33-99-Concrete-Aggregates.md``):

Fine aggregate:
  - Clause 6.1  — grading within the sieve-analysis limits
  - Clause 6.2  - not more than 45 % passing any sieve and retained on the
                  next consecutive sieve
                - fineness modulus between 2.3 and 3.1
  - Clause 6.4  - continuing shipments: FM within 0.20 of the base FM
  - Table 1     - clay lumps and friable particles
    (Clause 7.1) - material finer than the 75-µm (No. 200) sieve, with the
                  manufactured-sand dust-of-fracture relaxation
                - coal and lignite
  - Clause 7.2  - organic impurities (color test + C 87 exemptions)
  - Clause 7.3  - deleteriously reactive materials mitigation
  - Clause 8.1  - sulfate soundness (5 cycles)

Coarse aggregate:
  - Clause 10.1 / Table 2 — grading for the selected size number
  - Table 3     - clay lumps and friable particles
    (Clause 11.1) - chert lighter than 2.40 sp gr SSD
                  - sum of clay lumps, friable particles and chert
                  - material finer than the 75-µm sieve, with the Footnote
                    C relaxations (1.5 % clay-free, weighted L formula)
                  - coal and lignite
                  - abrasion (Footnote A: slag exemption + 1120 kg/m³)
                  - magnesium/sodium sulfate soundness (Footnote B)
  - Clause 11.2 - reactive materials mitigation

No Qt dependency — pure functions and dataclasses, fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.codes.tables import astm_c33_quality as q
from concrete_mix.engine.psd import PSDResult, check_conformance
from concrete_mix.validation.base import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    ClauseCheck,
)

__all__ = [
    "PASS",
    "FAIL",
    "NOT_EVALUATED",
    "ClauseCheck",
    "FineQualityInputs",
    "CoarseQualityInputs",
    "evaluate_astm_c33_fine",
    "evaluate_astm_c33_coarse",
]

_EPS = 1e-9  # inclusive-limit tolerance for floating point comparisons


# ---------------------------------------------------------------------------
# Input bundles (None / unchecked ⇒ requirement not evaluated)
# ---------------------------------------------------------------------------


@dataclass
class FineQualityInputs:
    """Laboratory results and options for the fine-aggregate checks."""

    # Clause 6.4 — continuing shipments from a given source.
    check_fm_variation: bool = False
    base_fineness_modulus: float | None = None
    # Table 1 (Clause 7.1) — mass % of total sample; None = not tested.
    clay_lumps_pct: float | None = None
    finer_75um_pct: float | None = None
    coal_lignite_pct: float | None = None
    # Option selectors that pick the applicable Table 1 limit.
    concrete_subject_to_abrasion: bool = True   # 4.2.4.3 default: 3.0 %
    surface_appearance_important: bool = False  # 4.2.4.4 default: 1.0 %
    manufactured_sand_dust_of_fracture: bool = False  # Table 1 footnote A
    # Clause 7.2 — organic impurities outcome.
    #   "not_tested" | "not_darker" | "darker_coal_lignite" |
    #   "darker_c87" | "darker_no_exemption"
    organic_status: str = "not_tested"
    c87_relative_strength_pct: float | None = None  # 7.2.3 (≥ 95 %)
    # Clause 8.1 — soundness, 5 cycles, weighted average loss %.
    soundness_loss_pct: float | None = None
    soundness_salt: str = ""  # "" | "sodium" | "magnesium"
    # Clause 7.3 — reactive materials.
    #   "not_tested" | "not_exposed" | "not_reactive" | "low_alkali_cement" |
    #   "preventive_material" | "reactive_unmitigated"
    reactivity_status: str = "not_tested"


@dataclass
class CoarseQualityInputs:
    """Laboratory results and options for the coarse-aggregate checks."""

    # Table 3 class designation, e.g. "4S". Empty → class not specified;
    # Clause 11.1 default for the weathering region is used instead.
    class_designation: str = ""
    weathering_region: str = "S"  # "S" | "M" | "N" (11.1 default classes)
    # Table 3 columns — mass %; None = not tested.
    clay_lumps_pct: float | None = None
    chert_pct: float | None = None
    finer_75um_pct: float | None = None
    coal_lignite_pct: float | None = None
    abrasion_loss_pct: float | None = None
    soundness_loss_pct: float | None = None
    soundness_salt: str = ""  # "" | "sodium" | "magnesium"
    # Footnote A — crushed air-cooled blast-furnace slag.
    is_slag: bool = False
    slag_unit_weight_kg_m3: float | None = None
    # Footnote C — material finer than 75-µm relaxations.
    essentially_clay_free: bool = False          # option (1): 1.5 %
    weighted_limit_enabled: bool = False         # option (2): L formula
    p_sand_pct: float | None = None              # P in Footnote C
    t_fine_limit_pct: float | None = None        # T (Table 1 fine limit)
    a_fine_actual_pct: float | None = None       # A (actual in fine agg)
    # Clause 11.2 — reactive materials (same statuses as fine).
    reactivity_status: str = "not_tested"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fmt(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"


def _grading_check(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    clause: str,
    title: str,
    sieve_label: str,
) -> ClauseCheck:
    """Clause 6.1 / 10.1 grading-band check from the computed PSD."""
    conforms = check_conformance(result, band)
    violations = []
    for s, p, ok in zip(result.sieve_sizes, result.percent_passing, conforms):
        if ok or s not in band:
            continue
        lo, hi = band[s]
        if lo == hi:
            limit_txt = f"{lo:g} %"
        else:
            limit_txt = f"{lo:g}–{hi:g} %"
        direction = "too fine" if p > hi else "too coarse"
        which = "max" if p > hi else "min"
        bound = hi if p > hi else lo
        violations.append(
            f"{sieve_label(s)}: {_fmt(p)} % passing vs {limit_txt} limit "
            f"({direction}, {which} {bound:g} %)"
        )
    if violations:
        shown = "; ".join(violations[:6])
        if len(violations) > 6:
            shown += f"; … and {len(violations) - 6} more sieve(s)"
        return ClauseCheck(
            clause=clause,
            title=title,
            status=FAIL,
            requirement=(
                "Grading shall be within the limits of the standard's "
                "grading table for the selected reference"
            ),
            measured=f"{len(violations)} sieve(s) out of band",
            detail=shown + ".",
        )
    if not band:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement="Grading shall be within the table limits",
            measured="no reference band selected",
        )
    return ClauseCheck(
        clause=clause,
        title=title,
        status=PASS,
        requirement="Grading within the table limits",
        measured="all specified sieves in band",
    )


def _reactivity_check(
    status: str, clause: str
) -> ClauseCheck:
    """Clause 7.3 (fine) / 11.2 (coarse) — reactive materials mitigation."""
    requirement = (
        "Aggregate for concrete subject to wetting, extended exposure to "
        "humid atmosphere, or contact with moist ground shall not contain "
        "deleteriously reactive materials in injurious amounts unless used "
        "with a cement containing less than 0.60 % alkalies (Na₂O + "
        "0.658K₂O) or with a material shown to prevent harmful expansion"
    )
    labels = {
        "not_tested": ("not tested", NOT_EVALUATED),
        "not_exposed": (
            "concrete not subject to wetting/humidity/moist ground — "
            "clause does not apply",
            PASS,
        ),
        "not_reactive": ("no injuriously reactive materials present", PASS),
        "low_alkali_cement": (
            "reactive — mitigated with low-alkali cement (< 0.60 % Na₂O eq)",
            PASS,
        ),
        "preventive_material": (
            "reactive — mitigated with a proven preventive material", PASS
        ),
        "reactive_unmitigated": (
            "reactive — no mitigation", FAIL
        ),
    }
    measured, outcome = labels.get(status, ("not tested", NOT_EVALUATED))
    detail = ""
    if outcome == FAIL:
        detail = (
            "Deleteriously reactive material is present in injurious "
            "amounts without mitigation. Use a cement containing less "
            "than 0.60 % alkalies calculated as sodium oxide equivalent "
            "(Na₂O + 0.658K₂O), or add a material that has been shown to "
            "prevent harmful expansion due to alkali-aggregate reaction "
            "(see also Appendix X1 for evaluation methods)."
        )
    return ClauseCheck(
        clause=clause,
        title="Deleteriously reactive materials (alkali-aggregate reaction)",
        status=outcome,
        requirement=requirement,
        measured=measured,
        detail=detail,
    )


def _soundness_check(
    loss: float | None,
    salt: str,
    limits_by_salt: dict[str, float],
    clause: str,
) -> ClauseCheck:
    """Clause 8.1 (fine) / Table 3 Footnote B (coarse) sulfate soundness."""
    if loss is None or salt not in limits_by_salt:
        limit_txt = " / ".join(
            f"{v:g} % ({k} sulfate)" for k, v in limits_by_salt.items()
        )
        return ClauseCheck(
            clause=clause,
            title="Sulfate soundness (5 cycles, weighted average loss)",
            status=NOT_EVALUATED,
            requirement=f"Weighted average loss not greater than {limit_txt}",
            measured="not tested",
        )
    limit = limits_by_salt[salt]
    salt_label = {"sodium": "sodium", "magnesium": "magnesium"}[salt]
    ok = loss <= limit + _EPS
    return ClauseCheck(
        clause=clause,
        title="Sulfate soundness (5 cycles, weighted average loss)",
        status=PASS if ok else FAIL,
        requirement=(
            f"Weighted average loss not greater than {limit:g} % when "
            f"{salt_label} sulfate is used"
        ),
        measured=f"{_fmt(loss)} % loss ({salt_label} sulfate)",
        detail=(
            ""
            if ok
            else f"Loss {_fmt(loss)} % exceeds the {limit:g} % limit for "
                 f"{salt_label} sulfate."
        ),
    )


# ---------------------------------------------------------------------------
# Fine aggregate
# ---------------------------------------------------------------------------


def evaluate_astm_c33_fine(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    inputs: FineQualityInputs,
) -> list[ClauseCheck]:
    """Run every ASTM C33 fine-aggregate requirement (Clauses 5–8)."""
    checks: list[ClauseCheck] = []

    def sieve_label(s: float) -> str:
        return f"{s:g} mm" if s >= 1.0 else f"{s * 1000:g} µm"

    # ── Clause 6.1 — grading within the limits ──
    checks.append(
        _grading_check(
            result, band, "6.1",
            "Grading requirements (sieve analysis)", sieve_label,
        )
    )

    # ── Clause 6.2 — 45 % max between consecutive sieves ──
    pairs: list[tuple[float, float, float]] = []  # (coarser, finer, retained %)
    for i in range(len(result.sieve_sizes) - 1):
        coarser = result.sieve_sizes[i]
        finer = result.sieve_sizes[i + 1]
        retained = (
            result.cumulative_percent_retained[i + 1]
            - result.cumulative_percent_retained[i]
        )
        pairs.append((coarser, finer, retained))
    over = [p for p in pairs if p[2] > q.FINE_MAX_RETAINED_BETWEEN_SIEVES_PCT + _EPS]
    if over:
        detail = "; ".join(
            f"{_fmt(r)} % passing {sieve_label(c)} and retained on "
            f"{sieve_label(f)}"
            for c, f, r in over[:6]
        )
        if len(over) > 6:
            detail += f"; … and {len(over) - 6} more"
        checks.append(
            ClauseCheck(
                clause="6.2",
                title="Not more than 45 % between consecutive sieves",
                status=FAIL,
                requirement=(
                    "The fine aggregate shall have not more than 45 % "
                    "passing any sieve and retained on the next consecutive "
                    "sieve of those shown in Clause 6.1"
                ),
                measured=(
                    f"{len(over)} sieve interval(s) above 45 % "
                    f"(max {_fmt(max(r for _, _, r in over))} %)"
                ),
                detail=detail + ".",
            )
        )
    else:
        worst = max((r for _, _, r in pairs), default=0.0)
        checks.append(
            ClauseCheck(
                clause="6.2",
                title="Not more than 45 % between consecutive sieves",
                status=PASS,
                requirement=(
                    "Not more than 45 % passing any sieve and retained on "
                    "the next consecutive sieve (Clause 6.1 series)"
                ),
                measured=f"max {_fmt(worst)} % between consecutive sieves",
            )
        )

    # ── Clause 6.2 — fineness modulus range ──
    if result.fineness_modulus is None:
        checks.append(
            ClauseCheck(
                clause="6.2",
                title="Fineness modulus 2.3–3.1",
                status=NOT_EVALUATED,
                requirement=(
                    "Fineness modulus shall be not less than 2.3 nor more "
                    "than 3.1"
                ),
                measured="FM not computable (standard sieves missing)",
            )
        )
    else:
        fm = result.fineness_modulus
        ok = q.FINE_FM_MIN - _EPS <= fm <= q.FINE_FM_MAX + _EPS
        checks.append(
            ClauseCheck(
                clause="6.2",
                title="Fineness modulus 2.3–3.1",
                status=PASS if ok else FAIL,
                requirement=(
                    "Fineness modulus shall be not less than 2.3 nor more "
                    "than 3.1"
                ),
                measured=f"FM = {fm:.2f}",
                detail=(
                    ""
                    if ok
                    else f"FM {fm:.2f} is "
                         + ("below the 2.3 minimum (excessively fine sand)"
                            if fm < q.FINE_FM_MIN
                            else "above the 3.1 maximum (excessively coarse sand)")
                         + "."
                ),
            )
        )

    # ── Clause 6.4 — continuing shipments FM variation ──
    if not inputs.check_fm_variation or inputs.base_fineness_modulus is None:
        checks.append(
            ClauseCheck(
                clause="6.4",
                title="FM within 0.20 of the base FM",
                status=NOT_EVALUATED,
                requirement=(
                    "For continuing shipments the fineness modulus shall not "
                    "vary more than 0.20 from the base fineness modulus of "
                    "the source"
                ),
                measured="continuing-shipment check not enabled",
            )
        )
    elif result.fineness_modulus is None:
        checks.append(
            ClauseCheck(
                clause="6.4",
                title="FM within 0.20 of the base FM",
                status=NOT_EVALUATED,
                requirement=(
                    "For continuing shipments the fineness modulus shall not "
                    "vary more than 0.20 from the base fineness "
                    "modulus of the source"
                ),
                measured="FM not computable (standard sieves missing)",
            )
        )
    else:
        variation = abs(result.fineness_modulus - inputs.base_fineness_modulus)
        ok = variation <= q.FINE_FM_VARIATION_MAX + _EPS
        checks.append(
            ClauseCheck(
                clause="6.4",
                title="FM within 0.20 of the base FM",
                status=PASS if ok else FAIL,
                requirement=(
                    "For continuing shipments the fineness modulus shall "
                    "not vary more than 0.20 from the base fineness "
                    f"modulus (base = {inputs.base_fineness_modulus:.2f})"
                ),
                measured=f"variation = {variation:.2f}",
                detail=(
                    ""
                    if ok
                    else f"FM varies {variation:.2f} from the base "
                         f"{inputs.base_fineness_modulus:.2f}; the "
                         "maximum permitted variation is 0.20."
                ),
            )
        )

    # ── Table 1 (Clause 7.1) — clay lumps and friable particles ──
    checks.append(
        _max_percent_check(
            value=inputs.clay_lumps_pct,
            limit=q.FINE_CLAY_LUMPS_MAX,
            clause="Table 1 (7.1)",
            title="Clay lumps and friable particles",
            requirement=(
                "Clay lumps and friable particles: not more than 3.0 % of "
                "total sample"
            ),
            value_label="clay lumps and friable particles",
        )
    )

    # ── Table 1 — material finer than 75-µm (No. 200) sieve ──
    if inputs.manufactured_sand_dust_of_fracture:
        finer_limit = (
            q.FINE_FINER_75UM_MANUFACTURED_ABRASION_MAX
            if inputs.concrete_subject_to_abrasion
            else q.FINE_FINER_75UM_MANUFACTURED_OTHER_MAX
        )
        basis = (
            "manufactured sand — fines are the dust of fracture, "
            "essentially free of clay or shale (Table 1 Footnote A "
            "relaxation applied)"
        )
    else:
        finer_limit = (
            q.FINE_FINER_75UM_ABRASION_MAX
            if inputs.concrete_subject_to_abrasion
            else q.FINE_FINER_75UM_OTHER_MAX
        )
        basis = (
            "concrete subject to abrasion" if inputs.concrete_subject_to_abrasion
            else "all other concrete"
        )
    checks.append(
        _max_percent_check(
            value=inputs.finer_75um_pct,
            limit=finer_limit,
            clause="Table 1 (7.1)",
            title="Material finer than 75-µm (No. 200) sieve",
            requirement=(
                f"Material finer than the 75-µm sieve: not more than "
                f"{finer_limit:g} % ({basis})"
            ),
            value_label="material finer than 75 µm",
        )
    )

    # ── Table 1 — coal and lignite ──
    coal_limit = (
        q.FINE_COAL_LIGNITE_APPEARANCE_MAX
        if inputs.surface_appearance_important
        else q.FINE_COAL_LIGNITE_OTHER_MAX
    )
    coal_basis = (
        "where surface appearance of concrete is of importance"
        if inputs.surface_appearance_important
        else "all other concrete"
    )
    checks.append(
        _max_percent_check(
            value=inputs.coal_lignite_pct,
            limit=coal_limit,
            clause="Table 1 (7.1)",
            title="Coal and lignite",
            requirement=(
                f"Coal and lignite: not more than {coal_limit:g} % "
                f"({coal_basis})"
            ),
            value_label="coal and lignite",
        )
    )

    # ── Clause 7.2 — organic impurities ──
    checks.append(_organic_impurities_check(inputs))

    # ── Clause 7.3 — reactive materials ──
    checks.append(_reactivity_check(inputs.reactivity_status, "7.3"))

    # ── Clause 8.1 — soundness ──
    checks.append(
        _soundness_check(
            inputs.soundness_loss_pct,
            inputs.soundness_salt,
            q.FINE_SOUNDNESS_MAX_BY_SALT,
            "8.1",
        )
    )

    return checks


def _max_percent_check(
    value: float | None,
    limit: float,
    clause: str,
    title: str,
    requirement: str,
    value_label: str,
) -> ClauseCheck:
    """Generic "not more than X %" requirement from a standard table."""
    if value is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement=requirement,
            measured="not tested",
        )
    ok = value <= limit + _EPS
    return ClauseCheck(
        clause=clause,
        title=title,
        status=PASS if ok else FAIL,
        requirement=requirement,
        measured=f"{_fmt(value)} % {value_label}",
        detail=(
            ""
            if ok
            else f"{value_label.capitalize()} at {_fmt(value)} % exceeds "
                 f"the {limit:.1f} % maximum."
        ),
    )


def _organic_impurities_check(inputs: FineQualityInputs) -> ClauseCheck:
    """Clause 7.2 — organic impurities color test with its exemptions."""
    requirement = (
        "Fine aggregate shall be free of injurious amounts of organic "
        "impurities; aggregates producing a color darker than the standard "
        "shall be rejected unless an exemption in 7.2.2 or 7.2.3 applies"
    )
    status = inputs.organic_status
    if status == "not_tested":
        return ClauseCheck(
            clause="7.2",
            title="Organic impurities",
            status=NOT_EVALUATED,
            requirement=requirement,
            measured="not tested",
        )
    if status == "not_darker":
        return ClauseCheck(
            clause="7.2",
            title="Organic impurities",
            status=PASS,
            requirement=requirement,
            measured="color not darker than the standard",
        )
    if status == "darker_coal_lignite":
        return ClauseCheck(
            clause="7.2.2",
            title="Organic impurities",
            status=PASS,
            requirement=requirement,
            measured=(
                "color darker than standard — discoloration due "
                "principally to small quantities of coal, lignite or "
                "similar discrete particles"
            ),
        )
    if status == "darker_c87":
        strength = inputs.c87_relative_strength_pct
        if strength is None:
            return ClauseCheck(
                clause="7.2.3",
                title="Organic impurities",
                status=NOT_EVALUATED,
                requirement=requirement,
                measured="color darker than standard; C 87 strength not entered",
            )
        ok = strength >= q.FINE_C87_MIN_RELATIVE_STRENGTH_PCT - _EPS
        return ClauseCheck(
            clause="7.2.3",
            title="Organic impurities",
            status=PASS if ok else FAIL,
            requirement=requirement,
            measured=(
                f"color darker than standard; C 87 7-day relative strength "
                f"{_fmt(strength)} %"
            ),
            detail=(
                ""
                if ok
                else f"Relative strength {_fmt(strength)} % is below the "
                     f"{q.FINE_C87_MIN_RELATIVE_STRENGTH_PCT:g} % minimum "
                     "of Test Method C 87; the aggregate fails the organic "
                     "impurities requirement."
            ),
        )
    # darker_no_exemption
    return ClauseCheck(
        clause="7.2.1",
        title="Organic impurities",
        status=FAIL,
        requirement=requirement,
        measured="color darker than the standard, no exemption applicable",
        detail=(
            "The aggregate produces a color darker than the standard and "
            "neither the coal/lignite exemption (7.2.2) nor the mortar "
            "strength exemption (7.2.3) applies; it shall be rejected."
        ),
    )


# ---------------------------------------------------------------------------
# Coarse aggregate
# ---------------------------------------------------------------------------


def evaluate_astm_c33_coarse(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
    inputs: CoarseQualityInputs,
) -> list[ClauseCheck]:
    """Run every ASTM C33 coarse-aggregate requirement (Clauses 9–11)."""
    checks: list[ClauseCheck] = []

    def sieve_label(s: float) -> str:
        return f"{s:g} mm" if s >= 1.0 else f"{s * 1000:g} µm"

    # ── Clause 10.1 / Table 2 — grading for the selected size number ──
    checks.append(
        _grading_check(
            result, band, "10.1 (Table 2)",
            "Grading requirements (size number)", sieve_label,
        )
    )

    # Resolve the Table 3 class row.
    designation = inputs.class_designation or q.REGION_DEFAULT_CLASS.get(
        inputs.weathering_region, "3S"
    )
    klass = q.get_coarse_class(designation)

    # ── Table 3 — clay lumps and friable particles ──
    checks.append(
        _class_limit_check(
            inputs.clay_lumps_pct, klass, "clay_lumps",
            clause="Table 3 (11.1)",
            title="Clay lumps and friable particles",
            value_label="clay lumps and friable particles",
        )
    )

    # ── Table 3 — chert lighter than 2.40 sp gr SSD ──
    checks.append(
        _class_limit_check(
            inputs.chert_pct, klass, "chert",
            clause="Table 3 (11.1)",
            title=f"Chert (less than {q.CHERT_SP_GRAVITY_SSD:g} sp gr SSD)",
            value_label="chert",
        )
    )

    # ── Table 3 — sum of clay lumps, friable particles and chert ──
    sum_value = (
        inputs.clay_lumps_pct + inputs.chert_pct
        if inputs.clay_lumps_pct is not None and inputs.chert_pct is not None
        else None
    )
    checks.append(
        _class_limit_check(
            sum_value, klass, "sum_deleterious",
            clause="Table 3 (11.1)",
            title="Sum of clay lumps, friable particles and chert",
            value_label="sum of deleterious substances",
        )
    )

    # ── Table 3 Footnote C — material finer than 75-µm sieve ──
    checks.append(
        _coarse_finer_75um_check(inputs, klass)
    )

    # ── Table 3 — coal and lignite ──
    checks.append(
        _class_limit_check(
            inputs.coal_lignite_pct, klass, "coal_lignite",
            clause="Table 3 (11.1)",
            title="Coal and lignite",
            value_label="coal and lignite",
        )
    )

    # ── Table 3 Footnote A — abrasion / slag unit weight ──
    checks.append(_coarse_abrasion_check(inputs))

    # ── Table 3 Footnote B — soundness ──
    checks.append(
        _soundness_check(
            inputs.soundness_loss_pct,
            inputs.soundness_salt,
            q.COARSE_SOUNDNESS_MAX_BY_SALT,
            "Table 3 (11.1), Footnote B",
        )
    )

    # ── Clause 11.2 — reactive materials ──
    checks.append(_reactivity_check(inputs.reactivity_status, "11.2"))

    return checks


def _class_limit_check(
    value: float | None,
    klass: q.CoarseClass,
    key: str,
    clause: str,
    title: str,
    value_label: str,
) -> ClauseCheck:
    """A Table 3 maximum for the selected class (dash ⇒ no requirement)."""
    limit = klass.limit(key)
    if limit is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement=(
                f"Class {klass.designation}: no requirement in Table 3 "
                "for this property"
            ),
            measured="no requirement (—) in Table 3",
        )
    return _max_percent_check(
        value=value,
        limit=limit,
        clause=clause,
        title=title,
        requirement=(
            f"Class {klass.designation}: not more than {limit:g} % "
            f"{value_label}"
        ),
        value_label=value_label,
    )


def _coarse_finer_75um_check(
    inputs: CoarseQualityInputs, klass: q.CoarseClass
) -> ClauseCheck:
    """Table 3 'material finer than 75-µm' with the Footnote C relaxations.

    The standard states the alternatives separately (1.5 % when clay-free,
    or the weighted L formula); when more than one applies the app enforces
    the most permissive applicable limit, which can never reject an
    aggregate the standard accepts.
    """
    title = "Material finer than 75-µm (No. 200) sieve"
    clause = "Table 3 (11.1), Footnote C"
    limit = q.COARSE_FINER_75UM_DEFAULT_MAX
    relaxations: list[str] = []

    if inputs.essentially_clay_free:
        limit = max(limit, q.COARSE_FINER_75UM_CLAY_FREE_MAX)
        relaxations.append(
            "essentially free of clay or shale — limit increased to 1.5 % "
            "(Footnote C, option 1)"
        )

    if inputs.weighted_limit_enabled:
        weighted = q.weighted_finer_75um_limit(
            inputs.p_sand_pct if inputs.p_sand_pct is not None else -1.0,
            inputs.t_fine_limit_pct if inputs.t_fine_limit_pct is not None else -1.0,
            inputs.a_fine_actual_pct if inputs.a_fine_actual_pct is not None else -1.0,
        )
        if weighted is None:
            relaxations.append(
                "weighted limit (Footnote C, option 2) not applicable — the "
                "actual amount in the fine aggregate must be less than its "
                "Table 1 limit (A < T)"
            )
        else:
            limit = max(limit, weighted)
            relaxations.append(
                f"weighted limit L = {weighted:.2f} % applied (Footnote C, "
                "option 2: L = 1 + [P/(100 − P)]·(T − A))"
            )

    basis = f"Class {klass.designation} base limit 1.0 %"
    if relaxations:
        basis += "; " + "; ".join(relaxations)

    if inputs.finer_75um_pct is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement=basis,
            measured="not tested",
        )
    value = inputs.finer_75um_pct
    ok = value <= limit + _EPS
    return ClauseCheck(
        clause=clause,
        title=title,
        status=PASS if ok else FAIL,
        requirement=basis,
        measured=f"{_fmt(value)} % material finer than 75 µm",
        detail=(
            ""
            if ok
            else f"Material finer than the 75-µm sieve at {_fmt(value)} % "
                 f"exceeds the {limit:.2f} % limit for Class "
                 f"{klass.designation}."
        ),
    )


def _coarse_abrasion_check(inputs: CoarseQualityInputs) -> ClauseCheck:
    """Table 3 abrasion column with the Footnote A blast-furnace-slag rule."""
    clause = "Table 3 (11.1), Footnote A"
    if inputs.is_slag:
        weight = inputs.slag_unit_weight_kg_m3
        if weight is None:
            return ClauseCheck(
                clause=clause,
                title="Abrasion / slag unit weight",
                status=NOT_EVALUATED,
                requirement=(
                    "Crushed air-cooled blast-furnace slag is excluded from "
                    f"the abrasion requirements but its rodded or jigged "
                    f"unit weight shall be not less than "
                    f"{q.COARSE_SLAG_MIN_UNIT_WEIGHT_KG_M3:g} kg/m³ (70 lb/ft³)"
                ),
                measured="slag declared; unit weight not entered",
            )
        ok = weight >= q.COARSE_SLAG_MIN_UNIT_WEIGHT_KG_M3 - _EPS
        return ClauseCheck(
            clause=clause,
            title="Abrasion / slag unit weight",
            status=PASS if ok else FAIL,
            requirement=(
                "Crushed air-cooled blast-furnace slag is excluded from the "
                f"abrasion requirements but its unit weight shall be not "
                f"less than {q.COARSE_SLAG_MIN_UNIT_WEIGHT_KG_M3:g} kg/m³ "
                "(70 lb/ft³)"
            ),
            measured=f"{weight:g} kg/m³ rodded/jigged unit weight (slag)",
            detail=(
                ""
                if ok
                else f"Slag unit weight {weight:g} kg/m³ is below the "
                     f"{q.COARSE_SLAG_MIN_UNIT_WEIGHT_KG_M3:g} kg/m³ minimum."
            ),
        )
    return _max_percent_check(
        value=inputs.abrasion_loss_pct,
        limit=q.COARSE_ABRASION_MAX,
        clause=clause,
        title="Abrasion (Los Angeles machine loss)",
        requirement=(
            f"Abrasion loss not greater than {q.COARSE_ABRASION_MAX:g} % "
            "(Test Method C 131 or C 535)"
        ),
        value_label="abrasion loss",
    )
