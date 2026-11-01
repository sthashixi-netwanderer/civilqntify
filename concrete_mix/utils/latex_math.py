"""LaTeX conversion and rasterisation for calculation-step formulas.

CivilQntify records every mix-design calculation as a hand-written ASCII string
(``W = 2/3x160 + 1/3x190``). Those strings are shown to the user and exported to
PDF, where they read as ``2/3x160`` rather than the standard's typeset
fraction.

This module turns a formula into real LaTeX, and rasterises it with
matplotlib's ``mathtext`` so the PyQt surfaces can display it without a TeX
installation being present.

Entry points:
    :func:`segments`        - split a *formula* into prose and maths runs.
    :func:`to_latex`        - a LaTeX fragment, maths wrapped in ``$...$``.
    :func:`fragment_runs`   - the inverse: split a *fragment* into runs.
    :func:`render_png`      - PNG bytes for the PyQt surfaces (Computer Modern).
    :func:`render_data_uri` - the same raster as a ``data:`` URI, for HTML.
    :func:`fragment_html`   - a fragment as HTML: prose as text, maths as images.

Formulas are *mixed* prose and maths (``From Table 7: nmsa=20``), so the
converter works run by run and never assumes the whole string is an equation.
The LaTeX escaping helpers moved here from ``export/pdf_report.py`` so that
prose and maths share one set of rules.
"""

from __future__ import annotations

import base64
import functools
import html
import io
import re
import struct
from typing import Final

# mathtext parses at roughly 1.4 ms per character, so a long formula — which a
# hand-edited history import can carry — would stall the GUI thread for
# seconds. Past this length a formula is treated as plain text, never maths.
MAX_FORMULA_CHARS: Final = 512

__all__ = [
    "MAX_FORMULA_CHARS",
    "escape_latex",
    "sanitize_latex",
    "segments",
    "fold_math",
    "to_latex",
    "fragment_runs",
    "fragment_html",
    "png_dimensions",
    "render_png",
    "render_data_uri",
]


# ── LaTeX escaping (moved verbatim from export/pdf_report.py) ───────────────

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
    "σ": r"$\sigma$",
    "π": r"$\pi$",
    "³": r"$^{3}$",
    "²": r"$^{2}$",
    "≥": r"$\geq$",
    "≤": r"$\leq$",
    "×": r"$\times$",
    "−": r"$-$",
    "–": "--",
    "—": "---",
    "•": r"$\bullet$",
    "‘": "'",
    "’": "'",
    "“": "``",
    "”": "''",
    "₂": r"$_{2}$",
    "₁": r"$_{1}$",
    "₀": r"$_{0}$",
}


def escape_latex(text: str) -> str:
    """Escape untrusted text once, never recognize caller-supplied TeX.

    Only our fixed Unicode replacements contain trusted math. Insert them
    character-by-character so their commands are neither re-escaped nor
    confused with user-controlled placeholder strings.

    Args:
        text: Untrusted text, typically a user-entered material name.

    Returns:
        The text with every LaTeX special character neutralised.
    """
    return "".join(_LATEX_UNICODE.get(char, _LATEX_ESCAPES.get(char, char))
                   if ord(char) >= 32 else " " for char in str(text))


def sanitize_latex(text: str | None) -> str:
    """Escape ``text`` for LaTeX output, tolerating ``None``.

    Args:
        text: Untrusted text, or ``None``.

    Returns:
        The escaped text, or an empty string when ``text`` is ``None``.
    """
    return escape_latex(text) if text is not None else ""


# ── Splitting a formula into prose and maths ───────────────────────────────

# A whitespace-delimited token is mathematical when it carries one of these.
# Purely alphabetic words ("From", "Table", "uncrushed") stay prose.
_MATH_CHARS: Final = frozenset("=+-*/^()<>%&|×÷−±≥≤→~_'σπρΔ")

_WORD_RE: Final = re.compile(r"^[A-Za-z][A-Za-z]*$")

_TEXT: Final = "text"
_MATH: Final = "math"


