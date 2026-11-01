"""BS 3892-1:1997 pfa conformity evaluator (clauses 5–12, Annex G).

Every requirement of BS 3892-1:1997 — the pfa grade BRE 331 clause 9.1
assumes — is reported as one :class:`ClauseCheck` so the UI can render a
single clause-cited report regardless of which properties the laboratory
supplied. A property with no test result stays ``not_evaluated`` and never
triggers non-conformance.

Two layers of limits are distinguished, following Annex G:

* the **characteristic value** of clauses 5–12 (autocontrol conformity,
  G.4/G.5); a result outside it is a *defect*;
* the **Table G.3 major-defect level** — a deviation *in excess of* the
  stated allowance means the lot does not conform outright (G.6). The same
  levels are the acceptance-inspection limits at delivery (15.4).

Clause 1 NOTE: the strength factor and loss-on-ignition limits are
*absolute* — no G.3 allowance applies to them.

Source: ``BS-3892-1-1997-PFA-Specification.md`` (project root).
"""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.validation.base import FAIL, NOT_EVALUATED, PASS, ClauseCheck

_EPS = 1e-9

#: Deviation allowances of Table G.3, keyed by clause. A result deviating
#: from its clause 5–12 requirement by MORE than the allowance (strictly,
#: "in excess of") is a major defect. ``None`` marks the two absolute
#: limits (clause 1 NOTE): strength factor and loss on ignition.
MAJOR_DEFECT_ALLOWANCE: dict[str, float | None] = {
    "5": 0.1,      # moisture content, +0.1 %
    "6": 0.5,      # fineness, +0.5 %
    "7": 50.0,     # particle density, −50 kg/m³
    "8": 2.0,      # water requirement, +2 %
    "10": 15.0,    # initial setting time, −15 min
    "11": 1.0,     # soundness, +1 mm
    "12.1": 0.5,   # sulfuric anhydride, +0.5 % (m/m)
    "12.2": None,  # loss on ignition — absolute upper limit (clause 1 NOTE)
    "12.3": 0.01,  # chloride, +0.01 % (m/m)
    "12.4": 1.0,   # calcium oxide, +1.0 % (m/m)
    # clause 9 strength factor — absolute minimum limit (clause 1 NOTE),
    # deliberately absent here and passed as ``major_delta=None`` below.
}


@dataclass(frozen=True)
class BS3892LabResults:
    """Laboratory results for one pfa sample; ``None`` = not tested.

    Units and reporting precision follow the standard: moisture/fineness/
    chemical percentages in % (m/m), particle density in kg/m³, water
    requirement in % of the control-mortar water, strength factor
    dimensionless (reported 0.01), setting times and soundness expansion
    in minutes / mm per BS EN 196-3.
    """

    moisture_pct: float | None = None            # clause 5 (annex C)
    fineness_45um_pct: float | None = None       # clause 6 (annex D)
    particle_density_kg_m3: float | None = None  # clause 7 (BS EN 196-6 4.5.3)
    water_requirement_pct: float | None = None   # clause 8 (annex E)
    strength_factor: float | None = None         # clause 9 (annex F)
    setting_time_paste_min: float | None = None  # clause 10 (BS EN 196-3)
    setting_time_cement_min: float | None = None  # reference cement alone
    soundness_expansion_mm: float | None = None  # clause 11 (BS EN 196-3)
    so3_pct: float | None = None                 # clause 12.1
    loi_pct: float | None = None                 # clause 12.2
    chloride_pct: float | None = None            # clause 12.3
    cao_pct: float | None = None                 # clause 12.4


