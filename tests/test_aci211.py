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
    WATER_CONTENT_AIR_ENTRAINED,
    WATER_CONTENT_NON_AIR_ENTRAINED,
    get_air_content,
    get_no_data_overdesign,
    interpolate_ca_volume,
    interpolate_w_c_ratio,
    interpolate_water_content,
    modification_factor_k,
)
from concrete_mix.models.materials import (
    Admixture,
    Cement,
    CoarseAggregate,
    FineAggregate,
    SCM,
    SCMType,
)
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
# Phase 7: ACI 318 Table 26.4.3.1(b) / PRC-211.1-22 Table 4.7.4.1 — No-Data
# Overdesign (exact piecewise psi rules)
# ---------------------------------------------------------------------------
class TestACINoDataOverdesign:
    """Verify the exact Table 4.7.4.1 required-average formulas."""

    def test_below_3000psi(self):
        """f'c < 3000 psi → +1000 psi: 17.0 MPa + 6.895 = 23.90."""
        assert abs(get_no_data_overdesign(17.0) - 23.90) < 0.01

    def test_3000_5000_band(self):
        """3000–5000 psi → +1200 psi: 25.0 + 8.274 = 33.27."""
        assert abs(get_no_data_overdesign(25.0) - 33.27) < 0.01

    def test_above_5000psi(self):
        """f'c > 5000 psi → 1.10·f'c + 700 psi: 40.0 → 48.83."""
        assert abs(get_no_data_overdesign(40.0) - 48.83) < 0.01

    def test_interpolate_within_band_is_exact(self):
        """Within a band the increment tracks f'c exactly — no curve fitting."""
        # 21 and 23 MPa both sit in the 3000–5000 psi band (+1200 psi each);
        # 2 MPa apart in, 2 MPa apart out.
        assert get_no_data_overdesign(23.0) - get_no_data_overdesign(21.0) == 2.00

    def test_20mpa_below_3000psi_breakpoint(self):
        """20 MPa < 3000 psi (20.68 MPa) → +1000 psi (6.895 MPa)."""
        assert abs(get_no_data_overdesign(20.0) - 26.89) < 0.01

    def test_design_ceils_to_whole_mpa(self):
        """App policy: f'cr ceils to whole MPa (17.24 → 24.13 → 25)."""
        designer = ACI211MixDesign()
        assert abs(designer.calculate_target_mean_strength(
            17.24, has_production_data=False) - 25) < 0.01


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 Table 4.7.4.3 — k modification for 15–29 tests
# ---------------------------------------------------------------------------
class TestACIKFactor:
    def test_tabulated_values(self):
        assert modification_factor_k(15) == 1.16
        assert modification_factor_k(20) == 1.08
        assert modification_factor_k(25) == 1.03

    def test_thirty_or_more_is_one(self):
        assert modification_factor_k(30) == 1.00
        assert modification_factor_k(60) == 1.00

    def test_intermediate_interpolated(self):
        """Table note: linear interpolation for intermediate n is acceptable."""
        assert abs(modification_factor_k(27) - 1.018) < 1e-9

    def test_below_fifteen_rejected(self):
        with pytest.raises(ValueError, match="at least 15"):
            modification_factor_k(10)

    def test_n20_lifts_target(self):
        """k = 1.08 raises f'cr vs unmodified s (Table 4.7.4.4 with ks)."""
        designer = ACI211MixDesign()
        fcr_k = designer.calculate_target_mean_strength(
            25.0, 4.0, num_tests=20)
        fcr_plain = designer.calculate_target_mean_strength(25.0, 4.0)
        assert fcr_k > fcr_plain

    def test_over_5000psi_uses_090_branch(self):
        """Table 4.7.4.4's f'c > 5000 psi row: max(f'c+1.34ks, 0.90f'c+2.33ks).

        The 0.90 branch governs once 0.99·k·s > 0.10·f'c — at f'c = 60 and
        s = 8 it lifts f'cr above the 1.34 branch (70.72), and above the
        ≤5000-psi row's −500 psi term it would have produced.
        """
        designer = ACI211MixDesign()
        # max(60 + 1.34×8, 0.90×60 + 2.33×8) = max(70.72, 72.64) = 72.64 → 73
        # (up to whole MPa, app policy)
        assert designer.calculate_target_mean_strength(60.0, 8.0) == 73


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
        # max(30.87, 30.36, 27.4) = 30.87 → 31 (up to whole MPa, app policy)
        result = designer.calculate_target_mean_strength(25.0, 4.0)
        assert abs(result - 31) < 0.01

    def test_with_production_data_low_variability(self):
        """When s is low, f'c + 1.34s may govern."""
        designer = ACI211MixDesign()
        # f'c=25, s=2.0: f'c + 1.34*2 = 27.68, f'c + 2.33*2 - 3.45 = 26.21
        # max(27.68, 26.21, 27.4) = 27.68 → 28 (up to whole MPa, app policy)
        result = designer.calculate_target_mean_strength(25.0, 2.0)
        assert abs(result - 28) < 0.01

    def test_no_production_data(self):
        """Should use ACI 318 Table 26.4.3.1(b)."""
        designer = ACI211MixDesign()
        # 25 MPa: table value = 33.27 → 34 (up to whole MPa, app policy)
        result = designer.calculate_target_mean_strength(25.0, has_production_data=False)
        assert abs(result - 34) < 0.1

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
        """S2 sulfate exposure should cap W/C at 0.45 (4500 psi class)."""
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=35.0,
            slump_mm=75.0,
            sulfate_exposure_class="S2",
        )
        result = designer.design(inp)
        assert result.w_c_ratio <= 0.45
        assert any("sulfate" in w.lower() for w in result.warnings)

    def test_sulfate_s2_blocks_below_4500psi(self):
        """S2 below 31.0 MPa (4500 psi) fails fast (Table 4.7.3a)."""
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            sulfate_exposure_class="S2",
        )
        with pytest.raises(ValueError, match="minimum 31.0 MPa"):
            designer.design(inp)

    def test_sulfate_s1_s3_floors(self):
        """S1 blocks below 27.6 MPa (4000 psi); S3 below 34.5 (5000 psi)."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="minimum 27.6 MPa"):
            designer.design(MixDesignInput(
                code="aci211", target_strength_mpa=25.0, slump_mm=75.0,
                sulfate_exposure_class="S1"))
        with pytest.raises(ValueError, match="minimum 34.5 MPa"):
            designer.design(MixDesignInput(
                code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
                sulfate_exposure_class="S3"))

    def test_sulfate_cement_guidance_surfaced(self):
        """S1–S3 designs carry the Table 4.7.3a cement-type guidance."""
        designer = ACI211MixDesign()
        result = designer.design(MixDesignInput(
            code="aci211", target_strength_mpa=35.0, slump_mm=75.0,
            sulfate_exposure_class="S2"))
        assert any("Type V" in w for w in result.warnings)

    def test_air_above_6000psi_flags_table_note_1(self):
        """Air-entrained f'cr above 41.4 MPa reads w/cm < 0.33 —
        Table 5.3.4 Note 1 must be surfaced, not silent."""
        designer = ACI211MixDesign()
        result = designer.design(MixDesignInput(
            code="aci211", target_strength_mpa=45.0, slump_mm=75.0,
            air_entrained=True))
        assert any("Table 5.3.4 Note 1" in w for w in result.warnings)

    def test_air_at_6000psi_no_note_1(self):
        """At exactly the 6000 psi row (0.33 tabulated) no flag is raised."""
        designer = ACI211MixDesign()
        result = designer.design(MixDesignInput(
            code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
            air_entrained=True))
        assert not any("Note 1" in w for w in result.warnings)

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

    def test_no_app_floor_m20_designs(self):
        """No 25 MPa floor: M20 ACI designs (exposure minima still apply)."""
        designer = ACI211MixDesign()
        result = designer.design(MixDesignInput(
            code="aci211",
            target_strength_mpa=20.0,
            slump_mm=75.0,
        ))
        assert result.target_mean_strength_mpa > 20.0

    def test_sanity_floor_still_guards(self):
        with pytest.raises(ValueError, match=r"\[5, 100\]"):
            MixDesignInput(
                code="aci211",
                target_strength_mpa=4.0,
                slump_mm=75.0,
            )


# ---------------------------------------------------------------------------
# ACI 301 Table 4.2.2.6(c) — Freezing-and-thawing exposure (gap-audit Phase 2)
# ---------------------------------------------------------------------------
class TestACIFreezingExposure:
    """F-class durability: air entrainment, w/c caps, min strength, F3 SCM caps."""

    def _inp(self, f_class, strength=35.0, air=True, scms=(), **kw):
        return MixDesignInput(
            code="aci211",
            target_strength_mpa=strength,
            slump_mm=75.0,
            air_entrained=air,
            freezing_exposure_class=f_class,
            scms=scms,
            **kw,
        )

    def test_f0_default_legacy_path(self):
        """F0 keeps the legacy Table 5.3.3 air path (20 mm, air-entrained → 5.0%)."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp("F0"))
        assert result.air_volume_percent == 5.0
        assert not any("4.2.2.6(c)" in s.clause_ref for s in result.steps)

    def test_f1_requires_air_entrainment(self):
        """F1 without air entrainment is non-compliant → hard error."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="requires air-entrained"):
            designer.design(self._inp("F1", air=False))

    def test_f1_air_from_table(self):
        """20 mm F1 air-entrained → 5.0% per Table 4.7.3.1."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp("F1"))
        assert result.air_volume_percent == 5.0
        step4 = next(s for s in result.steps if s.step_number == 4)
        assert "F1" in step4.clause_ref

    def test_f3_air_from_table(self):
        """20 mm F3 air-entrained → 6.0% per Table 4.7.3.1."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp("F3"))
        assert result.air_volume_percent == 6.0

    def test_f2_min_strength_blocks_m25(self):
        """M25 < 31.0 MPa minimum for F2 (Table 4.7.3b) → hard error."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="minimum 31.0 MPa"):
            designer.design(self._inp("F2", strength=25.0))

    def test_f3_min_strength_blocks_m30(self):
        """M30 < 34.5 MPa minimum for F3 → hard error."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="minimum 34.5 MPa"):
            designer.design(self._inp("F3", strength=30.0))

    def test_f1_wc_cap_governs(self):
        """F1 caps a manual 0.60 w/c at 0.55 (lowest-governs, §4.7.1)."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp("F1", strength=25.0, w_c_ratio=0.60))
        assert result.w_c_ratio == 0.55
        assert any("F1" in w and "0.55" in w for w in result.warnings)

    def test_f3_scm_fly_ash_over_cap_blocked(self):
        """30% fly ash in F3 exceeds the 25% cap (Table 4.2.1.1(b))."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="F3"):
            designer.design(
                self._inp(
                    "F3",
                    scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=30.0),),
                )
            )

    def test_f3_scm_within_caps_passes(self):
        """20% fly ash in F3 is within all Table 4.2.1.1(b) caps."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        result = designer.design(
            self._inp(
                "F3",
                scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=20.0),),
            )
        )
        assert result.scm_kg > 0

    def test_f3_silica_fume_over_cap_blocked(self):
        """12% silica fume in F3 exceeds the 10% cap."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="Silica fume"):
            designer.design(
                self._inp(
                    "F3",
                    scms=(SCM(type=SCMType.SILICA_FUME, replacement_percent=12.0),),
                )
            )

    def test_high_strength_frost_notes_air_footnote(self):
        """At ≥34.5 MPa the 1.0-point air footnote is surfaced, not applied."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp("F2", strength=40.0))
        assert result.air_volume_percent == 6.0
        assert any("1.0-point" in w for w in result.warnings)

    def test_invalid_f_class_rejected(self):
        with pytest.raises(ValueError, match="Freezing exposure class"):
            MixDesignInput(
                code="aci211",
                target_strength_mpa=30.0,
                slump_mm=75.0,
                freezing_exposure_class="F4",
            )


