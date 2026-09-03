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


@pytest.fixture(autouse=True)
def _stub_compliance_dialog(monkeypatch):
    """Stub the modal compliance dialog so headless tests never block."""
    monkeypatch.setattr(
        "app.widgets.psd_widget.ParticleSizeDistributionTab"
        "._show_astm_compliance_dialog",
        lambda self, checks: None,
    )


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

    # Too coarse at 1.18 mm (52.2% < 55%) and 600 µm (30.0% < 35%);
    # all else conforms to IS 383 Zone II band.
    _fill_and_plot(tab, [0, 5, 30, 180, 100, 25, 60], pan=50)

    # The plot itself stays clean — no summary box overlaid on the axes
    texts = _plot_texts(tab)
    assert "Outside the standard band" not in texts

    # Summary lives in the banner below the plot
    assert not tab._result_panel._band_warning.isHidden()
    assert "Outside the standard band" in tab._result_panel._band_warning.text()
    assert (
        "600 µm: 30.0% < 35% limit — too coarse"
        in tab._result_panel._band_warning.text()
    )

    # Predicted adjustments are shown below the plot
    assert not tab._result_panel._corrections_label.isHidden()
    corr_text = tab._result_panel._corrections_label.text()
    assert "Suggested adjustments" in corr_text
    assert "600 µm" in corr_text

    # Offending points must be marked on the curve
    assert any(
        coll.get_offsets().shape[0] >= 1 for coll in tab._fig.axes[0].collections
    )


def test_conforming_gradation_has_no_warning(qt):
    """A gradation inside the band must not show the warning banner."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()

    # Zone II conforming sand (limits: 4.75 90–100, 2.36 75–100, 1.18 55–90,
    # 0.600 35–59, 0.300 8–30, 0.150 0–10)
    _fill_and_plot(tab, [0, 5, 25, 80, 100, 90, 50], pan=10)

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


def test_user_gradation_curve_is_smoothed_through_measured_points(qt):
    """The user's gradation must render as one smooth curve, not polyline
    segments: densely sampled between sieves, passing exactly through every
    measured %passing, within 0–100 % and never extended past the measured
    sieve range."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _fill_and_plot(tab, [0, 25, 100, 150, 120, 75, 25], pan=5)

    ax = tab._fig.axes[0]
    gradation = next(
        line for line in ax.lines if line.get_label() == "Your gradation"
    )
    x, y = (list(v) for v in gradation.get_data())

    result = tab._last_result
    # Densely sampled between sieves, not one vertex per sieve
    assert len(x) > 2 * len(result.sieve_sizes)
    # Not extended past the measured sieve range
    assert min(x) == pytest.approx(min(result.sieve_sizes))
    assert max(x) == pytest.approx(max(result.sieve_sizes))
    assert all(0.0 <= value <= 100.0 for value in y)
    # Curve passes exactly through every measured point
    for size, passing in zip(result.sieve_sizes, result.percent_passing):
        index = x.index(size)
        assert y[index] == pytest.approx(passing)


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
    # Sub-millimetre characteristic sizes are shown with the µ symbol
    # (D10 ≈ 360 µm, D30 ≈ 830 µm for this sample); D60 ≈ 1.7 mm stays mm.
    assert "µm" in texts
    assert "mm" in texts

    # Verify line count on axes includes the D-lines (horizontal and vertical reference lines)
    ax = tab._fig.axes[0]
    # Gradation line + 3 horizontal D-lines + 3 vertical D-lines + 3 D-marker points = 10 lines
    assert len(ax.lines) >= 7


def test_size_formatting_uses_micro_symbol_for_sub_mm():
    """UI convention: sub-millimetre sizes display with the µ symbol
    (600 µm, 150 µm), never a decimal-mm or bare-m spelling."""
    from app.widgets.psd_widget import _fmt_d_size, _fmt_size

    assert _fmt_size(10.0) == "10 mm"
    assert _fmt_size(4.75) == "4.75 mm"
    assert _fmt_size(0.600) == "600 µm"
    assert _fmt_size(0.150) == "150 µm"

    assert _fmt_d_size(37.5) == "37.5 mm"
    assert _fmt_d_size(4.75) == "4.75 mm"
    assert _fmt_d_size(1.18) == "1.18 mm"
    assert _fmt_d_size(0.83) == "830 µm"
    assert _fmt_d_size(0.1534) == "153 µm"