def _bound_check(
    clause: str,
    title: str,
    requirement: str,
    value: float | None,
    limit: float,
    unit: str,
    *,
    direction: str,
    fmt: str,
    major_delta: float | None,
) -> ClauseCheck:
    """One clause-5-to-12 requirement with an absolute numeric limit.

    ``direction`` is ``"max"`` (value shall not exceed the limit) or
    ``"min"`` (value shall not fall below it). ``major_delta`` is the
    Table G.3 allowance; ``None`` marks an absolute limit (clause 1 NOTE).
    """
    if value is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=NOT_EVALUATED,
            requirement=requirement,
            measured="not tested",
        )
    if direction == "max":
        ok = value <= limit + _EPS
        deviation = value - limit
        breach_word = "above"
    else:
        ok = value >= limit - _EPS
        deviation = limit - value
        breach_word = "below"
    measured = f"{fmt.format(value)}{unit}"
    if ok:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=PASS,
            requirement=requirement,
            measured=measured,
            detail="",
        )
    if major_delta is None:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=FAIL,
            requirement=requirement,
            measured=measured,
            detail=(
                f"{fmt.format(deviation)}{unit} {breach_word} the {fmt.format(limit)}{unit} "
                "limit. The standard sets this as an absolute limit (clause 1 "
                "NOTE) — no Table G.3 major-defect allowance applies."
            ),
        )
    if deviation > major_delta + _EPS:
        return ClauseCheck(
            clause=clause,
            title=title,
            status=FAIL,
            requirement=requirement,
            measured=measured,
            detail=(
                f"Major defect (Table G.3): the deviation {fmt.format(deviation)}{unit} "
                f"{breach_word} the {fmt.format(limit)}{unit} requirement exceeds the "
                f"{fmt.format(major_delta)}{unit} allowance — the lot does not conform "
                f"(G.6); the same level is the acceptance-inspection limit at "
                f"delivery (15.4)."
            ),
        )
    return ClauseCheck(
        clause=clause,
        title=title,
        status=FAIL,
        requirement=requirement,
        measured=measured,
        detail=(
            f"{fmt.format(deviation)}{unit} {breach_word} the {fmt.format(limit)}{unit} "
            f"requirement — a defect under G.3.3, but within the Table G.3 "
            f"major-defect allowance ({fmt.format(major_delta)}{unit}), so not a "
            f"major defect."
        ),
    )


def _setting_time_check(
    paste_min: float | None, cement_min: float | None
) -> ClauseCheck:
    """Clause 10: the combination paste sets no earlier than the cement."""
    requirement = (
        "Initial setting time of a standard-consistence paste made from the "
        "pfa/Portland cement combination (clause 8) shall be not less than "
        "that of the Portland cement tested alone (BS EN 196-3)"
    )
    if paste_min is None or cement_min is None:
        return ClauseCheck(
            clause="10",
            title="Initial setting time (combination vs cement alone)",
            status=NOT_EVALUATED,
            requirement=requirement,
            measured="not tested",
        )
    ok = paste_min >= cement_min - _EPS
    measured = f"paste {paste_min:.0f} min vs cement {cement_min:.0f} min"
    if ok:
        return ClauseCheck(
            clause="10",
            title="Initial setting time (combination vs cement alone)",
            status=PASS,
            requirement=requirement,
            measured=measured,
        )
    deviation = cement_min - paste_min
    if deviation > 15.0 + _EPS:
        detail = (
            f"Major defect (Table G.3): the paste sets {deviation:.0f} min "
            f"earlier than the cement alone — more than the 15 min allowance; "
            f"the lot does not conform (G.6); the same level is the "
            f"acceptance-inspection limit at delivery (15.4)."
        )
    else:
        detail = (
            f"The paste sets {deviation:.0f} min earlier than the cement "
            f"alone — a defect under G.3.3, but within the Table G.3 "
            f"major-defect allowance (15 min), so not a major defect."
        )
    return ClauseCheck(
        clause="10",
        title="Initial setting time (combination vs cement alone)",
        status=FAIL,
        requirement=requirement,
        measured=measured,
        detail=detail,
    )


