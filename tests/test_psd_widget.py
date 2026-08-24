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
    """A gradation outside the zone must be marked on the curve and
    summarised in the banner below the plot — never overlaid on it."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    assert tab.band_combo.currentData() == ("fine", "II")  # default Zone II

    # Too fine at 600 µm (36% > 30%) and 300 µm (22% > 20%); all else conforms
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)

    # The plot itself stays clean — no summary box overlaid on the axes
    texts = _plot_texts(tab)
    assert "Outside the standard band" not in texts

    # Summary lives in the banner below the plot
    assert not tab._result_panel._band_warning.isHidden()
    assert "Outside the standard band" in tab._result_panel._band_warning.text()
    assert (
        "600 µm: 36.0% > 30% limit — too fine"
        in tab._result_panel._band_warning.text()
    )
    assert (
        "300 µm: 22.0% > 20% limit — too fine"
        in tab._result_panel._band_warning.text()
    )

    # Predicted adjustments are shown below the plot
    assert not tab._result_panel._corrections_label.isHidden()
    corr_text = tab._result_panel._corrections_label.text()
    assert "Suggested adjustments" in corr_text
    assert "600 µm" in corr_text
    assert "44%" in corr_text  # (36 − 20) / 36 blend fraction
    assert "43%" in corr_text  # (22 − 12.5) / 22 blend fraction

    # Both offending points must still be marked on the curve
    assert any(
        coll.get_offsets().shape[0] == 2 for coll in tab._fig.axes[0].collections
    )


def test_conforming_gradation_has_no_warning(qt):
    """A gradation inside the band must not show the warning banner."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()

    # Zone II conforming sand (limits: 4.75 90–100, 2.36 40–100, 1.18 0–50,
    # 0.600 10–30, 0.300 5–20, 0.150 0–10)
    _fill_and_plot(tab, [0, 5, 45, 200, 125, 35, 80], pan=10)

    texts = _plot_texts(tab)
    assert "Outside the standard band" not in texts
    assert tab._result_panel._band_warning.isHidden()
    assert tab._result_panel._corrections_label.isHidden()
    # Badge below the plot confirms conformance
    assert tab._last_result is not None
    assert tab._last_result.all_conform


def test_characteristic_d_diameters_plotted_on_graph(qt):
    """D10, D30, and D60 characteristic sizes must be plotted on the graph with
    reference lines to both axes and annotated with proper decimal precision."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    # Fine aggregate sample with known D10, D30, D60
    _fill_and_plot(tab, [0, 25, 100, 150, 120, 75, 25], pan=5)

    texts = _plot_texts(tab)
    # Check that D10, D30, D60 annotations are present on the plot
    assert "D_{10}" in texts or "D₁₀" in texts
    assert "D_{30}" in texts or "D₃₀" in texts
    assert "D_{60}" in texts or "D₆₀" in texts
    assert "mm" in texts

    # Verify line count on axes includes the D-lines (horizontal and vertical reference lines)
    ax = tab._fig.axes[0]
    # Gradation line + 3 horizontal D-lines + 3 vertical D-lines + 3 D-marker points = 10 lines
    assert len(ax.lines) >= 7

