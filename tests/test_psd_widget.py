"""PSD widget tests — out-of-band annotation on the gradation plot."""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_psd_test_")
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["HOME"] = _TMP

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
    assert tab.band_combo.currentData() == (
        "is383", "fine", "II"
    )  # default IS Zone II

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


def test_coarse_mode_lists_all_astm_table_2_sieves_and_only_supported_bands(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    from concrete_mix.engine.psd import ASTM_COARSE_SIEVES

    tab = ParticleSizeDistributionTab()
    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))

    assert tab._current_sieves() == ASTM_COARSE_SIEVES
    assert tab.table.rowCount() == len(ASTM_COARSE_SIEVES) + 2
    assert [
        tab.table.item(row, 0).data(0x0100)
        for row in range(len(ASTM_COARSE_SIEVES))
    ] == ASTM_COARSE_SIEVES
    assert [tab.band_combo.itemData(i) for i in range(tab.band_combo.count())] == [
        ("astm_c33", "coarse", 10),
        ("astm_c33", "coarse", 20),
        ("astm_c33", "coarse", 40),
    ]
    assert [tab.band_combo.itemText(i) for i in range(tab.band_combo.count())] == [
        "10 mm reference (ASTM Size 8)",
        "20 mm reference (ASTM Size 67)",
        "40 mm reference (ASTM Size 467)",
    ]
    assert tab.table.item(ASTM_COARSE_SIEVES.index(19.0), 5).text() == "90–100"
    assert tab.table.item(ASTM_COARSE_SIEVES.index(12.5), 5).text() == "—"


def test_is_coarse_mode_uses_table_7_sieves_and_references(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    from concrete_mix.engine.psd import IS_COARSE_SIEVES

    tab = ParticleSizeDistributionTab()
    assert tab.standard_combo.currentData() == "is383"
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))

    assert tab._current_sieves() == IS_COARSE_SIEVES
    assert tab.table.rowCount() == len(IS_COARSE_SIEVES) + 2
    assert [tab.band_combo.itemData(i) for i in range(tab.band_combo.count())] == [
        ("is383", "coarse", "graded", 40),
        ("is383", "coarse", "graded", 20),
        ("is383", "coarse", "graded", 16),
        ("is383", "coarse", "graded", 12.5),
        ("is383", "coarse", "single", 63),
        ("is383", "coarse", "single", 40),
        ("is383", "coarse", "single", 20),
        ("is383", "coarse", "single", 16),
        ("is383", "coarse", "single", 12.5),
        ("is383", "coarse", "single", 10),
    ]
    assert tab.band_combo.currentData() == (
        "is383", "coarse", "graded", 20
    )
    assert tab._current_band(tab.band_combo.currentData()) == {
        40.0: (100, 100),
        20.0: (90, 100),
        10.0: (25, 55),
        4.75: (0, 10),
    }
    assert tab.table.item(IS_COARSE_SIEVES.index(20.0), 5).text() == "90–100"
    assert tab.table.item(IS_COARSE_SIEVES.index(16.0), 5).text() == "—"

    tab.band_combo.setCurrentIndex(9)  # IS 10 mm single-sized
    assert tab.table.item(IS_COARSE_SIEVES.index(10.0), 5).text() == "85–100"
    assert tab.table.item(IS_COARSE_SIEVES.index(20.0), 5).text() == "—"


