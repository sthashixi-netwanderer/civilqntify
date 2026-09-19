"""PDF report generator for concrete mix design results.

Uses LaTeX for professional typesetting (with fpdf2 fallback).
Generates a LaTeX source document and compiles it to PDF via pdflatex/xelatex/lualatex
if available, otherwise falls back to fpdf2 for portability.

Structure:
- Input parameters summary
- Material quantities (per m³ and total)
- Step-by-step calculation trace with formulas and clause references
- Warnings and engineering notes
- Glossary of terms
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
import pathlib
import sys
from typing import Any

from fpdf import FPDF

from concrete_mix.models.mix_result import MixDesignResult
from concrete_mix.utils.display import display_name

# ── Logo resolution ─────────────────────────────────────────────────


def _find_logo_file() -> pathlib.Path | None:
    """Locate logo in ``app/resources`` for PDF headers.

    Uses only the app/resources directory (project root and bundled
    PyInstaller location). Search order: logo.png → logo_with_wordmark.png → icon.png.
    Returns None if no logo is found (header renders text-only).
    """
    candidates = ["logo.png", "logo_with_wordmark.png", "icon.png"]
    search_dirs: list[pathlib.Path] = []
    try:
        # Project root = parents[2] from concrete_mix/export/pdf_report.py
        project_root = pathlib.Path(__file__).resolve().parents[2]
        search_dirs.append(project_root / "app" / "resources")
    except Exception:
        pass
    # PyInstaller / frozen bundle — datas bundles app/resources
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(pathlib.Path(meipass) / "app" / "resources")
    # CWD fallback (when launched from project root)
    search_dirs.append(pathlib.Path.cwd() / "app" / "resources")
    for d in search_dirs:
        for name in candidates:
            p = d / name
            try:
                if p.is_file():
                    return p
            except Exception:
                continue
    return None

# ── LaTeX escaping ──────────────────────────────────────────────────

_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# Unicode replacements for LaTeX (math mode or text)
_LATEX_UNICODE = {
    "\u03c3": r"$\sigma$",
    "\u03c0": r"$\pi$",
    "\u00b3": r"$^{3}$",
    "\u00b2": r"$^{2}$",
    "\u2265": r"$\geq$",
    "\u2264": r"$\leq$",
    "\u00d7": r"$\times$",
    "\u2212": r"$-$",
    "\u2013": r"--",
    "\u2014": r"---",
    "\u2022": r"$\bullet$",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2082": r"$_{2}$",
    "\u2081": r"$_{1}$",
    "\u2080": r"$_{0}$",
}


def _escape_latex(text: str) -> str:
    """Escape text for LaTeX, handling Unicode and special chars."""
    # First handle Unicode math symbols
    for char, repl in _LATEX_UNICODE.items():
        text = text.replace(char, repl)
    # Then escape LaTeX specials, but avoid double-escaping already inserted commands
    # We need to be careful: only escape raw specials not part of inserted LaTeX commands
    # Simple approach: escape & % $ # _ { } ~ ^ \ that are not already part of \$ etc.
    # First protect existing LaTeX commands by placeholder
    # For now, just escape the remaining specials that are not in math mode
    # We will escape &, %, #, _, {, }, ~, ^, \  but not $ (since we use math)
    # To avoid breaking math we inserted, we temporarily replace them
    placeholders = {}
    for i, (k, v) in enumerate(_LATEX_UNICODE.items()):
        ph = f"__LATEXUNI{i}__"
        if v in text:
            placeholders[ph] = v
            text = text.replace(v, ph)
    # Now escape specials except $ and \
    for char in ["&", "%", "#", "_", "{", "}", "~", "^"]:
        esc = _LATEX_ESCAPES[char]
        text = text.replace(char, esc)
    # Restore placeholders
    for ph, v in placeholders.items():
        text = text.replace(ph, v)
    return text


def _sanitize_latex(text: str) -> str:
    """Sanitize text for LaTeX: escape and handle non-ASCII."""
    if not text:
        return ""
    text = _escape_latex(str(text))
    # Replace any remaining non-ASCII with ?
    return text.encode("ascii", errors="replace").decode("ascii")


# ── fpdf2 fallback (original implementation, kept for portability) ──

_UNICODE_MAP = {
    "\u03c3": "s",
    "\u03c0": "pi",
    "\u00b3": "^3",
    "\u00b2": "^2",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u00d7": "x",
    "\u2212": "-",
    "\u2013": "-",
    "\u2014": "--",
    "\u2022": "*",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2082": "2",
    "\u2081": "1",
    "\u2080": "0",
}


def _sanitize(text: str) -> str:
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _MixReportPDF(FPDF):
    def __init__(self, code_used: str) -> None:
        super().__init__()
        self._code_used = code_used
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        logo_path = _find_logo_file()
        y_start = self.get_y()
        # Try to embed logo on the left (30 mm wide) with wordmark to its right
        if logo_path is not None:
            try:
                # Preserve aspect ratio; logo.png is ~400×60, logo_with_wordmark ~600×120
                self.image(str(logo_path), x=10, y=y_start, w=32)
                # Text block to the right of the logo
                self.set_xy(44, y_start + 1)
                self.set_font("Helvetica", "B", 18)
                self.set_text_color(30, 64, 175)
                self.cell(0, 10, "CivilQntify", new_x="LMARGIN", new_y="NEXT")
                self.set_x(44)
                self.set_font("Helvetica", "", 9)
                self.set_text_color(107, 114, 128)
                self.cell(0, 5, _sanitize(f"Concrete Mix Design Report  |  {self._code_used}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}"), new_x="LMARGIN", new_y="NEXT")
                # Ensure enough vertical space below the taller of logo/text
                # Logo height ≈ w * (h/w); for safety, advance to at least y_start+12
                target_y = max(self.get_y() + 2, y_start + 14)
                self.set_y(target_y)
                self.set_draw_color(30, 64, 175)
                self.set_line_width(0.5)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(4)
                return
            except Exception:
                # Fall back to text-only header if image embedding fails
                pass
        # Text-only header (fallback / no logo found)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(30, 64, 175)
        self.cell(0, 10, "CivilQntify", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(107, 114, 128)
        self.cell(0, 5, _sanitize(f"Concrete Mix Design Report  |  {self._code_used}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}"), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 64, 175)
        self.set_line_width(0.5)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(156, 163, 175)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

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
        if self.get_y() + needed_mm > 270:
            self.add_page()


def _generate_pdf_via_fpdf(result: MixDesignResult, input_params: dict[str, Any] | None = None) -> bytes:
    """Original fpdf2 implementation — used as fallback when LaTeX is unavailable."""
    pdf = _MixReportPDF(result.code_used)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.section_title("1. Executive Summary")
    if "ACI" in result.code_used:
        code_label = "ACI PRC-211.1-22 (American)"
    elif "doe" in result.code_used.lower():
        code_label = "DOE BRE 331:1997 (British)"
    else:
        code_label = "IS 10262:2019 (Indian)"
    pdf.body_text(f"This report presents a concrete mix design performed in accordance with {code_label}. The design targets a characteristic compressive strength of {result.target_mean_strength_mpa:.1f} MPa with a water-cement ratio of {result.w_c_ratio:.3f}.")
    if result.volume_m3 != 1.0:
        pdf.body_text(f"The total volume requested is {result.volume_m3:.1f} m\u00b3. All quantities below are shown per cubic metre and as total batch amounts.")
    pdf.section_title("2. Input Parameters")
    if input_params:
        is_aci = input_params.get("code") == "aci211"
        is_doe = input_params.get("code") == "doe"
        pdf.subsection_title("Design Standard")
        pdf.key_value_row("Code", code_label)
        pdf.subsection_title("Mix Parameters")
        pdf.key_value_row("Target Strength (f'c / fck)", f"{input_params.get('target_strength_mpa', '?')} MPa")
        pdf.key_value_row("Required Slump", f"{input_params.get('slump_mm', '?')} mm")
        pdf.key_value_row("NMSA", f"{input_params.get('nmsa', '?')} mm")
        pdf.subsection_title("Cement")
        pdf.key_value_row("Cement Type", display_name(str(input_params.get("cement_type", "?"))))
        pdf.key_value_row("Specific Gravity", f"{input_params.get('cement_sg', '?')}")
        pdf.subsection_title("Fine Aggregate")
        pdf.key_value_row("Specific Gravity", f"{input_params.get('fine_agg_sg', '?')}")
        if is_aci:
            pdf.key_value_row("Fineness Modulus", f"{input_params.get('fine_agg_fm', '?')}")
        elif is_doe:
            pdf.key_value_row("% Passing 600 µm", f"{input_params.get('fine_agg_pct_passing_600um', '?')}%")
        else:
            zone = input_params.get("fine_agg_grading_zone") or "II"
            pdf.key_value_row("Grading Zone", f"Zone {zone}")
        pdf.subsection_title("Coarse Aggregate")
        pdf.key_value_row("Specific Gravity", f"{input_params.get('coarse_agg_sg', '?')}")
        if is_doe:
            _rd = input_params.get("aggregate_relative_density_ssd")
            pdf.key_value_row(
                "Rel. Density, combined SSD (Item 4.1)",
                f"{_rd:.2f} (known)" if _rd else "Auto (mean of FA/CA SG)",
            )
        if is_aci:
            pdf.subsection_title("ACI-Specific Options")
            pdf.key_value_row("Air-Entrained", "Yes" if input_params.get("air_entrained") else "No")
            pdf.key_value_row("Sulfate Exposure Class", str(input_params.get("sulfate_exposure_class", "S0")))
            pdf.key_value_row("Production Data", "\u226530 tests" if input_params.get("has_production_data", True) else "No data (<30 tests)")
        elif is_doe:
            pdf.subsection_title("DOE-Specific Options (BRE 331)")
            pdf.key_value_row("Defective Percent", f"{input_params.get('defective_percent', 5.0)}%")
            _n = input_params.get("num_test_cubes", input_params.get("n_cubes", "—"))
            pdf.key_value_row("Test Cubes (n, Figure 3)", f"{_n}")
            pdf.key_value_row("Test Age", f"{input_params.get('age_days', 28)} days")
            pdf.key_value_row("Entrained Air (§8)", f"{input_params.get('air_pct', 0.0)}%")
        else:
            pdf.subsection_title("IS-Specific Options")
            exposure = input_params.get("exposure_class")
            pdf.key_value_row("Exposure Class (IS 456)", display_name(exposure) if exposure else "None specified")
        scm_pct = input_params.get("scm_replacement_percent", 0)
        if scm_pct > 0:
            pdf.subsection_title("Supplementary Cementitious Material")
            pdf.key_value_row("SCM Type", display_name(str(input_params.get("scm_type", "?"))))
            pdf.key_value_row("Replacement", f"{scm_pct:.1f}%")
        adm_wr = input_params.get("admixture_water_reduction", 0)
        if adm_wr > 0:
            pdf.subsection_title("Admixture")
            pdf.key_value_row("Water Reduction", f"{adm_wr:.1f}%")
        pdf.key_value_row("Target Volume", f"{input_params.get('volume_m3', 1.0)} m\u00b3")
    else:
        pdf.note_text("(Input parameters were not recorded for this calculation.)")
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
    ratio = result.mix_ratio
    pdf.ln(4)
    pdf.subsection_title("Mix Ratio (Cement : Fine Aggregate : Coarse Aggregate)")
    pdf.body_text("The mix ratio shows the proportion of each solid material relative to cement = 1, with the water-cement ratio in parentheses.")
    pdf.key_value_row("Cement : Fine Agg : Coarse Agg (W/C)", f"{ratio['cement']:.1f} : {ratio['fine_aggregate']:.1f} : {ratio['coarse_aggregate']:.1f} ({result.w_c_ratio:.3f})")
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
    pdf.add_page()
    pdf.section_title("4. Calculation Steps (Detailed)")
    pdf.note_text("Each step below shows the formula used, the input values, and the result. Clause references point to the relevant section of the design code.")
    for step in result.steps:
        pdf.check_page_space(35)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(44, 62, 80)
        ref = f"  [{step.clause_ref}]" if step.clause_ref else ""
        pdf.cell(0, 6, _sanitize(f"Step {step.step_number}: {step.description}{ref}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Courier", "", 9)
        pdf.set_text_color(107, 114, 128)
        pdf.set_x(15)
        pdf.cell(0, 5, _sanitize(f"Formula: {step.formula}"), new_x="LMARGIN", new_y="NEXT")
        if step.inputs:
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(107, 114, 128)
            inputs_str = ",  ".join(f"{k}={v}" for k, v in step.inputs.items())
            pdf.set_x(15)
            pdf.multi_cell(180, 5, _sanitize(f"Inputs:  {inputs_str}"))
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 64, 175)
        pdf.set_x(15)
        pdf.cell(0, 6, _sanitize(f"Result: {step.result:.2f} {step.unit}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    pdf.check_page_space(50)
    pdf.section_title("5. Warnings & Advisory Notes")
    if result.warnings:
        for w in result.warnings:
            pdf.warning_text(w)
        pdf.ln(2)
    else:
        pdf.body_text("No warnings were generated for this design.")
    pdf.body_text("Note: The above warnings are advisory. The designer should review each item and confirm that the final mix is validated by trial batches before use in construction.")
    pdf.add_page()
    pdf.section_title("6. Engineering Context & Glossary")
    is_aci_report = "ACI" in result.code_used
    is_doe_report = "doe" in result.code_used.lower()
    if is_aci_report:
        pdf.subsection_title("Target Mean Strength (f'cr)")
        pdf.body_text("The target mean strength f'cr is the average compressive strength that the concrete batch must achieve to ensure that the specified f'c is met with acceptable statistical confidence. Per ACI 318, f'cr is calculated using the larger of two formulas:\n  \u2022  f'cr = f'c + 1.34 \u00d7 s\n  \u2022  f'cr = f'c + 2.33 \u00d7 s \u2212 3.45 MPa\nwhere s is the standard deviation from prior test data. When no data exists, ACI 318 Table 26.4.3.1(b) provides conservative overdesign values.")
        pdf.subsection_title("Water/Cement Ratio")
        pdf.body_text("The W/C ratio is the most significant factor controlling concrete strength and durability. A lower W/C ratio produces stronger, less permeable concrete but requires more cement and may reduce workability. The W/C ratio is selected from ACI 211.1 Table 6.3.4 based on the target mean strength, then capped by durability requirements (e.g., sulfate exposure per ACI 318 Table 19.3.2).")
        pdf.subsection_title("Air Entrainment")
        pdf.body_text("Air-entrained concrete contains tiny, uniformly distributed air bubbles (typically 2\u20138%) that improve freeze\u2013thaw durability. The air content target depends on NMSA and exposure severity (ACI 211.1 Table 6.3.3). Air-entrained mixes use less water and have different W/C ratio tables.")
        pdf.subsection_title("Sulfate Exposure Classes")
        pdf.body_text("ACI 318 defines sulfate exposure classes (S0\u2013S3) based on soil and groundwater sulfate concentrations. Higher classes impose stricter W/C limits:\n  \u2022  S0: No exposure \u2014 no limit\n  \u2022  S1: Moderate \u2014 W/C \u2264 0.50\n  \u2022  S2: Severe \u2014 W/C \u2264 0.45\n  \u2022  S3: Very severe \u2014 W/C \u2264 0.40\nThese limits override the strength-based W/C ratio when more restrictive.")
    elif is_doe_report:
        pdf.subsection_title("Target Mean Strength (fm, Figure 3)")
        pdf.body_text("The target mean strength fm = fc + M with margin M = k \u00d7 s (BRE 331:1997 \u00a74.4). The multiplier k follows the allowed defective percentage (5% \u2192 1.64); s follows Figure 3 by test-cube count n (Line A n<20 / Line B n\u226520).")
        pdf.subsection_title("Free-Water/Cement Ratio (Figure 4)")
        pdf.body_text("The free-W/C ratio is read from Figure 4 curves at the target mean strength, anchored by the Table 2 reference strength at W/C = 0.5 for the cement class and aggregate type (crushed/uncrushed).")
        pdf.subsection_title("Free-Water Content (Table 3)")
        pdf.body_text("Free-water content follows Table 3 by NMSA (10/20/40 mm), aggregate type and workability class (slump or Vebe). Mixed fine/coarse types use W = 2/3 Wf + 1/3 Wc.")
        pdf.subsection_title("Wet Density & Aggregates (Figures 5–6)")
        pdf.body_text("Stage 4 estimates the wet density of fully compacted concrete from Figure 5 using the free-water content and the combined aggregate relative density at SSD (Item 4.1, known/assumed); total aggregate = D \u2212 C \u2212 W (C4). Stage 5 splits fines/coarse via Figure 6 at the % passing 600 \u00b5m.")
    else:
        pdf.subsection_title("Target Mean Strength (ftm)")
        pdf.body_text("The target mean strength ftm is calculated as:\n  ftm = fck + 1.65 \u00d7 s\nwhere fck is the characteristic compressive strength and s is the assumed standard deviation from IS 10262:2019 Table 1. This ensures that at least 95% of test results exceed fck.")
        pdf.subsection_title("Water/Cement Ratio")
        pdf.body_text("The W/C ratio determines concrete strength and durability. IS 10262 provides separate W/C ratio curves for OPC 33, OPC 43, and OPC 53 grade cements. The selected W/C is then checked against IS 456:2000 Table 3 exposure limits, which cap the W/C ratio based on environmental conditions.")
        pdf.subsection_title("Exposure Classes (IS 456:2000)")
        pdf.body_text("IS 456:2000 Table 5 defines exposure conditions that govern durability:\n  \u2022  Mild: Min 220 kg/m\u00b3 cement, W/C \u2264 0.60\n  \u2022  Moderate: Min 240 kg/m\u00b3 cement, W/C \u2264 0.60, grade M20\n  \u2022  Severe: Min 250 kg/m\u00b3 cement, W/C \u2264 0.50, grade M25\n  \u2022  Very Severe: Min 260 kg/m\u00b3 cement, W/C \u2264 0.45, grade M30\n  \u2022  Extreme: Min 280 kg/m\u00b3 cement, W/C \u2264 0.40, grade M35\nThese limits ensure adequate durability for the intended service environment.")
        pdf.subsection_title("Grading Zones")
        pdf.body_text("Fine aggregate (sand) is classified into Grading Zones I\u2013IV based on particle size distribution per IS 383. Zone II is the reference; coarser sand (Zone I) requires slightly less water, while finer sand (Zone III/IV) requires more. The water content is adjusted by \u22123% for Zone I and +3%/+6% for Zone III/IV.")
    if is_doe_report:
        pdf.subsection_title("Trial Batches (BRE 331 \u00a76)")
    elif not is_aci_report:
        pdf.subsection_title("Trial Batches (IS 10262:2019 Clause 5.8)")
    else:
        pdf.subsection_title("Trial Batches (ACI 211.1 \u00a75.3.10)")
    if "IS" in result.code_used or "10262" in result.code_used:
        wc = result.w_c_ratio
        pdf.body_text(
            f"Per IS 10262:2019 Clause 5.8, calculated proportions must be checked and adjusted using 4 trial batches:\n"
            f"  \u2022  Trial Mix 1: Initial calculated proportions (W/C = {wc:.2f}) — measure slump and inspect for segregation/bleeding and finishing properties.\n"
            f"  \u2022  Trial Mix 2: If workability differs from target, adjust water/admixture keeping W/C constant at {wc:.2f}.\n"
            f"  \u2022  Trial Mixes 3 & 4: Same water content as Trial 2 with W/C varied by \u00b110% ({wc*0.9:.2f} & {wc*1.1:.2f}) to establish the compressive strength vs. W/C relationship.\n"
            f"  \u2022  Clause 5.8.1 Reporting: Mix design report shall document testing period, structural details, material test data/brands, trial records, and recommended final proportions."
        )
    elif is_doe_report:
        pdf.body_text("BRE 331:1997 \u00a76 trial batch (0.05 m\u00b3 reference): cast six 150 mm cubes plus slump/Vebe and density tests. Check the Figure 3 margin, Figure 4 W/C and Figure 5 density against measured strength, workability and yield, then adjust water, cement or fines proportion before adoption.")
    else:
        pdf.body_text("This mix design is a theoretical starting point. Before use in construction, the designer must prepare and test trial batches to verify that target strength and workability are achieved.")
    pdf.subsection_title("Moisture Correction")
    pdf.body_text("The aggregate quantities in this report are in saturated surface-dry (SSD) condition. In practice, the actual water added must be adjusted for the moisture content and absorption of the aggregates. If the aggregates are wetter than SSD, reduce the mixing water; if drier, increase it.")
    if is_doe_report:
        pdf.subsection_title("Density Method (BRE 331 Stage 4)")
        pdf.body_text("This DOE design uses the wet-density method: the Figure 5 wet density of fully compacted concrete (from free-water content and combined aggregate relative density at SSD, Item 4.1) minus cement and water gives the total aggregate content (C4). No absolute-volume summation is used.")
    else:
        pdf.subsection_title("Volume Method")
        pdf.body_text("This design uses the absolute volume method. The volume of each ingredient (cement, water, air, aggregates) is calculated from its mass and specific gravity, and the total is verified to equal 1.0 m\u00b3. Any discrepancy is absorbed by adjusting the fine aggregate quantity.")
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
    pdf.check_page_space(40)
    pdf.section_title("Disclaimer")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.multi_cell(0, 5, "This report is generated by CivilQntify software and is intended for preliminary design and educational purposes. The designer of record is responsible for verifying all calculations, conducting trial batches, and ensuring compliance with local codes and project specifications. The software authors assume no liability for designs derived from this report.")
    return bytes(pdf.output())


# ── LaTeX generation ────────────────────────────────────────────────

def _latex_escape_si(value: str) -> str:
    return _sanitize_latex(value)


def generate_latex_source(
    result: MixDesignResult,
    input_params: dict[str, Any] | None = None,
) -> str:
    """Generate LaTeX source for the mix design report.

    Returns a complete LaTeX document (article class) that can be compiled
    with pdflatex/xelatex/lualatex. Uses booktabs for tables and xcolor for
    engineering styling.
    """
    code_label = "ACI PRC-211.1-22 (American)" if "ACI" in result.code_used else ("DOE BRE 331:1997 (British)" if "doe" in result.code_used.lower() else "IS~10262:2019 (Indian)")
    code_short = _sanitize_latex(result.code_used)
    date_str = datetime.now().strftime("%Y--%m--%d")
    is_aci = "ACI" in result.code_used
    is_doe = "doe" in result.code_used.lower()
    # Logo for LaTeX header — checked at generation time; actual file is copied in generate_pdf_report
    _logo_for_latex = _find_logo_file()
    _has_logo = _logo_for_latex is not None and _logo_for_latex.suffix.lower() in (".png", ".pdf", ".jpg", ".jpeg")

    # Helper to format numbers
    def fmt(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:.2f}"
        return _sanitize_latex(str(v))

    # Input param helpers
    ip = input_params or {}
    target_strength = ip.get("target_strength_mpa", result.target_mean_strength_mpa)
    slump = ip.get("slump_mm", "-")
    nmsa = ip.get("nmsa", "-")
    cement_type = _sanitize_latex(display_name(str(ip.get("cement_type", "-"))))
    cement_sg = ip.get("cement_sg", "-")
    fine_sg = ip.get("fine_agg_sg", "-")
    coarse_sg = ip.get("coarse_agg_sg", "-")
    fine_fm = ip.get("fine_agg_fm", "-")
    grading_zone = ip.get("fine_agg_grading_zone", "II")
    doe_p600 = ip.get("fine_agg_pct_passing_600um", "-")
    doe_rd = ip.get("aggregate_relative_density_ssd", None)
    air_entrained = "Yes" if ip.get("air_entrained") else "No"
    sulfate = _sanitize_latex(str(ip.get("sulfate_exposure_class", "S0")))
    has_data = r"$\geq$30 tests" if ip.get("has_production_data", True) else "No data ($<$30 tests)"
    exposure = _sanitize_latex(display_name(ip.get("exposure_class")) if ip.get("exposure_class") else "None specified")
    scm_pct = ip.get("scm_replacement_percent", 0)
    scm_type = _sanitize_latex(display_name(str(ip.get("scm_type", "-"))))
    adm_wr = ip.get("admixture_water_reduction", 0)
    volume = ip.get("volume_m3", result.volume_m3)

    ratio = result.mix_ratio
    mix_ratio_str = f"{ratio['cement']:.1f} : {ratio['fine_aggregate']:.1f} : {ratio['coarse_aggregate']:.1f} ({result.w_c_ratio:.3f})"

    # Warnings
    warnings_latex = ""
    if result.warnings:
        warnings_latex = "\n".join(f"\\item {_sanitize_latex(w)}" for w in result.warnings)
        warnings_latex = f"\\begin{{itemize}}[leftmargin=1.2em]\n{warnings_latex}\n\\end{{itemize}}"
    else:
        warnings_latex = "No warnings were generated for this design."

    # Steps
    steps_latex = ""
    for step in result.steps:
        inputs = ", ".join(f"{_sanitize_latex(k)}={_sanitize_latex(str(v))}" for k, v in (step.inputs or {}).items())
        inputs_line = f"\\textbf{{Inputs:}} {inputs}\\\\" if inputs else ""
        formula = _sanitize_latex(step.formula)
        # Keep formulas readable; if they contain math, wrap in \( \)
        steps_latex += f"""
