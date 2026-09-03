"""IS 383:2016 compliance evaluator — pass / fail / not-evaluated per clause.

Uses a fully conforming Zone II fine grading and a conforming 20 mm graded
coarse grading as baselines, then flips one input at a time.
"""

from __future__ import annotations

import pytest

from concrete_mix.codes.tables.grading_bands import get_fine_band, get_is_coarse_band
from concrete_mix.engine.psd import IS_FINE_SIEVES, IS_COARSE_SIEVES, compute_psd
from concrete_mix.validation.base import FAIL, NOT_EVALUATED, PASS
from concrete_mix.validation.is383 import (
    IS383CoarseQualityInputs,
    IS383FineQualityInputs,
    evaluate_is383_coarse,
    evaluate_is383_fine,
)


def _fine_result():
    """Zone II sand: 100 / 98 / 90 / 70 / 45 / 20 / 5 % passing."""
    masses = [0, 20, 80, 200, 250, 250, 150]  # pan 50 g, total 1000 g
    return compute_psd(masses, IS_FINE_SIEVES, pan_mass=50.0)


def _coarse_result():
    """20 mm graded coarse aggregate within the Table 7 band."""
    # IS coarse sieves: 80, 63, 40, 20, 16, 12.5, 10, 4.75, 2.36
    # Band (graded 20): 40:(100,100), 20:(90,100), 10:(25,55), 4.75:(0,10)
    # Passing: 100, 100, 100, 95, 75, 55, 40, 8, 0
    masses = [0, 0, 0, 50, 200, 200, 150, 320, 80]
    return compute_psd(masses, IS_COARSE_SIEVES, pan_mass=0.0)


def _by_title(checks, fragment):
    for c in checks:
        if fragment.lower() in c.title.lower():
            return c
    raise AssertionError(f"no check titled '{fragment}' in {[c.title for c in checks]}")


# ---------------------------------------------------------------------------
# Fine aggregate
# ---------------------------------------------------------------------------


class TestFineGrading:
    def test_conforming_zone_ii_passes(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), IS383FineQualityInputs(),
            zone="II",
        )
        grading = _by_title(checks, "grading")
        assert grading.status == PASS
        assert "Zone II" in grading.measured

    def test_out_of_zone_beyond_tolerance_fails(self):
        # 2.36 at 69 (6 points below the Zone II limit of 75) — beyond the
        # Clause 6.3 tolerance.
        masses = [0, 20, 290, 40, 200, 250, 150]  # total 1000, pan 50
        result = compute_psd(masses, IS_FINE_SIEVES, pan_mass=50.0)
        checks = evaluate_is383_fine(
            result, get_fine_band("II"), IS383FineQualityInputs(), zone="II"
        )
        grading = _by_title(checks, "grading")
        assert grading.status == FAIL

    def test_tolerated_deviation_passes_with_detail(self):
        # 2.36 at 72 — 3 points below the Zone II lower limit, within the
        # Clause 6.3 tolerance.
        masses = [0, 20, 260, 20, 250, 250, 150]  # total 950 → pan 50 = 1000
        result = compute_psd(masses, IS_FINE_SIEVES, pan_mass=50.0)
        checks = evaluate_is383_fine(
            result, get_fine_band("II"), IS383FineQualityInputs(), zone="II"
        )
        grading = _by_title(checks, "grading")
        assert grading.status == PASS
        assert "tolerance" in grading.detail

    def test_crushed_stone_sand_150um_relief(self):
        # 150 µm at 16 % — 6 points over the 10 % limit, beyond the
        # Clause 6.3 allowance → fails for natural sand. At 14 % crushed
        # stone sand passes through the raised 20 % limit (Table 9 Note 1);
        # (natural sand at 14 % would still pass via the 6.3 allowance —
        # covered in the zone-tolerance tests).
        masses16 = [0, 20, 80, 200, 250, 250, 40]  # pan 160 → total 1000 g
        result16 = compute_psd(masses16, IS_FINE_SIEVES, pan_mass=160.0)
        natural = evaluate_is383_fine(
            result16, get_fine_band("II"),
            IS383FineQualityInputs(source_type="uncrushed"), zone="II",
        )
        assert _by_title(natural, "grading").status == FAIL

        masses14 = [0, 20, 80, 200, 250, 250, 60]  # pan 140 → total 1000 g
        result14 = compute_psd(masses14, IS_FINE_SIEVES, pan_mass=140.0)
        crushed = evaluate_is383_fine(
            result14, get_fine_band("II"),
            IS383FineQualityInputs(source_type="crushed_stone_sand"),
            zone="II",
        )
        crushed_grading = _by_title(crushed, "grading")
        assert crushed_grading.status == PASS
        assert "20 %" in crushed_grading.detail


