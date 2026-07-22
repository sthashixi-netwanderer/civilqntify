"""Material quantification engine — calculates total material bill."""

from __future__ import annotations

import math

from material_quantify.models.bill import MaterialBill
from material_quantify.models.elements import StructuralElement
from material_quantify.models.transfer_data import MixDesignTransferData


class MaterialQuantifier:
    """Calculates total material quantities from mix design proportions.

    Takes mix design data (per m³) and project geometry, applies wastage,
    and produces a complete material bill of quantities.

    Usage::

        td = MixDesignTransferData.from_mix_design_result(result)
        quantifier = MaterialQuantifier(td)

        # Option 1: by total volume
        bill = quantifier.quantify_by_volume(25.0, wastage_percent=5.0)

        # Option 2: by element dimensions
        elements = [
            StructuralElement("footing", 2.0, 2.0, 0.5, quantity=4),
            StructuralElement("column", 0.4, 0.4, 3.0, quantity=8),
        ]
        bill = quantifier.quantify_by_elements(elements, wastage_percent=7.5)
    """

    def __init__(self, transfer_data: MixDesignTransferData) -> None:
        self._data = transfer_data
        self._overrides: dict[str, float] = {}

    def override(self, **kwargs: float) -> None:
        """Override specific mix design values before quantification.

        Example::
            quantifier.override(cement_kg_per_m3=400.0, water_kg_per_m3=200.0)
        """
        valid_fields = {
            "cement_kg_per_m3",
            "water_kg_per_m3",
            "fine_aggregate_kg_per_m3",
            "coarse_aggregate_kg_per_m3",
            "scm_kg_per_m3",
            "admixture_kg_per_m3",
            "field_water_kg_per_m3",
            "field_fine_aggregate_kg_per_m3",
            "field_coarse_aggregate_kg_per_m3",
            "cement_bag_weight_kg",
        }
        for key in kwargs:
            if key not in valid_fields:
                raise ValueError(
                    f"Cannot override '{key}'. Valid fields: {sorted(valid_fields)}"
                )
        self._overrides.update(kwargs)

    @property
    def effective_data(self) -> MixDesignTransferData:
        """Transfer data with overrides applied."""
        if not self._overrides:
            return self._data
        return self._data.with_overrides(**self._overrides)

    def quantify_by_volume(
        self,
        total_volume_m3: float,
        wastage_percent: float = 5.0,
    ) -> MaterialBill:
        """Quantify materials for a given total concrete volume.

        Args:
            total_volume_m3: Net concrete volume in m³
            wastage_percent: Wastage allowance (e.g. 5.0 for 5%)

        Returns:
            MaterialBill with all total quantities
        """
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
        """Quantify materials from structural element dimensions.

        Args:
            elements: List of structural elements with dimensions and quantities
            wastage_percent: Wastage allowance

        Returns:
            MaterialBill with all total quantities
        """
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
        """Core computation — scale per-m³ quantities to project volume."""
        td = self.effective_data
        gross_volume = net_volume_m3 * (1.0 + wastage_percent / 100.0)
        v = gross_volume

        # Material totals (using field batch weights for actual site quantities)
        cement_total = td.cement_kg_per_m3 * v
        water_total = td.field_water_kg_per_m3 * v
        fa_total = td.field_fine_aggregate_kg_per_m3 * v
        ca_total = td.field_coarse_aggregate_kg_per_m3 * v
        scm_total = td.scm_kg_per_m3 * v
        admixture_total = td.admixture_kg_per_m3 * v

        # Cement bags (round up)
        bags = math.ceil(cement_total / td.cement_bag_weight_kg)

        # Aggregate bulk volumes
        fa_bulk_m3 = fa_total / (td.fine_agg_specific_gravity * 1000.0) if td.fine_agg_specific_gravity > 0 else 0.0
        ca_bulk_m3 = ca_total / td.coarse_agg_bulk_density_kg_m3 if td.coarse_agg_bulk_density_kg_m3 > 0 else 0.0

        return MaterialBill(
            net_concrete_volume_m3=net_volume_m3,
            wastage_percent=wastage_percent,
            gross_concrete_volume_m3=gross_volume,
            total_cement_kg=round(cement_total, 1),
            total_cement_bags=bags,
            cement_bag_weight_kg=td.cement_bag_weight_kg,
            total_water_kg=round(water_total, 1),
            total_water_liters=round(water_total, 1),
            total_fine_aggregate_kg=round(fa_total, 1),
            total_fine_aggregate_bulk_m3=round(fa_bulk_m3, 3),
            total_coarse_aggregate_kg=round(ca_total, 1),
            total_coarse_aggregate_bulk_m3=round(ca_bulk_m3, 3),
            total_scm_kg=round(scm_total, 1),
            total_admixture_kg=round(admixture_total, 3),
            transfer_data=td,
        )
