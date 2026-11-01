"""Aggregate moisture correction for concrete mix design batch weights.

The model stores **total moisture content** (ASTM C566 / BS 812): the mass
of all evaporable water expressed as a percentage of the oven-dry
aggregate mass.  The user-facing mix-design inputs, however, are stated as
**free moisture above SSD**, because that is how the standards' worked
examples express the field adjustment:

* ACI PRC-211.1-22 clause 4.7.8.3 / clause 5.3.9.1 defines the free water on the SSD
  mass: ``f = (M_field − M_SSD) / M_SSD × 100``.
* IS 10262:2019 Annex B-11 and BS 812 define free (surface) moisture as
  ``f = MC − A`` in percentage points of the oven-dry mass.

The helpers below are the single boundary between those two conventions;
``MixDesignInput`` and the correction formulas always consume total MC.
"""

from __future__ import annotations


def free_to_total_moisture(
    free_moisture_percent: float,
    absorption_percent: float,
    code: str,
) -> float:
    """Convert user-facing free moisture above SSD to total moisture (MC).

    ACI PRC-211.1-22 clause 4.7.8.3 / clause 5.3.9.1 expresses free moisture on the
    **SSD mass**, so::

        MC = A + (1 + A/100) × f

    IS 10262:2019 Annex B-11 and BS 812/BS 1881 express free (surface)
    moisture in percentage points of the **oven-dry mass**, so::

        MC = A + f

    Args:
        free_moisture_percent: Free moisture above SSD (%). 0 = SSD;
            negative values are drier than SSD, with the oven-dry limit
            at ``−100·A/(100+A)`` (ACI) or ``−A`` (IS/DOE).
        absorption_percent: Aggregate absorption A (% of oven-dry mass).
        code: ``"aci211"``, ``"is10262"`` or ``"doe"``.

    Returns:
        Total moisture content MC (% of oven-dry mass).

    Raises:
        ValueError: If the free moisture implies a negative total moisture
            (drier than oven-dry aggregate).
    """
    if code == "aci211":
        total = absorption_percent + (
            1.0 + absorption_percent / 100.0
        ) * free_moisture_percent
    elif code in ("is10262", "doe"):
        total = absorption_percent + free_moisture_percent
    else:
        raise ValueError(f"Unknown mix-design code '{code}'")

    if total < -1e-9:
        limit = (
            -100.0 * absorption_percent / (100.0 + absorption_percent)
            if code == "aci211"
            else -absorption_percent
        )
        raise ValueError(
            f"Free moisture {free_moisture_percent:g}% is below the oven-dry "
            f"limit ({limit:.3f}%) for absorption {absorption_percent:g}%"
        )
    return max(0.0, total)


def total_to_free_moisture(
    total_moisture_percent: float,
    absorption_percent: float,
    code: str,
) -> float:
    """Convert stored total moisture (MC) back to free moisture above SSD.

    Inverse of :func:`free_to_total_moisture`; used when restoring a saved
    design into the free-moisture input fields.
    """
    if code == "aci211":
        return (
            (1.0 + total_moisture_percent / 100.0)
            / (1.0 + absorption_percent / 100.0)
            - 1.0
        ) * 100.0
    if code in ("is10262", "doe"):
        return total_moisture_percent - absorption_percent
    raise ValueError(f"Unknown mix-design code '{code}'")


def correct_for_moisture(
    ssd_mass_kg: float,
    absorption_percent: float,
    moisture_content_percent: float,
) -> float:
    """Calculate field batch weight from an SSD design weight.

    Uses the ACI PRC-211.1-22 clause 5.3.9.1 formula:

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
    (ACI PRC-211.1-22 clause 5.3.9.1):

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
