"""Tests for IS 10262:2019 and IS 456:2000 compliance.

Verifies that all table values and calculations match the published standards.
"""

import pytest

from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.codes.tables.is_tables import (
    CURVE_RESTRAINTS,
    IS456_EXPOSURE_LIMITS,
    STANDARD_DEVIATION,
    WATER_CONTENT,
    get_ca_volume_fraction,
    get_exposure_limits,
    get_std_dev,
    interpolate_w_c_ratio,
    interpolate_water_content,
    strength_from_wc_ratio,
    wc_ratio_from_strength,
)
from concrete_mix.models.mix_input import MixDesignInput


# ---------------------------------------------------------------------------
# Phase 1: IS 456:2000 Table 3 — Exposure Limits
# ---------------------------------------------------------------------------
class TestIS456ExposureLimits:
    """Verify IS 456:2000 Table 5 values via get_exposure_limits() (backward-compat wrapper)."""

    def test_mild_exposure(self):
        limits = get_exposure_limits("mild")
        assert limits["min_cement_kg_m3"] == 300
        assert limits["max_wc"] == 0.55

    def test_moderate_exposure(self):
        limits = get_exposure_limits("moderate")
        assert limits["min_cement_kg_m3"] == 300
        assert limits["max_wc"] == 0.50
        assert limits["min_grade"] == "M25"

    def test_severe_exposure(self):
        limits = get_exposure_limits("severe")
        assert limits["min_cement_kg_m3"] == 320
        assert limits["max_wc"] == 0.45
        assert limits["min_grade"] == "M30"

    def test_very_severe_exposure(self):
        limits = get_exposure_limits("very_severe")
        assert limits["min_cement_kg_m3"] == 340
        assert limits["max_wc"] == 0.45
        assert limits["min_grade"] == "M35"

    def test_extreme_exposure(self):
        limits = get_exposure_limits("extreme")
        assert limits["min_cement_kg_m3"] == 360
        assert limits["max_wc"] == 0.40
        assert limits["min_grade"] == "M40"

    def test_mild_cement_is_300(self):
        """Verify reinforced mild exposure minimum cement is 300 kg/m³ per IS 456 Table 5."""
        assert get_exposure_limits("mild")["min_cement_kg_m3"] == 300

    def test_moderate_wc_is_050(self):
        """Verify reinforced moderate exposure max W/C is 0.50 per IS 456 Table 5."""
        assert get_exposure_limits("moderate")["max_wc"] == 0.50


# ---------------------------------------------------------------------------
# IS 456:2000 Table 5 — Plain vs Reinforced Concrete Exposure Limits
# ---------------------------------------------------------------------------
class TestIS456PlainVsReinforced:
    """Verify IS 456:2000 Table 5 distinguishes plain and reinforced concrete."""

    def test_reinforced_mild(self):
        limits = get_exposure_limits("mild", "reinforced")
        assert limits["min_cement_kg_m3"] == 300
        assert limits["max_wc"] == 0.55
        assert limits["min_grade"] == "M20"

    def test_reinforced_moderate(self):
        limits = get_exposure_limits("moderate", "reinforced")
        assert limits["min_cement_kg_m3"] == 300
        assert limits["max_wc"] == 0.50
        assert limits["min_grade"] == "M25"

    def test_reinforced_severe(self):
        limits = get_exposure_limits("severe", "reinforced")
        assert limits["min_cement_kg_m3"] == 320
        assert limits["max_wc"] == 0.45
        assert limits["min_grade"] == "M30"

    def test_reinforced_very_severe(self):
        limits = get_exposure_limits("very_severe", "reinforced")
        assert limits["min_cement_kg_m3"] == 340
        assert limits["max_wc"] == 0.45
        assert limits["min_grade"] == "M35"

    def test_reinforced_extreme(self):
        limits = get_exposure_limits("extreme", "reinforced")
        assert limits["min_cement_kg_m3"] == 360
        assert limits["max_wc"] == 0.40
        assert limits["min_grade"] == "M40"

    def test_plain_mild(self):
        limits = get_exposure_limits("mild", "plain")
        assert limits["min_cement_kg_m3"] == 220
        assert limits["max_wc"] == 0.60
        assert limits["min_grade"] == ""  # IS 456: not specified

    def test_plain_moderate(self):
        limits = get_exposure_limits("moderate", "plain")
        assert limits["min_cement_kg_m3"] == 240
        assert limits["max_wc"] == 0.60
        assert limits["min_grade"] == "M15"

    def test_plain_severe(self):
        limits = get_exposure_limits("severe", "plain")
        assert limits["min_cement_kg_m3"] == 250
        assert limits["max_wc"] == 0.50
        assert limits["min_grade"] == "M20"

    def test_plain_very_severe(self):
        limits = get_exposure_limits("very_severe", "plain")
        assert limits["min_cement_kg_m3"] == 260
        assert limits["max_wc"] == 0.45
        assert limits["min_grade"] == "M20"

    def test_plain_extreme(self):
        limits = get_exposure_limits("extreme", "plain")
        assert limits["min_cement_kg_m3"] == 280
        assert limits["max_wc"] == 0.40
        assert limits["min_grade"] == "M25"

    def test_default_is_reinforced(self):
        """Default concrete_type should be 'reinforced' for backwards compatibility."""
        limits = get_exposure_limits("mild")
        assert limits["min_cement_kg_m3"] == 300

    def test_reinforced_mild_higher_cement_than_plain(self):
        """Reinforced requires more cement than plain for same exposure."""
        plain = get_exposure_limits("mild", "plain")
        reinforced = get_exposure_limits("mild", "reinforced")
        assert reinforced["min_cement_kg_m3"] > plain["min_cement_kg_m3"]

    def test_reinforced_mild_lower_wc_than_plain(self):
        """Reinforced allows lower W/C than plain for same exposure."""
        plain = get_exposure_limits("mild", "plain")
        reinforced = get_exposure_limits("mild", "reinforced")
        assert reinforced["max_wc"] < plain["max_wc"]