\\noindent\\textbf{{Step {step.step_number}: {_sanitize_latex(step.description)}}}\\hfill\\textsf{{\\footnotesize [{_sanitize_latex(step.clause_ref)}]}}\\\\
\\texttt{{Formula: {formula}}}\\\\
{inputs_line}
\\textcolor{{accentblue}}{{\\textbf{{Result: {step.result:.2f} { _sanitize_latex(step.unit)}}}}}\\\\[0.8em]
"""

    # Engineering context per code
    if is_aci:
        context_latex = r"""
\subsection{Target Mean Strength $f'_{cr}$}
The target mean strength $f'_{cr}$ is the average compressive strength that the concrete batch must achieve to ensure that the specified $f'_c$ is met with acceptable statistical confidence. Per ACI~318, $f'_{cr}$ is the larger of:
\begin{itemize}[leftmargin=1.2em]
  \item $f'_{cr}=f'_c+1.34\times s$
  \item $f'_{cr}=f'_c+2.33\times s-3.45$ MPa
\end{itemize}
where $s$ is the standard deviation from prior test data. When no data exists, ACI~318 Table 26.4.3.1(b) provides conservative overdesign values.

\subsection{Water--Cement Ratio}
The $W/C$ ratio is the most significant factor controlling strength and durability. A lower $W/C$ produces stronger, less permeable concrete but requires more cement. The ratio is selected from ACI~211.1 Table~6.3.4 based on the target mean strength, then capped by durability (e.g., sulfate exposure per ACI~318 Table~19.3.2).

\subsection{Air Entrainment}
Air-entrained concrete contains 2--8\% uniformly distributed bubbles that improve freeze--thaw durability. The target depends on NMSA and exposure severity (ACI~211.1 Table~6.3.3).

\subsection{Sulfate Exposure Classes}
ACI~318 classes $S_0$--$S_3$: $S_0$ no exposure (no limit), $S_1$ moderate $W/C\leq0.50$, $S_2$ severe $W/C\leq0.45$, $S_3$ very severe $W/C\leq0.40$. These override the strength-based $W/C$ when more restrictive.
"""
    # (IS context lives in the trailing else branch below.)
    elif is_doe:
        context_latex = r"""
\subsection{Target Mean Strength $f_m$ (Figure 3)}
The target mean strength is $f_m=f_c+M$ with margin $M=k\times s$ (BRE~331:1997 \S4.4). The multiplier $k$ follows the allowed defective percentage (5\% $\to$ 1.64); $s$ follows Figure~3 by test-cube count $n$ (Line~A $n<20$ / Line~B $n\ge20$), for any grade.

\subsection{Free-Water/Cement Ratio (Figure 4)}
The free-W/C ratio is read from the Figure~4 curves at the target mean strength, anchored by the Table~2 reference strength at W/C $=0.5$ for the cement class and aggregate type (crushed/uncrushed).

\subsection{Free-Water Content (Table 3)}
Free-water content follows Table~3 by NMSA (10/20/40~mm), aggregate type and workability class (slump or Vebe). Mixed fine/coarse types use $W=2/3\,W_f+1/3\,W_c$.

\subsection{Wet Density \& Aggregates (Figures 5--6)}
Stage~4 estimates the wet density of fully compacted concrete from Figure~5 using the free-water content and the combined aggregate relative density at SSD (Item~4.1, known/assumed); total aggregate $=D-C-W$ (C4). Stage~5 splits fines/coarse via Figure~6 at the percentage passing 600~$\mu$m.
"""
    else:
        context_latex = r"""
\subsection{Target Mean Strength $f_{tm}$}
The target mean strength is $f_{tm}=f_{ck}+1.65\times s$ where $f_{ck}$ is the characteristic strength and $s$ is the assumed standard deviation from IS~10262:2019 Table~1. This ensures $\geq$95\% of test results exceed $f_{ck}$. Where $X$ per Table~1 governs, $f'_{ck}=f_{ck}+X$ is used and the larger value adopted.

\subsection{Water--Cement Ratio}
IS~10262 provides $W/C$ curves for OPC~33/43/53. The selected $W/C$ is checked against IS~456:2000 Table~5 exposure limits which cap the ratio by environment.

\subsection{Exposure Classes (IS~456:2000)}
Mild: min 220 kg/m\textsuperscript{3}, $W/C\leq0.60$; Moderate: 240 kg/m\textsuperscript{3}, $W/C\leq0.60$, M20; Severe: 250 kg/m\textsuperscript{3}, $W/C\leq0.50$, M25; Very Severe: 260 kg/m\textsuperscript{3}, $W/C\leq0.45$, M30; Extreme: 280 kg/m\textsuperscript{3}, $W/C\leq0.40$, M35.

\subsection{Grading Zones}
Fine aggregate Zones I--IV per IS~383. Zone~II is reference; Zone~I $-3$\% water, Zone~III $+3$\%, Zone~IV $+6$\%.
"""

    # Cost/carbon
    cost_latex = ""
    if result.cost_per_m3 is not None or result.carbon_kg_co2_per_m3 is not None:
        cost_latex = r"\section{Cost \& Carbon Estimates}" + "\n"
        if result.cost_per_m3 is not None:
            cost_latex += f"Estimated cost: \\textbf{{{result.cost_per_m3:.2f} per m\\textsuperscript{{3}}}} \\\\\n"
        if result.carbon_kg_co2_per_m3 is not None:
            cost_latex += f"Embodied carbon: \\textbf{{{result.carbon_kg_co2_per_m3:.1f} kg CO\textsubscript{{2}}/m\\textsuperscript{{3}}}} \\\\\n"
        if result.volume_m3 != 1.0 and result.cost_per_m3 is not None:
            cost_latex += f"Total cost ({result.volume_m3:.1f} m\\textsuperscript{{3}}): \\textbf{{{result.cost_per_m3 * result.volume_m3:.2f}}} \\\\\n"

    # Pre-computed outside the f-string below: Python < 3.12 forbids
    # backslashes inside f-string expression parts, and these LaTeX
    # fragments are full of them.
    if is_doe:
        trial_latex = (
            "\\subsection{Trial Batches (BRE 331:1997 \\S6)}\n"
            "BRE~331 \\S6 trial batch (0.05~m\\textsuperscript{3} reference): cast six "
            "150~mm cubes plus slump/Vebe and density tests. Check the Figure~3 margin, "
            "Figure~4 W/C and Figure~5 density against measured strength, workability and "
            "yield, then adjust water, cement or fines proportion before adoption.\n"
        )
        method_latex = (
            "\\subsection{Density Method (BRE 331 Stage 4)}\n"
            "This DOE design uses the wet-density method: the Figure~5 wet density of fully "
            "compacted concrete (from free-water content and combined aggregate relative "
            "density at SSD, Item~4.1) minus cement and water gives the total aggregate "
            "content (C4). No absolute-volume summation is used.\n"
        )
    elif is_aci:
        trial_latex = (
            "\\subsection{Trial Batches (ACI 211.1 \\S5.3.10)}\n"
            "This mix design is a theoretical starting point. Before use in construction, "
            "prepare and test trial batches to verify that target strength and workability "
            "are achieved (yield check per ASTM~C138).\n"
        )
        method_latex = (
            "\\subsection{Volume Method}\n"
            "The absolute volume method is used. The volume of each ingredient (cement, "
            "water, air, aggregates) is calculated from its mass and specific gravity; the "
            "total is verified to equal 1.0 m\\textsuperscript{3}. Any discrepancy is "
            "absorbed by the fine aggregate.\n"
        )
    else:
        trial_latex = (
            "\\subsection{Trial Batches (IS 10262:2019 Clause 5.8)}\n"
            "This mix design provides theoretical baseline proportions. Per "
            "\\textbf{IS 10262:2019 Clause 5.8}, the calculated proportions must be "
            "validated using 4 trial batches:\n"
            "\\begin{itemize}\n"
            f"  \\item \\textbf{{Trial Mix 1}}: Initial calculated proportions (W/C $= {result.w_c_ratio:.2f}$) --- test slump/flow, observe freedom from segregation and bleeding, and check surface finish.\n"
            f"  \\item \\textbf{{Trial Mix 2}}: If measured workability differs from target, adjust water and/or admixture while holding free W/C constant at ${result.w_c_ratio:.2f}$.\n"
            f"  \\item \\textbf{{Trial Mixes 3 \\& 4}}: Same water content with W/C varied by $\\pm 10\\%$ (${result.w_c_ratio*0.90:.2f}$ \\& ${result.w_c_ratio*1.10:.2f}$) to plot the compressive strength vs.~W/C curve.\n"
            "  \\item \\textbf{Clause 5.8.1 Reporting}: The final report shall document testing period, project details, material test data/brands, trial records, and recommended final proportions.\n"
            "\\end{itemize}\n"
        )
        method_latex = (
            "\\subsection{Volume Method}\n"
            "The absolute volume method is used. The volume of each ingredient (cement, "
            "water, air, aggregates) is calculated from its mass and specific gravity; the "
            "total is verified to equal 1.0 m\\textsuperscript{3}. Any discrepancy is "
            "absorbed by the fine aggregate.\n"
        )
    if _has_logo:
        header_block = (
            "\\noindent\\begin{minipage}[c]{0.18\\textwidth}"
            "\\includegraphics[width=\\linewidth]{logo.png}\\end{minipage}\\hfill"
            "\\begin{minipage}[c]{0.80\\textwidth}"
            "{\\color{accentblue}\\LARGE\\textbf{CivilQntify}}\\\\[0.2em]"
            "{\\color{graytext}\\small Concrete Mix Design Report \\;|\\; "
            + code_short + " \\;|\\; " + date_str + "}"
            "\\end{minipage}\\\\[0.6em]"
            "\\noindent\\textcolor{accentblue}{\\rule{\\textwidth}{0.6pt}}\\\\[1.2em]"
        )
    else:
        header_block = (
            "\\noindent{\\color{accentblue}\\LARGE\\textbf{CivilQntify}}\\\\[0.3em]"
            "{\\color{graytext}\\small Concrete Mix Design Report \\;|\\; "
            + code_short + " \\;|\\; " + date_str + "}"
            "\\\\[0.6em]"
            "\\noindent\\textcolor{accentblue}{\\rule{\\textwidth}{0.6pt}}\\\\[1.2em]"
        )
    volume_note = (
        "The total volume requested is \\textbf{"
        + f"{result.volume_m3:.1f} m\\textsuperscript{{3}}"
        + "}. All quantities below are shown per cubic metre and as total batch amounts."
    ) if result.volume_m3 != 1.0 else ""

    latex = f"""\\documentclass[a4paper,11pt]{{article}}
\\usepackage[margin=2cm]{{geometry}}
\\usepackage{{xcolor}}
\\usepackage{{booktabs}}
\\usepackage{{amsmath,amsfonts,amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}
\\usepackage{{enumitem}}
\\usepackage{{microtype}}
\\usepackage{{lmodern}}
\\usepackage{{helvet}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}

\\definecolor{{accentblue}}{{RGB}}{{30,64,175}}
\\definecolor{{graytext}}{{RGB}}{{107,114,128}}
\\definecolor{{darktext}}{{RGB}}{{44,62,80}}
\\hypersetup{{colorlinks=true,linkcolor=accentblue,urlcolor=accentblue}}

\\setlength{{\\parskip}}{{0.6em}}
\\setlength{{\\parindent}}{{0em}}

\\begin{{document}}

% ── Header ──────────────────────────────────────────────────────────
{header_block}

% ── 1. Executive Summary ───────────────────────────────────────────
\\section{{Executive Summary}}
This report presents a concrete mix design performed in accordance with {code_label}. The design targets a characteristic compressive strength of \\textbf{{{_sanitize_latex(str(target_strength))} MPa}} with a water--cement ratio of \\textbf{{{result.w_c_ratio:.3f}}} and a target mean strength of \\textbf{{{result.target_mean_strength_mpa:.1f} MPa}}.
{volume_note}

% ── 2. Input Parameters ────────────────────────────────────────────
\\section{{Input Parameters}}
"""
    if input_params:
        latex += f"""
\\begin{{center}}
\\small
\\begin{{tabular}}{{ll}}
\\toprule
\\textbf{{Parameter}} & \\textbf{{Value}} \\\\
\\midrule
Code & {code_label} \\\\
Target strength ($f'_c$/$f_{{ck}}$) & { _sanitize_latex(str(target_strength)) } MPa \\\\
Slump & { _sanitize_latex(str(slump)) } mm \\\\
NMSA & { _sanitize_latex(str(nmsa)) } mm \\\\
Cement type & {cement_type} \\\\
Cement SG & { _sanitize_latex(str(cement_sg)) } \\\\
Fine aggregate SG & { _sanitize_latex(str(fine_sg)) } \\\\
"""
        if is_aci:
            latex += f"Fine aggregate FM & {_sanitize_latex(str(fine_fm))} \\\\\n"
        elif is_doe:
            latex += f"Fine aggregate passing 600 $\\mu$m & {_sanitize_latex(str(doe_p600))}\\% \\\\\n"
        else:
            latex += f"Grading zone & Zone {_sanitize_latex(str(grading_zone))} \\\\\n"
        latex += f"""Coarse aggregate SG & {_sanitize_latex(str(coarse_sg))} \\\\
"""
        if is_doe:
            _rd_tex = f"{doe_rd:.2f} (known)" if doe_rd else "Auto (mean of FA/CA SG)"
            latex += f"Combined RD, SSD (Item 4.1) & {_sanitize_latex(_rd_tex)} \\\\\n"
        if is_aci:
            latex += f"""Air-entrained & {air_entrained} \\\\\n"""
        elif is_doe:
            _n_tex = _sanitize_latex(str(ip.get("num_test_cubes", ip.get("n_cubes", "--"))))
            latex += f"""Defective percent & {_sanitize_latex(str(ip.get("defective_percent", 5.0)))}\\% \\\\\nTest cubes, $n$ (Figure 3) & {_n_tex} \\\\\nTest age & {_sanitize_latex(str(ip.get("age_days", 28)))} days \\\\\nEntrained air (\\S8) & {_sanitize_latex(str(ip.get("air_pct", 0.0)))}\\% \\\\\n"""
        else:
            latex += f"""Exposure class (IS 456) & {exposure} \\\\\n"""
        if is_aci:
            latex += f"Sulfate class & {sulfate} \\\\\nProduction data & {has_data} \\\\\n"
        if scm_pct and scm_pct > 0:
            latex += f"SCM type & {scm_type} \\\\\nSCM replacement & {scm_pct:.1f}\\% \\\\\n"
        if adm_wr and adm_wr > 0:
            latex += f"Admixture water reduction & {adm_wr:.1f}\\% \\\\\n"
        latex += f"Target volume & {volume:.1f} m\\textsuperscript{{3}} \\\\\n\\bottomrule\n\\end{{tabular}}\n\\end{{center}}\n"
    else:
        latex += r"\textit{(Input parameters were not recorded for this calculation.)}" + "\n"

    latex += f"""
% ── 3. Material Quantities ─────────────────────────────────────────
\\section{{Material Quantities}}
\\subsection*{{Proportions per Cubic Metre}}
\\begin{{center}}
\\begin{{tabular}}{{l r}}
\\toprule
\\textbf{{Constituent}} & \\textbf{{Quantity}} \\\\
\\midrule
Cement & {result.cement_kg:.1f} kg/m\\textsuperscript{{3}} \\\\
"""
    if result.scm_kg > 0:
        latex += f"SCM & {result.scm_kg:.1f} kg/m\\textsuperscript{{3}} \\\\\nTotal cementitious & {result.total_cementitious_kg:.1f} kg/m\\textsuperscript{{3}} \\\\\n"
    latex += f"""Water & {result.water_kg:.1f} kg/m\\textsuperscript{{3}} \\\\
Fine aggregate (sand) & {result.fine_aggregate_kg:.1f} kg/m\\textsuperscript{{3}} \\\\
Coarse aggregate & {result.coarse_aggregate_kg:.1f} kg/m\\textsuperscript{{3}} \\\\
Total aggregate & {result.total_aggregate_kg:.1f} kg/m\\textsuperscript{{3}} \\\\
\\midrule
Water--cement ratio & {result.w_c_ratio:.3f} \\\\
Target mean strength ($f'_{{cr}} / f_{{tm}}$) & {result.target_mean_strength_mpa:.1f} MPa \\\\
Air content & {result.air_volume_percent:.1f}\\% \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\vspace{{1em}}
\\noindent\\textbf{{Mix ratio (Cement : Fine : Coarse) :}} { _sanitize_latex(mix_ratio_str) }\\\\
{{\\small The ratio is normalised to cement $=$ 1; water appears as $W/C$.}}

"""
    if result.volume_m3 != 1.0:
        v = result.volume_m3
        latex += f"""
\\subsection*{{Total Batch Quantities ({v:.1f} m\\textsuperscript{{3}})}}
\\begin{{center}}
\\begin{{tabular}}{{l r}}
\\toprule
Cement & {result.cement_kg * v:.1f} kg \\\\
"""
        if result.scm_kg > 0:
            latex += f"SCM & {result.scm_kg * v:.1f} kg \\\\\n"
        latex += f"""Water & {result.water_kg * v:.1f} kg \\\\
Fine aggregate & {result.fine_aggregate_kg * v:.1f} kg \\\\
Coarse aggregate & {result.coarse_aggregate_kg * v:.1f} kg \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}
"""

    latex += f"""
% ── 4. Calculation Steps ───────────────────────────────────────────
\\section{{Calculation Steps}}
{{\\small Each step shows the formula, inputs and result. Clause references point to the design code.}}\\\\[0.6em]
{steps_latex}

% ── 5. Warnings ────────────────────────────────────────────────────
\\section{{Warnings \\& Advisory Notes}}
{warnings_latex}

{{\\small The above warnings are advisory. The designer must verify the final mix by trial batches before construction.}}

% ── 6. Engineering Context ─────────────────────────────────────────
\\section{{Engineering Context \\& Glossary}}
{context_latex}
{trial_latex}
\\subsection{{Moisture Correction}}
Aggregate quantities are in saturated surface-dry (SSD) condition. In practice the mixing water must be adjusted for the aggregates' moisture content and absorption. If aggregates are wetter than SSD, reduce water; if drier, increase it.

{method_latex}
{cost_latex}
% ── 8. Disclaimer ─────────────────────────────────────────────────
\\section*{{Disclaimer}}
{{\\small\\itshape This report is generated by CivilQntify software and is intended for preliminary design and educational purposes. The designer of record is responsible for verifying all calculations, conducting trial batches, and ensuring compliance with local codes and project specifications. The software authors assume no liability for designs derived from this report.}}

\\end{{document}}
"""
    return latex


def _find_latex_engine() -> str | None:
    """Return the first available LaTeX engine, or None."""
    for engine in ("pdflatex", "xelatex", "lualatex"):
        if shutil.which(engine):
            return engine
    return None


def generate_pdf_report(
    result: MixDesignResult,
    input_params: dict[str, Any] | None = None,
) -> bytes:
    """Generate a PDF mix design report via LaTeX (with fpdf2 fallback).

    The function first generates LaTeX source and attempts to compile it
    with pdflatex/xelatex/lualatex. If no engine is available or compilation
    fails, it falls back to the original fpdf2 implementation so the call
    never fails in headless/CI environments.

    Returns:
        PDF file content as bytes
    """
    # Try LaTeX path
    try:
        latex_src = generate_latex_source(result, input_params)
        engine = _find_latex_engine()
        if engine is not None:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Copy logo for LaTeX includegraphics (if header expects logo.png)
                if "includegraphics" in latex_src:
                    src_logo = _find_logo_file()
                    if src_logo is not None and src_logo.is_file():
                        try:
                            dst = pathlib.Path(tmpdir) / "logo.png"
                            # Keep PNG/JPG as-is; SVG not supported by pdflatex — skip
                            if src_logo.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf"):
                                import shutil as _shutil
                                _shutil.copyfile(src_logo, dst)
                            elif src_logo.suffix.lower() == ".svg":
                                # SVG not natively supported — skip logo for LaTeX path
                                latex_src = latex_src.replace("\\includegraphics[width=\\linewidth]{logo.png}", "")
                        except Exception:
                            pass
                tex_path = os.path.join(tmpdir, "report.tex")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(latex_src)
                # Run twice for references
                for _ in range(2):
                    proc = subprocess.run(
                        [engine, "-interaction=nonstopmode", "-halt-on-error", "report.tex"],
                        cwd=tmpdir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(f"{engine} failed: {proc.stdout.decode(errors='replace')[-2000:]}")
                pdf_path = os.path.join(tmpdir, "report.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
                raise FileNotFoundError("LaTeX compiled but report.pdf not found")
    except Exception as exc:
        # Fall through to fpdf2; keep a breadcrumb for debugging if needed
        # (do not raise — the caller expects PDF bytes)
        try:
            # Optional: log to stderr in debug builds
            import sys
            print(f"[CivilQntify] LaTeX PDF generation failed ({exc}), falling back to fpdf2", file=sys.stderr)
        except Exception:
            pass

    # Fallback: original fpdf2
    return _generate_pdf_via_fpdf(result, input_params)


# Keep the original name for backward-compat; also expose LaTeX source
__all__ = ["generate_pdf_report", "generate_latex_source", "_generate_pdf_via_fpdf"]