# ---------------------------------------------------------------------------
# ACI Table 5.3.3.1 — water-content adjustments (PRC-211.1-22 §5.3.3.1)
# ---------------------------------------------------------------------------
class TestACIWaterAdjustments531:
    """Temperature, manufactured sand, SCM rates, WRA minima, helper math."""

    def _inp(self, **kw):
        base = dict(code="aci211", target_strength_mpa=30.0, slump_mm=75.0)
        base.update(kw)
        return MixDesignInput(**base)

    def test_baseline_no_adjustment_step(self):
        """22.5 °C, natural sand, no SCM → no 3.1 step (legacy identical)."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp())
        assert not any(s.step_number == 3.1 for s in result.steps)

    def test_hot_weather_increases_water(self):
        """35 °C → +2%/10 °F over baseline: (35−22.5)×9/5/10×2 = +4.5%."""
        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        hot = designer.design(self._inp(concrete_temp_c=35.0)).water_kg
        assert abs(hot - base * 1.045) < 0.6
        hot_steps = [s for s in designer.design(
            self._inp(concrete_temp_c=35.0)).steps if s.step_number == 3.1]
        assert len(hot_steps) == 1 and "Table 5.3.3.1" in hot_steps[0].clause_ref

    def test_cold_weather_decreases_water(self):
        """10 °C → (10−22.5)×9/5/10×2 = −4.5%."""
        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        cold = designer.design(self._inp(concrete_temp_c=10.0)).water_kg
        assert abs(cold - base * 0.955) < 0.6

    def test_manufactured_sand_adds_five_percent(self):
        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        mfg = designer.design(self._inp(manufactured_sand=True)).water_kg
        assert abs(mfg - base * 1.05) < 0.6

    def test_fly_ash_reduces_water(self):
        """20% fly ash → −3%/10% = −6% mixing water."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        fa = designer.design(
            self._inp(scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=20.0),))
        ).water_kg
        assert abs(fa - base * 0.94) < 0.8

    def test_slag_reduces_water(self):
        """30% slag → −5%/10% = −15% mixing water."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        slag = designer.design(
            self._inp(scms=(SCM(type=SCMType.GGBFS, replacement_percent=30.0),))
        ).water_kg
        assert abs(slag - base * 0.85) < 1.0

    def test_silica_fume_is_guidance_only(self):
        """Silica fume warns (no table rate) without changing water."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = ACI211MixDesign()
        base = designer.design(self._inp()).water_kg
        sf = designer.design(
            self._inp(scms=(SCM(type=SCMType.SILICA_FUME, replacement_percent=7.0),))
        )
        assert abs(sf.water_kg - base) < 0.6
        assert any("Silica fume" in w for w in sf.warnings)

    def test_wra_below_minimum_warns(self):
        """Conventional WRA at 3% (< 5% floor, §4.7.6) warns."""
        from concrete_mix.models.materials import Admixture

        designer = ACI211MixDesign()
        result = designer.design(
            self._inp(admixture=Admixture(
                type="water_reducer", dosage_percent=0.4,
                water_reduction_percent=3.0))
        )
        assert any("at least 5%" in w for w in result.warnings)

    def test_hrwra_below_minimum_warns(self):
        """HRWRA at 8% (< 12% floor, §4.7.6) warns."""
        from concrete_mix.models.materials import Admixture

        designer = ACI211MixDesign()
        result = designer.design(
            self._inp(admixture=Admixture(
                type="superplasticizer", dosage_percent=1.0,
                water_reduction_percent=8.0))
        )
        assert any("at least 12%" in w for w in result.warnings)

    def test_helper_math(self):
        from concrete_mix.codes.tables.aci_tables import water_adjustment_531

        pct, applied = water_adjustment_531(
            rounded_aggregate=True, air_delta_pct=1.0, slump_delta_in=1.0)
        assert abs(pct - (-8.0 - 3.0 + 3.0)) < 1e-9
        assert len(applied) == 3
        pct0, applied0 = water_adjustment_531(temp_c=22.5)
        assert pct0 == 0.0 and applied0 == []

    def test_invalid_temp_rejected(self):
        with pytest.raises(ValueError, match="outside valid range"):
            MixDesignInput(code="aci211", target_strength_mpa=30.0,
                           slump_mm=75.0, concrete_temp_c=80.0)
