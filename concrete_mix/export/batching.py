"""Explicit SSD/design and moisture-adjusted field batching schedules."""
from __future__ import annotations

from concrete_mix.models.mix_result import MixDesignResult


MATERIAL_LABELS = {
    "water_kg": "Water", "cement_kg": "Cement", "scm_kg": "SCM",
    "fine_aggregate_kg": "Fine aggregate", "coarse_aggregate_kg": "Coarse aggregate",
    "admixture_kg": "Admixture",
}


def batching_schedule(result: MixDesignResult) -> dict:
    """Masses are kg/m³; totals scale once by the requested volume.

    ACI PRC-211.1-22 clause 4.7.8 / Table 5.3.9.1, IS 10262:2019 D-9.1
    and BRE 331:1997 clause 6 distinguish SSD design from mixer quantities.
    Missing field measurements remain None, not an assumed SSD schedule.
    """
    design = {
        "water_kg": result.water_kg,
        "cement_kg": result.cement_kg,
        "scm_kg": result.scm_kg,
        "fine_aggregate_kg": result.fine_aggregate_kg,
        "coarse_aggregate_kg": result.coarse_aggregate_kg,
        "admixture_kg": result.admixture_kg,
    }
    field = dict(design, water_kg=result.adjusted_water_kg,
                 fine_aggregate_kg=result.field_fine_aggregate_kg,
                 coarse_aggregate_kg=result.field_coarse_aggregate_kg)
    def totals(masses: dict) -> dict:
        return {key: value * result.volume_m3 if value is not None else None
                for key, value in masses.items()}
    return {
        "volume_m3": result.volume_m3,
        "design_ssd_per_m3": design,
        "field_per_m3": field,
        "design_ssd_batch_kg": totals(design),
        "field_batch_kg": totals(field),
        "design_ca_split_kg_per_m3": result.ca_split_kg,
        "design_ca_split_batch_kg": (
            {key: value * result.volume_m3 for key, value in result.ca_split_kg.items()}
            if result.ca_split_kg is not None else None),
        "admixture": {
            "type": result.admixture_type,
            "dosage_percent": result.admixture_dosage_percent,
            "water_reduction_percent": result.water_reduction_percent,
        },
        "missing_field_values": "Not assessed; verify aggregate moisture before batching.",
    }
