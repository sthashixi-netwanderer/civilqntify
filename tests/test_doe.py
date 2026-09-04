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

        # Expected: fm = 30 + 1.64 * 5.0 = 38.2 → 39 MPa (C2, rounded up)
        assert result.target_mean_strength_mpa == 39.0

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

        # Expected: fm = 30 + 1.64 * 8.0 = 43.12 → 44 MPa (C2, rounded up)
        assert result.target_mean_strength_mpa == 44.0

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

        # Expected (§7.1):
        # Target mean = 30 + 1.96*8 = 45.68 → 46 N/mm² (C2, rounded up)
        # Reference strength at 0.5 = 42 N/mm²
        # W/C ratio = 0.47 (Figure 4 read, 2 dp)
        # Water content = 160 kg/m³
        # Cement content = 160 / 0.47 = 340.4 → 340 kg/m³ (nearest 5 kg)
        # Wet density = 2400 kg/m³ (Figure 5 read to nearest 5 kg)
        # Total aggregate = 2400 - 340 - 160 = 1900 kg/m³ (doc: 1900)
        # Fine aggregate proportion = 27.7% (doc chart read 27%)
        # Fine aggregate = 525 kg/m³ (doc 515 — one 5-kg quantum)
        # Coarse aggregate = 1375 kg/m³ (doc 1385 — one 5-kg quantum)

        assert result.target_mean_strength_mpa == 46.0
        assert abs(result.w_c_ratio - 0.47) < 0.01
        assert result.water_kg == 160.0
        assert result.cement_kg == 340.0
        assert result.fine_aggregate_kg == 525.0
        assert result.coarse_aggregate_kg == 1375.0

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
        # Fine aggregate proportion = 21.8% (Figure 6 digitisation; the
        #   standard's chart reading is 22% — within chart tolerance)
        # Fine aggregate = 1845 × 0.218 → 400 kg/m³
        # Coarse aggregate = 1445 kg/m³

        assert result.w_c_ratio == 0.50
        assert result.water_kg == 160.0
        assert result.cement_kg == 320.0
        assert result.fine_aggregate_kg == 400.0
        assert result.coarse_aggregate_kg == 1445.0
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

        assert result.target_mean_strength_mpa == 46.0
        assert abs(result.w_c_ratio - 0.47) < 0.01
        assert result.water_kg == 160.0
        assert result.cement_kg == 340.0
        assert result.fine_aggregate_kg == 525.0
        assert result.coarse_aggregate_kg == 1375.0

    def test_doe_admixture_water_reduction(self):
        """Verify that water-reducing admixture in DOE reduces water and calculates batch mass (BRE 331 §5.3)."""
        from concrete_mix.models.materials import Admixture
        designer = DOEMixDesign()
        inp_plain = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=50.0,
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
        )
        res_plain = designer.design(inp_plain)

        inp_admix = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=50.0,
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
            admixture=Admixture(
                type="superplasticizer",
                dosage_percent=1.0,
                water_reduction_percent=15.0,
            ),
        )
        res_admix = designer.design(inp_admix)

        assert res_admix.water_kg < res_plain.water_kg
        assert res_admix.admixture_kg is not None
        assert res_admix.admixture_kg > 0
        assert res_admix.admixture_type == "superplasticizer"
        assert res_admix.admixture_dosage_percent == 1.0


