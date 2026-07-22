"""Tests for BRE/DOE (Teychenné et al. 1997) concrete mix design method compliance.

Verifies that all table values, curve-fits, and worked examples match the published standard.
"""

import pytest

from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.tables.doe_tables import (
    get_free_water_content,
    get_fine_aggregate_proportion,
    get_k_value,
    get_reference_strength,
    get_standard_deviation,
    get_wet_density,
    wc_ratio_from_strength,
)
from concrete_mix.models.materials import SCM, Cement, CoarseAggregate, FineAggregate, AggregateShape, CementType
from concrete_mix.models.mix_input import MixDesignInput


# ---------------------------------------------------------------------------
# Stage 1 — Reference Compressive Strength (Table 2)
# ---------------------------------------------------------------------------
class TestDOETable2ReferenceStrength:
    """Verify Table 2 reference strength values."""

    def test_class_42_5_uncrushed(self):
        assert get_reference_strength("42.5", "uncrushed", 3) == 22.0
        assert get_reference_strength("42.5", "uncrushed", 7) == 30.0
        assert get_reference_strength("42.5", "uncrushed", 28) == 42.0
        assert get_reference_strength("42.5", "uncrushed", 91) == 49.0

    def test_class_42_5_crushed(self):
        assert get_reference_strength("42.5", "crushed", 3) == 27.0
        assert get_reference_strength("42.5", "crushed", 7) == 36.0
        assert get_reference_strength("42.5", "crushed", 28) == 49.0
        assert get_reference_strength("42.5", "crushed", 91) == 56.0

    def test_class_52_5_uncrushed(self):
        assert get_reference_strength("52.5", "uncrushed", 3) == 29.0
        assert get_reference_strength("52.5", "uncrushed", 7) == 37.0
        assert get_reference_strength("52.5", "uncrushed", 28) == 48.0
        assert get_reference_strength("52.5", "uncrushed", 91) == 54.0

    def test_class_52_5_crushed(self):
        assert get_reference_strength("52.5", "crushed", 3) == 34.0
        assert get_reference_strength("52.5", "crushed", 7) == 43.0
        assert get_reference_strength("52.5", "crushed", 28) == 55.0
        assert get_reference_strength("52.5", "crushed", 91) == 61.0


# ---------------------------------------------------------------------------
# Stage 2 — Free-Water Content (Table 3)
# ---------------------------------------------------------------------------
class TestDOETable3FreeWater:
    """Verify Table 3 free-water content values."""

    def test_10mm_uncrushed(self):
        assert get_free_water_content(10, "uncrushed", slump_mm=5.0) == 150.0   # 0-10mm
        assert get_free_water_content(10, "uncrushed", slump_mm=20.0) == 180.0  # 10-30mm
        assert get_free_water_content(10, "uncrushed", slump_mm=45.0) == 205.0  # 30-60mm
        assert get_free_water_content(10, "uncrushed", slump_mm=100.0) == 225.0 # 60-180mm

    def test_20mm_crushed(self):
        assert get_free_water_content(20, "crushed", slump_mm=5.0) == 170.0
        assert get_free_water_content(20, "crushed", slump_mm=20.0) == 190.0
        assert get_free_water_content(20, "crushed", slump_mm=45.0) == 210.0
        assert get_free_water_content(20, "crushed", slump_mm=100.0) == 225.0


