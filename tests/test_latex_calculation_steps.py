"""Tests for LaTeX calculation steps on frontend and PDF/report exports."""

from __future__ import annotations

import json
import pytest
from PyQt6.QtWidgets import QApplication

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.engine.proportioner import design_mix
from concrete_mix.engine.target_strength import calculate_target_strength
from concrete_mix.export.json_export import export_to_json
from concrete_mix.export.pdf_report import _generate_pdf_via_fpdf, generate_latex_source, generate_pdf_report
from concrete_mix.export.text_report import generate_report
from concrete_mix.models.materials import FineAggregate
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult
from app.widgets.concrete_tab import ConcreteMixTab
from app.widgets.history_detail_dialog import HistoryDetailDialog
from app.widgets.result_panel import ResultPanel, TargetStrengthResultPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_calculation_step_latex_auto_generation():
    """CalculationStep should auto-generate formula_latex if not provided."""
    step = CalculationStep(
        step_number=1,
        description="Target strength",
        formula="f'ck = 30.0 + 1.65 × 5.0 = 38.25 MPa",
        inputs={"fck": 30.0, "s": 5.0},
        result=38.25,
        unit="MPa",
        clause_ref="IS 10262:2019 Cl. 4.2",
    )
    assert step.formula_latex != ""
    assert "$" in step.formula_latex
    assert r"\times" in step.formula_latex
    assert step.latex == step.formula_latex


def test_calculation_step_custom_latex_preserved():
    """Explicit formula_latex overrides default translation."""
    custom = r"$f'_{ck} = f_{ck} + 1.65\sigma$"
    step = CalculationStep(
        step_number=1,
        description="Target strength",
        formula="f'ck = 30.0 + 1.65 × 5.0 = 38.25 MPa",
        inputs={},
        result=38.25,
        unit="MPa",
        formula_latex=custom,
    )
    assert step.formula_latex == custom
    assert step.latex == custom


@pytest.mark.parametrize("code", ["is10262", "aci211", "doe"])
def test_all_codes_generate_latex_steps(code):
    """Engine proportioning for all 3 codes must populate step.latex."""
    inp = MixDesignInput(
        code=code,
        target_strength_mpa=30.0,
        slump_mm=50.0,
        fine_aggregate=FineAggregate(pct_passing_600um=50.0),
    )
    result = design_mix(inp)
    assert len(result.steps) > 0
    for s in result.steps:
        assert isinstance(s.latex, str)
        assert len(s.latex) > 0
        # If formula has math/operators/numbers, latex should wrap in math mode or translate symbols
        if any(ch in s.formula for ch in "=+-*/×÷"):
            assert "$" in s.latex or "\\" in s.latex


@pytest.mark.parametrize("code", ["is10262", "aci211", "doe"])
def test_target_strength_result_latex(code):
    """TargetStrengthResult generates formula_latex and latex."""
    ts = calculate_target_strength(code, 35.0)
    assert ts.formula_latex != ""
    assert ts.latex == ts.formula_latex


def test_result_panel_steps_tree_latex(qapp):
    """ResultPanel steps tree must display calculation in LaTeX format."""
    panel = ResultPanel()
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)
    panel.display_result(result)

    tree = panel._steps_tree
    # Check header
    assert tree.headerItem().text(2) == "Calculation (LaTeX)"

    # Check top level items
    assert tree.topLevelItemCount() == len(result.steps)
    for i, step in enumerate(result.steps):
        item = tree.topLevelItem(i)
        assert item.text(2) == step.latex
        assert item.toolTip(2) == step.latex


def test_target_strength_panel_latex(qapp):
    """TargetStrengthResultPanel typesets the working, not shows source."""
    panel = TargetStrengthResultPanel()
    ts = calculate_target_strength("is10262", 30.0)
    panel.display_result(ts)

    label_html = panel._formula_label.text()
    # The maths is rendered to inline images — no raw $...$ LaTeX source.
    assert "data:image/png;base64," in label_html
    assert "$" not in label_html
    assert ts.standard_name in label_html


def test_target_strength_panel_falls_back_when_render_fails(qapp, monkeypatch):
    """When the raster cannot be produced the LaTeX source stays visible."""
    import html as html_lib

    from concrete_mix.utils import latex_math

    monkeypatch.setattr(latex_math, "fragment_html", lambda *a, **k: "")
    panel = TargetStrengthResultPanel()
    ts = calculate_target_strength("is10262", 30.0)
    panel.display_result(ts)

    label_html = panel._formula_label.text()
    assert "font-family:monospace" in label_html
    assert html_lib.escape(ts.latex) in label_html


