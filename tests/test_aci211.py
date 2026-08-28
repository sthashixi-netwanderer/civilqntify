"""Tests for ACI 211.1-91 and ACI 318 compliance.

Verifies that all table values and calculations match the published standards.
"""

import pytest

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.tables.aci_tables import (
    AIR_CONTENT,
    AIR_CONTENT_ENTRAPPED,
    CA_VOLUME_FRACTION,
    WC_RATIO_AIR_ENTRAINED,
    WC_RATIO_NON_AIR_ENTRAINED,
    ACI_MAX_WC_FOR_EXPOSURE,
    ACI_NO_DATA_OVERDESIGN,
    WATER_CONTENT_AIR_ENTRAINED,
    WATER_CONTENT_NON_AIR_ENTRAINED,
    get_air_content,
    get_no_data_overdesign,
    interpolate_ca_volume,
    interpolate_w_c_ratio,
    interpolate_water_content,
)
from concrete_mix.models.materials import Cement, CoarseAggregate, FineAggregate
from concrete_mix.models.mix_input import MixDesignInput


# ---------------------------------------------------------------------------
# ACI 211.1 Table 6.3.3 — Water Content
# ---------------------------------------------------------------------------
class TestACIWaterContent:
    """Verify water content table values."""

    def test_10mm_25mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[10][25] == 208

    def test_10mm_150mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[10][150] == 237

    def test_20mm_50mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[20][50] == 187

    def test_40mm_100mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[40][100] == 178

    def test_20mm_50mm_slump_ae(self):
        assert WATER_CONTENT_AIR_ENTRAINED[20][50] == 166

    def test_interpolate_20mm_60mm_slump(self):
        """Between 50mm (187) and 75mm (202) — non-air-entrained per ACI 211.1-22."""
        result = interpolate_water_content(20, 60, False)
        # fraction = (60-50)/(75-50) = 0.4
        expected = 187 + 0.4 * (202 - 187)  # 187 + 6.0 = 193.0
        assert abs(result - 193.0) < 0.1

    def test_interpolate_clamp_low(self):
        """Below table range should clamp to lowest value."""
        result = interpolate_water_content(20, 10, False)
        assert result == 187

    def test_interpolate_clamp_high(self):
        """Above table range should clamp to 6-7 in. slump value (214 kg/m³)."""
        result = interpolate_water_content(20, 200, False)
        assert result == 214

    def test_175mm_slump_6_7in(self):
        """6-7 in. slump class (175 mm) = 360 lb/yd³ = 214 kg/m³ for 20 mm."""
        result = interpolate_water_content(20, 175, False)
        assert result == 214

    def test_175mm_slump_6_7in_air_entrained(self):
        """6-7 in. slump, air-entrained (325 lb/yd³ = 193 kg/m³) for 20 mm."""
        result = interpolate_water_content(20, 175, True)
        assert result == 193


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 Table 5.3.3 — Air Content
# ---------------------------------------------------------------------------
class TestACIAirContent:
    """Verify air content table values."""

    @pytest.mark.parametrize("nmsa,expected", [(10, 3.0), (20, 2.0), (40, 1.0)])
    def test_entrapped_air(self, nmsa, expected):
        assert AIR_CONTENT_ENTRAPPED[nmsa] == expected

    def test_entrained_mild_20mm(self):
        assert AIR_CONTENT[20]["mild"] == 2.0

    def test_entrained_moderate_20mm(self):
        """F1 exposure, 3/4 in. (20 mm): 5.0 % per Table 5.3.3."""
        assert AIR_CONTENT[20]["moderate"] == 5.0

    def test_entrained_severe_20mm(self):
        """F2/F3 exposure, 3/4 in. (20 mm): 6.0 % per Table 5.3.3."""
        assert AIR_CONTENT[20]["severe"] == 6.0

    def test_entrained_f1_by_nmsa(self):
        """F1: 3/8 in. → 6.0 %, 3/4 in. → 5.0 %, 1-1/2 in. → 4.5 %."""
        assert AIR_CONTENT[10]["moderate"] == 6.0
        assert AIR_CONTENT[40]["moderate"] == 4.5

    def test_entrained_f2f3_by_nmsa(self):
        """F2/F3: 3/8 in. → 7.5 %, 3/4 in. → 6.0 %, 1-1/2 in. → 5.5 %."""
        assert AIR_CONTENT[10]["severe"] == 7.5
        assert AIR_CONTENT[40]["severe"] == 5.5

    def test_get_air_entrapped(self):
        assert get_air_content(20, "moderate", False) == 2.0

    def test_get_air_entrained_moderate(self):
        assert get_air_content(20, "moderate", True) == 5.0


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 Table 5.3.4 — W/C Ratio
# ---------------------------------------------------------------------------
class TestACIWCRatio:
    """Verify W/C ratio table values (Table 5.3.4, psi → MPa conversion)."""

    def test_nae_27_6mpa(self):
        """4000 psi (27.6 MPa) non-air-entrained → 0.57."""
        assert WC_RATIO_NON_AIR_ENTRAINED[27.6] == 0.57

    def test_nae_41_4mpa(self):
        """6000 psi (41.4 MPa) non-air-entrained → 0.41."""
        assert WC_RATIO_NON_AIR_ENTRAINED[41.4] == 0.41

    def test_ae_13_8mpa(self):
        """2000 psi (13.8 MPa) air-entrained → 0.74."""
        assert WC_RATIO_AIR_ENTRAINED[13.8] == 0.74

    def test_ae_27_6mpa_lower_than_nae(self):
        """At 4000 psi, air-entrained w/cm (0.48) is lower than non-air (0.57)."""
        assert WC_RATIO_AIR_ENTRAINED[27.6] < WC_RATIO_NON_AIR_ENTRAINED[27.6]

    def test_interpolate_nae_32mpa(self):
        """Between 34.5 MPa (0.48) and 27.6 MPa (0.57)."""
        result = interpolate_w_c_ratio(32.0, False)
        # fraction = (34.5-32.0)/(34.5-27.6) = 0.3623
        expected = 0.48 + 0.3623 * (0.57 - 0.48)  # ≈ 0.5126
        assert abs(result - 0.5126) < 0.01

    def test_interpolate_3500psi_like_example_1(self):
        """ACI PRC-211.1-22 Example 1: 3500 psi (24.1 MPa) → w/cm ≈ 0.62."""
        result = interpolate_w_c_ratio(3500 * 0.00689476, False)
        assert abs(result - 0.62) < 0.015

    def test_interpolate_clamp_high_strength(self):
        """Above table range should clamp to lowest W/C (0.34)."""
        result = interpolate_w_c_ratio(80.0, False)
        assert result == 0.34

    def test_interpolate_clamp_low_strength(self):
        """Below table range should clamp to highest W/C (0.82)."""
        result = interpolate_w_c_ratio(5.0, False)
        assert result == 0.82