def segments(formula: str) -> list[tuple[str, str]]:
    """Split a formula into alternating prose and maths runs.

    Formulas in this project are frequently a mixture of both — ``"From Table 7:
    nmsa=20, agg=uncrushed"`` — so the maths is typeset and the prose is left
    alone rather than forcing the whole string into a maths mode that would
    render the English words in italics.

    Args:
        formula: A step's ``formula`` string.

    Returns:
        ``(kind, payload)`` pairs where ``kind`` is ``"text"`` or ``"math"``.
        Whitespace is preserved in the payloads.
    """
    runs: list[tuple[str, str]] = []
    for chunk in re.split(r"(\s+)", str(formula)):
        if not chunk:
            continue
        if not chunk.strip():
            runs.append((_TEXT, chunk))
            continue
        core = chunk.strip(".,;:()[]")
        is_math = (
            (any(ch.isdigit() for ch in core)
             or any(ch in _MATH_CHARS for ch in core))
            and not _WORD_RE.match(core)
        )
        runs.append((_MATH if is_math else _TEXT, chunk))

    # Whitespace carries no kind of its own: it must not split "a + b" into
    # three maths runs, so it is held back and folded into whichever run it
    # ends up adjoining.
    merged: list[tuple[str, str]] = []
    pending: list[str] = []
    for kind, payload in runs:
        if not payload.strip():
            pending.append(payload)
            continue
        gap = "".join(pending)
        pending = []
        if merged and merged[-1][0] == kind:
            merged[-1] = (kind, merged[-1][1] + gap + payload)
        else:
            if gap and merged:
                merged[-1] = (merged[-1][0], merged[-1][1] + gap)
            merged.append((kind, payload))
    if pending and merged:
        merged[-1] = (merged[-1][0], merged[-1][1] + "".join(pending))
    return merged


# ── Converting one maths run to a LaTeX maths body ─────────────────────────

_UNICODE_MATH: Final[dict[str, str]] = {
    "×": r"\times ", "÷": r"\div ", "−": "-", "±": r"\pm ",
    "≥": r"\geq ", "≤": r"\leq ", "→": r"\rightarrow ",
    "≈": r"\approx ", "σ": r"\sigma ", "π": r"\pi ",
    "ρ": r"\rho ", "Δ": r"\Delta ", "φ": r"\phi ",
}

_SUPERSCRIPTS: Final = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4"}
_SUBSCRIPTS: Final = {"₀": "0", "₁": "1", "₂": "2", "₃": "3"}

# A slash separated by a unit name is a compound unit (kg/m³), not a fraction.
_UNITS: Final = frozenset({
    "kg", "g", "m", "mm", "cm", "N", "kN", "MPa", "kPa", "Pa",
    "d", "s", "min", "L", "l", "mol", "kWh", "CO2",
})

# Bare functions get their own upright LaTeX command.
_FUNCTIONS: Final = frozenset({
    "max", "min", "abs", "sqrt", "log", "ln", "exp", "sin", "cos", "tan",
})

# One or two letters with an optional prime: f, W, s, f'c — set in italics.
_SHORT_RE: Final = re.compile(r"^[A-Za-z]'?[A-Za-z]?$")

_ESCAPE_OP: Final[dict[str, str]] = {
    "%": r"\%", "&": r"\&", "#": r"\#", "$": r"\$",
    "_": r"\_", "*": r"\times ", "~": r"\sim ",
    "{": r"\{", "}": r"\}", "\\": r"\backslash ",
    "<=": r"\leq ", ">=": r"\geq ",
}
_ESCAPE_NAME: Final[dict[str, str]] = {
    "%": r"\%", "&": r"\&", "#": r"\#", "$": r"\$", "\\": r"\textbackslash{}",
}

_UNI_CLASS: Final = "".join(
    re.escape(ch) for ch in sorted(_UNICODE_MATH, key=len, reverse=True)
)

_TOKEN_RE: Final = re.compile(
    r"(?P<space>\s+)"
    rf"|(?P<uni>[{_UNI_CLASS}])"
    r"|(?P<cmp><=|>=)"
    r"|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<ident>[A-Za-z][A-Za-z0-9_'°¹²³⁰-₟]*)"
    r"|(?P<op>[^\sA-Za-z0-9])"
)


def _strip_scripts(text: str) -> str:
    """Drop superscript/subscript digits and underscores from an identifier."""
    return re.sub(r"[⁰-₟_]", "", text)


def _make_scripts(text: str) -> str:
    """Turn ``passing_600`` into ``passing_{600}`` and ``m3`` into ``m^{3}``."""
    out = re.sub(r"_([A-Za-z0-9]+)", r"_{\1}", text)
    out = "".join(f"^{_SUPERSCRIPTS[ch]}" if ch in _SUPERSCRIPTS
                  else f"_{_SUBSCRIPTS[ch]}" if ch in _SUBSCRIPTS
                  else ch
                  for ch in out)
    return out


