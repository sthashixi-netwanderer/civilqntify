"""Deterministic project cost estimation shared by the GUI and reports.

The calculation mirrors the Cost Estimation tab: material quantities come from a
``MaterialBill`` (or any object exposing the same fields), prices are entered in
Ghana cedis, and overhead/profit and contingency are applied to the same bases
shown by the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ProjectMaterialPrices:
    """Material unit prices used by the Cost Estimation tab (GH₵)."""

    cement_per_bag: float = 85.0
    fine_aggregate_per_m3: float = 350.0
    coarse_aggregate_per_m3: float = 400.0
    water_per_1000_liters: float = 15.0
    admixture_per_kg: float = 12.0


@dataclass(frozen=True)
class ProjectCostOptions:
    """Additional project-cost inputs used by the Cost Estimation tab."""

    labour_count: float = 5.0
    labour_cost_per_unit: float = 150.0
    transport_per_m3: float = 80.0
    plant_overhead_percent: float = 10.0
    profit_percent: float = 15.0
    contingency_percent: float = 5.0


def estimate_project_cost(
    bill: Any,
    prices: ProjectMaterialPrices | None = None,
    options: ProjectCostOptions | None = None,
    project_info: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Calculate the project-cost result displayed by the application.

    Args:
        bill: ``MaterialBill`` or a compatible object containing the quantities
            populated in the Cost Estimation tab.
        prices: Material prices in Ghana cedis.
        options: Labour, transport, overhead, profit, and contingency inputs.
        project_info: Optional report metadata copied into the result.

    Returns:
        The same dictionary schema consumed by ``CostResultPanel``.
    """
    prices = prices or ProjectMaterialPrices()
    options = options or ProjectCostOptions()

    gross_volume = float(bill.gross_concrete_volume_m3)
    if gross_volume <= 0:
        raise ValueError("Total volume must be greater than zero")

    cement_cost = float(bill.total_cement_bags) * prices.cement_per_bag
    fine_aggregate_cost = (
        float(bill.total_fine_aggregate_bulk_m3) * prices.fine_aggregate_per_m3
    )
    coarse_aggregate_cost = (
        float(bill.total_coarse_aggregate_bulk_m3) * prices.coarse_aggregate_per_m3
    )
    water_cost = (
        float(bill.total_water_liters) / 1000.0 * prices.water_per_1000_liters
    )
    admixture_cost = float(bill.total_admixture_kg) * prices.admixture_per_kg
    total_material = (
        cement_cost
        + fine_aggregate_cost
        + coarse_aggregate_cost
        + water_cost
        + admixture_cost
    )

    material_cost_per_m3 = total_material / gross_volume
    labour = options.labour_count * options.labour_cost_per_unit
    transport = options.transport_per_m3 * gross_volume
    overhead_profit_rate = (
        options.plant_overhead_percent + options.profit_percent
    ) / 100.0
    overhead_profit = (total_material + labour + transport) * overhead_profit_rate
    subtotal = total_material + labour + transport + overhead_profit
    contingency = subtotal * options.contingency_percent / 100.0
    grand_total = subtotal + contingency
    cost_per_bag = (
        grand_total / float(bill.total_cement_bags)
        if bill.total_cement_bags > 0
        else 0.0
    )

    return {
        "material_cost_per_m3": material_cost_per_m3,
        "total_material_cost": total_material,
        "total_project_cost": grand_total,
        "cost_per_bag": cost_per_bag,
        "material_breakdown": [
            {
                "name": "Cement",
                "qty": float(bill.total_cement_bags),
                "unit": "bags",
                "kind": "count",
                "unit_price": prices.cement_per_bag,
                "total": cement_cost,
            },
            {
                "name": "Fine Aggregate",
                "qty": float(bill.total_fine_aggregate_bulk_m3),
                "unit": "m³",
                "kind": "volume",
                "unit_price": prices.fine_aggregate_per_m3,
                "total": fine_aggregate_cost,
            },
            {
                "name": "Coarse Aggregate",
                "qty": float(bill.total_coarse_aggregate_bulk_m3),
                "unit": "m³",
                "kind": "volume",
                "unit_price": prices.coarse_aggregate_per_m3,
                "total": coarse_aggregate_cost,
            },
            {
                "name": "Water",
                "qty": float(bill.total_water_liters),
                "unit": "L",
                "kind": "water",
                "unit_price": prices.water_per_1000_liters,
                "total": water_cost,
            },
            {
                "name": "Admixture",
                "qty": float(bill.total_admixture_kg),
                "unit": "kg",
                "kind": "mass",
                "unit_price": prices.admixture_per_kg,
                "total": admixture_cost,
            },
        ],
        "summary_rows": [
            {"label": "Material Cost", "amount": total_material},
            {"label": "Labour & Transport", "amount": labour + transport},
            {
                "label": f"Overhead & Profit ({overhead_profit_rate * 100:.0f}%)",
                "amount": overhead_profit,
            },
            {"label": "Subtotal", "amount": subtotal, "is_subtotal": True},
            {
                "label": f"Contingency ({options.contingency_percent:.0f}%)",
                "amount": contingency,
            },
            {"label": "GRAND TOTAL", "amount": grand_total, "is_total": True},
        ],
        "project_info": dict(project_info or {}),
    }
