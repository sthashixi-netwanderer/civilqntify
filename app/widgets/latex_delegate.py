"""Item delegate that paints calculation steps as typeset LaTeX maths.

The step working recorded in :attr:`CalculationStep.formula` is hand-written
ASCII (``W = 2/3x160 + 1/3x190``). :mod:`concrete_mix.utils.latex_math`
converts it to a LaTeX fragment and rasterises it with matplotlib's
``mathtext`` in the Computer Modern fontset — the shapes a compiled LaTeX
document would print, with no TeX installation required.

This delegate draws that raster into a tree or table cell. It is the PyQt
equivalent of a printed calculation trail: plain text wherever the maths
cannot be drawn, typeset maths wherever it can.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QFontInfo, QFontMetricsF, QImage, QPainter, QPen
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from concrete_mix.utils import latex_math

#: Column holding the step working in both the result panel tree and the
#: history detail table. Kept as a default so a caller wiring the delegate to
#: either surface does not have to repeat it.
FORMULA_COLUMN = 2

#: Raster resolution. High enough that a formula scaled down to UI size stays
#: crisp on a HiDPI screen, low enough that a cold render stays interactive.
_RENDER_DPI = 200
_RENDER_POINTS = 10

#: Ceiling on the drawn height. ``\frac`` and stacked scripts legitimately make
#: a row taller than its neighbours, but an unbounded multiple would let one
#: formula dominate the steps table, so oversized maths is scaled to fit.
_MAX_DRAW_HEIGHT_PX = 46

#: Smallest allowed scale. Below this the maths is drawn as plain text rather
#: than shrunk into illegibility.
_MIN_SCALE = 0.55

#: Fallback column width when a formula has not been rasterised yet. Wide
#: enough for a typical working so `resizeColumnToContents` behaves sensibly
#: even on the cold path.
_FALLBACK_WIDTH_PX = 160

#: Rasterised maths keyed by the LaTeX it was drawn from. ``render_png`` already
#: caches the encoded bytes; this avoids re-decoding on every repaint. A
#: ``None``-image entry records "this did not render" so the miss is not retried.
_IMAGE_CACHE: dict[str, Optional[QImage]] = {}
_IMAGE_CACHE_MAX = 512


def _cached_image(latex: str) -> Optional[QImage]:
    """Return the rasterised maths for ``latex``, or ``None`` if undrawable."""
    if latex in _IMAGE_CACHE:
        return _IMAGE_CACHE[latex]
    png = latex_math.render_png(latex, fontsize=_RENDER_POINTS, dpi=_RENDER_DPI)
    image = None
    if png:
        candidate = QImage.fromData(png)
        if not candidate.isNull():
            image = candidate
    if len(_IMAGE_CACHE) >= _IMAGE_CACHE_MAX:
        _IMAGE_CACHE.clear()
    _IMAGE_CACHE[latex] = image
    return image


def clear_image_cache() -> None:
    """Drop cached rasters.

    Not needed for correctness — the cache is keyed on content and bounded —
    but worth calling when a font or stylesheet change makes the previously
    rendered rasters the wrong size for the new UI font.
    """
    _IMAGE_CACHE.clear()


def prewarm(latex_forms: list[str]) -> None:
    """Rasterise ahead of the first size query or paint.

    A cold render costs a few tens of milliseconds per step. Doing that inside
    ``paint()`` makes the steps table appear row by row; doing it once when a
    design finishes computing trades that for a single pause. Rendering here
    also lets ``sizeHint`` report the formula's true width, which is what keeps
    a long working from being clipped by the column.
    """
    for latex in latex_forms:
        if latex:
            _cached_image(latex)


class MathDelegate(QStyledItemDelegate):
    """Paints a cell's LaTeX working as Computer Modern maths.

    The LaTeX is read from the item's :attr:`Qt.ItemDataRole.UserRole` data. An
    item carrying no such data is treated as holding the raw ASCII working and
    converted on the fly, so this can be attached to a table that was filled in
    before the class existed.
    """

    def __init__(self, parent=None, *, column: int = FORMULA_COLUMN) -> None:
        """Args:
            parent: Qt parent, normally the view the delegate is installed on.
            column: Index of the column this delegate paints.
        """
        super().__init__(parent)
        self._column = column

    def _latex(self, index) -> str:
        r"""The fragment to draw for ``index``.

        Both views already store the LaTeX fragment in the display text, so the
        cell value is used as-is. It is *not* passed through
        :func:`latex_math.to_latex` again: that converter reads ASCII, and
        re-running it on a fragment mangles every command into
        ``\backslash\mathrm{frac}``. :func:`latex_math.render_png` converts a
        fragment that still carries raw ASCII on its own.
        """
        latex = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(latex, str) and latex.strip():
            return latex
        return index.data(Qt.ItemDataRole.DisplayRole) or ""

    def _scale(self, option: QStyleOptionViewItem) -> float:
        """Factor mapping a render-time pixel to a screen pixel.

        The raster's em square is ``_RENDER_POINTS * _RENDER_DPI / 72``
        pixels tall; the screen's em square is the UI font's pixel size.
        Drawing at the ratio of the two sizes the maths to match the text
        beside it. The font's *em* size is used rather than its line height: the
        line height includes leading, and matching it would inflate the
        glyphs by roughly a third. The pixel size also covers fonts that
        the app stylesheet specifies in pixels, where ``pointSizeF()`` is
        ``-1`` and no point-based conversion is possible.
        """
        em_px = QFontInfo(option.font).pixelSize()
        if em_px <= 0:
            return 1.0
        return em_px / (_RENDER_POINTS * _RENDER_DPI / 72.0)

    def _drawn_size(self, image: Optional[QImage], scale: float) -> QSize:
        """Size ``image`` should be drawn at, held within the height cap.

        Returns an empty size when the maths must not be drawn at all.
        """
        if image is None or image.isNull():
            return QSize()
        width = max(1, round(image.width() * scale))
        height = max(1, round(image.height() * scale))
        if height > _MAX_DRAW_HEIGHT_PX:
            shrink = _MAX_DRAW_HEIGHT_PX / height
            if shrink < _MIN_SCALE:
                return QSize()
            width = max(1, round(width * shrink))
            height = _MAX_DRAW_HEIGHT_PX
        return QSize(width, height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """Draw the cell background, then the maths centred in the cell."""
        self.initStyleOption(option, index)
        text = option.text
        option.text = ""
        widget = option.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget
            )

        rect = option.rect
        image = _cached_image(self._latex(index))
        drawn = self._drawn_size(image, self._scale(option))
        painter.save()
        painter.setClipRect(rect)
        if not drawn.isEmpty():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            top = rect.y() + (rect.height() - drawn.height()) // 2
            painter.drawImage(
                QRect(rect.x(), top, drawn.width(), drawn.height()),
                image,
                QRect(0, 0, image.width(), image.height()),
            )
        elif text:
            # Either the maths did not parse, or the cell carries plain text
            # rather than a working. Either way the reader still gets the
            # formula; a blank cell would hide the calculation.
            metrics = QFontMetricsF(option.font)
            shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - 8)
            painter.setPen(QPen(option.palette.text().color()))
            painter.drawText(
                rect.adjusted(4, 0, -4, 0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                shown,
            )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Report the size the maths needs, so row and column sizing stay true.

        ``QTreeView.sizeHintForRow`` reads the height, which is what keeps the
        result panel's step list from growing an inner scrollbar; the width is
        what ``resizeColumnToContents`` reads, which is what stops a long
        working from being clipped. Both come from the raster, which
        :func:`prewarm` has normally already produced — so this stays cheap.
        """
        drawn = self._drawn_size(_cached_image(self._latex(index)), self._scale(option))
        if not drawn.isEmpty():
            return drawn
        metrics = QFontMetricsF(option.font)
        return QSize(_FALLBACK_WIDTH_PX, int(metrics.height()) * 2 + 2)

