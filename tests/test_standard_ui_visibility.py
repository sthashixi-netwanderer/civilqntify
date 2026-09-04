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


def test_input_sidebars_fit_their_360px_pane_floor(qapp):
    """No input sidebar may demand more width than the splitter's 360 px
    floor. Widgets whose minimum-size hints exceed it (non-wrapping
    checkbox labels, widest-item combo hints, long group-box titles)
    force the input column wider than the pane, so fields get clipped or
    pushed behind the pane edge when the sidebar is narrowed."""
    from PyQt6.QtWidgets import QScrollArea, QTabWidget

    from app.widgets.psd_widget import ParticleSizeDistributionTab

    def assert_fits(container, label):
        for sa in container.findChildren(QScrollArea):
            inner = sa.widget()
            if inner is None:
                continue
            width = inner.minimumSizeHint().width()
            assert width <= 360, (
                f"{label}: input content needs {width} px, "
                "more than the 360 px sidebar floor"
            )

    # PSD tab in its worst case: ASTM C33 with both quality pages built.
    psd = ParticleSizeDistributionTab()
    psd.standard_combo.setCurrentIndex(psd.standard_combo.findData("astm_c33"))
    assert_fits(psd, "PSD tab (ASTM C33)")

    # Concrete Mix and Material Quantify: every page of the left input
    # tab widget (identified by its 360 px floor).
    from app.widgets.concrete_tab import ConcreteMixTab
    from app.widgets.material_quantify_tab import MaterialQuantifyTab

    for parent_cls in (ConcreteMixTab, MaterialQuantifyTab):
        parent = parent_cls()
        for tabs in parent.findChildren(QTabWidget):
            if tabs.minimumWidth() != 360:
                continue
            for i in range(tabs.count()):
                assert_fits(
                    tabs.widget(i), f"{parent_cls.__name__}/{tabs.tabText(i)}"
                )

    # Cost Estimation: the input scroll (identified by its 360 px floor).
    from app.widgets.cost_estimation_tab import CostEstimationTab

    cost = CostEstimationTab()
    for sa in cost.findChildren(QScrollArea):
        if sa.minimumWidth() == 360:
            inner = sa.widget()
            assert inner is not None
            width = inner.minimumSizeHint().width()
            assert width <= 360, (
                f"CostEstimation input needs {width} px, "
                "more than the 360 px sidebar floor"
            )


def test_doe_ca_split_auto_selection(tab):
    """Verify coarse aggregate auto-splits for DOE: 3 for 40mm, 2 for 20mm, only in DOE."""
    # Start with DOE standard
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    assert tab._lbl_ca_split.isHidden() is False
    assert tab.ca_split_combo.isHidden() is False

    # Default NMSA is 20 mm -> auto split to 2 ("10+20")
    tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(20))
    assert tab.ca_split_combo.currentData() == "10+20"
    # Verify model enablement: "10+20" enabled, "10+20+40" disabled
    model = tab.ca_split_combo.model()
    assert model.item(1).isEnabled() is True   # 10+20
    assert model.item(2).isEnabled() is False  # 10+20+40

    # NMSA = 40 mm -> auto split to 3 ("10+20+40")
    tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(40))
    assert tab.ca_split_combo.currentData() == "10+20+40"
    assert model.item(1).isEnabled() is False  # 10+20
    assert model.item(2).isEnabled() is True   # 10+20+40

    # NMSA = 10 mm -> no split ("")
    tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(10))
    assert tab.ca_split_combo.currentData() == ""
    assert model.item(1).isEnabled() is False
    assert model.item(2).isEnabled() is False

    # Switch to IS 10262 -> CA split hidden and reset to ""
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("is10262"))
    assert tab._lbl_ca_split.isHidden() is True
    assert tab.ca_split_combo.isHidden() is True
    assert tab.ca_split_combo.currentData() == ""

    # Changing NMSA in IS does not activate DOE split
    tab.nmsa_combo.setCurrentIndex(tab.nmsa_combo.findData(40))
    assert tab.ca_split_combo.currentData() == ""

    # Switch back to DOE with NMSA=40 -> automatically selects 3 ("10+20+40")
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    assert tab._lbl_ca_split.isHidden() is False
    assert tab.ca_split_combo.isHidden() is False
    assert tab.ca_split_combo.currentData() == "10+20+40"


def test_scm_inputs_disabled_when_none(tab):
    """Verify SCM fields are grayed out when SCM type is 'None' and enabled when selected."""
    # Ensure SCM is None
    tab.scm_type_combo.setCurrentIndex(tab.scm_type_combo.findData(""))
    assert tab.scm_pct_spin.isEnabled() is False
    assert tab.scm_sg_spin.isEnabled() is False
    assert tab._lbl_scm_pct.isEnabled() is False
    assert tab._lbl_scm_sg.isEnabled() is False
    assert tab.scm_pct_spin.value() == 0.0

    # Select Fly Ash
    idx = tab.scm_type_combo.findData("fly_ash")
    assert idx >= 0
    tab.scm_type_combo.setCurrentIndex(idx)
    assert tab.scm_pct_spin.isEnabled() is True
    assert tab.scm_sg_spin.isEnabled() is True
    assert tab._lbl_scm_pct.isEnabled() is True
    assert tab._lbl_scm_sg.isEnabled() is True

    # Select None again -> disabled and reset
    tab.scm_type_combo.setCurrentIndex(tab.scm_type_combo.findData(""))
    assert tab.scm_pct_spin.isEnabled() is False
    assert tab.scm_sg_spin.isEnabled() is False
    assert tab._lbl_scm_pct.isEnabled() is False
    assert tab._lbl_scm_sg.isEnabled() is False
    assert tab.scm_pct_spin.value() == 0.0


def test_admixture_inputs_disabled_when_none(tab):
    """Verify Admixture fields are grayed out when Admixture type is 'None' and enabled when selected."""
    # Ensure Admixture is None
    tab.admix_type_combo.setCurrentIndex(tab.admix_type_combo.findData(""))
    assert tab.admix_dosage_spin.isEnabled() is False
    assert tab.admix_spin.isEnabled() is False
    assert tab.admix_sg_spin.isEnabled() is False
    assert tab.admix_water_spin.isEnabled() is False
    assert tab.reduced_water_label.isEnabled() is False
    assert tab._lbl_admix_dosage.isEnabled() is False
    assert tab._lbl_admix_reduction.isEnabled() is False
    assert tab._lbl_reduced_water.isEnabled() is False
    assert tab.admix_spin.value() == 0.0
    assert tab.reduced_water_label.text() == "—"

    # Select Superplasticizer
    idx = tab.admix_type_combo.findData("superplasticizer")
    assert idx >= 0
    tab.admix_type_combo.setCurrentIndex(idx)
    assert tab.admix_dosage_spin.isEnabled() is True
    assert tab.admix_spin.isEnabled() is True
    assert tab.admix_sg_spin.isEnabled() is True
    assert tab.reduced_water_label.isEnabled() is True
    assert tab._lbl_admix_dosage.isEnabled() is True
    assert tab._lbl_admix_reduction.isEnabled() is True
    assert tab._lbl_reduced_water.isEnabled() is True

    # Select None again -> disabled and reset
    tab.admix_type_combo.setCurrentIndex(tab.admix_type_combo.findData(""))
    assert tab.admix_dosage_spin.isEnabled() is False
    assert tab.admix_spin.isEnabled() is False
    assert tab.admix_sg_spin.isEnabled() is False
    assert tab.reduced_water_label.isEnabled() is False
    assert tab.admix_spin.value() == 0.0
    assert tab.reduced_water_label.text() == "—"

