"""ASTM C33 compliance engine tests — every clause check, pass and fail.

Values verified against docs/ASTM-C33-99-Concrete-Aggregates.md
(Clauses 6–8 fine aggregate; 9–11 + Tables 2 and 3 coarse aggregate).
"""

from __future__ import annotations

import pytest

from concrete_mix.codes.tables import astm_c33_quality as q
from concrete_mix.codes.tables.grading_bands import (
    ASTM_COARSE_BANDS,
    get_astm_coarse_band,
    get_astm_fine_band,
)
from concrete_mix.engine.psd import (
    ASTM_COARSE_SIEVES,
    ASTM_FINE_SIEVES,
    compute_psd,
)
from concrete_mix.validation.astm_c33 import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    CoarseQualityInputs,
    FineQualityInputs,
    evaluate_astm_c33_coarse,
    evaluate_astm_c33_fine,
)


def _fine_result(masses=None, pan=5.0):
    """A conforming ASTM C33 fine sand by default (FM = 3.05)."""
    if masses is None:
        masses = [0, 2, 10, 30, 25, 20, 8]
    return compute_psd(masses, ASTM_FINE_SIEVES, pan_mass=pan)


def _coarse_result(masses=None, pan=0.0, nominal=20):
    """A conforming Size 67 (20 mm) coarse aggregate by default."""
    if masses is None:
        # 25.0:0, 19.0:8, 12.5:30, 9.5:40, 4.75:15, 2.36:4, 1.18:2, 0.300:1
        masses = [0, 0, 0, 0, 0, 0, 0, 8, 30, 40, 15, 4, 2, 1]
    return compute_psd(masses, ASTM_COARSE_SIEVES, pan_mass=pan)


def _get(checks, clause, title_part):
    """Find a check by clause and title fragment."""
    matches = [
        c
        for c in checks
        if c.clause == clause and title_part.lower() in c.title.lower()
    ]
    assert matches, (
        f"no check with clause {clause} matching {title_part!r}; "
        f"have: {[(c.clause, c.title) for c in checks]}"
    )
    return matches[0]


# ── Fine aggregate — grading clauses ──────────────────────────────────


def test_fine_conforming_sample_passes_6_1_and_6_2():
    result = _fine_result()
    checks = evaluate_astm_c33_fine(result, get_astm_fine_band(), FineQualityInputs())
    assert _get(checks, "6.1", "grading").status == PASS
    assert _get(checks, "6.2", "45 %").status == PASS
    assert _get(checks, "6.2", "fineness modulus").status == PASS
    assert result.fineness_modulus == pytest.approx(3.05)


def test_fine_out_of_band_gradation_fails_clause_6_1():
    # 2.36 mm: 75 % passing < 80 % lower limit — too coarse.
    result = _fine_result(masses=[0, 5, 20, 35, 20, 12, 3])
    checks = evaluate_astm_c33_fine(result, get_astm_fine_band(), FineQualityInputs())
    check = _get(checks, "6.1", "grading")
    assert check.status == FAIL
    assert "2.36 mm" in check.detail
    assert "too coarse" in check.detail


def test_fine_retention_above_45_pct_fails_clause_6_2():
    # 50 % passing 2.36 mm and retained on 1.18 mm.
    result = _fine_result(masses=[0, 1, 9, 50, 20, 12, 3])
    checks = evaluate_astm_c33_fine(result, get_astm_fine_band(), FineQualityInputs())
    check = _get(checks, "6.2", "45 %")
    assert check.status == FAIL
    assert "50.0 %" in check.measured
    assert "1.18 mm" in check.detail and "2.36 mm" in check.detail