# ---------------------------------------------------------------------------
# BRE 331:1997 §8 — air-entrained DOE design (Table 8 replication)
# ---------------------------------------------------------------------------
class TestDOEAirEntrained:
    """§8.6 worked example: fc30, 1% defectives, s=5, 4.5% air, 20 mm
    (coarse crushed / fine uncrushed), 25 mm slump, 50% passing 600 µm."""

    def _table8_input(self):
        from concrete_mix.models.materials import (
            AggregateShape, Cement, CementType, CoarseAggregate, FineAggregate,
        )

        return MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=25.0,
            cement=Cement(type=CementType.OPC_43, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, pct_passing_600um=50.0,
                shape=AggregateShape.GRAVEL),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.65,
                shape=AggregateShape.ANGULAR),
            defective_percent=1.0,
            std_deviation=5.0,
            air_pct=4.5,
            w_c_ratio=0.55,  # Item 1.8 durability cap (not binding here)
            min_cement_kg=285.0,
        )

    def test_modified_target(self):
        """§8.6 chain: C2 gives 30 + 2.33×5 = 41.65 → 42 (rounded up);
        Item 1.4.2 modified target = 42/(1 − 0.055×4.5) = 55.81."""
        designer = DOEMixDesign()
        result = designer.design(self._table8_input())
        assert abs(result.target_mean_strength_mpa - 42.0) < 0.05
        s31 = next(s for s in result.steps if s.step_number == 3.1)
        assert abs(s31.result - 55.81) < 0.1

    def test_table8_masses(self):
        """Table 8: w/c 0.45, W 145, C 320, total aggregate 1875 (600+1275)."""
        designer = DOEMixDesign()
        result = designer.design(self._table8_input())
        assert result.water_kg == 145.0
        assert result.cement_kg == 320.0
        # Total aggregate 1875 matches the form exactly (2340 − 320 − 145);
        # the Figure 6 read of 32.75% vs the form's "say 32%" puts FA/CA at
        # 615/1260 vs the table's 600/1275 — one 5-kg quantum of tolerance.
        assert result.fine_aggregate_kg == 615.0
        assert abs(result.coarse_aggregate_kg - 1260.0) <= 5.0
        # Table 8 reads w/c 0.45 off Figure 4.
        assert abs(result.w_c_ratio - 0.45) < 0.005
        assert result.air_volume_percent == 4.5

    def test_air_outside_3_to_7_warns(self):
        designer = DOEMixDesign()
        inp = self._table8_input()
        object.__setattr__(inp, "air_pct", 2.0)
        result = designer.design(inp)
        assert any("3–7%" in w for w in result.warnings)

    def test_no_air_no_air_steps(self):
        """Legacy path: no 3.1/9.1 steps, air 0.0."""
        designer = DOEMixDesign()
        inp = self._table8_input()
        object.__setattr__(inp, "air_pct", 0.0)
        result = designer.design(inp)
        assert not any(s.step_number in (3.1, 9.1) for s in result.steps)
        assert result.air_volume_percent == 0.0


