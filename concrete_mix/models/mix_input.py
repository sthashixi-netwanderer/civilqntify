"""Immutable input model for concrete mix design."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from concrete_mix.models.materials import (
    SCM,
    Admixture,
    Cement,
    CoarseAggregate,
    FineAggregate,
)


@dataclass(frozen=True)
class MixDesignInput:
    """All inputs required for a concrete mix design calculation.

    Args:
        code: Mix design code to use — "aci211" or "is10262"
        target_strength_mpa: Required characteristic/compressive strength (MPa)
        slump_mm: Required slump in mm
        cement: Cement material properties
        fine_aggregate: Fine aggregate (sand) properties
        coarse_aggregate: Coarse aggregate properties
        scms: Optional list of supplementary cementitious materials
        admixture: Optional chemical admixture
        exposure_class: IS 456 exposure class (for IS 10262 only)
            Valid: "mild", "moderate", "severe", "very_severe", "extreme"
        concrete_type: Plain or reinforced concrete (IS 456:2000 Table 5).
            "plain" or "reinforced" (default). Determines which row of
            Table 5 is used for min cement, max W/C, and min grade limits.
        air_entrained: Whether air-entrained concrete is required (ACI only)
        w_c_ratio: Optional manual override for W/C ratio
        volume_m3: Target concrete volume in cubic meters (default 1.0)
        has_production_data: Whether ≥30 test results exist (ACI only).
            False uses ACI 318 Table 26.4.3.1(b) overdesign.
        sulfate_exposure_class: ACI 318 sulfate exposure class (ACI only).
            Valid: "S0", "S1", "S2", "S3". Default "S0" (no sulfate).
    """

    code: Literal["aci211", "is10262", "doe"]
    target_strength_mpa: float
    characteristic_strength_mpa: float | None = (
        None  # User enters this; target is calculated
    )
    ca_volume_fraction_override: float | None = (
        None  # Direct CA volume fraction from Table 5
    )
    slump_mm: float = 75.0
    cement: Cement = field(default_factory=Cement)
    fine_aggregate: FineAggregate = field(default_factory=FineAggregate)
    coarse_aggregate: CoarseAggregate = field(default_factory=CoarseAggregate)
    scms: tuple[SCM, ...] = ()
    admixture: Optional[Admixture] = None
    exposure_class: Optional[str] = None
    concrete_type: Literal["plain", "reinforced"] = "reinforced"
    air_entrained: bool = False
    w_c_ratio: Optional[float] = None
    volume_m3: float = 1.0
    has_production_data: bool = True
    sulfate_exposure_class: str = "S0"
    defective_percent: float = 5.0
    age_days: int = 28
    min_cement_kg: float | None = None
    max_cement_kg: float | None = None
    std_deviation: float | None = None  # DOE: user-provided standard deviation (MPa)
    margin_mpa: float | None = None  # DOE: user-specified margin (MPa), overrides k×s calculation

    def __post_init__(self) -> None:
        if self.code == "doe":
            # DOE uses wider strength range (28-day characteristic)
            if not 5.0 <= self.target_strength_mpa <= 100.0:
                raise ValueError(
                    f"Characteristic strength {self.target_strength_mpa} MPa outside valid range [5, 100]"
                )
            # DOE Table 3: NMSA must be 10, 20, or 40 mm
            valid_nmsa = (10, 20, 40)
            nmsa = self.coarse_aggregate.nominal_max_size_mm
            if nmsa not in valid_nmsa:
                raise ValueError(
                    f"NMSA {nmsa} mm not supported in DOE method. "
                    f"Use one of {valid_nmsa} mm (BRE 331:1997 Table 3)"
                )
            # DOE Table 3: Slump must be 0-180 mm
            if not 0.0 <= self.slump_mm <= 180.0:
                raise ValueError(
                    f"Slump {self.slump_mm} mm outside valid range [0, 180] for DOE method. "
                    f"See BRE 331:1997 Table 3"
                )
        else:
            if not 10.0 <= self.target_strength_mpa <= 80.0:
                raise ValueError(
                    f"Target strength {self.target_strength_mpa} MPa outside valid range [10, 80]"
                )
        min_slump = 0.0 if self.code == "doe" else 10.0
        if not min_slump <= self.slump_mm <= 250.0:
            raise ValueError(f"Slump {self.slump_mm} mm outside valid range [{min_slump}, 250]")
        if self.exposure_class is not None:
            valid_classes = ("mild", "moderate", "severe", "very_severe", "extreme")
            if self.exposure_class not in valid_classes:
                raise ValueError(
                    f"Exposure class '{self.exposure_class}' not valid. Use one of {valid_classes}"
                )
        if self.w_c_ratio is not None and not 0.25 <= self.w_c_ratio <= 0.80:
            raise ValueError(
                f"W/C ratio {self.w_c_ratio} outside valid range [0.25, 0.80]"
            )
        if self.volume_m3 <= 0:
            raise ValueError("Volume must be positive")
        if self.sulfate_exposure_class not in ("S0", "S1", "S2", "S3"):
            raise ValueError(
                f"Sulfate exposure class '{self.sulfate_exposure_class}' not valid. "
                "Use one of ('S0', 'S1', 'S2', 'S3')"
            )
        if self.min_cement_kg is not None and self.min_cement_kg <= 0:
            raise ValueError("Minimum cement content must be positive")
        if self.max_cement_kg is not None and self.max_cement_kg <= 0:
            raise ValueError("Maximum cement content must be positive")

    @property
    def nmsa(self) -> int:
        """Nominal Maximum Size of Aggregate (mm)."""
        return self.coarse_aggregate.nominal_max_size_mm

    @property
    def characteristic_strength(self) -> float:
        """Characteristic compressive strength (fck)."""
        return self.characteristic_strength_mpa or self.target_strength_mpa

    @property
    def total_scm_replacement_percent(self) -> float:
        """Total SCM replacement percentage."""
        return sum(s.replacement_percent for s in self.scms)
