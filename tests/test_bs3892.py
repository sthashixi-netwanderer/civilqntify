"""BS 3892-1:1997 pfa conformity evaluator tests.

The evaluator mirrors clauses 5–12 of the standard extracted in
``BS-3892-1-1997-PFA-Specification.md``: each property reports one
:class:`ClauseCheck`, untested properties stay ``not_evaluated``, and a
failing result is flagged as a Table G.3 major defect when its deviation
exceeds the G.3 allowance (which is also the acceptance-inspection limit
at delivery per 15.4).
"""

from __future__ import annotations

from concrete_mix.validation.base import FAIL, NOT_EVALUATED, PASS
from concrete_mix.validation.bs3892 import (
    BS3892LabResults,
    evaluate_bs3892_pfa,
    major_defects,
)


def _by_clause(checks, clause):
    return next(c for c in checks if c.clause == clause)


def _conforming() -> BS3892LabResults:
    """A pfa that meets every clause-5-to-12 characteristic value."""
    return BS3892LabResults(
        moisture_pct=0.3,
        fineness_45um_pct=8.0,
        particle_density_kg_m3=2300.0,
        water_requirement_pct=92.0,
        strength_factor=0.85,
        setting_time_paste_min=170.0,
        setting_time_cement_min=160.0,
        soundness_expansion_mm=2.0,
        so3_pct=1.2,
        loi_pct=5.0,
        chloride_pct=0.03,
        cao_pct=5.0,
    )


def _with(**kw) -> BS3892LabResults:
    """The conforming pfa with one or more results overridden."""
    base = _conforming()
    return BS3892LabResults(**{**base.__dict__, **kw})


def test_conforming_pfa_passes_every_clause():
    checks = evaluate_bs3892_pfa(_conforming())
    assert len(checks) == 11
    assert all(c.status == PASS for c in checks)
    assert major_defects(checks) == []


def test_untested_properties_are_not_evaluated():
    checks = evaluate_bs3892_pfa(BS3892LabResults())
    assert len(checks) == 11
    assert all(c.status == NOT_EVALUATED for c in checks)
    assert not any(c.failed for c in checks)


def test_moisture_clause_5_boundaries():
    # clause 5: not more than 0.5 % — the limit itself passes
    assert _by_clause(evaluate_bs3892_pfa(_with(moisture_pct=0.5)), "5").status == PASS
    # 0.55 % fails the characteristic value but is within the G.3 allowance
    c = _by_clause(evaluate_bs3892_pfa(_with(moisture_pct=0.55)), "5")
    assert c.status == FAIL
    assert "Major defect" not in c.detail
    # > 0.6 % (requirement + 0.1 %) is a Table G.3 major defect
    c = _by_clause(evaluate_bs3892_pfa(_with(moisture_pct=0.61)), "5")
    assert c.status == FAIL
    assert c.detail.startswith("Major defect")
    assert "G.6" in c.detail and "15.4" in c.detail


def test_fineness_clause_6_boundaries():
    assert _by_clause(evaluate_bs3892_pfa(_with(fineness_45um_pct=12.0)), "6").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(fineness_45um_pct=12.3)), "6")
    assert c.status == FAIL and "Major defect" not in c.detail
    # +0.5 % allowance → > 12.5 % is a major defect
    assert _by_clause(evaluate_bs3892_pfa(_with(fineness_45um_pct=12.51)), "6") \
        .detail.startswith("Major defect")


def test_particle_density_clause_7_boundaries():
    # clause 7: not less than 2000 kg/m³ — the limit itself passes
    assert _by_clause(evaluate_bs3892_pfa(_with(particle_density_kg_m3=2000.0)), "7").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(particle_density_kg_m3=1975.0)), "7")
    assert c.status == FAIL and "Major defect" not in c.detail
    # −50 kg/m³ allowance → < 1950 kg/m³ is a major defect
    assert _by_clause(evaluate_bs3892_pfa(_with(particle_density_kg_m3=1949.0)), "7") \
        .detail.startswith("Major defect")


