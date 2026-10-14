"""CSV export for concrete mix design results."""

from __future__ import annotations

import csv
import io

from concrete_mix.models.mix_result import MixDesignResult
from concrete_mix.export.batching import batching_schedule


def export_to_csv(result: MixDesignResult) -> str:
    """Export mix design result to CSV string.

    Returns:
        CSV-formatted string with all mix proportions
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Parameter", "Value", "Unit"])
    writer.writerow(["Code", result.code_used, ""])
    writer.writerow(["Target Mean Strength", f"{result.target_mean_strength_mpa:.1f}", "MPa"])
    writer.writerow(["W/C Ratio", f"{result.w_c_ratio:.2f}", ""])
    writer.writerow(["Water", f"{result.water_kg:.1f}", "kg/m³"])
    writer.writerow(["Cement", f"{result.cement_kg:.1f}", "kg/m³"])
    writer.writerow(["SCM", f"{result.scm_kg:.1f}", "kg/m³"])
    writer.writerow(["Total Cementitious", f"{result.total_cementitious_kg:.1f}", "kg/m³"])
    writer.writerow(["Fine Aggregate", f"{result.fine_aggregate_kg:.1f}", "kg/m³"])
    writer.writerow(["Coarse Aggregate", f"{result.coarse_aggregate_kg:.1f}", "kg/m³"])
    writer.writerow(["Total Aggregate", f"{result.total_aggregate_kg:.1f}", "kg/m³"])
    writer.writerow(["Air Content", f"{result.air_volume_percent:.1f}", "%"])

    if result.cost_per_m3 is not None:
        writer.writerow(["Cost", f"{result.cost_per_m3:.2f}", "USD/m³"])
    if result.carbon_kg_co2_per_m3 is not None:
        writer.writerow(["Embodied Carbon", f"{result.carbon_kg_co2_per_m3:.1f}", "kg CO₂/m³"])

    schedule = batching_schedule(result)
    writer.writerow(["Requested batch volume", result.volume_m3, "m³"])
    for section, unit in (("design_ssd_per_m3", "kg/m³"), ("field_per_m3", "kg/m³"),
                          ("design_ssd_batch_kg", "kg"), ("field_batch_kg", "kg")):
        for key, value in schedule[section].items():
            writer.writerow([f"{section}: {key}", value if value is not None else "Not assessed", unit])
    for section in ("design_ca_split_kg_per_m3", "design_ca_split_batch_kg"):
        for key, value in (schedule[section] or {}).items():
            writer.writerow([f"{section}: {key}", value, "kg/m³" if section.endswith("per_m3") else "kg"])
    for key, value in schedule["admixture"].items():
        writer.writerow([f"Admixture {key}", value if value is not None else "Not assessed", ""])
    for warning in result.warnings:
        writer.writerow(["Warning", warning, ""])
    writer.writerow(["Field batching note", schedule["missing_field_values"], ""])
    return output.getvalue()