# ---------------------------------------------------------------------------
# Phase 3: IS 10262:2019 Table 1 — Standard Deviation
# ---------------------------------------------------------------------------
class TestStandardDeviation:
    """Verify standard deviation table per IS 10262:2019 Table 1."""

    @pytest.mark.parametrize("grade", ["M10", "M15"])
    def test_low_grades_are_3_5(self, grade):
        assert STANDARD_DEVIATION[grade] == 3.5

    @pytest.mark.parametrize("grade", ["M20", "M25"])
    def test_mid_grades_are_4_0(self, grade):
        assert STANDARD_DEVIATION[grade] == 4.0

    @pytest.mark.parametrize("grade", ["M30", "M35", "M40", "M45", "M50", "M55", "M60"])
    def test_high_grades_are_5_0(self, grade):
        assert STANDARD_DEVIATION[grade] == 5.0

    @pytest.mark.parametrize("grade", ["M65", "M70", "M75", "M80"])
    def test_very_high_grades_are_6_0(self, grade):
        assert STANDARD_DEVIATION[grade] == 6.0

    def test_m10_not_3_0(self):
        """Regression: old value was 3.0."""
        assert STANDARD_DEVIATION["M10"] == 3.5

    def test_m20_not_3_5(self):
        """Regression: old value was 3.5."""
        assert STANDARD_DEVIATION["M20"] == 4.0

    def test_get_std_dev_m25(self):
        assert get_std_dev("M25") == 4.0

    def test_get_std_dev_unknown_defaults_5(self):
        assert get_std_dev("M99") == 5.0


# ---------------------------------------------------------------------------
# Phase 5: IS 10262 Table 5 — Water Content
# ---------------------------------------------------------------------------
class TestWaterContent:
    """Verify water content table values per IS 10262:2019 Table 4."""

    def test_10mm_50mm_slump(self):
        """Table 4: NMSA 10mm → 208 kg/m³ (50mm slump reference)."""
        assert WATER_CONTENT[10] == 208

    def test_10mm_base_value(self):
        """Table 4: NMSA 10mm base water content."""
        assert WATER_CONTENT[10] == 208

    def test_20mm_50mm_slump(self):
        """Table 4: NMSA 20mm → 186 kg/m³."""
        assert WATER_CONTENT[20] == 186

    def test_40mm_50mm_slump(self):
        """Table 4: NMSA 40mm → 165 kg/m³."""
        assert WATER_CONTENT[40] == 165

    def test_interpolate_20mm_75mm_slump(self):
        """Clause 5.3: 75mm = +3% for 25mm above 50mm → 186 × 1.03 = 191.58."""
        result = interpolate_water_content(20, 75, "II")
        assert abs(result - 191.58) < 0.1

    def test_interpolate_20mm_62mm_slump(self):
        """Clause 5.3: 62mm = +3% × (12/25) above 50mm → 186 × 1.0144 ≈ 188.68."""
        result = interpolate_water_content(20, 62, "II")
        expected = 186 * (1.0 + 3.0 * 12.0 / 25.0 / 100.0)
        assert abs(result - expected) < 0.1


# ---------------------------------------------------------------------------
# Grading zone — water content is NOT adjusted by zone in IS 10262:2019
# ---------------------------------------------------------------------------
class TestGradingZoneNoWaterAdjustment:
    """The grading zone affects only the CA fraction (Table 5), not water."""

    @pytest.mark.parametrize("zone", ["I", "II", "III", "IV"])
    def test_water_same_for_all_zones(self, zone):
        """IS 10262:2019 has no grading-zone water adjustment."""
        result = interpolate_water_content(20, 50, zone)
        assert abs(result - 186.0) < 0.1