def test_water_requirement_clause_8_boundaries():
    assert _by_clause(evaluate_bs3892_pfa(_with(water_requirement_pct=95.0)), "8").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(water_requirement_pct=96.5)), "8")
    assert c.status == FAIL and "Major defect" not in c.detail
    # +2 % allowance → > 97 % is a major defect
    assert _by_clause(evaluate_bs3892_pfa(_with(water_requirement_pct=97.1)), "8") \
        .detail.startswith("Major defect")


def test_strength_factor_clause_9_is_absolute():
    # clause 9: minimum limit value 0.80 — the limit itself passes
    assert _by_clause(evaluate_bs3892_pfa(_with(strength_factor=0.80)), "9").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(strength_factor=0.79)), "9")
    assert c.status == FAIL
    # clause 1 NOTE: strength factor is an absolute limit — no G.3 allowance
    assert "Major defect" not in c.detail
    assert "absolute" in c.detail


def test_initial_setting_time_clause_10_relative():
    # clause 10: paste ≥ the Portland cement tested alone
    assert _by_clause(evaluate_bs3892_pfa(_with(setting_time_paste_min=160.0)), "10").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(setting_time_paste_min=145.0)), "10")
    assert c.status == FAIL and "Major defect" not in c.detail
    # −15 min allowance → paste below (cement − 15) is a major defect
    assert _by_clause(evaluate_bs3892_pfa(_with(setting_time_paste_min=144.0)), "10") \
        .detail.startswith("Major defect")
    # either timestamp missing → not evaluated
    assert _by_clause(evaluate_bs3892_pfa(_with(setting_time_cement_min=None)), "10") \
        .status == NOT_EVALUATED


def test_soundness_clause_11_boundaries():
    assert _by_clause(evaluate_bs3892_pfa(_with(soundness_expansion_mm=10.0)), "11").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(soundness_expansion_mm=10.5)), "11")
    assert c.status == FAIL and "Major defect" not in c.detail
    # +1 mm allowance → > 11 mm is a major defect
    assert _by_clause(evaluate_bs3892_pfa(_with(soundness_expansion_mm=11.1)), "11") \
        .detail.startswith("Major defect")


def test_chemical_composition_clause_12_boundaries():
    # 12.1 SO₃ ≤ 2.0 % (major > 2.5 %)
    assert _by_clause(evaluate_bs3892_pfa(_with(so3_pct=2.0)), "12.1").status == PASS
    assert _by_clause(evaluate_bs3892_pfa(_with(so3_pct=2.2)), "12.1").status == FAIL
    assert _by_clause(evaluate_bs3892_pfa(_with(so3_pct=2.51)), "12.1") \
        .detail.startswith("Major defect")
    # 12.2 LOI ≤ 7.0 % — absolute limit, no G.3 allowance
    assert _by_clause(evaluate_bs3892_pfa(_with(loi_pct=7.0)), "12.2").status == PASS
    c = _by_clause(evaluate_bs3892_pfa(_with(loi_pct=7.5)), "12.2")
    assert c.status == FAIL and "absolute" in c.detail
    # 12.3 chloride ≤ 0.10 % (major > 0.11 %)
    assert _by_clause(evaluate_bs3892_pfa(_with(chloride_pct=0.10)), "12.3").status == PASS
    assert _by_clause(evaluate_bs3892_pfa(_with(chloride_pct=0.105)), "12.3").status == FAIL
    assert _by_clause(evaluate_bs3892_pfa(_with(chloride_pct=0.111)), "12.3") \
        .detail.startswith("Major defect")
    # 12.4 CaO ≤ 10.0 % (major > 11.0 %)
    assert _by_clause(evaluate_bs3892_pfa(_with(cao_pct=10.0)), "12.4").status == PASS
    assert _by_clause(evaluate_bs3892_pfa(_with(cao_pct=10.5)), "12.4").status == FAIL
    assert _by_clause(evaluate_bs3892_pfa(_with(cao_pct=11.01)), "12.4") \
        .detail.startswith("Major defect")


def test_major_defects_collector():
    results = _conforming()
    bad = BS3892LabResults(**{**results.__dict__, "moisture_pct": 0.8,
                              "chloride_pct": 0.5})
    checks = evaluate_bs3892_pfa(bad)
    majors = major_defects(checks)
    assert {c.clause for c in majors} == {"5", "12.3"}
    assert all(c.failed for c in majors)