class TestFineTable2:
    def test_untested_substances_are_not_evaluated(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), IS383FineQualityInputs(),
            zone="II",
        )
        for fragment in ("Coal and lignite", "Clay lumps", "finer than 75",
                         "Shale", "Mica", "Total deleterious"):
            assert _by_title(checks, fragment).status == NOT_EVALUATED

    def test_coal_over_1pct_fails(self):
        inputs = IS383FineQualityInputs(coal_lignite_pct=1.4)
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), inputs, zone="II"
        )
        assert _by_title(checks, "Coal and lignite").status == FAIL

    def test_75um_limit_follows_source_column(self):
        # 11 % finer than 75 µm: within the mixed-sand limit (12 %) but
        # far over the uncrushed limit (3 %).
        checks_mixed = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(source_type="mixed_sand", finer_75um_pct=11.0),
            zone="II",
        )
        assert _by_title(checks_mixed, "finer than 75").status == PASS
        checks_uncrushed = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(source_type="uncrushed", finer_75um_pct=11.0),
            zone="II",
        )
        assert _by_title(checks_uncrushed, "finer than 75").status == FAIL
        # Crushed stone sand carries the highest column limit (15 %).
        checks_crushed = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                source_type="crushed_stone_sand", finer_75um_pct=14.0
            ),
            zone="II",
        )
        assert _by_title(checks_crushed, "finer than 75").status == PASS

    def test_shale_dash_for_crushed_sand(self):
        # Crushed / mixed sand: shale has no requirement (Table 2 dash).
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                source_type="crushed_stone_sand", shale_pct=5.0
            ),
            zone="II",
        )
        shale = _by_title(checks, "Shale")
        assert shale.status == NOT_EVALUATED
        assert "no requirement" in shale.requirement.lower()

    def test_total_deleterious_sums_components(self):
        inputs = IS383FineQualityInputs(
            source_type="uncrushed",
            coal_lignite_pct=2.0, clay_lumps_pct=1.5,
            finer_75um_pct=1.0, shale_pct=1.0,
        )
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), inputs, zone="II"
        )
        total = _by_title(checks, "Total deleterious")
        assert total.status == FAIL  # 5.5 > 5.00 for uncrushed sand
        assert "5.50" in total.measured

    def test_total_deleterious_partial_sum_is_flagged(self):
        inputs = IS383FineQualityInputs(
            source_type="uncrushed", coal_lignite_pct=4.9
        )
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), inputs, zone="II"
        )
        total = _by_title(checks, "Total deleterious")
        assert total.status == PASS
        assert "partial" in total.measured

    def test_mica_tiers(self):
        base = IS383FineQualityInputs(mica_pct=2.0)
        no_tests = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), base, zone="II"
        )
        assert _by_title(no_tests, "Mica content").status == FAIL  # 2.0 > 1.0

        with_tests = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                mica_pct=2.0, mica_tests_conducted=True,
                mica_type="muscovite",
            ),
            zone="II",
        )
        assert _by_title(with_tests, "Mica content").status == PASS  # ≤ 3.0

        biotite = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                mica_pct=4.5, mica_tests_conducted=True,
                mica_type="muscovite_biotite",
            ),
            zone="II",
        )
        assert _by_title(biotite, "Mica content").status == PASS  # ≤ 5.0

    def test_mica_total_including_mica(self):
        # Uncrushed sand: deleterious 4.0 + mica 4.5 = 8.5 > 8.00 → fail
        # even though 4.5 ≤ 5.0 (muscovite + biotite with tests).
        inputs = IS383FineQualityInputs(
            source_type="uncrushed",
            coal_lignite_pct=2.0, clay_lumps_pct=1.0, finer_75um_pct=1.0,
            mica_pct=4.5, mica_tests_conducted=True,
            mica_type="muscovite_biotite",
        )
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"), inputs, zone="II"
        )
        mica = _by_title(checks, "Mica content")
        assert mica.status == FAIL
        assert "including mica" in mica.requirement