# ---------------------------------------------------------------------------
# IS 10262 — W/C Ratio Curves
# ---------------------------------------------------------------------------
class TestWCRatio:
    """Verify W/C ratio polynomial curve from IS 10262:2019 Figure 1."""

    def test_strength_from_wc_ratio_045(self):
        """Test f(x) = 183x² - 287.4x + 128 at x = 0.45."""
        result = strength_from_wc_ratio(0.45)
        assert abs(result - 35.73) < 0.1

    def test_strength_from_wc_ratio_035(self):
        """Test f(x) at x = 0.35 should be ~49.8 MPa."""
        result = strength_from_wc_ratio(0.35)
        assert abs(result - 49.83) < 0.1

    def test_wc_ratio_from_strength_opc43_48mpa(self):
        """OPC 43 at 48 MPa should give w/c ≈ 0.36 (standard worked example: 48.25→0.36)."""
        result = wc_ratio_from_strength(48.0, "OPC_43")
        assert abs(result - 0.3616) < 0.01

    def test_wc_ratio_from_strength_opc33_38mpa(self):
        """OPC 33 at 38 MPa should give w/c ≈ 0.39 per IS Fig.1 Curve A (OPC 33 < OPC 43 at same strength)."""
        result = wc_ratio_from_strength(38.0, "OPC_33")
        assert abs(result - 0.3920) < 0.01

    def test_wc_ratio_from_strength_opc53_55mpa(self):
        """OPC 53 at 55 MPa should give w/c ≈ 0.36 per IS Fig.1 Curve C (OPC 53 > OPC 43 at same strength)."""
        result = wc_ratio_from_strength(55.0, "OPC_53")
        assert abs(result - 0.3587) < 0.01

    def test_wc_ratio_standard_worked_example_a(self):
        """Annex A/B: target=48.25 MPa → w/c=0.36 for OPC 43."""
        result = wc_ratio_from_strength(48.25, "OPC_43")
        assert abs(result - 0.36) < 0.01

    def test_wc_ratio_standard_worked_example_e(self):
        """Annex E: target=38.25 MPa → w/c=0.43 for OPC 43."""
        result = wc_ratio_from_strength(38.25, "OPC_43")
        assert abs(result - 0.43) < 0.01

    def test_wc_ratio_standard_worked_example_f(self):
        """Annex F: target=20.77 MPa → w/c=0.61 for OPC 43."""
        result = wc_ratio_from_strength(20.77, "OPC_43")
        assert abs(result - 0.61) < 0.01

    def test_wc_ratio_works_for_any_strength(self):
        """Polynomial equation should work for any target strength."""
        # OPC 43 at 40 MPa (below curve restraint min of 43)
        result = wc_ratio_from_strength(40.0, "OPC_43")
        assert result > 0
        # OPC 43 at 55 MPa (above curve restraint max of 53)
        result = wc_ratio_from_strength(55.0, "OPC_43")
        assert result > 0
        # OPC 53 at 50 MPa (below curve restraint min of 53)
        result = wc_ratio_from_strength(50.0, "OPC_53")
        assert result > 0

    def test_curve_restraints_defined(self):
        """All curve restraints should be defined."""
        assert "OPC_33" in CURVE_RESTRAINTS
        assert "OPC_43" in CURVE_RESTRAINTS
        assert "OPC_53" in CURVE_RESTRAINTS
        assert CURVE_RESTRAINTS["OPC_33"] == (33.0, 43.0)
        assert CURVE_RESTRAINTS["OPC_43"] == (43.0, 53.0)
        assert CURVE_RESTRAINTS["OPC_53"][0] == 53.0

    def test_curve_restraints_opc33_valid_range(self):
        """OPC 33 should accept strength in range 33-43 MPa."""
        result = wc_ratio_from_strength(38.0, "OPC_33")
        assert result > 0

    def test_interpolate_w_c_ratio_backward_compat(self):
        """interpolate_w_c_ratio should still work for backward compatibility."""
        result = interpolate_w_c_ratio(48.0, "OPC_43")
        assert abs(result - 0.3616) < 0.01


# ---------------------------------------------------------------------------
# IS 10262 — Coarse Aggregate Volume (Table 7)
# ---------------------------------------------------------------------------
class TestCAVolumeFraction:
    """Verify CA volume fraction from IS 10262:2019 Table 5."""

    def test_20mm_zone_ii(self):
        result = get_ca_volume_fraction(20, "II")
        assert abs(result - 0.62) < 0.01

    def test_20mm_zone_i(self):
        result = get_ca_volume_fraction(20, "I")
        assert abs(result - 0.60) < 0.01

    def test_10mm_zone_ii(self):
        result = get_ca_volume_fraction(10, "II")
        assert abs(result - 0.50) < 0.01

    def test_40mm_zone_ii(self):
        result = get_ca_volume_fraction(40, "II")
        assert abs(result - 0.71) < 0.01


# ---------------------------------------------------------------------------
# IS 10262 — Full Design Integration
# ---------------------------------------------------------------------------
class TestISDesignIntegration:
    """Integration tests for IS 10262 design method."""

    def test_m25_mild_exposure_cement_above_minimum(self):
        """Verify cement content meets IS 456 mild exposure minimum for reinforced (300 kg/m³)."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            exposure_class="mild",
            concrete_type="reinforced",
        )
        result = designer.design(inp)
        assert result.cement_kg >= 300.0, (
            f"Cement {result.cement_kg} below IS 456 reinforced mild minimum of 300 kg/m³"
        )

    def test_m25_moderate_exposure_wc_within_limit(self):
        """Verify W/C ratio respects IS 456 moderate exposure limit (0.60)."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=50.0,
            exposure_class="moderate",
        )
        result = designer.design(inp)
        assert result.w_c_ratio <= 0.60, (
            f"W/C ratio {result.w_c_ratio} exceeds IS 456 moderate limit of 0.60"
        )

    def test_m25_target_mean_strength(self):
        """ftm = 25 + 1.65 × 4.0 = 31.6 → 32 MPa (ceiled, Cl. 4.2)."""
        designer = IS10262MixDesign()
        result = designer.calculate_target_mean_strength(25.0, 4.0)
        assert abs(result - 32) < 0.01

    def test_m20_target_mean_strength(self):
        """ftm = 20 + 1.65 × 4.0 = 26.6 → 27 MPa (ceiled, Cl. 4.2)."""
        designer = IS10262MixDesign()
        result = designer.calculate_target_mean_strength(20.0, 4.0)
        assert abs(result - 27) < 0.01

    def test_no_double_water_adjustment(self):
        """Verify water is NOT double-counted for high slump."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=100.0,
            exposure_class="mild",
        )
        result = designer.design(inp)
        # Clause 5.3: 100mm slump = +6% → 186 × 1.06 = 197.16
        assert result.water_kg <= 198.0, (
            f"Water {result.water_kg} too high — possible double-counting"
        )

    def test_m25_mild_exposure_plain_concrete_cement_above_minimum(self):
        """Verify plain concrete mild minimum is 220 kg/m³ (lower than reinforced 300)."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            exposure_class="mild",
            concrete_type="plain",
        )
        result = designer.design(inp)
        assert result.cement_kg >= 220.0, (
            f"Cement {result.cement_kg} below IS 456 plain mild minimum of 220 kg/m³"
        )

    def test_entrapped_air_40mm(self):
        """Verify 40mm entrapped air is 0.8% (not 0.5%)."""
        designer = IS10262MixDesign()
        air = designer.get_air_content(40)
        assert air == 0.8

    def test_entrapped_air_20mm(self):
        designer = IS10262MixDesign()
        air = designer.get_air_content(20)
        assert air == 1.0

    def test_entrapped_air_10mm(self):
        designer = IS10262MixDesign()
        air = designer.get_air_content(10)
        assert air == 1.5