def test_fine_fm_above_3_1_and_below_2_3_fail_clause_6_2():
    coarse = evaluate_astm_c33_fine(
        _fine_result(masses=[0, 5, 20, 35, 20, 12, 3]),
        get_astm_fine_band(),
        FineQualityInputs(),
    )
    check = _get(coarse, "6.2", "fineness modulus")
    assert check.status == FAIL
    assert "above the 3.1 maximum" in check.detail

    fine = evaluate_astm_c33_fine(
        _fine_result(masses=[0, 0, 2, 10, 25, 33, 25]),
        get_astm_fine_band(),
        FineQualityInputs(),
    )
    check = _get(fine, "6.2", "fineness modulus")
    assert check.status == FAIL
    assert "below the 2.3 minimum" in check.detail


def test_fine_fm_boundary_values_2_3_and_3_1_pass():
    # FM exactly 3.10 (Clause 6.2 upper bound, inclusive) — conforms.
    result = compute_psd(
        [0, 2, 10, 30, 23, 24, 11], ASTM_FINE_SIEVES, pan_mass=0.0
    )
    assert result.fineness_modulus == pytest.approx(3.10)
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs()
    )
    assert _get(checks, "6.2", "fineness modulus").status == PASS
    assert _get(checks, "6.1", "grading").status == PASS

    # FM exactly 2.30 (Clause 6.2 lower bound, inclusive) — conforms.
    result = compute_psd(
        [0, 0, 5, 15, 25, 25, 20], ASTM_FINE_SIEVES, pan_mass=10.0
    )
    assert result.fineness_modulus == pytest.approx(2.30)
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs()
    )
    assert _get(checks, "6.2", "fineness modulus").status == PASS


def test_fine_fm_variation_clause_6_4():
    result = _fine_result()  # FM 3.05
    far = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(check_fm_variation=True, base_fineness_modulus=2.60),
    )
    check = _get(far, "6.4", "0.20")
    assert check.status == FAIL
    assert check.measured == "variation = 0.45"

    near = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(check_fm_variation=True, base_fineness_modulus=2.95),
    )
    assert _get(near, "6.4", "0.20").status == PASS

    off = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs()
    )
    assert _get(off, "6.4", "0.20").status == NOT_EVALUATED


# ── Fine aggregate — Table 1 deleterious substances ────────────────────


def test_fine_clay_lumps_table_1():
    result = _fine_result()
    fail = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs(clay_lumps_pct=3.5)
    )
    check = _get(fail, "Table 1 (7.1)", "clay lumps")
    assert check.status == FAIL
    assert "3.0" in check.detail

    ok = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs(clay_lumps_pct=2.9)
    )
    assert _get(ok, "Table 1 (7.1)", "clay lumps").status == PASS

    na = evaluate_astm_c33_fine(
        result, get_astm_fine_band(), FineQualityInputs()
    )
    assert _get(na, "Table 1 (7.1)", "clay lumps").status == NOT_EVALUATED


def test_fine_material_finener_than_75um_limit_selection():
    result = _fine_result()
    # Abrasion exposure (default): 3.0 % limit.
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(finer_75um_pct=4.0, concrete_subject_to_abrasion=True),
    )
    check = _get(checks, "Table 1 (7.1)", "75-µm")
    assert check.status == FAIL
    assert "3 % (concrete subject to abrasion)" in check.requirement

    # All other concrete: 5.0 % limit — same value passes.
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(finer_75um_pct=4.0, concrete_subject_to_abrasion=False),
    )
    assert _get(checks, "Table 1 (7.1)", "75-µm").status == PASS

    # Manufactured sand dust of fracture: 5/7 limits (Table 1 Footnote A).
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(
            finer_75um_pct=6.5,
            concrete_subject_to_abrasion=False,
            manufactured_sand_dust_of_fracture=True,
        ),
    )
    check = _get(checks, "Table 1 (7.1)", "75-µm")
    assert check.status == PASS
    assert "7 %" in check.requirement

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(
            finer_75um_pct=4.5,
            concrete_subject_to_abrasion=True,
            manufactured_sand_dust_of_fracture=True,
        ),
    )
    check = _get(checks, "Table 1 (7.1)", "75-µm")
    assert check.status == PASS
    assert "5 %" in check.requirement


