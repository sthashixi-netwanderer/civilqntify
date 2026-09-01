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
from concrete_mix.utils.display import display_name
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
        """Get water content from IS 10262:2019 Table 4 (base + slump rule).

        The grading zone does not affect water content in IS 10262:2019.
        """
        return interpolate_water_content(nmsa, slump_mm)

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

        # Step 2: Water content (IS 10262:2019 Table 4 + Clause 5.3)
        # Sequence per the standard's Annex A/B worked examples:
        #   1. Base water from Table 4 (angular aggregate, 50 mm slump)
        #   2. Slump adjustment: ±3% per 25 mm from 50 mm (Clause 5.3)
        #   3. Aggregate shape adjustment in kg (Clause 5.3)
        #   4. Admixture water reduction (Clause 5.3 + Annex G)
        # (Annex A: 186 → 191.58 at 75 mm slump → 148 after 23% reduction.)
        base_water = WATER_CONTENT.get(nmsa, 186)
        water_kg = interpolate_water_content(nmsa, inp.slump_mm, grading_zone)

        # IS 10262:2019 Clause 5.3 — Adjust for aggregate shape
        # Table 4 assumes angular aggregate as base. Adjustments are in kg/m³:
        #   Sub-angular: -10 kg, gravel with some crushed particles: -15 kg,
        #   Rounded gravel: -20 kg
        agg_shape = inp.coarse_aggregate.shape.value
        shape_adj_kg = AGGREGATE_SHAPE_ADJUSTMENT_KG.get(agg_shape, 0.0)
        if shape_adj_kg != 0:
            water_kg += shape_adj_kg
            if shape_adj_kg < 0:
                warnings.append(
                    f"Water reduced by {abs(shape_adj_kg):.0f} kg/m³ "
                    f"for '{display_name(agg_shape)}' aggregate per IS 10262:2019 Clause 5.3"
                )
            else:
                warnings.append(
                    f"Water increased by {shape_adj_kg:.0f} kg/m³ "
                    f"for '{display_name(agg_shape)}' aggregate per IS 10262:2019 Clause 5.3"
                )

        # IS 10262:2019 Clause 5.3 — Admixture water reduction
        # Reference: Annex G for admixture types and typical water reduction
        water_before_admixture = water_kg  # slump + shape adjusted, before admixture
        admixture_mass_kg = 0.0

        # Step 2: Water content (IS 10262:2019 Table 4) — show water before
        # admixture reduction, including slump/shape adjustments.
        _slump_delta_pct = (inp.slump_mm - 50.0) / 25.0 * 3.0
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
                "IS 10262:2019 Table 4 + Clause 5.3",
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
                    f"Reduced by {reduction_pct:.1f}% ({display_name(admixture.type_string)})",
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
                    f"for '{display_name(inp.exposure_class)}' exposure per IS 456:2000"
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

        # IS 10262:2019 Clause 5.4.1 / Annex B — for fly ash (or other mineral
        # admixture) replacement of 20 percent or more, the cementitious
        # materials content may be increased by 10 percent for the preliminary
        # trial (Annex B: 431 × 1.10 = 474 kg/m³ at 30 % fly ash).
        if scm_replacement >= 20.0:
            cementitious_total *= 1.10
            warnings.append(
                f"SCM replacement {scm_replacement:.0f}% ≥ 20% — cementitious content "
                f"increased by 10% for preliminary trial per IS 10262:2019 Clause 5.4.1 "
                f"(Annex B practice)"
            )
            steps.append(
                self._make_step(
                    4.05,
                    "Cementitious increase (≥20% SCM)",
                    "Cementitious × 1.10 per Clause 5.4.1",
                    {"cementitious_before": water_kg / wc, "increase_pct": 10.0},
                    cementitious_total,
                    "kg/m³",
                    "IS 10262:2019 Clause 5.4.1, Annex B",
                )
            )

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
                f"for '{display_name(inp.exposure_class) if inp.exposure_class else 'mild'}' exposure per IS 456:2000"
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
                    f"(type: {display_name(admixture.type_string)})",
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
        # Base CA fraction from Table 5 keyed by the fine-aggregate grading
        # zone (classified per IS 383 Table 9). An explicit
        # ca_volume_fraction_override (the form's Table 5 row selection,
        # also used when a PSD analysis locks the zone) replaces the zone
        # lookup; the Clause 5.5.1 w/c adjustment applies either way.
        ca_fraction_override = getattr(inp, "ca_volume_fraction_override", None)
        if ca_fraction_override is not None:
            ca_fraction_base = float(ca_fraction_override)
            base_desc = f"Table 5 fraction (override): {ca_fraction_base:.2f}"
        else:
            ca_fraction_base = self.get_coarse_aggregate_volume(
                nmsa, grading_zone=grading_zone
            )
            base_desc = f"Table 5 fraction: {ca_fraction_base}"
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
                f"{base_desc}{wcr_adj_desc}",
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

        # Step 8: Trial Mixes Protocol per IS 10262:2019 Clause 5.8
        wc_trial3 = round(wc * 0.90, 2)
        wc_trial4 = round(wc * 1.10, 2)
        steps.append(
            self._make_step(
                8,
                "Trial mixes protocol",
                "4 trial batches: Trial 1 (initial) → Trial 2 (workability adj) → Trials 3 & 4 (W/C ±10%)",
                {
                    "trial_1_2_wc": round(wc, 2),
                    "trial_3_wc": wc_trial3,
                    "trial_4_wc": wc_trial4,
                },
                4.0,
                "batches",
                "IS 10262:2019 Clause 5.8",
            )
        )

        # Trial batch recommendation per Clause 5.8
        warnings.append(
            "IS 10262:2019 Clause 5.8: Mandatory 4-trial batch protocol required — "
            "Trial 1 (workability & segregation/bleeding check), Trial 2 (water/admixture adjustment at constant W/C), "
            f"Trials 3 & 4 (same water with W/C ±10%: {wc_trial3:.2f} & {wc_trial4:.2f} to establish strength vs. W/C curve), "
            "followed by field trials and Clause 5.8.1 reporting."
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


def calculate_is10262_trial_mixes(
    result: MixDesignResult,
    inp: MixDesignInput | None = None,
) -> dict[str, Any]:
    """Calculate the 4 trial mix batches per IS 10262:2019 Clause 5.8.

    IS 10262:2019 Clause 5.8 specifies:
    - Trial Mix 1: Initial laboratory batch with calculated proportions. Measure
      workability (slump/flow), observe freedom from segregation and bleeding, and
      check finishing properties.
    - Trial Mix 2: If measured workability differs from target, adjust water and/or
      admixture content while keeping free W/C at the design value.
    - Trial Mixes 3 & 4: Water content is kept same as Trial Mix 2, while W/C is varied
      by ±10% of the pre-selected value to establish the compressive strength vs. W/C curve.
    - Proportions Finalization: Proportions are finalized from Trials 2 to 4 to satisfy
      both strength and durability requirements, followed by field trials.
    - Clause 5.8.1 Reporting: Mandatory documentation items.
    """
    w1 = result.water_kg
    c1 = result.cement_kg
    scm1 = result.scm_kg
    wc1 = result.w_c_ratio
    fa1 = result.fine_aggregate_kg
    ca1 = result.coarse_aggregate_kg
    adm1 = result.admixture_kg or 0.0
    air_pct = result.air_volume_percent

    if inp is not None:
        sg_c = inp.cement.specific_gravity
        sg_scm = inp.scms[0].specific_gravity if inp.scms else 3.15
        sg_fa = inp.fine_aggregate.specific_gravity
        sg_ca = inp.coarse_aggregate.specific_gravity
        sg_adm = inp.admixture.specific_gravity if inp.admixture else 1.15
        dosage_pct = inp.admixture.dosage_percent if inp.admixture else 0.0
        scm_pct = inp.total_scm_replacement_percent
        nmsa = inp.nmsa
        grading_zone = inp.fine_aggregate.grading_zone or "II"
        ca_frac_base = get_ca_volume_fraction(nmsa, grading_zone)
    else:
        sg_c = 3.15
        sg_scm = 2.20 if scm1 > 0 else 3.15
        sg_fa = 2.65
        sg_ca = 2.65
        sg_adm = 1.15
        cm_total = c1 + scm1
        scm_pct = (scm1 / cm_total * 100.0) if cm_total > 0 else 0.0
        dosage_pct = (adm1 / cm_total * 100.0) if (adm1 > 0 and cm_total > 0) else 0.0
        vol_ca = ca1 / (sg_ca * 1000.0)
        vol_fa = fa1 / (sg_fa * 1000.0)
        ca_frac_base = vol_ca / (vol_ca + vol_fa) if (vol_ca + vol_fa) > 0 else 0.62

    # Trial 1: Calculated design
    t1 = {
        "trial_number": 1,
        "name": "Trial Mix No. 1 (Calculated Design Proportions)",
        "w_c_ratio": round(wc1, 2),
        "water_kg": round(w1, 1),
        "cement_kg": round(c1, 1),
        "scm_kg": round(scm1, 1),
        "fine_agg_kg": round(fa1, 1),
        "coarse_agg_kg": round(ca1, 1),
        "admixture_kg": round(adm1, 2) if adm1 > 0 else 0.0,
        "purpose": "Initial laboratory trial. Measure workability (slump/flow), inspect for freedom from segregation/bleeding and finishing properties.",
        "action": "If slump matches target and mix is cohesive, proceed. If workability differs, adjust water/admixture for Trial 2.",
    }

    # Trial 2: Workability adjusted baseline
    t2 = {
        "trial_number": 2,
        "name": "Trial Mix No. 2 (Workability-Adjusted Baseline)",
        "w_c_ratio": round(wc1, 2),
        "water_kg": round(w1, 1),
        "cement_kg": round(c1, 1),
        "scm_kg": round(scm1, 1),
        "fine_agg_kg": round(fa1, 1),
        "coarse_agg_kg": round(ca1, 1),
        "admixture_kg": round(adm1, 2) if adm1 > 0 else 0.0,
        "purpose": "Adjust water and/or admixture dosage if Trial 1 workability differed, while holding free W/C constant at target.",
        "action": "Establish confirmed baseline water content for Trials 3 and 4.",
    }

    # Trial 3: W/C -10%
    wc3 = round(wc1 * 0.90, 2)
    cm3 = w1 / wc3
    if scm_pct >= 20.0:
        cm3 *= 1.10
    scm3 = cm3 * (scm_pct / 100.0)
    c3 = cm3 - scm3
    adm3 = cm3 * (dosage_pct / 100.0) if dosage_pct > 0 else 0.0

    vol_c3 = c3 / (sg_c * 1000.0)
    vol_scm3 = scm3 / (sg_scm * 1000.0) if scm3 > 0 else 0.0
    vol_w3 = w1 / 1000.0
    vol_air3 = air_pct / 100.0
    vol_adm3 = (adm3 / (sg_adm * 1000.0)) if adm3 > 0 else 0.0
    vol_agg3 = max(0.0, 1.0 - (vol_c3 + vol_scm3 + vol_w3 + vol_air3 + vol_adm3))

    ca_frac3 = adjust_ca_volume_for_wcr(ca_frac_base, wc3)
    vol_ca3 = vol_agg3 * ca_frac3
    vol_fa3 = vol_agg3 - vol_ca3
    ca3 = vol_ca3 * sg_ca * 1000.0
    fa3 = vol_fa3 * sg_fa * 1000.0

    t3 = {
        "trial_number": 3,
        "name": f"Trial Mix No. 3 (W/C -10%: {wc3:.2f})",
        "w_c_ratio": wc3,
        "water_kg": round(w1, 1),
        "cement_kg": round(c3, 1),
        "scm_kg": round(scm3, 1),
        "fine_agg_kg": round(fa3, 1),
        "coarse_agg_kg": round(ca3, 1),
        "admixture_kg": round(adm3, 2) if adm3 > 0 else 0.0,
        "purpose": "Lower W/C ratio by ~10% (same water content as Trial 2, increased cementitious content) to establish higher strength curve point.",
        "action": "Cast test cubes (7 & 28 days) and measure workability.",
    }

    # Trial 4: W/C +10%
    wc4 = round(wc1 * 1.10, 2)
    cm4 = w1 / wc4
    if scm_pct >= 20.0:
        cm4 *= 1.10
    scm4 = cm4 * (scm_pct / 100.0)
    c4 = cm4 - scm4
    adm4 = cm4 * (dosage_pct / 100.0) if dosage_pct > 0 else 0.0

    vol_c4 = c4 / (sg_c * 1000.0)
    vol_scm4 = scm4 / (sg_scm * 1000.0) if scm4 > 0 else 0.0
    vol_w4 = w1 / 1000.0
    vol_air4 = air_pct / 100.0
    vol_adm4 = (adm4 / (sg_adm * 1000.0)) if adm4 > 0 else 0.0
    vol_agg4 = max(0.0, 1.0 - (vol_c4 + vol_scm4 + vol_w4 + vol_air4 + vol_adm4))

    ca_frac4 = adjust_ca_volume_for_wcr(ca_frac_base, wc4)
    vol_ca4 = vol_agg4 * ca_frac4
    vol_fa4 = vol_agg4 - vol_ca4
    ca4 = vol_ca4 * sg_ca * 1000.0
    fa4 = vol_fa4 * sg_fa * 1000.0

    t4 = {
        "trial_number": 4,
        "name": f"Trial Mix No. 4 (W/C +10%: {wc4:.2f})",
        "w_c_ratio": wc4,
        "water_kg": round(w1, 1),
        "cement_kg": round(c4, 1),
        "scm_kg": round(scm4, 1),
        "fine_agg_kg": round(fa4, 1),
        "coarse_agg_kg": round(ca4, 1),
        "admixture_kg": round(adm4, 2) if adm4 > 0 else 0.0,
        "purpose": "Higher W/C ratio by ~10% (same water content as Trial 2, decreased cementitious content) to establish lower strength curve point.",
        "action": "Cast test cubes (7 & 28 days) and measure workability. Verify cement meets IS 456 minimum durability limit.",
    }

    return {
        "standard": "IS 10262:2019",
        "clause": "Clause 5.8 (Trial Mixes) & Clause 5.8.1 (Reporting)",
        "summary": (
            "IS 10262:2019 Clause 5.8 requires that calculated mix proportions be checked and validated "
            "by a sequence of 4 trial batches in the laboratory to develop the compressive strength vs. "
            "water-cement ratio curve before final production."
        ),
        "trials": [t1, t2, t3, t4],
        "reporting_checklist": [
            ("a", "Period of testing (starting and ending date)"),
            ("b", "Details of work / type of structure"),
            ("c", "All mix design input data as per Clause 4.1 & IS 456 deviations"),
            ("d", "Relevant test data of different materials (aggregates, cement, water, admixtures)"),
            ("e", "Details of materials (brand of cement, mfg date/week, % pozzolana/slag, aggregate sources)"),
            ("f", "Details of the 4 trial batches conducted (workability, bleeding, cube compressive strengths)"),
            ("g", "Recommended final mix proportions and field trial validation records"),
        ],
    }