def _emit_ident(value: str) -> str:
    """Render one identifier: functions and units upright, symbols italic."""
    if _strip_scripts(value).lower() in _FUNCTIONS:
        # No trailing space: the original whitespace token is preserved anyway.
        return "\\" + _strip_scripts(value).lower()
    if _SHORT_RE.match(value):
        return value
    name = "".join(_ESCAPE_NAME.get(ch, ch) for ch in _make_scripts(value))
    return r"\mathrm{" + name + "}"


def _emit_token(kind: str, value: str) -> str:
    """Convert a single token to its LaTeX maths representation."""
    if kind == "space":
        return " "
    if kind == "uni":
        return _UNICODE_MATH[value]
    if kind == "number":
        return "".join(f"^{_SUPERSCRIPTS[ch]}" if ch in _SUPERSCRIPTS
                       else f"_{_SUBSCRIPTS[ch]}" if ch in _SUBSCRIPTS
                       else ch for ch in value)
    if kind == "ident":
        return _emit_ident(value)
    return _ESCAPE_OP.get(value, value)


def _fraction_operand(tokens: list[tuple[str, str, str]], index: int) -> str | None:
    """Return the LaTeX for a fraction's neighbour, or ``None`` if not one."""
    if index < 0 or index >= len(tokens):
        return None
    kind, value, emitted = tokens[index]
    if kind == "number":
        return emitted
    if kind == "ident":
        core = _strip_scripts(value)
        if core in _UNITS:          # kg/m³ is a unit, not a fraction
            return None
        if _SHORT_RE.match(core):
            return emitted
    return None


def fold_math(span: str) -> str:
    """Convert one run of ASCII maths into a LaTeX maths body.

    The body is returned *without* the surrounding ``$...$``, so callers that
    need a full expression (the LaTeX PDF export) can wrap it themselves.

    Args:
        span: A run classified as maths by :func:`segments`.

    Returns:
        LaTeX for the maths body, or an empty string when nothing remains.
    """
    tokens = [
        (m.lastgroup, m.group(), _emit_token(m.lastgroup, m.group()))
        for m in _TOKEN_RE.finditer(str(span))
    ]

    out: list[str] = []
    i, n = 0, len(tokens)
    while i < n:
        kind, value, emitted = tokens[i]
        if kind == "op" and value == "/":
            numerator = _fraction_operand(tokens, i - 1)
            denominator = _fraction_operand(tokens, i + 1)
            if numerator is not None and denominator is not None:
                if out and out[-1] == numerator:
                    out.pop()
                out.append(rf"\frac{{{numerator}}}{{{denominator}}}")
                i += 2
                continue
        out.append(emitted)
        i += 1

    return re.sub(r"\s+", " ", "".join(out)).strip()


def to_latex(formula: str) -> str:
    """Convert a whole formula to a LaTeX fragment.

    Prose runs are escaped with :func:`sanitize_latex` — they may carry
    user-entered material names and must never be read as TeX. Maths runs are
    emitted from a fixed vocabulary by :func:`fold_math`, which cannot pass
    through caller-supplied TeX either.

    Args:
        formula: A step's ``formula`` string.

    Returns:
        A LaTeX fragment with maths runs wrapped in ``$...$``.
    """
    if len(str(formula)) > MAX_FORMULA_CHARS:
        return sanitize_latex(formula)

    parts: list[str] = []
    for kind, payload in segments(formula):
        payload = payload.strip()
        if not payload:
            continue
        if kind == _MATH:
            body = fold_math(payload)
            if body:
                parts.append(f"${body}$")
        else:
            parts.append(sanitize_latex(payload))
    return " ".join(parts)


# ── Rendering a LaTeX fragment ─────────────────────────────────────────────
#
# Everything the PyQt surfaces hold is a *fragment* — prose with maths runs
# wrapped in ``$...$`` — not a raw ASCII formula. Rendering it is the inverse
# of :func:`to_latex`: split the fragment on its ``$`` delimiters, hand the
# maths runs to mathtext and draw the prose runs as plain text. Re-running
# :func:`segments` on a fragment (as an earlier revision did) feeds LaTeX to a
# converter that only understands ASCII, which mangles every command into
# ``\backslash\mathrm{frac}`` and either draws nonsense or fails outright.

