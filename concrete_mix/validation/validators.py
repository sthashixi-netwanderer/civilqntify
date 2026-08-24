"""Input validation for concrete mix design."""

from __future__ import annotations

from concrete_mix.codes.tables.is_tables import get_exposure_limits
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.utils.display import display_name


def validate_mix_input(inp: MixDesignInput) -> list[str]:
    """Validate a mix design input and return a list of warning messages.

    Returns an empty list if no issues found.
    Errors (invalid values) are raised as ValueError in __post_init__.
    This catches soft warnings (unusual but not invalid combinations).
    """
    warnings: list[str] = []

    # Code-specific validation
    if inp.code == "is10262":
        warnings.extend(_validate_is_input(inp))
    elif inp.code == "aci211":
        warnings.extend(_validate_aci_input(inp))
    elif inp.code == "doe":
        warnings.extend(_validate_doe_input(inp))

    # Common warnings
    if inp.w_c_ratio is not None and inp.w_c_ratio > 0.60:
        warnings.append(
            f"W/C ratio {inp.w_c_ratio} is high — durability may be compromised"
        )

    if inp.slump_mm > 150:
        warnings.append(f"Slump {inp.slump_mm} mm is very high — segregation risk")

    if inp.total_scm_replacement_percent > 50:
        warnings.append(
            f"Total SCM replacement {inp.total_scm_replacement_percent}% is high — "
            "early strength may be significantly reduced"
        )

    return warnings


def _validate_is_input(inp: MixDesignInput) -> list[str]:
    """IS 10262 specific validations.

    Uses IS456_EXPOSURE_LIMITS from is_tables.py as the single source of truth.
    """
    warnings: list[str] = []

    # Grade vs exposure class constraints (IS 456:2000 Table 5)
    if inp.exposure_class:
        limits = get_exposure_limits(inp.exposure_class, inp.concrete_type)
        if inp.w_c_ratio is not None and inp.w_c_ratio > limits["max_wc"]:
            warnings.append(
                f"W/C ratio {inp.w_c_ratio} exceeds maximum {limits['max_wc']} "
                f"for '{display_name(inp.exposure_class)}' exposure per IS 456:2000 Table 5"
            )

    # Cement type should be IS grade
    from concrete_mix.models.materials import CementType

    is_types = {
        CementType.OPC_33,
        CementType.OPC_43,
        CementType.OPC_53,
        CementType.PPC,
        CementType.PSC,
    }
    if inp.cement.type not in is_types:
        warnings.append(
            f"Cement type '{display_name(inp.cement.type.value)}' is not a standard IS cement grade"
        )

    # Grading zone should be specified for IS method
    if inp.fine_aggregate.grading_zone is None:
        warnings.append(
            "Grading zone not specified — Zone II will be assumed for IS 10262"
        )

    # Aggregate shape validation
    from concrete_mix.codes.tables.is_tables import AGGREGATE_SHAPE_ADJUSTMENT_KG
    from concrete_mix.models.materials import AggregateShape

    agg_shape = inp.coarse_aggregate.shape
    adj_kg = AGGREGATE_SHAPE_ADJUSTMENT_KG.get(agg_shape.value, 0.0)
    if adj_kg < 0:
        warnings.append(
            f"Aggregate shape '{display_name(agg_shape.value)}' reduces water demand by "
            f"{abs(adj_kg):.0f} kg/m³ per IS 10262:2019 Clause 5.2"
        )

    return warnings


def _validate_aci_input(inp: MixDesignInput) -> list[str]:
    """ACI 211.1 specific validations."""
    warnings: list[str] = []

    # Cement type should be ACI type
    from concrete_mix.models.materials import CementType

    aci_types = {
        CementType.TYPE_I,
        CementType.TYPE_II,
        CementType.TYPE_III,
        CementType.TYPE_IV,
        CementType.TYPE_V,
    }
    is_types = {
        CementType.OPC_33,
        CementType.OPC_43,
        CementType.OPC_53,
        CementType.PPC,
        CementType.PSC,
    }
    if inp.cement.type not in aci_types and inp.cement.type not in is_types:
        warnings.append(
            f"Cement type '{display_name(inp.cement.type.value)}' is not a standard ASTM C150 type"
        )

    # Fineness modulus should be specified for ACI method
    if inp.fine_aggregate.fineness_modulus is None:
        warnings.append(
            "Fineness modulus not specified — 2.70 will be assumed for ACI 211"
        )

    # Air-entrained warning for severe exposure
    if not inp.air_entrained and inp.exposure_class in (
        "severe",
        "very_severe",
        "extreme",
    ):
        warnings.append(
            "Air entrainment recommended for severe/extreme exposure conditions"
        )

    return warnings


def _validate_doe_input(inp: MixDesignInput) -> list[str]:
    """DOE (BR 331:1997) specific validations."""
    warnings: list[str] = []

    if inp.nmsa not in (10, 20, 40):
        warnings.append(
            f"NMSA {inp.nmsa} mm is not a standard DOE size — use 10, 20, or 40 mm"
        )

    return warnings
