"""PSD widget ASTM C33 compliance-gate tests — dialog + quality inputs."""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_astm_ui_")
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


def _make_astm_tab(tab, aggregate: str = "fine"):
    tab.standard_combo.setCurrentIndex(
        tab.standard_combo.findData("astm_c33")
    )
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData(aggregate))
    return tab


def _fill_and_plot(tab, masses, pan):
    sieves = tab._current_sieves()
    assert len(masses) == len(sieves)
    for i, m in enumerate(masses):
        tab.table.item(i, 1).setText(str(m))
    tab.table.item(len(sieves), 1).setText(str(pan))
    tab._on_compute_plot()


@pytest.fixture()
def dialog_calls(monkeypatch):
    """Record compliance-dialog invocations instead of opening a modal."""
    calls: list[list] = []
    monkeypatch.setattr(
        "app.widgets.psd_widget.ParticleSizeDistributionTab"
        "._show_astm_compliance_dialog",
        lambda self, checks: calls.append(list(checks)),
    )
    return calls


def test_quality_group_visibility_follows_standard_and_type(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    # IS 383 default — quality group visible on the IS fine page.
    assert not tab._quality_group.isHidden()
    assert tab._quality_stack.currentIndex() == 2
    assert "IS 383" in tab._quality_group.title()

    _make_astm_tab(tab, "fine")
    assert not tab._quality_group.isHidden()
    assert tab._quality_stack.currentIndex() == 0
    assert "ASTM C33" in tab._quality_group.title()

    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData("coarse"))
    assert tab._quality_stack.currentIndex() == 1

    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData("is383"))
    assert not tab._quality_group.isHidden()
    assert tab._quality_stack.currentIndex() == 3  # IS 383 coarse page


