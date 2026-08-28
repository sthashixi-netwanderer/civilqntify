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
    get_free_water_content,
    get_fine_aggregate_proportion,
    get_k_value,
    get_reference_strength,
    get_standard_deviation,
    get_wet_density,
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
        return target_strength_mpa + margin

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
        # DOE structural assumption: this app designs for structural elements only
        # (BRE 331:1997 §4.4, Figure 3; IS 456 exposure).  Characteristic strength
        # fc must be ≥ 25 MPa — enforced in MixDesignInput.__post_init__.
        # Standard deviation is derived from number of test cubes n (see §4.4).
        # n < 20 → s = 8 MPa (Figure 3 Line A), n ≥ 20 → s = 4 MPa
        # (Figure 3 Line B).  The n value is shown to convey meaning:
        # "number of test cubes that will be cast for testing the strength".
        num_cubes: int | None = getattr(inp, "num_test_cubes", None)
        # Validate structural fc again for programmatic callers bypassing Input validation
        if fc < 25.0:
            raise ValueError(
                f"DOE (BR 331:1997) structural design requires fc ≥ 25 MPa. Got {fc} MPa. "
                f"(This app assumes the mix is for structural elements; "
                f"see BRE 331 §4.4, Figure 3)"
            )
        # Record structural assumption as informational warning (visible in result)
        n_str = f"{num_cubes}" if num_cubes is not None else "—"
        if num_cubes is not None and num_cubes >= 20:
            s_desc = "4 MPa (Line B, n≥20)"
        elif num_cubes is not None:
            s_desc = "8 MPa (Line A, n<20)"
        else:
            s_desc = "8 MPa (n<20) / 4 MPa (n≥20)"
        structural_note = (
            "DOE design assumes structural concrete (fc ≥ 25 MPa). "
            f"Standard deviation s = {s_desc} for n test cubes "
            f"(n={n_str}; BRE 331:1997 Figure 3, §4.4 — n<20 → 8 MPa, n≥20 → 4 MPa). "
            "Ensure trial batch verification per BRE 331 §6."
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

        # --- Validate DOE inputs against Table 3 ---
        validation_warnings = validate_doe_inputs(
            nmsa=inp.nmsa,
            slump_mm=inp.slump_mm,
            agg_type=agg_type,
        )
        warnings.extend(validation_warnings)

        # ==================================================================
        # STAGE 1 — Target mean strength and W/C ratio
        # ==================================================================

        # Step 1.1: Standard deviation (Figure 3 or user-provided)
        # Structural DOE: n<20 → s=8 MPa (Line A), n≥20 → s=4 MPa (Line B) per BRE 331 §4.4.
        user_std_dev = getattr(inp, 'std_deviation', None)
        if user_std_dev is not None and user_std_dev > 0:
            std_dev = user_std_dev
            steps.append(self._make_step(
                number=1,
                description="Standard deviation (s) — structural, n = number of test cubes",
                formula=f"User-provided: s = {std_dev:.1f} MPa (BRE 331 §4.4, n={num_cubes if num_cubes is not None else '—'})",
                inputs={"fc": fc, "std_deviation": std_dev, "n_test_cubes": num_cubes},
                result=std_dev,
                unit="MPa",
                clause_ref="User input (BRE 331:1997 §4.4, structural fc≥25 MPa)",
            ))
        else:
            std_dev = get_standard_deviation(fc, has_data, n=num_cubes)
            # Describe n-aware structural rule
            if num_cubes is not None:
                if num_cubes < 20:
                    n_desc = f"n={num_cubes} (<20) → Line A, s=8 MPa"
                else:
                    n_desc = f"n={num_cubes} (≥20) → Line B, s=4 MPa"
                steps.append(self._make_step(
                    number=1,
                    description="Standard deviation (s) — structural, n = number of test cubes",
                    formula=f"Figure 3 structural: fc={fc:.0f} MPa, {n_desc}",
                    inputs={"fc": fc, "n_test_cubes": num_cubes, "has_production_data": has_data},
                    result=std_dev,
                    unit="MPa",
                    clause_ref="Figure 3, BRE 331 §4.4 (structural fc≥25 MPa, n<20→8 MPa, n≥20→4 MPa)",
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

        # Step 1.3: Target mean strength (Calculation C2)
        target_mean = fc + margin
        steps.append(self._make_step(
            number=3,
            description="Target mean strength (f_m = f_c + M)",
            formula=f"f_m = {fc:.1f} + {margin:.1f}",
            inputs={"fc": fc, "M": margin},
            result=target_mean,
            unit="MPa",
            clause_ref="Calculation C2",
        ))

        # Step 1.4: Reference strength at W/C=0.5 (Table 2)
        age_days = inp.age_days
        ref_strength = get_reference_strength(cement_class, agg_type, age_days)
        steps.append(self._make_step(
            number=4,
            description="Reference strength at W/C=0.5 (Table 2)",
            formula=f"Table 2: class={cement_class}, agg={agg_type}, age={age_days}d",
            inputs={"cement_class": cement_class, "agg_type": agg_type, "age_days": age_days},
            result=ref_strength,
            unit="MPa",
            clause_ref="Table 2",
        ))

        # Step 1.5: Free-W/C ratio from Figure 4
        wc_calc = wc_ratio_from_strength(target_mean, ref_strength)

        # Step 1.6: Apply maximum W/C override (durability)
        max_wc = inp.w_c_ratio  # repurposed as durability limit
        wc_final = wc_calc
        if max_wc is not None and max_wc < wc_calc:
            wc_final = max_wc
            warnings.append(
                f"Durability override: W/C reduced from {wc_calc:.2f} to {wc_final:.2f} "
                f"(max allowed = {max_wc:.2f})"
            )

        steps.append(self._make_step(
            number=5,
            description="Free-W/C ratio from Figure 4",
            formula=f"Figure 4: f(target={target_mean:.1f}, ref={ref_strength:.0f})",
            inputs={"target_mean": target_mean, "ref_strength": ref_strength, "max_wc": max_wc},
            result=wc_final,
            unit="",
            clause_ref="Figure 4, Item 1.7/1.8",
        ))

        # ==================================================================
        # STAGE 2 — Free-water content (Table 3)
        # ==================================================================

        nmsa = inp.nmsa
        coarse_agg_type = self._map_agg_type(inp)
        fine_agg_type = self._map_fine_agg_type(inp)

        # When coarse and fine aggregates are of different types, use the
        # weighted formula: W = 2/3 Wf + 1/3 Wc (BRE 331:1997 Note to Table 3)
        if coarse_agg_type != fine_agg_type:
            w_fine = get_free_water_content(nmsa, fine_agg_type, inp.slump_mm)
            w_coarse = get_free_water_content(nmsa, coarse_agg_type, inp.slump_mm)
            water = (2.0 / 3.0) * w_fine + (1.0 / 3.0) * w_coarse
            steps.append(self._make_step(
                number=6,
                description="Free-water content (Table 3, mixed types)",
                formula=f"W = 2/3×{w_fine:.0f} + 1/3×{w_coarse:.0f} = {water:.1f}",
                inputs={"nmsa": nmsa, "fine_agg_type": fine_agg_type, "coarse_agg_type": coarse_agg_type,
                        "slump_mm": inp.slump_mm, "w_fine": w_fine, "w_coarse": w_coarse},
                result=water,
                unit="kg/m³",
                clause_ref="Table 3 Note, Item 2.3",
            ))
        else:
            water = get_free_water_content(nmsa, coarse_agg_type, inp.slump_mm)
            steps.append(self._make_step(
                number=6,
                description="Free-water content (Table 3)",
                formula=f"Table 3: nmsa={nmsa}, agg={coarse_agg_type}, slump={inp.slump_mm:.0f}",
                inputs={"nmsa": nmsa, "agg_type": coarse_agg_type, "slump_mm": inp.slump_mm},
                result=water,
                unit="kg/m³",
                clause_ref="Table 3, Item 2.3",
            ))

        # Admixture water reduction (BRE 331:1997 §5.3)
        admixture_mass_kg = 0.0
        admixture_type_result = None
        admixture_dosage_result = None
        if inp.admixture and inp.admixture.water_reduction_percent > 0:
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
        # STAGE 3 — Cement content (Calculation C3)
        # ==================================================================

        cement_calc = water / wc_final
        steps.append(self._make_step(
            number=7,
            description="Cement content (C3: W ÷ W/C)",
            formula=f"{water:.0f} ÷ {wc_final:.2f}",
            inputs={"water": water, "wc_ratio": wc_final},
            result=cement_calc,
            unit="kg/m³",
            clause_ref="Calculation C3, Item 3.1",
        ))

        # Min/max cement durability limits (stored in scm_kg / admixture fields
        # as None — we check via optional attributes or warnings)
        min_cement = getattr(inp, "min_cement_kg", None)
        max_cement = getattr(inp, "max_cement_kg", None)

        cement_content = cement_calc
        if max_cement is not None and cement_calc > max_cement:
            cement_content = max_cement
            wc_final = water / cement_content
            warnings.append(
                f"Max cement content {max_cement:.0f} kg/m³ exceeded — "
                f"reduced to {cement_content:.0f} kg/m³, W/C revised to {wc_final:.2f}"
            )
        if min_cement is not None and cement_calc < min_cement:
            cement_content = min_cement
            wc_final = water / cement_content
            warnings.append(
                f"Min cement content {min_cement:.0f} kg/m³ not met — "
                f"increased to {cement_content:.0f} kg/m³, W/C revised to {wc_final:.2f}"
            )

        steps.append(self._make_step(
            number=8,
            description="Final cement content",
            formula=f"C = {water:.0f} / {wc_final:.2f}",
            inputs={"water": water, "wc_ratio": wc_final, "min_cement": min_cement, "max_cement": max_cement},
            result=cement_content,
            unit="kg/m³",
            clause_ref="Item 3.1–3.3",
        ))

        if inp.admixture and inp.admixture.dosage_percent > 0:
            admixture_mass_kg = cement_content * (inp.admixture.dosage_percent / 100.0)
            admixture_type_result = inp.admixture.type_string
            admixture_dosage_result = inp.admixture.dosage_percent
            steps.append(self._make_step(
                number=8.1,
                description="Admixture content",
                formula=f"Admixture = {inp.admixture.dosage_percent:.2f}% by mass of cement",
                inputs={"cement": cement_content, "dosage_pct": inp.admixture.dosage_percent},
                result=admixture_mass_kg,
                unit="kg/m³",
                clause_ref="BRE 331:1997 §5.3",
            ))

        # ==================================================================
        # STAGE 4 — Wet density and total aggregate (Figure 5, C4)
        # ==================================================================

        agg_sg = inp.coarse_aggregate.specific_gravity
        wet_density = get_wet_density(water, agg_sg)
        steps.append(self._make_step(
            number=9,
            description="Estimated wet density (Figure 5)",
            formula=f"Figure 5: water={water:.0f}, SG={agg_sg:.2f}",
            inputs={"water": water, "agg_sg": agg_sg},
            result=wet_density,
            unit="kg/m³",
            clause_ref="Figure 5, Item 4.1",
        ))

        # Calculation C4: Total aggregate = D − C − W
        total_agg = wet_density - cement_content - water
        steps.append(self._make_step(
            number=10,
            description="Total aggregate content (C4: D − C − W)",
            formula=f"{wet_density:.0f} − {cement_content:.0f} − {water:.0f}",
            inputs={"wet_density": wet_density, "cement": cement_content, "water": water},
            result=total_agg,
            unit="kg/m³",
            clause_ref="Calculation C4, Item 4.2",
        ))

        # ==================================================================
        # STAGE 5 — Proportion of fine aggregate (Figure 6, C5)
        # ==================================================================

        pct_passing = self._get_pct_passing_600um(inp)
        fine_agg_prop = get_fine_aggregate_proportion(
            nmsa=nmsa,
            wc_ratio=wc_final,
            pct_passing_600um=pct_passing,
            slump_mm=inp.slump_mm,
        )
        steps.append(self._make_step(
            number=11,
            description="Fine aggregate proportion (Figure 6)",
            formula=f"Figure 6: nmsa={nmsa}, slump={inp.slump_mm:.0f}, W/C={wc_final:.2f}, passing_600={pct_passing:.0f}%",
            inputs={"nmsa": nmsa, "slump_mm": inp.slump_mm, "wc_ratio": wc_final, "pct_passing_600um": pct_passing},
            result=fine_agg_prop,
            unit="%",
            clause_ref="Figure 6, Item 5.1–5.3",
        ))

        # Calculation C5: Fine aggregate = total × proportion / 100
        fine_agg = total_agg * (fine_agg_prop / 100.0)
        steps.append(self._make_step(
            number=12,
            description="Fine aggregate content (C5: total × prop%)",
            formula=f"{total_agg:.0f} × {fine_agg_prop:.1f}%",
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

        # ==================================================================
        # Round to nearest 5 kg per DOE convention
        # ==================================================================
        cement_content = _round_to_5(cement_content)
        fine_agg = _round_to_5(fine_agg)
        coarse_agg = _round_to_5(coarse_agg)
        water = _round_to_5(water)

        return MixDesignResult(
            code_used="doe",
            target_mean_strength_mpa=target_mean,
            w_c_ratio=round(wc_final, 2),
            water_kg=water,
            cement_kg=cement_content,
            fine_aggregate_kg=fine_agg,
            coarse_aggregate_kg=coarse_agg,
            air_volume_percent=0.0,
            volume_m3=inp.volume_m3,
            steps=tuple(steps),
            warnings=tuple(warnings),
            admixture_kg=round(admixture_mass_kg, 2) if admixture_mass_kg > 0 else None,
            admixture_type=admixture_type_result,
            admixture_dosage_percent=admixture_dosage_result,
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
        crushed_names = {"crushed", "angular", "crushed_fragments", "sub_angular"}
        return "crushed" if shape in crushed_names or "crushed" in shape or "angular" in shape else "uncrushed"

    @staticmethod
    def _map_fine_agg_type(inp: MixDesignInput) -> str:
        """Map FineAggregate shape to DOE 'crushed' / 'uncrushed'.

        Uses the fine aggregate's shape field if set, otherwise falls back
        to the coarse aggregate type (for backward compatibility).
        """
        if hasattr(inp.fine_aggregate, 'shape') and inp.fine_aggregate.shape is not None:
            raw = inp.fine_aggregate.shape
            shape = raw.value.lower() if hasattr(raw, "value") else str(raw).lower()
            crushed_names = {"crushed", "angular", "crushed_fragments", "sub_angular"}
            return "crushed" if shape in crushed_names or "crushed" in shape or "angular" in shape else "uncrushed"
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

        Uses the dedicated pct_passing_600um field on FineAggregate.
        Falls back to 60% (medium sand) if not provided.
        """
        p = inp.fine_aggregate.pct_passing_600um
        if p is not None:
            return p
        return 60.0


def _round_to_5(value: float) -> float:
    """Round to the nearest 5 kg per DOE convention (Item 4.3 note)."""
    return round(value / 5) * 5
