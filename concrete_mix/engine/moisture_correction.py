"""Aggregate moisture correction for concrete mix design batch weights."""

from __future__ import annotations


def correct_for_moisture(
    dry_mass_kg: float,
    absorption_percent: float,
    moisture_content_percent: float,
) -> float:
    """Calculate field batch weight from SSD (Saturated Surface Dry) mass.

    Args:
        dry_mass_kg: Mass in SSD condition (kg)
        absorption_percent: Aggregate absorption (%)
        moisture_content_percent: Free moisture content (%)

    Returns:
        Batch weight (kg) — adjusted for actual moisture in aggregate
    """
    return dry_mass_kg * (1 + moisture_content_percent / 100.0)


def adjust_water_for_aggregate_moisture(
    design_water_kg: float,
    fa_ssd_mass_kg: float,
    fa_absorption_percent: float,
    fa_moisture_percent: float,
    ca_ssd_mass_kg: float,
    ca_absorption_percent: float,
    ca_moisture_percent: float,
) -> float:
    """Adjust mix water to account for aggregate moisture.

    If aggregate is wetter than SSD, reduce water.
    If aggregate is drier than SSD, add water.

    Args:
        design_water_kg: Design water content (kg)
        fa_ssd_mass_kg: Fine aggregate mass in SSD condition (kg)
        fa_absorption_percent: Fine aggregate absorption (%)
        fa_moisture_percent: Fine aggregate free moisture (%)
        ca_ssd_mass_kg: Coarse aggregate mass in SSD condition (kg)
        ca_absorption_percent: Coarse aggregate absorption (%)
        ca_moisture_percent: Coarse aggregate free moisture (%)

    Returns:
        Adjusted water content (kg)
    """
    # Free moisture = actual moisture - absorption
    fa_free_moisture = (fa_moisture_percent - fa_absorption_percent) / 100.0
    ca_free_moisture = (ca_moisture_percent - ca_absorption_percent) / 100.0

    water_from_fa = fa_ssd_mass_kg * fa_free_moisture
    water_from_ca = ca_ssd_mass_kg * ca_free_moisture

    return design_water_kg - water_from_fa - water_from_ca
