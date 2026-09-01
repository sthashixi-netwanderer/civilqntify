"""IS 10262:2019 Table 5 — the fine-aggregate grading zone must reach the
concrete design.

Table 5 (Clause 5.5) keys the coarse-aggregate volume fraction by the
fine-aggregate grading zone, classified per IS 383 Table 9. The form shows
the zone as the "Zone X — fraction" CA-volume row for IS mode; these tests
lock the full chain:

  visible Table 5 row  →  grading zone  →  ``_build_kwargs``  →  engine
  Step 5 (base fraction + Clause 5.5.1 w/c adjustment),

including the explicit ``ca_volume_fraction_override`` path and the
PSD-transferred zone lock.
"""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_table5_")
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


def _step(result, number: int) -> dict:
    for s in result.steps:
        if s.step_number == number:
            return s
    raise AssertionError(f"step {number} not found")


def _design(**overrides):
    from concrete_mix import design_mix_simple

    kwargs = dict(
        code="is10262",
        target_strength_mpa=30.0,
        slump_mm=75.0,
        nmsa=20,
        fine_agg_grading_zone="II",
    )
    kwargs.update(overrides)
    return design_mix_simple(**kwargs)


# ---------------------------------------------------------------------------
# Engine — Table 5 consumption
# ---------------------------------------------------------------------------


class TestEngineTable5:
    def test_table5_base_follows_zone(self):
        # IS 10262:2019 Table 5, 20 mm: I 0.60, II 0.62, III 0.64, IV 0.66
        z1 = _step(_design(fine_agg_grading_zone="I"), 5)
        z4 = _step(_design(fine_agg_grading_zone="IV"), 5)
        assert z1.inputs["ca_fraction_base"] == pytest.approx(0.60)
        assert z4.inputs["ca_fraction_base"] == pytest.approx(0.66)

    def test_table5_values_match_standard(self):
        from concrete_mix.codes.tables.is_tables import CA_VOLUME_FRACTION

        assert CA_VOLUME_FRACTION == {
            10: {"I": 0.48, "II": 0.50, "III": 0.52, "IV": 0.54},
            20: {"I": 0.60, "II": 0.62, "III": 0.64, "IV": 0.66},
            40: {"I": 0.69, "II": 0.71, "III": 0.72, "IV": 0.73},
        }

    def test_override_replaces_zone_lookup(self):
        # An explicit Table 5 row selection (the form's CA-volume combo,
        # or a PSD-locked zone) overrides the plain zone lookup.
        result = _design(ca_volume_fraction_override=0.66)
        step = _step(result, 5)
        assert step.inputs["ca_fraction_base"] == pytest.approx(0.66)
        assert "override" in step.description

    def test_wcr_adjustment_applies_to_override(self):
        from concrete_mix.codes.tables.is_tables import adjust_ca_volume_for_wcr

        result = _design(ca_volume_fraction_override=0.62)
        step = _step(result, 5)
        base = step.inputs["ca_fraction_base"]
        wc = step.inputs["wcr"]
        expected = adjust_ca_volume_for_wcr(base, wc)
        assert step.inputs["ca_fraction_adjusted"] == pytest.approx(expected)

    def test_zone_without_override_unchanged(self):
        result = _design(fine_agg_grading_zone="III")
        step = _step(result, 5)
        assert step.inputs["ca_fraction_base"] == pytest.approx(0.64)
        assert "override" not in step.description


# ---------------------------------------------------------------------------
# UI — the visible Table 5 row drives the zone
# ---------------------------------------------------------------------------


def _tab(qt):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    assert tab.code_combo.currentData() == "is10262"
    return tab


def _select_zone_row(tab, zone: str) -> None:
    for i in range(tab.ca_fraction_combo.count()):
        if tab.ca_fraction_combo.itemText(i).startswith(f"Zone {zone} "):
            tab.ca_fraction_combo.setCurrentIndex(i)
            return
    raise AssertionError(f"Zone {zone} row not found")


class TestUIZoneSync:
    def test_default_is_mode_shows_table5_rows(self, qt):
        tab = _tab(qt)
        assert tab.ca_fraction_combo.isVisibleTo(tab) or not tab.grading_combo.isVisibleTo(tab)
        assert tab.ca_fraction_combo.count() == 4
        # Default zone II keeps its row selected after the initial rebuild.
        assert tab.grading_combo.currentData() == "II"
        assert tab.ca_fraction_combo.currentText().startswith("Zone II")

    def test_row_selection_drives_zone_and_kwargs(self, qt):
        tab = _tab(qt)
        _select_zone_row(tab, "IV")
        assert tab.grading_combo.currentData() == "IV"
        kwargs = tab._build_kwargs()
        assert kwargs["fine_agg_grading_zone"] == "IV"
        assert kwargs["ca_volume_fraction_override"] == pytest.approx(0.66)

    def test_row_selection_changes_engine_result(self, qt):
        from concrete_mix import design_mix_simple

        tab = _tab(qt)
        _select_zone_row(tab, "III")
        result = design_mix_simple(**tab._build_kwargs())
        assert _step(result, 5).inputs["ca_fraction_base"] == pytest.approx(0.64)

    def test_nmsa_change_preserves_zone(self, qt):
        tab = _tab(qt)
        _select_zone_row(tab, "III")
        tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(10))
        # Same zone, new Table 5 row for the new NMSA (10 mm → 0.52).
        assert tab.grading_combo.currentData() == "III"
        assert tab.ca_fraction_combo.currentText().startswith("Zone III")
        assert tab.ca_fraction_combo.currentData() == pytest.approx(0.52)

    def test_non_is_mode_ignores_row_sync(self, qt):
        tab = _tab(qt)
        tab.code_combo.setCurrentIndex(tab.code_combo.findData("aci211"))
        # ca_fraction_combo is unused for ACI; the handler must not fight
        # the plain grading combo.
        tab.grading_combo.setCurrentIndex(tab.grading_combo.findData("III"))
        assert tab.grading_combo.currentData() == "III"


class TestPSDZoneLock:
    def test_lock_sets_both_combos(self, qt):
        tab = _tab(qt)
        tab._lock_zone("III")
        assert tab.grading_combo.currentData() == "III"
        assert tab.ca_fraction_combo.currentText().startswith("Zone III")
        assert tab.ca_fraction_combo.currentData() == pytest.approx(0.64)
        assert not tab.ca_fraction_combo.isEnabled()
        kwargs = tab._build_kwargs()
        assert kwargs["fine_agg_grading_zone"] == "III"
        assert kwargs["ca_volume_fraction_override"] == pytest.approx(0.64)

    def test_lock_survives_nmsa_change(self, qt):
        tab = _tab(qt)
        tab._lock_zone("III")
        tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(40))
        assert tab.grading_combo.currentData() == "III"
        assert tab.ca_fraction_combo.currentData() == pytest.approx(0.72)
        assert not tab.ca_fraction_combo.isEnabled()

    def test_unlock_restores_selection(self, qt):
        tab = _tab(qt)
        before_zone = tab.grading_combo.currentData()
        tab._lock_zone("IV")
        tab._on_psd_inputs_cleared()
        assert tab.grading_combo.currentData() == before_zone
        assert tab.ca_fraction_combo.isEnabled()

    def test_locked_zone_reaches_engine(self, qt):
        from concrete_mix import design_mix_simple

        tab = _tab(qt)
        tab._lock_zone("IV")
        result = design_mix_simple(**tab._build_kwargs())
        assert _step(result, 5).inputs["ca_fraction_base"] == pytest.approx(0.66)