def test_concrete_tab_html_report_latex(qapp):
    """HTML report preview must typeset the calculation steps."""
    tab = ConcreteMixTab()
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)
    tab._last_result = result
    html = tab._generate_mix_report_html()

    assert "Calculation (LaTeX)" in html
    # Maths runs are embedded as inline PNG images; the raw LaTeX source is
    # not shown.
    assert "data:image/png;base64," in html
    for step in result.steps:
        assert step.description in html
        assert step.latex not in html


def test_concrete_tab_html_report_falls_back_to_source(qapp, monkeypatch):
    """If the raster fails the report cell shows the LaTeX source, not blank."""
    import html as html_lib

    from concrete_mix.utils import latex_math

    monkeypatch.setattr(latex_math, "fragment_html", lambda *a, **k: "")
    tab = ConcreteMixTab()
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)
    tab._last_result = result
    html = tab._generate_mix_report_html()

    assert "font-family:monospace;" in html
    for step in result.steps:
        assert html_lib.escape(step.latex) in html


def test_history_detail_dialog_latex(qapp):
    """HistoryDetailDialog steps table must show Calculation (LaTeX)."""
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)

    # Convert to serialized dict representation as stored in SQLite
    from history.serializers import _model_dict
    res_dict = _model_dict(result)

    rec = {
        "id": 1,
        "tab_type": "mix_design",
        "calculation_type": "mix_design",
        "name": "Test Mix",
        "code_used": "IS 10262:2019",
        "created_at": "2026-01-01T00:00:00",
        "input_json": json.dumps({"target_strength_mpa": 30.0}),
        "result_json": json.dumps(res_dict),
    }

    dlg = HistoryDetailDialog(rec)
    # Find table widget in dialog
    from PyQt6.QtWidgets import QTableWidget
    from app.widgets.latex_delegate import MathDelegate

    tables = dlg.findChildren(QTableWidget)
    assert len(tables) >= 1
    steps_table = tables[0]
    assert steps_table.horizontalHeaderItem(2).text() == "Calculation (LaTeX)"
    # The Calculation column must be painted by the maths delegate, so the
    # LaTeX is typeset rather than shown as source text.
    assert isinstance(steps_table.itemDelegateForColumn(2), MathDelegate)
    for i, step in enumerate(result.steps):
        assert steps_table.item(i, 2).text() == step.latex
        assert steps_table.item(i, 2).toolTip() == step.latex


def test_result_panel_steps_delegate_typesets(qapp):
    """The result panel's steps tree must paint column 2 with the delegate."""
    from PyQt6.QtWidgets import QStyleOptionViewItem

    from app.widgets.latex_delegate import MathDelegate

    panel = ResultPanel()
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    panel.display_result(design_mix(inp))

    delegate = panel._steps_tree.itemDelegateForColumn(2)
    assert isinstance(delegate, MathDelegate)

    # A populated cell reports the raster's size — proof the maths is drawn
    # rather than elided as plain text.
    index = panel._steps_tree.model().index(0, 2)
    option = QStyleOptionViewItem()
    option.font = panel._steps_tree.font()
    size = delegate.sizeHint(option, index)
    assert size.width() > 0
    assert size.height() > 0


def test_math_delegate_scales_to_font_em_not_line_height(qapp):
    """The delegate draws maths at the font's em size.

    Regression: scaling by the font's line height inflated the maths ~1.4x,
    and a pixel-sized font (the app stylesheet sets ``font-size: 13px``) made
    ``pointSizeF()`` return ``-1`` and skip scaling entirely, drawing the
    maths at its raw 200-DPI size — about twice the row text.
    """
    from PyQt6.QtGui import QFont, QFontInfo
    from PyQt6.QtWidgets import QStyleOptionViewItem

    from app.widgets.latex_delegate import _RENDER_DPI, _RENDER_POINTS, MathDelegate

    delegate = MathDelegate(None, column=2)
    raster_em_px = _RENDER_POINTS * _RENDER_DPI / 72.0

    pixel_font = QFont()
    pixel_font.setPixelSize(13)
    option = QStyleOptionViewItem()
    option.font = pixel_font
    assert delegate._scale(option) == pytest.approx(13.0 / raster_em_px)

    point_font = QFont()
    point_font.setPointSizeF(10.0)
    option.font = point_font
    em_px = QFontInfo(point_font).pixelSize()
    assert em_px > 0
    assert delegate._scale(option) == pytest.approx(em_px / raster_em_px)