def test_uppercase_preserving_si_units():
    """The label-casing helper keeps SI micro symbols lowercase while
    uppercasing the rest (Qt's text-transform would render µ as "M")."""
    from app.styles import uppercase_preserving_si_units

    assert uppercase_preserving_si_units(
        "Material finer than 75-µm (No. 200) sieve"
    ) == "MATERIAL FINER THAN 75-µm (NO. 200) SIEVE"
    assert uppercase_preserving_si_units("FA Passing 600 µm (%)") == (
        "FA PASSING 600 µm (%)"
    )
    assert uppercase_preserving_si_units("Standard") == "STANDARD"


def test_uppercase_labels_keep_micro_symbol(qt):
    """Qt's text-transform maps µ to capital Greek Mu, so the quality
    labels used to render "75-µm" as "75-MM". Labels are cased in Python
    now — the micro symbol must survive on the built widgets."""
    from PyQt6.QtWidgets import QLabel

    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    texts = [lbl.text() for lbl in tab.findChildren(QLabel)]
    assert any("75-µm" in t for t in texts)
    assert not any("75-MM" in t or "\u039c" in t for t in texts)


def test_mix_design_label_keeps_micro_symbol(qt, monkeypatch):
    """The Mix Design tab's "FA Passing 600 µm (%)" label must keep its
    micro symbol under the uppercase label style."""
    import app.widgets.concrete_tab as ct

    monkeypatch.setattr(ct.QMessageBox, "information", _NoDialog.information)
    monkeypatch.setattr(ct.QMessageBox, "warning", _NoDialog.warning)

    from PyQt6.QtWidgets import QLabel

    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    texts = [lbl.text() for lbl in tab.findChildren(QLabel)]
    assert any("600 µm" in t for t in texts)
    assert not any("\u039c" in t for t in texts)


def test_use_in_mix_design_emits_standard_specific_payload(qt, monkeypatch):
    """"Use in Mix Design" must hand the mix-design form exactly the
    sieve-analysis-derived parameters each standard consumes:
    ACI FM (§4.3.5), IS 383 zone → Table 5, DOE %p600 (§1.2.5)."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    # ASTM C33 runs its compliance gate on compute; stub the modal dialog.
    monkeypatch.setattr(
        "app.widgets.psd_widget.ParticleSizeDistributionTab"
        "._show_astm_compliance_dialog",
        lambda self, checks: None,
    )

    tab = ParticleSizeDistributionTab()
    payloads: list[dict] = []
    tab._result_panel.apply_to_mix_design.connect(payloads.append)

    # IS 383 fine sample (36% > 30% passing at 600 µm):
    # cum retained % = 0,1,10,52,64,78,99 → p600 = 36.0 %.
    # IS 383:2016 sets no fineness-modulus requirement, so none is
    # calculated for the handoff either.
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    assert tab._result_panel._btn_apply.isEnabled()

    tab._result_panel._btn_apply.click()

    assert len(payloads) == 1
    p = payloads[0]
    assert p["aggregate_kind"] == "fine"
    assert p["band_standard"] == "is383"
    assert p["nominal_size_mm"] is None
    assert p["fineness_modulus"] is None  # IS 383: no FM requirement
    assert p["pct_passing_600um"] == pytest.approx(36.0)
    assert p["grading_zone"] in ("I", "II", "III", "IV")
    # This sample violates the Zone II band on two sieves.
    assert p["all_conform"] is False
    assert any("not calculated" in w for w in p["warnings"])

    # ASTM C33 fine aggregate is the one analysis with an FM requirement
    # (Clause 6.2: 2.3–3.1). The same masses on the ASTM Table 1 series
    # keep cum retained % = 0,1,10,52,64,78,99 → FM = 3.04.
    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    tab._result_panel._btn_apply.click()

    assert len(payloads) == 2
    p2 = payloads[1]
    assert p2["aggregate_kind"] == "fine"
    assert p2["band_standard"] == "astm_c33"
    assert p2["fineness_modulus"] == pytest.approx(3.04)

    # Clearing the panel must disarm the handoff button.
    tab._result_panel.clear()
    assert not tab._result_panel._btn_apply.isEnabled()


def test_fineness_modulus_calculated_only_where_required(qt, monkeypatch):
    """The FM is calculated only where a standard consumes it: ASTM C33
    fine aggregate (Clause 6.2 FM 2.3–3.1). IS 383:2016 grades fine
    aggregate by zone (Table 9) and ASTM C33 coarse aggregate carries no
    FM requirement — for those selections nothing is calculated, shown or
    exported."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    monkeypatch.setattr(
        "app.widgets.psd_widget.ParticleSizeDistributionTab"
        "._show_astm_compliance_dialog",
        lambda self, checks: None,
    )

    def fill_midpoint_mass(pan=0.0):
        """Put all mass on one middle sieve so any sieve stack computes."""
        sieves = tab._current_sieves()
        masses = [0.0] * len(sieves)
        masses[len(sieves) // 2] = 250.0
        _fill_and_plot(tab, masses, pan=pan)

    tab = ParticleSizeDistributionTab()

    # IS 383 fine (default) — zone grading, no FM.
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    assert tab._last_result.fineness_modulus is None
    assert tab._result_panel._fm_group.isHidden()

    # IS 383 coarse — still no FM requirement.
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))
    fill_midpoint_mass()
    assert tab._last_result.fineness_modulus is None
    assert tab._result_panel._fm_group.isHidden()

    # ASTM C33 coarse (Table 2) — no FM requirement either.
    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    assert tab.agg_combo.currentData() == "coarse"
    fill_midpoint_mass()
    assert tab._last_result.fineness_modulus is None
    assert tab._result_panel._fm_group.isHidden()

    # ASTM C33 fine — Clause 6.2 restricts the FM, so it is calculated
    # and its derivation working is shown.
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("fine"))
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    assert tab._last_result.fineness_modulus == pytest.approx(3.04)
    assert not tab._result_panel._fm_group.isHidden()


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