def evaluate_bs3892_pfa(results: BS3892LabResults) -> list[ClauseCheck]:
    """Run every BS 3892-1:1997 physical and chemical requirement."""
    return [
        _bound_check(
            "5", "Moisture content",
            "Moisture content shall be not more than 0.5 % "
            "(dried at (105 ± 5) °C per annex C; report to 0.1 %)",
            results.moisture_pct, 0.5, "%",
            direction="max", fmt="{:.2f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["5"],
        ),
        _bound_check(
            "6", "Fineness (45 µm sieve residue)",
            "Proportion by mass retained on a 45 µm test sieve shall be not "
            "more than 12.0 % (wet sieving per annex D; report to 0.1 %)",
            results.fineness_45um_pct, 12.0, "%",
            direction="max", fmt="{:.2f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["6"],
        ),
        _bound_check(
            "7", "Particle density",
            "Particle density shall be not less than 2000 kg/m³ "
            "(per 4.5.3 of BS EN 196-6 : 1992)",
            results.particle_density_kg_m3, 2000.0, " kg/m³",
            direction="min", fmt="{:.0f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["7"],
        ),
        _bound_check(
            "8", "Water requirement",
            "Water requirement of a 30 % pfa : 70 % Portland cement class "
            "42.5 combination shall be not greater than 95 % of the cement "
            "alone (flow-table method per annex E; report to 1 %)",
            results.water_requirement_pct, 95.0, "%",
            direction="max", fmt="{:.1f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["8"],
        ),
        _bound_check(
            "9", "Strength factor",
            "Strength factor of the clause 8 combination shall have a "
            "minimum limit value of 0.80 (28-day test/control mortar "
            "strengths per annex F; report to 0.01)",
            results.strength_factor, 0.80, "",
            direction="min", fmt="{:.2f}",
            major_delta=None,  # absolute minimum limit (clause 1 NOTE)
        ),
        _setting_time_check(
            results.setting_time_paste_min, results.setting_time_cement_min
        ),
        _bound_check(
            "11", "Soundness",
            "Soundness of the combination paste shall have an expansion of "
            "not more than 10 mm (BS EN 196-3)",
            results.soundness_expansion_mm, 10.0, " mm",
            direction="max", fmt="{:.1f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["11"],
        ),
        _bound_check(
            "12.1", "Sulfuric anhydride (SO₃)",
            "SO₃ content shall be not more than 2.0 % (m/m) "
            "(clause 8 of BS EN 196-2 : 1995)",
            results.so3_pct, 2.0, "%",
            direction="max", fmt="{:.2f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["12.1"],
        ),
        _bound_check(
            "12.2", "Loss on ignition",
            "Loss on ignition shall have a maximum limit value of 7 % (m/m) "
            "(clause 7 of BS EN 196-2 : 1995, 1 h ignition) — absolute limit",
            results.loi_pct, 7.0, "%",
            direction="max", fmt="{:.2f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["12.2"],
        ),
        _bound_check(
            "12.3", "Chloride ion content",
            "Chloride ion content shall be not more than 0.10 % (m/m) "
            "(clause 4 of BS EN 196-21 : 1992)",
            results.chloride_pct, 0.10, "%",
            direction="max", fmt="{:.3f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["12.3"],
        ),
        _bound_check(
            "12.4", "Calcium oxide content",
            "CaO content shall be not more than 10.0 % (m/m) "
            "(clause 13 of BS EN 196-2 : 1995)",
            results.cao_pct, 10.0, "%",
            direction="max", fmt="{:.2f}",
            major_delta=MAJOR_DEFECT_ALLOWANCE["12.4"],
        ),
    ]


def major_defects(checks: list[ClauseCheck]) -> list[ClauseCheck]:
    """Checks whose deviation exceeds the Table G.3 major-defect level.

    Major-defect details open with the literal ``Major defect`` so callers
    can count them without re-deriving the limits.
    """
    return [c for c in checks if c.detail.startswith("Major defect")]
