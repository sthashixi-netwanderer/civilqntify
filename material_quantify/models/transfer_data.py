"""Data handoff model from Mix Design to Material Quantification."""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.models.mix_result import MixDesignResult


@dataclass
class MixDesignTransferData:
    """Structured data transferred from Module 1 (Mix Design) to Module 2 (Quantification).

    Contains batch weights per unit volume (1 m³) and metadata needed
    for material quantification. All masses are in SSD condition unless
    prefixed with ``field_`` (moisture-adjusted batch weights).

    Attributes:
        code_used: Standard name (e.g. "ACI 211.1-91", "IS 10262:2019")
        cement_kg_per_m3: Cement mass per m³ (SSD basis)
        water_kg_per_m3: Water mass per m³ (design, before moisture correction)
        fine_aggregate_kg_per_m3: Fine aggregate mass per m³ (SSD)
        coarse_aggregate_kg_per_m3: Coarse aggregate mass per m³ (SSD)
        scm_kg_per_m3: Supplementary cementitious material mass per m³
        admixture_kg_per_m3: Chemical admixture mass per m³ (0 if none)
        air_volume_percent: Air content (%)
        w_c_ratio: Water-cement ratio
        target_mean_strength_mpa: Target mean strength (f'cr / ftm)
        field_water_kg_per_m3: Moisture-adjusted water per m³
        field_fine_aggregate_kg_per_m3: Moisture-adjusted FA per m³
        field_coarse_aggregate_kg_per_m3: Moisture-adjusted CA per m³
        cement_bag_weight_kg: Weight of one cement bag (50 kg IS, 94 lb ≈ 42.64 kg ACI)
        coarse_agg_bulk_density_kg_m3: Dry rodded bulk density of CA
        fine_agg_specific_gravity: SG of fine aggregate (for volume calc)
        coarse_agg_specific_gravity: SG of coarse aggregate (for volume calc)
    """

    code_used: str
    cement_kg_per_m3: float
    water_kg_per_m3: float
    fine_aggregate_kg_per_m3: float
    coarse_aggregate_kg_per_m3: float
    scm_kg_per_m3: float
    admixture_kg_per_m3: float
    air_volume_percent: float
    w_c_ratio: float
    target_mean_strength_mpa: float
    field_water_kg_per_m3: float
    field_fine_aggregate_kg_per_m3: float
    field_coarse_aggregate_kg_per_m3: float
    cement_bag_weight_kg: float
    coarse_agg_bulk_density_kg_m3: float
    fine_agg_specific_gravity: float
    coarse_agg_specific_gravity: float

    @classmethod
    def from_mix_design_result(
        cls,
        result: MixDesignResult,
        cement_bag_weight_kg: float = 50.0,
        coarse_agg_bulk_density_kg_m3: float = 1600.0,
        fine_agg_sg: float = 2.65,
        coarse_agg_sg: float = 2.70,
    ) -> MixDesignTransferData:
        """Construct transfer data from a MixDesignResult.

        Args:
            result: The completed mix design result from Module 1
            cement_bag_weight_kg: 50 kg for IS, 42.64 kg (94 lb) for ACI
            coarse_agg_bulk_density_kg_m3: Dry rodded bulk density
            fine_agg_sg: Fine aggregate specific gravity
            coarse_agg_sg: Coarse aggregate specific gravity
        """
        is_aci = "ACI" in result.code_used.upper()
        bag_weight = 42.64 if is_aci else cement_bag_weight_kg

        return cls(
            code_used=result.code_used,
            cement_kg_per_m3=result.cement_kg,
            water_kg_per_m3=result.water_kg,
            fine_aggregate_kg_per_m3=result.fine_aggregate_kg,
            coarse_aggregate_kg_per_m3=result.coarse_aggregate_kg,
            scm_kg_per_m3=result.scm_kg,
            admixture_kg_per_m3=result.admixture_kg if result.admixture_kg is not None else 0.0,
            air_volume_percent=result.air_volume_percent,
            w_c_ratio=result.w_c_ratio,
            target_mean_strength_mpa=result.target_mean_strength_mpa,
            field_water_kg_per_m3=result.adjusted_water_kg if result.adjusted_water_kg is not None else result.water_kg,
            field_fine_aggregate_kg_per_m3=result.field_fine_aggregate_kg if result.field_fine_aggregate_kg is not None else result.fine_aggregate_kg,
            field_coarse_aggregate_kg_per_m3=result.field_coarse_aggregate_kg if result.field_coarse_aggregate_kg is not None else result.coarse_aggregate_kg,
            cement_bag_weight_kg=bag_weight,
            coarse_agg_bulk_density_kg_m3=coarse_agg_bulk_density_kg_m3,
            fine_agg_specific_gravity=fine_agg_sg,
            coarse_agg_specific_gravity=coarse_agg_sg,
        )

    def with_overrides(self, **kwargs: float) -> MixDesignTransferData:
        """Return a new transfer data with specified fields overridden.

        Example:
            new_data = data.with_overrides(cement_kg_per_m3=400.0)
        """
        import dataclasses
        current = dataclasses.asdict(self)
        current.update(kwargs)
        return MixDesignTransferData(**current)

    def to_display_dict(self) -> list[tuple[str, str, str]]:
        """Return list of (label, value, unit) for display."""
        return [
            ("Standard", self.code_used, ""),
            ("Target Mean Strength", f"{self.target_mean_strength_mpa:.1f}", "MPa"),
            ("W/C Ratio", f"{self.w_c_ratio:.3f}", ""),
            ("Cement", f"{self.cement_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Water (design)", f"{self.water_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Water (field)", f"{self.field_water_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Fine Aggregate (SSD)", f"{self.fine_aggregate_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Fine Aggregate (field)", f"{self.field_fine_aggregate_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Coarse Aggregate (SSD)", f"{self.coarse_aggregate_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Coarse Aggregate (field)", f"{self.field_coarse_aggregate_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("SCM", f"{self.scm_kg_per_m3:.1f}", "kg/m\u00b3"),
            ("Air Content", f"{self.air_volume_percent:.1f}", "%"),
        ]