# ---------------------------------------------------------------------------
# ACI §4.7.9 / §5.3.10 — yield basis, trial adjustments, prestressed scope
# ---------------------------------------------------------------------------
class TestACITrialAdjustments:
    """Theoretical density step, Ry check, water/air/strength re-estimates."""

    def _inp(self, **kw):
        base = dict(code="aci211", target_strength_mpa=30.0, slump_mm=75.0)
        base.update(kw)
        return MixDesignInput(**base)

    def test_theoretical_density_step_always_present(self):
        """Every ACI design reports its theoretical fresh density (§4.7.9)."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp())
        step10 = [s for s in result.steps if s.step_number == 10]
        assert len(step10) == 1
        assert "C138" in step10[0].clause_ref
        assert step10[0].result > 2200.0  # normal-density concrete

    def test_no_trial_inputs_no_adjustment_steps(self):
        """Without trial data there are no 10.x adjustment steps."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp())
        assert not any(isinstance(s.step_number, float)
                       and 10.0 < s.step_number < 11.0 for s in result.steps)

    def test_yield_in_tolerance(self):
        """Measured density matching theory → Ry ≈ 1.00, no warning."""
        designer = ACI211MixDesign()
        plain = designer.design(self._inp())
        theo = next(s for s in plain.steps if s.step_number == 10).result
        result = designer.design(self._inp(trial_density_kg_m3=theo))
        s101 = next(s for s in result.steps if s.step_number == 10.1)
        assert abs(s101.inputs["relative_yield"] - 1.0) < 0.01
        assert not any("relative yield" in w for w in result.warnings)

    def test_yield_out_of_tolerance_warns(self):
        """3% over-yield → Ry ≈ 1.03 with a tolerance warning."""
        designer = ACI211MixDesign()
        plain = designer.design(self._inp())
        theo = next(s for s in plain.steps if s.step_number == 10).result
        result = designer.design(self._inp(trial_density_kg_m3=theo / 1.03))
        assert any("0.98–1.02" in w for w in result.warnings)

    def test_slump_correction_math(self):
        """25.4 mm low slump → +5.93 kg/m³ on the yield-corrected water."""
        designer = ACI211MixDesign()
        plain = designer.design(self._inp())
        theo = next(s for s in plain.steps if s.step_number == 10).result
        result = designer.design(self._inp(
            trial_density_kg_m3=theo, trial_slump_mm=75.0 - 25.4))
        s102 = next(s for s in result.steps if s.step_number == 10.2)
        assert abs(s102.inputs["slump_correction"] - 5.93) < 0.05

    def test_air_correction_needs_air_entrained(self):
        """1% low air → +2.97 kg/m³; ignored for non-air designs."""
        designer = ACI211MixDesign()
        air = designer.design(self._inp(air_entrained=True))
        air_pct = air.air_volume_percent
        r = designer.design(self._inp(air_entrained=True,
                                      trial_air_pct=air_pct - 1.0))
        s103 = next(s for s in r.steps if s.step_number == 10.3)
        assert abs(s103.inputs["water_correction"] - 2.97) < 0.05
        plain = designer.design(self._inp(trial_air_pct=1.0))
        assert not any(s.step_number == 10.3 for s in plain.steps)

    def test_strength_efficiency_recommendation(self):
        """Trial 5 MPa low → positive cement delta at constant w/c."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(trial_strength_mpa=25.0))
        s104 = next(s for s in result.steps if s.step_number == 10.4)
        assert s104.result > 0  # add cement
        assert any("second trial" in w for w in result.warnings)

    def test_prestressed_chloride_guidance(self):
        """Prestressed C1 cites 0.06%, not the 0.30% non-prestressed cap."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(corrosion_exposure_class="C1",
                                           prestressed=True))
        assert any("0.06%" in w and "PRESTRESSED" in w for w in result.warnings)
        assert not any("0.30%" in w for w in result.warnings)
