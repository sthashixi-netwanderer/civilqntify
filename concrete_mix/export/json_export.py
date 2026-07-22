"""JSON export for concrete mix design results."""

from __future__ import annotations

import json

from concrete_mix.models.mix_result import MixDesignResult


def export_to_json(result: MixDesignResult, indent: int = 2) -> str:
    """Export mix design result to JSON string.

    Returns:
        JSON-formatted string with all mix proportions and steps
    """
    data = {
        "code": result.code_used,
        "target_mean_strength_mpa": result.target_mean_strength_mpa,
        "w_c_ratio": result.w_c_ratio,
        "proportions_per_m3": {
            "water_kg": result.water_kg,
            "cement_kg": result.cement_kg,
            "scm_kg": result.scm_kg,
            "total_cementitious_kg": result.total_cementitious_kg,
            "fine_aggregate_kg": result.fine_aggregate_kg,
            "coarse_aggregate_kg": result.coarse_aggregate_kg,
            "total_aggregate_kg": result.total_aggregate_kg,
            "air_volume_percent": result.air_volume_percent,
        },
        "calculation_steps": [
            {
                "step": s.step_number,
                "description": s.description,
                "formula": s.formula,
                "inputs": s.inputs,
                "result": s.result,
                "unit": s.unit,
                "clause_ref": s.clause_ref,
            }
            for s in result.steps
        ],
        "warnings": list(result.warnings),
    }

    if result.cost_per_m3 is not None:
        data["cost_estimate_usd_per_m3"] = result.cost_per_m3
    if result.carbon_kg_co2_per_m3 is not None:
        data["carbon_estimate_kg_co2_per_m3"] = result.carbon_kg_co2_per_m3

    return json.dumps(data, indent=indent)
