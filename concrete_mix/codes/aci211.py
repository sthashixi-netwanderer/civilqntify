"""ACI PRC-211.1-22 concrete mix design implementation.

Implements the absolute volume method for proportioning normal-weight concrete
per ACI PRC-211.1-22 "Selecting Proportions for Normal-Density and
High-Density Concrete" (guide). Overdesign criteria per ACI 318.
"""

from __future__ import annotations

from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.tables.aci_tables import (
    get_air_content,
    get_no_data_overdesign,
    interpolate_ca_volume,
    interpolate_w_c_ratio,
    interpolate_water_content,
    ACI_MAX_WC_FOR_EXPOSURE,
)
from concrete_mix.engine.moisture_correction import adjust_water_for_aggregate_moisture, correct_for_moisture
from concrete_mix.engine.volume_calculator import absolute_volume, total_volume
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult
from concrete_mix.utils.constants import SG_WATER


class ACI211MixDesign(MixDesignCode):
    """ACI PRC-211.1-22 mix design method — absolute volume method."""

    @property
    def code_name(self) -> str:
        return "aci211"

    @property
    def code_full_name(self) -> str:
        return "ACI PRC-211.1-22"

    def calculate_target_mean_strength(
        self, target_strength_mpa: float, std_dev: float | None = None,
        has_production_data: bool = True,
    ) -> float:
        """ACI 211.1 / ACI 318 target mean strength.

        When has_production_data=True (≥30 tests available):
            f'cr = max(f'c + 1.34×s, f'c + 2.33×s - 3.45)

        When has_production_data=False (no prior data):
            Uses ACI 318 Table 26.4.3.1(b) overdesign table.

        Args:
            target_strength_mpa: Specified compressive strength f'c (MPa)
            std_dev: Standard deviation in MPa (default 4.0 ≈ 600 psi)
            has_production_data: Whether ≥30 test results exist
        """
        if not has_production_data:
            return round(get_no_data_overdesign(target_strength_mpa), 1)

        s = std_dev if std_dev is not None else 4.0  # default 4 MPa ≈ 600 psi

        # Both ACI 318 formulas; use the larger
        fcr_statistical = target_strength_mpa + 1.34 * s
        fcr_limited = target_strength_mpa + 2.33 * s - 3.45

        fcr = max(fcr_statistical, fcr_limited)

        # Must be at least f'c + 2.4 MPa (≈350 psi) per ACI 318
        fcr = max(fcr, target_strength_mpa + 2.4)

        return round(fcr, 1)

    def get_water_content(
        self, nmsa: int, slump_mm: float, **kwargs
    ) -> float:
        """Get water content from ACI Table 5.3.3."""
        air_entrained = kwargs.get("air_entrained", False)
        return interpolate_water_content(nmsa, slump_mm, air_entrained)

    def get_w_c_ratio(
        self, target_mean_strength_mpa: float, **kwargs
    ) -> float:
        """Get w/cm ratio from ACI PRC-211.1-22 Table 5.3.4."""
        air_entrained = kwargs.get("air_entrained", False)
        return interpolate_w_c_ratio(target_mean_strength_mpa, air_entrained)

    def get_coarse_aggregate_volume(self, nmsa: int, **kwargs) -> float:
        """Get CA volume fraction from ACI Table 5.3.6.

        Returns volume of dry-rodded CA per unit volume of concrete.
        """
        fm = kwargs.get("fineness_modulus", 2.70)
        return interpolate_ca_volume(nmsa, fm)

    def get_air_content(self, nmsa: int, **kwargs) -> float:
        """Get air content from ACI Table 5.3.3."""
        exposure = kwargs.get("exposure", "moderate")
        air_entrained = kwargs.get("air_entrained", False)
        return get_air_content(nmsa, exposure, air_entrained)

    def design(self, inp: MixDesignInput) -> MixDesignResult:
        """Run full ACI 211.1 mix design using absolute volume method."""
        steps: list[CalculationStep] = []
        warnings: list[str] = []
        nmsa = inp.nmsa

        # Determine exposure level for air content
        exposure_map = {
            "mild": "mild",
            "moderate": "moderate",
            "severe": "severe",
            "very_severe": "severe",
            "extreme": "severe",
        }
        exposure = exposure_map.get(inp.exposure_class or "moderate", "moderate")

        # Step 1: Target mean strength
        has_data = getattr(inp, "has_production_data", True)
        fcr = self.calculate_target_mean_strength(
            inp.target_strength_mpa, has_production_data=has_data
        )
        formula = (
            "Table 26.4.3.1(b) (no data)"
            if not has_data
            else "max(f'c + 1.34s, f'c + 2.33s - 3.45)"
        )
        steps.append(self._make_step(
            1, "Target mean strength (f'cr)",
            formula,
            {"f'c": inp.target_strength_mpa, "s": 4.0, "has_data": has_data},
            fcr, "MPa",
            "ACI 318"
        ))

        # Step 2: Slump selection (input already has it)
        steps.append(self._make_step(
            2, "Slump",
            "Selected based on structural element type",
            {"slump_mm": inp.slump_mm},
            inp.slump_mm, "mm",
            "ACI PRC-211.1-22 Table 5.3.1"
        ))

        # Step 3: Water content
        base_water_kg = self.get_water_content(nmsa, inp.slump_mm, air_entrained=inp.air_entrained)
        water_kg = base_water_kg
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            reduction_pct = inp.admixture.water_reduction_percent
            water_kg = base_water_kg * (1.0 - reduction_pct / 100.0)
            steps.append(self._make_step(
                3, "Water content (with admixture reduction)",
                f"Base water {base_water_kg:.1f} kg/m³ reduced by {reduction_pct:.1f}% ({inp.admixture.type_string})",
                {"base_water": base_water_kg, "reduction_pct": reduction_pct, "admixture_type": inp.admixture.type_string},
                water_kg, "kg/m³",
                "ACI PRC-211.1-22 §6.3 / Table 5.3.3"
            ))
        else:
            steps.append(self._make_step(
                3, "Water content",
                "From Table 5.3.3 by NMSA and slump",
                {"nmsa": nmsa, "slump": inp.slump_mm, "air_entrained": inp.air_entrained},
                water_kg, "kg/m³",
                "ACI PRC-211.1-22 Table 5.3.3"
            ))

        # Step 4: Air content
        air_percent = self.get_air_content(
            nmsa, exposure=exposure, air_entrained=inp.air_entrained
        )
        steps.append(self._make_step(
            4, "Air content",
            "From Table 5.3.3 by NMSA and exposure (ACI 318 F-class)",
            {"nmsa": nmsa, "exposure": exposure, "air_entrained": inp.air_entrained},
            air_percent, "%",
            "ACI PRC-211.1-22 Table 5.3.3"
        ))

        # Step 5: W/C ratio
        if inp.w_c_ratio is not None:
            wc = inp.w_c_ratio
        else:
            wc = self.get_w_c_ratio(fcr, air_entrained=inp.air_entrained)

        # Apply ACI 318 Table 19.3.2 sulfate exposure W/C limits
        sulfate_class = getattr(inp, "sulfate_exposure_class", "S0")
        if sulfate_class in ACI_MAX_WC_FOR_EXPOSURE:
            max_wc = ACI_MAX_WC_FOR_EXPOSURE[sulfate_class]
            if wc > max_wc:
                warnings.append(
                    f"W/C ratio {wc:.2f} reduced to {max_wc:.2f} "
                    f"for sulfate exposure class '{sulfate_class}' per ACI 318 Table 19.3.2"
                )
                wc = max_wc

        steps.append(self._make_step(
            5, "Water-cement ratio",
            "From Table 5.3.4 by required average strength (interpolated)",
            {"f'cr": fcr, "air_entrained": inp.air_entrained, "sulfate_class": sulfate_class},
            wc, "",
            "ACI PRC-211.1-22 Table 5.3.4 / ACI 318 Table 19.3.2"
        ))

        # Step 6: Cement content
        scm_replacement = inp.total_scm_replacement_percent
        cementitious_total = water_kg / wc
        scm_kg = cementitious_total * (scm_replacement / 100.0)
        cement_kg = cementitious_total - scm_kg

        steps.append(self._make_step(
            6, "Cement content",
            "Cementitious = Water / w/cm ratio",
            {"water": water_kg, "wc": wc, "scm_replacement_pct": scm_replacement},
            cement_kg, "kg/m³",
            "ACI PRC-211.1-22 §5.3.5"
        ))

        if scm_kg > 0:
            steps.append(self._make_step(
                6.1, "SCM content",
                "SCM = Total cementitious × replacement%",
                {"total_cementitious": cementitious_total, "replacement_pct": scm_replacement},
                scm_kg, "kg/m³",
                "ACI 211.1"
            ))

        # Admixture content & volume
        admixture_mass_kg = 0.0
        vol_admixture = 0.0
        admixture_type_result = None
        admixture_dosage_result = None

        if inp.admixture and inp.admixture.dosage_percent > 0:
            admixture_mass_kg = cementitious_total * (inp.admixture.dosage_percent / 100.0)
            admixture_type_result = inp.admixture.type_string
            admixture_dosage_result = inp.admixture.dosage_percent
            admixture_sg = getattr(inp.admixture, "specific_gravity", 1.15)
            vol_admixture = absolute_volume(admixture_mass_kg, admixture_sg)
            steps.append(self._make_step(
                6.2, "Chemical admixture content",
                f"Admixture = {inp.admixture.dosage_percent:.2f}% by mass of cementitious material",
                {"cementitious_total": cementitious_total, "dosage_pct": inp.admixture.dosage_percent, "admixture_mass_kg": admixture_mass_kg},
                admixture_mass_kg, "kg/m³",
                "ACI PRC-211.1-22 §4.5 / §6.3"
            ))

        # Step 7: Coarse aggregate volume (ACI PRC-211.1-22 §5.3.6)
        ca_vol_fraction = self.get_coarse_aggregate_volume(
            nmsa, fineness_modulus=inp.fine_aggregate.fineness_modulus
        )
        # CA volume = fraction × total concrete volume (1 m³)
        ca_vol_m3 = ca_vol_fraction  # per 1 m³ of concrete
        # Oven-dry-rodded weight = dry-rodded volume × dry-rodded density;
        # convert to SSD basis by multiplying by (1 + absorption), exactly as
        # ACI PRC-211.1-22 Example 1 (§9.2.6):
        #   1917 lb/yd³ × (1 + 0.5%) = 1927 lb/yd³ (SSD)
        ca_dry_kg = ca_vol_m3 * inp.coarse_aggregate.bulk_density_kg_m3
        ca_kg = ca_dry_kg * (1.0 + inp.coarse_aggregate.absorption_percent / 100.0)

        steps.append(self._make_step(
            7, "Coarse aggregate volume",
            f"CA (SSD) = Table 5.3.6 value × dry-rodded density × (1 + {inp.coarse_aggregate.absorption_percent:.1f}%)",
            {
                "nmsa": nmsa,
                "fm": inp.fine_aggregate.fineness_modulus,
                "dry_rodded_kg": ca_dry_kg,
                "absorption_pct": inp.coarse_aggregate.absorption_percent,
            },
            ca_kg, "kg/m³",
            "ACI PRC-211.1-22 Table 5.3.6 + §5.3.6 (SSD conversion)"
        ))

        # Step 8: Fine aggregate volume (by absolute volume method)
        vol_cement = absolute_volume(cement_kg, inp.cement.specific_gravity)
        vol_scm = absolute_volume(scm_kg, inp.scms[0].specific_gravity) if inp.scms else 0.0
        vol_water = absolute_volume(water_kg, SG_WATER)
        vol_ca = absolute_volume(ca_kg, inp.coarse_aggregate.specific_gravity)
        vol_air = air_percent / 100.0

        vol_fa = 1.0 - (vol_cement + vol_scm + vol_water + vol_ca + vol_air + vol_admixture)
        fa_kg = vol_fa * inp.fine_aggregate.specific_gravity * 1000.0

        steps.append(self._make_step(
            8, "Fine aggregate content (absolute volume method)",
            "FA vol = 1.0 - (cement + water + CA(SSD) + air + admixture) volumes; "
            "FA mass = vol × SG × 1000",
            {"vol_cement": vol_cement, "vol_water": vol_water, "vol_ca": vol_ca, "vol_air": vol_air, "vol_admixture": vol_admixture},
            fa_kg, "kg/m³",
            "ACI PRC-211.1-22 §5.3.7"
        ))

        # Step 9: Moisture correction
        adjusted_water = adjust_water_for_aggregate_moisture(
            water_kg,
            fa_kg, inp.fine_aggregate.absorption_percent, inp.fine_aggregate.moisture_content_percent,
            ca_kg, inp.coarse_aggregate.absorption_percent, inp.coarse_aggregate.moisture_content_percent,
        )
        if abs(adjusted_water - water_kg) > 0.5:
            steps.append(self._make_step(
                9, "Moisture-corrected water",
                "Adjusted water = Design water - free moisture on aggregates",
                {"design_water": water_kg, "adjusted": adjusted_water},
                adjusted_water, "kg/m³",
                "ACI PRC-211.1-22 §5.3.9.1"
            ))

        # Field batch weights
        field_fa = correct_for_moisture(fa_kg, inp.fine_aggregate.absorption_percent, inp.fine_aggregate.moisture_content_percent)
        field_ca = correct_for_moisture(ca_kg, inp.coarse_aggregate.absorption_percent, inp.coarse_aggregate.moisture_content_percent)
        field_water = adjusted_water

        # Warnings
        if fa_kg < 0:
            warnings.append(
                "Negative fine aggregate volume — increase W/C ratio or reduce air content"
            )

        # Verify total volume
        actual_vol = total_volume(
            cement_kg, water_kg, fa_kg, ca_kg,
            inp.cement.specific_gravity,
            inp.fine_aggregate.specific_gravity,
            inp.coarse_aggregate.specific_gravity,
            air_percent,
            scm_kg,
            inp.scms[0].specific_gravity if inp.scms else 3.15,
        )
        if abs(actual_vol - 1.0) > 0.02:
            warnings.append(
                f"Total absolute volume {actual_vol:.4f} m³ deviates from 1.0 m³"
            )

        return MixDesignResult(
            code_used="ACI PRC-211.1-22",
            target_mean_strength_mpa=fcr,
            w_c_ratio=wc,
            water_kg=round(water_kg, 1),
            cement_kg=round(cement_kg, 1),
            scm_kg=round(scm_kg, 1),
            fine_aggregate_kg=round(fa_kg, 1),
            coarse_aggregate_kg=round(ca_kg, 1),
            air_volume_percent=round(air_percent, 1),
            volume_m3=inp.volume_m3,
            steps=tuple(steps),
            warnings=tuple(warnings),
            adjusted_water_kg=round(field_water, 1),
            field_fine_aggregate_kg=round(field_fa, 1),
            field_coarse_aggregate_kg=round(field_ca, 1),
            admixture_kg=round(admixture_mass_kg, 2) if admixture_mass_kg > 0 else None,
            admixture_type=admixture_type_result,
            admixture_dosage_percent=admixture_dosage_result,
        )
