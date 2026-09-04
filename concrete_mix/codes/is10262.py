"""IS 10262:2019 concrete mix design implementation.

Implements the 5-step empirical method for proportioning concrete
per IS 10262:2019 and IS 456:2000.
"""

from __future__ import annotations

import math

from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.tables.is_tables import (
    AGGREGATE_SHAPE_ADJUSTMENT_KG,
    HS_AIR_CONTENT,
    HS_MINERAL_DOSAGE,
    IS456_MAX_CEMENT_KG_M3,
    MASS_AIR_CONTENT,
    MASS_MORTAR_VOLUME,
    MASS_ROUNDED_REDUCTION_KG,
    WATER_CONTENT,
    adjust_ca_volume_for_wcr,
    calculate_target_strength,
    get_ca_volume_fraction,
    get_exposure_limits,
    hs_ca_volume_fraction,
    hs_wcm_ratio,
    hs_water_content,
    interpolate_w_c_ratio,
    interpolate_water_content,
    mass_ca_volume_fraction,
    mass_water_content,
    required_min_fck_mpa,
    site_assumed_std_dev,
    table6_min_cement_adjustment,
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
        """IS 10262:2019 entrapped air — Table 3 (ordinary), Table 6 (HS),
        Table 11 (mass). Pass concrete_class="high_strength"/"mass" to
        select; defaults to the ordinary table."""
        concrete_class = kwargs.get("concrete_class", "ordinary")
        if concrete_class == "high_strength":
            if nmsa not in HS_AIR_CONTENT:
                raise ValueError(
                    f"NMSA {nmsa} mm has no Table 6 air content (§6.2.3)"
                )
            return HS_AIR_CONTENT[nmsa]
        if concrete_class == "mass":
            if nmsa not in MASS_AIR_CONTENT:
                raise ValueError(
                    f"NMSA {nmsa} mm has no Table 11 air content (§9.3)"
                )
            return MASS_AIR_CONTENT[nmsa]
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

        # IS 456:2000 Table 5 — the exposure class imposes a minimum grade
        # of concrete (e.g. M30 for severe/reinforced). Fail fast: a lower
        # characteristic strength can never satisfy durability.
        if inp.exposure_class:
            min_fck = required_min_fck_mpa(inp.exposure_class, inp.concrete_type)
            if min_fck is not None and inp.target_strength_mpa < min_fck:
                raise ValueError(
                    f"Characteristic strength M{inp.target_strength_mpa:g} is below "
                    f"the minimum grade M{min_fck:g} for "
                    f"'{display_name(inp.exposure_class)}' exposure "
                    f"({inp.concrete_type} concrete) per IS 456:2000 Table 5. "
                    f"Use M{min_fck:g} or higher, or a less severe exposure class."
                )
            # IS 10262:2019 Table 5 Note 4 — Zone IV fine aggregate is not
            # recommended in reinforced concrete unless tests have established
            # the suitability of the proposed mix proportions. (Table 13
            # admits Zone IV for mass concrete, so mass designs are exempt.)
            if (grading_zone == "IV" and inp.concrete_type == "reinforced"
                    and not inp.mass_concrete and nmsa not in (80, 150)):
                warnings.append(
                    "Fine aggregate Grading Zone IV should not be used in "
                    "reinforced concrete unless tests have been made to ascertain "
                    "the suitability of the proposed mix proportions "
                    "(IS 10262:2019 Table 5 Note 4)"
                )

        # Design route: ordinary (§5), high-strength (§6, fck ≥ M65) or mass
        # concrete (§9, explicit flag or 80/150 mm aggregate).
        is_hs = inp.target_strength_mpa >= 65.0
        is_mass = bool(inp.mass_concrete) or nmsa in (80, 150)
        trial_clause = "5.8"
        if is_hs and is_mass:
            raise ValueError(
                "IS 10262:2019 offers no combined high-strength mass-concrete "
                "procedure — design high-strength (§6) and mass (§9) separately"
            )
        if is_hs:
            trial_clause = "6.2.9"
            # Tables 6/7/8/10 tabulate 10, 12.5 and 20 mm for the
            # high-strength route (§6.2.2); larger sizes have no §6 data.
            if nmsa not in (10, 12.5, 20):
                raise ValueError(
                    f"High-strength concrete is generally restricted to 20 mm "
                    f"maximum aggregate — Tables 6/7/8/10 cover 10, 12.5 and "
                    f"20 mm (IS 10262:2019 §6.2.2); got {nmsa} mm"
                )
            if grading_zone == "IV":
                raise ValueError(
                    "Grading Zone IV has no Table 10 coarse-aggregate volume — "
                    "high-strength concrete prefers Zone I/II sand "
                    "(IS 10262:2019 §6.1.3, §6.2.7)"
                )
            if grading_zone == "III":
                warnings.append(
                    "Zone III sand is tabulated but a coarser Zone I/II sand "
                    "is preferred for high-strength concrete "
                    "(IS 10262:2019 §6.1.3)"
                )
            if inp.target_strength_mpa >= 80.0 and nmsa == 20:
                warnings.append(
                    "For M80 and above, 10.0–12.5 mm aggregate is preferable "
                    "to 20 mm (IS 10262:2019 §6.2.2)"
                )
            warnings.append(
                "High-strength route: verify crushed-stone aggregate with "
                "impact/crushing value ≤ 22% and combined flakiness + "
                "elongation index ≤ 30% (IS 10262:2019 §6.1.2)"
            )
        elif nmsa == 12.5:
            # Ordinary grades have no 12.5 mm water/aggregate tables —
            # the size is tabulated only in the §6 high-strength tables.
            raise ValueError(
                "12.5 mm aggregate is tabulated only for high-strength "
                "concrete (IS 10262:2019 Tables 6/7/8/10); ordinary grades "
                "use 10/20/40 mm (Table 4)"
            )
        if is_mass:
            trial_clause = "9.11"
            if nmsa not in (40, 80, 150):
                raise ValueError(
                    f"Mass concrete uses 40/80/150 mm nominal aggregate "
                    f"(IS 10262:2019 §9); got {nmsa} mm"
                )
            warnings.append(
                "Mass concrete: combine coarse fractions to Table 14 (80/150 "
                "mm) or IS 383 Table 7 (40 mm) grading (IS 10262:2019 §9.9)"
            )

        # Determine standard deviation: a site record (≥30 results, Cl. 4.2.1)
        # wins when supplied; otherwise the Table 2 assumed value for the
        # declared site control (fair control adds 1 N/mm², Table 2 Note 1).
        grade_name = f"M{int(inp.target_strength_mpa)}"
        if inp.std_deviation is not None and inp.std_deviation > 0:
            std_dev = inp.std_deviation
            warnings.append(
                f"Using site-record standard deviation {std_dev:.2f} N/mm² — "
                f"valid only for ≥30 results of an unchanged mix, re-checked "
                f"monthly (IS 10262:2019 Cl. 4.2.1.1–4.2.1.3)"
            )
        else:
            std_dev = site_assumed_std_dev(grade_name, inp.site_control)

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

        # §9.2: for 80/150 mm aggregate the target is raised 20%/25% for the
        # wet-sieved cube results. Strength reporting only — w/c selection
        # (§9.5) keeps using the un-raised target above. The raised value is
        # kept exact (2 dp), like the Cl. 4.2 target itself.
        ftm_report = ftm
        if is_mass and nmsa in (80, 150):
            _wet_factor = 1.20 if nmsa == 80 else 1.25
            ftm_report = round(ftm * _wet_factor, 2)
            steps.append(
                self._make_step(
                    1.1,
                    "Target strength (wet-sieving allowance)",
                    f"{ftm:.2f} × {_wet_factor:.2f} for {nmsa} mm msa cube tests"
                    f" → {ftm_report:.2f}",
                    {"ftm": ftm, "wet_factor": _wet_factor, "nmsa": nmsa},
                    ftm_report,
                    "MPa",
                    "IS 10262:2019 §9.2",
                )
            )

        # Step 2: Water content (IS 10262:2019 Table 4 + Clause 5.3)
        # Sequence per the standard's Annex A/B worked examples:
        #   1. Base water from Table 4 (angular aggregate, 50 mm slump)
        #   2. Slump adjustment: ±3% per 25 mm from 50 mm (Clause 5.3)
        #   3. Aggregate shape adjustment in kg (Clause 5.3)
        #   4. Admixture water reduction (Clause 5.3 + Annex G)
        # (Annex A: 186 → 191.58 at 75 mm slump → 148 after 23% reduction.)
        # Step 2: Water content — route table by design section.
        # Ordinary: Table 4 + slump rule + aggregate-shape cut (Cl. 5.3).
        # High-strength: Table 7 + slump rule (§6.2.4; no shape cuts are
        #   tabulated for high-strength, so none are applied).
        # Mass: Table 12 + slump rule, with the §9.4 rounded-gravel cut only
        #   (other shapes keep the angular-table value — nothing else is
        #   tabulated).
        agg_shape = inp.coarse_aggregate.shape.value
        water_table_ref = "IS 10262:2019 Table 4 + Clause 5.3"
        if is_hs:
            water_kg = hs_water_content(nmsa, inp.slump_mm)
            base_water = hs_water_content(nmsa, 50.0)
            shape_adj_kg = 0.0
            water_table_ref = "IS 10262:2019 Table 7 + §6.2.4"
        elif is_mass:
            water_kg = mass_water_content(
                nmsa, inp.slump_mm,
                rounded_gravel=(agg_shape == "rounded_gravel"),
            )
            base_water = mass_water_content(nmsa, 50.0)
            shape_adj_kg = 0.0
            water_table_ref = "IS 10262:2019 Table 12 + §9.4"
        else:
            base_water = WATER_CONTENT.get(nmsa, 186)
            water_kg = interpolate_water_content(nmsa, inp.slump_mm, grading_zone)

            # IS 10262:2019 Clause 5.3 — Adjust for aggregate shape
            # Table 4 assumes angular aggregate as base. Adjustments are in kg/m³:
            #   Sub-angular: -10 kg, gravel with some crushed particles: -15 kg,
            #   Rounded gravel: -20 kg
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
        if is_mass and agg_shape == "rounded_gravel":
            _formula_parts.append(
                f"rounded cut −{MASS_ROUNDED_REDUCTION_KG[nmsa]:.0f} kg (§9.4)"
            )
        steps.append(
            self._make_step(
                2,
                "Water content (before admixture reduction)",
                f"From {'Table 7' if is_hs else ('Table 12' if is_mass else 'Table 4')}: "
                + ", ".join(_formula_parts),
                {
                    "nmsa": nmsa,
                    "grading_zone": grading_zone,
                    "slump_mm": inp.slump_mm,
                    "shape": agg_shape if shape_adj_kg != 0 else "none",
                },
                water_before_admixture,
                "kg/m³",
                water_table_ref,
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

        # Step 3: W/C ratio — Figure 1 (ordinary/mass at base target, §9.5)
        # or Table 8 interpolation for high-strength (§6.2.5, HRWRA +
        # silica-fume concretes with ≥53 MPa cement).
        if inp.w_c_ratio is not None:
            wc = inp.w_c_ratio
        elif is_hs:
            wc = hs_wcm_ratio(ftm, nmsa)
            if ftm > 100.0:
                warnings.append(
                    f"Target {ftm:.1f} MPa is beyond the Table 8 range "
                    f"(ends at 100 MPa) — 100 MPa row used; verify by trial "
                    f"(IS 10262:2019 §6.2.5)"
                )
            if cement_type_str in ("OPC_33", "OPC_43", "PPC", "PSC"):
                warnings.append(
                    f"Table 8 assumes ≥53 MPa cement; {cement_type_str} is "
                    f"weaker — reduce the tabulated w/cm suitably and verify "
                    f"by trial (IS 10262:2019 Table 8 note)"
                )
        else:
            wc = self.get_w_c_ratio(ftm, cement_type=cement_type_str)

        # Apply exposure class limits (IS 456:2000)
        durability_governed = False
        if inp.exposure_class:
            limits = get_exposure_limits(inp.exposure_class, inp.concrete_type)
            if wc > limits["max_wc"]:
                warnings.append(
                    f"W/C ratio {wc:.2f} reduced to {limits['max_wc']:.2f} "
                    f"for '{display_name(inp.exposure_class)}' exposure per IS 456:2000"
                )
                wc = limits["max_wc"]
                durability_governed = True

        steps.append(
            self._make_step(
                3,
                "Water-cement ratio"
                + (" (Table 8)" if is_hs and inp.w_c_ratio is None else ""),
                f"From {'Table 8' if is_hs and inp.w_c_ratio is None else 'Figure'} "
                f"for {cement_type_str} cement at ftm",
                {"ftm": ftm, "cement_type": cement_type_str},
                wc,
                "",
                ("IS 10262:2019 Table 8" if is_hs and inp.w_c_ratio is None
                 else "IS 10262:2019 Figure 1"),
            )
        )

        # Step 4: Cement content
        scm_replacement = inp.total_scm_replacement_percent
        cementitious_total = water_kg / wc

        def _scm_pct(*names: str) -> float:
            return sum(
                s.replacement_percent for s in inp.scms
                if (s.type.value if hasattr(s.type, "value") else str(s.type)) in names
            )

        # Preliminary-trial cementitious increase for high mineral dosages:
        # ordinary Cl. 5.4.1/Annex B (any SCM ≥ 20%, e.g. 431 × 1.10 = 474 at
        # 30% fly ash); mass §9.6.1 (fly ash ≥ 20% or GGBS ≥ 30%);
        # high-strength §6.2.5/Annex D-7 (§6.2.5: "In case other cementitious
        # materials such as fly ash, ggbs are also used, the cementitious
        # material content shall be suitably increased" — the D-7 worked
        # example adds 10% at 15% fly ash; silica fume alone is excluded, as
        # §6.2.5 names only fly ash and ggbs).
        _bump_due = False
        _bump_ref = ""
        if not is_hs and not is_mass and scm_replacement >= 20.0:
            _bump_due, _bump_ref = True, "IS 10262:2019 Clause 5.4.1, Annex B"
        elif is_mass and (_scm_pct("fly_ash", "fly_ash_c") >= 20.0
                          or _scm_pct("ggbfs") >= 30.0):
            _bump_due, _bump_ref = True, "IS 10262:2019 §9.6.1"
        elif is_hs and (_scm_pct("fly_ash", "fly_ash_c") > 0.0
                        or _scm_pct("ggbfs") > 0.0):
            _bump_due, _bump_ref = True, "IS 10262:2019 §6.2.5, Annex D-7"
        if _bump_due:
            cementitious_total *= 1.10
            warnings.append(
                f"SCM replacement {scm_replacement:.0f}% warrants a 10% "
                f"cementitious increase for the preliminary trial "
                f"({_bump_ref})"
            )
            steps.append(
                self._make_step(
                    4.05,
                    "Cementitious increase (high mineral dosage)",
                    f"Cementitious × 1.10 per {_bump_ref}",
                    {"cementitious_before": water_kg / wc, "increase_pct": 10.0},
                    cementitious_total,
                    "kg/m³",
                    _bump_ref,
                )
            )

        scm_kg = cementitious_total * (scm_replacement / 100.0)
        cement_kg = cementitious_total - scm_kg

        # Minimum cementitious content per IS 456 Table 5. The standard's
        # own worked examples compare the TOTAL cementitious (OPC + SCM)
        # against the Table 5 minimum — Annex B-7: 474 (= 332 OPC + 142 fly
        # ash) > 320; Annex D-7: 535 > 320 — while the 450 kg/m³ maximum
        # (below) applies to OPC alone (Annex A-1(j): "not including fly
        # ash"). Table 6 of IS 456 adjusts the minimum for NMSA other than
        # 20 mm (10 mm +40; 40 mm −30; the Annex F-7 mass example applies
        # the −30 to 80/150 mm as the largest tabulated correction).
        min_cement = 220.0  # default: plain concrete mild exposure
        if inp.exposure_class:
            limits = get_exposure_limits(inp.exposure_class, inp.concrete_type)
            min_cement = limits["min_cement_kg_m3"]
        _t6_adj = table6_min_cement_adjustment(nmsa)
        _min_t5 = min_cement  # Table 5 base, before the Table 6 adjustment
        min_cement += _t6_adj
        _t6_note = (
            f" (Table 5 {_min_t5:.0f} {'+' if _t6_adj >= 0 else '−'} "
            f"{abs(_t6_adj):.0f} per Table 6, {nmsa:g} mm msa)"
            if _t6_adj else ""
        )

        if cementitious_total < min_cement:
            warnings.append(
                f"Cementitious {cementitious_total:.0f} kg/m³ below minimum "
                f"{min_cement:.0f} kg/m³ for "
                f"'{display_name(inp.exposure_class) if inp.exposure_class else 'mild'}' "
                f"exposure per IS 456:2000 Tables 5–6 — total raised to the "
                f"minimum at the same SCM split"
            )
            cementitious_total = min_cement
            cement_kg = cementitious_total - scm_kg
            steps.append(self._make_step(
                4.06,
                "Minimum cementitious check (IS 456 Tables 5–6)",
                f"Cementitious raised to {min_cement:.0f} kg/m³"
                + _t6_note,
                {"cementitious": cementitious_total, "minimum": min_cement,
                 "table5_base": _min_t5, "table6_adj": _t6_adj},
                cementitious_total, "kg/m³",
                "IS 456:2000 Tables 5–6" + (" / IS 10262:2019 Annex F-7"
                                            if nmsa in (80, 150) else ""),
            ))
        elif _t6_adj:
            # Table 6 shifted the minimum — audit it even when not governing.
            steps.append(self._make_step(
                4.06,
                "Minimum cementitious check (IS 456 Tables 5–6)",
                f"Cementitious {cementitious_total:.0f} vs minimum "
                f"{min_cement:.0f} kg/m³" + _t6_note,
                {"cementitious": cementitious_total, "minimum": min_cement,
                 "table5_base": _min_t5, "table6_adj": _t6_adj},
                cementitious_total, "kg/m³",
                "IS 456:2000 Tables 5–6" + (" / IS 10262:2019 Annex F-7"
                                            if nmsa in (80, 150) else ""),
            ))

        # IS 456:2000 Clause 8.2.4.2 — cement content (not including mineral
        # admixtures such as fly ash, per IS 10262:2019 Annex A-1(j)) should
        # preferably not exceed 450 kg/m³. Deliberately a warning, not a cap:
        # silently cutting cement would raise w/c and break the strength
        # design; the standard's remedy is redesign (SCM replacement, lower
        # heat/shrinkage measures) verified by trials.
        if cement_kg > IS456_MAX_CEMENT_KG_M3:
            warnings.append(
                f"Cement {cement_kg:.0f} kg/m³ exceeds the preferred maximum "
                f"{IS456_MAX_CEMENT_KG_M3:.0f} kg/m³ (cement only, excluding SCM) "
                f"per IS 456:2000 Clause 8.2.4.2 — consider SCM replacement and "
                f"design for drying-shrinkage, early thermal cracking and ASR risk"
            )

        # Cl. 5.1 note: water contributed by liquid admixtures counts in the
        # water-cement ratio at durability upper limits.
        if inp.admixture_water_kg > 0:
            w_eff = (water_kg + inp.admixture_water_kg) / cementitious_total
            steps.append(
                self._make_step(
                    3.1,
                    "Effective water-cement ratio (incl. admixture water)",
                    f"({water_kg:.1f} + {inp.admixture_water_kg:.1f}) / "
                    f"{cementitious_total:.1f}",
                    {"water": water_kg,
                     "admixture_water": inp.admixture_water_kg,
                     "cementitious": cementitious_total},
                    w_eff,
                    "",
                    "IS 10262:2019 Cl. 5.1 note",
                )
            )
            if durability_governed and w_eff > limits["max_wc"] + 1e-9:
                raise ValueError(
                    f"Effective water-cement ratio {w_eff:.2f} (including "
                    f"{inp.admixture_water_kg:.1f} kg/m³ admixture water) exceeds "
                    f"the durability maximum {limits['max_wc']:.2f} per IS 456:2000 "
                    f"Table 5 — reduce mixing water or admixture liquid"
                )

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

            # Table 9 recommended mineral dosages for high-strength mixes —
            # outside the band warns (the band, not a hard limit, is stated).
            if is_hs:
                for _scm in inp.scms:
                    _key = (_scm.type.value if hasattr(_scm.type, "value")
                            else str(_scm.type))
                    _band = HS_MINERAL_DOSAGE.get(_key)
                    if _band is None:
                        continue
                    if not _band[0] <= _scm.replacement_percent <= _band[1]:
                        warnings.append(
                            f"{_key} dosage {_scm.replacement_percent:g}% is outside "
                            f"the Table 9 recommended {_band[0]:g}–{_band[1]:g}% "
                            f"for high-strength mixes (IS 10262:2019 Table 9)"
                        )

        # High-strength w/cm values are attainable in practice only with
        # PCE high-range water reducers (§6.1.4, reduction ≥ 30%).
        if is_hs and wc <= 0.35:
            _adm = inp.admixture
            _hrwra_ok = (_adm is not None
                         and _adm.water_reduction_percent >= 30.0)
            if not _hrwra_ok:
                warnings.append(
                    f"w/cm {wc:.2f} ≤ 0.35 normally requires a PCE "
                    f"superplasticiser (≥30% water reduction, IS 10262:2019 "
                    f"§6.1.4) — confirm workability by trial"
                )

        # IS 10262:2019 Annex A (A-9e) — Admixture mass and volume calculation
        # Admixture dosage is % by mass of cementitious material.
        # Volume = Mass / (Specific gravity × 1000)
        # NOTE: gated on dosage, not on water reduction — retarding,
        # accelerating and air-entraining admixtures carry mass/volume even
        # when their water reduction is 0% (cf. ACI engine, dosage gate).
        has_admixture_mass = (
            inp.admixture is not None and inp.admixture.dosage_percent > 0
        )
        if has_admixture_mass:
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

        # Step 5: Aggregate proportions — Table 5 (ordinary, Cl. 5.5),
        # Table 10 at w/cm 0.30 (high-strength, §6.2.7), Table 13 (mass, §9.7).
        # A Table 5 row override replaces the zone lookup in any route; the
        # w/c adjustment applies either way (base 0.30 for Table 10).
        ca_fraction_override = getattr(inp, "ca_volume_fraction_override", None)
        if ca_fraction_override is not None:
            ca_fraction_base = float(ca_fraction_override)
            base_desc = f"Table 5 fraction (override): {ca_fraction_base:.2f}"
        elif is_hs:
            ca_fraction_base = hs_ca_volume_fraction(nmsa, grading_zone)
            base_desc = f"Table 10 fraction: {ca_fraction_base}"
        elif is_mass:
            ca_fraction_base = mass_ca_volume_fraction(nmsa, grading_zone)
            base_desc = f"Table 13 fraction: {ca_fraction_base}"
        else:
            ca_fraction_base = self.get_coarse_aggregate_volume(
                nmsa, grading_zone=grading_zone
            )
            base_desc = f"Table 5 fraction: {ca_fraction_base}"
        ca_fraction = adjust_ca_volume_for_wcr(
            ca_fraction_base, wc, base_wcr=0.30 if is_hs else 0.50)
        wcr_adj_desc = ""
        if abs(ca_fraction - ca_fraction_base) > 0.001:
            wcr_adj_desc = f" (adjusted from {ca_fraction_base} at W/C={'0.30' if is_hs else '0.50'}, Δ={ca_fraction - ca_fraction_base:+.2f})"

        # Placing-method reduction of the CA fraction: ordinary §5.5.2
        # (up to 10% — the worked examples use the full 10%); high-strength
        # §6.2.7 (up to 5%); mass sizes carry no tabulated pump reduction.
        # An explicit pump_ca_reduction_percent (0–10) overrides the route
        # maximum; anything above it is rejected (§5.5.2 "up to").
        if inp.placing_method == "pump":
            _route_max = 5.0 if is_hs else (None if is_mass else 10.0)
            _route_ref = (
                "§6.2.7" if is_hs else ("§9 (no tabulated value)" if is_mass else "§5.5.2")
            )
            _explicit = getattr(inp, "pump_ca_reduction_percent", None)
            if _explicit is not None:
                if _route_max is not None and _explicit > _route_max:
                    raise ValueError(
                        f"Pump CA reduction {_explicit:g}% exceeds the "
                        f"{_route_max:g}% maximum for this route "
                        f"(IS 10262:2019 {_route_ref})"
                    )
                ca_fraction = round(ca_fraction * (1.0 - _explicit / 100.0), 3)
                wcr_adj_desc += f" (pumped placing: −{_explicit:g}% → {ca_fraction:.3f}, {_route_ref})"
                warnings.append(
                    f"Coarse-aggregate fraction reduced {_explicit:g}% for pumped "
                    f"placing (IS 10262:2019 {_route_ref}) — confirm slump, "
                    f"w/c and strength on the trial batches"
                )
            elif is_hs:
                ca_fraction = round(ca_fraction * 0.95, 3)
                wcr_adj_desc += f" (pumped placing: −5% → {ca_fraction:.3f}, §6.2.7)"
                warnings.append(
                    "Coarse-aggregate fraction reduced 5% for pumped placing "
                    "(IS 10262:2019 §6.2.7) — confirm slump, w/cm and strength "
                    "on the trial batches"
                )
            elif is_mass:
                warnings.append(
                    "Pumped placing has no tabulated CA reduction for "
                    "mass-concrete sizes — placeability is governed by the "
                    "§9.10 mortar check below; verify by trial (IS 10262:2019 §9)"
                )
            else:
                ca_fraction = round(ca_fraction * 0.9, 3)
                wcr_adj_desc += f" (pumped placing: −10% → {ca_fraction:.3f}, §5.5.2)"
                warnings.append(
                    "Coarse-aggregate fraction reduced 10% for pumped placing "
                    "(IS 10262:2019 §5.5.2) — confirm slump, w/c and strength on "
                    "the trial batches"
                )

        # IS method: CA fraction is of TOTAL AGGREGATE volume
        # IS 10262:2019 Annex A (A-9) — Mix calculations per unit volume
        # Air table follows the route: Table 3 / Table 6 (HS) / Table 11 (mass).
        _air_class = "high_strength" if is_hs else ("mass" if is_mass else "ordinary")
        air_percent = self.get_air_content(nmsa, concrete_class=_air_class)
        vol_cement = absolute_volume(cement_kg, inp.cement.specific_gravity)
        vol_scm = (
            absolute_volume(scm_kg, inp.scms[0].specific_gravity) if inp.scms else 0.0
        )
        vol_water = absolute_volume(water_kg, SG_WATER)
        vol_air = air_percent / 100.0

        # IS 10262:2019 Annex A (A-9e) — Include admixture volume in absolute
        # volume calculation whenever a dose is batched (see note above).
        vol_admixture = 0.0
        if has_admixture_mass:
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

        # §9.10: large-aggregate mixes need a minimum mortar content for
        # placing and workability. Mortar = cement + pozzolana + water +
        # admixture + air + fine aggregate (absolute volumes).
        if is_mass and nmsa in (80, 150):
            _mortar = (vol_cement + vol_scm + vol_water + vol_air
                       + vol_admixture + vol_fa)
            _shape_key = ("crushed" if agg_shape in ("angular", "crushed_fragments")
                          else "rounded")
            _m_lo, _m_hi = MASS_MORTAR_VOLUME[(nmsa, _shape_key)]
            if not _m_lo <= _mortar <= _m_hi:
                warnings.append(
                    f"Mortar content {_mortar:.3f} m³/m³ is outside the "
                    f"suggested {_m_lo:.2f}–{_m_hi:.2f} for {nmsa} mm "
                    f"{_shape_key} aggregate — adjust fine aggregate and "
                    f"cementitious contents for placeability (IS 10262:2019 §9.10)"
                )
            steps.append(
                self._make_step(
                    6.1,
                    "Mortar content check",
                    f"Mortar {_mortar:.3f} vs suggested {_m_lo:.2f}–{_m_hi:.2f}",
                    {"mortar": _mortar, "suggested": (_m_lo, _m_hi)},
                    _mortar,
                    "m³/m³",
                    "IS 10262:2019 §9.10, Table 15",
                )
            )

        # Moisture correction. Shared engine uses the ACI §5.3.9.1 identity
        # w_batch = w_SSD·(1+MC)/(1+A); the IS 10262 annexes apply free
        # moisture = MC − A to the SSD mass instead (A-11/B-11). The two
        # formulations differ by ≤ 0.5 kg/m³ per constituent on the annex
        # values (B-11: 747.5 vs 748 kg; added water 110.6 vs 110 kg) — a
        # documented deviation well inside IS 2 rounding.
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

        # Step 8: Trial Mixes Protocol (Cl. 5.8 ordinary / §6.2.9 HS / §9.11 mass)
        _trial_ref = f"IS 10262:2019 Clause {trial_clause}"
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
                _trial_ref,
            )
        )

        # Trial batch recommendation
        _report_ref = {"5.8": "5.8.1", "6.2.9": "6.2.10", "9.11": "9.12"}[trial_clause]
        warnings.append(
            f"{_trial_ref}: Mandatory 4-trial batch protocol required — "
            "Trial 1 (workability & segregation/bleeding check), Trial 2 (water/admixture adjustment at constant W/C), "
            f"Trials 3 & 4 (same water with W/C ±10%: {wc_trial3:.2f} & {wc_trial4:.2f} to establish strength vs. W/C curve), "
            f"followed by field trials and Clause {_report_ref} reporting."
        )

        # Self-compacting concrete (§7–§8): fresh-property class checks plus
        # the §8.3 constituent-envelope checks. NOTE — this is an SCC
        # compliance overlay on an ordinarily-proportioned mix, NOT the full
        # Annex E proportioning procedure (powder content, water/powder
        # ratio and paste-volume design). Active when a target class or any
        # fresh measurement is supplied. Failures warn (trials iterate);
        # only a provably oversized powder content blocks.
        _scc_measured = {
            "slump_flow_mm": inp.scc_slump_flow_mm,
            "lbox_ratio": inp.scc_lbox_ratio,
            "segregation_pct": inp.scc_segregation_pct,
            "vfunnel_s": inp.scc_vfunnel_s,
        }
        if inp.scc_class is not None or any(v is not None for v in _scc_measured.values()):
            _SF_RANGES = {"SF1": (550.0, 650.0), "SF2": (660.0, 750.0),
                          "SF3": (760.0, 850.0)}
            _scc_notes: dict = {}
            if inp.scc_slump_flow_mm is not None:
                _sf = inp.scc_slump_flow_mm
                _met = [c for c, (lo, hi) in _SF_RANGES.items() if lo <= _sf <= hi]
                _scc_notes["slump_flow_class_met"] = _met
                if inp.scc_class is not None:
                    _lo, _hi = _SF_RANGES[inp.scc_class]
                    if not _lo <= _sf <= _hi:
                        warnings.append(
                            f"Slump-flow {_sf:.0f} mm is outside the target "
                            f"{inp.scc_class} range ({_lo:.0f}–{_hi:.0f} mm, "
                            f"IS 10262:2019 §7.2.1) — adjust water/powder and "
                            f"superplasticiser, then re-test"
                        )
                elif not _met:
                    warnings.append(
                        f"Slump-flow {_sf:.0f} mm meets no SF class (SF1 550–650, "
                        f"SF2 660–750, SF3 760–850; §7.2.1)"
                    )
            if inp.scc_lbox_ratio is not None:
                _scc_notes["lbox_ratio"] = inp.scc_lbox_ratio
                if inp.scc_lbox_ratio < 0.8:
                    warnings.append(
                        f"L-box ratio {inp.scc_lbox_ratio:.2f} is below the 0.80 "
                        f"passing-ability minimum (IS 10262:2019 §7.2.2)"
                    )
            if inp.scc_segregation_pct is not None:
                _sr = inp.scc_segregation_pct
                _scc_notes["segregation_class"] = (
                    "SR2" if _sr < 15.0 else ("SR1" if _sr <= 20.0 else "none"))
                if _sr > 20.0:
                    warnings.append(
                        f"Segregation ratio {_sr:.1f}% exceeds the SR1 15–20% "
                        f"band (IS 10262:2019 §7.2.3) — consider a viscosity- "
                        f"modifying admixture (§8.3)"
                    )
            if inp.scc_vfunnel_s is not None:
                _vf = inp.scc_vfunnel_s
                _scc_notes["viscosity_class"] = (
                    "V1" if _vf <= 8.0 else ("V2" if _vf <= 25.0 else "none"))
                if _vf > 25.0:
                    warnings.append(
                        f"V-funnel time {_vf:.1f} s exceeds the V2 8–25 s band "
                        f"(IS 10262:2019 §7.2.4)"
                    )
            # §8.3 constituent envelope on the design itself.
            _fa_mass_frac = (fa_kg / (fa_kg + ca_kg)
                             if (fa_kg + ca_kg) > 0 else 0.0)
            _scc_notes["fine_agg_mass_fraction"] = round(_fa_mass_frac, 3)
            if not 0.48 <= _fa_mass_frac <= 0.60:
                warnings.append(
                    f"Fine aggregate is {_fa_mass_frac * 100:.1f}% of total "
                    f"aggregate by mass — SCC typically needs 48–60% "
                    f"(IS 10262:2019 §8.3(a))"
                )
            if not 150.0 <= water_kg <= 210.0:
                warnings.append(
                    f"Mixing water {water_kg:.0f} kg/m³ is outside the typical "
                    f"SCC 150–210 kg/m³ band (IS 10262:2019 §8.3(b))"
                )
            _powder = cement_kg + scm_kg
            if _powder > 600.0:
                raise ValueError(
                    f"Powder content {_powder:.0f} kg/m³ (cement + mineral "
                    f"admixtures, before aggregate fines) already exceeds the "
                    f"SCC 400–600 kg/m³ fines band (IS 10262:2019 §8.3(a))"
                )
            if _powder < 400.0:
                warnings.append(
                    f"Cement + mineral admixtures are {_powder:.0f} kg/m³; with "
                    f"aggregate fines the <0.125 mm powder should total "
                    f"400–600 kg/m³ (IS 10262:2019 §8.3(a))"
                )
            # §8.3(c): SCC water reduction comes from a PCE high-range water
            # reducer at ">30 percent" — gate on 30, not the generic
            # superplasticizer floor.
            _hrwra = (inp.admixture is not None
                      and inp.admixture.water_reduction_percent >= 30.0)
            if not _hrwra:
                warnings.append(
                    "SCC normally requires a PCE high-range water reducer "
                    "(>30% reduction), sometimes with a viscosity-modifying "
                    "admixture (IS 10262:2019 §8.3(c))"
                )
            steps.append(
                self._make_step(
                    8.1,
                    "SCC fresh-property classes",
                    f"Target {inp.scc_class or '—'}; measured: "
                    + ", ".join(f"{k}={v}" for k, v in _scc_measured.items()
                                if v is not None),
                    {"target_class": inp.scc_class, **_scc_measured, **_scc_notes,
                     "fine_agg_mass_fraction": round(_fa_mass_frac, 3),
                     "water_kg": water_kg, "powder_kg": _powder},
                    1.0,
                    "check",
                    "IS 10262:2019 §7.2 / §8.3",
                )
            )

        # Calculate admixture mass for result
        admixture_mass_result = 0.0
        admixture_type_result = None
        admixture_dosage_result = None
        water_reduction_result = None
        if has_admixture_mass:
            admixture_mass_result = cementitious_total * (
                inp.admixture.dosage_percent / 100.0
            )
            admixture_type_result = inp.admixture.type_string
            admixture_dosage_result = inp.admixture.dosage_percent
            water_reduction_result = inp.admixture.water_reduction_percent

        # Reporting convention of the standard's annexes (A-10 … F-11):
        # constituent quantities are reported to the nearest whole kg
        # (cement 412, water 148, FA 648, CA 1234). Half-up rounding so
        # e.g. 147.5 kg follows the annexes rather than banker's rounding.
        return MixDesignResult(
            code_used="IS 10262:2019",
            target_mean_strength_mpa=ftm_report,
            w_c_ratio=round(wc, 2),
            water_kg=_round_whole_kg(water_kg),
            cement_kg=_round_whole_kg(cement_kg),
            scm_kg=_round_whole_kg(scm_kg),
            fine_aggregate_kg=_round_whole_kg(fa_kg),
            coarse_aggregate_kg=_round_whole_kg(ca_kg),
            air_volume_percent=round(air_percent, 1),
            volume_m3=inp.volume_m3,
            steps=tuple(steps),
            warnings=tuple(warnings),
            adjusted_water_kg=_round_whole_kg(field_water),
            field_fine_aggregate_kg=_round_whole_kg(field_fa),
            field_coarse_aggregate_kg=_round_whole_kg(field_ca),
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
        _is_hs = inp.target_strength_mpa >= 65.0
        _is_mass = bool(getattr(inp, "mass_concrete", False)) or nmsa in (80, 150)
        if _is_hs:
            ca_frac_base = hs_ca_volume_fraction(nmsa, grading_zone)
        elif _is_mass:
            ca_frac_base = mass_ca_volume_fraction(nmsa, grading_zone)
        else:
            ca_frac_base = get_ca_volume_fraction(nmsa, grading_zone)
        # Preliminary-trial bump mirrors design(): ordinary ≥20% any SCM,
        # mass fly ash ≥20% or GGBS ≥30%, high-strength any fly ash/GGBS
        # (§6.2.5 / Annex D-7).
        _scm_types = [
            (s.type.value if hasattr(s.type, "value") else str(s.type))
            for s in inp.scms
        ]
        _fa_pct = sum(p for t, p in zip(_scm_types, [s.replacement_percent for s in inp.scms])
                      if t in ("fly_ash", "fly_ash_c"))
        _ggbs_pct = sum(p for t, p in zip(_scm_types, [s.replacement_percent for s in inp.scms])
                        if t == "ggbfs")
        if _is_hs:
            bump = _fa_pct > 0.0 or _ggbs_pct > 0.0
        elif _is_mass:
            bump = _fa_pct >= 20.0 or _ggbs_pct >= 30.0
        else:
            bump = scm_pct >= 20.0
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
        # No input record: fall back to the ordinary preliminary-trial rule.
        bump = scm_pct >= 20.0
        _is_hs = False
        _is_mass = False

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
    if bump:
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

    ca_frac3 = adjust_ca_volume_for_wcr(
        ca_frac_base, wc3, base_wcr=0.30 if _is_hs else 0.50)
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
    if bump:
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

    ca_frac4 = adjust_ca_volume_for_wcr(
        ca_frac_base, wc4, base_wcr=0.30 if _is_hs else 0.50)
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



def _round_whole_kg(value: float) -> float:
    """Round to the nearest whole kg, half away from zero.

    The IS 10262:2019 annexes report all constituent quantities to the
    nearest whole kg (A-10: cement 412, water 148, FA 648, CA 1234; the
    147.52 → 148 water in A-6 shows half-up, not banker's, rounding).
    """
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)
