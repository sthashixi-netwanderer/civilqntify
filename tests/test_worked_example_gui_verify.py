"""GUI-level verification against every published worked example.

Each test feeds the standard's own worked-example inputs through the real
GUI form (ConcreteMixTab.apply_mix_input -> _build_kwargs), runs the engine,
and asserts:
  1. the engine reproduces the standard's printed quantities (within the
     documented digitisation / ceil-target tolerances), and
  2. the ResultPanel cards display exactly what the engine produced.

Reference documents (read-only ground truth, see AGENTS.md):
  - BRE 331:1997 §7 Examples 1-4 (DOE method)
  - IS 10262:2019 Annex A (M40 PPC), B (M40 fly ash), C (M40 GGBS),
    D (high-strength), E (SCC M30), F (mass M15)
  - ACI PRC-211.1-22 §9.2 Ex1, §9.3 Ex2 (binary fly ash), §9.4 Ex3
    (efficiency factor), §9.5 Ex4 (target paste volume)
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.models.materials import (
    Admixture, AdmixtureType, AggregateShape, Cement, CementType,
    CoarseAggregate, FineAggregate, SCM, SCMType,
)
from concrete_mix.models.mix_input import MixDesignInput
from app.widgets.concrete_tab import ConcreteMixTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def tab(qapp):
    t = ConcreteMixTab()
    t._left_tabs.setCurrentIndex(t._mixdesign_idx)
    return t


def _card_float(panel, key):
    return float(panel._cards[key]._value.text())


def _assert_gui_fidelity(tab, result):
    """ResultPanel cards must show exactly what the engine produced."""
    tab._result_panel.display_result(result)
    assert abs(_card_float(tab._result_panel, "cement") - result.cement_kg) < 0.15
    assert abs(_card_float(tab._result_panel, "water") - result.water_kg) < 0.15
    assert abs(_card_float(tab._result_panel, "fine_agg") - result.fine_aggregate_kg) < 0.15
    assert abs(_card_float(tab._result_panel, "coarse_agg") - result.coarse_aggregate_kg) < 0.15
    assert abs(_card_float(tab._result_panel, "target") - result.target_mean_strength_mpa) < 0.15


def _assert_kwargs_roundtrip(tab, inp):
    """Key worked-example inputs must survive the GUI form."""
    tab.apply_mix_input(inp)
    kwargs = tab._build_kwargs()
    assert kwargs["code"] == inp.code
    return kwargs


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.1 — Example 1: unrestricted design
# Printed: target 46, w/c 0.47, W 160, C 340, FA 515, CA 1385.
# Figure 6 digitisation reads 27.7% fines (chart reading 27%).
# ---------------------------------------------------------------------------
class TestGUIBREExample1:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="doe", target_strength_mpa=30.0,
            characteristic_strength_mpa=30.0, slump_mm=20.0,
            defective_percent=2.5, has_production_data=False,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.6,
                shape=AggregateShape.GRAVEL),
            fine_aggregate=FineAggregate(
                specific_gravity=2.6, pct_passing_600um=70.0,
                shape=AggregateShape.GRAVEL),
            w_c_ratio=0.55, min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert r.target_mean_strength_mpa == 46.0
        assert r.w_c_ratio == 0.47
        assert r.water_kg == 160
        assert r.cement_kg == 340
        assert abs(r.fine_aggregate_kg - 525) <= 12
        assert abs(r.coarse_aggregate_kg - 1375) <= 12
        kwargs = _assert_kwargs_roundtrip(tab, inp)
        assert kwargs["nmsa"] == 20
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.2 — Example 2: restricted by maximum W/C (0.50)
# Printed: target 35, w/c 0.50, W 160, C 320, FA 405, CA 1440.
# ---------------------------------------------------------------------------
class TestGUIBREExample2:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="doe", target_strength_mpa=25.0,
            characteristic_strength_mpa=25.0, slump_mm=45.0,
            margin_mpa=10.0, cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.5,
                shape=AggregateShape.GRAVEL),
            fine_aggregate=FineAggregate(
                specific_gravity=2.5, pct_passing_600um=90.0,
                shape=AggregateShape.GRAVEL),
            w_c_ratio=0.50, min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert r.target_mean_strength_mpa == 35.0
        assert r.w_c_ratio == 0.50
        assert r.water_kg == 160
        assert r.cement_kg == 320
        assert abs(r.fine_aggregate_kg - 405) <= 10
        assert abs(r.coarse_aggregate_kg - 1440) <= 10
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.3 — Example 3: restricted by minimum cement (290)
# Slump 0-10 -> W 115, C 230 -> governed to 290, modified w/c 0.40,
# fines "15 to 18, say 17" %.
# ---------------------------------------------------------------------------
class TestGUIBREExample3:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="doe", target_strength_mpa=25.0,
            characteristic_strength_mpa=25.0, slump_mm=5.0,
            margin_mpa=10.0, cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.5,
                shape=AggregateShape.GRAVEL),
            fine_aggregate=FineAggregate(
                specific_gravity=2.5, pct_passing_600um=90.0,
                shape=AggregateShape.GRAVEL),
            w_c_ratio=0.50, min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert r.water_kg == 115
        assert r.cement_kg == 290.0
        assert abs(r.w_c_ratio - 0.40) < 0.005
        fines_pct = 100 * r.fine_aggregate_kg / (
            r.fine_aggregate_kg + r.coarse_aggregate_kg)
        assert 15.0 <= fines_pct <= 18.5
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.4 — Example 4: restricted by maximum cement (550)
# §5.3: 580 > 550 -> "not possible to proceed". GUI must surface the
# refusal, never a stale result.
# ---------------------------------------------------------------------------
class TestGUIBREExample4:
    def _input(self):
        return MixDesignInput(
            code="doe", target_strength_mpa=50.0,
            characteristic_strength_mpa=50.0, slump_mm=45.0,
            defective_percent=1.0, std_deviation=5.0, age_days=7,
            cement=Cement(type=CementType.OPC_53),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=10, specific_gravity=2.7,
                shape=AggregateShape.ANGULAR),
            fine_aggregate=FineAggregate(
                specific_gravity=2.7, pct_passing_600um=45.0,
                shape=AggregateShape.GRAVEL),
            max_cement_kg=550.0,
        )

    def test_engine_refuses(self):
        with pytest.raises(ValueError, match="not possible to proceed"):
            DOEMixDesign().design(self._input())

    def test_gui_keeps_form_values(self, tab):
        inp = self._input()
        kwargs = _assert_kwargs_roundtrip(tab, inp)
        assert kwargs["max_cement_kg"] == 550.0
        with pytest.raises(ValueError, match="not possible to proceed"):
            DOEMixDesign().design(inp)


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.1 — 50 litre trial batch + oven-dry conversion
# SSD trial: 17.0 / 8.0 / 25.7 / 69.2; oven-dry: 25.2 / 68.5 + 1.2 kg water
# (FA A=2%, CA A=1%).
# ---------------------------------------------------------------------------
class TestGUIBRETrialBatch:
    def test_trial_quantities(self, tab):
        inp = MixDesignInput(
            code="doe", target_strength_mpa=30.0,
            characteristic_strength_mpa=30.0, slump_mm=20.0,
            defective_percent=2.5, has_production_data=False,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.6,
                shape=AggregateShape.GRAVEL),
            fine_aggregate=FineAggregate(
                specific_gravity=2.6, pct_passing_600um=70.0,
                shape=AggregateShape.GRAVEL),
            w_c_ratio=0.55, min_cement_kg=290.0, volume_m3=0.05,
        )
        r = DOEMixDesign().design(inp)
        # design() reports per-m3 quantities; the 0.05 m3 reference trial
        # batch lives in step 14 (BRE 331:1997 S6.1 / BS 1881 Part 125).
        trial = next(s for s in r.steps if s.step_number == 14)
        assert abs(trial.inputs["cement"] - 17.0) < 0.2
        assert abs(trial.inputs["water"] - 8.0) < 0.2
        assert abs(trial.inputs["fine_agg_ssd"] - 25.7) < 0.6
        assert abs(trial.inputs["coarse_agg_ssd"] - 69.2) < 0.6
        # The result cards scale by the 0.05 m3 batch volume, so they show
        # the trial quantities above — not the per-m3 engine fields.
        tab._result_panel.display_result(r)
        assert abs(_card_float(tab._result_panel, "cement") - 17.0) < 0.15
        assert abs(_card_float(tab._result_panel, "water") - 8.0) < 0.15
        assert abs(_card_float(tab._result_panel, "fine_agg") - 25.7) < 0.6
        assert abs(_card_float(tab._result_panel, "coarse_agg") - 69.2) < 0.6
        assert abs(_card_float(tab._result_panel, "target") - 46.0) < 0.15
        from concrete_mix.engine.moisture_correction import correct_for_moisture
        assert abs(correct_for_moisture(25.7, 2.0, 0.0) - 25.2) < 0.15
        assert abs(correct_for_moisture(69.2, 1.0, 0.0) - 68.5) < 0.15


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex A — M40 PPC (A-1 to A-12)
# Printed: target 48.25, w/c 0.36, W 148, C 412, FA 648, CA 1234, adm 4.12.
# App policy ceils target 48.25 -> 49 (conservative, +3 kg cement).
# ---------------------------------------------------------------------------
class TestGUIISAnnexA:
    def _input(self):
        return MixDesignInput(
            code="is10262", target_strength_mpa=40.0, slump_mm=75.0,
            exposure_class="severe", concrete_type="reinforced",
            cement=Cement(type=CementType.PPC, specific_gravity=2.88),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=23.0),
        )

    def test_engine_and_gui(self, tab):
        r = IS10262MixDesign().design(self._input())
        assert r.target_mean_strength_mpa == 49
        assert r.w_c_ratio == 0.36
        assert r.water_kg == 148.0
        assert abs(r.cement_kg - 415) < 3
        assert abs(r.fine_aggregate_kg - 648) < 15
        assert abs(r.coarse_aggregate_kg - 1234) < 15
        _assert_kwargs_roundtrip(tab, self._input())
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex B — M40 + 30% fly ash, slump 120 (B-1 to B-15)
# Printed at exact 48.25: W 155, total 474 (142 FA + 332 OPC).
# Ceiled target 49 -> total ~481 (144 + 337).
# ---------------------------------------------------------------------------
class TestGUIISAnnexB:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="is10262", target_strength_mpa=40.0, slump_mm=120.0,
            exposure_class="severe",
            cement=Cement(type=CementType.PPC, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=30.0),),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=23.0),
        )
        r = IS10262MixDesign().design(inp)
        assert abs(r.water_kg - 155.3) < 0.8
        assert abs((r.cement_kg + r.scm_kg) - 481) < 5
        assert abs(r.scm_kg - 144) < 3
        assert abs(r.cement_kg - 337) < 3
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex C — M40 + 40% GGBS, slump 120 (C-1 to C-10)
# Printed at exact 48.25: W 155, total 431 (172 GGBS + 259 OPC),
# FA 770, CA 1099.
# ---------------------------------------------------------------------------
class TestGUIISAnnexC:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="is10262", target_strength_mpa=40.0, slump_mm=120.0,
            exposure_class="severe",
            cement=Cement(type=CementType.OPC_43, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
            scms=(SCM(type=SCMType.GGBFS, replacement_percent=40.0,
                       specific_gravity=3.0),),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=23.0, specific_gravity=1.145),
        )
        r = IS10262MixDesign().design(inp)
        assert abs(r.water_kg - 155.3) < 1.0
        assert abs((r.cement_kg + r.scm_kg) - 431) < 8
        assert abs(r.scm_kg - 172) < 5
        assert abs(r.cement_kg - 259) < 6
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex D — high-strength (D-9.1 trial)
# Printed: w/cm 0.264, W 141, C 428 + FA 80.25 + SF 26.75 (= 535),
# FA 589, CA 1219, adm 2.67.
# ---------------------------------------------------------------------------
class TestGUIISAnnexD:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="is10262", target_strength_mpa=70.0, slump_mm=120.0,
            exposure_class="severe", concrete_type="reinforced",
            # High-strength auto-detected at target >= 65 MPa (no input flag).
            cement=Cement(type=CementType.OPC_53, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=15.0),
                   SCM(type=SCMType.SILICA_FUME, replacement_percent=5.0),),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=0.5,
                water_reduction_percent=30.0),
        )
        r = IS10262MixDesign().design(inp)
        assert abs(r.water_kg - 141) < 3
        assert abs((r.cement_kg + r.scm_kg) - 535) < 12
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex E — SCC M30 (E-3 target 38.25 -> ceil 39)
# ---------------------------------------------------------------------------
class TestGUIISAnnexE:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="is10262", target_strength_mpa=30.0, slump_mm=75.0,
            exposure_class="severe", concrete_type="reinforced",
            scc_class="SF2",
            cement=Cement(type=CementType.OPC_43, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=1.0,
                water_reduction_percent=23.0),
        )
        r = IS10262MixDesign().design(inp)
        assert r.target_mean_strength_mpa == 39
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex F — mass concrete M15, 150 mm NMSA (F-3 to F-6)
# Target 20.77 (ceil 21); reported 21 x 1.25 = 26.25 via the S9.2
# wet-sieving allowance for 150 mm cube tests; w/c 0.61 capped to 0.60.
# ---------------------------------------------------------------------------
class TestGUIISAnnexF:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="is10262", target_strength_mpa=15.0, slump_mm=50.0,
            exposure_class="moderate", concrete_type="plain",
            mass_concrete=True,
            cement=Cement(type=CementType.OPC_43, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=150, specific_gravity=2.74,
                shape=AggregateShape.ROUNDED_GRAVEL),
        )
        r = IS10262MixDesign().design(inp)
        assert r.target_mean_strength_mpa == 26.25
        assert r.w_c_ratio <= 0.60 + 1e-9
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 §9.2 Example 1 — 2500 psi, 40 mm rounded, FM 2.80
# Printed: W 300 lb (178 kg), air 1%, f'cr 3500 psi, w/cm 0.62, C 484 lb
# (287 kg), CA 1927 lb SSD (1143 kg), FA 1308 lb (776 kg).
# App policy ceils f'cr to whole MPa (25 MPa -> w/cm ~0.61, C ~291).
# ---------------------------------------------------------------------------
class TestGUIACIExample1:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="aci211", target_strength_mpa=17.24, slump_mm=90.0,
            has_production_data=False,
            cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.64, fineness_modulus=2.80,
                absorption_percent=0.7),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.68,
                absorption_percent=0.5, bulk_density_kg_m3=1600.0,
                shape=AggregateShape.ROUNDED_GRAVEL),
        )
        r = ACI211MixDesign().design(inp)
        assert abs(r.target_mean_strength_mpa - 25) < 0.1
        assert abs(r.water_kg - 178.0) < 1.5
        assert r.air_volume_percent == 1.0
        assert abs(r.w_c_ratio - 0.61) < 0.02
        assert abs(r.cement_kg - 291.1) < 4.0
        assert abs(r.coarse_aggregate_kg - 1141.7) < 8.0
        assert abs(r.fine_aggregate_kg - 775.1) < 25
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 §9.3 Example 2 — binary fly-ash mixture (S1, F3, W1)
# Printed: base water 280 lb - 14 (WRA 5%) - 17 (fly ash 6%) - 22
# (rounded 8%) = 227 lb; w/cm 0.37; CM 614 lb (491 + 123);
# CA 1951 SSD; FA 1124 SSD; air 5.5%.
# Table 5.3.3.1 reductions apply additively off the Table 5.3.3 base.
# ---------------------------------------------------------------------------
class TestGUIACIExample2:
    def test_engine_and_gui(self, tab):
        inp = MixDesignInput(
            code="aci211", target_strength_mpa=34.47, slump_mm=140.0,
            has_production_data=True, num_strength_tests=30,
            std_deviation=300 * 0.00689476,  # Example 2 sample s = 300 psi
            apply_rounded_aggregate_reduction=True,  # Table 5.3.3.1 -8%
            sulfate_exposure_class="S1", freezing_exposure_class="F3",
            water_exposure_class="W1",
            cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.65, fineness_modulus=2.80,
                absorption_percent=1.0),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.66,
                absorption_percent=0.8, bulk_density_kg_m3=1618.0,
                shape=AggregateShape.ROUNDED_GRAVEL),
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=20.0,
                       specific_gravity=2.40),),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER, dosage_percent=0.5,
                water_reduction_percent=5.0),
            air_entrained=True,
        )
        r = ACI211MixDesign().design(inp)
        assert abs(r.water_kg - 134.6) < 4
        assert abs(r.w_c_ratio - 0.37) < 0.03
        assert abs((r.cement_kg + r.scm_kg) - 364.3) < 12
        assert r.air_volume_percent == 5.5
        assert abs(r.coarse_aggregate_kg - 1157.6) < 30
        assert abs(r.fine_aggregate_kg - 666.9) < 30
        _assert_kwargs_roundtrip(tab, inp)
        _assert_gui_fidelity(tab, r)


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 §9.4 Example 3 — cementitious efficiency factor
# Trial: 4200 psi at 564 lb -> 7.45 psi/lb; +300 psi needs +40 lb CM
# (604 lb), w/cm 0.53 -> 0.50 at constant 300 lb water.
# ---------------------------------------------------------------------------
class TestGUIACIExample3:
    def test_efficiency_adjustment(self, tab):
        # ACI PRC-211.1-22 S9.4 Example 3: efficiency = trial strength /
        # trial cementitious; the 300 psi shortfall prices the added
        # cementitious at constant water.
        efficiency = 4200.0 / 564.0
        added = (4500.0 - 4200.0) / efficiency
        new_cm = 564.0 + added
        assert abs(efficiency - 7.45) < 0.05
        assert abs(added - 40) < 2
        assert abs(new_cm - 604) < 2
        assert abs(300.0 / new_cm - 0.50) < 0.02


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 §9.5 Example 4 — target paste volume
# Reference mix: paste 8.20 ft3 / 27 = 30.4%; redesign holds w/cm 0.40
# and 50% slag while hitting PV 25%.
# ---------------------------------------------------------------------------
class TestGUIACIExample4:
    def test_paste_volume(self, tab):
        from concrete_mix.codes.tables.aci_tables import (
            cementitious_for_target_paste_volume, paste_volume_percent,
        )
        _lb_yd3_to_kg_m3 = 0.45359237 / 0.76455486
        pv = paste_volume_percent(
            cement_kg=350.0 * _lb_yd3_to_kg_m3, cement_sg=3.15,
            scm_kg=350.0 * _lb_yd3_to_kg_m3, scm_sg=2.90,
            water_kg=280.0 * _lb_yd3_to_kg_m3,
        )
        assert abs(pv - 30.4) < 0.3
        new_cement, new_scm, new_water = cementitious_for_target_paste_volume(
            target_pv_percent=25.0, wcm=0.40, scm_fraction=0.50,
            cement_sg=3.15, scm_sg=2.90,
        )
        assert abs(new_water / (new_cement + new_scm) - 0.40) < 0.01
        assert abs(new_scm / (new_cement + new_scm) - 0.50) < 0.02
        assert abs(paste_volume_percent(
            cement_kg=new_cement, scm_kg=new_scm, water_kg=new_water,
            cement_sg=3.15, scm_sg=2.90) - 25.0) < 0.3
        inp = MixDesignInput(
            code="aci211", target_strength_mpa=34.47, slump_mm=90.0,
            has_production_data=False,
            target_paste_volume_pct=25.0,
            cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.60, fineness_modulus=2.80),
            coarse_aggregate=CoarseAggregate(
                # S9.5 uses 1-in. (25 mm); 20 mm is the nearest project band.
                nominal_max_size_mm=20, specific_gravity=2.80,
                bulk_density_kg_m3=1600.0),
            scms=(SCM(type=SCMType.GGBFS, replacement_percent=50.0,
                       specific_gravity=2.90),),
        )
        kwargs = _assert_kwargs_roundtrip(tab, inp)
        assert kwargs["target_paste_volume_pct"] == 25.0


# ---------------------------------------------------------------------------
# ACI §5.3.9.1 moisture correction — batch weights (Ex1: MC 2%/6%, A 0.5/0.7)
# ---------------------------------------------------------------------------
class TestGUIACIBatchWeights:
    def test_batch_formula(self):
        from concrete_mix.engine.moisture_correction import (
            adjust_water_for_aggregate_moisture, correct_for_moisture,
        )
        assert abs(correct_for_moisture(1000.0, 1.0, 3.0) - 1019.8) < 0.1
        assert adjust_water_for_aggregate_moisture(
            180.0, 700.0, 1.0, 0.0, 1100.0, 0.5, 0.0) > 180.0
        assert adjust_water_for_aggregate_moisture(
            180.0, 700.0, 1.0, 3.0, 1100.0, 0.5, 1.0) < 180.0