# ---------------------------------------------------------------------------
# IS 10262:2019 Clause 5.8 — Trial Mixes and Reporting
# ---------------------------------------------------------------------------

class TestIS10262TrialMixesClause58:
    """Verify Section 5.8 Trial Mixes calculation and Clause 5.8.1 reporting protocol."""

    def test_trial_mixes_protocol_calculation(self):
        """Verify 4 trial mixes generation with ±10% W/C variation."""
        from concrete_mix import design_mix_simple
        from concrete_mix.codes.is10262 import calculate_is10262_trial_mixes

        result = design_mix_simple(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            nmsa=20,
            exposure_class="mild",
        )
        inp = getattr(result, "_input", None)

        protocol = calculate_is10262_trial_mixes(result, inp)
        assert protocol["standard"] == "IS 10262:2019"
        assert "5.8" in protocol["clause"]
        assert len(protocol["trials"]) == 4

        t1, t2, t3, t4 = protocol["trials"]

        # Trial 1 & 2 at design W/C
        assert t1["trial_number"] == 1
        assert t1["w_c_ratio"] == result.w_c_ratio
        assert t1["water_kg"] == result.water_kg
        assert t1["cement_kg"] == result.cement_kg

        assert t2["trial_number"] == 2
        assert t2["w_c_ratio"] == result.w_c_ratio
        assert t2["water_kg"] == result.water_kg

        # Trial 3 at -10% W/C (higher cement)
        assert t3["trial_number"] == 3
        assert t3["w_c_ratio"] == pytest.approx(round(result.w_c_ratio * 0.90, 2))
        assert t3["water_kg"] == result.water_kg
        assert t3["cement_kg"] > result.cement_kg

        # Trial 4 at +10% W/C (lower cement)
        assert t4["trial_number"] == 4
        assert t4["w_c_ratio"] == pytest.approx(round(result.w_c_ratio * 1.10, 2))
        assert t4["water_kg"] == result.water_kg
        assert t4["cement_kg"] < result.cement_kg

        # All trials have positive aggregate quantities
        for t in (t1, t2, t3, t4):
            assert t["fine_agg_kg"] > 0
            assert t["coarse_agg_kg"] > 0
            assert t["water_kg"] > 0
            assert t["cement_kg"] > 0

    def test_reporting_checklist_contains_clause_5_8_1_items(self):
        """Verify Clause 5.8.1 reporting checklist items (a to g)."""
        from concrete_mix.codes.is10262 import calculate_is10262_trial_mixes

        designer = IS10262MixDesign()
        inp = MixDesignInput(code="is10262", target_strength_mpa=30.0)
        result = designer.design(inp)

        protocol = calculate_is10262_trial_mixes(result, inp)
        checklist = protocol["reporting_checklist"]
        assert len(checklist) == 7
        codes = [item[0] for item in checklist]
        assert codes == ["a", "b", "c", "d", "e", "f", "g"]

        # Check content of items
        assert "Period of testing" in checklist[0][1]
        assert "Details of work" in checklist[1][1]
        assert "Recommended final mix" in checklist[6][1]

    def test_design_includes_clause_5_8_step_and_warning(self):
        """Verify design result includes Clause 5.8 step and warnings."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(code="is10262", target_strength_mpa=25.0)
        result = designer.design(inp)

        # Check calculation steps
        trial_steps = [s for s in result.steps if "5.8" in s.clause_ref or "Trial" in s.description]
        assert len(trial_steps) >= 1
        assert trial_steps[0].result == 4.0

        # Check warnings
        trial_warnings = [w for w in result.warnings if "5.8" in w and "trial" in w.lower()]
        assert len(trial_warnings) >= 1
        assert "±10%" in trial_warnings[0]

    def test_no_app_floor_m20_designs(self):
        """No 25 MPa floor: M20 IS designs with Table 2 values (S=4.0, X=5.5)."""
        designer = IS10262MixDesign()
        result = designer.design(MixDesignInput(
            code="is10262", target_strength_mpa=20.0, slump_mm=75.0,
            exposure_class="mild"))
        # ftm = max(20 + 1.65×4.0, 20 + 5.5) = 26.6 → 27 MPa (ceiled, Cl. 4.2)
        assert abs(result.target_mean_strength_mpa - 27) < 0.01

    def test_sanity_floor_still_guards(self):
        """The [5, 100] MPa sanity range still rejects nonsense."""
        with pytest.raises(ValueError, match=r"\[5, 100\]"):
            MixDesignInput(code="is10262", target_strength_mpa=4.0)


# ---------------------------------------------------------------------------
# IS 10262 small scope items: placing method, site control, SD record,
# admixture water (gap-audit all-phases)
# ---------------------------------------------------------------------------
class TestISPlacingSiteControlAdmixWater:
    def test_pump_reduces_ca_ten_percent(self):
        """Pumped placing cuts the Table 5 fraction by 10% (§5.5.2)."""
        from concrete_mix import design_mix_simple

        chute = design_mix_simple(code="is10262", target_strength_mpa=30.0,
                                  slump_mm=75.0, nmsa=20, exposure_class="mild")
        pump = design_mix_simple(code="is10262", target_strength_mpa=30.0,
                                 slump_mm=75.0, nmsa=20, exposure_class="mild",
                                 placing_method="pump")
        assert pump.fine_aggregate_kg > chute.fine_aggregate_kg
        assert pump.coarse_aggregate_kg < chute.coarse_aggregate_kg
        assert any("§5.5.2" in w for w in pump.warnings)

    def test_invalid_placing_rejected(self):
        with pytest.raises(ValueError, match="Placing method"):
            MixDesignInput(code="is10262", target_strength_mpa=30.0,
                           placing_method="crane")

    def test_pump_explicit_percent_honoured(self):
        """Explicit 6% pump reduction applies instead of the 10% maximum."""
        from concrete_mix import design_mix_simple

        auto = design_mix_simple(code="is10262", target_strength_mpa=30.0,
                                 slump_mm=75.0, nmsa=20, exposure_class="mild",
                                 placing_method="pump")
        explicit = design_mix_simple(
            code="is10262", target_strength_mpa=30.0, slump_mm=75.0,
            nmsa=20, exposure_class="mild", placing_method="pump",
            pump_ca_reduction_percent=6.0)
        assert explicit.coarse_aggregate_kg > auto.coarse_aggregate_kg
        assert any("6%" in w for w in explicit.warnings)

    def test_pump_percent_above_route_max_rejected(self):
        """12% is rejected at the model (0–10); 8% on a high-strength
        route is rejected by the engine (§6.2.7 caps at 5%)."""
        with pytest.raises(ValueError, match="0–10"):
            MixDesignInput(code="is10262", target_strength_mpa=30.0,
                           placing_method="pump",
                           pump_ca_reduction_percent=12.0)
        designer = IS10262MixDesign()
        with pytest.raises(ValueError, match="5% maximum"):
            designer.design(MixDesignInput(
                code="is10262", target_strength_mpa=70.0, slump_mm=75.0,
                placing_method="pump", pump_ca_reduction_percent=8.0))

    def test_unknown_zone_rejected(self):
        """Table 5/13 tabulate every zone — unknown zones raise (F7)."""
        from concrete_mix.codes.tables.is_tables import (
            get_ca_volume_fraction, mass_ca_volume_fraction)
        with pytest.raises(ValueError, match="Grading zone"):
            get_ca_volume_fraction(20, "V")
        with pytest.raises(ValueError, match="Grading zone"):
            mass_ca_volume_fraction(40, "V")

    def test_fair_site_control_raises_target(self):
        """Fair control adds 1 N/mm² to S (Table 2 Note 1)."""
        from concrete_mix.engine.target_strength import calculate_target_strength

        good = calculate_target_strength("is10262", 30.0, site_control="good")
        fair = calculate_target_strength("is10262", 30.0, site_control="fair")
        # good: 30 + 1.65×5 = 38.25 → 39; fair: 30 + 1.65×6 = 39.9 → 40 (ceiled, Cl. 4.2)
        assert good.target_mean_strength_mpa == pytest.approx(39)
        assert fair.target_mean_strength_mpa == pytest.approx(40)
        assert fair.target_mean_strength_mpa > good.target_mean_strength_mpa
        assert fair.standard_deviation_mpa == 6.0

    def test_user_std_deviation_override(self):
        """A site record (≥30 results) replaces the assumed deviation."""
        from concrete_mix.engine.target_strength import calculate_target_strength

        r = calculate_target_strength("is10262", 30.0, std_deviation=4.0)
        assert r.standard_deviation_mpa == 4.0
        # 30 + 1.65×4 = 36.6 → 37 MPa (ceiled, IS 10262 Cl. 4.2)
        assert abs(r.target_mean_strength_mpa - 37) < 0.01

    def test_design_honours_site_control_and_override(self):
        designer = IS10262MixDesign()
        fair_inp = MixDesignInput(code="is10262", target_strength_mpa=30.0,
                                  site_control="fair")
        # 30 + 1.65×6 = 39.9 → 40 MPa (ceiled, IS 10262 Cl. 4.2)
        assert abs(designer.design(fair_inp).target_mean_strength_mpa
                   - 40) < 0.01
        user_inp = MixDesignInput(code="is10262", target_strength_mpa=30.0,
                                  std_deviation=4.5)
        # 30 + 1.65×4.5 = 37.425 → 38 MPa (ceiled, IS 10262 Cl. 4.2)
        assert abs(designer.design(user_inp).target_mean_strength_mpa
                   - 38) < 0.01

    def test_std_helpers_validate_records(self):
        from concrete_mix.codes.tables.is_tables import (
            pooled_std_dev, std_from_samples)

        with pytest.raises(ValueError, match="at least 30"):
            std_from_samples([30.0] * 29)
        assert abs(std_from_samples([30.0] * 30) - 0.0) < 1e-9
        with pytest.raises(ValueError, match="n1,n2"):
            pooled_std_dev(4.0, 9, 4.0, 25)
        assert abs(pooled_std_dev(4.0, 15, 5.0, 15) - 4.528) < 0.01

    def test_admixture_water_counted_at_cap(self):
        """Admixture water breaching the durability cap blocks (Cl. 5.1 note)."""
        designer = IS10262MixDesign()
        ok_inp = MixDesignInput(
            code="is10262", target_strength_mpa=30.0, slump_mm=75.0,
            exposure_class="mild",
            admixture_water_kg=5.0,
        )
        ok = designer.design(ok_inp)
        assert any(s.step_number == 3.1 for s in ok.steps)
        # M25/moderate with a manual 0.60 w/c: capped to 0.50, so 60 kg of
        # admixture water pushes the effective ratio far over the cap.
        bad_inp = MixDesignInput(
            code="is10262", target_strength_mpa=25.0, slump_mm=75.0,
            exposure_class="moderate", w_c_ratio=0.60,
            admixture_water_kg=60.0,
        )
        with pytest.raises(ValueError, match="durability maximum"):
            designer.design(bad_inp)
# ---------------------------------------------------------------------------
# IS 10262 §6 — high-strength concrete (M65+)
# ---------------------------------------------------------------------------
class TestISHighStrength:
    def _m70(self, **kw):
        from concrete_mix.models.materials import (
            AggregateShape, Cement, CementType, CoarseAggregate, FineAggregate,
        )

        base = dict(
            code="is10262", target_strength_mpa=70.0, slump_mm=50.0,
            exposure_class="severe", concrete_type="reinforced",
            cement=Cement(type=CementType.OPC_53, specific_gravity=3.15),
            fine_aggregate=FineAggregate(specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
        )
        base.update(kw)
        return MixDesignInput(**base)

    def test_m70_uses_table8_and_table7(self):
        """ftm max(70 + 1.65×6, 70 + 8) = 79.9 → 80 (ceiled) → w/cm ≈0.29 (Table 8); water 186 (Table 7); air 0.5."""
        designer = IS10262MixDesign()
        result = designer.design(self._m70())
        assert abs(result.target_mean_strength_mpa - 80) < 0.05
        assert abs(result.w_c_ratio - 0.29) < 0.02
        assert result.water_kg == 186.0
        assert result.air_volume_percent == 0.5
        assert any("Table 8" in s.clause_ref for s in result.steps)

    def test_m70_flags_heat_and_hrwra(self):
        """640 kg cement triggers the 450 warning + PCE + quality notes."""
        designer = IS10262MixDesign()
        result = designer.design(self._m70())
        assert any("450" in w for w in result.warnings)
        assert any("PCE" in w for w in result.warnings)
        assert any("22%" in w for w in result.warnings)

    def test_40mm_blocked(self):
        from concrete_mix.models.materials import CoarseAggregate

        designer = IS10262MixDesign()
        inp = self._m70(coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=40, specific_gravity=2.74))
        with pytest.raises(ValueError, match="§6.2.2"):
            designer.design(inp)

    def test_zone_iv_blocked(self):
        from concrete_mix.models.materials import FineAggregate

        designer = IS10262MixDesign()
        inp = self._m70(fine_aggregate=FineAggregate(
            specific_gravity=2.65, grading_zone="IV"))
        with pytest.raises(ValueError, match="Table 10"):
            designer.design(inp)

    def test_m80_prefers_10mm(self):
        designer = IS10262MixDesign()
        inp = self._m70()
        object.__setattr__(inp, "target_strength_mpa", 80.0)
        result = designer.design(inp)
        assert any("10.0–12.5" in w for w in result.warnings)

    def test_silica_dosage_band(self):
        from concrete_mix.models.materials import SCM, SCMType

        designer = IS10262MixDesign()
        inp = self._m70(scms=(SCM(type=SCMType.SILICA_FUME,
                                  replacement_percent=12.0),))
        result = designer.design(inp)
        assert any("Table 9" in w for w in result.warnings)

    def test_trial_clause_is_629(self):
        designer = IS10262MixDesign()
        result = designer.design(self._m70())
        step8 = next(s for s in result.steps if s.step_number == 8)
        assert "6.2.9" in step8.clause_ref

    def test_table_helpers(self):
        from concrete_mix.codes.tables.is_tables import (
            hs_ca_volume_fraction, hs_wcm_ratio, hs_water_content)

        assert hs_wcm_ratio(70.0, 20) == 0.33
        assert abs(hs_wcm_ratio(77.5, 20) - 0.30) < 1e-9
        assert hs_water_content(10, 75.0) == 206.0
        assert hs_ca_volume_fraction(20, "II") == 0.66
        with pytest.raises(ValueError, match="Table 10"):
            hs_ca_volume_fraction(20, "IV")
        with pytest.raises(ValueError, match="§6.2.2"):
            hs_water_content(40, 50.0)


# ---------------------------------------------------------------------------
# IS 10262 §9 — mass concrete
# ---------------------------------------------------------------------------
class TestISMassConcrete:
    def _m25_80mm(self, **kw):
        from concrete_mix.models.materials import (
            AggregateShape, CoarseAggregate, FineAggregate,
        )

        base = dict(
            code="is10262", target_strength_mpa=25.0, slump_mm=50.0,
            exposure_class="mild", concrete_type="reinforced",
            mass_concrete=True,
            fine_aggregate=FineAggregate(specific_gravity=2.65,
                                         grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=80, specific_gravity=2.70,
                shape=AggregateShape.ANGULAR),
        )
        base.update(kw)
        return MixDesignInput(**base)

    def test_80mm_uses_table12_and_wet_sieving(self):
        """Water 145 (Table 12); target 32 × 1.2 = 38.4 (§9.2,
        reporting only — w/c keeps the un-raised 32); air 0.3."""
        designer = IS10262MixDesign()
        result = designer.design(self._m25_80mm())
        assert result.water_kg == 145.0
        assert abs(result.target_mean_strength_mpa - 38.4) < 0.01
        assert result.air_volume_percent == 0.3

    def test_mortar_check_present(self):
        """80 mm designs carry the §9.10/Table 15 mortar step."""
        designer = IS10262MixDesign()
        result = designer.design(self._m25_80mm())
        assert any(s.step_number == 6.1 for s in result.steps)

    def test_rounded_cut(self):
        """Rounded 80 mm gravel cuts 15 kg (§9.4): 145 → 130."""
        from concrete_mix.models.materials import (
            AggregateShape, CoarseAggregate,
        )

        designer = IS10262MixDesign()
        inp = self._m25_80mm(coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=80, specific_gravity=2.70,
            shape=AggregateShape.ROUNDED_GRAVEL))
        assert designer.design(inp).water_kg == 130.0

    def test_40mm_mass_has_no_mortar_step(self):
        """Table 15 covers 80/150 mm only — 40 mm mass skips the check."""
        from concrete_mix.models.materials import CoarseAggregate

        designer = IS10262MixDesign()
        inp = self._m25_80mm(coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=40, specific_gravity=2.70))
        result = designer.design(inp)
        assert result.water_kg == 165.0
        assert not any(s.step_number == 6.1 for s in result.steps)

    def test_80mm_auto_routes_to_mass(self):
        """80 mm aggregate without the flag still takes the mass route."""
        designer = IS10262MixDesign()
        inp = self._m25_80mm(mass_concrete=False)
        result = designer.design(inp)
        assert result.water_kg == 145.0

    def test_mass_ggbs30_bump(self):
        """Mass GGBS ≥30% earns the §9.6.1 preliminary-trial increase."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = IS10262MixDesign()
        inp = self._m25_80mm(
            scms=(SCM(type=SCMType.GGBFS, replacement_percent=30.0),))
        result = designer.design(inp)
        assert any(s.step_number == 4.05 for s in result.steps)

    def test_hs_mass_conflict_blocked(self):
        designer = IS10262MixDesign()
        inp = self._m25_80mm()
        object.__setattr__(inp, "target_strength_mpa", 70.0)
        with pytest.raises(ValueError, match="no combined"):
            designer.design(inp)

    def test_trial_clause_is_911(self):
        designer = IS10262MixDesign()
        result = designer.design(self._m25_80mm())
        step8 = next(s for s in result.steps if s.step_number == 8)
        assert "9.11" in step8.clause_ref


