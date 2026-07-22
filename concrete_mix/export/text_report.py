"""Human-readable text report for concrete mix design results."""

from __future__ import annotations

from concrete_mix.models.materials import GHANA_CEMENT_EQUIVALENTS, GRADING_ZONE_DESCRIPTIONS
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult


def generate_report(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
) -> str:
    """Generate a human-readable text report of the mix design.

    Includes input parameters, step-by-step calculations, final proportions,
    and warnings. Suitable for engineering review and documentation.

    Args:
        result: Mix design result
        inp: Optional input parameters for context

    Returns:
        Formatted text report string
    """
    lines: list[str] = []
    sep = "=" * 70

    # Header
    lines.append(sep)
    lines.append(f"  CONCRETE MIX DESIGN REPORT — {result.code_used}")
    lines.append(sep)
    lines.append("")

    # Input parameters
    if inp:
        lines.append("INPUT PARAMETERS")
        lines.append("-" * 40)
        lines.append(f"  Target strength (fck/f'c):    {inp.target_strength_mpa:.1f} MPa")
        lines.append(f"  Required slump:              {inp.slump_mm:.0f} mm")
        lines.append(f"  Cement type:                 {inp.cement.type.value}")
        lines.append(f"  Cement SG:                   {inp.cement.specific_gravity:.2f}")
        lines.append(f"  NMSA:                        {inp.nmsa} mm")
        lines.append(f"  Fine aggregate SG:           {inp.fine_aggregate.specific_gravity:.2f}")
        if inp.fine_aggregate.fineness_modulus:
            lines.append(f"  Fineness Modulus:            {inp.fine_aggregate.fineness_modulus:.2f}")
        if inp.fine_aggregate.grading_zone:
            lines.append(f"  Grading Zone:                {inp.fine_aggregate.grading_zone}")
            zone_info = GRADING_ZONE_DESCRIPTIONS.get(inp.fine_aggregate.grading_zone)
            if zone_info:
                lines.append(f"    ({zone_info['name']})")
        lines.append(f"  Coarse aggregate SG:         {inp.coarse_aggregate.specific_gravity:.2f}")
        lines.append(f"  Air-entrained:               {'Yes' if inp.air_entrained else 'No'}")
        lines.append(f"  Aggregate shape:             {inp.coarse_aggregate.shape.value}")
        if inp.exposure_class:
            lines.append(f"  Exposure class:              {inp.exposure_class}")
        if inp.scms:
            for scm in inp.scms:
                lines.append(f"  SCM: {scm.type.value} — {scm.replacement_percent:.0f}% replacement")
        if inp.admixture:
            lines.append(f"  Admixture: {inp.admixture.type} at {inp.admixture.dosage_percent:.1f}%")
            lines.append(f"    Water reduction: {inp.admixture.water_reduction_percent:.0f}%")
        lines.append("")

    # Calculation steps
    if result.steps:
        lines.append("CALCULATION STEPS")
        lines.append("-" * 40)
        for step in result.steps:
            lines.append(f"  Step {step.step_number}: {step.description}")
            lines.append(f"    Formula: {step.formula}")
            lines.append(f"    Inputs:  {step.inputs}")
            lines.append(f"    Result:  {step.result:.2f} {step.unit}")
            if step.clause_ref:
                lines.append(f"    Ref:     {step.clause_ref}")
            lines.append("")

    # Final mix proportions
    lines.append("FINAL MIX PROPORTIONS (per 1 m³)")
    lines.append("-" * 40)
    lines.append(f"  Target mean strength:     {result.target_mean_strength_mpa:.1f} MPa")
    lines.append(f"  W/C ratio:                {result.w_c_ratio:.2f}")
    lines.append(f"  Water:                    {result.water_kg:.1f} kg")
    lines.append(f"  Cement:                   {result.cement_kg:.1f} kg")
    if result.scm_kg > 0:
        lines.append(f"  SCM:                      {result.scm_kg:.1f} kg")
        lines.append(f"  Total cementitious:       {result.total_cementitious_kg:.1f} kg")
    lines.append(f"  Fine aggregate:           {result.fine_aggregate_kg:.1f} kg")
    lines.append(f"  Coarse aggregate:         {result.coarse_aggregate_kg:.1f} kg")
    lines.append(f"  Air content:              {result.air_volume_percent:.1f}%")
    lines.append(f"  Total aggregate:          {result.total_aggregate_kg:.1f} kg")
    lines.append("")

    # Ghana Cement Equivalent
    if inp:
        ghana_info = GHANA_CEMENT_EQUIVALENTS.get(inp.cement.type.value)
        if ghana_info:
            lines.append("GHANA CEMENT EQUIVALENT")
            lines.append("-" * 40)
            lines.append(f"  Cement Type:         {inp.cement.type.value}")
            lines.append(f"  Ghana Grade:         {ghana_info['ghana_grade']}")
            lines.append(f"  GS Specification:    {ghana_info['gs_spec']}")
            lines.append(f"  Typical Use:         {ghana_info['use']}")
            lines.append("")

    # Moisture Adjustment Report
    if result.adjusted_water_kg is not None:
        lines.append("MOISTURE ADJUSTMENT & FIELD BATCH WEIGHTS")
        lines.append("-" * 60)
        lines.append(f"  {'Material':<20} {'SSD (kg)':<12} {'Absorb %':<12} {'Moisture %':<12} {'Field (kg)':<12}")
        lines.append(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
        lines.append(f"  {'Cement':<20} {result.cement_kg:<12.1f} {'--':<12} {'--':<12} {result.cement_kg:<12.1f}")
        lines.append(f"  {'Water':<20} {result.water_kg:<12.1f} {'--':<12} {'--':<12} {result.adjusted_water_kg:<12.1f}")
        if inp:
            fa_abs = inp.fine_aggregate.absorption_percent
            fa_moist = inp.fine_aggregate.moisture_content_percent
            ca_abs = inp.coarse_aggregate.absorption_percent
            ca_moist = inp.coarse_aggregate.moisture_content_percent
        else:
            fa_abs = fa_moist = ca_abs = ca_moist = 0.0
        lines.append(
            f"  {'Fine Aggregate':<20} {result.fine_aggregate_kg:<12.1f} "
            f"{fa_abs:<12.1f} {fa_moist:<12.1f} {result.field_fine_aggregate_kg:<12.1f}"
        )
        lines.append(
            f"  {'Coarse Aggregate':<20} {result.coarse_aggregate_kg:<12.1f} "
            f"{ca_abs:<12.1f} {ca_moist:<12.1f} {result.field_coarse_aggregate_kg:<12.1f}"
        )
        lines.append("")
        water_diff = result.adjusted_water_kg - result.water_kg
        if water_diff > 0:
            lines.append(f"  Note: Water increased by {water_diff:.1f} kg (aggregates drier than SSD)")
        elif water_diff < 0:
            lines.append(f"  Note: Water reduced by {abs(water_diff):.1f} kg (aggregates wetter than SSD)")
        else:
            lines.append("  Note: Aggregates at SSD condition — no water adjustment needed")
        lines.append("")

    # Cost and carbon estimates
    if result.cost_per_m3 is not None:
        lines.append("COST ESTIMATE")
        lines.append("-" * 40)
        lines.append(f"  Material cost per m³:     ${result.cost_per_m3:.2f}")
        lines.append("")

    if result.carbon_kg_co2_per_m3 is not None:
        lines.append("CARBON ESTIMATE")
        lines.append("-" * 40)
        lines.append(f"  Embodied CO₂:             {result.carbon_kg_co2_per_m3:.1f} kg CO₂/m³")
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("WARNINGS & NOTES")
        lines.append("-" * 40)
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")
        lines.append("")

    lines.append(sep)
    lines.append(f"  Report generated for {result.code_used}")
    lines.append(sep)

    return "\n".join(lines)
