"""Data handoff model from Mix Design to Material Quantification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
        scm_type: Identity of the SCM ("ggbfs", "fly_ash", ...) so the bill
            and its invoice can name it rather than say "SCM"
        admixture_type: Identity of the admixture ("pce", "hrwra", ...), for
            the same reason as ``scm_type``
        ca_split_kg: DOE single-size coarse aggregate split (BRE 331:1997
            clause 5.5) as per-m³ masses keyed by size, e.g.
            ``{"10 mm": 460.0, "20 mm": 925.0}``. None when the design uses
            a single graded stock.
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

    # Purchasing density includes interparticle voids (ACI clause 4.7.7.2).
    # This default is an explicit project assumption, NOT a standard density.
    fine_agg_bulk_density_kg_m3: float = 1600.0
    fine_agg_bulk_density_basis: str = "Project assumption: as-delivered bulk density; verify on site"
    scm_type: str = "SCM (unspecified)"
    # Single-size subdivision is per-m³ and must scale with the pour, so it is
    # stored per-m³ here and scaled by the quantifier alongside the totals.
    ca_split_kg: Optional[dict[str, float]] = None
    admixture_type: str = "Admixture (unspecified)"

    @classmethod
    def from_mix_design_result(
        cls,
        result: MixDesignResult,
        cement_bag_weight_kg: float = 50.0,
        coarse_agg_bulk_density_kg_m3: float = 1600.0,
        fine_agg_sg: float = 2.65,
        coarse_agg_sg: float = 2.70,
        scm_type: Optional[str] = None,
    ) -> MixDesignTransferData:
        """Construct transfer data from a MixDesignResult.

        Args:
            result: The completed mix design result from Module 1
            cement_bag_weight_kg: 50 kg for IS, 42.64 kg (94 lb) for ACI
            coarse_agg_bulk_density_kg_m3: Dry rodded bulk density
            fine_agg_sg: Fine aggregate specific gravity
            coarse_agg_sg: Coarse aggregate specific gravity
            scm_type: Overrides the result's own SCM identity. Callers that
                hold a more specific label than the engine recorded (the CLI
                distinguishes "Fly Ash Class C" where the engine records the
                single ``fly_ash`` type) pass it here.
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
            scm_type=scm_type or result.scm_type or "SCM (unspecified)",
            ca_split_kg=dict(result.ca_split_kg) if result.ca_split_kg else None,
            admixture_type=(
                result.admixture_type or "Admixture (unspecified)"
            ),
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
            ("SCM type", self.scm_type, ""),
            ("Admixture type", self.admixture_type, ""),
            ("Air Content", f"{self.air_volume_percent:.1f}", "%"),
        ] + [
            (f"Coarse Aggregate ({size})", f"{kg:.1f}", "kg/m\u00b3")
            for size, kg in (self.ca_split_kg or {}).items()
        ]
