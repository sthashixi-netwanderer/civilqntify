"""IS 383:2016 quality-table constants vs the extracted standard.

Every value here is spot-checked against
docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md (IS 383:2016
Third Revision + Amendment No. 1) so the compliance checks can never drift
from the standard.
"""

from __future__ import annotations

from concrete_mix.codes.tables import is383_quality as q


class TestTable2Deleterious:
    def test_coal_and_clay_are_1pct_everywhere(self):
        assert q.TABLE2_COAL_LIGNITE_MAX == 1.00
        assert q.TABLE2_CLAY_LUMPS_MAX == 1.00

    def test_finer_75um_by_source(self):
        assert q.TABLE2_FINER_75UM_MAX["fine_uncrushed"] == 3.00
        assert q.TABLE2_FINER_75UM_MAX["fine_crushed_stone_sand"] == 15.00
        assert q.TABLE2_FINER_75UM_MAX["fine_mixed_sand"] == 12.00
        assert q.TABLE2_FINER_75UM_MAX["fine_manufactured"] == 10.00
        assert q.TABLE2_FINER_75UM_MAX["coarse_uncrushed"] == 1.00
        assert q.TABLE2_FINER_75UM_MAX["coarse_crushed"] == 1.00
        assert q.TABLE2_FINER_75UM_MAX["coarse_manufactured"] == 1.00

    def test_soft_fragments_coarse_only(self):
        assert q.TABLE2_SOFT_FRAGMENTS_MAX["coarse_uncrushed"] == 3.00
        assert q.TABLE2_SOFT_FRAGMENTS_MAX["coarse_manufactured"] == 3.00
        # Crushed coarse aggregate: dash in Table 2 — no requirement.
        assert q.TABLE2_SOFT_FRAGMENTS_MAX["coarse_crushed"] is None

    def test_shale_fine_only(self):
        assert q.TABLE2_SHALE_MAX["fine_uncrushed"] == 1.00
        assert q.TABLE2_SHALE_MAX["fine_manufactured"] == 1.00
        # Crushed / mixed sand: dash — no requirement.
        assert q.TABLE2_SHALE_MAX["fine_crushed_stone_sand"] is None
        assert q.TABLE2_SHALE_MAX["fine_mixed_sand"] is None

    def test_total_deleterious_columns(self):
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["fine_uncrushed"] == 5.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["fine_crushed_stone_sand"] == 2.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["fine_mixed_sand"] == 2.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["fine_manufactured"] == 2.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["coarse_uncrushed"] == 5.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["coarse_crushed"] == 5.00
        assert q.TABLE2_TOTAL_DELETERIOUS_MAX["coarse_manufactured"] == 2.00

    def test_mica_tiers_note3(self):
        assert q.MICA_DEFAULT_MAX == 1.00
        assert q.MICA_MUSCOVITE_WITH_TESTS_MAX == 3.00
        assert q.MICA_MUSCOVITE_BIOTITE_WITH_TESTS_MAX == 5.00
        assert q.MICA_TOTAL_INCL_DELETERIOUS_MAX["fine_uncrushed"] == 8.00
        assert q.MICA_TOTAL_INCL_DELETERIOUS_MAX["fine_mixed_sand"] == 5.00

    def test_organic_relative_strength_note4(self):
        assert q.ORGANIC_RELATIVE_STRENGTH_MIN_PCT == 95.0


class TestPhysicalAndMechanical:
    def test_flakiness_elongation_combined(self):
        assert q.FLAKINESS_ELONGATION_COMBINED_MAX == 40.0

    def test_crushing_value_and_ten_percent_fines(self):
        assert q.ACV_WEARING_MAX == 30.0
        assert q.ACV_THRESHOLD_FOR_TEN_PCT_FINES == 30.0
        assert q.TEN_PCT_FINES_LOAD_MIN_KN == 50.0

    def test_impact_and_abrasion(self):
        assert q.AIV_WEARING_MAX == 30.0
        assert q.AIV_OTHER_MAX == 45.0
        assert q.ABRASION_WEARING_MAX == 30.0
        assert q.ABRASION_OTHER_MAX == 50.0

    def test_high_grade_limits_note(self):
        # Clause 5.4 Note: M65 and above — 22 % for crushing and impact.
        assert q.ACV_HIGH_GRADE_MAX == 22.0
        assert q.AIV_HIGH_GRADE_MAX == 22.0

    def test_soundness_551_note_guide_limits(self):
        assert q.SOUNDNESS_MAX_BY_SALT["fine"] == {"sodium": 10.0, "magnesium": 15.0}
        assert q.SOUNDNESS_MAX_BY_SALT["coarse"] == {"sodium": 12.0, "magnesium": 18.0}


class TestAAR:
    def test_mortar_bar_38c(self):
        assert q.AAR_MORTAR_BAR_38C == {90: 0.05, 180: 0.10}

    def test_mortar_bar_60c_slowly_reactive(self):
        assert q.AAR_MORTAR_BAR_60C == {90: 0.05, 180: 0.06}

    def test_accelerated_mortar_bar_80c(self):
        assert q.AAR_AMBT_INNOCUOUS_MAX == 0.10
        assert q.AAR_AMBT_DELETERIOUS_MIN == 0.20


class TestManufacturedAndUtilization:
    def test_table3_all_manufactured(self):
        assert q.MANUFACTURED_ALKALI_NA2O_EQ_MAX == 0.3
        assert q.MANUFACTURED_SULPHATE_SO3_MAX == 0.5
        assert q.MANUFACTURED_CHLORIDE_MAX == 0.04
        assert q.MANUFACTURED_WATER_ABSORPTION_MAX == 5.0
        assert q.MANUFACTURED_RCA_ABSORPTION_MAX == 10.0
        assert (q.MANUFACTURED_SG_MIN, q.MANUFACTURED_SG_MAX) == (2.1, 3.2)

    def test_table1_utilization_caps(self):
        caps = q.TABLE1_UTILIZATION_MAX_PCT
        assert caps["iron_slag"]["reinforced"] == "25 %"
        assert caps["steel_slag"]["reinforced"] == "Nil"
        assert caps["rca"]["reinforced"] == "20 % (only up to M25 grade)"
        assert caps["ra"]["plain"] == "Nil"
        assert caps["bottom_ash"]["lean"] == "25 %"
        assert caps["copper_slag"]["plain"] == "40 %"


class TestZoneToleranceConstants:
    def test_clause_63_tolerance(self):
        assert q.ZONE_TOLERANCE_SINGLE_SIEVE_PCT == 5.0
        assert q.ZONE_TOLERANCE_CUMULATIVE_PCT == 10.0
        assert q.ZONE_TOLERANCE_EXEMPT_SIEVE_MM == 0.600

    def test_table9_note1_crushed_stone_sand_150um(self):
        assert q.ZONE_150UM_CRUSHED_STONE_SAND_MAX == 20.0

    def test_table9_notes_advisories_exist(self):
        assert "Zone IV" in q.ZONE_IV_RC_CAUTION
        assert "Note 4" in q.ZONE_IV_RC_CAUTION
        assert "Note 3" in q.ZONE_FINER_RATIO_NOTE