# ---------------------------------------------------------------------------
# ACI 318 26.4.2.1(a)(5) — NMSA structural-dimension limits
# ---------------------------------------------------------------------------
class TestACINMSALimits:
    """NMSA vs form width / slab depth / bar spacing (PRC-211.1-22 §4.3.2)."""

    def _inp(self, nmsa=20, **kw):
        from concrete_mix.models.materials import CoarseAggregate

        return MixDesignInput(
            code="aci211",
            target_strength_mpa=30.0,
            slump_mm=75.0,
            coarse_aggregate=CoarseAggregate(nominal_max_size_mm=nmsa),
            **kw,
        )

    def test_no_dimensions_no_check(self):
        """Legacy designs without dimensions are unaffected."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp())
        assert result.coarse_aggregate_kg > 0

    def test_form_width_violation(self):
        """20 mm > 90/5 = 18 mm → blocked with the governing limit cited."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="1/5.*90"):
            designer.design(self._inp(form_width_mm=90.0))

    def test_form_width_boundary_passes(self):
        """20 mm = 100/5 exactly → compliant (limit is 'exceed')."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(form_width_mm=100.0))
        assert result.coarse_aggregate_kg > 0

    def test_slab_depth_violation(self):
        """20 mm > 50/3 ≈ 16.7 mm → blocked."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="1/3.*50"):
            designer.design(self._inp(slab_depth_mm=50.0))

    def test_bar_spacing_violation(self):
        """20 mm > 25×3/4 = 18.75 mm → blocked."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="3/4.*25"):
            designer.design(self._inp(bar_spacing_mm=25.0))

    def test_bar_spacing_boundary_passes(self):
        """40 mm vs 60 mm spacing → max 45 mm → compliant."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(nmsa=40, bar_spacing_mm=60.0))
        assert result.coarse_aggregate_kg > 0

    def test_multiple_violations_reported(self):
        """All breached limits are listed, not just the first."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError) as exc:
            designer.design(
                self._inp(form_width_mm=50.0, slab_depth_mm=30.0)
            )
        msg = str(exc.value)
        assert "1/5" in msg and "1/3" in msg

    def test_nonpositive_dimension_rejected(self):
        with pytest.raises(ValueError, match="must be positive"):
            MixDesignInput(
                code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
                form_width_mm=0.0,
            )

    def test_simple_api_passthrough(self):
        """design_mix_simple accepts dimensions and enforces them."""
        from concrete_mix import design_mix_simple

        with pytest.raises(ValueError, match="26.4.2.1"):
            design_mix_simple(
                code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
                nmsa=20, form_width_mm=80.0,
            )
# ---------------------------------------------------------------------------
# ACI 301 Tables 4.2.2.6(d)/(e) — Water-contact and corrosion exposure
# ---------------------------------------------------------------------------
class TestACIWaterCorrosionExposure:
    """W-class permeability and C-class (non-prestressed) chloride protection."""

    def _inp(self, strength=35.0, w="W0", c="C0", **kw):
        return MixDesignInput(
            code="aci211",
            target_strength_mpa=strength,
            slump_mm=75.0,
            water_exposure_class=w,
            corrosion_exposure_class=c,
            **kw,
        )

    def test_defaults_add_no_noise(self):
        """W0/C0 designs gain no new warnings — legacy outputs unchanged."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp())
        assert not any("Water exposure" in w for w in result.warnings)
        assert not any("Corrosion exposure" in w for w in result.warnings)

    def test_w2_min_strength_blocks_m25(self):
        """M25 < 27.6 MPa minimum for W2 water-barrier elements."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="minimum 27.6 MPa"):
            designer.design(self._inp(strength=25.0, w="W2"))

    def test_w2_wc_cap_governs(self):
        """W2 caps a manual 0.60 w/c at 0.50 (lowest-governs, §4.7.1)."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(strength=30.0, w="W2", w_c_ratio=0.60))
        assert result.w_c_ratio == 0.50
        assert any("W2" in w and "0.50" in w for w in result.warnings)

    def test_w1_is_guidance_only(self):
        """W1 has no numeric cap — design succeeds with a practice note."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(w="W1"))
        assert result.w_c_ratio > 0
        assert any("4.2.2.6(a)" in w for w in result.warnings)

    def test_c2_min_strength_blocks_m30(self):
        """M30 < 34.5 MPa minimum for C2 external chlorides."""
        designer = ACI211MixDesign()
        with pytest.raises(ValueError, match="minimum 34.5 MPa"):
            designer.design(self._inp(strength=30.0, c="C2"))

    def test_c2_wc_cap_governs(self):
        """C2 caps a manual 0.60 w/c at 0.40."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(c="C2", w_c_ratio=0.60))
        assert result.w_c_ratio == 0.40
        assert any("C2" in w and "0.40" in w for w in result.warnings)

    def test_c1_chloride_guidance(self):
        """C1 surfaces the 0.30% chloride cap for constituent verification."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(c="C1"))
        assert any("0.30%" in w for w in result.warnings)

    def test_c2_chloride_guidance(self):
        """C2 surfaces the 0.15% chloride cap alongside the enforced numbers."""
        designer = ACI211MixDesign()
        result = designer.design(self._inp(c="C2"))
        assert any("0.15%" in w for w in result.warnings)

    def test_combined_lowest_governs(self):
        """F2 (0.45) + C2 (0.40) + manual 0.60 → 0.40 wins."""
        designer = ACI211MixDesign()
        result = designer.design(
            self._inp(c="C2", w_c_ratio=0.60, freezing_exposure_class="F2",
                      air_entrained=True)
        )
        assert result.w_c_ratio == 0.40

    def test_invalid_classes_rejected(self):
        with pytest.raises(ValueError, match="Water exposure class"):
            MixDesignInput(
                code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
                water_exposure_class="W3",
            )
        with pytest.raises(ValueError, match="Corrosion exposure class"):
            MixDesignInput(
                code="aci211", target_strength_mpa=30.0, slump_mm=75.0,
                corrosion_exposure_class="C3",
            )


# ---------------------------------------------------------------------------
# ACI §5.3.3.1 + §6.3 — additive water ledger (Example 2 semantics)
# ---------------------------------------------------------------------------
class TestACIWaterLedger:
    """Table 5.3.3.1 rows and the WRA reduction are percentages of the SAME
    Table 5.3.3 base, subtracted additively — Example 2 (§9.3.3):
    280 − 14 (WRA) − 17 (fly ash) − 22 (rounded) = 227 lb/yd³."""

    def _design(self, **kw):
        from concrete_mix.models.materials import SCM, SCMType, Admixture

        base = dict(code="aci211", target_strength_mpa=30.0, slump_mm=75.0)
        base.update(kw)
        return ACI211MixDesign().design(MixDesignInput(**base))

    def test_admixture_and_fly_ash_compound_additively(self):
        """20% fly ash (−6%) + WRA (−5%) → base × 0.89, not base × 0.95."""
        base = self._design().water_kg
        both = self._design(
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=20.0),),
            admixture=Admixture(
                type="superplasticizer", dosage_percent=1.0,
                water_reduction_percent=5.0, specific_gravity=1.15),
        ).water_kg
        assert abs(both - base * 0.89) < 0.6
        # The pre-fix bug returned base × 0.95 (fly-ash cut discarded).
        assert abs(both - base * 0.95) > 3.0

    def test_step_31_records_combined_adjustments(self):
        result = self._design(
            admixture=Admixture(
                type="superplasticizer", dosage_percent=1.0,
                water_reduction_percent=5.0, specific_gravity=1.15))
        s31 = next(s for s in result.steps if s.step_number == 3.1)
        assert s31.inputs["admixture_reduction_pct"] == 5.0
        assert "§6.3" in s31.clause_ref

    def test_rounded_aggregate_surfaces_guidance(self):
        """Rounded −8% is a Table 5.3.3.1 clause surfaced, not auto-applied
        (Example 1 keeps tabulated water; Example 2 applies the cut)."""
        from concrete_mix.models.materials import AggregateShape, CoarseAggregate

        result = self._design(
            coarse_aggregate=CoarseAggregate(
                shape=AggregateShape.ROUNDED_GRAVEL))
        assert any("Rounded coarse aggregate" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# ACI §9.5 Example 4 — target paste volume
# ---------------------------------------------------------------------------
class TestACIPasteVolume:
    def test_example4_formula_reproduces_288lb_cement(self):
        """Example 4: PV 25%, w/cm 0.40, 50% slag (RD 2.90) → 288 lb/yd³
        cement = 170.9 kg/m³."""
        from concrete_mix.codes.tables.aci_tables import (
            cementitious_for_target_paste_volume)

        cement, scm, water = cementitious_for_target_paste_volume(
            25.0, 0.40, 0.5, 3.15, 2.90)
        assert abs(cement - 170.9) < 0.5   # 288 lb/yd³ × 0.5933
        assert abs(scm - 170.9) < 0.5      # 50% of cementitious
        assert abs(water - 136.7) < 0.5    # 0.40 × 341.8 = 230 lb/yd³

    def test_design_hits_target_and_rebalances_aggregates(self):
        designer = ACI211MixDesign()
        inp = MixDesignInput(
            code="aci211", target_strength_mpa=35.0, slump_mm=75.0,
            target_paste_volume_pct=30.0)
        result = designer.design(inp)
        s82 = next(s for s in result.steps if s.step_number == 8.2)
        assert abs(s82.result - 30.0) < 0.2
        # Water follows w/cm × cementitious.
        assert abs(result.water_kg - result.w_c_ratio
                   * (result.cement_kg + result.scm_kg)) < 1.0
        # Aggregates were rebalanced (step 8 masses recomputed).
        assert result.coarse_aggregate_kg > 0 and result.fine_aggregate_kg > 0
        assert any("HRWRA" in w for w in result.warnings)

    def test_paste_volume_always_reported(self):
        result = ACI211MixDesign().design(
            MixDesignInput(code="aci211", target_strength_mpa=30.0,
                           slump_mm=75.0))
        s81 = next(s for s in result.steps if s.step_number == 8.1)
        assert 0 < s81.result < 100

    def test_out_of_range_target_rejected(self):
        with pytest.raises(ValueError, match="Target paste volume"):
            MixDesignInput(code="aci211", target_strength_mpa=30.0,
                           slump_mm=75.0, target_paste_volume_pct=10.0)


# ---------------------------------------------------------------------------
# ACI Table 4.7.3b — F3 plain-concrete row
# ---------------------------------------------------------------------------
class TestACIF3PlainRow:
    def _design(self, concrete_type):
        return ACI211MixDesign().design(MixDesignInput(
            code="aci211", target_strength_mpa=32.0, slump_mm=75.0,
            air_entrained=True, freezing_exposure_class="F3",
            concrete_type=concrete_type))

    def test_plain_f3_allows_m32(self):
        """Plain F3 row (0.45 / 4500 psi) admits M32; reinforced F3 blocks it."""
        result = self._design("plain")
        assert result.w_c_ratio <= 0.45
        with pytest.raises(ValueError, match="minimum 34.5"):
            self._design("reinforced")

    def test_plain_f3_min_strength_still_enforced(self):
        with pytest.raises(ValueError, match="plain concrete row"):
            ACI211MixDesign().design(MixDesignInput(
                code="aci211", target_strength_mpa=25.0, slump_mm=75.0,
                air_entrained=True, freezing_exposure_class="F3",
                concrete_type="plain"))


# ---------------------------------------------------------------------------
# ACI Appendix B — high-density concrete guidance
# ---------------------------------------------------------------------------
class TestACIHighDensityGuidance:
    def test_dense_aggregates_surface_appendix_b(self):
        """A batch mass ≥ 180 lb/ft³ (2885 kg/m³) triggers the B.3/B.4 notes."""
        from concrete_mix.models.materials import CoarseAggregate, FineAggregate

        result = ACI211MixDesign().design(MixDesignInput(
            code="aci211", target_strength_mpa=35.0, slump_mm=75.0,
            fine_aggregate=FineAggregate(specific_gravity=3.1),
            coarse_aggregate=CoarseAggregate(
                specific_gravity=3.1, bulk_density_kg_m3=2100.0)))
        assert result.coarse_aggregate_kg > 0
        assert any("Appendix B" in w for w in result.warnings)

    def test_normal_density_stays_quiet(self):
        result = ACI211MixDesign().design(
            MixDesignInput(code="aci211", target_strength_mpa=30.0,
                           slump_mm=75.0))
        assert not any("Appendix B" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# ACI num_strength_tests input plumbing
# ---------------------------------------------------------------------------
class TestACINumTestsInput:
    def test_invalid_n_rejected(self):
        with pytest.raises(ValueError, match="at least 15"):
            MixDesignInput(code="aci211", target_strength_mpa=30.0,
                           slump_mm=75.0, num_strength_tests=10)

    def test_n15_applies_k(self):
        """n = 15 → k = 1.16 lifts f'cr above the unmodified value.
        (n = 29's k ≈ 1.006 lifts f'cr by only ~0.06 MPa, which whole-MPa
        rounding absorbs — a known, accepted effect of the ceil policy.)"""
        designer = ACI211MixDesign()
        with_k = designer.calculate_target_mean_strength(
            30.0, 4.0, num_tests=15)
        without = designer.calculate_target_mean_strength(30.0, 4.0)
        assert with_k > without