# ---------------------------------------------------------------------------
# Figure 3 — Standard Deviation & Margin
# ---------------------------------------------------------------------------
class TestDOEMarginAndDeviation:
    """Verify standard deviation and defective k-values."""

    def test_std_dev_plateau_line_a(self):
        """Line A (<20 results) plateau at 8.0 MPa for fc >= 20."""
        assert get_standard_deviation(20.0, has_production_data=False) == 8.0
        assert get_standard_deviation(30.0, has_production_data=False) == 8.0

    def test_std_dev_sloping_line_a(self):
        """Line A slopes down to origin below 20 MPa."""
        assert get_standard_deviation(10.0, has_production_data=False) == 4.0

    def test_std_dev_plateau_line_b(self):
        """Line B (>=20 results) plateau at 4.0 MPa for fc >= 20."""
        assert get_standard_deviation(20.0, has_production_data=True) == 4.0
        assert get_standard_deviation(35.0, has_production_data=True) == 4.0

    def test_std_dev_sloping_line_b(self):
        """Line B slopes down below 20 MPa."""
        assert get_standard_deviation(10.0, has_production_data=True) == 2.0

    def test_k_values_defectives(self):
        """Verify k-values from defective percentages."""
        assert get_k_value(10.0) == 1.28
        assert get_k_value(5.0) == 1.64
        assert get_k_value(2.5) == 1.96
        assert get_k_value(1.0) == 2.33

    def test_user_provided_std_deviation(self):
        """Test that user-provided standard deviation overrides Figure 3."""
        designer = DOEMixDesign()

        cement = Cement(type=CementType.OPC_43)
        coarse_agg = CoarseAggregate(nominal_max_size_mm=20, specific_gravity=2.6, shape=AggregateShape.ROUNDED_GRAVEL)
        fine_agg = FineAggregate(specific_gravity=2.6, pct_passing_600um=70.0)

        # Test with user-provided standard deviation of 5.0 MPa
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            has_production_data=False,  # Would normally use 8.0 MPa from Figure 3
            defective_percent=5.0,  # k = 1.64
            std_deviation=5.0,  # User-provided value
        )

        result = designer.design(inp)

        # Expected: fm = 30 + 1.64 * 5.0 = 38.2 MPa
        assert abs(result.target_mean_strength_mpa - 38.2) < 0.5

    def test_auto_std_deviation_when_not_provided(self):
        """Test that auto standard deviation from Figure 3 is used when std_deviation is None."""
        designer = DOEMixDesign()

        cement = Cement(type=CementType.OPC_43)
        coarse_agg = CoarseAggregate(nominal_max_size_mm=20, specific_gravity=2.6, shape=AggregateShape.ROUNDED_GRAVEL)
        fine_agg = FineAggregate(specific_gravity=2.6, pct_passing_600um=70.0)

        # Test with no user-provided standard deviation (should use Figure 3)
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            has_production_data=False,  # Should use 8.0 MPa from Figure 3 Line A
            defective_percent=5.0,  # k = 1.64
            std_deviation=None,  # Auto
        )

        result = designer.design(inp)

        # Expected: fm = 30 + 1.64 * 8.0 = 43.12 MPa
        assert abs(result.target_mean_strength_mpa - 43.1) < 0.5

    def test_mixed_aggregate_types_water_formula(self):
        """Test weighted water formula when fine and coarse aggregates differ (BRE 331:1997 Note to Table 3).

        When coarse and fine aggregates are of different types:
        W = 2/3 Wf + 1/3 Wc

        Example: 20mm NMSA, slump 10-30mm
        - Uncrushed fine aggregate: Wf = 160 kg/m³
        - Crushed coarse aggregate: Wc = 190 kg/m³
        - Expected: W = 2/3 × 160 + 1/3 × 190 = 106.67 + 63.33 = 170 kg/m³
        """
        from concrete_mix.codes.tables.doe_tables import get_free_water_content

        # Verify the weighted formula calculation
        nmsa = 20
        slump_mm = 20.0  # 10-30mm range

        w_fine = get_free_water_content(nmsa, "uncrushed", slump_mm)
        w_coarse = get_free_water_content(nmsa, "crushed", slump_mm)
        w_mixed = (2.0 / 3.0) * w_fine + (1.0 / 3.0) * w_coarse

        # Table 3 values for 20mm aggregate, 10-30mm slump:
        # Uncrushed: 160 kg/m³, Crushed: 190 kg/m³
        assert w_fine == 160.0
        assert w_coarse == 190.0
        assert abs(w_mixed - 170.0) < 0.1  # 170 kg/m³

        # Test with actual mix design
        designer = DOEMixDesign()
        cement = Cement(type=CementType.OPC_43)
        # Uncrushed fine aggregate (natural sand)
        fine_agg = FineAggregate(
            specific_gravity=2.6,
            pct_passing_600um=70.0,
            shape=AggregateShape.ROUNDED_GRAVEL,  # uncrushed
        )
        # Crushed coarse aggregate (manufactured)
        coarse_agg = CoarseAggregate(
            nominal_max_size_mm=20,
            specific_gravity=2.6,
            shape=AggregateShape.ANGULAR,  # crushed
        )

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            has_production_data=True,
            defective_percent=5.0,
        )

        result = designer.design(inp)

        # Water should be 170 kg/m³ (weighted average)
        assert result.water_kg == 170.0


