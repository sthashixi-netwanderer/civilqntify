"""Tests for the per-standard characteristic-strength dropdown.

Strength is a closed set per code: whatever the user sees in the combo is
exactly what reaches the engine, every listed value is one the standard
actually defines, and there is no way to type something else.
"""

from __future__ import annotations

import os
import tempfile

# Isolate QSettings storage BEFORE any Qt/app import so tests never touch
# the developer's real CivilQntify settings.
_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_grade_test_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", _TMP_CONFIG)
os.environ.setdefault("HOME", _TMP_CONFIG)

import pytest

qapp = None  # set in fixture


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


@pytest.fixture()
def metric_prefs(qt):
    """Unit preferences pinned to metric, so item labels are deterministic."""
    import app.unit_preferences as up_mod

    up_mod._instance = None
    prefs = up_mod.get_unit_prefs()
    prefs.set_system(up_mod.UnitSystem("metric"))
    yield prefs
    up_mod._instance = None


@pytest.fixture()
def imperial_prefs(metric_prefs):
    from app.unit_preferences import UnitSystem

    metric_prefs.set_system(UnitSystem("imperial"))
    yield metric_prefs


def _values(combo) -> list[float]:
    """The metric MPa value behind every item, in display order."""
    return [combo.itemData(i) for i in range(combo.count())]


def _labels(combo) -> list[str]:
    return [combo.itemText(i) for i in range(combo.count())]


def _enabled(combo) -> list[str]:
    """Labels of the items the active exposure class still permits."""
    model = combo.model()
    return [
        combo.itemText(i)
        for i in range(combo.count())
        if model.item(i).isEnabled()
    ]


class TestGradeSets:
    """Each standard offers exactly the strengths it defines."""

    def test_is10262_offers_m10_to_m80(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        assert _values(combo) == [float(g) for g in range(10, 85, 5)]
        assert _labels(combo)[0].startswith("M10")
        assert _labels(combo)[-1].startswith("M80")

    def test_aci211_offers_the_318_increment_grid(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("aci211")
        labels = _labels(combo)
        assert labels[0].startswith("2,500 psi")
        assert labels[-1].startswith("8,000 psi")
        # Every minimum the ACI exposure tables impose must be selectable,
        # or raising an exposure class would make the design unsatisfiable.
        for psi in (2500, 3500, 4000, 4500, 5000):
            assert any(lbl.startswith(f"{psi:,} psi") for lbl in labels), psi

    def test_doe_offers_20_to_60_in_5_mpa_steps(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("doe")
        assert _values(combo) == [float(v) for v in range(20, 65, 5)]

    def test_unknown_code_offers_nothing(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        # Degrades to "no choices" rather than raising on an unrecognised
        # standard, so a future code cannot break the form at import time.
        assert _values(StrengthGradeCombo("unknown")) == []


class TestCodeSwitching:
    """Changing standard reloads the list; the value follows when it can."""

    def test_value_carries_across_when_both_codes_offer_it(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(30.0)
        combo.populate("doe", keep_value=True)
        assert combo.value() == pytest.approx(30.0)

    def test_value_snaps_to_nearest_when_the_new_code_lacks_it(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(10.0)  # below the DoE grid entirely
        combo.populate("doe", keep_value=True)
        assert combo.value() == pytest.approx(20.0)

    def test_switch_emits_so_downstream_readouts_refresh(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        seen: list[float] = []
        combo.valueChanged.connect(seen.append)
        combo.populate("aci211", keep_value=True)
        assert seen
        assert seen[-1] == pytest.approx(combo.value())


class TestExposureGating:
    """Below-minimum grades are greyed, not hidden and not remapped."""

    def test_no_exposure_class_means_no_floor(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        assert len(_enabled(combo)) == combo.count()

    def test_is_severe_gates_grades_below_m30(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.set_minimum(30.0)  # IS 456 Table 5, severe + reinforced
        enabled = _enabled(combo)
        assert enabled[0].startswith("M30")
        assert not any(lbl.startswith("M25") for lbl in enabled)

    def test_aci_c2_gates_grades_below_5000_psi(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("aci211")
        combo.set_minimum(34.47)  # 5000 psi, the C2 floor
        enabled = _enabled(combo)
        assert enabled[0].startswith("5,000 psi")
        assert not any(lbl.startswith("4,500 psi") for lbl in enabled)

    def test_gating_never_moves_the_selection(self, qt):
        """A grade a newly-chosen class forbids stays selected and greyed.

        Remapping it would hide the clash; the engine's existing, more
        specific message at Calculate is the better place to surface it.
        """
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(25.0)
        combo.set_minimum(30.0)
        assert combo.value() == pytest.approx(25.0)
        assert combo.currentText().startswith("M25")
        assert not combo.model().item(combo.currentIndex()).isEnabled()


class TestSavedRecords:
    """A record saved before the field became a dropdown still round-trips."""

    def test_off_list_value_becomes_a_marked_extra_item(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(33.7)  # no M-grade matches
        assert combo.value() == pytest.approx(33.7)
        assert "saved record" in combo.currentText()
        assert combo.count() == 16  # 15 grades plus the extra

    def test_on_list_value_adds_no_extra_item(self, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(30.0)
        assert combo.count() == 15
        assert "saved record" not in combo.currentText()

    def test_extra_is_dropped_when_the_standard_changes(self, qt):
        """An off-list value belongs to the code it was recorded under."""
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(33.7)
        combo.populate("doe", keep_value=True)
        assert combo.value() in _values(combo)
        assert "saved record" not in combo.currentText()


class TestUnitDisplay:
    """Imperial re-renders the labels; it never converts the stored value."""

    def test_imperial_labels_carry_psi_while_value_stays_mpa(
        self, imperial_prefs, qt
    ):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(30.0)
        assert combo.currentText() == "M30 · 4,351 psi"
        assert combo.value() == pytest.approx(30.0)

    def test_metric_labels_stay_metric(self, metric_prefs, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        combo = StrengthGradeCombo("is10262")
        combo.setValue(30.0)
        assert combo.currentText() == "M30 · 30 MPa"
        assert combo.value() == pytest.approx(30.0)

    def test_aci_leads_with_its_native_psi_in_both_modes(self, metric_prefs, qt):
        from app.widgets.strength_grade_combo import StrengthGradeCombo

        # ACI specifies f'c in psi, so that is the designation the engineer
        # is matching against their drawings, in either display mode. Read
        # item 0, not currentText(): a fresh combo starts from the IS M25
        # default and snaps to the nearest ACI grade, 3,600 psi.
        combo = StrengthGradeCombo("aci211")
        assert combo.itemText(0) == "2,500 psi · 17.2 MPa"