def test_fragment_html_typesets_math_and_keeps_prose():
    """The HTML composer embeds maths as images and leaves prose as text."""
    from concrete_mix.utils import latex_math

    out = latex_math.fragment_html(r"W = $\frac{2}{3} \times 160$ kg")

    assert "data:image/png;base64," in out
    assert "W =" in out
    assert "kg" in out
    assert "$" not in out


def test_fragment_html_empty_or_oversized_returns_empty():
    """Nothing drawable is an empty string, never partial maths."""
    from concrete_mix.utils import latex_math

    assert latex_math.fragment_html("") == ""
    assert latex_math.fragment_html("   ") == ""
    oversized = "x" * (latex_math.MAX_FORMULA_CHARS + 1)
    assert latex_math.fragment_html(oversized) == ""


def test_fragment_html_keeps_unparsable_math_visible():
    """A maths run mathtext rejects stays visible as escaped source."""
    from concrete_mix.utils import latex_math

    out = latex_math.fragment_html(r"bad $\frac{1}{$ here")

    assert "data:image/png;base64," not in out
    assert "bad" in out
    assert "here" in out


def test_fragment_html_bakes_images_at_display_size():
    """Inline maths rasters must be baked at the attribute size.

    Qt rescales an ``<img>`` with a fast filter when the attributes differ
    from the intrinsic image size, which drops sub-pixel ink — a lone ``=``
    used to render as a blank gap. Baking at display size keeps the drawn
    size identical to the raster's own pixels.
    """
    import base64
    import io
    import re

    from concrete_mix.utils import latex_math

    out = latex_math.fragment_html(r"FA volume $=$ total $-$ CA volume", fontsize=9)
    matches = re.findall(
        r'src="data:image/png;base64,([A-Za-z0-9+/=]+)" '
        r'width="(\d+)" height="(\d+)"',
        out,
    )
    assert len(matches) == 2  # the "=" and the "-" runs
    for payload, attr_w, attr_h in matches:
        png = base64.b64decode(payload)
        assert latex_math.png_dimensions(png) == (int(attr_w), int(attr_h))


def test_pdf_report_exports_latex_format():
    """PDF exports (FPDF and LaTeX source) must export LaTeX format calculation steps."""
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)

    # 1. LaTeX source
    source = generate_latex_source(result)
    assert r"\textbf{Calculation (LaTeX):}" in source
    for step in result.steps:
        assert step.latex in source

    # 2. FPDF fallback export
    pdf_bytes = _generate_pdf_via_fpdf(result)
    assert pdf_bytes.startswith(b"%PDF")
    # Verify generate_pdf_report also succeeds
    full_pdf = generate_pdf_report(result)
    assert full_pdf.startswith(b"%PDF")


def test_pdf_fallback_typesets_formula_images():
    """The fpdf2 fallback embeds one rendered image per calculation step.

    fpdf2 has no maths engine, so the fallback must embed the same Computer
    Modern rasters the app paints rather than printing the LaTeX source.
    Each PNG contributes an image XObject plus a soft mask object.
    """
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)

    pdf_bytes = _generate_pdf_via_fpdf(result)

    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.count(b"/Subtype /Image") >= len(result.steps)


def test_formula_image_sized_for_print():
    """A working rasterises to PNG bytes drawn at report body-text size."""
    from concrete_mix.export import pdf_report

    image = pdf_report._render_formula_image(r"$W = \frac{2}{3} \times 160$ kg")

    assert image is not None
    png, width_mm, height_mm = image
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert 0 < width_mm <= pdf_report._FORMULA_MAX_WIDTH_MM
    assert 0 < height_mm <= pdf_report._FORMULA_MAX_HEIGHT_MM


def test_pdf_fallback_keeps_text_when_render_fails(monkeypatch):
    """A fragment mathtext cannot draw still yields a valid PDF."""
    from concrete_mix.export import pdf_report

    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)
    monkeypatch.setattr(pdf_report, "_render_formula_image", lambda formula: None)

    pdf_bytes = pdf_report._generate_pdf_via_fpdf(result)

    assert pdf_bytes.startswith(b"%PDF")


def test_json_and_text_exports_include_latex():
    """JSON and text exports include LaTeX format."""
    inp = MixDesignInput(code="is10262", target_strength_mpa=30.0, slump_mm=50.0)
    result = design_mix(inp)

    # JSON export
    json_str = export_to_json(result)
    data = json.loads(json_str)
    assert "calculation_steps" in data
    for i, s in enumerate(data["calculation_steps"]):
        assert "formula_latex" in s
        assert s["formula_latex"] == result.steps[i].latex

    # Text report
    txt = generate_report(result, inp)
    assert "Calculation (LaTeX):" in txt
