"""Tests for MaterialQuantifyTab subtabs and UI behaviors."""

from __future__ import annotations

import os
import tempfile
import pytest

_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_quant_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

from app.unit_preferences import UnitSystem
from app.widgets.material_quantify_tab import MaterialQuantifyTab


qapp = None


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


@pytest.fixture()
def fresh_prefs(qt):
    import app.unit_preferences as up_mod

    settings = up_mod.get_unit_prefs()._settings
    settings.clear()
    up_mod._instance = None
    p = up_mod.get_unit_prefs()
    p.set_system(UnitSystem.METRIC)
    yield p
    up_mod._instance = None


def test_material_quantify_tab_subtabs_exist(fresh_prefs):
    """Verify that both subtabs exist in MaterialQuantifyTab."""
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs

    assert tab._left_tabs.count() == 2
    assert tab._left_tabs.tabText(0) == "Design Mix Proportions"
    assert tab._left_tabs.tabText(1) == "Mix Ratios & Volume"


def test_mix_ratio_subtab_preset_change(fresh_prefs):
    """Selecting a preset on Mix Ratio subtab updates proportion spinboxes."""
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs

    # Switch to Mix Ratio subtab
    tab._left_tabs.setCurrentIndex(1)

    # Change preset to M25 (1:1:2)
    idx = tab.ratio_preset_combo.findText("M25 (1:1:2)")
    assert idx >= 0
    tab.ratio_preset_combo.setCurrentIndex(idx)

    assert tab.ratio_cement_spin.value() == 1.0
    assert tab.ratio_sand_spin.value() == 1.0
    assert tab.ratio_gravel_spin.value() == 2.0
    assert tab.ratio_wc_spin.value() == 0.45
    assert tab.ratio_dry_factor_spin.value() == 1.54
    assert "1 : 1 : 2" in tab.ratio_summary_lbl.text()

    # Change to Mortar 1:4
    idx_m = tab.ratio_preset_combo.findText("Mortar 1:4")
    assert idx_m >= 0
    tab.ratio_preset_combo.setCurrentIndex(idx_m)

    assert tab.ratio_cement_spin.value() == 1.0
    assert tab.ratio_sand_spin.value() == 4.0
    assert tab.ratio_gravel_spin.value() == 0.0
    assert tab.ratio_dry_factor_spin.value() == 1.33
    assert "Mortar Proportion: 1 : 4" in tab.ratio_summary_lbl.text()


def test_mix_ratio_custom_spin_change(fresh_prefs):
    """Manually changing ratio spinbox switches preset to Custom Ratio."""
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs
    tab._left_tabs.setCurrentIndex(1)

    tab.ratio_sand_spin.setValue(2.75)
    assert tab.ratio_preset_combo.currentText() == "Custom Ratio"
    assert "1 : 2.75 : 3" in tab.ratio_summary_lbl.text()


def test_mix_ratio_mode_switch_and_elements(fresh_prefs):
    """Switching mode to elements on Mix Ratio subtab shows elements table."""
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs
    tab._left_tabs.setCurrentIndex(1)

    # Switch to elements mode
    idx = tab.ratio_mode_combo.findData("elements")
    tab.ratio_mode_combo.setCurrentIndex(idx)

    assert tab._grp_ratio_volume.isHidden() is True
    assert tab._grp_ratio_elements.isHidden() is False

    # Add element
    tab._add_ratio_element()
    assert tab._ratio_elem_table.rowCount() == 1
    elems = tab._get_ratio_elements()
    assert len(elems) == 1
    assert elems[0].length_m == 1.0

    # Remove element
    tab._ratio_elem_table.selectRow(0)
    tab._remove_ratio_element()
    assert tab._ratio_elem_table.rowCount() == 0


def test_mix_ratio_unit_preferences_update(fresh_prefs):
    """Unit preference change updates headers on both subtabs."""
    tab = MaterialQuantifyTab()
    tab.unit_prefs = fresh_prefs

    fresh_prefs.set_system(UnitSystem.IMPERIAL)
    tab.on_unit_changed()

    assert "yd³" in tab._elem_table.horizontalHeaderItem(5).text()
    assert "yd³" in tab._ratio_elem_table.horizontalHeaderItem(5).text()
    assert "in" in tab._elem_table.horizontalHeaderItem(1).text()
    assert "in" in tab._ratio_elem_table.horizontalHeaderItem(1).text()
