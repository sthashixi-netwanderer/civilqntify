"""Tests for Material Quantification module (Module 2).

Verifies:
- Transfer data construction from MixDesignResult
- Structural element volume calculations
- Material quantifier (by volume and by elements)
- Override functionality
- Wastage factor application
- Bag rounding (ceiling)
"""

import math

import pytest

from concrete_mix import design_mix_simple
from material_quantify import MaterialQuantifier, StructuralElement
from material_quantify.models.bill import MaterialBill
from material_quantify.models.transfer_data import MixDesignTransferData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def is_result():
    """IS 10262 mix design result (M25, mild exposure)."""
    return design_mix_simple(
        code="is10262",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
        cement_type="OPC_43",
        exposure_class="mild",
    )


@pytest.fixture
def aci_result():
    """ACI 211.1 mix design result (25 MPa structural concrete)."""
    return design_mix_simple(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=75.0,
        nmsa=20,
        cement_type="TYPE_I",
    )


@pytest.fixture
def is_transfer(is_result):
    """Transfer data from IS result."""
    return MixDesignTransferData.from_mix_design_result(is_result)


@pytest.fixture
def aci_transfer(aci_result):
    """Transfer data from ACI result."""
    return MixDesignTransferData.from_mix_design_result(aci_result)


# ---------------------------------------------------------------------------
# Transfer Data
# ---------------------------------------------------------------------------

class TestTransferData:
    """Test MixDesignTransferData construction and overrides."""

    def test_from_is_result(self, is_result):
        td = MixDesignTransferData.from_mix_design_result(is_result)
        assert "IS" in td.code_used
        assert td.cement_kg_per_m3 > 0
        assert td.water_kg_per_m3 > 0
        assert td.fine_aggregate_kg_per_m3 > 0
        assert td.coarse_aggregate_kg_per_m3 > 0
        assert td.cement_bag_weight_kg == 50.0

    def test_from_aci_result(self, aci_result):
        td = MixDesignTransferData.from_mix_design_result(aci_result)
        assert "ACI" in td.code_used
        assert td.cement_bag_weight_kg == 42.64

    def test_with_overrides(self, is_transfer):
        new = is_transfer.with_overrides(cement_kg_per_m3=400.0)
        assert new.cement_kg_per_m3 == 400.0
        assert is_transfer.cement_kg_per_m3 != 400.0  # original unchanged

    def test_display_dict(self, is_transfer):
        rows = is_transfer.to_display_dict()
        assert len(rows) > 0
        assert all(len(r) == 3 for r in rows)


# ---------------------------------------------------------------------------
# Structural Element
# ---------------------------------------------------------------------------

class TestStructuralElement:
    """Test structural element volume calculations."""

    def test_footing_volume(self):
        elem = StructuralElement("footing", 2.0, 2.0, 0.5, quantity=4)
        assert elem.volume_per_element_m3 == 2.0
        assert elem.total_volume_m3 == 8.0

    def test_column_volume(self):
        elem = StructuralElement("column", 0.4, 0.4, 3.0, quantity=8)
        assert abs(elem.volume_per_element_m3 - 0.48) < 0.001
        assert abs(elem.total_volume_m3 - 3.84) < 0.001

    def test_beam_volume(self):
        elem = StructuralElement("beam", 6.0, 0.3, 0.5, quantity=10)
        assert elem.volume_per_element_m3 == pytest.approx(0.9)
        assert elem.total_volume_m3 == pytest.approx(9.0)

    def test_slab_volume(self):
        elem = StructuralElement("slab", 10.0, 5.0, 0.15, quantity=1)
        assert elem.volume_per_element_m3 == 7.5
        assert elem.total_volume_m3 == 7.5

    def test_wall_volume(self):
        elem = StructuralElement("wall", 10.0, 3.0, 0.2, quantity=2)
        assert elem.volume_per_element_m3 == 6.0
        assert elem.total_volume_m3 == 12.0

    def test_invalid_dimensions_raise(self):
        with pytest.raises(ValueError, match="positive"):
            StructuralElement("footing", -1.0, 2.0, 0.5)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            StructuralElement("footing", 2.0, 2.0, 0.5, quantity=0)

    def test_dimension_labels(self):
        assert StructuralElement("footing", 1, 1, 1).dimension_labels == ("Length", "Width", "Depth")
        assert StructuralElement("column", 1, 1, 1).dimension_labels == ("Length", "Width", "Height")
        assert StructuralElement("beam", 1, 1, 1).dimension_labels == ("Length", "Width", "Depth")
        assert StructuralElement("slab", 1, 1, 1).dimension_labels == ("Length", "Width", "Thickness")
        assert StructuralElement("wall", 1, 1, 1).dimension_labels == ("Length", "Height", "Thickness")

    def test_summary_line(self, capsys):
        elem = StructuralElement("footing", 2.0, 2.0, 0.5, quantity=4)
        summary = elem.summary_line()
        assert "Footing" in summary
        assert "4x" in summary


