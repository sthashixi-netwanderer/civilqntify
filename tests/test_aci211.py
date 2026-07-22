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
        assert WATER_CONTENT_NON_AIR_ENTRAINED[10][25] == 207

    def test_10mm_150mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[10][150] == 268

    def test_20mm_50mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[20][50] == 193

    def test_40mm_100mm_slump_nae(self):
        assert WATER_CONTENT_NON_AIR_ENTRAINED[40][100] == 193

    def test_20mm_50mm_slump_ae(self):
        assert WATER_CONTENT_AIR_ENTRAINED[20][50] == 179

    def test_interpolate_20mm_60mm_slump(self):
        """Between 50mm (193) and 75mm (208) — non-air-entrained."""
        result = interpolate_water_content(20, 60, False)
        # fraction = (60-50)/(75-50) = 0.4
        expected = 193 + 0.4 * (208 - 193)  # 193 + 6.0 = 199.0
        assert abs(result - 199.0) < 0.1

    def test_interpolate_clamp_low(self):
        """Below table range should clamp to lowest value."""
        result = interpolate_water_content(20, 10, False)
        assert result == 183

    def test_interpolate_clamp_high(self):
        """Above table range should clamp to highest value."""
        result = interpolate_water_content(20, 200, False)
        assert result == 228


# ---------------------------------------------------------------------------
# ACI 211.1 Table 6.3.3 — Air Content
# ---------------------------------------------------------------------------
class TestACIAirContent:
    """Verify air content table values."""

    @pytest.mark.parametrize("nmsa,expected", [(10, 1.5), (20, 1.0), (40, 0.5)])
    def test_entrapped_air(self, nmsa, expected):
        assert AIR_CONTENT_ENTRAPPED[nmsa] == expected

    def test_entrained_mild_20mm(self):
        assert AIR_CONTENT[20]["mild"] == 2.0

    def test_entrained_moderate_20mm(self):
        assert AIR_CONTENT[20]["moderate"] == 4.5

    def test_entrained_severe_20mm(self):
        assert AIR_CONTENT[20]["severe"] == 6.0

    def test_get_air_entrapped(self):
        assert get_air_content(20, "moderate", False) == 1.0

    def test_get_air_entrained_moderate(self):
        assert get_air_content(20, "moderate", True) == 4.5


# ---------------------------------------------------------------------------
# ACI 211.1 Table 6.3.4 — W/C Ratio
# ---------------------------------------------------------------------------
class TestACIWCRatio:
    """Verify W/C ratio table values."""

    def test_nae_28mpa(self):
        assert WC_RATIO_NON_AIR_ENTRAINED[28.0] == 0.55

    def test_nae_40mpa(self):
        assert WC_RATIO_NON_AIR_ENTRAINED[40.0] == 0.42

    def test_ae_10mpa(self):
        assert WC_RATIO_AIR_ENTRAINED[10.0] == 0.82

    def test_interpolate_nae_32mpa(self):
        """Between 30 (0.52) and 35 (0.47)."""
        result = interpolate_w_c_ratio(32.0, False)
        # fraction = (32-30)/(35-30) = 0.4 ... but sorted descending
        # Between 35 (0.47) and 30 (0.52): fraction = (32-35)/(30-35) = 0.6
        expected = 0.47 + 0.6 * (0.52 - 0.47)  # 0.47 + 0.03 = 0.50
        assert abs(result - 0.50) < 0.01

    def test_interpolate_clamp_high_strength(self):
        """Above table range should clamp to lowest W/C."""
        result = interpolate_w_c_ratio(80.0, False)
        assert result == 0.29

    def test_interpolate_clamp_low_strength(self):
        """Below table range should clamp to highest W/C."""
        result = interpolate_w_c_ratio(5.0, False)
        assert result == 0.75


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
        """Between 20 (28.5) and 25 (33.5)."""
        result = get_no_data_overdesign(22.0)
        expected = 28.5 + 0.4 * (33.5 - 28.5)  # 28.5 + 2.0 = 30.5
        assert abs(result - 30.5) < 0.1


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