# LaTeX escapes :func:`escape_latex` introduces into prose runs, and the plain
# characters matplotlib should draw in their place.
_UNESCAPE_TEXT: Final[tuple[tuple[str, str], ...]] = (
    (r"\textbackslash{}", "\\"),
    (r"\textasciitilde{}", "~"),
    (r"\textasciicircum{}", "^"),
    (r"\&", "&"),
    (r"\%", "%"),
    (r"\#", "#"),
    (r"\$", "$"),
    (r"\_", "_"),
    (r"\{", "{"),
    (r"\}", "}"),
    ("---", "\u2014"),
    ("--", "\u2013"),
)

# mathtext rejects the text-mode escapes ``\&`` and ``\#``, and has no
# ``\textbackslash``/``\textasciitilde``/``\textasciicircum`` at all, so maths
# runs are translated into the equivalent mathtext before drawing.
_MATHTEXT_FIXUPS: Final[tuple[tuple[str, str], ...]] = (
    (r"\textbackslash{}", r"\backslash{}"),
    (r"\textasciitilde{}", r"\sim{}"),
    (r"\textasciicircum{}", r"{}^{\wedge}"),
    (r"\#", r"\text{\#}"),
    (r"\&", "&"),
)

# A single maths run longer than this is not handed to mathtext: parse cost is
# superlinear in the run length, and a pathological history import would stall
# the paint. The whole fragment is drawn as plain text instead.
MAX_MATH_RUN_CHARS: Final = 512

# Line advance, as a multiple of the font size. Large enough to clear a
# ``\frac``'s stacked numerator and denominator without looking loose.
_LINE_SPACING: Final = 1.35


def _unescape_prose(text: str) -> str:
    """Undo :func:`escape_latex` so matplotlib draws prose as plain text."""
    for escaped, plain in _UNESCAPE_TEXT:
        text = text.replace(escaped, plain)
    return text


def _to_mathtext(body: str) -> str:
    """Adapt a LaTeX maths body to what matplotlib's mathtext accepts.

    ``\\&`` and ``\\#`` are *text-mode* LaTeX commands that mathtext rejects
    outright, while a bare ``&`` is accepted and ``\\text{\\#}`` prints the
    hash. ``\\textbackslash``/``\\textasciitilde``/``\\textasciicircum`` have
    no mathtext equivalent, so they map onto ``\\backslash``/``\\sim`` and a
    superscript wedge. :func:`to_latex` keeps the text-mode spellings because
    they are what a real TeX engine compiles.
    """
    for latex, mathtext in _MATHTEXT_FIXUPS:
        body = body.replace(latex, mathtext)
    return body


def fragment_runs(line: str) -> list[tuple[bool, str]]:
    """Split one line of a LaTeX fragment into prose and maths runs.

    An unescaped ``$`` toggles maths mode, matching LaTeX's own rule, so a
    literal dollar written as ``\\$`` stays prose.

    Args:
        line: One line of a fragment, without its trailing newline.

    Returns:
        ``(is_maths, payload)`` pairs in order. Whitespace inside a line is
        preserved so adjacent runs butt together; the line's own outer
        whitespace is trimmed, since layout supplies the margins.
    """
    runs: list[tuple[bool, str]] = []
    position = 0
    in_math = False
    for match in re.finditer(r"(?<!\\)\$", line):
        start = match.start()
        runs.append((in_math, line[position:start]))
        position = start + 1
        in_math = not in_math
    runs.append((in_math, line[position:]))

    while runs and not runs[0][1].strip():
        runs.pop(0)
    while runs and not runs[-1][1].strip():
        runs.pop()
    if not runs:
        return [(False, line)]
    runs[0] = (runs[0][0], runs[0][1].lstrip())
    runs[-1] = (runs[-1][0], runs[-1][1].rstrip())
    return [run for run in runs if run[1]]


def render_data_uri(formula: str, **kwargs) -> str:
    """Rasterise a formula to a ``data:`` URI for the HTML surfaces.

    QLabel and QTextBrowser both accept a base64 PNG data URI as an ``<img>``
    source, which is what lets the report preview show typeset maths with no
    web engine and no external file.

    Args:
        formula: A formula string — a LaTeX fragment, or raw ASCII.
        **kwargs: Forwarded to :func:`render_png`.

    Returns:
        A ``data:image/png;base64,...`` URI, or an empty string when the
        formula cannot be drawn.
    """
    png = render_png(formula, **kwargs)
    if not png:
        return ""
    return _png_data_uri(png)


