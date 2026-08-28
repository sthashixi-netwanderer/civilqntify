"""Regression tests against the standards' own worked examples.

Each test reproduces a fully worked example published in the reference
standard, so any future change that breaks conformance fails here.

Sources:
  - BRE 331:1997 "Design of normal concrete mixes", §7 Examples 1-4
  - IS 10262:2019 Annex A (M40 PPC + superplasticizer) and Annex B
    (M40 + 30 % fly ash)
  - ACI PRC-211.1-22 §9.2 Example 1 (2500 psi, 1-1/2 in. rounded aggregate)
"""

import pytest

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.models.materials import (
    Admixture,
    AdmixtureType,
    AggregateShape,
    Cement,
    CementType,
    CoarseAggregate,
    FineAggregate,
    SCM,
    SCMType,
)
from concrete_mix.models.mix_input import MixDesignInput


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.1 — Example 1: unrestricted design
# f_c 30 N/mm² @ 28 d, 2.5 % defectives (k = 1.96), s = 8 (Figure 3, line A),
# class 42.5, uncrushed, 20 mm, slump 10-30, 70 % passing 600 µm, RD 2.6,
# max W/C 0.55, min cement 290.
# Standard result: W/C 0.47, W 160, C 340, density 2400, fine 27 % (≈515),
# coarse ≈1385.
# ---------------------------------------------------------------------------
class TestBREExample1:
    def test_design(self):
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            characteristic_strength_mpa=30.0,
            slump_mm=20.0,
            defective_percent=2.5,
            has_production_data=False,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.6,
                shape=AggregateShape.GRAVEL,
            ),
            fine_aggregate=FineAggregate(
                specific_gravity=2.6, pct_passing_600um=70.0,
                shape=AggregateShape.GRAVEL,
            ),
            w_c_ratio=0.55,
            min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert abs(r.target_mean_strength_mpa - 45.7) < 0.1  # 30 + 1.96×8
        assert r.w_c_ratio == 0.47
        assert r.water_kg == 160
        assert r.cement_kg == 340
        assert abs(r.fine_aggregate_kg - 515) <= 5
        assert abs(r.coarse_aggregate_kg - 1385) <= 5


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.2 — Example 2: restricted by maximum W/C (0.50)
# f_c 25, margin 10, class 42.5, uncrushed, 40 mm, slump 30-60,
# 90 % passing 600 µm, RD 2.5, min cement 290.
# Standard result: W/C 0.50 (durability limit), W 160, C 320, density 2325,
# fine 22 % (405), coarse 1440.
# ---------------------------------------------------------------------------
class TestBREExample2:
    def test_design(self):
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=25.0,
            characteristic_strength_mpa=25.0,
            slump_mm=45.0,
            margin_mpa=10.0,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.5,
                shape=AggregateShape.GRAVEL,
            ),
            fine_aggregate=FineAggregate(
                specific_gravity=2.5, pct_passing_600um=90.0,
                shape=AggregateShape.GRAVEL,
            ),
            w_c_ratio=0.50,
            min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert r.target_mean_strength_mpa == 35.0
        assert r.w_c_ratio == 0.50
        assert r.water_kg == 160
        assert r.cement_kg == 320
        assert r.fine_aggregate_kg == 405
        assert r.coarse_aggregate_kg == 1440


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.3 — Example 3: restricted by minimum cement (290)
# As Example 2 but slump 0-10 → W 115, C 290 (min), modified W/C 0.40,
# fine proportion "15 to 18, say 17" %.
# ---------------------------------------------------------------------------
class TestBREExample3:
    def test_design(self):
        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=25.0,
            characteristic_strength_mpa=25.0,
            slump_mm=5.0,
            margin_mpa=10.0,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.5,
                shape=AggregateShape.GRAVEL,
            ),
            fine_aggregate=FineAggregate(
                specific_gravity=2.5, pct_passing_600um=90.0,
                shape=AggregateShape.GRAVEL,
            ),
            w_c_ratio=0.50,
            min_cement_kg=290.0,
        )
        r = DOEMixDesign().design(inp)
        assert r.water_kg == 115
        assert r.cement_kg == 290
        assert r.w_c_ratio == 0.40  # modified ratio 115/290
        # Fine proportion within the standard's Figure 6 band 15-18 %
        fine_pct = r.fine_aggregate_kg / (r.fine_aggregate_kg + r.coarse_aggregate_kg)
        assert 0.15 <= fine_pct <= 0.18


