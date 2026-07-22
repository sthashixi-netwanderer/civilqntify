"""Embodied carbon estimation for concrete mix design."""

from __future__ import annotations

from concrete_mix.models.mix_result import MixDesignResult
from concrete_mix.utils.constants import (
    CARBON_CEMENT_OPC,
    CARBON_COARSE_AGG,
    CARBON_FINE_AGG,
    CARBON_FLY_ASH,
    CARBON_GGBFS,
    CARBON_SILICA_FUME,
    CARBON_WATER,
)


def estimate_carbon(
    result: MixDesignResult,
    scm_type: str = "fly_ash",
) -> float:
    """Estimate embodied carbon (kg CO₂) per m³ of concrete.

    Uses typical embodied carbon factors:
    - Cement (OPC): 0.90 kg CO₂/kg
    - Fly ash: 0.05 kg CO₂/kg
    - GGBFS: 0.08 kg CO₂/kg
    - Silica fume: 0.10 kg CO₂/kg
    - Fine aggregate: 0.005 kg CO₂/kg
    - Coarse aggregate: 0.007 kg CO₂/kg
    - Water: 0.0003 kg CO₂/kg

    Args:
        result: Mix design result
        scm_type: Type of SCM ("fly_ash", "ggbfs", "silica_fume")

    Returns:
        kg CO₂ per m³ of concrete
    """
    carbon = 0.0
    carbon += result.cement_kg * CARBON_CEMENT_OPC
    carbon += result.water_kg * CARBON_WATER
    carbon += result.fine_aggregate_kg * CARBON_FINE_AGG
    carbon += result.coarse_aggregate_kg * CARBON_COARSE_AGG

    if result.scm_kg > 0:
        scm_factors = {
            "fly_ash": CARBON_FLY_ASH,
            "ggbfs": CARBON_GGBFS,
            "silica_fume": CARBON_SILICA_FUME,
        }
        factor = scm_factors.get(scm_type, CARBON_FLY_ASH)
        carbon += result.scm_kg * factor

    return round(carbon, 1)


def carbon_savings_vs_opc(
    result: MixDesignResult,
    scm_type: str = "fly_ash",
) -> dict[str, float]:
    """Calculate carbon savings from SCM replacement.

    Returns:
        Dict with "baseline_kg_co2", "actual_kg_co2", "savings_kg_co2", "savings_percent"
    """
    # Baseline: all cement, no SCM
    baseline = result.total_cementitious_kg * CARBON_CEMENT_OPC
    baseline += result.water_kg * CARBON_WATER
    baseline += result.fine_aggregate_kg * CARBON_FINE_AGG
    baseline += result.coarse_aggregate_kg * CARBON_COARSE_AGG

    actual = estimate_carbon(result, scm_type)

    savings = baseline - actual
    savings_pct = (savings / baseline * 100) if baseline > 0 else 0.0

    return {
        "baseline_kg_co2": round(baseline, 1),
        "actual_kg_co2": round(actual, 1),
        "savings_kg_co2": round(savings, 1),
        "savings_percent": round(savings_pct, 1),
    }
