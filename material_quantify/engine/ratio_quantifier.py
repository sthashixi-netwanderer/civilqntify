"""Mix Ratio material quantification engine — calculates material quantities from volumetric ratios.

Supports nominal concrete mixes (e.g., M25 1:1:2, M20 1:1.5:3, M15 1:2:4, M10 1:3:6)
and mortar mixes (e.g., 1:3, 1:4, 1:5, 1:6) or custom volumetric ratios.

Formulas & Principles:
- Net wet volume = V_net (m³)
- Gross wet volume = V_net × (1 + wastage% / 100)
- Dry volume of materials = Gross wet volume × Dry volume factor (typically 1.54 for concrete, 1.33 for mortar)
- Total ratio parts = Cement parts + Sand parts + Coarse aggregate parts
- Cement volume = (Cement parts / Total parts) × Dry volume
- Cement bags = Cement volume (m³) / 0.035 m³/bag (1 bag of cement = 0.035 m³)
- Cement mass = Cement bags (exact) × Bag weight (50 kg)
- Fine aggregate volume = (Sand parts / Total parts) × Dry volume
- Fine aggregate mass = Fine aggregate volume × Sand bulk density (kg/m³)
- Coarse aggregate volume = (Coarse parts / Total parts) × Dry volume
- Coarse aggregate mass = Coarse aggregate volume × Coarse aggregate bulk density (kg/m³)
- Water mass/volume = Cement mass × Water-Cement ratio (w/c)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from material_quantify.models.bill import MaterialBill
from material_quantify.models.elements import StructuralElement
from material_quantify.models.transfer_data import MixDesignTransferData


@dataclass(frozen=True)
class MixRatioPreset:
    """Standard nominal mix ratio preset."""

    name: str
    cement_ratio: float
    sand_ratio: float
    gravel_ratio: float
    w_c_ratio: float
    dry_volume_factor: float
    description: str
    target_fck_mpa: float = 20.0
    is_mortar: bool = False


# Standard Nominal Concrete & Mortar Presets
MIX_RATIO_PRESETS: dict[str, MixRatioPreset] = {
    "M25 (1:1:2)": MixRatioPreset(
        name="M25 (1:1:2)",
        cement_ratio=1.0,
        sand_ratio=1.0,
        gravel_ratio=2.0,
        w_c_ratio=0.45,
        dry_volume_factor=1.54,
        description="Heavy structural RCC, water retaining structures, heavily loaded columns",
        target_fck_mpa=25.0,
    ),
    "M20 (1:1.5:3)": MixRatioPreset(
        name="M20 (1:1.5:3)",
        cement_ratio=1.0,
        sand_ratio=1.5,
        gravel_ratio=3.0,
        w_c_ratio=0.50,
        dry_volume_factor=1.54,
        description="Standard reinforced concrete for slabs, beams, columns, footings",
        target_fck_mpa=20.0,
    ),
    "M15 (1:2:4)": MixRatioPreset(
        name="M15 (1:2:4)",
        cement_ratio=1.0,
        sand_ratio=2.0,
        gravel_ratio=4.0,
        w_c_ratio=0.55,
        dry_volume_factor=1.54,
        description="General concrete work, bed concrete, paths, small slabs",
        target_fck_mpa=15.0,
    ),
    "M10 (1:3:6)": MixRatioPreset(
        name="M10 (1:3:6)",
        cement_ratio=1.0,
        sand_ratio=3.0,
        gravel_ratio=6.0,
        w_c_ratio=0.60,
        dry_volume_factor=1.54,
        description="Plain cement concrete (PCC), leveling courses, foundation bed",
        target_fck_mpa=10.0,
    ),
    "M7.5 (1:4:8)": MixRatioPreset(
        name="M7.5 (1:4:8)",
        cement_ratio=1.0,
        sand_ratio=4.0,
        gravel_ratio=8.0,
        w_c_ratio=0.65,
        dry_volume_factor=1.54,
        description="Mass concrete, simple foundation base",
        target_fck_mpa=7.5,
    ),
    "M5 (1:5:10)": MixRatioPreset(
        name="M5 (1:5:10)",
        cement_ratio=1.0,
        sand_ratio=5.0,
        gravel_ratio=10.0,
        w_c_ratio=0.70,
        dry_volume_factor=1.54,
        description="Lean concrete sub-base",
        target_fck_mpa=5.0,
    ),
    "Mortar 1:3": MixRatioPreset(
        name="Mortar 1:3",
        cement_ratio=1.0,
        sand_ratio=3.0,
        gravel_ratio=0.0,
        w_c_ratio=0.50,
        dry_volume_factor=1.33,
        description="Rich mortar, pointing, waterproof plaster, structural repair",
        target_fck_mpa=15.0,
        is_mortar=True,
    ),
    "Mortar 1:4": MixRatioPreset(
        name="Mortar 1:4",
        cement_ratio=1.0,
        sand_ratio=4.0,
        gravel_ratio=0.0,
        w_c_ratio=0.55,
        dry_volume_factor=1.33,
        description="External plastering, masonry for high load walls",
        target_fck_mpa=10.0,
        is_mortar=True,
    ),
    "Mortar 1:5": MixRatioPreset(
        name="Mortar 1:5",
        cement_ratio=1.0,
        sand_ratio=5.0,
        gravel_ratio=0.0,
        w_c_ratio=0.60,
        dry_volume_factor=1.33,
        description="General brickwork and blockwork masonry",
        target_fck_mpa=7.5,
        is_mortar=True,
    ),
    "Mortar 1:6": MixRatioPreset(
        name="Mortar 1:6",
        cement_ratio=1.0,
        sand_ratio=6.0,
        gravel_ratio=0.0,
        w_c_ratio=0.65,
        dry_volume_factor=1.33,
        description="Internal plastering, non-load-bearing masonry",
        target_fck_mpa=5.0,
        is_mortar=True,
    ),
}


class MixRatioQuantifier:
    """Calculates material bill from nominal mix ratios and work volume.

    Usage::

        # Standard M20 (1:1.5:3) for 10 m³ concrete:
        quantifier = MixRatioQuantifier(
            cement_ratio=1.0,
            sand_ratio=1.5,
            gravel_ratio=3.0,
            w_c_ratio=0.50,
            dry_volume_factor=1.54,
            cement_bag_volume_m3=0.035,
        )
        bill = quantifier.quantify_by_volume(10.0, wastage_percent=5.0)

        # By structural elements:
        elements = [
            StructuralElement("slab", 10.0, 5.0, 0.15, quantity=1),
            StructuralElement("beam", 6.0, 0.3, 0.5, quantity=4),
        ]
        bill = quantifier.quantify_by_elements(elements, wastage_percent=5.0)
    """

    def __init__(
        self,
        cement_ratio: float = 1.0,
        sand_ratio: float = 1.5,
        gravel_ratio: float = 3.0,
        w_c_ratio: float = 0.50,
        dry_volume_factor: float = 1.54,
        cement_bag_volume_m3: float = 0.035,
        cement_bag_weight_kg: float = 50.0,
        fine_agg_bulk_density_kg_m3: float = 1600.0,
        coarse_agg_bulk_density_kg_m3: float = 1500.0,
        fine_agg_sg: float = 2.65,
        coarse_agg_sg: float = 2.70,
        label: str = "Mix Ratio",
        target_fck_mpa: float = 20.0,
    ) -> None:
        if cement_ratio <= 0:
            raise ValueError(f"Cement ratio must be positive, got {cement_ratio}")
        if sand_ratio < 0:
            raise ValueError(f"Sand ratio must be non-negative, got {sand_ratio}")
        if gravel_ratio < 0:
            raise ValueError(f"Gravel ratio must be non-negative, got {gravel_ratio}")
        if dry_volume_factor <= 0:
            raise ValueError(
                f"Dry volume factor must be positive, got {dry_volume_factor}"
            )
        if cement_bag_volume_m3 <= 0:
            raise ValueError(
                f"Cement bag volume must be positive, got {cement_bag_volume_m3}"
            )
        if cement_bag_weight_kg <= 0:
            raise ValueError(
                f"Cement bag weight must be positive, got {cement_bag_weight_kg}"
            )
        if w_c_ratio <= 0:
            raise ValueError(f"W/C ratio must be positive, got {w_c_ratio}")

        self.cement_ratio = float(cement_ratio)
        self.sand_ratio = float(sand_ratio)
        self.gravel_ratio = float(gravel_ratio)
        self.w_c_ratio = float(w_c_ratio)
        self.dry_volume_factor = float(dry_volume_factor)
        self.cement_bag_volume_m3 = float(cement_bag_volume_m3)
        self.cement_bag_weight_kg = float(cement_bag_weight_kg)
        self.fine_agg_bulk_density_kg_m3 = float(fine_agg_bulk_density_kg_m3)
        self.coarse_agg_bulk_density_kg_m3 = float(coarse_agg_bulk_density_kg_m3)
        self.fine_agg_sg = float(fine_agg_sg)
        self.coarse_agg_sg = float(coarse_agg_sg)
        self.label = label
        self.target_fck_mpa = float(target_fck_mpa)

    @property
    def total_ratio_parts(self) -> float:
        """Sum of ratio parts (e.g. 1 + 1.5 + 3 = 5.5)."""
        return self.cement_ratio + self.sand_ratio + self.gravel_ratio

    @classmethod
    def from_preset(
        cls,
        preset_name: str,
        cement_bag_volume_m3: float = 0.035,
        cement_bag_weight_kg: float = 50.0,
        fine_agg_bulk_density_kg_m3: float = 1600.0,
        coarse_agg_bulk_density_kg_m3: float = 1500.0,
    ) -> MixRatioQuantifier:
        """Create a quantifier from a known preset name."""
        if preset_name not in MIX_RATIO_PRESETS:
            raise ValueError(
                f"Unknown preset '{preset_name}'. Valid: {list(MIX_RATIO_PRESETS.keys())}"
            )
        p = MIX_RATIO_PRESETS[preset_name]
        return cls(
            cement_ratio=p.cement_ratio,
            sand_ratio=p.sand_ratio,
            gravel_ratio=p.gravel_ratio,
            w_c_ratio=p.w_c_ratio,
            dry_volume_factor=p.dry_volume_factor,
            cement_bag_volume_m3=cement_bag_volume_m3,
            cement_bag_weight_kg=cement_bag_weight_kg,
            fine_agg_bulk_density_kg_m3=fine_agg_bulk_density_kg_m3,
            coarse_agg_bulk_density_kg_m3=coarse_agg_bulk_density_kg_m3,
            label=p.name,
            target_fck_mpa=p.target_fck_mpa,
        )

    def quantify_by_volume(
        self,
        total_volume_m3: float,
        wastage_percent: float = 5.0,
    ) -> MaterialBill:
        """Quantify materials for a given total concrete/mortar volume in m³."""
        if total_volume_m3 <= 0:
            raise ValueError(f"Volume must be positive, got {total_volume_m3}")
        if wastage_percent < 0:
            raise ValueError(f"Wastage must be non-negative, got {wastage_percent}")

        return self._compute(total_volume_m3, wastage_percent)

    def quantify_by_elements(
        self,
        elements: list[StructuralElement],
        wastage_percent: float = 5.0,
    ) -> MaterialBill:
        """Quantify materials from structural element dimensions."""
        if not elements:
            raise ValueError("At least one structural element is required")

        net_volume = sum(e.total_volume_m3 for e in elements)
        if net_volume <= 0:
            raise ValueError("Total element volume must be positive")

        return self._compute(net_volume, wastage_percent)

    def _compute(
        self,
        net_volume_m3: float,
        wastage_percent: float,
    ) -> MaterialBill:
        """Core calculation using dry volume factor and volumetric proportions."""
        gross_volume = net_volume_m3 * (1.0 + wastage_percent / 100.0)
        total_dry_volume = gross_volume * self.dry_volume_factor
        sum_parts = self.total_ratio_parts

        if sum_parts <= 0:
            raise ValueError("Sum of ratio parts must be greater than 0")

        # 1. Cement volume & bags (1 bag = cement_bag_volume_m3, e.g. 0.035 m³)
        cement_vol_m3 = (self.cement_ratio / sum_parts) * total_dry_volume
        cement_bags_exact = cement_vol_m3 / self.cement_bag_volume_m3
        cement_bags = math.ceil(cement_bags_exact)
        cement_total_kg = cement_bags_exact * self.cement_bag_weight_kg

        # 2. Fine aggregate (Sand) volume & mass
        sand_vol_m3 = (self.sand_ratio / sum_parts) * total_dry_volume
        sand_total_kg = sand_vol_m3 * self.fine_agg_bulk_density_kg_m3

        # 3. Coarse aggregate volume & mass (0 for mortar)
        gravel_vol_m3 = (self.gravel_ratio / sum_parts) * total_dry_volume
        gravel_total_kg = gravel_vol_m3 * self.coarse_agg_bulk_density_kg_m3

        # 4. Water (mass in kg and liters, 1 kg = 1 L)
        water_total_kg = cement_total_kg * self.w_c_ratio
        water_total_liters = water_total_kg

        # 5. Build per-m³ equivalent transfer data for reporting & cost estimation
        # Per m³ gross:
        unit_dry_vol = 1.0 * self.dry_volume_factor
        c_m3_vol = (self.cement_ratio / sum_parts) * unit_dry_vol
        c_m3_kg = (c_m3_vol / self.cement_bag_volume_m3) * self.cement_bag_weight_kg
        w_m3_kg = c_m3_kg * self.w_c_ratio
        fa_m3_vol = (self.sand_ratio / sum_parts) * unit_dry_vol
        fa_m3_kg = fa_m3_vol * self.fine_agg_bulk_density_kg_m3
        ca_m3_vol = (self.gravel_ratio / sum_parts) * unit_dry_vol
        ca_m3_kg = ca_m3_vol * self.coarse_agg_bulk_density_kg_m3

        ratio_str = f"{self.cement_ratio:g}:{self.sand_ratio:g}"
        if self.gravel_ratio > 0:
            ratio_str += f":{self.gravel_ratio:g}"

        code_label = f"{self.label} ({ratio_str})" if self.label != ratio_str else f"Mix Ratio {ratio_str}"

        td = MixDesignTransferData(
            code_used=code_label,
            target_mean_strength_mpa=self.target_fck_mpa,
            w_c_ratio=self.w_c_ratio,
            cement_kg_per_m3=round(c_m3_kg, 1),
            water_kg_per_m3=round(w_m3_kg, 1),
            field_water_kg_per_m3=round(w_m3_kg, 1),
            fine_aggregate_kg_per_m3=round(fa_m3_kg, 1),
            field_fine_aggregate_kg_per_m3=round(fa_m3_kg, 1),
            coarse_aggregate_kg_per_m3=round(ca_m3_kg, 1),
            field_coarse_aggregate_kg_per_m3=round(ca_m3_kg, 1),
            scm_kg_per_m3=0.0,
            admixture_kg_per_m3=0.0,
            air_volume_percent=1.0,
            fine_agg_specific_gravity=self.fine_agg_sg,
            coarse_agg_specific_gravity=self.coarse_agg_sg,
            cement_bag_weight_kg=self.cement_bag_weight_kg,
            coarse_agg_bulk_density_kg_m3=self.coarse_agg_bulk_density_kg_m3,
        )

        return MaterialBill(
            net_concrete_volume_m3=net_volume_m3,
            wastage_percent=wastage_percent,
            gross_concrete_volume_m3=gross_volume,
            total_cement_kg=round(cement_total_kg, 1),
            total_cement_bags=cement_bags,
            cement_bag_weight_kg=self.cement_bag_weight_kg,
            total_water_kg=round(water_total_kg, 1),
            total_water_liters=round(water_total_liters, 1),
            total_fine_aggregate_kg=round(sand_total_kg, 1),
            total_fine_aggregate_bulk_m3=round(sand_vol_m3, 3),
            total_coarse_aggregate_kg=round(gravel_total_kg, 1),
            total_coarse_aggregate_bulk_m3=round(gravel_vol_m3, 3),
            total_scm_kg=0.0,
            total_admixture_kg=0.0,
            transfer_data=td,
        )
