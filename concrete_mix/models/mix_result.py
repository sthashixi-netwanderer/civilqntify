"""Immutable result model for concrete mix design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CalculationStep:
    """A single calculation step with reference to the code clause."""
    step_number: int
    description: str
    formula: str
    inputs: dict[str, Any]
    result: float
    unit: str
    clause_ref: str = ""

    def __str__(self) -> str:
        return f"Step {self.step_number}: {self.description} = {self.result:.2f} {self.unit}"


@dataclass(frozen=True)
class MixDesignResult:
    """Complete result of a concrete mix design calculation.

    All masses are per unit volume (1 m³ by default).
    Multiply by volume_m3 for total quantities.
    """
    code_used: str
    target_mean_strength_mpa: float
    w_c_ratio: float
    water_kg: float
    cement_kg: float
    scm_kg: float = 0.0
    fine_aggregate_kg: float = 0.0
    coarse_aggregate_kg: float = 0.0
    air_volume_percent: float = 0.0
    volume_m3: float = 1.0
    steps: tuple[CalculationStep, ...] = ()
    warnings: tuple[str, ...] = ()
    cost_per_m3: Optional[float] = None
    carbon_kg_co2_per_m3: Optional[float] = None
    # Moisture adjustment — field batch weights
    adjusted_water_kg: Optional[float] = None
    field_fine_aggregate_kg: Optional[float] = None
    field_coarse_aggregate_kg: Optional[float] = None
    # Admixture data (IS 10262:2019 Annex A)
    admixture_kg: Optional[float] = None
    admixture_type: Optional[str] = None
    admixture_dosage_percent: Optional[float] = None
    water_reduction_percent: Optional[float] = None
    # DOE single-size coarse aggregate split (BRE 331:1997 §5.5, C5 note):
    # per-m³ masses keyed by single size, e.g. {"10 mm": 460.0, "20 mm": 925.0}.
    # None when a single graded stock is used (no subdivision).
    ca_split_kg: Optional[dict[str, float]] = None

    @property
    def total_cementitious_kg(self) -> float:
        """Total cementitious material (cement + SCMs)."""
        return self.cement_kg + self.scm_kg

    @property
    def cement_only_kg(self) -> float:
        """Cement excluding SCM replacements."""
        return self.cement_kg

    @property
    def total_aggregate_kg(self) -> float:
        """Total aggregate (fine + coarse)."""
        return self.fine_aggregate_kg + self.coarse_aggregate_kg

    @property
    def mix_ratio(self) -> dict[str, float]:
        """Mix ratio normalized to cement = 1.

        Returns dict with keys: cement, fine_aggregate,
        coarse_aggregate, scm (if any).
        Water is excluded (it goes into the W/C ratio display).
        """
        c = self.total_cementitious_kg
        if c == 0:
            return {"cement": 0, "fine_aggregate": 0, "coarse_aggregate": 0}
        ratio: dict[str, float] = {
            "cement": 1.0,
            "fine_aggregate": round(self.fine_aggregate_kg / c, 1),
            "coarse_aggregate": round(self.coarse_aggregate_kg / c, 1),
        }
        if self.scm_kg > 0:
            ratio["scm"] = round(self.scm_kg / c, 1)
        return ratio

    @property
    def mix_ratio_string(self) -> str:
        """Human-readable mix ratio string, e.g. '1 : 1.5 : 2.8 (0.450)'.

        Format: Cement : Fine Aggregate : Coarse Aggregate (W/C)
        """
        r = self.mix_ratio
        return (
            f"{r['cement']} : {r['fine_aggregate']} : {r['coarse_aggregate']}"
            f" ({self.w_c_ratio:.3f})"
        )

    def scaled_to_volume(self, volume_m3: float) -> MixDesignResult:
        """Return a new result scaled to a different volume."""
        factor = volume_m3 / self.volume_m3
        return MixDesignResult(
            code_used=self.code_used,
            target_mean_strength_mpa=self.target_mean_strength_mpa,
            w_c_ratio=self.w_c_ratio,
            water_kg=self.water_kg * factor,
            cement_kg=self.cement_kg * factor,
            scm_kg=self.scm_kg * factor,
            fine_aggregate_kg=self.fine_aggregate_kg * factor,
            coarse_aggregate_kg=self.coarse_aggregate_kg * factor,
            air_volume_percent=self.air_volume_percent,
            volume_m3=volume_m3,
            steps=self.steps,
            warnings=self.warnings,
            cost_per_m3=self.cost_per_m3,
            carbon_kg_co2_per_m3=self.carbon_kg_co2_per_m3,
            adjusted_water_kg=self.adjusted_water_kg * factor if self.adjusted_water_kg is not None else None,
            field_fine_aggregate_kg=self.field_fine_aggregate_kg * factor if self.field_fine_aggregate_kg is not None else None,
            field_coarse_aggregate_kg=self.field_coarse_aggregate_kg * factor if self.field_coarse_aggregate_kg is not None else None,
            admixture_kg=self.admixture_kg * factor if self.admixture_kg is not None else None,
            admixture_type=self.admixture_type,
            admixture_dosage_percent=self.admixture_dosage_percent,
            water_reduction_percent=self.water_reduction_percent,
            ca_split_kg=(
                {k: v * factor for k, v in self.ca_split_kg.items()}
                if self.ca_split_kg is not None
                else None
            ),
        )
