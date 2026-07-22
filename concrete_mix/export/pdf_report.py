"""PDF report generator for concrete mix design results.

Uses fpdf2 to produce a professional engineering report with:
- Input parameters summary
- Material quantities (per m³ and total)
- Step-by-step calculation trace with formulas and clause references
- Warnings and engineering notes
- Glossary of terms for non-specialist readers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fpdf import FPDF

from concrete_mix.models.mix_result import MixDesignResult

# Unicode → ASCII replacements for PDF core fonts (Helvetica/Courier)
_UNICODE_MAP = {
    "\u03c3": "s",       # σ (sigma)
    "\u03c0": "pi",      # π (pi)
    "\u00b3": "^3",      # ³
    "\u00b2": "^2",      # ²
    "\u2265": ">=",      # ≥
    "\u2264": "<=",      # ≤
    "\u00d7": "x",       # ×
    "\u2212": "-",       # − (minus)
    "\u2013": "-",       # – (en dash)
    "\u2014": "--",      # — (em dash)
    "\u2022": "*",       # • (bullet)
    "\u2018": "'",       # '
    "\u2019": "'",       # '
    "\u201c": '"',       # "
    "\u201d": '"',       # "
    "\u2082": "2",       # ₂ (subscript 2)
    "\u2081": "1",       # ₁ (subscript 1)
    "\u2080": "0",       # ₀ (subscript 0)
}


def _sanitize(text: str) -> str:
    """Replace Unicode characters unsupported by PDF core fonts."""
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)
    # Strip any remaining non-latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _MixReportPDF(FPDF):
    """Custom PDF with header/footer and helper methods."""

    def __init__(self, code_used: str) -> None:
        super().__init__()
        self._code_used = code_used
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(30, 64, 175)  # blue accent
        self.cell(0, 10, "CivilQntify", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(107, 114, 128)  # gray
        self.cell(
            0, 5,
            _sanitize(
                f"Concrete Mix Design Report  |  {self._code_used}  |  "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ),
            new_x="LMARGIN", new_y="NEXT",
        )
        self.set_draw_color(30, 64, 175)
        self.set_line_width(0.5)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(156, 163, 175)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    # ── Helpers ─────────────────────────────────────────────────────

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 64, 175)
        self.ln(4)
        self.cell(0, 8, _sanitize(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(209, 213, 219)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def subsection_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(55, 65, 81)
        self.ln(2)
        self.cell(0, 7, _sanitize(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def key_value_row(self, key: str, value: str, indent: float = 0) -> None:
        x = 10 + indent
        self.set_font("Helvetica", "", 10)
        self.set_text_color(107, 114, 128)
        self.set_x(x)
        self.cell(80 - indent, 6, _sanitize(key), new_x="END")
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(44, 62, 80)
        self.cell(0, 6, _sanitize(value), new_x="LMARGIN", new_y="NEXT")

    def note_text(self, text: str) -> None:
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(107, 114, 128)
        self.multi_cell(0, 5, _sanitize(text))
        self.ln(1)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(44, 62, 80)
        self.multi_cell(0, 5, _sanitize(text))
        self.ln(1)

    def warning_text(self, text: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(146, 64, 14)
        self.multi_cell(0, 5, _sanitize(f"  !  {text}"))
        self.ln(1)

    def check_page_space(self, needed_mm: float = 40) -> None:
        """Add a page break if not enough space remaining."""
        if self.get_y() + needed_mm > 270:
            self.add_page()


def generate_pdf_report(
    result: MixDesignResult,
    input_params: dict[str, Any] | None = None,
) -> bytes:
    """Generate a PDF mix design report.

    Args:
        result: The completed mix design result
        input_params: Optional dict of input parameters used for the calculation.
            Keys should match the kwargs passed to design_mix_simple().

    Returns:
        PDF file content as bytes
    """
    pdf = _MixReportPDF(result.code_used)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ════════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ════════════════════════════════════════════════════════════════
    pdf.section_title("1. Executive Summary")

    code_label = "ACI 211.1-91 (American)" if "ACI" in result.code_used else "IS 10262:2019 (Indian)"
    pdf.body_text(
        f"This report presents a concrete mix design performed in accordance with "
        f"{code_label}. The design targets a characteristic compressive strength of "
        f"{result.target_mean_strength_mpa:.1f} MPa with a water-cement ratio of "
        f"{result.w_c_ratio:.3f}."
    )

    if result.volume_m3 != 1.0:
        pdf.body_text(
            f"The total volume requested is {result.volume_m3:.1f} m\u00b3. "
            f"All quantities below are shown per cubic metre and as total batch amounts."
        )

    # ════════════════════════════════════════════════════════════════
    # 2. INPUT PARAMETERS
    # ════════════════════════════════════════════════════════════════
    pdf.section_title("2. Input Parameters")

    if input_params:
        is_aci = input_params.get("code") == "aci211"

        pdf.subsection_title("Design Standard")
        pdf.key_value_row("Code", code_label)

        pdf.subsection_title("Mix Parameters")
        pdf.key_value_row("Target Strength (f'c / fck)", f"{input_params.get('target_strength_mpa', '?')} MPa")
        pdf.key_value_row("Required Slump", f"{input_params.get('slump_mm', '?')} mm")
        pdf.key_value_row("NMSA", f"{input_params.get('nmsa', '?')} mm")

        pdf.subsection_title("Cement")
        pdf.key_value_row("Cement Type", str(input_params.get("cement_type", "?")))
        pdf.key_value_row("Specific Gravity", f"{input_params.get('cement_sg', '?')}")

        pdf.subsection_title("Fine Aggregate")
        pdf.key_value_row("Specific Gravity", f"{input_params.get('fine_agg_sg', '?')}")
        if is_aci:
            pdf.key_value_row("Fineness Modulus", f"{input_params.get('fine_agg_fm', '?')}")
        else:
            zone = input_params.get("fine_agg_grading_zone") or "II"
            pdf.key_value_row("Grading Zone", f"Zone {zone}")

        pdf.subsection_title("Coarse Aggregate")
        pdf.key_value_row("Specific Gravity", f"{input_params.get('coarse_agg_sg', '?')}")

        # Code-specific
        if is_aci:
            pdf.subsection_title("ACI-Specific Options")
            pdf.key_value_row("Air-Entrained", "Yes" if input_params.get("air_entrained") else "No")
            pdf.key_value_row("Sulfate Exposure Class", str(input_params.get("sulfate_exposure_class", "S0")))
            pdf.key_value_row("Production Data", "\u226530 tests" if input_params.get("has_production_data", True) else "No data (<30 tests)")
        else:
            pdf.subsection_title("IS-Specific Options")
            exposure = input_params.get("exposure_class")
            pdf.key_value_row("Exposure Class (IS 456)", exposure.title() if exposure else "None specified")

        # SCM
        scm_pct = input_params.get("scm_replacement_percent", 0)
        if scm_pct > 0:
            pdf.subsection_title("Supplementary Cementitious Material")
            pdf.key_value_row("SCM Type", str(input_params.get("scm_type", "?")))
            pdf.key_value_row("Replacement", f"{scm_pct:.1f}%")

        # Admixture
        adm_wr = input_params.get("admixture_water_reduction", 0)
        if adm_wr > 0:
            pdf.subsection_title("Admixture")
            pdf.key_value_row("Water Reduction", f"{adm_wr:.1f}%")

        pdf.key_value_row("Target Volume", f"{input_params.get('volume_m3', 1.0)} m\u00b3")
    else:
        pdf.note_text("(Input parameters were not recorded for this calculation.)")

    # ════════════════════════════════════════════════════════════════
    # 3. MATERIAL QUANTITIES
    # ════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Material Quantities")

    pdf.subsection_title("Proportions per Cubic Metre")
    pdf.key_value_row("Cement", f"{result.cement_kg:.1f} kg/m\u00b3")
    if result.scm_kg > 0:
        pdf.key_value_row("SCM", f"{result.scm_kg:.1f} kg/m\u00b3")
        pdf.key_value_row("Total Cementitious", f"{result.total_cementitious_kg:.1f} kg/m\u00b3")
    pdf.key_value_row("Water", f"{result.water_kg:.1f} kg/m\u00b3")
    pdf.key_value_row("Fine Aggregate (Sand)", f"{result.fine_aggregate_kg:.1f} kg/m\u00b3")
    pdf.key_value_row("Coarse Aggregate", f"{result.coarse_aggregate_kg:.1f} kg/m\u00b3")
    pdf.key_value_row("Total Aggregate", f"{result.total_aggregate_kg:.1f} kg/m\u00b3")
    pdf.ln(2)
    pdf.key_value_row("Water/Cement Ratio", f"{result.w_c_ratio:.3f}")
    pdf.key_value_row("Target Mean Strength (f'cr/ftm)", f"{result.target_mean_strength_mpa:.1f} MPa")
    pdf.key_value_row("Air Content", f"{result.air_volume_percent:.1f}%")

    # Mix Ratio
    ratio = result.mix_ratio
    pdf.ln(4)
    pdf.subsection_title("Mix Ratio (Cement : Fine Aggregate : Coarse Aggregate)")
    pdf.body_text(
        "The mix ratio shows the proportion of each solid material relative to "
        "cement = 1, with the water-cement ratio in parentheses."
    )
    pdf.key_value_row(
        "Cement : Fine Agg : Coarse Agg (W/C)",
        f"{ratio['cement']:.1f} : {ratio['fine_aggregate']:.1f} : {ratio['coarse_aggregate']:.1f} ({result.w_c_ratio:.3f})",
    )

    # Total batch
    if result.volume_m3 != 1.0:
        v = result.volume_m3
        pdf.ln(4)
        pdf.subsection_title(f"Total Batch Quantities ({v:.1f} m\u00b3)")
        pdf.key_value_row("Cement", f"{result.cement_kg * v:.1f} kg")
        if result.scm_kg > 0:
            pdf.key_value_row("SCM", f"{result.scm_kg * v:.1f} kg")
        pdf.key_value_row("Water", f"{result.water_kg * v:.1f} kg")
        pdf.key_value_row("Fine Aggregate", f"{result.fine_aggregate_kg * v:.1f} kg")
        pdf.key_value_row("Coarse Aggregate", f"{result.coarse_aggregate_kg * v:.1f} kg")

    # ════════════════════════════════════════════════════════════════
    # 4. CALCULATION STEPS
    # ════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Calculation Steps (Detailed)")

    pdf.note_text(
        "Each step below shows the formula used, the input values, and the result. "
        "Clause references point to the relevant section of the design code."
    )

    for step in result.steps:
        pdf.check_page_space(35)

        # Step header
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(44, 62, 80)
        ref = f"  [{step.clause_ref}]" if step.clause_ref else ""
        pdf.cell(0, 6, _sanitize(f"Step {step.step_number}: {step.description}{ref}"),
                 new_x="LMARGIN", new_y="NEXT")

        # Formula
        pdf.set_font("Courier", "", 9)
        pdf.set_text_color(107, 114, 128)
        pdf.set_x(15)
        pdf.cell(0, 5, _sanitize(f"Formula: {step.formula}"), new_x="LMARGIN", new_y="NEXT")

        # Inputs
        if step.inputs:
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(107, 114, 128)
            inputs_str = ",  ".join(f"{k}={v}" for k, v in step.inputs.items())
            pdf.set_x(15)
            pdf.multi_cell(180, 5, _sanitize(f"Inputs:  {inputs_str}"))

        # Result
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 64, 175)
        pdf.set_x(15)
        pdf.cell(0, 6, _sanitize(f"Result: {step.result:.2f} {step.unit}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # ════════════════════════════════════════════════════════════════
    # 5. WARNINGS & NOTES
    # ════════════════════════════════════════════════════════════════
    pdf.check_page_space(50)
    pdf.section_title("5. Warnings & Advisory Notes")

    if result.warnings:
        for w in result.warnings:
            pdf.warning_text(w)
        pdf.ln(2)
    else:
        pdf.body_text("No warnings were generated for this design.")

    pdf.body_text(
        "Note: The above warnings are advisory. The designer should review each "
        "item and confirm that the final mix is validated by trial batches before "
        "use in construction."
    )

    # ════════════════════════════════════════════════════════════════
    # 6. ENGINEERING CONTEXT
    # ════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. Engineering Context & Glossary")

    is_aci_report = "ACI" in result.code_used

    if is_aci_report:
        pdf.subsection_title("Target Mean Strength (f'cr)")
        pdf.body_text(
            "The target mean strength f'cr is the average compressive strength that "
            "the concrete batch must achieve to ensure that the specified f'c is met "
            "with acceptable statistical confidence. Per ACI 318, f'cr is calculated "
            "using the larger of two formulas:\n"
            "  \u2022  f'cr = f'c + 1.34 \u00d7 s\n"
            "  \u2022  f'cr = f'c + 2.33 \u00d7 s \u2212 3.45 MPa\n"
            "where s is the standard deviation from prior test data. When no data "
            "exists, ACI 318 Table 26.4.3.1(b) provides conservative overdesign values."
        )

        pdf.subsection_title("Water/Cement Ratio")
        pdf.body_text(
            "The W/C ratio is the most significant factor controlling concrete strength "
            "and durability. A lower W/C ratio produces stronger, less permeable concrete "
            "but requires more cement and may reduce workability. The W/C ratio is selected "
            "from ACI 211.1 Table 6.3.4 based on the target mean strength, then capped by "
            "durability requirements (e.g., sulfate exposure per ACI 318 Table 19.3.2)."
        )

        pdf.subsection_title("Air Entrainment")
        pdf.body_text(
            "Air-entrained concrete contains tiny, uniformly distributed air bubbles "
            "(typically 2\u20138%) that improve freeze\u2013thaw durability. The air content "
            "target depends on NMSA and exposure severity (ACI 211.1 Table 6.3.3). "
            "Air-entrained mixes use less water and have different W/C ratio tables."
        )

        pdf.subsection_title("Sulfate Exposure Classes")
        pdf.body_text(
            "ACI 318 defines sulfate exposure classes (S0\u2013S3) based on soil and "
            "groundwater sulfate concentrations. Higher classes impose stricter W/C limits:\n"
            "  \u2022  S0: No exposure \u2014 no limit\n"
            "  \u2022  S1: Moderate \u2014 W/C \u2264 0.50\n"
            "  \u2022  S2: Severe \u2014 W/C \u2264 0.45\n"
            "  \u2022  S3: Very severe \u2014 W/C \u2264 0.40\n"
            "These limits override the strength-based W/C ratio when more restrictive."
        )
    else:
        pdf.subsection_title("Target Mean Strength (ftm)")
        pdf.body_text(
            "The target mean strength ftm is calculated as:\n"
            "  ftm = fck + 1.65 \u00d7 s\n"
            "where fck is the characteristic compressive strength and s is the assumed "
            "standard deviation from IS 10262:2019 Table 1. This ensures that at least "
            "95% of test results exceed fck."
        )

        pdf.subsection_title("Water/Cement Ratio")
        pdf.body_text(
            "The W/C ratio determines concrete strength and durability. IS 10262 "
            "provides separate W/C ratio curves for OPC 33, OPC 43, and OPC 53 grade "
            "cements. The selected W/C is then checked against IS 456:2000 Table 3 "
            "exposure limits, which cap the W/C ratio based on environmental conditions."
        )

        pdf.subsection_title("Exposure Classes (IS 456:2000)")
        pdf.body_text(
            "IS 456:2000 Table 5 defines exposure conditions that govern durability:\n"
            "  \u2022  Mild: Min 220 kg/m\u00b3 cement, W/C \u2264 0.60\n"
            "  \u2022  Moderate: Min 240 kg/m\u00b3 cement, W/C \u2264 0.60, grade M20\n"
            "  \u2022  Severe: Min 250 kg/m\u00b3 cement, W/C \u2264 0.50, grade M25\n"
            "  \u2022  Very Severe: Min 260 kg/m\u00b3 cement, W/C \u2264 0.45, grade M30\n"
            "  \u2022  Extreme: Min 280 kg/m\u00b3 cement, W/C \u2264 0.40, grade M35\n"
            "These limits ensure adequate durability for the intended service environment."
        )

        pdf.subsection_title("Grading Zones")
        pdf.body_text(
            "Fine aggregate (sand) is classified into Grading Zones I\u2013IV based on "
            "particle size distribution per IS 383. Zone II is the reference; coarser "
            "sand (Zone I) requires slightly less water, while finer sand (Zone III/IV) "
            "requires more. The water content is adjusted by \u22123% for Zone I and "
            "+3%/+6% for Zone III/IV."
        )

    pdf.subsection_title("Trial Batches")
    pdf.body_text(
        "This mix design is a theoretical starting point. Before use in construction, "
        "the designer must prepare and test at least 3 trial batches to verify that "
        "the target strength and workability are achieved. Adjustments to water content, "
        "admixture dosage, or aggregate proportions may be needed based on trial results."
    )

    pdf.subsection_title("Moisture Correction")
    pdf.body_text(
        "The aggregate quantities in this report are in saturated surface-dry (SSD) "
        "condition. In practice, the actual water added must be adjusted for the "
        "moisture content and absorption of the aggregates. If the aggregates are "
        "wetter than SSD, reduce the mixing water; if drier, increase it."
    )

    pdf.subsection_title("Volume Method")
    pdf.body_text(
        "This design uses the absolute volume method. The volume of each ingredient "
        "(cement, water, air, aggregates) is calculated from its mass and specific "
        "gravity, and the total is verified to equal 1.0 m\u00b3. Any discrepancy "
        "is absorbed by adjusting the fine aggregate quantity."
    )

    # ════════════════════════════════════════════════════════════════
    # 7. COST & CARBON (if available)
    # ════════════════════════════════════════════════════════════════
    if result.cost_per_m3 is not None or result.carbon_kg_co2_per_m3 is not None:
        pdf.check_page_space(40)
        pdf.section_title("7. Cost & Carbon Estimates")

        if result.cost_per_m3 is not None:
            pdf.key_value_row("Estimated Cost", f"{result.cost_per_m3:.2f} per m\u00b3")
        if result.carbon_kg_co2_per_m3 is not None:
            pdf.key_value_row("Embodied Carbon", f"{result.carbon_kg_co2_per_m3:.1f} kg CO\u2082/m\u00b3")
        if result.volume_m3 != 1.0:
            if result.cost_per_m3 is not None:
                pdf.key_value_row("Total Cost", f"{result.cost_per_m3 * result.volume_m3:.2f}")
            if result.carbon_kg_co2_per_m3 is not None:
                pdf.key_value_row("Total Carbon", f"{result.carbon_kg_co2_per_m3 * result.volume_m3:.1f} kg CO\u2082")

    # ════════════════════════════════════════════════════════════════
    # 8. DISCLAIMER
    # ════════════════════════════════════════════════════════════════
    pdf.check_page_space(40)
    pdf.section_title("Disclaimer")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.multi_cell(
        0, 5,
        "This report is generated by CivilQntify software and is intended for "
        "preliminary design and educational purposes. The designer of record is "
        "responsible for verifying all calculations, conducting trial batches, and "
        "ensuring compliance with local codes and project specifications. The "
        "software authors assume no liability for designs derived from this report."
    )

    return bytes(pdf.output())
