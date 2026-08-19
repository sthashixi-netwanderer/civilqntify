"""PSD widget tests — out-of-band annotation on the gradation plot."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_psd_test_")
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["HOME"] = _TMP

import pytest

_qapp = None


@pytest.fixture()
def qt():
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication

        _qapp = QApplication.instance() or QApplication([])
    yield _qapp


def _fill_and_plot(tab, masses, pan):
    sieves = tab._current_sieves()
    assert len(masses) == len(sieves)
    for i, m in enumerate(masses):
        tab.table.item(i, 1).setText(str(m))
    tab.table.item(len(sieves), 1).setText(str(pan))
    tab._on_compute_plot()


def _plot_texts(tab):
    return " ".join(t.get_text() for t in tab._fig.axes[0].texts)


def test_out_of_band_gradation_is_annotated_on_plot(qt):
    """A gradation outside the selected zone must be commented on the graph."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    assert tab.band_combo.currentData() == ("fine", "II")  # default Zone II

    # Too fine at 600 µm (36% > 30%) and 300 µm (22% > 20%); all else conforms
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)

    texts = _plot_texts(tab)
    assert "Outside the standard band" in texts
    assert "600 µm: 36.0% > 30% limit — too fine" in texts
    assert "300 µm: 22.0% > 20% limit — too fine" in texts
    # Both offending points must be marked on the curve
    assert any(
        coll.get_offsets().shape[0] == 2 for coll in tab._fig.axes[0].collections
    )


def test_conforming_gradation_has_no_warning(qt):
    """A gradation inside the band must not show the warning comment."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()

    # Zone II conforming sand (limits: 4.75 90–100, 2.36 40–100, 1.18 0–50,
    # 0.600 10–30, 0.300 5–20, 0.150 0–10)
    _fill_and_plot(tab, [0, 5, 45, 200, 125, 35, 80], pan=10)

    texts = _plot_texts(tab)
    assert "Outside the standard band" not in texts
    # Badge below the plot confirms conformance
    assert tab._last_result is not None
    assert tab._last_result.all_conform