class TestFineOrganic:
    def test_pass_colour(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(organic_status="pass"), zone="II",
        )
        assert _by_title(checks, "Organic").status == PASS

    def test_fail_without_part6_strength(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(organic_status="fail_color"), zone="II",
        )
        assert _by_title(checks, "Organic").status == FAIL

    def test_relieved_by_95pct_relative_strength(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                organic_status="fail_color_relieved",
                organic_relative_strength_pct=96.0,
            ),
            zone="II",
        )
        assert _by_title(checks, "Organic").status == PASS

        low = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                organic_status="fail_color_relieved",
                organic_relative_strength_pct=94.0,
            ),
            zone="II",
        )
        assert _by_title(low, "Organic").status == FAIL


class TestFineShapeSoundnessAAR:
    def test_combined_flakiness_elongation(self):
        ok = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(flakiness_index_pct=22, elongation_index_pct=17),
            zone="II",
        )
        assert _by_title(ok, "flakiness").status == PASS

        bad = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(flakiness_index_pct=25, elongation_index_pct=18),
            zone="II",
        )
        assert _by_title(bad, "flakiness").status == FAIL

    def test_one_index_only_is_not_evaluated(self):
        checks = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(flakiness_index_pct=20), zone="II",
        )
        assert _by_title(checks, "flakiness").status == NOT_EVALUATED

    def test_soundness_by_salt(self):
        ok = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(soundness_loss_pct=9.0, soundness_salt="sodium"),
            zone="II",
        )
        assert _by_title(ok, "Soundness").status == PASS

        mg = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                soundness_loss_pct=14.0, soundness_salt="magnesium"
            ),
            zone="II",
        )
        assert _by_title(mg, "Soundness").status == PASS

        over = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(soundness_loss_pct=11.0, soundness_salt="sodium"),
            zone="II",
        )
        assert _by_title(over, "Soundness").status == FAIL

    def test_aar_mortar_bar_limits(self):
        ok = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="mortar_bar_38c", aar_expansion_pct=0.04,
                aar_age_days=90,
            ),
            zone="II",
        )
        assert _by_title(ok, "reactivity").status == PASS

        over = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="mortar_bar_38c", aar_expansion_pct=0.11,
                aar_age_days=180,
            ),
            zone="II",
        )
        assert _by_title(over, "reactivity").status == FAIL

    def test_aar_60c_and_unknown_age(self):
        # 60 °C regime: 0.055 % at 180 days ≤ 0.06 % → passes.
        slowly = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="mortar_bar_60c", aar_expansion_pct=0.055,
                aar_age_days=180,
            ),
            zone="II",
        )
        assert _by_title(slowly, "reactivity").status == PASS
        # Limits exist only at 90 and 180 days — other ages are not
        # evaluated rather than guessed.
        unknown = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="mortar_bar_60c", aar_expansion_pct=0.05,
                aar_age_days=30,
            ),
            zone="II",
        )
        assert _by_title(unknown, "reactivity").status == NOT_EVALUATED

    def test_aar_accelerated_mortar_bar(self):
        innocuous = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="ambt_80c", aar_expansion_pct=0.08, aar_age_days=16
            ),
            zone="II",
        )
        assert _by_title(innocuous, "accelerated").status == PASS

        bad = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="ambt_80c", aar_expansion_pct=0.25, aar_age_days=16
            ),
            zone="II",
        )
        assert _by_title(bad, "accelerated").status == FAIL

        inconclusive = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                aar_method="ambt_80c", aar_expansion_pct=0.15, aar_age_days=16
            ),
            zone="II",
        )
        check = _by_title(inconclusive, "accelerated")
        assert check.status == PASS
        assert "inconclusive" in check.measured.lower()

    def test_aar_status_outcomes(self):
        mitigated = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(aar_method="mitigated_low_alkali"), zone="II",
        )
        assert _by_title(mitigated, "reactivity").status == PASS

        unmitigated = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(aar_method="reactive_unmitigated"), zone="II",
        )
        assert _by_title(unmitigated, "reactivity").status == FAIL


