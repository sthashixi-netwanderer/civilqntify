"""Target mean strength calculations independent of mix proportioning.

This module intentionally does not construct a full ``MixDesignInput``. Target
mean strength is determined from the selected standard's strength, variability,
and standard-specific statistical inputs; slump, aggregate, material, and
volume inputs belong to the separate mix-design workflow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign

from concrete_mix.codes.tables.doe_tables import get_k_value, get_standard_deviation
from concrete_mix.codes.tables.is_tables import (
    _grade_from_fck,
    calculate_target_strength as calculate_is_target_strength,
    get_std_dev,
)


@dataclass(frozen=True)
class TargetStrengthResult:
    """Standard-based target mean strength result, with audit metadata."""

    code: str
    standard_name: str
    characteristic_strength_mpa: float
    target_mean_strength_mpa: float
    standard_deviation_mpa: float | None
    margin_mpa: float
    formula: str
    reference: str


def calculate_target_strength(
    code: str,
    characteristic_strength_mpa: float,
    *,
    has_production_data: bool = True,
    defective_percent: float = 5.0,
    num_test_cubes: int | None = None,
) -> TargetStrengthResult:
    """Calculate target mean strength using only target-strength inputs.

    The numeric target is delegated to the same standard implementations used
    by the full mix-design pipeline. This avoids maintaining a second set of
    standard formulas for the mode-specific UI.

    References:
        IS 10262:2019 target-strength relation and Tables 1–2
        ACI PRC-211.1-22 §4.7.4 and ACI 318 target-strength provisions
        BRE 331:1997 §4.4, §5.1, and Figure 3
    """
    if not math.isfinite(characteristic_strength_mpa) or characteristic_strength_mpa < 25.0:
        raise ValueError(
            f"Structural mix design requires characteristic compressive strength "
            f"fc ≥ 25 MPa. Got {characteristic_strength_mpa} MPa. "
            f"This application assumes the design is for structural concrete."
        )

    code = code.lower()
    fck = float(characteristic_strength_mpa)

    if code == "is10262":
        target, formula = calculate_is_target_strength(fck)
        grade = _grade_from_fck(fck)
        standard_deviation = get_std_dev(grade)
        return TargetStrengthResult(
            code=code,
            standard_name="IS 10262:2019",
            characteristic_strength_mpa=fck,
            target_mean_strength_mpa=target,
            standard_deviation_mpa=standard_deviation,
            margin_mpa=target - fck,
            formula=formula,
            reference="IS 10262:2019 target-strength relation, Tables 1–2",
        )

    if code == "aci211":
        designer = ACI211MixDesign()
        target = designer.calculate_target_mean_strength(
            fck,
            has_production_data=has_production_data,
        )
        if has_production_data:
            # The existing ACI implementation uses its documented 4 MPa default
            # when no project-specific sample deviation is supplied.
            standard_deviation = 4.0
            formula = (
                "max(f'c + 1.34 × s, f'c + 2.33 × s − 3.45, "
                "f'c + 2.4), s = 4.0 MPa"
            )
        else:
            standard_deviation = None
            formula = "ACI 318 Table 26.4.3.1(b), no prior strength-test data"
        return TargetStrengthResult(
            code=code,
            standard_name="ACI PRC-211.1-22",
            characteristic_strength_mpa=fck,
            target_mean_strength_mpa=target,
            standard_deviation_mpa=standard_deviation,
            margin_mpa=target - fck,
            formula=formula,
            reference="ACI PRC-211.1-22 §4.7.4 / ACI 318 Table 26.4.3.1",
        )

    if code == "doe":
        if fck < 25.0:
            raise ValueError(
                "DOE (BR 331:1997) structural design requires characteristic "
                "strength fc ≥ 25 MPa (Figure 3, §4.4)"
            )
        if not 0.5 <= defective_percent <= 15.0:
            raise ValueError("Defective percent must be between 0.5 and 15%")
        if num_test_cubes is None:
            num_test_cubes = 20
        if num_test_cubes <= 0:
            raise ValueError("Number of test cubes (n) must be positive")

        standard_deviation = get_standard_deviation(fck, n=num_test_cubes)
        k = get_k_value(defective_percent)
        target = DOEMixDesign().calculate_target_mean_strength(
            fck,
            num_test_cubes=num_test_cubes,
            defective_percent=defective_percent,
        )
        line = "Line A" if num_test_cubes < 20 else "Line B"
        formula = (
            f"fm = fc + k × s = {fck:.2f} + {k:.2f} × "
            f"{standard_deviation:.2f} ({line}, n={num_test_cubes})"
        )
        return TargetStrengthResult(
            code=code,
            standard_name="DOE (BR 331:1997)",
            characteristic_strength_mpa=fck,
            target_mean_strength_mpa=target,
            standard_deviation_mpa=standard_deviation,
            margin_mpa=target - fck,
            formula=formula,
            reference="BRE 331:1997 §4.4, §5.1, Figure 3",
        )

    raise ValueError(f"Unknown target-strength standard: {code}")