def test_standard_switch_changes_fine_sieves_and_band(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    from concrete_mix.engine.psd import ASTM_FINE_SIEVES, IS_FINE_SIEVES

    tab = ParticleSizeDistributionTab()
    assert tab._current_sieves() == IS_FINE_SIEVES
    assert tab.band_combo.currentData() == ("is383", "fine", "II")

    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    assert tab._current_sieves() == ASTM_FINE_SIEVES
    assert tab.table.item(0, 0).text() == "9.5 mm"
    assert tab.band_combo.currentData() == (
        "astm_c33", "fine", "table1"
    )
    assert tab._current_band(tab.band_combo.currentData())[4.75] == (95, 100)
    assert tab.table.item(0, 5).text() == "100"


def test_smooth_band_passes_control_points_without_overshoot_or_crossing(qt):
    from app.widgets.psd_widget import _smooth_band_boundary
    from concrete_mix.codes.tables.grading_bands import (
        ASTM_COARSE_BANDS,
        IS_COARSE_GRADED_BANDS,
        IS_COARSE_SINGLE_SIZED_BANDS,
    )

    bands = [
        *ASTM_COARSE_BANDS.values(),
        *IS_COARSE_GRADED_BANDS.values(),
        *IS_COARSE_SINGLE_SIZED_BANDS.values(),
    ]
    for band in bands:
        sizes = sorted(band)
        lower = [band[size][0] for size in sizes]
        upper = [band[size][1] for size in sizes]
        smooth_sizes, smooth_lower = _smooth_band_boundary(sizes, lower)
        upper_sizes, smooth_upper = _smooth_band_boundary(sizes, upper)

        assert smooth_sizes == upper_sizes
        assert smooth_sizes[0] == pytest.approx(sizes[0])
        assert smooth_sizes[-1] == pytest.approx(sizes[-1])
        assert all(0.0 <= value <= 100.0 for value in smooth_lower)
        assert all(0.0 <= value <= 100.0 for value in smooth_upper)
        assert all(
            smooth_lower[i] <= smooth_upper[i]
            for i in range(len(smooth_sizes))
        )
        assert all(
            smooth_lower[i] <= smooth_lower[i + 1]
            for i in range(len(smooth_lower) - 1)
        )
        assert all(
            smooth_upper[i] <= smooth_upper[i + 1]
            for i in range(len(smooth_upper) - 1)
        )

        for size, expected_lower, expected_upper in zip(sizes, lower, upper):
            index = smooth_sizes.index(size)
            assert smooth_lower[index] == pytest.approx(expected_lower)
            assert smooth_upper[index] == pytest.approx(expected_upper)


def test_coarse_plot_uses_a_smooth_shaded_astm_section(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))
    assert tab.band_combo.currentData() == ("astm_c33", "coarse", 20)
    masses = [0.0] * len(tab._current_sieves())
    masses[6] = 5.0
    masses[7] = 5.0
    masses[9] = 20.0
    masses[10] = 40.0
    masses[11] = 25.0
    masses[12] = 5.0
    _fill_and_plot(tab, masses, pan=0.0)

    ax = tab._fig.axes[0]
    band_path = ax.collections[0].get_paths()[0]
    assert len(band_path.vertices) > 2 * 5
    assert "ASTM C33/C33M Table 2" in ax.get_title()


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


