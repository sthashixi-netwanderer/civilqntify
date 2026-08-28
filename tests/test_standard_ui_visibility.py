"""Tests for standard-specific UI visibility in ConcreteMixTab."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication
from app.widgets.concrete_tab import ConcreteMixTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def tab(qapp):
    return ConcreteMixTab()


def test_doe_ui_visibility(tab):
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))

    # BRE 331 §1.2.4: Aggregate is classified ONLY as crushed or uncrushed.
    # No aggregate shape (Angular, Sub-angular, Gravel, etc.) and no dry-rodded bulk density.
    assert tab._lbl_shape.isHidden() is True
    assert tab.agg_shape_combo.isHidden() is True
    assert tab._lbl_ca_bulk.isHidden() is True
    assert tab.ca_bulk_spin.isHidden() is True

    # DOE coarse and fine aggregate types are visible
    assert tab._lbl_ca_type.isHidden() is False
    assert tab.ca_type_combo.isHidden() is False
    assert tab._lbl_fa_type.isHidden() is False
    assert tab.fa_type_combo.isHidden() is False

    # DOE % passing 600 µm is visible (Figure 6)
    assert tab._lbl_pct_passing_600um.isHidden() is False
    assert tab.pct_passing_600um_spin.isHidden() is False

    # Admixture SG is hidden for DOE (wet density method uses D - C - W)
    assert tab._lbl_admix_sg.isHidden() is True
    assert tab.admix_sg_spin.isHidden() is True

    # DOE Admixture types (BS 5075 / BS EN 934-2 / BRE 331 §5.3)
    doe_admix_data = [tab.admix_type_combo.itemData(i) for i in range(tab.admix_type_combo.count())]
    assert "" in doe_admix_data
    assert "plasticizer" in doe_admix_data
    assert "superplasticizer" in doe_admix_data
    assert "water_reducer_retarder" not in doe_admix_data

    # DOE SCM types (BRE 331 Part 3: pfa and ggbs only)
    doe_scm_data = [tab.scm_type_combo.itemData(i) for i in range(tab.scm_type_combo.count())]
    assert "" in doe_scm_data
    assert "fly_ash" in doe_scm_data  # pfa
    assert "ggbfs" in doe_scm_data    # ggbs
    assert "silica_fume" not in doe_scm_data
    assert "metakaolin" not in doe_scm_data

    # Other standard controls are hidden
    assert tab._lbl_fm.isHidden() is True
    assert tab.fm_spin.isHidden() is True
    assert tab._lbl_ca_frac.isHidden() is True
    assert tab.ca_fraction_combo.isHidden() is True
    assert tab._lbl_concrete_type.isHidden() is True
    assert tab.concrete_type_combo.isHidden() is True
    assert tab._lbl_exposure.isHidden() is True
    assert tab.exposure_combo.isHidden() is True
    assert tab._lbl_max_wc.isHidden() is True
    assert tab.max_wc_label.isHidden() is True
    assert tab._lbl_air.isHidden() is True
    assert tab.air_check.isHidden() is True
    assert tab._lbl_sulfate.isHidden() is True
    assert tab.sulfate_combo.isHidden() is True


def test_is10262_ui_visibility(tab):
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("is10262"))

    # IS 10262 shows Table 6 shape and Table 5 CA fraction (or grading combo)
    assert tab._lbl_shape.isHidden() is False
    assert tab.agg_shape_combo.isHidden() is False
    assert tab._lbl_ca_frac.isHidden() is False
    assert tab.ca_fraction_combo.isHidden() is False
    assert tab._lbl_concrete_type.isHidden() is False
    assert tab.concrete_type_combo.isHidden() is False
    assert tab._lbl_exposure.isHidden() is False
    assert tab.exposure_combo.isHidden() is False
    assert tab._lbl_max_wc.isHidden() is False
    assert tab.max_wc_label.isHidden() is False

    # Admixture SG is visible for IS 10262 (Annex A Step A-9(e) absolute volume method)
    assert tab._lbl_admix_sg.isHidden() is False
    assert tab.admix_sg_spin.isHidden() is False

    # IS 10262 Admixture types (IS 9103 & IS 10262 Annex G)
    is_admix_data = [tab.admix_type_combo.itemData(i) for i in range(tab.admix_type_combo.count())]
    assert "superplasticizer" in is_admix_data
    assert "plasticizer" in is_admix_data
    assert "air_entraining" in is_admix_data

    # IS 10262 SCM types (IS 3812 / IS 455 / IS 15388 / IS 16354)
    is_scm_data = [tab.scm_type_combo.itemData(i) for i in range(tab.scm_type_combo.count())]
    assert "fly_ash" in is_scm_data
    assert "ggbfs" in is_scm_data
    assert "silica_fume" in is_scm_data
    assert "metakaolin" in is_scm_data

    # DOE and ACI specific controls are hidden
    assert tab._lbl_ca_type.isHidden() is True
    assert tab.ca_type_combo.isHidden() is True
    assert tab._lbl_fa_type.isHidden() is True
    assert tab.fa_type_combo.isHidden() is True
    assert tab._lbl_pct_passing_600um.isHidden() is True
    assert tab.pct_passing_600um_spin.isHidden() is True
    assert tab._lbl_ca_bulk.isHidden() is True
    assert tab.ca_bulk_spin.isHidden() is True
    assert tab._lbl_fm.isHidden() is True
    assert tab.fm_spin.isHidden() is True
    assert tab._lbl_air.isHidden() is True
    assert tab.air_check.isHidden() is True
    assert tab._lbl_sulfate.isHidden() is True
    assert tab.sulfate_combo.isHidden() is True


def test_aci211_ui_visibility(tab):
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("aci211"))

    # ACI 211.1 shows dry-rodded bulk density, Fineness Modulus, air, sulfate
    assert tab._lbl_ca_bulk.isHidden() is False
    assert tab.ca_bulk_spin.isHidden() is False
    assert tab._lbl_fm.isHidden() is False
    assert tab.fm_spin.isHidden() is False
    assert tab._lbl_air.isHidden() is False
    assert tab.air_check.isHidden() is False
    assert tab._lbl_sulfate.isHidden() is False
    assert tab.sulfate_combo.isHidden() is False

    # Admixture SG is visible for ACI 211.1 (§4.5 / §4.7.7 absolute volume method)
    assert tab._lbl_admix_sg.isHidden() is False
    assert tab.admix_sg_spin.isHidden() is False

    # ACI 211.1 Admixture types (ASTM C494 / ASTM C260 & ACI 211.1 §6.3)
    aci_admix_data = [tab.admix_type_combo.itemData(i) for i in range(tab.admix_type_combo.count())]
    assert "water_reducer" in aci_admix_data
    assert "water_reducer_retarder" in aci_admix_data
    assert "superplasticizer" in aci_admix_data
    assert "air_entraining" in aci_admix_data

    # ACI 211.1 SCM types (ASTM C618 / C989 / C1240)
    aci_scm_data = [tab.scm_type_combo.itemData(i) for i in range(tab.scm_type_combo.count())]
    assert "fly_ash" in aci_scm_data
    assert "fly_ash_c" in aci_scm_data
    assert "ggbfs" in aci_scm_data
    assert "silica_fume" in aci_scm_data
    assert "metakaolin" in aci_scm_data

    # DOE and IS specific controls are hidden
    assert tab._lbl_shape.isHidden() is True
    assert tab.agg_shape_combo.isHidden() is True
    assert tab._lbl_ca_type.isHidden() is True
    assert tab.ca_type_combo.isHidden() is True
    assert tab._lbl_fa_type.isHidden() is True
    assert tab.fa_type_combo.isHidden() is True
    assert tab._lbl_pct_passing_600um.isHidden() is True
    assert tab.pct_passing_600um_spin.isHidden() is True
    assert tab._lbl_ca_frac.isHidden() is True
    assert tab.ca_fraction_combo.isHidden() is True
    assert tab._lbl_concrete_type.isHidden() is True
    assert tab.concrete_type_combo.isHidden() is True
    assert tab._lbl_exposure.isHidden() is True
    assert tab.exposure_combo.isHidden() is True
    assert tab._lbl_max_wc.isHidden() is True
    assert tab.max_wc_label.isHidden() is True