def _png_data_uri(png: bytes) -> str:
    """Wrap PNG bytes as a base64 ``data:`` URI."""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def png_dimensions(png: bytes) -> tuple[int, int] | None:
    """Return the pixel size of PNG ``png``, read from its IHDR header.

    The header is parsed directly — 8 signature bytes, a 4-byte chunk length,
    the ``IHDR`` tag, then width and height as big-endian uint32 — so callers
    embedding the raster in HTML can size it without decoding the image.

    Args:
        png: PNG-encoded bytes.

    Returns:
        ``(width, height)`` in pixels, or ``None`` when ``png`` is not a PNG.
    """
    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", png[16:24])


def _resize_png(png: bytes, width: int, height: int) -> bytes | None:
    """Resample ``png`` to an exact pixel size for a 1:1 draw.

    Qt's rich-text engine scales an ``<img>`` with a fast filter when the
    ``width``/``height`` attributes differ from the image's intrinsic size.
    Thin strokes — a lone ``=`` is two sub-pixel bars — can fall between
    sampled rows and vanish entirely from the drawn result. Baking the raster
    at its final size with a high-quality resample preserves that ink, and the
    matching attribute sizes then make Qt draw the image without rescaling.

    Args:
        png: PNG-encoded bytes.
        width: Target width in pixels.
        height: Target height in pixels.

    Returns:
        Resampled PNG bytes; the original bytes when no resample is needed;
        ``None`` when Pillow is unavailable, in which case the caller keeps
        the current attribute-scaling behaviour.
    """
    if png_dimensions(png) == (width, height):
        return png
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow ships with matplotlib
        return None
    with Image.open(io.BytesIO(png)) as image:
        resized = image.convert("RGBA").resize((width, height), Image.LANCZOS)
        channel = io.BytesIO()
        resized.save(channel, format="PNG")
    return channel.getvalue()


def fragment_html(
    fragment: str,
    *,
    fontsize: int = 10,
    dpi: int = 200,
    valign: str = "middle",
) -> str:
    """Compose a LaTeX fragment into HTML with the maths as inline images.

    The HTML surfaces — the target-strength callout and the report preview's
    ``QTextBrowser`` — cannot typeset maths themselves. Prose runs are kept as
    escaped text so they inherit the surrounding font and wrap normally; each
    maths run becomes a transparent PNG data URI, sized in CSS pixels so the
    maths reads at the same point size as the text beside it. This is the
    :func:`fragment_runs` inverse of :func:`to_latex`, for Qt rich text.

    Args:
        fragment: A LaTeX fragment — prose with maths runs in ``$...$``. A
            string carrying no ``$`` is treated as a raw ASCII formula and
            converted first, matching :func:`render_png`.
        fontsize: Point size the maths is rendered at.
        dpi: Raster resolution; a higher value stays crisp when scaled.
        valign: CSS vertical alignment for the inline maths images.

    Returns:
        HTML for the fragment, or an empty string when the fragment is empty,
        too long, or nothing could be drawn. Callers must fall back to plain
        text on an empty result so a parse failure never blanks a result.
    """
    source = str(fragment)
    if not source.strip() or len(source) > MAX_FORMULA_CHARS:
        return ""
    if "$" not in source:
        source = to_latex(source)
    if not source.strip():
        return ""

    # 96 CSS pixels to the inch: a raster drawn at ``dpi`` is displayed by
    # this factor so ``fontsize`` points of maths stay ``fontsize`` points.
    css_scale = 96.0 / dpi

    lines: list[str] = []
    for line in source.split("\n"):
        pieces: list[str] = []
        for is_math, payload in fragment_runs(line):
            if not is_math:
                pieces.append(html.escape(_unescape_prose(payload)))
                continue
            png = render_png(f"${payload}$", fontsize=fontsize, dpi=dpi)
            size = png_dimensions(png) if png else None
            if not size:
                # The maths did not parse; keep the source visible instead of
                # dropping the term from the working.
                pieces.append(html.escape(f"${payload}$"))
                continue
            width, height = size
            area = (
                max(1, round(width * css_scale)),
                max(1, round(height * css_scale)),
            )
            # Bake at display size: Qt drops sub-pixel strokes (a lone ``=``)
            # when it has to rescale the image to the attribute size itself.
            baked = _resize_png(png, *area) or png
            pieces.append(
                f'<img src="{_png_data_uri(baked)}" '
                f'width="{area[0]}" '
                f'height="{area[1]}" '
                f'style="vertical-align:{valign};" alt=""/>'
            )
        lines.append("".join(pieces))
    return "<br/>".join(lines)


