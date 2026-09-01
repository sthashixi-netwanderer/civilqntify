"""IS 383 PSD-tab UI tests — quality pages, compliance dispatch, history
round-trip and the mix-design transfer payload.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_is383_ui_")
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


# Zone II fine grading: 100 / 98 / 90 / 70 / 45 / 20 / 5 % passing.
_ZONE_II_MASSES = [0, 20, 80, 200, 250, 250, 150]  # + 50 g pan = 1000 g


def _fill(tab, masses, pan):
    sieves = tab._current_sieves()
    assert len(masses) == len(sieves)
    for i, m in enumerate(masses):
        tab.table.item(i, 1).setText(str(m))
    tab.table.item(len(sieves), 1).setText(str(pan))


def _tab(qt, db=None):
    from app.widgets.psd_widget import ParticleSizeDistributionTab

    tab = ParticleSizeDistributionTab()
    tab._history_db = db
    return tab


class TestQualityPages:
    def test_is383_shows_quality_group_by_default(self, qt):
        tab = _tab(qt)
        assert tab.standard_combo.currentData() == "is383"
        assert tab._quality_group.isVisible() or tab._quality_group.isVisibleTo(tab)
        # Default: IS 383 + fine → IS fine page (index 2).
        assert tab._quality_stack.currentIndex() == 2
        assert "IS 383" in tab._quality_group.title()

    def test_is383_coarse_page(self, qt):
        tab = _tab(qt)
        tab.agg_combo.setCurrentIndex(1)  # coarse
        assert tab._quality_stack.currentIndex() == 3

    def test_astm_pages_still_selected(self, qt):
        tab = _tab(qt)
        tab.standard_combo.setCurrentIndex(1)  # ASTM C33
        assert tab._quality_stack.currentIndex() == 0
        assert "ASTM C33" in tab._quality_group.title()
        tab.agg_combo.setCurrentIndex(1)
        assert tab._quality_stack.currentIndex() == 1

    def test_manufactured_block_toggles_with_source(self, qt):
        tab = _tab(qt)
        assert not tab._is_mfd_groups["is_fine"].isVisibleTo(tab)
        idx = tab.is_fine_source_combo.findData("manufactured")
        tab.is_fine_source_combo.setCurrentIndex(idx)
        assert tab._is_mfd_groups["is_fine"].isVisibleTo(tab)
        tab.is_fine_source_combo.setCurrentIndex(0)
        assert not tab._is_mfd_groups["is_fine"].isVisibleTo(tab)

    def test_live_total_labels(self, qt):
        tab = _tab(qt)
        tab.is_fine_coal_spin.setValue(1.5)
        tab.is_fine_clay_spin.setValue(1.0)
        assert "2.50" in tab.is_fine_total_label.text()
        tab.is_fine_fi_spin.setValue(20.0)
        tab.is_fine_ei_spin.setValue(15.0)
        assert "35.0" in tab.is_fine_combined_shape_label.text()


class TestComplianceDispatch:
    def test_is383_compute_populates_checks(self, qt, monkeypatch):
        tab = _tab(qt)
        monkeypatch.setattr(
            tab, "_show_astm_compliance_dialog", lambda checks: None
        )
        _fill(tab, _ZONE_II_MASSES, 50)
        tab._on_compute_plot()

        assert tab._astm_checks
        assert all(c.status != "fail" for c in tab._astm_checks)
        clauses = " ".join(c.clause for c in tab._astm_checks)
        assert "Table 2" in clauses          # deleterious substances
        assert "5.3" in clauses              # flakiness/elongation
        assert "5.5.1" in clauses            # soundness
        assert "5.6" in clauses              # AAR
        assert "6.3" in clauses              # grading zone w/ tolerance

    def test_is383_failure_opens_dialog_with_standard_name(self, qt, monkeypatch):
        tab = _tab(qt)
        shown: list[tuple[list, str]] = []

        def fake_show(checks):
            standard = (
                "IS 383" if tab.standard_combo.currentData() == "is383"
                else "ASTM C33"
            )
            shown.append((checks, standard))

        monkeypatch.setattr(tab, "_show_astm_compliance_dialog", fake_show)

        # Failing deleterious substance: coal & lignite over 1 %.
        tab.is_fine_coal_spin.setValue(2.5)
        _fill(tab, _ZONE_II_MASSES, 50)
        tab._on_compute_plot()

        assert shown, "non-conformance must open the dialog"
        checks, standard = shown[0]
        assert standard == "IS 383"
        failed = [c for c in checks if c.failed]
        assert any("Coal and lignite" in c.title for c in failed)

    def test_dialog_standard_name_in_title(self, qt):
        from app.widgets.astm_c33_compliance_dialog import ASTM_C33ComplianceDialog
        from concrete_mix.validation.is383 import (
            IS383FineQualityInputs,
            evaluate_is383_fine,
        )
        from concrete_mix.codes.tables.grading_bands import get_fine_band
        from concrete_mix.engine.psd import IS_FINE_SIEVES, compute_psd

        result = compute_psd(
            _ZONE_II_MASSES, IS_FINE_SIEVES, pan_mass=50.0
        )
        checks = evaluate_is383_fine(
            result, get_fine_band("II"),
            IS383FineQualityInputs(coal_lignite_pct=2.5), zone="II",
        )
        dlg = ASTM_C33ComplianceDialog(
            checks, "fine", standard_name="IS 383"
        )
        assert dlg.windowTitle().startswith("IS 383 Compliance")
        assert [c for c in checks if c.failed]


class TestHistoryRoundTrip:
    def test_is383_quality_saved_and_restored(self, qt, tmp_path):
        from history.db import HistoryDB

        db = HistoryDB(tmp_path / "h.db")
        tab = _tab(qt, db=db)

        tab.is_fine_source_combo.setCurrentIndex(
            tab.is_fine_source_combo.findData("crushed_stone_sand")
        )
        tab.is_fine_coal_spin.setValue(0.8)
        tab.is_fine_mica_spin.setValue(2.0)
        tab.is_fine_mica_tests_check.setChecked(True)
        idx = tab.is_fine_organic_combo.findData("fail_color_relieved")
        tab.is_fine_organic_combo.setCurrentIndex(idx)
        tab.is_fine_organic_strength_spin.setValue(97.0)
        tab.is_fine_fi_spin.setValue(18.0)
        tab.is_fine_ei_spin.setValue(20.0)
        idx = tab.is_fine_aar_combo.findData("mortar_bar_38c")
        tab.is_fine_aar_combo.setCurrentIndex(idx)
        tab.is_fine_aar_expansion_spin.setValue(0.04)
        idx = tab.is_fine_aar_age_combo.findData(90)
        tab.is_fine_aar_age_combo.setCurrentIndex(idx)

        _fill(tab, _ZONE_II_MASSES, 50)
        tab._on_compute_plot()

        rec = db.list_calculations(tab_type="psd")[0]
        calc_id = rec["id"]

        # Dirty the form, then load the record back.
        tab.is_fine_coal_spin.setValue(-1.0)
        tab.is_fine_mica_spin.setValue(-1.0)
        tab.is_fine_fi_spin.setValue(-1.0)
        tab.is_fine_source_combo.setCurrentIndex(0)

        tab.load_from_history(calc_id)

        assert tab.is_fine_source_combo.currentData() == "crushed_stone_sand"
        assert tab.is_fine_coal_spin.value() == pytest.approx(0.8)
        assert tab.is_fine_mica_spin.value() == pytest.approx(2.0)
        assert tab.is_fine_mica_tests_check.isChecked()
        assert tab.is_fine_organic_combo.currentData() == "fail_color_relieved"
        assert tab.is_fine_organic_strength_spin.value() == pytest.approx(97.0)
        assert tab.is_fine_fi_spin.value() == pytest.approx(18.0)
        assert tab.is_fine_ei_spin.value() == pytest.approx(20.0)
        assert tab.is_fine_aar_combo.currentData() == "mortar_bar_38c"
        assert tab.is_fine_aar_expansion_spin.value() == pytest.approx(0.04)
        assert tab.is_fine_aar_age_combo.currentData() == 90
        # IS checks were recomputed on load
        assert tab._astm_checks

    def test_is383_coarse_quality_saved(self, qt, tmp_path):
        from history.db import HistoryDB

        db = HistoryDB(tmp_path / "h.db")
        tab = _tab(qt, db=db)
        tab.agg_combo.setCurrentIndex(1)  # IS coarse

        tab.is_coarse_acv_spin.setValue(28.0)
        tab.is_coarse_wearing_check.setChecked(True)
        masses = [0, 0, 0, 50, 200, 200, 150, 320, 80]
        _fill(tab, masses, 0)
        tab._on_compute_plot()

        rec = db.get_calculation(db.list_calculations(tab_type="psd")[0]["id"])
        saved = json.loads(rec["input_json"])
        assert "is383_coarse_quality" in saved
        assert saved["is383_coarse_quality"]["crushing_value_pct"] == 28.0
        assert saved["is383_coarse_quality"]["wearing_surfaces"] is True


class TestMixDesignTransferPayload:
    def _captured_payload(self, qt, masses, pan):
        tab = _tab(qt)
        captured: list[dict] = []
        tab._result_panel.apply_to_mix_design.connect(captured.append)
        _fill(tab, masses, pan)
        tab._on_compute_plot()
        tab._result_panel._on_apply_to_mix()
        assert captured
        return captured[0]

    def test_conforming_zone_payload(self, qt):
        payload = self._captured_payload(qt, _ZONE_II_MASSES, 50)
        assert payload["grading_zone"] == "II"
        assert payload["zone_conforms"] is True
        assert payload["zone_deviations"] == []
        assert payload["zone_crushed_sand_relief"] is False

    def test_tolerated_deviation_reported_in_payload(self, qt):
        # 2.36 at 72 % — 3 points below Zone II's 75 limit, tolerated.
        masses = [0, 20, 260, 20, 250, 250, 150]
        payload = self._captured_payload(qt, masses, 50)
        assert payload["grading_zone"] == "II"
        assert payload["zone_conforms"] is True
        assert len(payload["zone_deviations"]) == 1
        assert "2.36" in payload["zone_deviations"][0]

    def test_beyond_tolerance_warns(self, qt):
        # 2.36 at 69 % — beyond the Clause 6.3 tolerance.
        masses = [0, 20, 290, 40, 200, 250, 150]
        payload = self._captured_payload(qt, masses, 50)
        assert payload["zone_conforms"] is False
        assert any("Clause 6.3" in w for w in payload["warnings"])

    def test_zone_iv_flagged(self, qt):
        # Zone IV: 4.75:99, 2.36:97, 1.18:95, 0.600:88, 0.300:30, 0.150:10
        masses = [0, 10, 20, 20, 70, 580, 180]  # + 120 g pan = 1000 g
        payload = self._captured_payload(qt, masses, 120)
        assert payload["grading_zone"] == "IV"


class TestMixTabApplyMessages:
    def _apply(self, qt, monkeypatch, payload):
        from PyQt6.QtWidgets import QMessageBox
        from app.widgets import concrete_tab as ctmod
        from app.widgets.concrete_tab import ConcreteMixTab

        shown: list[str] = []

        def fake_information(parent, title, text, *a, **k):
            shown.append(text)
            return QMessageBox.StandardButton.Ok

        monkeypatch.setattr(
            ctmod.QMessageBox, "information", staticmethod(fake_information)
        )
        tab = ConcreteMixTab()
        tab._on_psd_apply(payload)
        return tab, "\n".join(shown)

    def test_zone_iv_caution_shown_for_reinforced(self, qt, monkeypatch):
        tab, text = self._apply(qt, monkeypatch, {
            "aggregate_kind": "fine",
            "band_standard": "is383",
            "nominal_size_mm": None,
            "fineness_modulus": None,
            "grading_zone": "IV",
            "pct_passing_600um": 88.0,
            "all_conform": True,
            "warnings": [],
            "zone_conforms": True,
            "zone_deviations": [],
            "zone_crushed_sand_relief": False,
        })
        # Default concrete type is reinforced → strongest caution wording.
        assert tab.concrete_type_combo.currentData() == "reinforced"
        assert "Zone IV" in text
        assert "reinforced concrete" in text
        assert "Note 4" in text
        # The zone was transferred and locked (CA fraction combo disabled
        # for IS 10262 Table 5).
        assert "zone" in tab._psd_locked
        assert not tab.ca_fraction_combo.isEnabled()

    def test_deviations_and_relief_reported(self, qt, monkeypatch):
        _tab_widget, text = self._apply(qt, monkeypatch, {
            "aggregate_kind": "fine",
            "band_standard": "is383",
            "nominal_size_mm": None,
            "fineness_modulus": None,
            "grading_zone": "II",
            "pct_passing_600um": 45.0,
            "all_conform": True,
            "warnings": [],
            "zone_conforms": True,
            "zone_deviations": [
                "2.36 mm 72.0 % passing vs 75–100 % (3.0 % out, within "
                "the Clause 6.3 tolerance)"
            ],
            "zone_crushed_sand_relief": True,
        })
        assert "Clause 6.3" in text
        assert "20 %" in text          # crushed-stone-sand 150 µm relief
        assert "Note 1" in text

    def test_full_conformance_message(self, qt, monkeypatch):
        _tab_widget, text = self._apply(qt, monkeypatch, {
            "aggregate_kind": "fine",
            "band_standard": "is383",
            "nominal_size_mm": None,
            "fineness_modulus": None,
            "grading_zone": "II",
            "pct_passing_600um": 45.0,
            "all_conform": True,
            "warnings": [],
            "zone_conforms": True,
            "zone_deviations": [],
            "zone_crushed_sand_relief": False,
        })
        assert "conforms fully to Zone II" in text
