"""Aggregate moisture correction for concrete mix design batch weights."""

from __future__ import annotations


def correct_for_moisture(
    ssd_mass_kg: float,
    absorption_percent: float,
    moisture_content_percent: float,
) -> float:
    """Calculate field batch weight from an SSD design weight.

    Uses the ACI PRC-211.1-22 §5.3.9.1 formula:

        w_batched = w_SSD × (1 + MC%) / (1 + A%)

    where MC is the total (free + absorbed) moisture content of the
    stockpiled aggregate and A is the aggregate absorption, both expressed
    as percentages of the oven-dry aggregate mass.

    Args:
        ssd_mass_kg: Design mass in SSD condition (kg)
        absorption_percent: Aggregate absorption (%)
        moisture_content_percent: Total moisture content (%)

    Returns:
        Batch weight (kg) — adjusted for actual moisture in the aggregate
    """
    return ssd_mass_kg * (1.0 + moisture_content_percent / 100.0) / (
        1.0 + absorption_percent / 100.0
    )


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

    Free water on each aggregate = batched weight − SSD weight
    (ACI PRC-211.1-22 §5.3.9.1):

        free water = w_SSD × [(1 + MC%) / (1 + A%) − 1]

    If the aggregate is wetter than SSD the free water is positive and is
    subtracted from the mix water; if drier than SSD the value is negative
    and extra water is added.

    Args:
        design_water_kg: Design water content (kg)
        fa_ssd_mass_kg: Fine aggregate mass in SSD condition (kg)
        fa_absorption_percent: Fine aggregate absorption (%)
        fa_moisture_percent: Fine aggregate total moisture (%)
        ca_ssd_mass_kg: Coarse aggregate mass in SSD condition (kg)
        ca_absorption_percent: Coarse aggregate absorption (%)
        ca_moisture_percent: Coarse aggregate total moisture (%)

    Returns:
        Adjusted (batch) water content (kg)
    """
    def free_water(ssd_mass: float, absorption: float, moisture: float) -> float:
        return ssd_mass * (
            (1.0 + moisture / 100.0) / (1.0 + absorption / 100.0) - 1.0
        )

    water_from_fa = free_water(fa_ssd_mass_kg, fa_absorption_percent, fa_moisture_percent)
    water_from_ca = free_water(ca_ssd_mass_kg, ca_absorption_percent, ca_moisture_percent)

    return design_water_kg - water_from_fa - water_from_ca
