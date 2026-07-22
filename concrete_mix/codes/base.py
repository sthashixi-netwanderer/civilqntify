"""Abstract base class for concrete mix design code implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult


class MixDesignCode(ABC):
    """Abstract interface for a concrete mix design code (ACI, IS, EN, etc.)."""

    @property
    @abstractmethod
    def code_name(self) -> str:
        """Short identifier for the code (e.g. 'aci211', 'is10262')."""
        ...

    @property
    @abstractmethod
    def code_full_name(self) -> str:
        """Full standard name (e.g. 'ACI 211.1-91')."""
        ...

    @abstractmethod
    def calculate_target_mean_strength(
        self, target_strength_mpa: float, std_dev: float | None = None
    ) -> float:
        """Calculate the target mean strength from characteristic strength.

        Args:
            target_strength_mpa: Characteristic/compressive strength (f'c or fck) in MPa
            std_dev: Standard deviation in MPa (code-specific default if None)
        """
        ...

    @abstractmethod
    def get_water_content(
        self, nmsa: int, slump_mm: float, **kwargs
    ) -> float:
        """Get water content (kg/m³) from code tables.

        Args:
            nmsa: Nominal maximum aggregate size (mm)
            slump_mm: Required slump (mm)
        """
        ...

    @abstractmethod
    def get_w_c_ratio(
        self, target_mean_strength_mpa: float, **kwargs
    ) -> float:
        """Get water-cement ratio from code tables.

        Args:
            target_mean_strength_mpa: Target mean strength in MPa
        """
        ...

    @abstractmethod
    def get_coarse_aggregate_volume(self, nmsa: int, **kwargs) -> float:
        """Get coarse aggregate volume fraction.

        Returns:
            Volume fraction — interpretation depends on code:
            - ACI: fraction of total concrete volume
            - IS: fraction of total aggregate volume
        """
        ...

    @abstractmethod
    def get_air_content(self, nmsa: int, **kwargs) -> float:
        """Get air content (%) for the given conditions."""
        ...

    @abstractmethod
    def design(self, inp: MixDesignInput) -> MixDesignResult:
        """Run the full mix design calculation.

        Args:
            inp: Complete mix design input parameters

        Returns:
            MixDesignResult with all proportions and calculation steps
        """
        ...

    def _make_step(
        self,
        number: int,
        description: str,
        formula: str,
        inputs: dict,
        result: float,
        unit: str,
        clause_ref: str = "",
    ) -> CalculationStep:
        """Helper to create a CalculationStep."""
        return CalculationStep(
            step_number=number,
            description=description,
            formula=formula,
            inputs=inputs,
            result=result,
            unit=unit,
            clause_ref=clause_ref,
        )
