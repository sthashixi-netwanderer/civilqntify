"""Tests for the PSD → mix-design linkage module.

Every supported standard requires sieve-analysis data before proportioning,
and each consumes a different derived parameter:
  - ACI PRC-211.1-22 §4.3.5 — fineness modulus → Table 5.3.6.
  - IS 10262:2019 Clause 5.4 — IS 383 Table 9 grading zone → Table 5.
  - BRE 331:1997 §1.2.5 — percentage passing 600 µm → Figure 6.
"""

from __future__ import annotations

import pytest

from concrete_mix.engine.grading import determine_grading_zone
from concrete_mix.engine.psd import (
    COARSE_SIEVES,
    FINE_SIEVES,
    check_conformance,
    compute_psd,
)
from concrete_mix.engine.psd_link import (
    PSDLinkage,
    derive_mix_design_params,
)


# ---------------------------------------------------------------------------
# Textbook fine-aggregate sample (mirrors TestComputePSD)
# ---------------------------------------------------------------------------
class TestFineAggregateDerivation:
    """Sample (total 500 g, no pan) from the PSD computation tests.

        10 mm → 0 g, 4.75 → 25 g, 2.36 → 90 g, 1.18 → 100 g,
        0.600 → 110 g, 0.300 → 100 g, 0.150 → 55 g, pan → 20 g

    Cumulative %retained: 0, 5, 23, 43, 65, 85, 96
      FM = (5+23+43+65+85+96)/100 = 3.17 (ACI 211.1-22 §4.3.5)
      %passing at 600 µm = 100 − 65 = 35.0 % (BRE 331 §1.2.5)
    """

    @pytest.fixture
    def linkage(self) -> PSDLinkage:
        masses = [0.0, 25.0, 90.0, 100.0, 110.0, 100.0, 55.0]
        result = compute_psd(masses, FINE_SIEVES, pan_mass=20.0)
        return derive_mix_design_params(result)

    def test_fineness_modulus_for_aci(self, linkage):
        assert linkage.fineness_modulus == pytest.approx(3.17)
        assert linkage.aci211_ready

    def test_pct_passing_600um_for_doe(self, linkage):
        assert linkage.pct_passing_600um == pytest.approx(35.0)
        assert linkage.doe_ready

    def test_grading_zone_determined_by_sieve_analysis(self, linkage):
        # The zone must be whatever the IS 383 engine derives from this curve.
        masses = [0.0, 25.0, 90.0, 100.0, 110.0, 100.0, 55.0]
        result = compute_psd(masses, FINE_SIEVES, pan_mass=20.0)
        expected = determine_grading_zone(
            dict(zip(result.sieve_sizes, result.percent_passing))
        )
        assert linkage.grading_zone == expected
        assert linkage.is10262_ready

    def test_no_warnings_for_complete_fine_stack(self, linkage):
        assert linkage.warnings == ()

    def test_conformance_flag_not_part_of_linkage_params(self):
        # A non-conforming curve still yields valid parameters — conformance
        # is surfaced as a separate warning by the UI handoff.
        masses = [0.0, 400.0, 90.0, 10.0, 0.0, 0.0, 0.0]
        result = compute_psd(masses, FINE_SIEVES)
        check_conformance(result, {4.75: (95.0, 100.0)})
        linkage = derive_mix_design_params(result)
        assert linkage.fineness_modulus is not None


class TestCoarseAggregateAnalysis:
    """A coarse stack cannot supply the fine-aggregate-only parameters."""

    def test_coarse_stack_yields_warnings_per_standard(self):
        # ASTM C33/C33M Table 2 stack (14 lab sieves) — no fine-aggregate
        # series present.
        masses = [
            0.0,    # 100 mm
            0.0,    # 90 mm
            0.0,    # 75 mm
            0.0,    # 63 mm
            150.0,  # 50 mm
            2200.0,  # 37.5 mm
            900.0,  # 25 mm
            800.0,  # 19 mm
            200.0,  # 12.5 mm
            250.0,  # 9.5 mm
            60.0,   # 4.75 mm
            40.0,   # 2.36 mm
            25.0,   # 1.18 mm
            35.0,   # 0.300 mm
        ]
        pan = 45.0
        result = compute_psd(masses, COARSE_SIEVES, pan_mass=pan)
        linkage = derive_mix_design_params(result)

        assert linkage.fineness_modulus is None
        assert not linkage.aci211_ready
        assert linkage.grading_zone is None
        assert not linkage.is10262_ready
        assert linkage.pct_passing_600um is None
        assert not linkage.doe_ready

        text = " ".join(linkage.warnings)
        assert "Table 5" in text            # IS 10262 zone warning
        assert "Fineness modulus" in text   # ACI FM warning
        assert "600 µm" in text             # DOE/BRE p600 warning