def test_fine_coal_and_lignite_table_1():
    result = _fine_result()
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(coal_lignite_pct=0.8, surface_appearance_important=True),
    )
    check = _get(checks, "Table 1 (7.1)", "coal")
    assert check.status == FAIL
    assert "0.5" in check.requirement

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(coal_lignite_pct=0.8, surface_appearance_important=False),
    )
    assert _get(checks, "Table 1 (7.1)", "coal").status == PASS


# ── Fine aggregate — 7.2 / 7.3 / 8.1 ──────────────────────────────────


def test_fine_organic_impurities_clause_7_2():
    result = _fine_result()

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(organic_status="darker_no_exemption"),
    )
    check = _get(checks, "7.2.1", "organic")
    assert check.status == FAIL
    assert "rejected" in check.detail

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(
            organic_status="darker_c87", c87_relative_strength_pct=94.0
        ),
    )
    assert _get(checks, "7.2.3", "organic").status == FAIL

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(
            organic_status="darker_c87", c87_relative_strength_pct=95.0
        ),
    )
    assert _get(checks, "7.2.3", "organic").status == PASS

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(organic_status="darker_coal_lignite"),
    )
    assert _get(checks, "7.2.2", "organic").status == PASS


def test_fine_reactivity_clause_7_3():
    result = _fine_result()
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(reactivity_status="reactive_unmitigated"),
    )
    check = _get(checks, "7.3", "reactive")
    assert check.status == FAIL
    assert "0.60" in check.detail

    for status in ("low_alkali_cement", "preventive_material"):
        checks = evaluate_astm_c33_fine(
            result, get_astm_fine_band(),
            FineQualityInputs(reactivity_status=status),
        )
        assert _get(checks, "7.3", "reactive").status == PASS


def test_fine_soundness_clause_8_1():
    result = _fine_result()
    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(soundness_loss_pct=10.5, soundness_salt="sodium"),
    )
    check = _get(checks, "8.1", "soundness")
    assert check.status == FAIL
    assert "10 %" in check.requirement

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(soundness_loss_pct=10.0, soundness_salt="sodium"),
    )
    assert _get(checks, "8.1", "soundness").status == PASS

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(soundness_loss_pct=15.0, soundness_salt="magnesium"),
    )
    assert _get(checks, "8.1", "soundness").status == PASS

    checks = evaluate_astm_c33_fine(
        result, get_astm_fine_band(),
        FineQualityInputs(soundness_loss_pct=15.0, soundness_salt="sodium"),
    )
    assert _get(checks, "8.1", "soundness").status == FAIL


# ── Coarse aggregate ───────────────────────────────────────────────────


def test_coarse_conforming_size_67_passes_10_1():
    result = _coarse_result()
    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20), CoarseQualityInputs()
    )
    assert _get(checks, "10.1 (Table 2)", "grading").status == PASS


def test_coarse_out_of_band_gradation_fails_10_1():
    # 4.75 mm: 12 % passing > 10 % upper limit for Size 67.
    masses = [0, 0, 0, 0, 0, 0, 0, 8, 30, 40, 10, 7, 2, 3]
    result = compute_psd(masses, ASTM_COARSE_SIEVES, pan_mass=0.0)
    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20), CoarseQualityInputs()
    )
    check = _get(checks, "10.1 (Table 2)", "grading")
    assert check.status == FAIL
    assert "4.75 mm" in check.detail
    assert "too fine" in check.detail


def test_coarse_table_3_class_limits():
    result = _coarse_result()
    inputs = CoarseQualityInputs(class_designation="4S")
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    assert _get(checks, "Table 3 (11.1)", "clay lumps").requirement.startswith(
        "Class 4S: not more than 3 %"
    )

    fail = CoarseQualityInputs(class_designation="4S", clay_lumps_pct=3.5)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), fail)
    assert _get(checks, "Table 3 (11.1)", "clay lumps").status == FAIL

    # Same value passes the more lenient Class 3M (5.0 %).
    ok = CoarseQualityInputs(class_designation="3M", clay_lumps_pct=3.5)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), ok)
    assert _get(checks, "Table 3 (11.1)", "clay lumps").status == PASS