def test_astm_fine_nonconformance_opens_dialog_with_clause(qt, dialog_calls):
    """A fine sample failing Clause 6.2 (FM > 3.1) must open the dialog and
    the recorded checks must cite the clause."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "fine")

    # FM = 3.57 → above the 3.1 maximum of Clause 6.2.
    _fill_and_plot(tab, [0, 5, 20, 35, 20, 12, 3], pan=5)

    assert len(dialog_calls) == 1
    checks = dialog_calls[0]
    assert tab._astm_checks == checks
    fm_fail = [
        c
        for c in checks
        if c.clause == "6.2" and "fineness modulus" in c.title.lower()
    ]
    assert fm_fail and fm_fail[0].failed
    assert "3.1" in fm_fail[0].detail


def test_astm_fine_conforming_no_dialog(qt, dialog_calls):
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    from concrete_mix.validation.astm_c33 import FAIL

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "fine")

    # Conforming ASTM C33 fine sand: FM 3.05, all sieves in band.
    _fill_and_plot(tab, [0, 2, 10, 30, 25, 20, 8], pan=5)

    assert dialog_calls == []
    assert tab._astm_checks
    assert not [c for c in tab._astm_checks if c.status == FAIL]


def test_astm_table_1_failure_reported_via_dialog(qt, dialog_calls):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "fine")
    tab.fine_clay_spin.setValue(3.5)  # Table 1 max 3.0 %

    _fill_and_plot(tab, [0, 2, 10, 30, 25, 20, 8], pan=5)

    assert len(dialog_calls) == 1
    clay = [
        c
        for c in dialog_calls[0]
        if c.clause == "Table 1 (7.1)" and "clay" in c.title.lower()
    ]
    assert clay and clay[0].failed
    assert "3.5" in clay[0].measured


def test_astm_coarse_table_3_failure_reported_via_dialog(qt, dialog_calls):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "coarse")
    # Default band: 20 mm (Size 67). Default class: 3S.
    # Clay 2.0 % passes alone; chert 6.0 % exceeds the 3S 5.0 % limit and
    # the sum column (2.0 + 6.0 = 8.0 % > 7.0 %) also fails.
    tab.coarse_clay_spin.setValue(2.0)
    tab.coarse_chert_spin.setValue(6.0)

    _fill_and_plot(
        tab,
        [0, 0, 0, 0, 0, 0, 0, 8, 30, 40, 15, 4, 2, 1],
        pan=0,
    )

    assert len(dialog_calls) == 1
    chert = [
        c for c in dialog_calls[0] if "chert" in c.title.lower()
    ]
    assert chert and chert[0].failed
    assert chert[0].clause == "Table 3 (11.1)"
    total = [c for c in dialog_calls[0] if "sum" in c.title.lower()]
    assert total and total[0].failed
    assert "8.0" in total[0].measured


def test_is383_analysis_runs_compliance_checks(qt, dialog_calls):
    """IS 383 now has its own evaluator: a conforming analysis stays
    silent (status-bar summary), a grading failure beyond the Clause 6.3
    tolerance opens the clause-cited dialog."""
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()

    # Fully in-zone Zone II sand (100/98/90/70/45/20/5 % passing):
    # no failure → no dialog, checks recorded with no FAIL status.
    _fill_and_plot(tab, [0, 20, 80, 200, 250, 250, 150], pan=50)
    assert dialog_calls == []
    assert tab._astm_checks
    assert not [c for c in tab._astm_checks if c.failed]

    # Out-of-band sample (1.18 mm 7.5 points below the Zone II limit —
    # beyond the Clause 6.3 tolerance) → dialog with the cited clause.
    _fill_and_plot(tab, [0, 5, 45, 210, 60, 70, 105], pan=5)
    assert len(dialog_calls) == 1
    grading = [c for c in dialog_calls[0] if c.clause.startswith("6.3")]
    assert grading and grading[0].failed
    assert tab._astm_checks == dialog_calls[0]


def test_coarse_sum_label_updates_live(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "coarse")

    assert tab.coarse_sum_label.text() == "—"
    tab.coarse_clay_spin.setValue(2.5)
    tab.coarse_chert_spin.setValue(3.0)
    assert tab.coarse_sum_label.text() == "5.5 %"


def test_gathered_fine_inputs_reflect_ui_state(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "fine")

    inputs = tab._gather_fine_quality_inputs()
    assert inputs.clay_lumps_pct is None  # "not tested"
    assert inputs.concrete_subject_to_abrasion is True  # 4.2.4.3 default
    assert inputs.organic_status == "not_tested"

    tab.fine_clay_spin.setValue(2.4)
    tab.fine_abrasion_check.setChecked(False)
    tab.fine_manufactured_check.setChecked(True)
    tab.fine_organic_combo.setCurrentIndex(
        tab.fine_organic_combo.findData("darker_c87")
    )
    assert tab.fine_c87_spin.isEnabled()
    tab.fine_c87_spin.setValue(96.5)

    inputs = tab._gather_fine_quality_inputs()
    assert inputs.clay_lumps_pct == 2.4
    assert inputs.concrete_subject_to_abrasion is False
    assert inputs.manufactured_sand_dust_of_fracture is True
    assert inputs.organic_status == "darker_c87"
    assert inputs.c87_relative_strength_pct == 96.5


def test_gathered_coarse_inputs_reflect_ui_state(qt):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    _make_astm_tab(tab, "coarse")

    tab.coarse_class_combo.setCurrentIndex(
        tab.coarse_class_combo.findData("4S")
    )
    tab.coarse_slag_check.setChecked(True)
    tab.coarse_slag_weight_spin.setValue(1150.0)

    inputs = tab._gather_coarse_quality_inputs()
    assert inputs.class_designation == "4S"
    assert inputs.is_slag is True
    assert inputs.slag_unit_weight_kg_m3 == 1150.0
    assert inputs.chert_pct is None

    # Weighted-limit fields only count when the option is enabled.
    tab.coarse_weighted_check.setChecked(True)
    tab.coarse_p_spin.setValue(40.0)
    inputs = tab._gather_coarse_quality_inputs()
    assert inputs.p_sand_pct == 40.0
    assert inputs.t_fine_limit_pct == 3.0


def test_compliance_dialog_renders_clause_citations(qt):
    from PyQt6.QtWidgets import QLabel, QTableWidget

    from app.widgets.astm_c33_compliance_dialog import ASTM_C33ComplianceDialog
    from concrete_mix.codes.tables.grading_bands import get_astm_coarse_band
    from concrete_mix.engine.psd import ASTM_COARSE_SIEVES, compute_psd
    from concrete_mix.validation.astm_c33 import (
        CoarseQualityInputs,
        evaluate_astm_c33_coarse,
    )

    result = compute_psd(
        [0, 0, 0, 0, 0, 0, 0, 8, 30, 40, 15, 4, 2, 1],
        ASTM_COARSE_SIEVES,
        pan_mass=0.0,
    )
    inputs = CoarseQualityInputs(
        class_designation="4S", clay_lumps_pct=3.5, abrasion_loss_pct=55.0
    )
    checks = evaluate_astm_c33_coarse(result, get_astm_coarse_band(20), inputs)
    failures = [c for c in checks if c.failed]
    assert len(failures) == 2

    dialog = ASTM_C33ComplianceDialog(checks, "coarse")
    labels = dialog.findChildren(QLabel)
    text = " ".join(l.text() for l in labels)
    assert "does not conform to ASTM C33" in text
    assert "Clause Table 3 (11.1)" in text
    assert "3.5 % clay" in text
    assert "55.0 % abrasion" in text

    # The full checklist table carries every evaluated requirement.
    table = dialog.findChild(QTableWidget)
    assert table is not None
    assert table.rowCount() == len(checks)
    clauses = [table.item(r, 1).text() for r in range(table.rowCount())]
    assert "10.1 (Table 2)" in clauses
    assert "11.2" in clauses