def test_use_in_mix_design_emits_standard_specific_payload(qt):
    """"Use in Mix Design" must hand the mix-design form exactly the
    sieve-analysis-derived parameters each standard consumes:
    ACI FM (§4.3.5), IS 383 zone → Table 5, DOE %p600 (§1.2.5)."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    payloads: list[dict] = []
    tab._result_panel.apply_to_mix_design.connect(payloads.append)

    # Out-of-band fine sample (36% > 30% passing at 600 µm):
    # cum retained % = 0,1,10,52,64,78,99 → FM = 3.04, p600 = 36.0 %
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    assert tab._result_panel._btn_apply.isEnabled()

    tab._result_panel._btn_apply.click()

    assert len(payloads) == 1
    p = payloads[0]
    assert p["aggregate_kind"] == "fine"
    assert p["band_standard"] == "is383"
    assert p["nominal_size_mm"] is None
    assert p["fineness_modulus"] == pytest.approx(3.04)
    assert p["pct_passing_600um"] == pytest.approx(36.0)
    assert p["grading_zone"] in ("I", "II", "III", "IV")
    # This sample violates the Zone II band on two sieves.
    assert p["all_conform"] is False

    # Clearing the panel must disarm the handoff button.
    tab._result_panel.clear()
    assert not tab._result_panel._btn_apply.isEnabled()


class _NoDialog:
    """Stub that absorbs modal QMessageBox calls during headless tests."""

    @staticmethod
    def information(*_a, **_k):
        return 0

    @staticmethod
    def warning(*_a, **_k):
        return 0


def _emit_apply(tab, payload):
    tab._result_stack  # ensure built
    tab._on_psd_apply(payload)


def test_psd_fed_fields_are_locked_until_clear(qt, monkeypatch):
    """Handoff locks the form fields fed from PSD; Clear unlocks and
    restores their pre-application defaults."""
    import app.widgets.concrete_tab as ct
    monkeypatch.setattr(ct.QMessageBox, "information", _NoDialog.information)
    monkeypatch.setattr(ct.QMessageBox, "warning", _NoDialog.warning)

    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    # Ensure IS mode keeps the plain grading combo visible (non-IS code).
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("aci211"))

    fm_before = tab.fm_spin.value()
    p600_before = tab.pct_passing_600um_spin.value()

    _emit_apply(
        tab,
        {
            "aggregate_kind": "fine",
            "band_standard": "astm_c33",
            "nominal_size_mm": None,
            "fineness_modulus": 3.04,
            "grading_zone": None,
            "pct_passing_600um": 36.0,
            "all_conform": True,
            "warnings": [],
        },
    )

    # FM and p600 are now locked and carrying the PSD-derived values.
    assert "fm" in tab._psd_locked
    assert "p600" in tab._psd_locked
    assert tab.fm_spin.value() == 3.04
    assert tab.pct_passing_600um_spin.value() == 36.0
    assert not tab.fm_spin.isEnabled()
    assert not tab.pct_passing_600um_spin.isEnabled()

    # Clearing the PSD tab emits clear_all_inputs → unlock + restore.
    tab._on_psd_inputs_cleared()
    assert tab._psd_locked == set()
    assert tab.fm_spin.isEnabled()
    assert tab.pct_passing_600um_spin.isEnabled()
    assert tab.fm_spin.value() == fm_before
    assert tab.pct_passing_600um_spin.value() == p600_before


def test_psd_zone_lock_uses_active_source_and_survives_mode_switch(
    qt, monkeypatch
):
    """In IS mode the grading zone is carried by the CA-fraction combo; a
    mode/standard switch must re-lock it rather than let it be re-enabled."""
    import app.widgets.concrete_tab as ct
    monkeypatch.setattr(ct.QMessageBox, "information", _NoDialog.information)
    monkeypatch.setattr(ct.QMessageBox, "warning", _NoDialog.warning)

    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("is10262"))

    # IS + default NMSA: the CA-fraction combo is the active zone source.
    g_before = tab.grading_combo.currentIndex()
    c_before = tab.ca_fraction_combo.currentIndex()
    assert tab.ca_fraction_combo.count() > 0

    _emit_apply(
        tab,
        {
            "aggregate_kind": "fine",
            "band_standard": "is383",
            "nominal_size_mm": None,
            "fineness_modulus": None,
            "grading_zone": "I",
            "pct_passing_600um": None,
            "all_conform": True,
            "warnings": [],
        },
    )

    assert "zone" in tab._psd_locked
    assert not tab.ca_fraction_combo.isEnabled()

    # Mode switches must NOT silently re-enable the locked zone.
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("target_strength"))
    assert not tab.ca_fraction_combo.isEnabled()
    tab.mode_combo.setCurrentIndex(tab.mode_combo.findData("mix_design"))
    assert not tab.ca_fraction_combo.isEnabled()

    # Only the PSD Clear path unlocks and restores the original selection.
    tab._on_psd_inputs_cleared()
    assert "zone" not in tab._psd_locked
    assert tab.grading_combo.isEnabled()
    assert tab.ca_fraction_combo.isEnabled()
    assert tab.grading_combo.currentIndex() == g_before
    assert tab.ca_fraction_combo.currentIndex() == c_before

