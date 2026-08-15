"""Material bill of quantities — the output of Module 2."""

from __future__ import annotations

from dataclasses import dataclass

from material_quantify.models.transfer_data import MixDesignTransferData


@dataclass(frozen=True)
class MaterialBill:
    """Complete material bill of quantities for a concrete pour.

    All totals are for the gross volume (including wastage).

    Attributes:
        net_concrete_volume_m3: Sum of structural element volumes
        wastage_percent: Wastage allowance percentage
        gross_concrete_volume_m3: Net volume × (1 + wastage/100)
        total_cement_kg: Total cement required (kg)
        total_cement_bags: Number of bags (rounded up)
        cement_bag_weight_kg: Weight per bag
        total_water_kg: Total water (kg)
        total_water_liters: Total water (L) — 1 kg = 1 L
        total_fine_aggregate_kg: Total fine aggregate (kg)
        total_fine_aggregate_bulk_m3: Total fine aggregate bulk volume (m³)
        total_coarse_aggregate_kg: Total coarse aggregate (kg)
        total_coarse_aggregate_bulk_m3: Total coarse aggregate bulk volume (m³)
        total_scm_kg: Total supplementary cementitious material (kg)
        total_admixture_kg: Total chemical admixture (kg)
        transfer_data: Reference to the mix design data used
    """

    net_concrete_volume_m3: float
    wastage_percent: float
    gross_concrete_volume_m3: float

    total_cement_kg: float
    total_cement_bags: float
    cement_bag_weight_kg: float

    total_water_kg: float
    total_water_liters: float

    total_fine_aggregate_kg: float
    total_fine_aggregate_bulk_m3: float

    total_coarse_aggregate_kg: float
    total_coarse_aggregate_bulk_m3: float

    total_scm_kg: float
    total_admixture_kg: float

    transfer_data: MixDesignTransferData

    def format_report(self) -> str:
        """Generate a human-readable material bill report."""
        td = self.transfer_data
        lines: list[str] = []
        sep = "=" * 65

        lines.append(sep)
        lines.append("  MATERIAL BILL OF QUANTITIES")
        lines.append(sep)
        lines.append("")

        lines.append("MIX DESIGN REFERENCE")
        lines.append("-" * 40)
        lines.append(f"  Standard:              {td.code_used}")
        lines.append(f"  Target Strength:       {td.target_mean_strength_mpa:.1f} MPa")
        lines.append(f"  W/C Ratio:             {td.w_c_ratio:.3f}")
        lines.append(f"  Proportions basis:     per 1 m\u00b3 (field batch weights)")
        lines.append("")

        lines.append("VOLUME SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Net concrete volume:   {self.net_concrete_volume_m3:.3f} m\u00b3")
        lines.append(f"  Wastage factor:        {self.wastage_percent:.1f}%")
        lines.append(f"  Gross concrete volume: {self.gross_concrete_volume_m3:.3f} m\u00b3")
        lines.append("")

        lines.append("TOTAL MATERIAL QUANTITIES")
        lines.append("-" * 65)
        lines.append(f"  {'Material':<25} {'Total (kg)':<14} {'Volume':<14} {'Bags':<10}")
        lines.append(f"  {'-'*25} {'-'*14} {'-'*14} {'-'*10}")
        lines.append(
            f"  {'Cement':<25} {self.total_cement_kg:<14.1f} {'--':<14} "
            f"{self.total_cement_bags:<10.0f}"
        )
        lines.append(f"  {'Water':<25} {self.total_water_kg:<14.1f} {f'{self.total_water_liters:.1f} L':<14} {'--':<10}")
        lines.append(
            f"  {'Fine Aggregate':<25} {self.total_fine_aggregate_kg:<14.1f} "
            f"{f'{self.total_fine_aggregate_bulk_m3:.3f} m³':<14} {'--':<10}"
        )
        lines.append(
            f"  {'Coarse Aggregate':<25} {self.total_coarse_aggregate_kg:<14.1f} "
            f"{f'{self.total_coarse_aggregate_bulk_m3:.3f} m³':<14} {'--':<10}"
        )
        if self.total_scm_kg > 0:
            lines.append(
                f"  {'SCM':<25} {self.total_scm_kg:<14.1f} {'--':<14} {'--':<10}"
            )
        if self.total_admixture_kg > 0:
            lines.append(
                f"  {'Admixture':<25} {self.total_admixture_kg:<14.3f} {'--':<14} {'--':<10}"
            )
        lines.append("")

        lines.append("CEMENT BAG SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Bag weight:            {self.cement_bag_weight_kg:.1f} kg")
        lines.append(f"  Total bags required:   {self.total_cement_bags:.0f}")
        lines.append("")

        lines.append(sep)
        return "\n".join(lines)
