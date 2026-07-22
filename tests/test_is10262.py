"""Tests for IS 10262:2019 and IS 456:2000 compliance.

Verifies that all table values and calculations match the published standards.
"""

import pytest

from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.codes.tables.is_tables import (
    CURVE_RESTRAINTS,
    GRADING_ZONE_ADJUSTMENT,
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
# Phase 8: Grading Zone Adjustments
# ---------------------------------------------------------------------------
class TestGradingZoneAdjustment:
    """Verify grading zone water adjustment factors."""

    def test_zone_ii_is_reference(self):
        assert GRADING_ZONE_ADJUSTMENT["II"] == 1.0

    def test_zone_i_reduces_water(self):
        """Regression: was 1.0, should be 0.97."""
        assert GRADING_ZONE_ADJUSTMENT["I"] == 0.97

    def test_zone_iii_increases_water(self):
        assert GRADING_ZONE_ADJUSTMENT["III"] == 1.03

    def test_zone_iv_increases_water(self):
        assert GRADING_ZONE_ADJUSTMENT["IV"] == 1.06

    def test_water_with_zone_i(self):
        result = interpolate_water_content(20, 50, "I")
        expected = 186 * 0.97  # = 180.42
        assert abs(result - expected) < 0.1

    def test_water_with_zone_iii(self):
        result = interpolate_water_content(20, 50, "III")
        expected = 186 * 1.03  # = 191.58
        assert abs(result - expected) < 0.1


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
        """OPC 33 at 38 MPa should give w/c ≈ 0.43 (standard worked example: 38.25→0.43)."""
        result = wc_ratio_from_strength(38.0, "OPC_33")
        assert abs(result - 0.4320) < 0.01

    def test_wc_ratio_from_strength_opc53_55mpa(self):
        """OPC 53 at 55 MPa should give w/c ≈ 0.32."""
        result = wc_ratio_from_strength(55.0, "OPC_53")
        assert abs(result - 0.3187) < 0.01

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
        """ftm = 25 + 1.65 × 4.0 = 31.6 MPa."""
        designer = IS10262MixDesign()
        result = designer.calculate_target_mean_strength(25.0, 4.0)
        assert abs(result - 31.6) < 0.1

    def test_m20_target_mean_strength(self):
        """ftm = 20 + 1.65 × 4.0 = 26.6 MPa."""
        designer = IS10262MixDesign()
        result = designer.calculate_target_mean_strength(20.0, 4.0)
        assert abs(result - 26.6) < 0.1

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
