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
    site_assumed_std_dev,
)
from concrete_mix.codes.tables.aci_tables import modification_factor_k


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
    num_strength_tests: int | None = None,
    site_control: str = "good",
    std_deviation: float | None = None,
    margin_mpa: float | None = None,
) -> TargetStrengthResult:
    """Calculate target mean strength using only target-strength inputs.

    The numeric target is delegated to the same standard implementations used
    by the full mix-design pipeline. This avoids maintaining a second set of
    standard formulas for the mode-specific UI.

    A user-supplied ``margin_mpa`` (DOE only, from established site records
    per BRE 331:1997 §4.4) bypasses the k × s computation entirely: no
    defective percentage, standard deviation, or test-cube count is needed
    and the target is simply ``ceil(fc + M)`` per Calculation C2. It is
    ignored for the IS/ACI branches, which have no margin concept.

    References:
        IS 10262:2019 target-strength relation and Tables 1–2
        ACI PRC-211.1-22 §4.7.4 and ACI 318 target-strength provisions
        BRE 331:1997 §4.4, §5.1, and Figure 3
    """
    code = code.lower()
    fck = float(characteristic_strength_mpa)

    # No app-imposed structural floor for any code: DOE Figure 3 spans the
    # full axis, and IS/ACI durability is gated by exposure minima, not by
    # an input floor. 5 MPa is a sanity floor for all three.
    if not math.isfinite(fck) or not 5.0 <= fck <= 100.0:
        raise ValueError(
            f"Characteristic strength fc outside valid range [5, 100] MPa. "
            f"Got {characteristic_strength_mpa} MPa."
        )

    if code == "is10262":
        grade = _grade_from_fck(fck)
        if std_deviation is not None and std_deviation > 0:
            standard_deviation = std_deviation
        else:
            standard_deviation = site_assumed_std_dev(grade, site_control)
        target, formula = calculate_is_target_strength(fck, standard_deviation)
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
        _s = std_deviation if (std_deviation is not None and std_deviation > 0) else None
        target = designer.calculate_target_mean_strength(
            fck,
            std_dev=_s,
            has_production_data=has_production_data,
            num_tests=num_strength_tests if has_production_data else None,
        )
        if has_production_data:
            # The ACI implementation uses its documented 4 MPa default when
            # no project-specific sample deviation is supplied; 15–29 tests
            # apply the Table 4.7.4.3 k-modification to s.
            s_eff = _s if _s is not None else 4.0
            k_eff = (
                modification_factor_k(num_strength_tests)
                if num_strength_tests is not None else 1.0
            )
            standard_deviation = s_eff
            _ks = k_eff * s_eff
            _branch = ("f'c + 2.33·k·s − 3.45" if fck <= 34.5
                       else "0.90·f'c + 2.33·k·s")
            formula = (
                f"max(f'c + 1.34·k·s, {_branch}, f'c + 2.4); "
                f"s = {s_eff:g} MPa"
                + (f", k = {k_eff:g} (n = {num_strength_tests}, Table 4.7.4.3)"
                   if num_strength_tests is not None else "")
            )
        else:
            standard_deviation = None
            formula = (
                "ACI 318 Table 26.4.3.1(b) / PRC-211.1-22 Table 4.7.4.1, "
                "no prior strength-test data"
            )
        return TargetStrengthResult(
            code=code,
            standard_name="ACI PRC-211.1:2022",
            characteristic_strength_mpa=fck,
            target_mean_strength_mpa=target,
            standard_deviation_mpa=standard_deviation,
            margin_mpa=target - fck,
            formula=formula,
            reference="ACI PRC-211.1-22 §4.7.4 / ACI 318 Table 26.4.3.1",
        )

    if code == "doe":
        if margin_mpa is not None:
            # Known-margin path (BRE 331:1997 §4.4): M comes straight from
            # site records, so k (defectives), s and n are all bypassed.
            margin = float(margin_mpa)
            if not math.isfinite(margin) or margin <= 0.0:
                raise ValueError(
                    f"Strength margin M must be positive. Got {margin_mpa} MPa."
                )
            target = float(math.ceil(fck + margin - 1e-9))
            formula = (
                f"fm = fc + M = {fck:.2f} + {margin:.2f} "
                f"→ {target:.0f} (user-specified M, rounded up, C2)"
            )
            return TargetStrengthResult(
                code=code,
                standard_name="DOE (BRE 331:1997)",
                characteristic_strength_mpa=fck,
                target_mean_strength_mpa=target,
                standard_deviation_mpa=None,
                margin_mpa=margin,
                formula=formula,
                reference="BRE 331:1997 §4.4, §5.1 (Calculation C2)",
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
            standard_name="DOE (BRE 331:1997)",
            characteristic_strength_mpa=fck,
            target_mean_strength_mpa=target,
            standard_deviation_mpa=standard_deviation,
            margin_mpa=target - fck,
            formula=formula,
            reference="BRE 331:1997 §4.4, §5.1, Figure 3",
        )

    raise ValueError(f"Unknown target-strength standard: {code}")