def test_coarse_chert_and_sum_checks():
    result = _coarse_result()
    # Individually inside 4S limits (3.0 / 5.0) but the sum column (5.0)
    # is exceeded: 2.5 + 3.0 = 5.5.
    inputs = CoarseQualityInputs(
        class_designation="4S", clay_lumps_pct=2.5, chert_pct=3.0
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    assert _get(checks, "Table 3 (11.1)", "chert").status == PASS
    assert _get(checks, "Table 3 (11.1)", "sum").status == FAIL
    assert "5.5" in _get(checks, "Table 3 (11.1)", "sum").measured

    # Classes with a dash in the chert column have no requirement.
    inputs = CoarseQualityInputs(class_designation="1S", chert_pct=4.0)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    assert _get(checks, "Table 3 (11.1)", "chert").status == NOT_EVALUATED


def test_coarse_finer_75um_footnote_c_options():
    result = _coarse_result()

    base = CoarseQualityInputs(class_designation="4S", finer_75um_pct=1.2)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), base)
    check = _get(checks, "Table 3 (11.1), Footnote C", "75-µm")
    assert check.status == FAIL

    clay_free = CoarseQualityInputs(
        class_designation="4S", finer_75um_pct=1.2, essentially_clay_free=True
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), clay_free)
    check = _get(checks, "Table 3 (11.1), Footnote C", "75-µm")
    assert check.status == PASS
    assert "1.5 %" in check.requirement

    # Weighted limit: L = 1 + (40/60)·(3.0 − 1.0) = 2.33.
    weighted = CoarseQualityInputs(
        class_designation="4S",
        finer_75um_pct=1.2,
        weighted_limit_enabled=True,
        p_sand_pct=40.0,
        t_fine_limit_pct=3.0,
        a_fine_actual_pct=1.0,
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), weighted)
    check = _get(checks, "Table 3 (11.1), Footnote C", "75-µm")
    assert check.status == PASS
    assert "L = 2.33" in check.requirement

    # A ≥ T invalidates the relaxation.
    invalid = CoarseQualityInputs(
        class_designation="4S",
        finer_75um_pct=1.2,
        weighted_limit_enabled=True,
        p_sand_pct=40.0,
        t_fine_limit_pct=3.0,
        a_fine_actual_pct=3.0,
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), invalid)
    check = _get(checks, "Table 3 (11.1), Footnote C", "75-µm")
    assert check.status == FAIL
    assert "not applicable" in check.requirement


def test_coarse_abrasion_and_slag_footnote_a():
    result = _coarse_result()
    fail = CoarseQualityInputs(class_designation="4S", abrasion_loss_pct=55.0)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), fail)
    check = _get(checks, "Table 3 (11.1), Footnote A", "abrasion")
    assert check.status == FAIL
    assert "55.0 % abrasion" in check.measured

    boundary = CoarseQualityInputs(class_designation="4S", abrasion_loss_pct=50.0)
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), boundary)
    assert _get(checks, "Table 3 (11.1), Footnote A", "abrasion").status == PASS

    # Slag: abrasion exempt, unit weight governs instead.
    slag_fail = CoarseQualityInputs(
        class_designation="4S", is_slag=True, slag_unit_weight_kg_m3=1100.0
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), slag_fail)
    check = _get(checks, "Table 3 (11.1), Footnote A", "slag")
    assert check.status == FAIL
    assert "1100" in check.detail

    slag_ok = CoarseQualityInputs(
        class_designation="4S",
        is_slag=True,
        slag_unit_weight_kg_m3=1120.0,
        abrasion_loss_pct=60.0,  # ignored for slag
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), slag_ok)
    check = _get(checks, "Table 3 (11.1), Footnote A", "slag")
    assert check.status == PASS