# ── Rasterising for the PyQt surfaces ──────────────────────────────────────


@functools.lru_cache(maxsize=512)
def render_png(
    formula: str,
    *,
    fontsize: int = 10,
    dpi: int = 200,
    fontfamily: str | None = None,
) -> bytes | None:
    """Render a formula to transparent PNG bytes using Computer Modern.

    matplotlib's ``mathtext`` covers the subset of LaTeX this project needs
    (``\\frac``, ``\\times``, subscripts, ``\\max``) and needs no TeX
    installation, which is what the PyQt surfaces require. The figure is built
    on an explicit Agg canvas so the global backend — set to ``QtAgg`` by
    :mod:`app.widgets.psd_widget` — is left untouched.

    The input is normally the LaTeX fragment held in
    :attr:`CalculationStep.latex`. A string carrying no ``$`` is treated as a
    raw ASCII formula and converted first, so a caller still holding
    ``step.formula`` need not convert it itself.

    Args:
        formula: A LaTeX fragment, or raw ASCII to convert and draw.
        fontsize: Point size for the rendered line.
        dpi: Raster resolution; higher is sharper when scaled.
        fontfamily: Font for the prose runs; ``None`` uses matplotlib's default.

    Returns:
        PNG bytes, or ``None`` when there is nothing to draw or mathtext
        cannot parse the maths. Callers must fall back to plain text on
        ``None`` so a parse failure never blanks a design result.
    """
    if not formula or not str(formula).strip():
        return None
    if len(str(formula)) > MAX_FORMULA_CHARS:
        return None

    source = str(formula)
    if "$" not in source:
        source = to_latex(source)
    if not source.strip():
        return None

    lines = [
        runs
        for runs in (fragment_runs(line) for line in source.split("\n"))
        if runs
    ]
    if not lines:
        return None

    try:
        import matplotlib
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception:
        return None

    # matplotlib interleaves maths and plain text within one Text artist, but
    # cannot mix the two *spines*, so a mixed line is drawn as several adjacent
    # artists. The baseline steps down per line and ``bbox_inches="tight"``
    # crops the transparent margins afterwards.
    line_px = fontsize * _LINE_SPACING * dpi / 72.0
    width_in = max(1.0, min(len(source) * fontsize * 0.62, 4000) / 72.0)
    height_in = max(
        1.0, (len(lines) * line_px + 2 * fontsize * dpi / 72.0) / dpi
    )
    buffer = io.BytesIO()
    try:
        with matplotlib.rc_context({"mathtext.fontset": "cm"}):
            figure = Figure(figsize=(width_in, height_in), dpi=dpi)
            FigureCanvasAgg(figure)
            figure.patch.set_alpha(0.0)
            try:
                renderer = figure.canvas.get_renderer()
                width_px = figure.get_figwidth() * dpi
                height_px = figure.get_figheight() * dpi
                top_px = fontsize * dpi / 72.0
                for row, runs in enumerate(lines):
                    x_px = 0.0
                    y = 1.0 - (top_px + row * line_px) / height_px
                    for is_math, payload in runs:
                        if is_math:
                            if len(payload) > MAX_MATH_RUN_CHARS:
                                return None
                            body = _to_mathtext(payload)
                            if not body.strip():
                                continue
                            shown = f"${body}$"
                        else:
                            shown = _unescape_prose(payload)
                        if not shown:
                            continue
                        try:
                            text = figure.text(
                                x_px / width_px,
                                y,
                                shown,
                                fontsize=fontsize,
                                fontfamily=fontfamily,
                                va="baseline",
                                ha="left",
                            )
                            extent = text.get_window_extent(renderer=renderer)
                        except Exception:
                            # One unparsable maths run fails the whole fragment:
                            # the caller then draws it as plain text, whereas a
                            # partial raster would silently drop a term.
                            return None
                        x_px += extent.width
                figure.savefig(
                    buffer,
                    format="png",
                    dpi=dpi,
                    bbox_inches="tight",
                    pad_inches=0.02,
                    transparent=True,
                )
            finally:
                # The object-oriented API owns this figure outright, so there
                # is no pyplot global state to unwind here.
                figure.clear()
    except Exception:
        return None

    data = buffer.getvalue()
    return data or None