class TestFineManufactured:
    def test_manufactured_checks_added_only_for_manufactured_source(self):
        natural = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(source_type="uncrushed"), zone="II",
        )
        with pytest.raises(AssertionError):
            _by_title(natural, "alkali content")

        mfd = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                source_type="manufactured",
                manufactured_type="rca",
                manufactured_alkali_pct=0.4,      # > 0.3 → fail
                manufactured_sulphate_pct=0.3,    # ok
                manufactured_chloride_pct=0.02,   # ok
                manufactured_absorption_pct=6.0,  # > 5, no pre-wetting → fail
                manufactured_specific_gravity=2.4,
            ),
            zone="II",
        )
        assert _by_title(mfd, "alkali content").status == FAIL
        assert _by_title(mfd, "sulphate").status == PASS
        assert _by_title(mfd, "chloride").status == PASS
        assert _by_title(mfd, "absorption").status == FAIL
        assert _by_title(mfd, "Specific gravity").status == PASS

    def test_rca_absorption_relief_with_prewetting(self):
        mfd = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                source_type="manufactured",
                manufactured_type="rca",
                manufactured_absorption_pct=8.0,
                rca_prewetted=True,
            ),
            zone="II",
        )
        absorption = _by_title(mfd, "absorption")
        assert absorption.status == PASS
        assert "pre-wetting" in absorption.requirement

    def test_utilization_advisory_lists_table1_caps(self):
        mfd = evaluate_is383_fine(
            _fine_result(), get_fine_band("II"),
            IS383FineQualityInputs(
                source_type="manufactured", manufactured_type="rca"
            ),
            zone="II",
        )
        advisory = _by_title(mfd, "extent of utilization")
        assert advisory.status == PASS
        assert "20 %" in advisory.requirement
        assert "prestressed" in advisory.detail


# ---------------------------------------------------------------------------
# Coarse aggregate
# ---------------------------------------------------------------------------


class TestCoarseGradingAndTable2:
    def test_conforming_graded_20mm_passes(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(),
        )
        assert _by_title(checks, "grading").status == PASS

    def test_out_of_band_fails(self):
        masses = [0, 0, 0, 150, 200, 200, 100, 280, 70]  # 20 mm: 85 (< 90)
        result = compute_psd(masses, IS_COARSE_SIEVES, pan_mass=0.0)
        checks = evaluate_is383_coarse(
            result, get_is_coarse_band("graded", 20), IS383CoarseQualityInputs()
        )
        assert _by_title(checks, "grading").status == FAIL

    def test_soft_fragments_dash_for_crushed(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(source_type="crushed", soft_fragments_pct=9.0),
        )
        soft = _by_title(checks, "Soft fragments")
        assert soft.status == NOT_EVALUATED
        assert "no requirement" in soft.requirement.lower()

    def test_soft_fragments_3pct_for_uncrushed(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(
                source_type="uncrushed", soft_fragments_pct=3.5
            ),
        )
        assert _by_title(checks, "Soft fragments").status == FAIL

    def test_total_deleterious_5pct_crushed(self):
        inputs = IS383CoarseQualityInputs(
            source_type="crushed",
            coal_lignite_pct=2.5, clay_lumps_pct=1.5,
            finer_75um_pct=0.5, soft_fragments_pct=0.5,
        )
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20), inputs
        )
        total = _by_title(checks, "Total deleterious")
        assert total.status == PASS  # 5.0 ≤ 5.00 for crushed coarse
        manufactured = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(
                source_type="manufactured",
                coal_lignite_pct=2.5, clay_lumps_pct=1.5,
            ),
        )
        assert _by_title(manufactured, "Total deleterious").status == FAIL  # > 2.00