# ---------------------------------------------------------------------------
# Material Quantifier — by Volume
# ---------------------------------------------------------------------------

class TestQuantifierByVolume:
    """Test MaterialQuantifier.quantify_by_volume."""

    def test_basic_quantification(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        bill = q.quantify_by_volume(10.0, wastage_percent=5.0)

        assert bill.net_concrete_volume_m3 == 10.0
        assert bill.wastage_percent == 5.0
        assert abs(bill.gross_concrete_volume_m3 - 10.5) < 0.001
        assert bill.total_cement_kg > 0
        assert bill.total_water_kg > 0
        assert bill.total_fine_aggregate_kg > 0
        assert bill.total_coarse_aggregate_kg > 0

    def test_zero_wastage(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        bill = q.quantify_by_volume(5.0, wastage_percent=0.0)

        assert bill.gross_concrete_volume_m3 == 5.0
        assert bill.wastage_percent == 0.0

    def test_cement_bags_rounded_up(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)

        expected_bags = math.ceil(bill.total_cement_kg / is_transfer.cement_bag_weight_kg)
        assert bill.total_cement_bags == expected_bags
        assert isinstance(bill.total_cement_bags, int) or bill.total_cement_bags == float(int(bill.total_cement_bags))

    def test_volume_scales_proportionally(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        bill_1 = q.quantify_by_volume(1.0, wastage_percent=0.0)
        bill_5 = q.quantify_by_volume(5.0, wastage_percent=0.0)

        assert abs(bill_5.total_cement_kg - bill_1.total_cement_kg * 5.0) < 0.1
        assert abs(bill_5.total_water_kg - bill_1.total_water_kg * 5.0) < 0.1

    def test_aci_bag_weight(self, aci_transfer):
        q = MaterialQuantifier(aci_transfer)
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)
        assert bill.cement_bag_weight_kg == 42.64

    def test_negative_volume_raises(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        with pytest.raises(ValueError, match="positive"):
            q.quantify_by_volume(-5.0)

    def test_negative_wastage_raises(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        with pytest.raises(ValueError, match="non-negative"):
            q.quantify_by_volume(5.0, wastage_percent=-1.0)


# ---------------------------------------------------------------------------
# Material Quantifier — by Elements
# ---------------------------------------------------------------------------

class TestQuantifierByElements:
    """Test MaterialQuantifier.quantify_by_elements."""

    def test_single_element(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        elements = [StructuralElement("slab", 10.0, 5.0, 0.15, quantity=1)]
        bill = q.quantify_by_elements(elements, wastage_percent=5.0)

        assert abs(bill.net_concrete_volume_m3 - 7.5) < 0.001
        assert abs(bill.gross_concrete_volume_m3 - 7.875) < 0.001

    def test_multiple_elements(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        elements = [
            StructuralElement("footing", 2.0, 2.0, 0.5, quantity=4),  # 8 m³
            StructuralElement("column", 0.4, 0.4, 3.0, quantity=8),   # 3.84 m³
            StructuralElement("beam", 6.0, 0.3, 0.5, quantity=10),    # 9.0 m³
        ]
        bill = q.quantify_by_elements(elements, wastage_percent=7.5)

        expected_net = 8.0 + 3.84 + 9.0
        assert abs(bill.net_concrete_volume_m3 - expected_net) < 0.01
        assert abs(bill.gross_concrete_volume_m3 - expected_net * 1.075) < 0.01

    def test_empty_elements_raises(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        with pytest.raises(ValueError, match="At least one"):
            q.quantify_by_elements([])


# ---------------------------------------------------------------------------
# Override
# ---------------------------------------------------------------------------

class TestOverride:
    """Test override functionality."""

    def test_override_cement(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        q.override(cement_kg_per_m3=400.0)
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)

        # With 400 kg/m³ and 0% wastage, total should be exactly 400
        assert abs(bill.total_cement_kg - 400.0) < 0.1

    def test_override_invalid_field_raises(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        with pytest.raises(ValueError, match="Cannot override"):
            q.override(invalid_field=123.0)

    def test_override_preserves_other_values(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        q.override(cement_kg_per_m3=400.0)
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)

        # Water should remain unchanged
        q2 = MaterialQuantifier(is_transfer)
        bill2 = q2.quantify_by_volume(1.0, wastage_percent=0.0)
        assert abs(bill.total_water_kg - bill2.total_water_kg) < 0.1


# ---------------------------------------------------------------------------
# Report Format
# ---------------------------------------------------------------------------

class TestMaterialBillReport:
    """Test MaterialBill.format_report."""

    def test_report_contains_key_sections(self, is_transfer):
        q = MaterialQuantifier(is_transfer)
        bill = q.quantify_by_volume(10.0, wastage_percent=5.0)
        report = bill.format_report()

        assert "MATERIAL BILL OF QUANTITIES" in report
        assert "MIX DESIGN REFERENCE" in report
        assert "VOLUME SUMMARY" in report
        assert "TOTAL MATERIAL QUANTITIES" in report
        assert "CEMENT BAG SUMMARY" in report
        assert "10.000 m" in report
        assert "5.0%" in report

    def test_report_shows_scm_when_present(self):
        result = design_mix_simple(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            scm_replacement_percent=20.0,
            scm_type="fly_ash",
        )
        td = MixDesignTransferData.from_mix_design_result(result)
        q = MaterialQuantifier(td)
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)
        report = bill.format_report()

        assert "SCM" in report


# ---------------------------------------------------------------------------
# Integration: Mix Design → Transfer → Quantify
# ---------------------------------------------------------------------------

class TestEndToEndIntegration:
    """Integration test: full pipeline from mix design to material bill."""

    def test_is_full_pipeline(self):
        result = design_mix_simple(
            code="is10262",
            target_strength_mpa=30.0,
            slump_mm=100.0,
            nmsa=20,
            cement_type="OPC_43",
            exposure_class="moderate",
            scm_replacement_percent=15.0,
            scm_type="fly_ash",
            admixture_water_reduction=10.0,
            volume_m3=1.0,
        )

        td = MixDesignTransferData.from_mix_design_result(result, cement_bag_weight_kg=50.0)
        elements = [
            StructuralElement("footing", 3.0, 3.0, 0.6, quantity=6),
            StructuralElement("column", 0.5, 0.5, 4.0, quantity=12),
            StructuralElement("beam", 8.0, 0.3, 0.6, quantity=8),
            StructuralElement("slab", 12.0, 8.0, 0.15, quantity=1),
        ]

        q = MaterialQuantifier(td)
        bill = q.quantify_by_elements(elements, wastage_percent=7.5)

        # Sanity checks
        assert bill.total_cement_kg > 0
        assert bill.total_water_kg > 0
        assert bill.total_cement_bags > 0
        assert bill.gross_concrete_volume_m3 > bill.net_concrete_volume_m3
        assert bill.total_scm_kg > 0

        report = bill.format_report()
        assert "IS 10262" in report

    def test_aci_full_pipeline(self):
        result = design_mix_simple(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            nmsa=20,
            cement_type="TYPE_I",
        )

        td = MixDesignTransferData.from_mix_design_result(result, cement_bag_weight_kg=42.64)
        q = MaterialQuantifier(td)
        bill = q.quantify_by_volume(50.0, wastage_percent=10.0)

        assert bill.cement_bag_weight_kg == 42.64
        assert bill.gross_concrete_volume_m3 == pytest.approx(55.0)
        assert "ACI" in bill.format_report()


# ---------------------------------------------------------------------------
# Mix Ratio Quantifier (Nominal Mix Method)
# ---------------------------------------------------------------------------

class TestMixRatioQuantifier:
    """Test MixRatioQuantifier nominal mix proportioning and 0.035 m³/bag rule."""

    def test_one_bag_equals_0_035_cubic_meter(self):
        """1 bag of cement = 0.035 m³ volume."""
        from material_quantify import MixRatioQuantifier

        # If total dry volume of cement needed is 0.035 m³, it must yield exactly 1.0 bag
        # Mix 1:0:0 with dry_factor=1.0, 0% wastage, net_volume=0.035 m³
        q = MixRatioQuantifier(
            cement_ratio=1.0,
            sand_ratio=0.0,
            gravel_ratio=0.0,
            w_c_ratio=0.50,
            dry_volume_factor=1.0,
            cement_bag_volume_m3=0.035,
            cement_bag_weight_kg=50.0,
        )
        bill = q.quantify_by_volume(0.035, wastage_percent=0.0)
        assert bill.total_cement_bags == 1
        assert bill.total_cement_kg == pytest.approx(50.0)

        # 0.070 m³ cement dry volume -> exactly 2 bags
        bill2 = q.quantify_by_volume(0.070, wastage_percent=0.0)
        assert bill2.total_cement_bags == 2
        assert bill2.total_cement_kg == pytest.approx(100.0)

        # 0.036 m³ cement dry volume -> 2 bags (rounded up ceiling)
        bill3 = q.quantify_by_volume(0.036, wastage_percent=0.0)
        assert bill3.total_cement_bags == 2

    def test_m20_1_1_5_3_nominal_quantification(self):
        """Test M20 (1:1.5:3) nominal concrete mix."""
        from material_quantify import MixRatioQuantifier

        q = MixRatioQuantifier(
            cement_ratio=1.0,
            sand_ratio=1.5,
            gravel_ratio=3.0,
            w_c_ratio=0.50,
            dry_volume_factor=1.54,
            cement_bag_volume_m3=0.035,
            cement_bag_weight_kg=50.0,
            fine_agg_bulk_density_kg_m3=1600.0,
            coarse_agg_bulk_density_kg_m3=1500.0,
            label="M20 (1:1.5:3)",
        )
        # 10 m³ net volume, 5% wastage -> gross = 10.5 m³
        # Dry volume = 10.5 * 1.54 = 16.17 m³
        # Sum parts = 1 + 1.5 + 3 = 5.5
        bill = q.quantify_by_volume(10.0, wastage_percent=5.0)

        assert bill.net_concrete_volume_m3 == 10.0
        assert bill.wastage_percent == 5.0
        assert bill.gross_concrete_volume_m3 == pytest.approx(10.5)

        # Cement: (1 / 5.5) * 16.17 = 2.94 m³
        # Bags = 2.94 / 0.035 = 84.0 bags -> 84 bags
        # Cement mass = 84 * 50 = 4200.0 kg
        assert bill.total_cement_bags == 84
        assert bill.total_cement_kg == pytest.approx(4200.0, rel=1e-3)

        # Sand: (1.5 / 5.5) * 16.17 = 4.41 m³
        # Sand mass = 4.41 * 1600 = 7056.0 kg
        assert bill.total_fine_aggregate_bulk_m3 == pytest.approx(4.41, rel=1e-3)
        assert bill.total_fine_aggregate_kg == pytest.approx(7056.0, rel=1e-3)

        # Coarse Agg: (3 / 5.5) * 16.17 = 8.82 m³
        # Coarse Agg mass = 8.82 * 1500 = 13230.0 kg
        assert bill.total_coarse_aggregate_bulk_m3 == pytest.approx(8.82, rel=1e-3)
        assert bill.total_coarse_aggregate_kg == pytest.approx(13230.0, rel=1e-3)

        # Water: 4200 * 0.5 = 2100.0 kg / Liters
        assert bill.total_water_kg == pytest.approx(2100.0, rel=1e-3)
        assert bill.total_water_liters == pytest.approx(2100.0, rel=1e-3)

    def test_m15_1_2_4_quantification(self):
        """Test M15 (1:2:4) nominal mix."""
        from material_quantify import MixRatioQuantifier

        q = MixRatioQuantifier(
            cement_ratio=1.0,
            sand_ratio=2.0,
            gravel_ratio=4.0,
            w_c_ratio=0.55,
            dry_volume_factor=1.54,
            label="M15 (1:2:4)",
        )
        bill = q.quantify_by_volume(1.0, wastage_percent=0.0)
        # Gross = 1.0 m³, Dry vol = 1.54 m³
        # Sum = 7.0
        # Cement vol = (1/7)*1.54 = 0.22 m³
        # Bags = 0.22 / 0.035 = 6.2857 -> 7 bags (ceil)
        assert bill.total_cement_bags == 7
        assert bill.total_fine_aggregate_bulk_m3 == pytest.approx((2 / 7) * 1.54, rel=1e-3)
        assert bill.total_coarse_aggregate_bulk_m3 == pytest.approx((4 / 7) * 1.54, rel=1e-3)

    def test_mortar_1_4_quantification(self):
        """Test Mortar 1:4 mix (no coarse aggregate, dry factor 1.33)."""
        from material_quantify import MixRatioQuantifier

        q = MixRatioQuantifier(
            cement_ratio=1.0,
            sand_ratio=4.0,
            gravel_ratio=0.0,
            w_c_ratio=0.55,
            dry_volume_factor=1.33,
            label="Mortar 1:4",
        )
        bill = q.quantify_by_volume(5.0, wastage_percent=5.0)

        # Gross = 5.25 m³, Dry vol = 5.25 * 1.33 = 6.9825 m³
        # Sum = 5.0
        # Cement vol = 6.9825 / 5 = 1.3965 m³
        # Bags = 1.3965 / 0.035 = 39.9 -> 40 bags
        assert bill.total_cement_bags == 40
        assert bill.total_coarse_aggregate_kg == 0.0
        assert bill.total_coarse_aggregate_bulk_m3 == 0.0
        assert bill.total_fine_aggregate_bulk_m3 == pytest.approx((4 / 5) * 6.9825, rel=1e-3)

    def test_presets_loading(self):
        """Test creating quantifiers from presets."""
        from material_quantify import MixRatioQuantifier, MIX_RATIO_PRESETS

        for preset_name in MIX_RATIO_PRESETS:
            q = MixRatioQuantifier.from_preset(preset_name)
            bill = q.quantify_by_volume(1.0, wastage_percent=5.0)
            assert bill.total_cement_bags > 0
            assert bill.total_fine_aggregate_kg > 0

    def test_quantify_by_elements(self):
        """Test MixRatioQuantifier with structural elements."""
        from material_quantify import MixRatioQuantifier, StructuralElement

        q = MixRatioQuantifier.from_preset("M20 (1:1.5:3)")
        elements = [
            StructuralElement("footing", 2.0, 2.0, 0.5, quantity=2),  # 4 m³
            StructuralElement("slab", 6.0, 4.0, 0.15, quantity=1),   # 3.6 m³
        ]
        bill = q.quantify_by_elements(elements, wastage_percent=5.0)
        assert bill.net_concrete_volume_m3 == pytest.approx(7.6)
        assert bill.gross_concrete_volume_m3 == pytest.approx(7.6 * 1.05)
        assert bill.total_cement_bags > 0

    def test_invalid_parameters_raise(self):
        """Test validation and error raising."""
        from material_quantify import MixRatioQuantifier

        with pytest.raises(ValueError, match="Cement ratio must be positive"):
            MixRatioQuantifier(cement_ratio=0.0)

        with pytest.raises(ValueError, match="Sand ratio must be non-negative"):
            MixRatioQuantifier(sand_ratio=-1.0)

        with pytest.raises(ValueError, match="Dry volume factor must be positive"):
            MixRatioQuantifier(dry_volume_factor=0.0)

        with pytest.raises(ValueError, match="Cement bag volume must be positive"):
            MixRatioQuantifier(cement_bag_volume_m3=-0.035)

        q = MixRatioQuantifier()
        with pytest.raises(ValueError, match="Volume must be positive"):
            q.quantify_by_volume(0.0)

        with pytest.raises(ValueError, match="Wastage must be non-negative"):
            q.quantify_by_volume(10.0, wastage_percent=-5.0)

        with pytest.raises(ValueError, match="At least one"):
            q.quantify_by_elements([])

    def test_report_formatting(self):
        """Test that report formatting works cleanly for mix ratio bills."""
        from material_quantify import MixRatioQuantifier

        q = MixRatioQuantifier.from_preset("M20 (1:1.5:3)")
        bill = q.quantify_by_volume(10.0, wastage_percent=5.0)
        report = bill.format_report()

        assert "MATERIAL BILL OF QUANTITIES" in report
        assert "M20" in report
        assert "Cement" in report
        assert "Fine Aggregate" in report