# ---------------------------------------------------------------------------
# Worked Examples (Section 7)
# ---------------------------------------------------------------------------
class TestDOEWorkedExamples:
    """Verify full design runs against worked examples in Section 7."""

    def test_example_1_unrestricted(self):
        """Example 1: Unrestricted mix design."""
        designer = DOEMixDesign()
        
        # Define materials
        cement = Cement(type=CementType.OPC_43)  # Maps to class 42.5
        coarse_agg = CoarseAggregate(nominal_max_size_mm=20, specific_gravity=2.6, shape=AggregateShape.ROUNDED_GRAVEL)  # uncrushed
        fine_agg = FineAggregate(specific_gravity=2.6, pct_passing_600um=70.0)

        # MixDesignInput
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,  # characteristic strength fc
            slump_mm=20.0,  # 10-30 mm range
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            has_production_data=False,  # no previous data (s=8)
            w_c_ratio=0.55,  # max W/C
            volume_m3=1.0,
            defective_percent=2.5,
        )

        # Modify min cement in kwargs/properties if needed. 
        # In doe.py min cement is read via getattr(inp, "min_cement_kg", None)
        object.__setattr__(inp, "min_cement_kg", 290.0)

        result = designer.design(inp)

        # Expected:
        # Target mean strength = 30 + 1.96*8 = 45.7 N/mm² (~46)
        # Reference strength at 0.5 = 42 N/mm²
        # W/C ratio = 0.47
        # Water content = 160 kg/m³
        # Cement content = 160 / 0.47 = 340 kg/m³
        # Wet density = 2400 kg/m³
        # Total aggregate = 2400 - 340 - 160 = 1900 kg/m³
        # Fine aggregate proportion = 27%
        # Fine aggregate = 515 kg/m³ (rounded to 5)
        # Coarse aggregate = 1385 kg/m³ (rounded to 5)
        
        assert abs(result.target_mean_strength_mpa - 45.7) < 0.5
        assert abs(result.w_c_ratio - 0.47) < 0.01
        assert result.water_kg == 160.0
        assert result.cement_kg == 340.0
        assert result.fine_aggregate_kg == 515.0
        assert result.coarse_aggregate_kg == 1385.0

    def test_example_2_max_wc_restricted(self):
        """Example 2: Capped by maximum W/C ratio limit."""
        designer = DOEMixDesign()
        
        cement = Cement(type=CementType.OPC_43)  # class 42.5
        coarse_agg = CoarseAggregate(nominal_max_size_mm=40, specific_gravity=2.5, shape=AggregateShape.ROUNDED_GRAVEL)
        fine_agg = FineAggregate(specific_gravity=2.5, pct_passing_600um=90.0)

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=25.0,
            slump_mm=45.0,  # 30-60 mm slump
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            w_c_ratio=0.50,  # Max allowed W/C
            volume_m3=1.0,
        )
        
        # Directly specified margin of 10 MPa (in DOE, can override std dev or margin)
        # In calculate_target_mean_strength, we can bypass std dev by setting target_strength_mpa directly
        # E.g. characteristic_strength_mpa = 25, target_strength_mpa = 35 (so margin = 10)
        object.__setattr__(inp, "characteristic_strength_mpa", 25.0)
        object.__setattr__(inp, "target_strength_mpa", 35.0)
        object.__setattr__(inp, "min_cement_kg", 290.0)

        result = designer.design(inp)

        # Expected:
        # Target mean strength = 35 MPa
        # W/C ratio calculated = 0.57, but capped at 0.50
        # Water = 160 kg/m³
        # Cement = 160 / 0.50 = 320 kg/m³
        # Wet density = 2325 kg/m³
        # Total aggregate = 2325 - 320 - 160 = 1845 kg/m³
        # Fine aggregate proportion = 22%
        # Fine aggregate = 1845 * 0.22 = 405.9 -> 405 kg/m³
        # Coarse aggregate = 1845 - 405 = 1440 kg/m³
        
        assert result.w_c_ratio == 0.50
        assert result.water_kg == 160.0
        assert result.cement_kg == 320.0
        assert result.fine_aggregate_kg == 405.0
        assert result.coarse_aggregate_kg == 1440.0
        assert any("durability override" in w.lower() for w in result.warnings)

    def test_example_3_min_cement_restricted(self):
        """Example 3: Restricted by minimum cement content."""
        designer = DOEMixDesign()
        
        cement = Cement(type=CementType.OPC_43)  # class 42.5
        coarse_agg = CoarseAggregate(nominal_max_size_mm=40, specific_gravity=2.5, shape=AggregateShape.ROUNDED_GRAVEL)
        fine_agg = FineAggregate(specific_gravity=2.5, pct_passing_600um=90.0)

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=25.0,
            slump_mm=5.0,  # 0-10 mm slump
            cement=cement,
            coarse_aggregate=coarse_agg,
            fine_aggregate=fine_agg,
            w_c_ratio=0.50,  # Max W/C
            volume_m3=1.0,
        )
        
        object.__setattr__(inp, "characteristic_strength_mpa", 25.0)
        object.__setattr__(inp, "target_strength_mpa", 35.0)
        object.__setattr__(inp, "min_cement_kg", 290.0)

        result = designer.design(inp)

        # Expected:
        # Target mean strength = 35 MPa
        # W/C calculated = 0.57, capped at W/C = 0.50
        # Water = 115 kg/m³
        # Cement calculated = 115 / 0.50 = 230 kg/m³, boosted to min 290 kg/m³
        # Modified W/C = 115 / 290 = 0.40
        # Wet density = 2375 kg/m³
        # Total aggregate = 2375 - 290 - 115 = 1970 kg/m³
        
        assert result.cement_kg == 290.0
        assert result.water_kg == 115.0
        assert abs(result.w_c_ratio - 0.40) < 0.01
        assert any("min cement content" in w.lower() for w in result.warnings)

    def test_design_mix_simple_doe(self):
        """Verify that design_mix_simple runs successfully for the doe standard."""
        from concrete_mix import design_mix_simple
        
        result = design_mix_simple(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            nmsa=20,
            cement_type="GRADE_42_5R", # Mapped to OPC_43, then Class 42.5
            cement_sg=3.15,
            fine_agg_sg=2.6,
            fine_agg_pct_passing_600um=70.0,
            coarse_agg_sg=2.6,
            aggregate_shape="rounded_gravel",
            has_production_data=False,
            w_c_ratio=0.55,
            min_cement_kg=290.0,
            defective_percent=2.5,
        )

        assert abs(result.target_mean_strength_mpa - 45.7) < 0.5
        assert abs(result.w_c_ratio - 0.47) < 0.01
        assert result.water_kg == 160.0
        assert result.cement_kg == 340.0
        assert result.fine_aggregate_kg == 515.0
        assert result.coarse_aggregate_kg == 1385.0
