"""Absolute volume method calculations for concrete mix design."""

from __future__ import annotations

from concrete_mix.utils.constants import SG_WATER


def absolute_volume(mass_kg: float, specific_gravity: float) -> float:
    """Calculate absolute volume (m³) of a material.

    Volume = mass / (SG × ρ_water)

    Args:
        mass_kg: Mass of material in kg
        specific_gravity: Specific gravity of the material (dimensionless)

    Returns:
        Absolute volume in m³
    """
    if specific_gravity <= 0:
        raise ValueError(f"Specific gravity must be positive, got {specific_gravity}")
    return mass_kg / (specific_gravity * 1000.0)


def mass_from_volume(volume_m3: float, specific_gravity: float) -> float:
    """Calculate mass (kg) from absolute volume.

    Mass = Volume × SG × ρ_water

    Args:
        volume_m3: Absolute volume in m³
        specific_gravity: Specific gravity of the material

    Returns:
        Mass in kg
    """
    return volume_m3 * specific_gravity * 1000.0


def total_volume(
    cement_kg: float,
    water_kg: float,
    fine_agg_kg: float,
    coarse_agg_kg: float,
    cement_sg: float,
    fine_agg_sg: float,
    coarse_agg_sg: float,
    air_percent: float,
    scm_kg: float = 0.0,
    scm_sg: float = 3.15,
) -> float:
    """Calculate total absolute volume of all ingredients (m³).

    Args:
        cement_kg: Mass of cement (kg)
        water_kg: Mass of water (kg)
        fine_agg_kg: Mass of fine aggregate (kg)
        coarse_agg_kg: Mass of coarse aggregate (kg)
        cement_sg: Specific gravity of cement
        fine_agg_sg: Specific gravity of fine aggregate
        coarse_agg_sg: Specific gravity of coarse aggregate
        air_percent: Air content (% by volume)
        scm_kg: Mass of SCM (kg)
        scm_sg: Specific gravity of SCM

    Returns:
        Total absolute volume in m³
    """
    vol_cement = absolute_volume(cement_kg, cement_sg)
    vol_scm = absolute_volume(scm_kg, scm_sg) if scm_kg > 0 else 0.0
    vol_water = absolute_volume(water_kg, SG_WATER)
    vol_fa = absolute_volume(fine_agg_kg, fine_agg_sg)
    vol_ca = absolute_volume(coarse_agg_kg, coarse_agg_sg)
    vol_air = air_percent / 100.0  # 1 m³ basis

    return vol_cement + vol_scm + vol_water + vol_fa + vol_ca + vol_air
