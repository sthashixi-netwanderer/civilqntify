"""ACI PRC-211.1-22 concrete mix design implementation.

Implements the absolute volume method for proportioning normal-weight concrete
per ACI PRC-211.1-22 "Selecting Proportions for Normal-Density and
High-Density Concrete" (guide). Overdesign criteria per ACI 318.
"""

from __future__ import annotations

import math

from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.tables.aci_tables import (
    C_CLASS_LIMITS,
    F_CLASS_AIR_CONTENT,
    F_CLASS_LIMITS,
    S_CLASS_CEMENT_GUIDANCE,
    S_CLASS_LIMITS,
    W_CLASS_LIMITS,
    cementitious_for_target_paste_volume,
    check_f3_scm_limits,
    check_nmsa_limits,
    get_air_content,
    get_f_class_limits,
    get_no_data_overdesign,
    interpolate_ca_volume,
    interpolate_w_c_ratio,
    interpolate_water_content,
    modification_factor_k,
    paste_volume_percent,
    water_adjustment_531,
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
        num_tests: int | None = None,
    ) -> float:
        """ACI 211.1 / ACI 318 target mean strength.

        When has_production_data=True (sample standard deviation available):
            Table 4.7.4.4 (ACI 301-20 Table 4.2.3.3(a)1):
              f'c ≤ 5000 psi:  f'cr = max(f'c + 1.34·k·s,
                                           f'c + 2.33·k·s − 500 psi)
              f'c >  5000 psi: f'cr = max(f'c + 1.34·k·s,
                                           0.90·f'c + 2.33·k·s)
            where k is the Table 4.7.4.3 modification factor when s is
            calculated from 15 to 29 tests (1.00 at ≥ 30 tests).
            (500 psi = 3.45 MPa; 5000 psi = 34.5 MPa.)

        When has_production_data=False (no prior data):
            Uses ACI 318 Table 26.4.3.1(b) / Table 4.7.4.1 overdesign rules.

        App policy: the reported f'cr is rounded UP to the next whole MPa
        (e.g. 24.13 -> 25) — e.g.
        30.87 → 30.9. ACI 318 works f'cr at psi granularity (≈0.007 MPa)
        with no rounding rule; whole-MPa rounding adds up to ~145 psi of
        conservatism, which is accepted as a uniform app policy across all
        three codes (IS and DOE targets are likewise ceiled to whole MPa).
        Rounding up (never down) stays conservative. The 1e-9 epsilon
        guards against float noise just above an exact integer.

        Args:
            target_strength_mpa: Specified compressive strength f'c (MPa)
            std_dev: Standard deviation in MPa (default 4.0 ≈ 600 psi)
            has_production_data: Whether a sample standard deviation is
                established (≥15 tests); False uses the no-data table
            num_tests: Number of strength tests behind ``std_dev`` —
                15–29 applies the Table 4.7.4.3 k-modification; ≥30 (or
                None) uses s unmodified
        """
        if not has_production_data:
            return math.ceil(get_no_data_overdesign(target_strength_mpa) - 1e-9)

        s = std_dev if std_dev is not None else 4.0  # default 4 MPa ≈ 600 psi
        k = modification_factor_k(num_tests) if num_tests is not None else 1.0
        ks = k * s

        # Table 4.7.4.4 — both branches of the table, by f'c vs 5000 psi.
        if target_strength_mpa <= 34.5:
            fcr_statistical = target_strength_mpa + 1.34 * ks
            fcr_limited = target_strength_mpa + 2.33 * ks - 3.45
        else:
            fcr_statistical = target_strength_mpa + 1.34 * ks
            fcr_limited = 0.90 * target_strength_mpa + 2.33 * ks

        fcr = max(fcr_statistical, fcr_limited)

        # Must be at least f'c + 2.4 MPa (≈350 psi) per ACI 318
        fcr = max(fcr, target_strength_mpa + 2.4)

        return math.ceil(fcr - 1e-9)

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
        if nmsa in (80, 150):
            raise ValueError(
                f"NMSA {nmsa} mm is an IS 10262 mass-concreting size (§9) — "
                f"ACI PRC-211.1-22 Tables 5.3.3/5.3.6 cover at most 40 mm (1-1/2 in.)"
            )

        # Determine exposure level for air content
        exposure_map = {
            "mild": "mild",
            "moderate": "moderate",
            "severe": "severe",
            "very_severe": "severe",
            "extreme": "severe",
        }
        exposure = exposure_map.get(inp.exposure_class or "moderate", "moderate")

        # ACI 318 26.4.2.1(a)(5) / PRC-211.1-22 §4.3.2 — NMSA must fit the
        # structure: ≤ 1/5 of form width, ≤ 1/3 of slab depth, ≤ 3/4 of clear
        # bar spacing. Dimensions are optional; only supplied ones are checked.
        nmsa_violations = check_nmsa_limits(
            float(nmsa),
            form_width_mm=inp.form_width_mm,
            slab_depth_mm=inp.slab_depth_mm,
            bar_spacing_mm=inp.bar_spacing_mm,
        )
        if nmsa_violations:
            raise ValueError(
                "NMSA violates structural-dimension limits "
                "(ACI 318 26.4.2.1(a)(5)): " + "; ".join(nmsa_violations)
            )

        # ACI PRC-211.1-22 Appendix B — high-density concrete (B.3/B.4). A
        # batch mass ≥ 180 lb/ft³ (≈2885 kg/m³) or aggregate SG above the
        # normal-weight range (≈3.0) leaves the Tables 5.3.3/5.3.6 scope:
        # proportions below are a starting point for trial verification,
        # not a finished Appendix B design (segregation, placing and
        # radiation/chemical requirements apply).
        _fa_sg = getattr(inp.fine_aggregate, "specific_gravity", 2.65)
        _ca_sg = getattr(inp.coarse_aggregate, "specific_gravity", 2.65)
        if _fa_sg > 3.0 or _ca_sg > 3.0:
            warnings.append(
                f"Aggregate SG (fine {_fa_sg:g}, coarse {_ca_sg:g}) exceeds "
                f"the normal-weight range — high-density scope: verify by "
                f"trial per ACI PRC-211.1-22 Appendix B (B.3/B.4)"
            )

        # ACI 301 Table 4.2.2.6(c) / ACI 318 Chapter 19 — freezing-and-thawing
        # exposure (PRC-211.1-22 §4.7.3, Table 4.7.3b). Fail fast on
        # non-compliant combinations, mirroring the IS 456 minimum-grade gate:
        # a frost-exposed mix cannot satisfy durability below these limits.
        f_class = getattr(inp, "freezing_exposure_class", "F0") or "F0"
        # Table 4.7.3b's last row gives plain concrete its own F3 limits
        # (w/cm ≤ 0.45, f'c ≥ 4500 psi) — milder than the reinforced F3 row.
        f_limits = get_f_class_limits(f_class, inp.concrete_type)
        if f_class in ("F1", "F2", "F3") and not inp.air_entrained:
            raise ValueError(
                f"Freezing exposure class '{f_class}' requires air-entrained "
                f"concrete per ACI 301 Table 4.2.2.6(c). Enable air entrainment."
            )
        f_min_fc = f_limits["min_fc_mpa"]
        if f_min_fc is not None and inp.target_strength_mpa < f_min_fc:
            raise ValueError(
                f"Specified strength {inp.target_strength_mpa:g} MPa is below "
                f"the minimum {f_min_fc:.1f} MPa for freezing exposure class "
                f"'{f_class}'{' (plain concrete row)' if f_class == 'F3' and inp.concrete_type == 'plain' else ''} "
                f"per ACI 301 Table 4.2.2.6(c) "
                f"(PRC-211.1-22 Table 4.7.3b). Use a higher strength."
            )
        if f_class == "F3" and inp.scms:
            f3_violations = check_f3_scm_limits(
                [
                    s.type.value if hasattr(s.type, "value") else str(s.type)
                    for s in inp.scms
                ],
                [s.replacement_percent for s in inp.scms],
            )
            if f3_violations:
                raise ValueError(
                    "SCM replacement violates Exposure Class F3 limits "
                    "(ACI 301 Table 4.2.1.1(b)): " + "; ".join(f3_violations)
                )

        # ACI 301 Table 4.2.2.6(d) — water-contact exposure (PRC-211.1-22
        # Table 4.7.3c). W2 (water-barrier elements) imposes a w/c cap and a
        # minimum strength; W1 adds 4.2.2.6(a) low-permeability practice
        # (curing/testing — guidance, not proportioning numbers).
        w_class = getattr(inp, "water_exposure_class", "W0") or "W0"
        w_limits = W_CLASS_LIMITS[w_class]
        w_min_fc = w_limits["min_fc_mpa"]
        if w_min_fc is not None and inp.target_strength_mpa < w_min_fc:
            raise ValueError(
                f"Specified strength {inp.target_strength_mpa:g} MPa is below "
                f"the minimum {w_min_fc:.1f} MPa for water exposure class "
                f"'{w_class}' per ACI 301 Table 4.2.2.6(d) "
                f"(PRC-211.1-22 Table 4.7.3c). Use a higher strength."
            )
        if w_class in ("W1", "W2"):
            warnings.append(
                f"Water exposure class '{w_class}' invokes ACI 301 4.2.2.6(a) "
                f"low-permeability provisions — verify curing, cover and "
                f"permeability testing beyond this proportioning"
            )

        # ACI 301 Table 4.2.2.6(e) — corrosion protection (PRC-211.1-22 Table
        # 4.7.3d, non-prestressed scope). C2 imposes a w/c cap and a minimum
        # strength; chloride caps are guidance — chloride content cannot be
        # derived from proportions and must be verified by constituent testing.
        c_class = getattr(inp, "corrosion_exposure_class", "C0") or "C0"
        c_limits = C_CLASS_LIMITS[c_class]
        c_min_fc = c_limits["min_fc_mpa"]
        if c_min_fc is not None and inp.target_strength_mpa < c_min_fc:
            raise ValueError(
                f"Specified strength {inp.target_strength_mpa:g} MPa is below "
                f"the minimum {c_min_fc:.1f} MPa for corrosion exposure class "
                f"'{c_class}' per ACI 301 Table 4.2.2.6(e) "
                f"(PRC-211.1-22 Table 4.7.3d). Use a higher strength."
            )
        # ACI 301 Table 4.2.2.6(b) — sulfate exposure (PRC-211.1-22 Table
        # 4.7.3a). Fail fast below the class minimum strength, like the
        # F/W/C gates above (S1: 4000 psi; S2: 4500 psi; S3 Option 2:
        # 5000 psi). Cement-type and calcium-chloride rules are guidance —
        # cement chemistry cannot be derived from proportions.
        s_class = getattr(inp, "sulfate_exposure_class", "S0") or "S0"
        s_limits = S_CLASS_LIMITS[s_class]
        s_min_fc = s_limits["min_fc_mpa"]
        if s_min_fc is not None and inp.target_strength_mpa < s_min_fc:
            raise ValueError(
                f"Specified strength {inp.target_strength_mpa:g} MPa is below "
                f"the minimum {s_min_fc:.1f} MPa for sulfate exposure class "
                f"'{s_class}' per ACI 301 Table 4.2.2.6(b) "
                f"(PRC-211.1-22 Table 4.7.3a). Use a higher strength."
            )
        if s_class in S_CLASS_CEMENT_GUIDANCE:
            warnings.append(
                f"Sulfate exposure class '{s_class}': "
                f"{S_CLASS_CEMENT_GUIDANCE[s_class]}"
            )

        c_cl = c_limits["max_chloride_pct"]
        if c_class in ("C1", "C2"):
            if inp.prestressed:
                warnings.append(
                    f"Corrosion exposure class '{c_class}' (PRESTRESSED): "
                    f"water-soluble chloride ≤ 0.06% by mass of cementitious "
                    f"material per ACI 301 Table 4.2.2.6(e) — verify by testing "
                    f"mix water, aggregates and admixtures"
                )
            else:
                warnings.append(
                    f"Corrosion exposure class '{c_class}' (non-prestressed): "
                    f"water-soluble chloride ≤ {c_cl:.2f}% by mass of cementitious "
                    f"material per ACI 301 Table 4.2.2.6(e) — verify by testing "
                    f"mix water, aggregates and admixtures"
                )

        # Step 1: Target mean strength
        has_data = getattr(inp, "has_production_data", True)
        _n_tests = getattr(inp, "num_strength_tests", None)
        _s_site = getattr(inp, "std_deviation", None)
        fcr = self.calculate_target_mean_strength(
            inp.target_strength_mpa,
            std_dev=_s_site if (_s_site is not None and _s_site > 0) else None,
            has_production_data=has_data,
            num_tests=_n_tests if has_data else None,
        )
        if not has_data:
            formula = "Table 26.4.3.1(b) / Table 4.7.4.1 (no data)"
        elif _n_tests is not None and _n_tests < 30:
            _second = ("f'c + 2.33·k·s − 3.45" if inp.target_strength_mpa <= 34.5
                       else "0.90·f'c + 2.33·k·s")
            formula = (
                f"max(f'c + 1.34·k·s, {_second}), "
                f"k = Table 4.7.4.3 (n = {_n_tests})"
            )
        elif inp.target_strength_mpa > 34.5:
            formula = "max(f'c + 1.34s, 0.90·f'c + 2.33s) — Table 4.7.4.4, f'c > 5000 psi"
        else:
            formula = "max(f'c + 1.34s, f'c + 2.33s - 3.45)"
        steps.append(self._make_step(
            1, "Target mean strength (f'cr)",
            formula,
            {"f'c": inp.target_strength_mpa,
             "s": _s_site if (_s_site is not None and _s_site > 0) else 4.0,
             "k_tests": _n_tests, "has_data": has_data},
            fcr, "MPa",
            "ACI 318 / PRC-211.1-22 Tables 4.7.4.1–4.7.4.4"
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
        # Table 5.3.3.1 refinements auto-applied from explicit inputs only:
        # SCM table rates (fly ash −3%/10%, slag −5%/10%), concrete
        # temperature off the 22.5 °C baseline, manufactured sand +5%.
        # Slump/air rows are intentionally NOT auto-applied (Table 5.3.3
        # interpolation already encodes them; Example 1 pins unadjusted
        # water), and rounded aggregate is left at the table value for the
        # same reason — see water_adjustment_531() for trial refinement.
        _fa_pct = sum(
            s.replacement_percent for s in inp.scms
            if (s.type.value if hasattr(s.type, "value") else str(s.type))
            in ("fly_ash", "fly_ash_c")
        )
        _slag_pct = sum(
            s.replacement_percent for s in inp.scms
            if (s.type.value if hasattr(s.type, "value") else str(s.type)) == "ggbfs"
        )
        if any(
            (s.type.value if hasattr(s.type, "value") else str(s.type))
            in ("silica_fume", "metakaolin")
            for s in inp.scms
        ):
            warnings.append(
                "Silica fume / calcined-clay SCMs usually increase mixing-water "
                "demand vs portland-only concrete (PRC-211.1-22 §4.7.6) — no "
                "table rate exists, so none was applied; verify by trial batch"
            )
        _adj_pct, _adj_applied = water_adjustment_531(
            temp_c=inp.concrete_temp_c,
            fly_ash_pct=_fa_pct,
            slag_pct=_slag_pct,
            manufactured_sand=inp.manufactured_sand,
        )
        # The admixture water reduction joins the SAME percentage ledger:
        # every Table 5.3.3.1 row and the WRA/HRWRA reduction are
        # percentages of the Table 5.3.3 base water, applied additively —
        # exactly as Example 2 (§9.3.3): 280 − 14 (WRA −5%) − 17 (fly ash
        # −6%) − 22 (rounded −8%) = 227 lb/yd³. Compounding them
        # sequentially would double-count the base.
        _admixture_reduction_pct = 0.0
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            _admixture_reduction_pct = inp.admixture.water_reduction_percent
            _adj_pct -= _admixture_reduction_pct
            _adj_applied = _adj_applied + [
                f"admixture −{_admixture_reduction_pct:.1f}% "
                f"({inp.admixture.type_string}, §6.3)"
            ]
        # The 22.5 °C baseline contributes exactly 0.0%; drop it from the
        # record so legacy designs show no adjustment step at all.
        water_kg = base_water_kg * (1.0 + _adj_pct / 100.0)
        steps.append(self._make_step(
            3, "Water content",
            "From Table 5.3.3 by NMSA and slump",
            {"nmsa": nmsa, "slump": inp.slump_mm, "air_entrained": inp.air_entrained},
            base_water_kg, "kg/m³",
            "ACI PRC-211.1-22 Table 5.3.3"
        ))
        if _adj_applied and abs(_adj_pct) > 1e-9:
            steps.append(self._make_step(
                3.1, "Water content (Table 5.3.3.1 + admixture adjustments)",
                "Base water adjusted: " + "; ".join(_adj_applied),
                {"base_water": base_water_kg, "adjustment_pct": _adj_pct,
                 "admixture_reduction_pct": _admixture_reduction_pct},
                water_kg, "kg/m³",
                "ACI PRC-211.1-22 Table 5.3.3.1 / §6.3"
            ))

        # Table 5.3.3.1 also lists −8% for rounded aggregate. The standard
        # is inconsistent in its own examples — Example 1 (§9.2.3) keeps the
        # tabulated water for a rounded coarse aggregate while Example 2
        # (§9.3.3) applies the −8% — so the engine keeps the tabulated
        # value (Example-1 parity) and surfaces the clause for the trial
        # batch instead of silently cutting water.
        if (inp.coarse_aggregate.shape.value
                if hasattr(inp.coarse_aggregate.shape, "value")
                else str(inp.coarse_aggregate.shape)) == "rounded_gravel":
            warnings.append(
                "Rounded coarse aggregate may reduce mixing water by 8% "
                "(Table 5.3.3.1; Example 2 applies it, Example 1 does not) — "
                "kept at the Table 5.3.3 estimate here; refine at the trial "
                "batch via water_adjustment_531(rounded_aggregate=True)"
            )

        # PRC-211.1-22 §4.7.6: conventional water-reducers should cut ≥5%,
        # HRWRAs ≥12%. Below that the admixture is likely under-dosed or the
        # wrong type for the claimed reduction — warn, don't second-guess.
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
            _adm_type = (
                inp.admixture.type.value
                if hasattr(inp.admixture.type, "value")
                else str(inp.admixture.type)
            )
            _red = inp.admixture.water_reduction_percent
            if _adm_type in ("water_reducer", "water_reducer_retarder",
                             "water_reducer_accelerator") and _red < 5.0:
                warnings.append(
                    f"Conventional water-reducer claims only {_red:.1f}% reduction; "
                    f"PRC-211.1-22 §4.7.6 expects at least 5% — verify dosage"
                )
            elif _adm_type in ("superplasticizer", "hrwra", "hrwra_retarder") \
                    and _red < 12.0:
                warnings.append(
                    f"High-range water-reducer claims only {_red:.1f}% reduction; "
                    f"PRC-211.1-22 §4.7.6 expects at least 12% — verify dosage"
                )

        # Step 4: Air content
        # An explicit F1–F3 selection drives the ACI 301 Table 4.2.2.6(c)1
        # values directly; F0 (default) keeps the legacy exposure-mapped path
        # so existing designs are byte-identical.
        if f_class in ("F1", "F2", "F3"):
            air_percent = F_CLASS_AIR_CONTENT.get(
                nmsa, F_CLASS_AIR_CONTENT[20]
            )[f_class]
            air_clause = (
                "ACI 301 Table 4.2.2.6(c)1 / ACI 318 Chapter 19 "
                f"(Exposure Class {f_class})"
            )
            air_desc = (
                f"Table 4.7.3.1 for Exposure Class {f_class} "
                f"(NMSA {nmsa} mm, air-entrained)"
            )
            if inp.target_strength_mpa >= 34.5:
                warnings.append(
                    "At f'c ≥ 5000 psi (34.5 MPa) a 1.0-point reduction of the "
                    "Table 4.7.3.1 air content is acceptable (table footnote); "
                    "full air content retained — verify by trial batch"
                )
        else:
            air_percent = self.get_air_content(
                nmsa, exposure=exposure, air_entrained=inp.air_entrained
            )
            air_clause = "ACI PRC-211.1-22 Table 5.3.3"
            air_desc = "From Table 5.3.3 by NMSA and exposure (ACI 318 F-class)"
        steps.append(self._make_step(
            4, "Air content",
            air_desc,
            {"nmsa": nmsa, "exposure": exposure, "air_entrained": inp.air_entrained,
             "freezing_class": f_class},
            air_percent, "%",
            air_clause
        ))

        # Step 5: W/C ratio
        if inp.w_c_ratio is not None:
            wc = inp.w_c_ratio
        else:
            wc = self.get_w_c_ratio(fcr, air_entrained=inp.air_entrained)
        # Table 5.3.4 Note 1: air-entrained concrete above 6000 psi reads
        # w/cm < 0.33 (stored as the 0.33 boundary) and "may require the
        # addition of chemical admixtures, SCMs and higher cementitious
        # content" — flag it instead of silently designing below the table.
        if inp.air_entrained and inp.w_c_ratio is None and fcr > 41.4:
            warnings.append(
                f"Required average strength {fcr:.1f} MPa exceeds the 6000 psi "
                f"(41.4 MPa) air-entrained row of Table 5.3.4 (w/cm < 0.33) — "
                f"verify with chemical admixtures/SCMs and trial batches "
                f"(ACI PRC-211.1-22 Table 5.3.4 Note 1)"
            )

        # Sulfate cap joins lowest-governs (§4.7.1) via S_CLASS_LIMITS
        # (values identical to ACI_MAX_WC_FOR_EXPOSURE for S1–S3).
        sulfate_class = s_class
        s_max_wc = s_limits["max_wc"]
        if s_max_wc is not None and wc > s_max_wc:
            warnings.append(
                f"W/C ratio {wc:.2f} reduced to {s_max_wc:.2f} "
                f"for sulfate exposure class '{sulfate_class}' per ACI 301 "
                f"Table 4.2.2.6(b)"
            )
            wc = s_max_wc

        # Lowest-w/cm-governs (PRC-211.1-22 §4.7.1): the freezing-exposure
        # cap competes with strength and sulfate caps; the minimum wins.
        f_max_wc = f_limits["max_wc"]
        if f_max_wc is not None and wc > f_max_wc:
            warnings.append(
                f"W/C ratio {wc:.2f} reduced to {f_max_wc:.2f} "
                f"for freezing exposure class '{f_class}' per ACI 301 Table 4.2.2.6(c)"
            )
            wc = f_max_wc

        # Same lowest-governs rule for water-contact (W2: 0.50) and corrosion
        # (C2: 0.40) caps.
        w_max_wc = w_limits["max_wc"]
        if w_max_wc is not None and wc > w_max_wc:
            warnings.append(
                f"W/C ratio {wc:.2f} reduced to {w_max_wc:.2f} "
                f"for water exposure class '{w_class}' per ACI 301 Table 4.2.2.6(d)"
            )
            wc = w_max_wc
        c_max_wc = c_limits["max_wc"]
        if c_max_wc is not None and wc > c_max_wc:
            warnings.append(
                f"W/C ratio {wc:.2f} reduced to {c_max_wc:.2f} "
                f"for corrosion exposure class '{c_class}' per ACI 301 Table 4.2.2.6(e)"
            )
            wc = c_max_wc

        steps.append(self._make_step(
            5, "Water-cement ratio",
            "From Table 5.3.4 by required average strength (interpolated)",
            {"f'cr": fcr, "air_entrained": inp.air_entrained, "sulfate_class": sulfate_class,
             "freezing_class": f_class, "water_class": w_class, "corrosion_class": c_class},
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

        # Step 8.1: paste volume — cementitious + water absolute volumes as
        # a percentage of the concrete volume (§9.5 Step 1). Reported for
        # every design; a target PV (Example 4 / AASHTO PP 84, e.g. 25%)
        # triggers the redesign below.
        _scm_sg_eff = (
            sum(s.specific_gravity * s.replacement_percent for s in inp.scms)
            / sum(s.replacement_percent for s in inp.scms)
            if inp.scms else 2.20
        )
        _pv = paste_volume_percent(
            cement_kg, scm_kg, water_kg,
            inp.cement.specific_gravity, _scm_sg_eff,
        )
        steps.append(self._make_step(
            8.1, "Paste volume",
            "(V_cement + V_SCM + V_water) / 1 m³ × 100",
            {"cement": cement_kg, "scm": scm_kg, "water": water_kg,
             "cement_sg": inp.cement.specific_gravity, "scm_sg": _scm_sg_eff},
            _pv, "%",
            "ACI PRC-211.1-22 §9.5 (Example 4)"
        ))

        # Step 8.2: Example 4 Steps 2–4 — solve the cementitious contents
        # that hit a target paste volume at the design w/cm and SCM
        # fraction, then shift the freed (or claimed) volume to the
        # aggregates pro-rata by their absolute volumes, exactly as the
        # example rebalances a 1.45 ft³ paste reduction 40/60 fine/coarse.
        _target_pv = getattr(inp, "target_paste_volume_pct", None)
        if _target_pv is not None:
            cement_kg, scm_kg, water_kg = cementitious_for_target_paste_volume(
                _target_pv, wc, scm_replacement / 100.0,
                inp.cement.specific_gravity, _scm_sg_eff,
            )
            cementitious_total = cement_kg + scm_kg
            vol_cement = absolute_volume(cement_kg, inp.cement.specific_gravity)
            vol_scm = absolute_volume(scm_kg, _scm_sg_eff)
            vol_water = absolute_volume(water_kg, SG_WATER)
            # Admixture dosage rides on the new cementitious total.
            if inp.admixture and inp.admixture.dosage_percent > 0:
                admixture_mass_kg = cementitious_total * (
                    inp.admixture.dosage_percent / 100.0)
                vol_admixture = absolute_volume(
                    admixture_mass_kg,
                    getattr(inp.admixture, "specific_gravity", 1.15))
            vol_agg_new = max(
                0.0, 1.0 - (vol_cement + vol_scm + vol_water + vol_air
                            + vol_admixture))
            _agg_ratio = vol_ca / (vol_ca + vol_fa) if (vol_ca + vol_fa) > 0 else 0.65
            vol_ca = vol_agg_new * _agg_ratio
            vol_fa = vol_agg_new - vol_ca
            ca_kg = vol_ca * inp.coarse_aggregate.specific_gravity * 1000.0
            fa_kg = vol_fa * inp.fine_aggregate.specific_gravity * 1000.0
            _pv = paste_volume_percent(
                cement_kg, scm_kg, water_kg,
                inp.cement.specific_gravity, _scm_sg_eff)
            steps.append(self._make_step(
                8.2, "Target-paste redesign",
                f"Cementitious solved for PV = {_target_pv:g}% at w/cm {wc:.2f} "
                f"and {scm_replacement:g}% SCM; aggregates rebalanced by volume",
                {"target_pv_pct": _target_pv, "wcm": wc,
                 "scm_fraction": scm_replacement / 100.0,
                 "cement": cement_kg, "scm": scm_kg, "water": water_kg,
                 "coarse_agg": ca_kg, "fine_agg": fa_kg,
                 "achieved_pv_pct": _pv},
                _pv, "%",
                "ACI PRC-211.1-22 §9.5 (Example 4, Steps 2–4)"
            ))
            warnings.append(
                f"Target paste volume {_target_pv:g}% reached at w/cm {wc:.2f} — "
                f"the reduced water content normally requires a high-range "
                f"water-reducing admixture (HRWRA), and mixing water below about "
                f"200 lb/yd³ (≈119 kg/m³) can impair finishability "
                f"(PRC-211.1-22 Example 4)"
            )

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

        # Step 10: Theoretical density and yield basis (ASTM C138 / §4.7.9).
        # Always reported: the design batch mass per 1 m³ IS the theoretical
        # fresh density. Relative yield needs a MEASURED fresh density
        # (trial input below); working tolerance Ry 0.98–1.02, with batch
        # tolerances ±1% cementitious / ±2% aggregate / ±1.5% air.
        _batch_mass = (water_kg + cementitious_total + ca_kg + fa_kg
                       + admixture_mass_kg)
        steps.append(self._make_step(
            10, "Theoretical density and yield basis",
            "Theoretical density = batch mass / 1 m³; Ry = 1.0/Ry needs measured density",
            {"batch_mass_kg": _batch_mass, "design_volume_m3": 1.0},
            _batch_mass, "kg/m³",
            "ACI PRC-211.1-22 §4.7.9 / ASTM C138"
        ))

        # Appendix B — high-density concrete. Above ~180 lb/ft³ (2885 kg/m³,
        # the bottom of Table B.2) the design is in high-density territory:
        # proportion the fresh density ABOVE the required oven-dry density by
        # the anticipated drying loss (B.3, typically 8–10 lb/ft³), allow for
        # air lost to vibration (B.4), use aggregates per ASTM C637/C638 and
        # follow ACI 304.3R for handling. Surfaced here; the absolute-volume
        # arithmetic itself is unchanged (B.6.1 worked example).
        if _batch_mass >= 2885.0:
            warnings.append(
                f"Theoretical density {_batch_mass:.0f} kg/m³ is in the "
                f"high-density range (≥180 lb/ft³, Appendix B Table B.2) — "
                f"proportion above the required oven-dry density by the "
                f"anticipated drying loss (B.3, typically 8–10 lb/ft³), "
                f"allow for vibration loss of entrained air (B.4), verify "
                f"aggregates to ASTM C637/C638 and consult ACI 304.3R for "
                f"handling (PRC-211.1-22 Appendix B)"
            )

        # Step 10.1–10.3: Post-trial adjustments (§5.3.10) from measured
        # trial observations. Each rule fires only on its own input; with no
        # trial inputs the design stands as the first-trial proportions.
        _trial_ry = None
        _re_water = water_kg  # re-estimated water per unit volume (§5.3.10.1)
        if inp.trial_density_kg_m3 is not None:
            _trial_yield = _batch_mass / inp.trial_density_kg_m3
            _trial_ry = _trial_yield / 1.0
            # Adjustment 1 base: re-estimated water per unit volume.
            _re_water = water_kg / _trial_yield
            _ry_note = (f"yield {_trial_yield:.3f} m³, Ry {_trial_ry:.3f}"
                        + (" — OUTSIDE 0.98–1.02 tolerance" if not 0.98 <= _trial_ry <= 1.02 else ""))
            steps.append(self._make_step(
                10.1, "Trial yield check",
                f"Yield = batch mass / measured density ({_ry_note})",
                {"batch_mass_kg": _batch_mass,
                 "measured_density": inp.trial_density_kg_m3,
                 "trial_yield_m3": _trial_yield, "relative_yield": _trial_ry},
                _trial_yield, "m³",
                "ACI PRC-211.1-22 §5.3.10 / ASTM C138"
            ))
            if not 0.98 <= _trial_ry <= 1.02:
                warnings.append(
                    f"Trial relative yield {_trial_ry:.3f} is outside the 0.98–1.02 "
                    f"working tolerance (§4.7.9.3) — check batch weights, specific "
                    f"gravities, moisture and air before adjusting proportions"
                )
            if inp.trial_slump_mm is not None:
                # ±10 lb/yd³ (5.93 kg/m³) per inch (25.4 mm) of slump correction.
                _slump_corr = 5.93 * (inp.slump_mm - inp.trial_slump_mm) / 25.4
                _re_water_slump = _re_water + _slump_corr
                steps.append(self._make_step(
                    10.2, "Trial water re-estimate (yield + slump)",
                    f"Re-water = {water_kg:.1f}/{_trial_yield:.3f} "
                    f"{_slump_corr:+.1f} (slump {inp.trial_slump_mm:.0f}→{inp.slump_mm:.0f} mm)",
                    {"trial_water": water_kg, "trial_yield_m3": _trial_yield,
                     "slump_correction": _slump_corr},
                    _re_water_slump, "kg/m³",
                    "ACI PRC-211.1-22 §5.3.10.1"
                ))
        if inp.trial_air_pct is not None and inp.air_entrained:
            # ∓5 lb/yd³ (2.97 kg/m³) per 1% air change; re-estimate
            # air-entrainer dosage for the target air content.
            _air_corr = 2.97 * (air_percent - inp.trial_air_pct)
            steps.append(self._make_step(
                10.3, "Trial air re-estimate",
                f"Water {_air_corr:+.1f} kg/m³ per 1% air "
                f"({inp.trial_air_pct:.1f}→{air_percent:.1f}%); re-estimate "
                f"air-entrainer dosage for target air",
                {"trial_air": inp.trial_air_pct, "target_air": air_percent,
                 "water_correction": _air_corr},
                _re_water + _air_corr, "kg/m³",
                "ACI PRC-211.1-22 §5.3.10.2"
            ))
        if inp.trial_strength_mpa is not None:
            # Adjustment 3: cement efficiency = strength per kg of cement per
            # m³; delta cement closes the gap to the required average f'cr,
            # water follows at constant w/cm, sand offsets the volume change.
            _eff = inp.trial_strength_mpa / cementitious_total if cementitious_total > 0 else 0.0
            if _eff > 0:
                _d_cem = (fcr - inp.trial_strength_mpa) / _eff
                _d_water = _d_cem * wc
                steps.append(self._make_step(
                    10.4, "Trial strength re-estimate (cement efficiency)",
                    f"Efficiency {_eff:.3f} MPa per kg/m³; "
                    f"cement {_d_cem:+.1f}, water {_d_water:+.1f} at constant w/c, "
                    f"offset sand for yield",
                    {"trial_strength": inp.trial_strength_mpa, "fcr": fcr,
                     "efficiency": _eff, "delta_cement": _d_cem,
                     "delta_water": _d_water},
                    _d_cem, "kg/m³",
                    "ACI PRC-211.1-22 §5.3.10.3"
                ))
                if abs(_d_cem) > 0.5:
                    warnings.append(
                        f"Trial strength suggests {'adding' if _d_cem > 0 else 'removing'} "
                        f"{abs(_d_cem):.0f} kg/m³ cementitious "
                        f"(+{abs(_d_water):.1f} kg/m³ water, sand rebalanced) — "
                        f"verify with a second trial batch (§5.3.10.3)"
                    )

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