def test_coarse_soundness_footnote_b():
    result = _coarse_result()
    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20),
        CoarseQualityInputs(
            class_designation="4S", soundness_loss_pct=18.5,
            soundness_salt="magnesium",
        ),
    )
    assert _get(checks, "Table 3 (11.1), Footnote B", "soundness").status == FAIL

    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20),
        CoarseQualityInputs(
            class_designation="4S", soundness_loss_pct=15.0,
            soundness_salt="sodium",
        ),
    )
    assert _get(checks, "Table 3 (11.1), Footnote B", "soundness").status == FAIL

    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20),
        CoarseQualityInputs(
            class_designation="4S", soundness_loss_pct=12.0,
            soundness_salt="sodium",
        ),
    )
    assert _get(checks, "Table 3 (11.1), Footnote B", "soundness").status == PASS


def test_coarse_reactivity_clause_11_2():
    result = _coarse_result()
    checks = evaluate_astm_c33_coarse(
        result, get_astm_coarse_band(20),
        CoarseQualityInputs(reactivity_status="reactive_unmitigated"),
    )
    assert _get(checks, "11.2", "reactive").status == FAIL


def test_coarse_class_default_resolution_clause_11_1():
    """No class stated → 3S/3M/1N applies by weathering region (11.1)."""
    result = _coarse_result()
    inputs = CoarseQualityInputs(
        class_designation="", weathering_region="N", coal_lignite_pct=0.8
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    # Class 1N limits coal & lignite to 0.5 % — fails.
    assert _get(checks, "Table 3 (11.1)", "coal").status == FAIL

    inputs = CoarseQualityInputs(
        class_designation="2N", coal_lignite_pct=0.8
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    # Explicit 2N allows 1.0 % — passes.
    assert _get(checks, "Table 3 (11.1)", "coal").status == PASS


def test_weighted_limit_helper_math():
    # L = 1 + [40/(100−40)]·(3.0 − 1.0) = 1 + 1.3333 = 2.3333
    assert q.weighted_finer_75um_limit(40.0, 3.0, 1.0) == pytest.approx(2.3333, abs=1e-3)
    # A ≥ T → relaxation not applicable.
    assert q.weighted_finer_75um_limit(40.0, 3.0, 3.0) is None
    assert q.weighted_finer_75um_limit(40.0, 3.0, 3.5) is None


def test_table_3_data_matches_standard():
    """Spot-check every Table 3 row against the extracted standard."""
    expected = {
        "1S": (10.0, None, None, 1.0, 1.0, 50.0, None),
        "2S": (5.0, None, None, 1.0, 0.5, 50.0, None),
        "3S": (5.0, 5.0, 7.0, 1.0, 0.5, 50.0, 18.0),
        "4S": (3.0, 5.0, 5.0, 1.0, 0.5, 50.0, 18.0),
        "5S": (2.0, 3.0, 3.0, 1.0, 0.5, 50.0, 18.0),
        "1M": (10.0, None, None, 1.0, 1.0, 50.0, None),
        "2M": (5.0, None, None, 1.0, 0.5, 50.0, None),
        "3M": (5.0, 8.0, 10.0, 1.0, 0.5, 50.0, 18.0),
        "4M": (5.0, 5.0, 7.0, 1.0, 0.5, 50.0, 18.0),
        "5M": (3.0, 3.0, 5.0, 1.0, 0.5, 50.0, 18.0),
        "1N": (5.0, None, None, 1.0, 0.5, 50.0, None),
        "2N": (10.0, None, None, 1.0, 1.0, 50.0, None),
    }
    keys = (
        "clay_lumps", "chert", "sum_deleterious", "finer_75um",
        "coal_lignite", "abrasion", "soundness",
    )
    for designation, values in expected.items():
        row = q.COARSE_CLASSES[designation]
        for key, value in zip(keys, values):
            assert row.limit(key) == value, (designation, key)
    assert q.REGION_DEFAULT_CLASS == {"S": "3S", "M": "3M", "N": "1N"}
    assert set(ASTM_COARSE_BANDS) == {10, 20, 40}