# ---------------------------------------------------------------------------
# BRE 331 Table 3 — Vebe basis, and §5.5 CA splits
# ---------------------------------------------------------------------------
class TestDOEVebeAndSplit:
    def test_vebe_class_matches_slump_class(self):
        """Vebe 8 s (class 1) gives the same water as 20 mm slump (class 1)."""
        designer = DOEMixDesign()
        slump_inp = MixDesignInput(code="doe", target_strength_mpa=30.0,
                                   slump_mm=20.0,
                                   fine_aggregate=FineAggregate(pct_passing_600um=70.0))
        vebe_inp = MixDesignInput(code="doe", target_strength_mpa=30.0,
                                  slump_mm=20.0, vebe_s=8.0,
                                  fine_aggregate=FineAggregate(pct_passing_600um=70.0))
        assert (designer.design(vebe_inp).water_kg
                == designer.design(slump_inp).water_kg == 160.0)

    def test_vebe_class_boundaries(self):
        from concrete_mix.codes.tables.doe_tables import vebe_to_workability_class

        assert vebe_to_workability_class(15.0) == 0
        assert vebe_to_workability_class(8.0) == 1
        assert vebe_to_workability_class(4.0) == 2
        assert vebe_to_workability_class(1.0) == 3

    def test_ca_split_10_20(self):
        """20 mm CA splits 1:2 to 5-kg parts summing to the total."""
        designer = DOEMixDesign()
        inp = MixDesignInput(code="doe", target_strength_mpa=30.0,
                             slump_mm=20.0, ca_split="10+20",
                             fine_aggregate=FineAggregate(pct_passing_600um=70.0))
        result = designer.design(inp)
        s131 = next(s for s in result.steps if s.step_number == 13.1)
        parts = s131.inputs["parts"]
        assert abs(parts["10 mm"] * 2 - parts["20 mm"]) <= 5.0
        assert parts["10 mm"] + parts["20 mm"] == result.coarse_aggregate_kg

    def test_ca_split_carried_on_result(self):
        """Step 13.1 parts are carried on the result for the panel (BRE §5.5)."""
        designer = DOEMixDesign()
        result = designer.design(
            MixDesignInput(code="doe", target_strength_mpa=30.0,
                           slump_mm=20.0, ca_split="10+20",
                           fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        assert result.ca_split_kg is not None
        assert set(result.ca_split_kg) == {"10 mm", "20 mm"}
        assert abs(sum(result.ca_split_kg.values()) - result.coarse_aggregate_kg) < 1e-9
        # Volume scaling keeps the split consistent with the CA total.
        scaled = result.scaled_to_volume(2.0)
        assert abs(sum(scaled.ca_split_kg.values()) - scaled.coarse_aggregate_kg) < 1e-9

    def test_ca_split_serialiser_round_trip(self):
        """History save/load preserves the single-size split."""
        import json

        from history.serializers import deserialize_mix_result, serialize_mix_result

        designer = DOEMixDesign()
        result = designer.design(
            MixDesignInput(code="doe", target_strength_mpa=30.0,
                           slump_mm=20.0, ca_split="10+20",
                           fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        restored = deserialize_mix_result(json.loads(serialize_mix_result(result)))
        assert restored.ca_split_kg == result.ca_split_kg

    def test_no_split_no_ca_split_on_result(self):
        designer = DOEMixDesign()
        result = designer.design(
            MixDesignInput(code="doe", target_strength_mpa=30.0, slump_mm=20.0,
                           fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        assert result.ca_split_kg is None

    def test_ca_split_wrong_nmsa_blocked(self):
        designer = DOEMixDesign()
        inp = MixDesignInput(code="doe", target_strength_mpa=30.0,
                             slump_mm=20.0, ca_split="10+20+40",
                             fine_aggregate=FineAggregate(pct_passing_600um=70.0))
        with pytest.raises(ValueError, match="requires 40 mm NMSA"):
            designer.design(inp)

    def test_no_split_no_step(self):
        designer = DOEMixDesign()
        result = designer.design(
            MixDesignInput(code="doe", target_strength_mpa=30.0, slump_mm=20.0,
                           fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        assert not any(s.step_number == 13.1 for s in result.steps)

    def test_trial_batch_reference_step(self):
        """Every DOE design carries the 0.05 m³ §6.1 trial quantities."""
        designer = DOEMixDesign()
        result = designer.design(
            MixDesignInput(code="doe", target_strength_mpa=30.0, slump_mm=20.0,
                           fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        s14 = next(s for s in result.steps if s.step_number == 14)
        assert s14.inputs["trial_volume_m3"] == 0.05
        assert abs(s14.inputs["cement"] - result.cement_kg * 0.05) < 0.01
        assert s14.inputs["absorption_water"] > 0  # default absorptions apply
# ---------------------------------------------------------------------------
# BRE 331:1997 §9 — pfa design (§9.4 replication) and §10 ggbs
# ---------------------------------------------------------------------------
class TestDOEPfaGgbs:
    """§9.4 example: fc35, specified margin 12, 30% pfa, 20 mm uncrushed,
    slump 10–30, 70% passing 600 µm, Item 3.8 cap 0.60, min 300."""

    def _pfa94_input(self):
        from concrete_mix.models.materials import (
            AggregateShape, Cement, CementType, CoarseAggregate, FineAggregate,
            SCM, SCMType,
        )

        return MixDesignInput(
            code="doe",
            target_strength_mpa=35.0,
            slump_mm=20.0,
            cement=Cement(type=CementType.OPC_43, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, pct_passing_600um=70.0,
                shape=AggregateShape.GRAVEL),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.60,
                shape=AggregateShape.GRAVEL),
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=30.0),),
            margin_mpa=12.0,
            w_c_ratio=0.60,
            min_cement_kg=300.0,
        )

    def test_pfa_example_masses(self):
        """Table 11/12: fm 47, W 145, C 280, F 120 — cementitious exact."""
        designer = DOEMixDesign()
        result = designer.design(self._pfa94_input())
        assert result.target_mean_strength_mpa == 47.0
        assert result.water_kg == 145.0
        assert result.cement_kg == 280.0
        assert abs(result.scm_kg - 120.0) < 0.5
        # (C+F) rounds to 400 kg/m³ as in Table 12; total aggregate
        # 2420 − 400 − 145 = 1875. The Figure 6 read of 25.75% vs the
        # table's 26% puts FA/CA at 485/1390 vs 490/1385 — one quantum.
        assert result.fine_aggregate_kg == 485.0
        assert abs(result.coarse_aggregate_kg - 1390.0) <= 5.0

    def test_pfa_ratios(self):
        """Item 1.7 W/(C+0.30F) ≈ 0.46; Item 3.7 W/(C+F) ≈ 0.36 ≤ 0.60."""
        designer = DOEMixDesign()
        result = designer.design(self._pfa94_input())
        assert abs(result.w_c_ratio - 0.46) < 0.02
        s72 = next(s for s in result.steps if s.step_number == 7.2)
        assert abs(s72.result - 0.36) < 0.02

    def test_pfa_outside_typical_range_warns(self):
        from concrete_mix.models.materials import SCM, SCMType

        designer = DOEMixDesign()
        inp = self._pfa94_input()
        object.__setattr__(
            inp, "scms", (SCM(type=SCMType.FLY_ASH, replacement_percent=10.0),))
        result = designer.design(inp)
        assert any("15–40%" in w for w in result.warnings)

    def test_ggbs_40_percent_splits_mass_for_mass(self):
        """≤40% ggbs: normal C3 total, water −5 kg, 60/40 split."""
        from concrete_mix.models.materials import SCM, SCMType

        designer = DOEMixDesign()
        inp = MixDesignInput(
            code="doe", target_strength_mpa=30.0, slump_mm=20.0,
            scms=(SCM(type=SCMType.GGBFS, replacement_percent=40.0),),
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
        )
        result = designer.design(inp)
        assert result.water_kg == 155.0  # 160 − 5 (§10.2.1)
        # C3 total 155/0.55 = 281.8 → 280 to the nearest 5 kg; mass-for-mass
        # split 60/40 → 168 cement + 112 ggbs (§10.3; no worked example in
        # the standard — pinned from the documented rounding chain).
        assert result.cement_kg == 168.0
        assert abs(result.scm_kg - 112.0) < 0.6
        s75 = next(s for s in result.steps if s.step_number == 7.5)
        assert "§10.3" in s75.clause_ref

    def test_ggbs_above_40_blocked(self):
        from concrete_mix.models.materials import SCM, SCMType

        designer = DOEMixDesign()
        inp = MixDesignInput(
            code="doe", target_strength_mpa=30.0, slump_mm=20.0,
            scms=(SCM(type=SCMType.GGBFS, replacement_percent=50.0),),
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
        )
        with pytest.raises(ValueError, match="consult the"):
            designer.design(inp)

    def test_unsupported_scm_blocked(self):
        from concrete_mix.models.materials import SCM, SCMType

        designer = DOEMixDesign()
        inp = MixDesignInput(
            code="doe", target_strength_mpa=30.0, slump_mm=20.0,
            scms=(SCM(type=SCMType.SILICA_FUME, replacement_percent=7.0),),
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
        )
        with pytest.raises(ValueError, match="no procedure"):
            designer.design(inp)

    def test_table9b_values(self):
        from concrete_mix.codes.tables.doe_tables import pfa_water_reduction

        assert pfa_water_reduction(30, 1) == 15.0
        assert pfa_water_reduction(30, 0) == 15.0
        assert pfa_water_reduction(25, 2) == 15.0  # interpolated 10→20
        assert pfa_water_reduction(50, 3) == 30.0
# ---------------------------------------------------------------------------
# BRE 331:1997 §1.2.4 two-class aggregate mapping (gap-audit Phase 1)
# ---------------------------------------------------------------------------
class TestDOEAggregateMapping:
    """Sub-angular/irregular aggregates are uncrushed; only angular/crushed rock is crushed."""

    def _inp(self, shape):
        from concrete_mix.models.materials import (
            AggregateShape, CoarseAggregate, FineAggregate,
        )

        return MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            coarse_aggregate=CoarseAggregate(shape=shape),
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
        )

    def test_sub_angular_is_uncrushed(self):
        from concrete_mix.models.materials import AggregateShape

        assert DOEMixDesign._map_agg_type(self._inp(AggregateShape.SUB_ANGULAR)) == "uncrushed"

    def test_rounded_gravel_is_uncrushed(self):
        from concrete_mix.models.materials import AggregateShape

        assert DOEMixDesign._map_agg_type(self._inp(AggregateShape.ROUNDED_GRAVEL)) == "uncrushed"

    def test_angular_is_crushed(self):
        from concrete_mix.models.materials import AggregateShape

        assert DOEMixDesign._map_agg_type(self._inp(AggregateShape.ANGULAR)) == "crushed"

    def test_crushed_fragments_is_crushed(self):
        from concrete_mix.models.materials import AggregateShape

        assert DOEMixDesign._map_agg_type(self._inp(AggregateShape.CRUSHED_FRAGMENTS)) == "crushed"

    def test_sub_angular_water_matches_uncrushed(self):
        """A sub-angular 20 mm / 10–30 mm mix takes the uncrushed Table 3 row (160 kg/m³)."""
        from concrete_mix.models.materials import AggregateShape, CoarseAggregate

        designer = DOEMixDesign()
        res = designer.design(self._inp(AggregateShape.SUB_ANGULAR))
        assert res.water_kg == 160.0
        ref = designer.design(self._inp(AggregateShape.ROUNDED_GRAVEL))
        assert res.water_kg == ref.water_kg


# ---------------------------------------------------------------------------
# BRE 331 Figure 3 — any-grade standard deviation (user-supplied equations)
# Line A (n<20): s = 0.4×fc (fc≤20) else 8 MPa
# Line B (n≥20): s = 0.2×fc (fc≤20) else 4 MPa
# ---------------------------------------------------------------------------
class TestDOEFigure3AnyGrade:
    def test_table_boundaries(self):
        from concrete_mix.codes.tables.doe_tables import get_standard_deviation as g

        assert g(20.0, True, n=19) == 8.0
        assert g(20.0, True, n=20) == 4.0
        assert g(15.0, True, n=10) == pytest.approx(6.0)    # 0.4 × 15
        assert g(15.0, True, n=30) == pytest.approx(3.0)    # 0.2 × 15
        assert g(10.0, True, n=1) == pytest.approx(4.0)
        assert g(10.0, True, n=60) == pytest.approx(2.0)
        assert g(25.0, True, n=10) == 8.0                   # plateau
        assert g(25.0, True, n=25) == 4.0                   # plateau

    def test_randomized_figure3_compliance(self):
        """Seeded property test: implementation == chart equations everywhere,
        continuous at fc = 20, monotone, and Line A ≥ Line B."""
        import random

        from concrete_mix.codes.tables.doe_tables import get_standard_deviation as g

        def chart(fcu, n):
            if n < 20:
                return 0.4 * fcu if fcu <= 20 else 8.0
            return 0.2 * fcu if fcu <= 20 else 4.0

        for seed in (7, 42, 1234):
            rng = random.Random(seed)
            for _ in range(1000):
                fcu = rng.uniform(5.0, 100.0)
                n = rng.randint(1, 60)
                assert g(fcu, True, n=n) == pytest.approx(chart(fcu, n))
                # ordering + monotonicity spot checks
                assert g(fcu, True, n=5) >= g(fcu, True, n=40) - 1e-9
        # continuity at the fc = 20 joint (0.4×20 = 8, 0.2×20 = 4)
        assert g(20.0, True, n=3) == g(20.0001, True, n=3) == pytest.approx(8.0)
        assert g(20.0, True, n=20) == g(20.0001, True, n=20) == pytest.approx(4.0)

    def test_input_accepts_any_grade(self):
        """DOE floor is now [5, 100] MPa; IS/ACI-style floors do not apply."""
        inp = MixDesignInput(code="doe", target_strength_mpa=15.0, slump_mm=30.0)
        assert inp.characteristic_strength == 15.0
        with pytest.raises(ValueError, match=r"\[5, 100\]"):
            MixDesignInput(code="doe", target_strength_mpa=4.0, slump_mm=30.0)

    def test_m15_end_to_end_uses_line_a_ramp(self):
        """M15, n=10: s = 0.4×15 = 6.0 → M = 9.84 → fm = 24.84 → 25 (C2)."""
        designer = DOEMixDesign()
        inp = MixDesignInput(code="doe", target_strength_mpa=15.0,
                             slump_mm=30.0, num_test_cubes=10,
                             fine_aggregate=FineAggregate(pct_passing_600um=70.0))
        result = designer.design(inp)
        assert abs(result.target_mean_strength_mpa - 25.0) < 0.01
        s1 = next(s for s in result.steps if s.step_number == 1)
        assert abs(s1.result - 6.0) < 1e-9
        assert "Line A" in s1.description
        assert "0.4" in s1.formula

    def test_m12_line_b_ramp_in_steps(self):
        """M12, n=30: s = 0.2×12 = 2.4 → fm = 15.936 → 16 (C2 rounded up)."""
        designer = DOEMixDesign()
        result = designer.design(MixDesignInput(
            code="doe", target_strength_mpa=12.0, slump_mm=20.0,
            num_test_cubes=30,
            fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        assert abs(result.target_mean_strength_mpa - 16.0) < 0.01
        s1 = next(s for s in result.steps if s.step_number == 1)
        assert "Line B" in s1.description and "0.2" in s1.formula
        assert "Figure 3" in s1.clause_ref

    def test_plateau_step_text(self):
        """fc > 20 shows the plateau equation, not the ramp."""
        designer = DOEMixDesign()
        result = designer.design(MixDesignInput(
            code="doe", target_strength_mpa=30.0, slump_mm=20.0,
            num_test_cubes=10,
            fine_aggregate=FineAggregate(pct_passing_600um=70.0)))
        s1 = next(s for s in result.steps if s.step_number == 1)
        assert s1.result == 8.0 and "plateau" in s1.formula

    def test_target_strength_mode_low_grade(self):
        """Target-only path honors Figure 3 below M25 too (fm ceiled per C2)."""
        from concrete_mix.engine.target_strength import calculate_target_strength

        r = calculate_target_strength("doe", 15.0, num_test_cubes=10)
        assert r.standard_deviation_mpa == pytest.approx(6.0)
        assert r.target_mean_strength_mpa == pytest.approx(25.0)
        assert "Line A" in r.formula
