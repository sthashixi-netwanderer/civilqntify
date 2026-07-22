"""Core proportioning logic — orchestrates the mix design calculation."""

from __future__ import annotations

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult

# Registry of available codes
_CODE_REGISTRY: dict[str, type[MixDesignCode]] = {
    "aci211": ACI211MixDesign,
    "doe": DOEMixDesign,
    "is10262": IS10262MixDesign,
}


def get_code_implementation(code: str) -> MixDesignCode:
    """Get a mix design code implementation by name.

    Args:
        code: Code identifier — "aci211" or "is10262"

    Returns:
        MixDesignCode instance

    Raises:
        ValueError: If code is not supported
    """
    cls = _CODE_REGISTRY.get(code.lower())
    if cls is None:
        available = ", ".join(_CODE_REGISTRY.keys())
        raise ValueError(
            f"Unknown mix design code '{code}'. Available: {available}"
        )
    return cls()


def design_mix(inp: MixDesignInput) -> MixDesignResult:
    """Run a complete concrete mix design.

    This is the main entry point for the mix design engine.

    Args:
        inp: Complete mix design input parameters

    Returns:
        MixDesignResult with all proportions and calculation steps

    Example:
        >>> from concrete_mix.models import MixDesignInput
        >>> inp = MixDesignInput(
        ...     code="is10262",
        ...     target_strength_mpa=25.0,
        ...     slump_mm=50.0,
        ... )
        >>> result = design_mix(inp)
        >>> print(result.cement_kg, result.water_kg)
    """
    code_impl = get_code_implementation(inp.code)
    return code_impl.design(inp)