class TestCoarseMechanical:
    def _run(self, **kw):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(**kw),
        )
        return checks

    def test_untested_mechanical_not_evaluated(self):
        checks = self._run()
        for fragment in ("crushing value", "impact value", "abrasion"):
            assert _by_title(checks, fragment).status == NOT_EVALUATED

    def test_acv_wearing_30(self):
        assert _by_title(
            self._run(crushing_value_pct=28.0, wearing_surfaces=True), "crushing"
        ).status == PASS
        assert _by_title(
            self._run(crushing_value_pct=32.0, wearing_surfaces=True), "crushing"
        ).status == FAIL

    def test_acv_over_30_needs_ten_percent_fines(self):
        # Non-wearing, ACV 33 (> 30): without the fines load the check is
        # not evaluated (test outstanding); ≥ 50 kN passes; < 50 kN fails.
        pending = self._run(crushing_value_pct=33.0)
        check = _by_title(pending, "crushing")
        assert check.status == NOT_EVALUATED
        assert "ten percent fines" in check.measured.lower()

        ok = self._run(crushing_value_pct=33.0, ten_pct_fines_load_kn=55.0)
        assert _by_title(ok, "crushing").status == PASS

        bad = self._run(crushing_value_pct=33.0, ten_pct_fines_load_kn=45.0)
        assert _by_title(bad, "crushing").status == FAIL

    def test_high_grade_22pct(self):
        assert _by_title(
            self._run(crushing_value_pct=23.0, high_grade=True), "crushing"
        ).status == FAIL
        assert _by_title(
            self._run(impact_value_pct=23.0, high_grade=True), "impact"
        ).status == FAIL

    def test_impact_45_other(self):
        assert _by_title(
            self._run(impact_value_pct=44.0), "impact"
        ).status == PASS
        assert _by_title(
            self._run(impact_value_pct=46.0), "impact"
        ).status == FAIL

    def test_abrasion_limits(self):
        # Other-than-wearing concrete: ≤ 50 %.
        assert _by_title(
            self._run(abrasion_loss_pct=31.0), "abrasion"
        ).status == PASS
        assert _by_title(
            self._run(abrasion_loss_pct=51.0), "abrasion"
        ).status == FAIL
        # Wearing surfaces: ≤ 30 %.
        assert _by_title(
            self._run(abrasion_loss_pct=31.0, wearing_surfaces=True), "abrasion"
        ).status == FAIL
        assert _by_title(
            self._run(abrasion_loss_pct=29.0, wearing_surfaces=True), "abrasion"
        ).status == PASS


class TestCoarseSoundnessAARManufactured:
    def test_soundness_12_18_by_salt(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(
                soundness_loss_pct=13.0, soundness_salt="sodium"
            ),
        )
        assert _by_title(checks, "Soundness").status == FAIL

        mg = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(
                soundness_loss_pct=17.0, soundness_salt="magnesium"
            ),
        )
        assert _by_title(mg, "Soundness").status == PASS

    def test_aar_applies_to_coarse(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(aar_method="reactive_unmitigated"),
        )
        assert _by_title(checks, "reactivity").status == FAIL

    def test_manufactured_extra_checks(self):
        checks = evaluate_is383_coarse(
            _coarse_result(), get_is_coarse_band("graded", 20),
            IS383CoarseQualityInputs(
                source_type="manufactured",
                manufactured_type="steel_slag",
                manufactured_specific_gravity=2.0,  # below 2.1 → fail
            ),
        )
        assert _by_title(checks, "Specific gravity").status == FAIL
        assert _by_title(checks, "extent of utilization").status == PASS