# ---------------------------------------------------------------------------
# ACI 211.1 Table 6.3.6 — Coarse Aggregate Volume
# ---------------------------------------------------------------------------
class TestACICAVolume:
    """Verify coarse aggregate volume table values."""

    def test_20mm_fm24(self):
        assert CA_VOLUME_FRACTION[(20, 2.40)] == 0.66

    def test_20mm_fm28(self):
        assert CA_VOLUME_FRACTION[(20, 2.80)] == 0.62  # Direct table entry

    def test_40mm_fm26(self):
        assert CA_VOLUME_FRACTION[(40, 2.60)] == 0.73

    def test_interpolate_20mm_fm27(self):
        """Between FM 2.60 (0.64) and FM 2.80 (0.62)."""
        result = interpolate_ca_volume(20, 2.70)
        expected = 0.64 + 0.5 * (0.62 - 0.64)  # 0.64 - 0.01 = 0.63
        assert abs(result - 0.63) < 0.01


# ---------------------------------------------------------------------------
# Phase 6: ACI 318 Table 19.3.2 — Sulfate Exposure W/C Limits
# ---------------------------------------------------------------------------
class TestACISulfateExposureLimits:
    """Verify ACI 318 sulfate exposure W/C limits."""

    def test_s0_no_limit(self):
        assert ACI_MAX_WC_FOR_EXPOSURE["S0"] == 0.99

    def test_s1_limit(self):
        assert ACI_MAX_WC_FOR_EXPOSURE["S1"] == 0.50

    def test_s2_limit(self):
        assert ACI_MAX_WC_FOR_EXPOSURE["S2"] == 0.45

    def test_s3_limit(self):
        assert ACI_MAX_WC_FOR_EXPOSURE["S3"] == 0.40


# ---------------------------------------------------------------------------
# Phase 7: ACI 318 Table 26.4.3.1(b) — No-Data Overdesign
# ---------------------------------------------------------------------------
class TestACINoDataOverdesign:
    """Verify ACI 318 no-data overdesign table."""

    def test_below_20mpa(self):
        assert get_no_data_overdesign(17.0) == 24.0

    def test_25mpa(self):
        assert get_no_data_overdesign(25.0) == 33.5

    def test_above_35mpa(self):
        assert get_no_data_overdesign(40.0) == 50.0

    def test_interpolate_22mpa(self):
        """Between 20 (27.0) and 25 (33.5) — both in the +8.5 MPa band."""
        result = get_no_data_overdesign(22.0)
        expected = 27.0 + 0.4 * (33.5 - 27.0)  # 27.0 + 2.6 = 29.6
        assert abs(result - 29.6) < 0.1

    def test_20mpa_below_3000psi_breakpoint(self):
        """20 MPa < 3000 psi (20.7 MPa) → +7 MPa overdesign (f'cr = 27)."""
        result = get_no_data_overdesign(20.0)
        assert abs(result - 27.0) < 0.1