# ---------------------------------------------------------------------------
# BRE 331:1997 §7.4 — Example 4: restricted by maximum cement (550)
# f_c 50 @ 7 days, 1 % defectives (k = 2.33), s = 5, class 52.5,
# crushed coarse + uncrushed fine, 10 mm, slump 30-60, 45 % passing 600 µm.
# Standard result: target mean ≈62, W/C 0.37, W = 2/3·205 + 1/3·230 ≈ 215,
# calculated C 580 > max 550 (spec cannot be met).
# ---------------------------------------------------------------------------
class TestBREExample4:
    def test_design(self):
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
        r = DOEMixDesign().design(inp)
        assert abs(r.target_mean_strength_mpa - 61.65) < 0.1
        # Figure 4 (pre-limit) ratio, recorded in step 5
        step5 = next(s for s in r.steps if s.step_number == 5)
        assert abs(step5.result - 0.37) < 0.005
        # Mixed-aggregate water per Note to Table 3, rounded to nearest 5
        assert r.water_kg == 215.0
        # Calculated cement 580 exceeds the 550 maximum → capped with warning
        assert r.cement_kg == 550.0
        assert any("max cement" in w.lower() for w in r.warnings)


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex A — M40, PPC (Curve 2), severe exposure, slump 75,
# 20 mm, Zone II, SP 1.0 % at 23 % water reduction, SG 2.88/2.74/2.65.
# Standard result: f'tm 48.25, w/c 0.36, W 191.58×0.77 = 147.5 ≈ 148,
# C ≈ 412, CA fraction 0.62 + 0.028 = 0.648.
# ---------------------------------------------------------------------------
class TestISAnnexA:
    def _input(self, slump=75.0):
        return MixDesignInput(
            code="is10262",
            target_strength_mpa=40.0,
            slump_mm=slump,
            exposure_class="severe",
            concrete_type="reinforced",
            cement=Cement(type=CementType.PPC, specific_gravity=2.88),
            fine_aggregate=FineAggregate(specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR,
            ),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER,
                dosage_percent=1.0,
                water_reduction_percent=23.0,
            ),
        )

    def test_target_strength_exact(self):
        # Clause 4.2: keep 48.25 (no ceiling rounding)
        assert self._input() is not None
        from concrete_mix.codes.tables.is_tables import calculate_target_strength
        ftm, _ = calculate_target_strength(40.0, 5.0)
        assert ftm == 48.25

    def test_ppc_uses_curve_2(self):
        # Fig. 1 Note 2: PPC uses the OPC 43 curve → same w/c as OPC 43
        from concrete_mix.codes.tables.is_tables import wc_ratio_from_strength
        assert wc_ratio_from_strength(48.25, "PPC") == wc_ratio_from_strength(48.25, "OPC_43")
        assert abs(wc_ratio_from_strength(48.25, "PPC") - 0.36) < 0.01

    def test_water_sequence_slump_then_admixture(self):
        # Annex A: 186 → 191.58 (75 mm slump) → ×0.77 = 147.5 ≈ 148
        r = IS10262MixDesign().design(self._input())
        assert r.target_mean_strength_mpa == 48.25
        assert r.w_c_ratio == 0.36
        assert abs(r.water_kg - 147.5) < 0.5
        assert abs(r.cement_kg - 410) < 3

    def test_ca_fraction_proportional_adjustment(self):
        # Annex A-8: 0.62 + 0.028 = 0.648 (not rounded to 0.65)
        r = IS10262MixDesign().design(self._input())
        step5 = next(s for s in r.steps if s.step_number == 5)
        assert step5.inputs["ca_fraction_adjusted"] == 0.648