# ---------------------------------------------------------------------------
# IS 10262 §§7–8 — self-compacting concrete checks
# ---------------------------------------------------------------------------
class TestISSCC:
    def _scc_base(self, **kw):
        from concrete_mix.models.materials import (
            Admixture, AdmixtureType, AggregateShape, CoarseAggregate,
            FineAggregate,
        )

        base = dict(
            code="is10262", target_strength_mpa=30.0, slump_mm=50.0,
            exposure_class="mild", concrete_type="reinforced",
            fine_aggregate=FineAggregate(specific_gravity=2.65,
                                         grading_zone="I"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=10, specific_gravity=2.70,
                shape=AggregateShape.ANGULAR),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=30.0),
        )
        base.update(kw)
        return MixDesignInput(**base)

    def test_passing_scc_has_no_scc_warnings(self):
        """In-class SF2 measurements on an in-envelope mix stay quiet.

        Slump 100 mm with the §8.3(c) PCE reduction (30%) keeps the mixing
        water inside the 150–210 kg/m³ band; coarser Zone I sand keeps fine
        aggregate within 48–60%.
        """
        designer = IS10262MixDesign()
        result = designer.design(self._scc_base(
            slump_mm=100.0,
            scc_class="SF2", scc_slump_flow_mm=700.0, scc_lbox_ratio=0.85,
            scc_segregation_pct=12.0, scc_vfunnel_s=6.0))
        assert any(s.step_number == 8.1 for s in result.steps)
        assert not any(("SF2" in w and "outside" in w) or "L-box" in w
                       or "Segregation" in w or "V-funnel" in w
                       or "48–60%" in w or "150–210" in w or "PCE" in w
                       for w in result.warnings)

    def test_scc_admixture_below_30pct_warns(self):
        """§8.3(c): SCC water reduction comes from PCE HRWRA at >30%."""
        from concrete_mix.models.materials import Admixture, AdmixtureType

        designer = IS10262MixDesign()
        result = designer.design(self._scc_base(
            slump_mm=100.0,
            scc_class="SF2", admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=25.0)))
        assert any("PCE" in w for w in result.warnings)

    def test_slump_flow_outside_target_warns(self):
        designer = IS10262MixDesign()
        result = designer.design(self._scc_base(
            scc_class="SF2", scc_slump_flow_mm=800.0))
        assert any("outside the target SF2" in w for w in result.warnings)

    def test_lbox_segregation_vfunnel_warn(self):
        designer = IS10262MixDesign()
        result = designer.design(self._scc_base(
            scc_lbox_ratio=0.70, scc_segregation_pct=25.0,
            scc_vfunnel_s=30.0))
        assert any("0.80" in w for w in result.warnings)
        assert any("SR1" in w for w in result.warnings)
        assert any("V2" in w for w in result.warnings)

    def test_powder_over_600_blocks(self):
        """Cement+SCM alone above 600 kg/m³ provably breaches §8.3(a)."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = IS10262MixDesign()
        inp = self._scc_base(
            target_strength_mpa=40.0, admixture=None,
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=20.0),),
            scc_class="SF2")
        with pytest.raises(ValueError, match="400–600"):
            designer.design(inp)

    def test_invalid_scc_inputs_rejected(self):
        with pytest.raises(ValueError, match="SCC class"):
            MixDesignInput(code="is10262", target_strength_mpa=30.0,
                           scc_class="SF4")
        with pytest.raises(ValueError, match="must be positive"):
            MixDesignInput(code="is10262", target_strength_mpa=30.0,
                           scc_lbox_ratio=-0.5)
# ---------------------------------------------------------------------------
# IS 456:2000 Table 5 durability gates (gap-audit Phase 1)
# ---------------------------------------------------------------------------
class TestIS456DurabilityGates:
    """Minimum-grade enforcement, 450 kg/m³ preferred maximum, Zone IV rule."""

    def test_severe_exposure_rejects_below_m30(self):
        """M25 + severe/reinforced violates the M30 minimum (IS 456 Table 5)."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            exposure_class="severe",
            concrete_type="reinforced",
        )
        with pytest.raises(ValueError, match="minimum grade M30"):
            designer.design(inp)

    def test_extreme_exposure_rejects_below_m40(self):
        """M30 + extreme/reinforced violates the M40 minimum (IS 456 Table 5)."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            exposure_class="extreme",
            concrete_type="reinforced",
        )
        with pytest.raises(ValueError, match="minimum grade M40"):
            designer.design(inp)

    def test_severe_exposure_accepts_m30(self):
        """M30 + severe/reinforced is exactly the Table 5 minimum — passes."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            exposure_class="severe",
            concrete_type="reinforced",
        )
        result = designer.design(inp)
        assert result.w_c_ratio <= 0.45

    def test_no_exposure_no_grade_gate(self):
        """Without an exposure class there is no Table 5 grade to enforce."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(code="is10262", target_strength_mpa=25.0)
        result = designer.design(inp)
        assert result.target_mean_strength_mpa > 25.0

    def test_cement_above_450_warns(self):
        """Cement-only content above 450 kg/m³ warns per IS 456 Cl 8.2.4.2."""
        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=180.0,
            exposure_class="mild",
            concrete_type="reinforced",
        )
        result = designer.design(inp)
        assert result.cement_kg > 450.0
        assert any("450" in w and "8.2.4.2" in w for w in result.warnings)

    def test_zone_iv_reinforced_warns(self):
        """Zone IV sand in reinforced concrete warns per Table 5 Note 4."""
        from concrete_mix.models.materials import FineAggregate

        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            exposure_class="mild",
            concrete_type="reinforced",
            fine_aggregate=FineAggregate(grading_zone="IV"),
        )
        result = designer.design(inp)
        assert any("Zone IV" in w for w in result.warnings)

    def test_zone_iv_plain_no_warning(self):
        """Zone IV in plain concrete is not subject to the Note 4 warning."""
        from concrete_mix.models.materials import FineAggregate

        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            exposure_class="mild",
            concrete_type="plain",
            fine_aggregate=FineAggregate(grading_zone="IV"),
        )
        result = designer.design(inp)
        assert not any("Zone IV" in w for w in result.warnings)

    def test_admixture_mass_without_water_reduction(self):
        """A dosed admixture with 0% reduction still has mass/volume (A-9e)."""
        from concrete_mix.models.materials import Admixture, AdmixtureType

        designer = IS10262MixDesign()
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            exposure_class="mild",
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER,
                dosage_percent=1.0,
                water_reduction_percent=0.0,
            ),
        )
        result = designer.design(inp)
        assert result.admixture_kg is not None and result.admixture_kg > 0
        # Water must be unreduced (no reduction applied): 186 × 1.03
        # (75 mm slump) − 15 kg (default gravel shape, Cl. 5.3).
        assert abs(result.water_kg - 176.6) < 1.0
        # ... yet the admixture mass step must exist.
        adm_steps = [s for s in result.steps if "Admixture content" in s.description]
        assert len(adm_steps) == 1

