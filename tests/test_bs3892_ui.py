"""BS 3892-1 pfa quality-check dialog and mix-tab wiring tests."""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_bs3892_ui_")
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["HOME"] = _TMP

from app.widgets.bs3892_compliance_dialog import BS3892ComplianceDialog


_qapp = None


@pytest.fixture()
def qt():
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication

        _qapp = QApplication.instance() or QApplication([])
    yield _qapp


def test_dialog_lists_all_eleven_properties(qt):
    dlg = BS3892ComplianceDialog()
    table = dlg._table
    assert table.rowCount() == 11
    clauses = [table.item(r, 1).text() for r in range(table.rowCount())]
    assert clauses == [
        "5", "6", "7", "8", "9", "10", "11", "12.1", "12.2", "12.3", "12.4",
    ]
    # Empty form: everything "— n/a", neutral banner.
    assert all("n/a" in table.item(r, 0).text() for r in range(table.rowCount()))


def test_dialog_live_recompute_flags_major_defect(qt):
    dlg = BS3892ComplianceDialog()
    dlg._spins["moisture_pct"].setValue(0.8)  # > 0.6 % major-defect level
    row5 = next(r for r in range(dlg._table.rowCount())
                if dlg._table.item(r, 1).text() == "5")
    assert dlg._table.item(row5, 0).text().startswith("✗")
    assert "major defect" in dlg._banner.text().lower()
    assert "G.6" in dlg._banner.text()

    dlg._spins["moisture_pct"].setValue(0.3)
    assert dlg._table.item(row5, 0).text().startswith("✓")
    assert "NOT met" not in dlg._banner.text()


def test_dialog_all_evaluated_shows_success(qt):
    dlg = BS3892ComplianceDialog()
    values = {
        "moisture_pct": 0.3, "fineness_45um_pct": 8.0,
        "particle_density_kg_m3": 2300.0, "water_requirement_pct": 92.0,
        "strength_factor": 0.85, "setting_time_paste_min": 170.0,
        "setting_time_cement_min": 160.0, "soundness_expansion_mm": 2.0,
        "so3_pct": 1.2, "loi_pct": 5.0, "chloride_pct": 0.03, "cao_pct": 5.0,
    }
    for attr, v in values.items():
        dlg._spins[attr].setValue(v)
    statuses = [dlg._table.item(r, 0).text() for r in range(dlg._table.rowCount())]
    assert all(s.startswith("✓") for s in statuses)
    assert dlg._banner.property("statusKind") == "pass"


def test_mix_tab_button_enabled_only_for_pfa(qt, monkeypatch):
    from app.widgets.concrete_tab import ConcreteMixTab

    opened: list = []

    class _FakeDialog:
        # The real dialog takes the parent widget; the fake must accept it
        # too — an exception escaping a Qt slot aborts PyQt ≥ 6.5.
        def __init__(self, *args, **kwargs) -> None:
            pass

    monkeypatch.setattr(
        "app.widgets.concrete_tab.BS3892ComplianceDialog", _FakeDialog
    )
    monkeypatch.setattr(
        "app.widgets.concrete_tab.open_detached",
        lambda dlg: opened.append(dlg),
    )

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))

    btn = tab.bs3892_check_btn
    assert not btn.isEnabled()  # SCM = None

    tab.scm_type_combo.setCurrentIndex(tab.scm_type_combo.findData("fly_ash"))
    assert btn.isEnabled()
    btn.click()
    assert len(opened) == 1 and isinstance(opened[0], _FakeDialog)

    tab.scm_type_combo.setCurrentIndex(tab.scm_type_combo.findData("ggbfs"))
    assert not btn.isEnabled()
