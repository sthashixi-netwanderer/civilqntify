"""DOE (Teychenné et al. 1997) concrete mix design implementation.

Source: "Design of normal concrete mixes" (BR 331), 2nd edition, 1997.
Building Research Establishment (BRE), UK.

This implements the 5-stage DOE mix design method:
  Stage 1: Target mean strength → free-water/cement ratio
  Stage 2: Workability → free-water content
  Stage 3: Cement content (W / W/C)
  Stage 4: Total aggregate content (density − C − W)
  Stage 5: Fine and coarse aggregate apportionment (Figure 6)
"""

from __future__ import annotations

import math
from typing import Any

from concrete_mix.codes.base import MixDesignCode
from concrete_mix.codes.tables.doe_tables import (
    GGBS_WATER_REDUCTION_KG,
    PFA_EFFICIENCY_K,
    figure6_panel_label,
    get_free_water_content,
    get_fine_aggregate_proportion,
    get_k_value,
    get_reference_strength,
    get_standard_deviation,
    get_wet_density,
    pfa_water_reduction,
    resolve_workability_class,
    validate_doe_inputs,
    wc_ratio_from_strength,
)
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult


class DOEMixDesign(MixDesignCode):
    """DOE (Department of the Environment) mix design method.

    Reference: Teychenné et al., "Design of normal concrete mixes", BR 331,
    2nd edition, 1997 (BRE Press).
    """

    # ------------------------------------------------------------------
    # Abstract property implementations
    # ------------------------------------------------------------------

    @property
    def code_name(self) -> str:
        return "doe"

    @property
    def code_full_name(self) -> str:
        return "DOE (BR 331:1997)"

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def calculate_target_mean_strength(
        self,
        target_strength_mpa: float,
        std_dev: float | None = None,
        **kwargs: Any,
    ) -> float:
        """Stage 1: f_m = f_c + M  (Calculation C2).

        The margin M = k × s.  If fewer than 20 results are available, use
        Line A of Figure 3; otherwise Line B.  For structural DOE mixes
        (fc ≥ 25 MPa) the app assumes construction for structural elements
        (BRE 331:1997 §4.4, Figure 3) and uses s = 8 MPa for n < 20
        (Line A) and s = 4 MPa for n ≥ 20 (Line B).  When
        ``n`` / ``num_test_cubes`` is supplied, that structural rule is
        applied (n < 20 → 8 MPa, n ≥ 20 → 4 MPa).
        """
        if std_dev is None:
            n = kwargs.get("n", kwargs.get("num_test_cubes", kwargs.get("number_of_results")))
            if n is None:
                n = kwargs.get("n_test_cubes")
            has_data = kwargs.get("has_production_data", True)
            # ``get_standard_deviation`` interprets n→structural: n<20→8 MPa, n≥20→4 MPa
            std_dev = get_standard_deviation(target_strength_mpa, has_data, n=n)

        defective_pct = kwargs.get("defective_percent", 5.0)
        k = get_k_value(defective_pct)
        margin = k * std_dev
        # C2 rounding: target mean rounded up to the whole N/mm² (§7.1:
        # 45.68 → 46; §7.4: 61.65 → 62).
        return float(math.ceil(target_strength_mpa + margin))

    def get_water_content(
        self, nmsa: int, slump_mm: float, **kwargs: Any,
    ) -> float:
        """Stage 2: free-water content from Table 3.

        When coarse and fine aggregates are of different types, use the
        weighted formula: W = 2/3 Wf + 1/3 Wc.
        """
        agg_type = kwargs.get("coarse_agg_type", "uncrushed")
        vebe_s: float | None = kwargs.get("vebe_s")
        return get_free_water_content(nmsa, agg_type, slump_mm, vebe_s)

    def get_w_c_ratio(
        self, target_mean_strength_mpa: float, **kwargs: Any,
    ) -> float:
        """Stage 1 (continued): W/C ratio from Figure 4.

        Uses the reference strength at W/C=0.5 (Table 2) and interpolates
        the Figure 4 curves.
        """
        cement_class = kwargs.get("cement_class", "42.5")
        agg_type = kwargs.get("coarse_agg_type", "uncrushed")
        age_days = kwargs.get("age_days", 28)
        ref = get_reference_strength(cement_class, agg_type, age_days)
        return wc_ratio_from_strength(target_mean_strength_mpa, ref)

    def get_coarse_aggregate_volume(self, nmsa: int, **kwargs: Any) -> float:
        """Not directly used in DOE — Figure 6 gives fine aggregate %."""
        return 0.0

    def get_air_content(self, nmsa: int, **kwargs: Any) -> float:
        """DOE ignores normally entrapped air in non-air-entrained mixes."""
        return 0.0

    # ------------------------------------------------------------------
    # Full design pipeline
    # ------------------------------------------------------------------

    def design(self, inp: MixDesignInput) -> MixDesignResult:
        """Run the 5-stage DOE mix design.

        The input object carries generic fields.  DOE-specific semantics:
          - `inp.code` == "doe"
          - `inp.cement.type` maps to a cement strength class ("42.5" or "52.5")
          - `inp.coarse_aggregate.shape` maps to "crushed" or "uncrushed"
          - `inp.fine_aggregate.grading_zone` stores % passing 600 µm
          - `inp.slump_mm` or `inp.target_strength_mpa` (Vebe via kwargs)
          - `inp.characteristic_strength_mpa` = f_c
          - `inp.target_strength_mpa` may serve as std_dev if has_production_data is False
        """
        steps: list[CalculationStep] = []
        warnings: list[str] = []

        fc = inp.characteristic_strength
        has_data = inp.has_production_data
        # BRE 331 Figure 3 covers the full strength axis, so any grade is
        # designable: the deviation follows the piecewise lines —
        #   Line A (n < 20 results):  s = 0.4×fc for fc ≤ 20, else s = 8 MPa
        #   Line B (n ≥ 20 results):  s = 0.2×fc for fc ≤ 20, else s = 4 MPa
        # (get_standard_deviation implements exactly this; §4.4).
        # n = number of test cubes that will be cast for testing the strength.
        num_cubes: int | None = getattr(inp, "num_test_cubes", None)
        # Record the Figure 3 basis as an informational warning.
        n_str = f"{num_cubes}" if num_cubes is not None else "—"
        if num_cubes is not None and num_cubes >= 20:
            s_desc = "Line B (n≥20): s = 0.2×fc (fc≤20), else 4 MPa"
        elif num_cubes is not None:
            s_desc = "Line A (n<20): s = 0.4×fc (fc≤20), else 8 MPa"
        else:
            s_desc = "Line A (n<20) / Line B (n≥20)"
        structural_note = (
            "DOE design per BRE 331:1997 Figure 3 (§4.4) — any characteristic "
            f"strength grade (fc = {fc:g} MPa). "
            f"Standard deviation s follows {s_desc} for n test cubes "
            f"(n={n_str}). Ensure trial batch verification per BRE 331 §6."
        )
        warnings.append(structural_note)

        # --- Map aggregate type to "crushed" / "uncrushed" ---
        agg_type = self._map_agg_type(inp)

        # --- Map cement class ---
        cement_class = self._map_cement_class(inp)
        cement_type = inp.cement.type.value
        if "53" not in cement_type and "52" not in cement_type and (
            "33" in cement_type or "32" in cement_type
        ):
            # BRE 331:1997 Table 2 only covers strength classes 42.5 and 52.5
            warnings.append(
                "BRE 331:1997 Table 2 has no curve for class 32.5/33 cements — "
                "the class 42.5 curve is used (conservative); verify by trial mix"
            )

        # --- Extract DOE-specific input: % passing 600 µm ---
        pct_600 = self._get_pct_passing_600um(inp)

        # --- Workability basis: Vebe wins over slump when provided ---
        # (BRE 331 Table 3 accepts either; both map to the same four classes).
        # When both are given they must agree on the class — if they map to
        # different Figure 6 columns, Vebe governs and a warning is raised
        # (project policy; the standard gives no precedence rule).
        # Representative slumps reproduce the class for Figure 6, which is
        # class-based internally.
        vebe_s = getattr(inp, "vebe_s", None)
        wc_class, workability_conflict = resolve_workability_class(
            inp.slump_mm, vebe_s
        )
        if workability_conflict:
            warnings.append(workability_conflict)
        if vebe_s is not None:
            workability_desc = f"Vebe {vebe_s:.1f} s (class {wc_class})"
        else:
            workability_desc = f"slump {inp.slump_mm:.0f} mm (class {wc_class})"
        rep_slump = {0: 5.0, 1: 20.0, 2: 45.0, 3: 120.0}[wc_class]

        # --- Validate DOE inputs against Table 3 (class-equivalent slump
        # when Vebe is the workability basis) ---
        validation_warnings = validate_doe_inputs(
            nmsa=inp.nmsa,
            slump_mm=rep_slump if vebe_s is not None else inp.slump_mm,
            agg_type=agg_type,
        )
        warnings.extend(validation_warnings)

        # --- Air entrainment (§8): 0 = non-air-entrained (legacy path) ---
        air_pct = float(getattr(inp, "air_pct", 0.0) or 0.0)
        if air_pct > 0 and not 3.0 <= air_pct <= 7.0:
            warnings.append(
                f"Entrained air {air_pct:.1f}% is outside the 3–7% range over "
                f"which the §8 allowances were validated (BRE 331:1997 §8) — "
                f"expect larger trial adjustments"
            )

        # --- SCM mode (Part three): pfa §9 / ggbs §10, single addition only.
        # Previously SCMs were silently ignored by the DOE engine; now they
        # select a standard branch — or fail loudly where BRE gives none.
        scm_mode: str | None = None
        p_pct = 0.0
        if inp.scms:
            if len(inp.scms) > 1:
                raise ValueError(
                    "DOE (BR 331:1997) supports a single pfa or ggbs addition; "
                    f"got {len(inp.scms)} SCMs. Use IS 10262 or ACI 211.1 for blends."
                )
            _scm = inp.scms[0]
            _t = _scm.type.value if hasattr(_scm.type, "value") else str(_scm.type)
            p_pct = float(inp.total_scm_replacement_percent)
            if not 0.0 < p_pct < 100.0:
                raise ValueError(
                    f"SCM replacement {p_pct:g}% is not a usable proportion"
                )
            if _t in ("fly_ash", "fly_ash_c"):
                scm_mode = "pfa"
                if not 15.0 <= p_pct <= 40.0:
                    warnings.append(
                        f"pfa proportion {p_pct:g}% is outside the typical 15–40% "
                        f"range (BRE 331:1997 §9.2.3); sulfate soils need 25–40% "
                        f"(Digest 363), ASR mitigation ≥ 30% (Digest 330)"
                    )
            elif _t == "ggbfs":
                scm_mode = "ggbs"
                if p_pct > 40.0:
                    raise ValueError(
                        f"ggbs proportion {p_pct:g}% exceeds 40%: BRE 331:1997 "
                        f"§10.3 gives no standard procedure above 40% (strength "
                        f"needs +10 to +50 kg/m³ cementitious) — consult the "
                        f"cement/ggbs supplier for the mix design"
                    )
            else:
                raise ValueError(
                    f"DOE (BR 331:1997) has no procedure for '{_t}' SCM — Part "
                    f"three covers pfa (§9) and ggbs (§10) only"
                )
        if scm_mode is not None and air_pct > 0:
            warnings.append(
                f"Combined air-entrained {scm_mode} design is outside the "
                f"scope of BRE 331 Part three (§8 with §9/§10) — both "
                f"modifications were applied independently; verify by trial mix"
            )

        # ==================================================================
        # STAGE 1 — Target mean strength and W/C ratio
        # ==================================================================

        # Step 1.1: Standard deviation (Figure 3 piecewise lines, any grade).
        # Line A (n<20): s = 0.4×fc for fc≤20 else 8 MPa.
        # Line B (n≥20): s = 0.2×fc for fc≤20 else 4 MPa (BRE 331 §4.4).
        user_std_dev = getattr(inp, 'std_deviation', None)
        if user_std_dev is not None and user_std_dev > 0:
            std_dev = user_std_dev
            steps.append(self._make_step(
                number=1,
                description="Standard deviation (s) — user provided",
                formula=f"s = {std_dev:.1f} MPa (user record, BRE 331 §4.4, n={num_cubes if num_cubes is not None else '—'})",
                inputs={"fc": fc, "std_deviation": std_dev, "n_test_cubes": num_cubes},
                result=std_dev,
                unit="MPa",
                clause_ref="User input (BRE 331:1997 §4.4)",
            ))
        else:
            std_dev = get_standard_deviation(fc, has_data, n=num_cubes)
            # Describe the n-aware Figure 3 line actually applied, equation
            # and all, so the step is a complete audit record.
            if num_cubes is not None:
                if num_cubes < 20:
                    _line = "Line A"
                    _n_desc = f"n={num_cubes} (<20 results)"
                    _eq = (f"s = 0.4 × {fc:g} = {std_dev:.2f}"
                           if fc <= 20 else "s = 8 MPa (plateau, fc > 20)")
                else:
                    _line = "Line B"
                    _n_desc = f"n={num_cubes} (≥20 results)"
                    _eq = (f"s = 0.2 × {fc:g} = {std_dev:.2f}"
                           if fc <= 20 else "s = 4 MPa (plateau, fc > 20)")
                steps.append(self._make_step(
                    number=1,
                    description=f"Standard deviation (s) — Figure 3 {_line}, {_n_desc}",
                    formula=f"Figure 3 {_line} (fc={fc:g} MPa, {_n_desc}): {_eq} [N/mm²]",
                    inputs={"fc": fc, "n_test_cubes": num_cubes, "has_production_data": has_data,
                            "figure3_line": _line},
                    result=std_dev,
                    unit="MPa",
                    clause_ref=f"Figure 3 {_line}, BRE 331 §4.4",
                ))
            else:
                steps.append(self._make_step(
                    number=1,
                    description="Standard deviation (s)",
                    formula="Figure 3: s = f(characteristic strength, production data)",
                    inputs={"fc": fc, "has_production_data": has_data},
                    result=std_dev,
                    unit="MPa",
                    clause_ref="Figure 3",
                ))

        # Step 1.2: Margin (Calculation C1)
        # Check if user specified margin directly (BRE 331:1997 §4.4)
        user_margin = getattr(inp, 'margin_mpa', None)
        if user_margin is not None and user_margin > 0:
            margin = user_margin
            steps.append(self._make_step(
                number=2,
                description="Margin (M) — User specified",
                formula=f"M = {margin:.1f} MPa (user-specified)",
                inputs={"margin": margin},
                result=margin,
                unit="MPa",
                clause_ref="User input (BRE 331:1997 §4.4)",
            ))
        else:
            defective_pct = inp.defective_percent
            k = get_k_value(defective_pct)
            margin = k * std_dev
            steps.append(self._make_step(
                number=2,
                description="Margin (M = k × s)",
                formula=f"M = {k:.2f} × {std_dev:.1f}",
                inputs={"k": k, "s": std_dev},
                result=margin,
                unit="MPa",
                clause_ref="Calculation C1",
            ))

        # Step 1.3: Target mean strength (Calculation C2). C2 is "expressed
        # to two significant figures" — the standard's own examples round
        # UP to the whole N/mm² (45.68 → 46, §7.1; 61.65 → 62, §7.4), so
        # the ceiling is applied here and the whole number feeds Figure 4.
        target_mean = float(math.ceil(fc + margin))
        steps.append(self._make_step(
            number=3,
            description="Target mean strength (f_m = f_c + M)",
            formula=f"f_m = {fc:g} + {margin:.2f} = {fc + margin:.2f}"
                    f" → {target_mean:g} N/mm² (rounded up, C2)",
            inputs={"fc": fc, "M": margin, "fm_exact": fc + margin},
            result=target_mean,
            unit="MPa",
            clause_ref="Calculation C2 (two significant figures)",
        ))

        # §8.1: air-entrained mixes aim higher to compensate ~5.5% strength
        # loss per 1% entrained air. The modified target feeds Figure 4.
        target_fig4 = target_mean
        if air_pct > 0:
            target_fig4 = target_mean / (1.0 - 0.055 * air_pct)
            steps.append(self._make_step(
                number=3.1,
                description="Modified target mean strength (air)",
                formula=f"({fc:.1f} + {margin:.1f}) / (1 − 0.055 × {air_pct:.1f})",
                inputs={"fc": fc, "M": margin, "air_pct": air_pct},
                result=target_fig4,
                unit="MPa",
                clause_ref="BRE 331:1997 §8.1",
            ))

        # Step 1.4: Reference strength at W/C=0.5 (Table 2; Table 10 for pfa
        # lists identical 28-day values, so the same lookup serves §9.3.1).
        age_days = inp.age_days
        ref_strength = get_reference_strength(cement_class, agg_type, age_days)
        steps.append(self._make_step(
            number=4,
            description="Reference strength at W/C=0.5 (Table 2"
                        + (" / Table 10 for pfa" if scm_mode == "pfa" else "") + ")",
            formula=f"Table 2: class={cement_class}, agg={agg_type}, age={age_days}d",
            inputs={"cement_class": cement_class, "agg_type": agg_type, "age_days": age_days},
            result=ref_strength,
            unit="MPa",
            clause_ref="Table 2" + (" + Table 10 (§9.3.1)" if scm_mode == "pfa" else ""),
        ))

        # Step 1.5: Free-W/C ratio from Figure 4. For pfa this ratio is
        # W/(C + 0.30F) (cementing efficiency k = 0.30, §9.2.2); the
        # durability cap then compares against W/(C+F) at Stage 3 (Item 3.8),
        # not against this ratio — so it is deferred for pfa.
        # Figure 4 is read to 2 dp and the worked examples chain that read
        # straight into C3 (§7.1: 160 ÷ 0.47 = 340 → 340; §7.4:
        # 215 ÷ 0.37 = 581 → 580), so the ratio is rounded here.
        wc_calc = round(wc_ratio_from_strength(target_fig4, ref_strength), 2)

        # Step 1.6: Apply maximum W/C override (durability)
        max_wc = inp.w_c_ratio  # repurposed as durability limit
        wc_final = wc_calc
        if max_wc is not None and scm_mode != "pfa" and max_wc < wc_calc:
            wc_final = max_wc
            warnings.append(
                f"Durability override: W/C reduced from {wc_calc:.2f} to {wc_final:.2f} "
                f"(max allowed = {max_wc:.2f})"
            )

        steps.append(self._make_step(
            number=5,
            description="Free-W/C ratio from Figure 4"
                        + (" (W/(C+0.30F) for pfa)" if scm_mode == "pfa" else ""),
            formula=f"Figure 4: f(target={target_fig4:.1f}, ref={ref_strength:.0f})",
            inputs={"target_mean": target_fig4, "ref_strength": ref_strength, "max_wc": max_wc},
            result=wc_final,
            unit="",
            clause_ref="Figure 4, Item 1.7/1.8" + (" + §9.3.1" if scm_mode == "pfa" else ""),
        ))

        # ==================================================================
        # STAGE 2 — Free-water content (Table 3)
        # ==================================================================

        nmsa = inp.nmsa
        coarse_agg_type = self._map_agg_type(inp)
        fine_agg_type = self._map_fine_agg_type(inp)

        # When coarse and fine aggregates are of different types, use the
        # weighted formula: W = 2/3 Wf + 1/3 Wc (BRE 331:1997 Note to Table 3).
        # §8.2: air-entrained mixes take water from one workability class
        # lower than specified (entrained air itself adds workability).
        water_cls = max(0, wc_class - 1) if air_pct > 0 else wc_class
        # Part three water cuts, applied to the Table 3 base below: pfa
        # Table 9 Part B by proportion and class (§9.3.2); ggbs rough-guide
        # −5 kg/m³ (§10.2.1).
        scm_water_cut = 0.0
        scm_water_note = ""
        scm_clause = ""
        if scm_mode == "pfa":
            scm_water_cut = pfa_water_reduction(p_pct, water_cls)
            scm_water_note = (f" − Table 9B pfa cut {scm_water_cut:.0f} "
                              f"(p={p_pct:g}%, class {water_cls})")
            scm_clause = " + Table 9 (§9.3.2)"
        elif scm_mode == "ggbs":
            scm_water_cut = GGBS_WATER_REDUCTION_KG
            scm_water_note = (f" − ggbs rough-guide cut {scm_water_cut:.0f} "
                              f"(§10.2.1)")
            scm_clause = " + §10.2.1"
        water_raw = 0.0
        if coarse_agg_type != fine_agg_type:
            w_fine = get_free_water_content(nmsa, fine_agg_type, workability_class=water_cls)
            w_coarse = get_free_water_content(nmsa, coarse_agg_type, workability_class=water_cls)
            water_raw = (2.0 / 3.0) * w_fine + (1.0 / 3.0) * w_coarse
            water = _round_to_5(water_raw) - scm_water_cut
            steps.append(self._make_step(
                number=6,
                description="Free-water content (Table 3, mixed types)",
                formula=f"W = 2/3×{w_fine:.0f} + 1/3×{w_coarse:.0f} = {water_raw:.1f}"
                        f" → {_round_to_5(water_raw):.0f} (nearest 5 kg, Item 2.3)"
                        f"{scm_water_note} = {water:.0f}",
                inputs={"nmsa": nmsa, "fine_agg_type": fine_agg_type, "coarse_agg_type": coarse_agg_type,
                        "workability": workability_desc, "water_class": water_cls,
                        "w_fine": w_fine, "w_coarse": w_coarse,
                        "scm_water_cut": scm_water_cut},
                result=water,
                unit="kg/m³",
                clause_ref="Table 3 Note, Item 2.3" + (" + §8.2 (one class lower)" if air_pct > 0 else "") + scm_clause,
            ))
        else:
            water_raw = float(get_free_water_content(nmsa, coarse_agg_type, workability_class=water_cls))
            water = _round_to_5(water_raw) - scm_water_cut
            steps.append(self._make_step(
                number=6,
                description="Free-water content (Table 3)",
                formula=f"Table 3: nmsa={nmsa}, agg={coarse_agg_type}, {workability_desc}"
                        + (f" → class {water_cls}" if air_pct > 0 else "")
                        + scm_water_note + f" = {water:.0f}",
                inputs={"nmsa": nmsa, "agg_type": coarse_agg_type, "workability": workability_desc,
                        "water_class": water_cls, "scm_water_cut": scm_water_cut},
                result=water,
                unit="kg/m³",
                clause_ref="Table 3, Item 2.3" + (" + §8.2 (one class lower)" if air_pct > 0 else "") + scm_clause,
            ))

        # Admixture water reduction (BRE 331:1997 §5.3 — only when a
        # water-reducing admixture is explicitly selected; "None" keeps the
        # Table 3 water unchanged).
        admixture_mass_kg = 0.0
        admixture_type_result = None
        admixture_dosage_result = None
        _admix_active = (
            inp.admixture is not None
            and (inp.admixture.type_string or "").strip().lower() not in ("", "none")
        )
        if _admix_active and inp.admixture.water_reduction_percent > 0:
            reduction_pct = inp.admixture.water_reduction_percent
            water_before = water
            water = water * (1.0 - reduction_pct / 100.0)
            steps.append(self._make_step(
                number=6.1,
                description="Free-water content (with admixture reduction)",
                formula=f"Base water {water_before:.1f} kg/m³ reduced by {reduction_pct:.1f}% ({inp.admixture.type_string})",
                inputs={"base_water": water_before, "reduction_pct": reduction_pct, "admixture_type": inp.admixture.type_string},
                result=water,
                unit="kg/m³",
                clause_ref="BRE 331:1997 §5.3",
            ))

        # ==================================================================
        # STAGE 3 — Cement content
        # Normal: C3 (W ÷ W/C). pfa: C6/C7/C8 with k = 0.30 (§9.3.3).
        # ggbs ≤ 40%: C3 total then mass-for-mass split (§10.3).
        # ==================================================================

        scm_content = 0.0  # pfa (F) or ggbs (G) content; 0 for plain mixes
        fig6_ratio = wc_final  # Figure 6 entry ratio (W/C, or W/(C+F) for pfa)
        min_cement = getattr(inp, "min_cement_kg", None)
        max_cement = getattr(inp, "max_cement_kg", None)
        if scm_mode == "pfa":
            # C6: C = (100−p)·W / ((100−(1−k)·p)·R), R = W/(C+kF), k = 0.30.
            _k = PFA_EFFICIENCY_K
            _den = (100.0 - (1.0 - _k) * p_pct) * wc_final
            cement_c = (100.0 - p_pct) * water / _den
            # C7: F = p·C/(100−p).
            scm_content = p_pct * cement_c / (100.0 - p_pct)
            combined = cement_c + scm_content
            steps.append(self._make_step(
                number=7,
                description="Portland cement content (C6)",
                formula=f"(100−{p_pct:g})×{water:.0f} / ((100−0.7×{p_pct:g})×{wc_final:.2f})",
                inputs={"water": water, "pfa_pct": p_pct, "equiv_ratio": wc_final},
                result=cement_c,
                unit="kg/m³",
                clause_ref="Calculation C6 (§9.3.3)",
            ))
            steps.append(self._make_step(
                number=7.1,
                description="pfa content (C7)",
                formula=f"{p_pct:g}×{cement_c:.0f} / (100−{p_pct:g})",
                inputs={"pfa_pct": p_pct, "cement": cement_c},
                result=scm_content,
                unit="kg/m³",
                clause_ref="Calculation C7 (§9.3.3)",
            ))
            # C8 + Item 3.8 durability comparison on W/(C+F).
            fig6_ratio = water / combined if combined > 0 else wc_final
            if max_wc is not None and fig6_ratio > max_wc:
                combined = water / max_wc
                cement_c = combined * (100.0 - p_pct) / 100.0
                scm_content = combined * p_pct / 100.0
                fig6_ratio = max_wc
                warnings.append(
                    f"Durability override (Item 3.8): W/(C+F) reduced to "
                    f"{max_wc:.2f}; combined cementitious raised to "
                    f"{combined:.0f} kg/m³ at p = {p_pct:g}%"
                )
            steps.append(self._make_step(
                number=7.2,
                description="Free-water/(cement+pfa) ratio (C8)",
                formula=f"{water:.0f} / ({cement_c:.0f}+{scm_content:.0f})",
                inputs={"water": water, "cement": cement_c, "pfa": scm_content,
                        "max_wc_item38": max_wc},
                result=fig6_ratio,
                unit="",
                clause_ref="Calculation C8, Item 3.7/3.8 (§9.3.3)",
            ))
            # Items 3.2/3.3 compare against combined (C+F) (Table 12).
            if max_cement is not None and combined > max_cement:
                # §5.3 / Example 4: the specification cannot be met — stop.
                raise ValueError(
                    f"Calculated cementitious content (C+F) {combined:.0f} kg/m³ "
                    f"exceeds the specified maximum {max_cement:.0f} kg/m³ — it "
                    f"is not possible to proceed with these requirements "
                    f"(BRE 331:1997 §5.3). Consider a different cement strength "
                    f"class, aggregate type or maximum size, lower workability, "
                    f"or a water-reducing admixture"
                )
            if min_cement is not None and combined < min_cement:
                combined = min_cement
                warnings.append(
                    f"Min cement content {min_cement:.0f} kg/m³ not met — "
                    f"combined (C+F) increased to {combined:.0f} kg/m³"
                )
            # The (C+F) total is carried forward to the nearest 5 kg —
            # the §9.4 example reports C 280 + F 120 = 400 kg/m³ — and
            # split back proportionally; Item 3.7's Figure 6 entry ratio
            # uses the rounded total.
            combined = _clamp_round5(combined, min_cement, max_cement)
            cement_c = combined * (100.0 - p_pct) / 100.0
            scm_content = combined * p_pct / 100.0
            fig6_ratio = water / combined if combined > 0 else wc_final
            cement_content = cement_c
            steps.append(self._make_step(
                number=8,
                description="Final cementitious content (C+F)",
                formula=f"{cement_c:.0f} (C) + {scm_content:.0f} (F) = {combined:.0f} kg/m³",
                inputs={"cement": cement_c, "pfa": scm_content,
                        "min_cement": min_cement, "max_cement": max_cement},
                result=combined,
                unit="kg/m³",
                clause_ref="Item 3.1 (Table 12), 3.2–3.3",
            ))
        else:
            cement_calc = water / wc_final
            steps.append(self._make_step(
                number=7,
                description="Cement content (C3: W ÷ W/C)",
                formula=f"{water:.0f} ÷ {wc_final:.2f} = {cement_calc:.1f}",
                inputs={"water": water, "wc_ratio": wc_final},
                result=cement_calc,
                unit="kg/m³",
                clause_ref="Calculation C3, Item 3.1",
            ))

            # Min cement durability limit (compared on the C3 total,
            # which for ggbs equals the combined (C+G) per §10.3).
            cement_content = cement_calc
            if max_cement is not None and cement_calc > max_cement:
                # §5.3 / Example 4 (§7.4: 580 kg/m³ > 550 maximum): when C3
                # exceeds a specified maximum "it is probable that the
                # specification cannot be met simultaneously on strength
                # and workability requirements with the selected
                # materials" — the design STOPS. Capping the cement while
                # keeping the water would raise the free-water/cement ratio
                # above the Figure 4 value and silently miss the target
                # mean strength.
                raise ValueError(
                    f"Calculated cement content {cement_calc:.0f} kg/m³ exceeds "
                    f"the specified maximum {max_cement:.0f} kg/m³ — it is not "
                    f"possible to proceed with these requirements "
                    f"(BRE 331:1997 §5.3, Example 4). Consider a different "
                    f"cement strength class, aggregate type or maximum size, "
                    f"lower workability, or a water-reducing admixture"
                )
            if min_cement is not None and cement_calc < min_cement:
                cement_content = min_cement
                warnings.append(
                    f"Min cement content {min_cement:.0f} kg/m³ not met — "
                    f"increased to {cement_content:.0f} kg/m³"
                )
            # C3 is reported and carried forward to the nearest 5 kg
            # (§7.4: 215 ÷ 0.37 = 581 → 580), and Item 3.4's modified
            # W/C is derived from the rounded content.
            cement_content = _clamp_round5(
                cement_content, min_cement, max_cement)
            wc_final = round(water / cement_content, 2)
            fig6_ratio = wc_final

            if scm_mode == "ggbs":
                # Mass-for-mass split of the C3 total (§10.3, ≤ 40% path);
                # 28-day strength comparable, limits compare on the combined
                # total (unchanged by the split).
                scm_content = cement_content * p_pct / 100.0
                cement_content = cement_content - scm_content
                steps.append(self._make_step(
                    number=7.5,
                    description="ggbs split (mass-for-mass)",
                    formula=f"{p_pct:g}% of {cement_content + scm_content:.0f}",
                    inputs={"total": cement_content + scm_content,
                            "ggbs_pct": p_pct},
                    result=scm_content,
                    unit="kg/m³",
                    clause_ref="BRE 331:1997 §10.3",
                ))

            steps.append(self._make_step(
                number=8,
                description="Final cement content"
                            + (" (C+G combined)" if scm_mode == "ggbs" else ""),
                formula=f"C = {water:.0f} / {wc_final:.2f} = {cement_calc:.1f}"
                        f" → {cement_content + scm_content:.0f} kg/m³ (nearest 5 kg)",
                inputs={"water": water, "wc_ratio": wc_final, "min_cement": min_cement,
                        "max_cement": max_cement, "c3_calculated": cement_calc},
                result=cement_content + scm_content,
                unit="kg/m³",
                clause_ref="Item 3.1–3.4",
            ))

        if _admix_active and inp.admixture.dosage_percent > 0:
            # Dosed on the combined cementitious content when pfa/ggbs is
            # present (IS 10262 Annex B practice); BRE 331 is silent on the
            # basis, so the assumption is recorded here.
            _dose_base = cement_content + scm_content
            admixture_mass_kg = _dose_base * (inp.admixture.dosage_percent / 100.0)
            admixture_type_result = inp.admixture.type_string
            admixture_dosage_result = inp.admixture.dosage_percent
            steps.append(self._make_step(
                number=8.1,
                description="Admixture content",
                formula=f"Admixture = {inp.admixture.dosage_percent:.2f}% by mass of "
                        + ("combined cementitious" if scm_mode else "cement"),
                inputs={"cementitious": _dose_base, "dosage_pct": inp.admixture.dosage_percent},
                result=admixture_mass_kg,
                unit="kg/m³",
                clause_ref="BRE 331:1997 §5.3",
            ))

        # ==================================================================
        # STAGE 4 — Wet density and total aggregate (Figure 5, C4)
        # ==================================================================

        agg_sg = inp.coarse_aggregate.specific_gravity
        _fig5_density = get_wet_density(water, agg_sg)
        # Item 4.2: the wet density of fully compacted concrete is
        # "expressed to the nearest 5 kg" (§4.3) — the standard's examples
        # read 2400 / 2325 / 2375 kg/m³ off the 5-kg chart grid.
        wet_density = float(_round_to_5(_fig5_density))
        steps.append(self._make_step(
            number=9,
            description="Estimated wet density (Figure 5)",
            formula=f"Figure 5: water={water:.0f}, SG={agg_sg:.2f}"
                    f" = {_fig5_density:.0f} → {wet_density:.0f} kg/m³ (nearest 5 kg)",
            inputs={"water": water, "agg_sg": agg_sg,
                    "figure5_read": _fig5_density},
            result=wet_density,
            unit="kg/m³",
            clause_ref="Figure 5, Item 4.1–4.2",
        ))

        # §8.3: air-entrained density = Figure 5 value minus 10·a·RDA,
        # then expressed to the nearest 5 kg like any Item 4.2 density.
        if air_pct > 0:
            _air_deduction = 10.0 * air_pct * agg_sg
            _density_before_round = wet_density - _air_deduction
            wet_density = float(_round_to_5(_density_before_round))
            steps.append(self._make_step(
                number=9.1,
                description="Wet density (air-entrained)",
                formula=f"{wet_density + _air_deduction:.0f} − 10 × {air_pct:.1f} × {agg_sg:.2f}"
                        f" = {_density_before_round:.1f} → {wet_density:.0f} kg/m³ (nearest 5 kg)",
                inputs={"figure5_density": wet_density + _air_deduction,
                        "air_pct": air_pct, "agg_sg": agg_sg,
                        "deduction": _air_deduction},
                result=wet_density,
                unit="kg/m³",
                clause_ref="BRE 331:1997 §8.3, Item 4.2",
            ))
            warnings.append(
                "Air-entrained trial mix: measure air content first (BS 1881 "
                "Part 106) — workability and strength readings depend on it "
                "(BRE 331:1997 §8.5)"
            )

        # Calculation C4 (C9 for pfa/ggbs): total = D − cementitious − W.
        _cementitious = cement_content + scm_content
        total_agg = wet_density - _cementitious - water
        steps.append(self._make_step(
            number=10,
            description="Total aggregate content (C4: D − C − W)"
                        + (" (C9: D − (C+F) − W)" if scm_mode else ""),
            formula=f"{wet_density:.0f} − {_cementitious:.0f} − {water:.0f}",
            inputs={"wet_density": wet_density, "cementitious": _cementitious, "water": water},
            result=total_agg,
            unit="kg/m³",
            clause_ref="Calculation C4, Item 4.2" + (" / C9 (§9.3.4)" if scm_mode else ""),
        ))

        # ==================================================================
        # STAGE 5 — Proportion of fine aggregate (Figure 6, C5)
        # ==================================================================

        pct_passing = self._get_pct_passing_600um(inp)
        # Figure 6 entry ratio: W/C normally, W/(C+F) for pfa (§9.3.5);
        # for ggbs the unchanged combined total keeps W/C (§10.3).
        # The panel column is the workability class (not the raw slump),
        # read by bilinear interpolation over the digitised chart panel.
        fine_agg_prop = get_fine_aggregate_proportion(
            nmsa=nmsa,
            wc_ratio=fig6_ratio,
            pct_passing_600um=pct_passing,
            workability_class=wc_class,
        )
        _panel = figure6_panel_label(nmsa, wc_class)
        steps.append(self._make_step(
            number=11,
            description="Fine aggregate proportion (Figure 6)"
                        + (" (W/(C+F) for pfa)" if scm_mode == "pfa" else ""),
            formula=f"Figure 6 [{_panel}]: w/c={fig6_ratio:.2f}, passing_600={pct_passing:.0f}% → {fine_agg_prop:.1f}%",
            inputs={"nmsa": nmsa, "workability": workability_desc, "workability_class": wc_class,
                    "figure6_panel": _panel, "ratio": fig6_ratio, "pct_passing_600um": pct_passing},
            result=fine_agg_prop,
            unit="%",
            clause_ref="Figure 6, Item 5.1–5.3" + (" + §9.3.5" if scm_mode == "pfa" else ""),
        ))

        # §8.2: entrained air makes concrete more cohesive — the fine
        # proportion may sometimes be cut by up to 5% of total aggregate.
        # Permissive ("may sometimes"), so guidance, never automatic.
        if air_pct > 0:
            warnings.append(
                "Air entrainment improves cohesiveness: it may be possible to "
                "reduce fine aggregate by up to 5% of total aggregate with a "
                "further small water saving (BRE 331:1997 §8.2) — decide at "
                "the trial mix, not here"
            )

        # Calculation C5: Fine aggregate = total × proportion / 100,
        # reported to the nearest 5 kg (§7.1: 1900 × 27% = 513 → 515).
        _fine_raw = total_agg * (fine_agg_prop / 100.0)
        fine_agg = float(_round_to_5(_fine_raw))
        steps.append(self._make_step(
            number=12,
            description="Fine aggregate content (C5: total × prop%)",
            formula=f"{total_agg:.0f} × {fine_agg_prop:.1f}% = {_fine_raw:.1f}"
                    f" → {fine_agg:.0f} kg/m³ (nearest 5 kg)",
            inputs={"total_agg": total_agg, "fine_agg_prop": fine_agg_prop},
            result=fine_agg,
            unit="kg/m³",
            clause_ref="Calculation C5, Item 5.4",
        ))

        # Coarse aggregate = total − fine
        coarse_agg = total_agg - fine_agg
        steps.append(self._make_step(
            number=13,
            description="Coarse aggregate content",
            formula=f"{total_agg:.0f} − {fine_agg:.0f}",
            inputs={"total_agg": total_agg, "fine_agg": fine_agg},
            result=coarse_agg,
            unit="kg/m³",
            clause_ref="Calculation C5, Item 5.4",
        ))

        # All reported quantities are already on the nearest-5-kg grid
        # carried through C3/C4/C5 above, so the step values equal the
        # result panel exactly.

        # §5.5: subdivide total coarse aggregate into single sizes when
        # requested. Parts round to 5 kg with the remainder on the largest
        # fraction so the split always sums to the total.
        ca_split = getattr(inp, "ca_split", None)
        _ca_split_parts: dict[str, float] | None = None
        if ca_split is not None:
            if ca_split == "10+20" and nmsa != 20:
                raise ValueError(
                    f"CA split '10+20' requires 20 mm NMSA, got {nmsa} mm "
                    f"(BRE 331:1997 §5.5)"
                )
            if ca_split == "10+20+40" and nmsa != 40:
                raise ValueError(
                    f"CA split '10+20+40' requires 40 mm NMSA, got {nmsa} mm "
                    f"(BRE 331:1997 §5.5)"
                )
            ratios = {"10+20": (("10 mm", 1.0), ("20 mm", 2.0)),
                      "10+20+40": (("10 mm", 1.0), ("20 mm", 1.5), ("40 mm", 3.0))}[ca_split]
            _total_ratio = sum(r for _, r in ratios)
            _parts: dict[str, float] = {}
            _assigned = 0.0
            for _i, (_label, _r) in enumerate(ratios):
                if _i < len(ratios) - 1:
                    _parts[_label] = _round_to_5(coarse_agg * _r / _total_ratio)
                    _assigned += _parts[_label]
                else:
                    _parts[_label] = coarse_agg - _assigned
            _ca_split_parts = dict(_parts)
            steps.append(self._make_step(
                number=13.1,
                description=f"Coarse aggregate split ({ca_split})",
                formula=" + ".join(f"{v:.0f} ({k})" for k, v in _parts.items())
                        + f" = {coarse_agg:.0f}",
                inputs={"total_ca": coarse_agg, "split": ca_split, "parts": _parts},
                result=coarse_agg,
                unit="kg/m³",
                clause_ref="BRE 331:1997 §5.5",
            ))

        # §6.1: reference 0.05 m³ trial batch — enough for six 150 mm cubes
        # plus slump/Vebe and density tests. SSD batch masses scale directly;
        # oven-dry equivalents (×100/(100+A)) plus absorption water cover
        # dry-batched aggregates, which must pre-soak with about half the
        # mixing water before cement goes in (BS 1881 Part 125).
        _trial_vol = 0.05
        _fa_abs = inp.fine_aggregate.absorption_percent
        _ca_abs = inp.coarse_aggregate.absorption_percent
        _dry_fa = fine_agg * 100.0 / (100.0 + _fa_abs)
        _dry_ca = coarse_agg * 100.0 / (100.0 + _ca_abs)
        _abs_water = (fine_agg - _dry_fa) + (coarse_agg - _dry_ca)
        _trial_inputs: dict = {
            "trial_volume_m3": _trial_vol,
            "cement": round(cement_content * _trial_vol, 2),
            "water": round(water * _trial_vol, 2),
            "fine_agg_ssd": round(fine_agg * _trial_vol, 2),
            "coarse_agg_ssd": round(coarse_agg * _trial_vol, 2),
            "fine_agg_oven_dry": round(_dry_fa * _trial_vol, 2),
            "coarse_agg_oven_dry": round(_dry_ca * _trial_vol, 2),
            "absorption_water": round(_abs_water * _trial_vol, 2),
        }
        if scm_content > 0:
            _trial_inputs["scm"] = round(scm_content * _trial_vol, 2)
        steps.append(self._make_step(
            number=14,
            description="Trial batch quantities (0.05 m³ reference)",
            formula=f"SSD × 0.05; oven-dry FA {_dry_fa * _trial_vol:.2f}, "
                    f"CA {_dry_ca * _trial_vol:.2f}, absorption water "
                    f"{_abs_water * _trial_vol:.2f}",
            inputs=_trial_inputs,
            result=_trial_vol,
            unit="m³",
            clause_ref="BRE 331:1997 §6.1 / BS 1881 Part 125",
        ))

        return MixDesignResult(
            code_used="doe",
            target_mean_strength_mpa=target_mean,
            # Reported ratio is W/C normally, W/(C+0.30F) for pfa (Item 1.7);
            # the W/(C+F) compliance ratio lives in step 7.2 (Item 3.7).
            w_c_ratio=round(wc_final, 2),
            water_kg=water,
            cement_kg=cement_content,
            scm_kg=round(scm_content, 1),
            fine_aggregate_kg=fine_agg,
            coarse_aggregate_kg=coarse_agg,
            air_volume_percent=round(air_pct, 1),
            volume_m3=inp.volume_m3,
            steps=tuple(steps),
            warnings=tuple(warnings),
            admixture_kg=round(admixture_mass_kg, 2) if admixture_mass_kg > 0 else None,
            admixture_type=admixture_type_result,
            admixture_dosage_percent=admixture_dosage_result,
            ca_split_kg=_ca_split_parts,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_agg_type(inp: MixDesignInput) -> str:
        """Map AggregateShape enum or string to DOE 'crushed' / 'uncrushed'.

        For DOE, the aggregate type determines water content from Table 3.
        When fine and coarse aggregates are of different types, the
        weighted formula W = 2/3 Wf + 1/3 Wc is used (BRE 331:1997 Note to Table 3).
        """
        raw = inp.coarse_aggregate.shape
        shape = raw.value.lower() if hasattr(raw, "value") else str(raw).lower()
        # BRE 331:1997 §1.2.4 recognises only two classes: uncrushed
        # (rounded/irregular particles, including sub-angular and gravel) and
        # crushed (angular, rough-textured, produced by crushing). Crushed
        # fragments stay crushed; everything else is uncrushed. NOTE: the
        # "crushed" substring test must come without a bare "angular"
        # substring test, because "sub_angular" contains "angular".
        crushed_names = {"crushed", "angular", "crushed_fragments"}
        if shape in crushed_names or "crushed" in shape:
            return "crushed"
        return "uncrushed"

    @staticmethod
    def _map_fine_agg_type(inp: MixDesignInput) -> str:
        """Map FineAggregate shape to DOE 'crushed' / 'uncrushed'.

        Uses the fine aggregate's shape field if set, otherwise falls back
        to the coarse aggregate type (for backward compatibility).
        """
        if hasattr(inp.fine_aggregate, 'shape') and inp.fine_aggregate.shape is not None:
            raw = inp.fine_aggregate.shape
            shape = raw.value.lower() if hasattr(raw, "value") else str(raw).lower()
            # Same two-class rule as _map_agg_type (BRE 331:1997 §1.2.4);
            # no bare "angular" substring test — see note above.
            crushed_names = {"crushed", "angular", "crushed_fragments"}
            if shape in crushed_names or "crushed" in shape:
                return "crushed"
            return "uncrushed"
        # Fallback to coarse aggregate type for backward compatibility
        return DOEMixDesign._map_agg_type(inp)

    @staticmethod
    def _map_cement_class(inp: MixDesignInput) -> str:
        """Map CementType enum to DOE cement strength class."""
        cement_type = inp.cement.type.value
        # Map to DOE classes based on BS EN 197-1 naming
        if "53" in cement_type:
            return "52.5"
        # OPC_33 and OPC_43 are both class 42.5 in BS EN 197-1
        return "42.5"

    @staticmethod
    def _get_pct_passing_600um(inp: MixDesignInput) -> float:
        """Extract % passing 600 µm sieve from fine aggregate.

        Required input: BRE 331:1997 Figure 6 (§5.5, Item 5.1) cannot be
        read without it. The dedicated pct_passing_600um field on
        FineAggregate is the source; missing values fail loudly rather
        than silently assuming a sand grading.
        """
        p = inp.fine_aggregate.pct_passing_600um
        if p is None:
            raise ValueError(
                "Percentage of fine aggregate passing the 600 µm sieve is "
                "required for DOE design (BRE 331:1997 Figure 6, Item 5.1) "
                "— no default sand grading is assumed"
            )
        return p


def _round_to_5(value: float) -> float:
    """Round to the nearest 5 kg per DOE convention (Item 4.3 note)."""
    return round(value / 5) * 5


def _clamp_round5(
    value: float,
    min_limit: float | None,
    max_limit: float | None,
) -> float:
    """Round to the nearest 5 kg without crossing a cementitious limit.

    Rounding must never push a cement content outside a specified
    min/max (Items 3.2/3.3): a round-up past the maximum lands on the
    largest 5-kg multiple at or below it, a round-down past the minimum
    on the smallest 5-kg multiple at or above it.
    """
    result = float(_round_to_5(value))
    if max_limit is not None and result > max_limit:
        result = float(math.floor(max_limit / 5.0) * 5.0)
    if min_limit is not None and result < min_limit:
        result = float(math.ceil(min_limit / 5.0) * 5.0)
    return result