class TestPartialStacks:
    """Missing individual sieves degrade only their own parameter."""

    def test_missing_fm_sieve_keeps_doe_input_working(self):
        # The FM series needs ALL six sieves {4.75…0.150}; DOE needs only
        # the single 600 µm sieve. Dropping the 300 µm sieve kills the ACI
        # fineness modulus but leaves the DOE %p600 computable.
        sizes = [10.0, 4.75, 2.36, 1.18, 0.600, 0.150]
        masses = [5.0, 10.0, 30.0, 25.0, 20.0, 10.0]
        result = compute_psd(masses, sizes)
        linkage = derive_mix_design_params(result)

        assert linkage.fineness_modulus is None
        assert any("Table 5.3.6" in w for w in linkage.warnings)
        assert linkage.pct_passing_600um is not None

    def test_partial_fm_series_reports_aci_warning(self):
        # Only three of the six FM sieves present.
        sizes = [2.36, 1.18, 0.600]
        result = compute_psd([50.0, 30.0, 20.0], sizes)
        linkage = derive_mix_design_params(result)

        assert linkage.fineness_modulus is None
        aci_warning = [
            w for w in linkage.warnings if "Table 5.3.6" in w
        ]
        assert len(aci_warning) == 1

    def test_fm_not_calculated_warns_without_blaming_sieves(self):
        # All six FM sieves are present, but the analysis' own standard
        # (IS 383:2016, or ASTM C33 coarse aggregate) carries no FM
        # requirement, so the FM was not calculated. The warning must say
        # exactly that instead of asking for sieves the analysis already
        # includes.
        masses = [0.0, 25.0, 90.0, 100.0, 110.0, 100.0, 55.0]
        result = compute_psd(
            masses, FINE_SIEVES, pan_mass=20.0,
            compute_fineness_modulus=False,
        )
        linkage = derive_mix_design_params(result)

        assert linkage.fineness_modulus is None
        assert not linkage.aci211_ready
        fm_warnings = [w for w in linkage.warnings if "Fineness modulus" in w]
        assert len(fm_warnings) == 1
        assert "not calculated" in fm_warnings[0]
        assert "Add sieves" not in fm_warnings[0]

    def test_warning_sieves_spell_sub_mm_with_micro_symbol(self):
        # UI-facing warnings name sub-millimetre sieves with the µ symbol
        # (600 µm), matching the PSD tab's sieve-size display.
        from concrete_mix.engine.psd_link import _fmt_sieve

        assert _fmt_sieve(0.600) == "600 µm"
        assert _fmt_sieve(0.150) == "150 µm"
        assert _fmt_sieve(4.75) == "4.75 mm"
        assert _fmt_sieve(10.0) == "10 mm"

    def test_zero_mass_result_keeps_finite_modulus_none(self):
        result = compute_psd([0.0] * len(FINE_SIEVES), FINE_SIEVES)
        linkage = derive_mix_design_params(result)

        # Zero-total short-circuits compute_psd to an empty distribution;
        # the fineness modulus stays undefined but the zone/p600 lookups on
        # a degenerate all-zero curve fall back to engine defaults.
        assert linkage.fineness_modulus is None
        assert not linkage.aci211_ready
        assert any("Table 5.3.6" in w for w in linkage.warnings)

    def test_astm_fine_aggregate_yields_pct_passing_600um(self):
        """Verify ASTM C33 fine aggregate PSD exports % passing 600 µm for DOE."""
        from concrete_mix.engine.psd import ASTM_FINE_SIEVES
        masses = [0.0, 20.0, 80.0, 120.0, 100.0, 110.0, 50.0]  # 480 g, pan 20 g
        result = compute_psd(masses, ASTM_FINE_SIEVES, pan_mass=20.0)
        linkage = derive_mix_design_params(result)

        assert linkage.pct_passing_600um is not None
        assert linkage.doe_ready
        assert result.pct_passing_600um is not None
        assert linkage.pct_passing_600um == result.pct_passing_600um

    def test_custom_sieve_stack_interpolates_600um_when_spanning(self):
        """Verify log-interpolation of % passing 600 µm when 0.600 mm is spanned."""
        sizes = [4.75, 2.00, 0.400, 0.100]
        # At 2.0 mm -> 80% passing, at 0.400 mm -> 30% passing.
        # 0.600 mm is between 0.400 and 2.0 mm.
        masses = [10.0, 90.0, 250.0, 100.0]
        result = compute_psd(masses, sizes, pan_mass=50.0)
        linkage = derive_mix_design_params(result)

        assert linkage.pct_passing_600um is not None
        assert linkage.doe_ready
        assert 30.0 <= linkage.pct_passing_600um <= 80.0