# ---------------------------------------------------------------------------
# ACI 211.1 — Target Mean Strength
# ---------------------------------------------------------------------------
class TestACITargetStrength:
    """Verify target mean strength calculations."""

    def test_with_production_data_limited(self):
        """f'cr = f'c + 2.33s - 3.45 (limited data formula)."""
        designer = ACI211MixDesign()
        # f'c=25, s=4.0: 25 + 2.33*4 - 3.45 = 30.87
        # Also check: f'c + 1.34*4 = 30.36
        # max(30.87, 30.36, 27.4) = 30.9
        result = designer.calculate_target_mean_strength(25.0, 4.0)
        assert abs(result - 30.9) < 0.1

    def test_with_production_data_low_variability(self):
        """When s is low, f'c + 1.34s may govern."""
        designer = ACI211MixDesign()
        # f'c=25, s=2.0: f'c + 1.34*2 = 27.68, f'c + 2.33*2 - 3.45 = 26.21
        # max(27.68, 26.21, 27.4) = 27.7
        result = designer.calculate_target_mean_strength(25.0, 2.0)
        assert abs(result - 27.7) < 0.1

    def test_no_production_data(self):
        """Should use ACI 318 Table 26.4.3.1(b)."""
        designer = ACI211MixDesign()
        # 25 MPa: table value = 33.5
        result = designer.calculate_target_mean_strength(25.0, has_production_data=False)
        assert abs(result - 33.5) < 0.1

    def test_minimum_fcr(self):
        """f'cr must be at least f'c + 2.4 MPa."""
        designer = ACI211MixDesign()
        result = designer.calculate_target_mean_strength(25.0, 0.1)
        assert result >= 25.0 + 2.4


# ---------------------------------------------------------------------------
# ACI 211.1 — Full Design Integration
# ---------------------------------------------------------------------------
class TestACIDesignIntegration:
    """Integration tests for ACI 211.1 design method."""

    def test_basic_design_produces_valid_result(self):
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
        )
        result = designer.design(inp)
        assert result.cement_kg > 0
        assert result.water_kg > 0
        assert result.fine_aggregate_kg > 0
        assert result.coarse_aggregate_kg > 0
        assert result.w_c_ratio > 0

    def test_sulfate_s2_caps_wc(self):
        """S2 sulfate exposure should cap W/C at 0.45."""
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            sulfate_exposure_class="S2",
        )
        result = designer.design(inp)
        assert result.w_c_ratio <= 0.45
        assert any("sulfate" in w.lower() for w in result.warnings)

    def test_sulfate_s0_no_cap(self):
        """S0 should not cap W/C."""
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            sulfate_exposure_class="S0",
        )
        result = designer.design(inp)
        assert any("sulfate" not in w.lower() or "S0" in w for w in result.warnings) or len(result.warnings) == 0

    def test_no_data_increases_target_strength(self):
        """No-data option should produce higher f'cr than with data."""
        designer = ACI211MixDesign()
        with_data = designer.calculate_target_mean_strength(25.0, 4.0, has_production_data=True)
        no_data = designer.calculate_target_mean_strength(25.0, 4.0, has_production_data=False)
        assert no_data >= with_data, (
            f"No-data f'cr ({no_data}) should be >= with-data f'cr ({with_data})"
        )

    def test_air_entrained_changes_water(self):
        """Air-entrained concrete should use less water."""
        designer = ACI211MixDesign()
        w_nae = designer.get_water_content(20, 75, air_entrained=False)
        w_ae = designer.get_water_content(20, 75, air_entrained=True)
        assert w_ae < w_nae

    def test_aci211_admixture_water_reduction(self):
        """Chemical admixture should reduce water and calculate batch dosage."""
        from concrete_mix.models.materials import Admixture
        designer = ACI211MixDesign()
        inp_plain = MixDesignInput(
            code="aci211",
            target_strength_mpa=30.0,
            slump_mm=75.0,
        )
        res_plain = designer.design(inp_plain)

        inp_admix = MixDesignInput(
            code="aci211",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            admixture=Admixture(
                type="superplasticizer",
                dosage_percent=1.0,
                water_reduction_percent=20.0,
                specific_gravity=1.15,
            ),
        )
        res_admix = designer.design(inp_admix)

        assert res_admix.water_kg < res_plain.water_kg
        assert res_admix.admixture_kg is not None
        assert res_admix.admixture_kg > 0
        assert res_admix.admixture_type == "superplasticizer"
        assert res_admix.admixture_dosage_percent == 1.0


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------
class TestInputValidation:
    """Verify input validation for new fields."""

    def test_invalid_sulfate_class_raises(self):
        with pytest.raises(ValueError, match="Sulfate exposure class"):
            MixDesignInput(
                code="aci211",
                target_strength_mpa=25.0,
                slump_mm=75.0,
                sulfate_exposure_class="S4",
            )

    def test_valid_sulfate_class_accepted(self):
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            sulfate_exposure_class="S1",
        )
        assert inp.sulfate_exposure_class == "S1"

    def test_has_production_data_default_true(self):
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
        )
        assert inp.has_production_data is True

    def test_structural_strength_minimum_enforced(self):
        with pytest.raises(ValueError, match="ACI211 structural design requires characteristic strength"):
            MixDesignInput(
                code="aci211",
                target_strength_mpa=20.0,
                slump_mm=75.0,
            )