def test_reactivity_group_stays_compact_when_page_is_stretched(qt):
    """QStackedWidget sizes both ASTM quality pages to the taller (coarse)
    page. The fine page's surplus height must fall to a trailing stretch —
    not inflate the near-empty reactive-materials group into a giant box
    around a single dropdown."""
    from PyQt6.QtWidgets import QGroupBox

    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab.resize(390, 1200)
    tab.show()
    qt.processEvents()
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData("astm_c33"))
    qt.processEvents()

    def enclosing_group(w):
        p = w.parentWidget()
        while p is not None and not isinstance(p, QGroupBox):
            p = p.parentWidget()
        return p

    combo = tab.fine_reactivity_combo
    group = enclosing_group(combo)
    assert group is not None
    # Natural height = title + one combo row + group margins (measured
    # 79 px offscreen); the pre-fix inflated group was several hundred.
    assert group.height() <= combo.height() + 80


def test_astm_c33_fields_have_info_buttons(qt):
    """Every ASTM C33 quality field explains itself with an 'i' button
    (like the Mix Design tab), and the texts are grounded in the cited
    clauses of ASTM C 33 – 99."""
    from app.widgets.info_button import InfoButton
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData("astm_c33"))

    buttons = tab._quality_group.findChildren(InfoButton)
    texts = [b._info_text for b in buttons]
    # Fine + coarse pages plus the section header all carry one per field.
    assert len(buttons) >= 25

    joined = "\n".join(texts)
    for clause in ("6.4", "7.1", "7.2", "7.3", "8.1", "11.1",
                   "11.2", "Footnote A", "Footnote B", "Footnote C"):
        assert clause in joined, f"no info text cites {clause}"
    # Every button has a real explanation, not just a title.
    assert all(len(t) > 30 for t in texts)

    # Spot-check plain-language content read from the standard.
    assert any("0.20" in t and "6.4" in t for t in texts)      # FM variation
    assert any("95 %" in t and "7.2.3" in t for t in texts)    # C 87 escape
    assert any("1120 kg/m³" in t for t in texts)               # slag unit weight
    assert any("2.40" in t for t in texts)                     # light chert
