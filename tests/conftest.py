"""Shared test-process environment.

Two process-wide settings keep the offscreen UI suite deterministic:

1. A single stable MPLCONFIGDIR — several test modules force a fresh
   ``HOME``/``XDG_CONFIG_HOME`` at import; without a pinned matplotlib
   config dir the font cache would be rebuilt several times per run.
2. ``text.hinting = 'none'`` — with the PyQt6 6.11 / Qt 6.11 /
   matplotlib 3.11 stack used here, FreeType hinting of QtAgg text
   intermittently aborts with ``FT_Render_Glyph … error 0x62 raster
   overflow`` once any QTableWidget has been created in the process
   (hinting rounds glyph transforms through a path that overflows the
   raster buffer). Disabling hinting only affects glyph raster quality,
   never geometry or text content, so plots stay assertion-identical.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "cq_mpl_cache")
)

import matplotlib

matplotlib.rcParams["text.hinting"] = "none"
