"""Box-aware wrapping label — fixes last-line clipping in padded callouts.

**Defect.** ``QLabel.heightForWidth()`` answers the height of the wrapped
*text* only. When the stylesheet gives the label a box (``padding`` plus
``border`` — every ``callout-*``, ``*-banner`` and ``section-title`` rule in
``app/styles.py``), layouts reserve that un-padded height, so the last
wrapped line is clipped by exactly the box height. Measured before the fix:
a DOE design note was allocated 122 px where 136 px were required (14 px =
6+6 padding + 1+1 border); the same deficit hit the IS/ACI strength notes,
the std-dev display and the result panel's ``section-title`` headers at
every sidebar width and font size (112 clipped instances in the sweep that
became ``tests/test_wrap_label_layout.py``).

**Fix.** :class:`WrapLabel` re-adds the stylesheet box inside
``heightForWidth()`` so every layout (``QFormLayout``, ``QVBoxLayout``, the
``QScrollArea`` height-for-width chain) reserves the real height at any
width and font size. ``setText()`` also invalidates ancestor layouts so a
dynamically lengthened value (water content, applied std-dev, verdict
panels) grows its row immediately instead of leaving a stale height behind.

Use it for every word-wrapped label whose object name carries a QSS box.
For un-boxed labels the added margins are zero and behaviour is identical
to a plain word-wrapped ``QLabel``.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QWidget


class WrapLabel(QLabel):
    """Word-wrapped label whose height report includes the stylesheet box."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        # Preferred/Minimum like the form labels in ConcreteMixTab._label:
        # never dictating the row width, growing with wrapped content.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt naming
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt naming
        box = self.contentsMargins()  # QSS padding + border; 0 for plain labels
        inner = max(1, width - box.left() - box.right())
        return QLabel.heightForWidth(self, inner) + box.top() + box.bottom()

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        super().setText(text)
        # Layout invalidation alone cannot grow a QScrollArea's content:
        # the scroll area only re-derives the content size on viewport or
        # widget resize, so rows were re-solved inside the stale content
        # height and long retxt clipped (the water-content row in DOE).
        # Two steps, in this order:
        #   1. activate every layout from the innermost outward so row
        #      heights reflect the new text *before* anything measures;
        #   2. resize the scroll-area content to its recomputed
        #      height-for-width (the same sizing widgetResizable applies on
        #      a viewport resize), repeating until the height stops moving
        #      — the first pass hands rows the stale height and only the
        #      following resize grants the grown height its re-solve.
        widget: QWidget | None = self.parentWidget()
        while widget is not None:
            layout = widget.layout()
            if layout is not None:
                layout.activate()
            widget = widget.parentWidget()
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, QScrollArea) and widget.widgetResizable():
                content = widget.widget()
                layout = content.layout() if content is not None else None
                if layout is not None and content.width() > 0:
                    for _ in range(4):
                        height = layout.totalHeightForWidth(content.width())
                        if height <= 0 or height == content.height():
                            break
                        content.resize(content.width(), height)
                break
            widget = widget.parentWidget()
