"""IS 10262:2019 concrete mix design implementation.

Implements the 5-step empirical method for proportioning concrete
per IS 10262:2019 and IS 456:2000.
"""

from __future__ import annotations

from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.tables.is_tables import (
    AGGREGATE_SHAPE_ADJUSTMENT_KG,
    WATER_CONTENT,
    adjust_ca_volume_for_wcr,
    calculate_target_strength,
    get_ca_volume_fraction,
    get_exposure_limits,
    get_std_dev,
    interpolate_w_c_ratio,
    interpolate_water_content,
)
from concrete_mix.engine.moisture_correction import (
    adjust_water_for_aggregate_moisture,
    correct_for_moisture,
)
from concrete_mix.engine.volume_calculator import absolute_volume, total_volume
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult
from concrete_mix.utils.constants import SG_WATER


class IS10262MixDesign(MixDesignCode):
    """IS 10262:2019 mix design method — 5-step empirical method."""

    @property
    def code_name(self) -> str:
        return "is10262"

    @property
    def code_full_name(self) -> str:
        return "IS 10262:2019"

    def calculate_target_mean_strength(
        self, target_strength_mpa: float, std_dev: float | None = None
    ) -> float:
        """IS 10262:2019 target mean strength (Clause 4.2).

        f'ck = max(fck + 1.65×S, fck + X)
        """
        ftm, _ = calculate_target_strength(target_strength_mpa, std_dev)
        return ftm

    def get_water_content(self, nmsa: int, slump_mm: float, **kwargs) -> float:
        """Get water content from IS 10262:2019 Table 4, adjusted for grading zone."""
        grading_zone = kwargs.get("grading_zone", "II")
        return interpolate_water_content(nmsa, slump_mm, grading_zone)

    def get_water_content_by_nmsa(self, nmsa: int) -> float:
        """Get water content from Table 4 (read-only, depends only on NMSA)."""
        if nmsa not in WATER_CONTENT:
            raise ValueError(f"NMSA {nmsa}mm not in IS water content table")
        return WATER_CONTENT[nmsa]

    def get_w_c_ratio(self, target_mean_strength_mpa: float, **kwargs) -> float:
        """Get W/C ratio from IS 10262 Figure 1/2/3 by cement type."""
        cement_type = kwargs.get("cement_type", "OPC_43")
        return interpolate_w_c_ratio(target_mean_strength_mpa, cement_type)

    def get_coarse_aggregate_volume(self, nmsa: int, **kwargs) -> float:
        """Get CA volume fraction from IS 10262 Table 7.

        Returns volume of CA per unit volume of total aggregate.
        """
        grading_zone = kwargs.get("grading_zone", "II")
        return get_ca_volume_fraction(nmsa, grading_zone)

    def get_air_content(self, nmsa: int, **kwargs) -> float:
        """IS 10262:2019 Table 11 — entrapped air only."""
        air_map = {10: 1.5, 20: 1.0, 40: 0.8, 80: 0.3, 150: 0.2}
        return air_map.get(nmsa, 1.0)

    def _get_cement_type_string(self, inp: MixDesignInput) -> str:
        """Map CementType enum to IS cement type string."""
        from concrete_mix.models.materials import CementType

        mapping = {
            CementType.OPC_33: "OPC_33",
            CementType.OPC_43: "OPC_43",
            CementType.OPC_53: "OPC_53",
            CementType.PPC: "PPC",
            CementType.PSC: "PSC",
        }
        return mapping.get(inp.cement.type, "OPC_43")

    def design(self, inp: MixDesignInput) -> MixDesignResult:
        """Run full IS 10262:2019 mix design using 5-step method."""
        steps: list[CalculationStep] = []
        warnings: list[str] = []
        nmsa = inp.nmsa
        grading_zone = inp.fine_aggregate.grading_zone or "II"
        cement_type_str = self._get_cement_type_string(inp)

        # Determine standard deviation
        grade_name = f"M{int(inp.target_strength_mpa)}"
        std_dev = get_std_dev(grade_name)

        # Step 1: Target mean strength (IS 10262:2019 Clause 4.2)
        ftm, strength_desc = calculate_target_strength(inp.target_strength_mpa, std_dev)
        steps.append(
            self._make_step(
                1,
                "Target mean strength (f'ck)",
                strength_desc,
                {"fck": inp.target_strength_mpa, "σ": std_dev},
                ftm,
                "MPa",
                "IS 10262:2019 Clause 4.2",
            )
        )

        # Step 2: Water content (IS 10262:2019 Table 4)
        # Base water content from Table 4 by NMSA
        base_water = WATER_CONTENT.get(nmsa, 186)
        water_kg = base_water

        # Adjust for grading zone (and slump if no admixture is used)
        effective_slump = 50.0 if (inp.admixture and inp.admixture.water_reduction_percent > 0) else inp.slump_mm
        water_kg = interpolate_water_content(nmsa, effective_slump, grading_zone)

        # IS 10262:2019 Clause 5.2 — Adjust for aggregate shape
        # Table 4 assumes angular aggregate as base. Adjustments are in kg/m³:
        #   Sub-angular: -10 kg, Rounded gravel: -20 kg
        agg_shape = inp.coarse_aggregate.shape.value
        shape_adj_kg = AGGREGATE_SHAPE_ADJUSTMENT_KG.get(agg_shape, 0.0)
        if shape_adj_kg != 0:
            water_kg += shape_adj_kg
            if shape_adj_kg < 0:
                warnings.append(
                    f"Water reduced by {abs(shape_adj_kg):.0f} kg/m³ "
                    f"for '{agg_shape}' aggregate per IS 10262:2019 Clause 5.2"
                )
            else:
                warnings.append(
                    f"Water increased by {shape_adj_kg:.0f} kg/m³ "
                    f"for '{agg_shape}' aggregate per IS 10262:2019 Clause 5.2"
                )

        # IS 10262:2019 Clause 5.3 — Admixture water reduction
        # Reference: Annex G for admixture types and typical water reduction
        water_before_admixture = water_kg  # base + shape adjusted, before admixture
        admixture_mass_kg = 0.0

        # Step 2: Water content (IS 10262:2019 Table 4) — show water before
        # admixture reduction, including slump/grading/shape adjustments.
        _slump_delta_pct = (effective_slump - 50.0) / 25.0 * 3.0
        _formula_parts = [f"NMSA {nmsa}mm → {base_water} kg/m³"]
        if abs(_slump_delta_pct) > 0.01:
            _formula_parts.append(f"slump adj {_slump_delta_pct:+.1f}%")
        if shape_adj_kg != 0:
            _formula_parts.append(f"shape adj {shape_adj_kg:+.0f} kg")
        steps.append(
            self._make_step(
                2,
                "Water content (before admixture reduction)",
                "From Table 4: " + ", ".join(_formula_parts),
                {
                    "nmsa": nmsa,
                    "grading_zone": grading_zone,
                    "slump_mm": inp.slump_mm,
                    "shape": agg_shape if shape_adj_kg != 0 else "none",
                },
                water_before_admixture,
                "kg/m³",
                "IS 10262:2019 Table 4 + Clause 5.2",
            )
        )

        # Step 2.1: Admixture water reduction — only when admixture is present
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            admixture = inp.admixture
            reduction_pct = admixture.water_reduction_percent
            reduction = water_kg * (reduction_pct / 100.0)
            water_kg -= reduction

            steps.append(
                self._make_step(
                    2.1,
                    "Admixture water reduction",
                    f"Reduced by {reduction_pct:.1f}% ({admixture.type_string})",
                    {
                        "water_before": water_before_admixture,
                        "reduction_pct": reduction_pct,
                        "reduction_kg": reduction,
                        "admixture_type": admixture.type_string,
                    },
                    water_kg,
                    "kg/m³",
                    "IS 10262:2019 Clause 5.3 + Annex G",
                )
            )

        # Step 3: W/C ratio
        if inp.w_c_ratio is not None:
            wc = inp.w_c_ratio
        else:
            wc = self.get_w_c_ratio(ftm, cement_type=cement_type_str)

        # Apply exposure class limits (IS 456:2000)
        if inp.exposure_class:
            limits = get_exposure_limits(inp.exposure_class, inp.concrete_type)
            if wc > limits["max_wc"]:
                warnings.append(
                    f"W/C ratio {wc:.2f} reduced to {limits['max_wc']:.2f} "
                    f"for '{inp.exposure_class}' exposure per IS 456:2000"
                )
                wc = limits["max_wc"]

        steps.append(
            self._make_step(
                3,
                "Water-cement ratio",
                f"From Figure for {cement_type_str} cement at ftm",
                {"ftm": ftm, "cement_type": cement_type_str},
                wc,
                "",
                "IS 10262:2019 Figure 1",
            )
        )

        # Step 4: Cement content
        scm_replacement = inp.total_scm_replacement_percent
        cementitious_total = water_kg / wc
        scm_kg = cementitious_total * (scm_replacement / 100.0)
        cement_kg = cementitious_total - scm_kg

        # Check minimum cement content per IS 456
        min_cement = 220.0  # default: plain concrete mild exposure
        if inp.exposure_class:
            limits = get_exposure_limits(inp.exposure_class, inp.concrete_type)
            min_cement = limits["min_cement_kg_m3"]

        if cement_kg < min_cement:
            warnings.append(
                f"Cement {cement_kg:.0f} kg/m³ below minimum {min_cement:.0f} kg/m³ "
                f"for '{inp.exposure_class or 'mild'}' exposure per IS 456:2000"
            )
            cement_kg = min_cement
            cementitious_total = cement_kg + scm_kg

        steps.append(
            self._make_step(
                4,
                "Cement content",
                "Cement = Water / W/C ratio",
                {"water": water_kg, "wc": wc, "scm_replacement_pct": scm_replacement},
                cement_kg,
                "kg/m³",
                "IS 10262:2019 Clause 5.3",
            )
        )

        if scm_kg > 0:
            steps.append(
                self._make_step(
                    4.1,
                    "SCM content",
                    "SCM = Total cementitious × replacement%",
                    {
                        "total_cementitious": cementitious_total,
                        "replacement_pct": scm_replacement,
                    },
                    scm_kg,
                    "kg/m³",
                    "IS 10262:2019",
                )
            )

        # IS 10262:2019 Annex A (A-9e) — Admixture mass and volume calculation
        # Admixture dosage is % by mass of cementitious material
        # Volume = Mass / (Specific gravity × 1000)
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            admixture = inp.admixture
            admixture_mass_kg = cementitious_total * (admixture.dosage_percent / 100.0)

            steps.append(
                self._make_step(
                    4.2,
                    "Admixture content",
                    f"Admixture = {admixture.dosage_percent:.2f}% by mass of cementitious material "
                    f"(type: {admixture.type_string})",
                    {
                        "cementitious_total": cementitious_total,
                        "dosage_pct": admixture.dosage_percent,
                        "admixture_type": admixture.type_string,
                        "specific_gravity": admixture.specific_gravity,
                    },
                    admixture_mass_kg,
                    "kg/m³",
                    "IS 10262:2019 Annex A (A-9e)",
                )
            )

        # Step 5: Aggregate proportions (IS 10262:2019 Clause 5.5)
        # Get base CA fraction from Table 5, then adjust for W/C ratio
        ca_fraction_base = self.get_coarse_aggregate_volume(
            nmsa, grading_zone=grading_zone
        )
        ca_fraction = adjust_ca_volume_for_wcr(ca_fraction_base, wc)
        wcr_adj_desc = ""
        if abs(ca_fraction - ca_fraction_base) > 0.001:
            wcr_adj_desc = f" (adjusted from {ca_fraction_base} at W/C=0.50, Δ={ca_fraction - ca_fraction_base:+.2f})"

        # IS method: CA fraction is of TOTAL AGGREGATE volume
        # IS 10262:2019 Annex A (A-9) — Mix calculations per unit volume
        air_percent = self.get_air_content(nmsa)
        vol_cement = absolute_volume(cement_kg, inp.cement.specific_gravity)
        vol_scm = (
            absolute_volume(scm_kg, inp.scms[0].specific_gravity) if inp.scms else 0.0
        )
        vol_water = absolute_volume(water_kg, SG_WATER)
        vol_air = air_percent / 100.0

        # IS 10262:2019 Annex A (A-9e) — Include admixture volume in absolute volume calculation
        vol_admixture = 0.0
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            admixture_mass_kg = cementitious_total * (
                inp.admixture.dosage_percent / 100.0
            )
            vol_admixture = absolute_volume(
                admixture_mass_kg, inp.admixture.specific_gravity
            )

        vol_total_agg = 1.0 - (
            vol_cement + vol_scm + vol_water + vol_air + vol_admixture
        )
        vol_ca = vol_total_agg * ca_fraction
        vol_fa = vol_total_agg - vol_ca

        ca_kg = vol_ca * inp.coarse_aggregate.specific_gravity * 1000.0
        fa_kg = vol_fa * inp.fine_aggregate.specific_gravity * 1000.0

        steps.append(
            self._make_step(
                5,
                "Coarse aggregate proportion",
                f"Table 5 fraction: {ca_fraction_base}{wcr_adj_desc}",
                {
                    "nmsa": nmsa,
                    "grading_zone": grading_zone,
                    "ca_fraction_base": ca_fraction_base,
                    "wcr": wc,
                    "ca_fraction_adjusted": ca_fraction,
                },
                ca_kg,
                "kg/m³",
                "IS 10262:2019 Table 5 + Clause 5.5.1",
            )
        )

        steps.append(
            self._make_step(
                6,
                "Fine aggregate proportion",
                "FA volume = Total aggregate volume - CA volume",
                {"vol_total_agg": vol_total_agg, "vol_ca": vol_ca},
                fa_kg,
                "kg/m³",
                "IS 10262:2019",
            )
        )

        # Moisture correction
        adjusted_water = adjust_water_for_aggregate_moisture(
            water_kg,
            fa_kg,
            inp.fine_aggregate.absorption_percent,
            inp.fine_aggregate.moisture_content_percent,
            ca_kg,
            inp.coarse_aggregate.absorption_percent,
            inp.coarse_aggregate.moisture_content_percent,
        )
        if abs(adjusted_water - water_kg) > 0.5:
            steps.append(
                self._make_step(
                    7,
                    "Moisture-corrected water",
                    "Adjusted water = Design water - free moisture from aggregates",
                    {"design_water": water_kg, "adjusted": adjusted_water},
                    adjusted_water,
                    "kg/m³",
                    "IS 10262:2019",
                )
            )

        # Field batch weights (adjusted for actual moisture in aggregates)
        field_fa = correct_for_moisture(
            fa_kg,
            inp.fine_aggregate.absorption_percent,
            inp.fine_aggregate.moisture_content_percent,
        )
        field_ca = correct_for_moisture(
            ca_kg,
            inp.coarse_aggregate.absorption_percent,
            inp.coarse_aggregate.moisture_content_percent,
        )
        field_water = adjusted_water

        # Verify total volume
        actual_vol = total_volume(
            cement_kg,
            water_kg,
            fa_kg,
            ca_kg,
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

        # Trial batch recommendation
        warnings.append(
            "IS 10262:2019 recommends minimum 3 trial batches for validation"
        )

        # Calculate admixture mass for result
        admixture_mass_result = 0.0
        admixture_type_result = None
        admixture_dosage_result = None
        water_reduction_result = None
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            admixture_mass_result = cementitious_total * (
                inp.admixture.dosage_percent / 100.0
            )
            admixture_type_result = inp.admixture.type_string
            admixture_dosage_result = inp.admixture.dosage_percent
            water_reduction_result = inp.admixture.water_reduction_percent

        return MixDesignResult(
            code_used="IS 10262:2019",
            target_mean_strength_mpa=ftm,
            w_c_ratio=round(wc, 2),
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
            admixture_kg=round(admixture_mass_result, 2)
            if admixture_mass_result > 0
            else None,
            admixture_type=admixture_type_result,
            admixture_dosage_percent=admixture_dosage_result,
            water_reduction_percent=water_reduction_result,
        )