# ---------------------------------------------------------------------------
# IS 10262:2019 Annex B — M40 with 30 % fly ash, slump 120
# W = 186×1.084 ×0.77 = 155, C(plain) 431 → ×1.10 = 474 total cementitious,
# fly ash 142, OPC 332.
# ---------------------------------------------------------------------------
class TestISAnnexB:
    def test_design(self):
        inp = MixDesignInput(
            code="is10262",
            target_strength_mpa=40.0,
            slump_mm=120.0,
            exposure_class="severe",
            cement=Cement(type=CementType.PPC, specific_gravity=3.15),
            fine_aggregate=FineAggregate(specific_gravity=2.65, grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.74,
                shape=AggregateShape.ANGULAR,
            ),
            scms=(SCM(type=SCMType.FLY_ASH, replacement_percent=30.0),),
            admixture=Admixture(
                type=AdmixtureType.SUPERPLASTICIZER,
                dosage_percent=1.0,
                water_reduction_percent=23.0,
            ),
        )
        r = IS10262MixDesign().design(inp)
        assert abs(r.water_kg - 155.3) < 0.5
        assert abs((r.cement_kg + r.scm_kg) - 474) < 3
        assert abs(r.scm_kg - 142.2) < 2
        assert abs(r.cement_kg - 331.8) < 2


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 §9.2 Example 1 — f'c 2500 psi (17.24 MPa), F0,
# non-air-entrained, 1-1/2 in. (40 mm) rounded aggregate, slump 3-4 in.,
# FM 2.80, CA: SG 2.68, A 0.5 %, dry-rodded density 100 lb/ft³ (1600 kg/m³),
# FA: SG 2.64, A 0.7 %.
# Standard result: W 300 lb/yd³ (178 kg/m³), entrapped air 1 %, f'cr 3500 psi
# (+1000 psi), w/cm 0.62, C 484 lb (287), CA 1917 lb dry → 1927 lb SSD (1143),
# FA 1308 lb (776).
# ---------------------------------------------------------------------------
class TestACIExample1:
    def test_design(self):
        with pytest.raises(ValueError, match="ACI211 structural design requires characteristic strength"):
            MixDesignInput(code="aci211", target_strength_mpa=17.24)

        inp = MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=90.0,
            has_production_data=False,
            cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
            fine_aggregate=FineAggregate(
                specific_gravity=2.64, fineness_modulus=2.80,
                absorption_percent=0.7,
            ),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=40, specific_gravity=2.68,
                absorption_percent=0.5, bulk_density_kg_m3=1600.0,
                shape=AggregateShape.ROUNDED_GRAVEL,
            ),
        )
        object.__setattr__(inp, "target_strength_mpa", 17.24)
        r = ACI211MixDesign().design(inp)
        assert abs(r.target_mean_strength_mpa - 24.1) < 0.2   # 3500 psi
        assert abs(r.water_kg - 178.0) < 1.0                  # 300 lb/yd³
        assert r.air_volume_percent == 1.0
        assert abs(r.w_c_ratio - 0.62) < 0.005                # Table 5.3.4 interp
        assert abs(r.cement_kg - 287.1) < 2.0                 # 484 lb/yd³
        # CA: 0.71 (Table 5.3.6) × 1600 × (1+0.5%) = 1141.7 ≈ 1927 lb SSD
        assert abs(r.coarse_aggregate_kg - 1141.7) < 3.0
        # FA by absolute volume ≈ 1308 lb (776 kg) ±2 %
        assert abs(r.fine_aggregate_kg - 776) < 20


# ---------------------------------------------------------------------------
# ACI PRC-211.1-22 moisture correction (§5.3.9.1)
# ---------------------------------------------------------------------------
class TestACIBatchWeights:
    def test_batch_weight_formula(self):
        from concrete_mix.engine.moisture_correction import (
            adjust_water_for_aggregate_moisture,
            correct_for_moisture,
        )
        # w_batched = w_SSD × (1 + MC%) / (1 + A%)
        assert abs(correct_for_moisture(1000.0, 1.0, 3.0) - 1019.8) < 0.1
        # Drier than SSD → negative free water → more mix water
        assert adjust_water_for_aggregate_moisture(
            180.0, 700.0, 1.0, 0.0, 1100.0, 0.5, 0.0
        ) > 180.0
        # Wetter than SSD → free water subtracted
        assert adjust_water_for_aggregate_moisture(
            180.0, 700.0, 1.0, 3.0, 1100.0, 0.5, 1.0
        ) < 180.0
