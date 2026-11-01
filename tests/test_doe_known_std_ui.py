"""DOE known-standard-deviation GUI input (BRE 331:1997 clause 4.4, Item 1.2).

The DOE panel must let the user declare that s is known from previous
control data and enter it — clause 7.4 Example 4 works exactly this way
("Previous control data indicated an expected standard deviation of
5 N/mm² and this is used in Item 1.2"). A known s governs the margin and
bypasses the Figure 3 record-count route; the engine floors it at the
Figure 3 line-B value.
"""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication

from concrete_mix import design_mix_simple
from concrete_mix.models.materials import (
    AggregateShape,
    Cement,
    CementType,
    CoarseAggregate,
    FineAggregate,
)
from concrete_mix.models.mix_input import MixDesignInput


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def tab(qapp):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    return tab


def test_known_std_controls_are_doe_only_and_default_off(tab):
    """The checkbox and its s spin exist, show only for DOE, and start
    inactive (Figure 3 by record count remains the default route)."""
    assert not tab.std_known_check.isHidden()
    assert not tab.std_known_check.isChecked()
    assert tab.std_dev_spin.isHidden()  # spin follows the checkbox
    assert not tab.n_cubes_spin.isEnabled() is False  # n route active

    tab.code_combo.setCurrentIndex(tab.code_combo.findData("aci211"))
    assert tab.std_known_check.isHidden()


def test_build_kwargs_auto_when_unchecked(tab):
    """Unchecked: engine derives s from the record count (status quo)."""
    kwargs = tab._build_kwargs()
    assert kwargs["std_deviation"] is None
    assert kwargs["num_test_cubes"] == tab.n_cubes_spin.value()


def test_build_kwargs_known_s_bypasses_figure3_route(tab):
    """Checked: the entered s is supplied and n is not (clause 4.4 — the
    known s governs; the Figure 3 record-count line is not used)."""
    tab.std_known_check.setChecked(True)
    tab.std_dev_spin.setValue(5.0)

    kwargs = tab._build_kwargs()
    assert kwargs["std_deviation"] == 5.0
    assert kwargs["num_test_cubes"] is None
    assert not tab.std_dev_spin.isHidden()
    assert tab.n_cubes_spin.isEnabled() is False

    tab.std_known_check.setChecked(False)
    assert tab.std_dev_spin.isHidden()
    assert tab.n_cubes_spin.isEnabled()


def test_applied_s_display_shows_known_value_and_line_b_floor(tab):
    """The applied-s readout mirrors the engine: a known s passes through
    unless it is below the Figure 3 line-B floor."""
    tab.strength_spin.setValue(50.0)

    tab.std_known_check.setChecked(True)
    tab.std_dev_spin.setValue(5.0)
    assert "5.0" in tab.std_dev_display.text()
    assert "previous" in tab.std_dev_display.text().lower()

    tab.std_dev_spin.setValue(3.0)  # below the Line B floor (4 MPa)
    # UnitSpinBox.setValue() bypasses Qt's valueChanged (only user edits
    # emit it) — refresh the readout through its slot as the engine path
    # sees it.
    tab._update_std_dev_display()
    assert "4.0" in tab.std_dev_display.text()
    assert "raised" in tab.std_dev_display.text().lower()


def test_bre_example4_reproduces_through_gui_kwargs(tab):
    """§7.4 Example 4 end-to-end through the GUI kwargs: known s = 5,
    fc 50 @ 7 days, 1 % defectives, class 52.5, 10 mm, slump 30–60,
    45 % passing 600 µm, max cement 550 → C3 = 580 > 550 → the design
    stops (clause 5.3)."""
    tab.strength_spin.setValue(50.0)
    tab.defective_pct_spin.setValue(1.0)
    tab.age_combo.setCurrentIndex(tab.age_combo.findData(7))
    tab.cement_type_combo.setCurrentIndex(
        tab.cement_type_combo.findData("GRADE_52_5N")
    )
    tab.slump_spin.setValue(45.0)
    tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(10))
    tab.ca_type_combo.setCurrentIndex(tab.ca_type_combo.findData("crushed"))
    tab.fa_type_combo.setCurrentIndex(tab.fa_type_combo.findData("uncrushed"))
    tab.pct_passing_600um_spin.setValue(45.0)
    tab.max_cement_spin.setValue(550.0)
    tab.std_known_check.setChecked(True)
    tab.std_dev_spin.setValue(5.0)

    with pytest.raises(ValueError, match="580 kg/m³.*550"):
        design_mix_simple(**tab._build_kwargs())


def test_margin_known_deactivates_the_known_s_route(tab):
    """A known margin M bypasses k×s entirely (clause 4.4, C2) — the
    known-s route must stand down while it is active."""
    tab.margin_known_check.setChecked(True)
    assert tab.std_known_check.isEnabled() is False

    tab.margin_known_check.setChecked(False)
    assert tab.std_known_check.isEnabled()


def test_history_roundtrip_restores_known_s(tab, qapp):
    """Loading a saved design with std_deviation re-checks the box and
    restores the entered s (and leaves the margin box untouched)."""
    inp = MixDesignInput(
        code="doe",
        target_strength_mpa=50.0,
        characteristic_strength_mpa=50.0,
        slump_mm=45.0,
        defective_percent=1.0,
        std_deviation=5.0,
        age_days=7,
        cement=Cement(type=CementType.OPC_53),
        coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=10, specific_gravity=2.7,
            shape=AggregateShape.ANGULAR,
        ),
        fine_aggregate=FineAggregate(
            specific_gravity=2.7, pct_passing_600um=45.0,
            shape=AggregateShape.GRAVEL,
        ),
        max_cement_kg=550.0,
    )
    tab.apply_mix_input(inp)

    assert tab.std_known_check.isChecked()
    assert tab.std_dev_spin.value() == pytest.approx(5.0)
    assert not tab.margin_known_check.isChecked()
