"""Tests for the particle-size-distribution calculation engine.

Verifies sieve-analysis math (ACI 211.1-22 §4.3.5 / IS 383 grading) and the
grading-band lookup tables.
"""

from __future__ import annotations

import math

import pytest

from concrete_mix.codes.tables.grading_bands import (
    COARSE_BANDS,
    COARSE_NOMINAL_SIZES,
    FINE_ZONES,
    get_coarse_band,
    get_fine_band,
)
from concrete_mix.engine.psd import (
    COARSE_SIEVES,
    FINE_SIEVES,
    STANDARD_SIEVES,
    PSDResult,
    check_conformance,
    compute_psd,
)


# ---------------------------------------------------------------------------
# Standard sieve sets
# ---------------------------------------------------------------------------
class TestStandardSieves:
    def test_fine_sieves_coarse_to_fine(self):
        # ACI 211.1-22 §4.3.5 halving series, coarsest → finest
        assert FINE_SIEVES == [10.0, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150]

    def test_coarse_sieves_coarse_to_fine(self):
        # IS 383 Table 7 / ASTM C33 series
        assert COARSE_SIEVES == [75.0, 37.5, 19.0, 9.5, 4.75, 2.36]

    def test_standard_sieves_keys(self):
        assert set(STANDARD_SIEVES) == {"fine", "coarse"}


# ---------------------------------------------------------------------------
# PSD computation — known textbook fine-aggregate sample
# ---------------------------------------------------------------------------
class TestComputePSD:
    """A worked fine-aggregate example with hand-computed expected values.

    Sample (total 500 g, no pan):
        10.0 mm →   0 g    4.75 →  25 g    2.36 →  90 g
        1.18   → 100 g    0.600 → 110 g   0.300 → 100 g
        0.150  →  55 g    pan  →  20 g
    Total = 0+25+90+100+110+100+55+20 = 500 g
    """

    @pytest.fixture
    def fine_sample(self):
        masses = [0.0, 25.0, 90.0, 100.0, 110.0, 100.0, 55.0]
        pan = 20.0
        result = compute_psd(masses, FINE_SIEVES, pan_mass=pan)
        return masses, pan, result

    def test_total_mass_includes_pan(self, fine_sample):
        _, _, result = fine_sample
        assert result.total_mass == pytest.approx(500.0)

    def test_percent_retained_first_sieves(self, fine_sample):
        _, _, result = fine_sample
        # 25 g / 500 g = 5 %, 90/500 = 18 %
        assert result.percent_retained[0] == pytest.approx(0.0)
        assert result.percent_retained[1] == pytest.approx(5.0)
        assert result.percent_retained[2] == pytest.approx(18.0)

    def test_cumulative_retained_monotonic(self, fine_sample):
        _, _, result = fine_sample
        cum = result.cumulative_percent_retained
        assert all(cum[i] <= cum[i + 1] for i in range(len(cum) - 1))
        # Last sieve cumulative = sum of all non-pan retained %
        assert cum[-1] == pytest.approx((0 + 25 + 90 + 100 + 110 + 100 + 55) / 500 * 100)

    def test_percent_passing_last_sieve_includes_pan(self, fine_sample):
        _, pan, result = fine_sample
        # %passing finest sieve = pan_mass / total * 100
        assert result.percent_passing[-1] == pytest.approx(pan / result.total_mass * 100)

    def test_percent_passing_identity(self, fine_sample):
        # %passing = 100 − cumulative retained for every sieve
        _, _, result = fine_sample
        for cum, p in zip(result.cumulative_percent_retained, result.percent_passing):
            assert p == pytest.approx(100.0 - cum)

    def test_fineness_modulus(self, fine_sample):
        # FM = Σ cumulative %retained on {0.150,0.300,0.600,1.18,2.36,4.75} / 100
        # (ACI 211.1-22 §4.3.5)
        _, _, result = fine_sample
        assert result.fineness_modulus is not None
        # Hand calc (total = 500 g, cumulative retained % per FM sieve):
        #   4.75 → 25/500   =  5
        #   2.36 → 115/500  = 23
        #   1.18 → 215/500  = 43
        #   0.60 → 325/500  = 65
        #   0.30 → 425/500  = 85
        #   0.15 → 480/500  = 96
        #   sum = 317 → FM = 3.17
        assert result.fineness_modulus == pytest.approx(3.17, abs=0.01)

    def test_d_values_present(self, fine_sample):
        _, _, result = fine_sample
        # With a well-graded sample, D10/D30/D60 should all be found
        assert result.d10 is not None and result.d10 > 0
        assert result.d30 is not None and result.d30 > 0
        assert result.d60 is not None and result.d60 > 0
        # Sizes must be ordered D10 ≤ D30 ≤ D60
        assert result.d10 <= result.d30 <= result.d60

    def test_uniformity_and_curvature(self, fine_sample):
        _, _, result = fine_sample
        assert result.uniformity_coefficient == pytest.approx(
            result.d60 / result.d10, abs=0.01
        )
        assert result.coefficient_of_curvature == pytest.approx(
            result.d30 ** 2 / (result.d60 * result.d10), abs=0.01
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestPSDEdgeCases:
    def test_zero_total_returns_none_indices(self):
        result = compute_psd([0.0] * 7, FINE_SIEVES, pan_mass=0.0)
        assert result.total_mass == 0.0
        assert result.fineness_modulus is None
        assert result.d10 is None
        assert result.all_conform is False  # empty conforms list

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="must match"):
            compute_psd([1.0, 2.0], FINE_SIEVES)

    def test_negative_mass_raises(self):
        with pytest.raises(ValueError, match="negative"):
            compute_psd([-1.0] + [0.0] * 6, FINE_SIEVES)

    def test_coarse_set_no_fineness_modulus(self):
        # FM is only defined for fine-aggregate sieves; coarse set → None
        masses = [0.0, 50.0, 200.0, 300.0, 150.0, 50.0]
        result = compute_psd(masses, COARSE_SIEVES, pan_mass=10.0)
        assert result.fineness_modulus is None
        assert result.total_mass == pytest.approx(sum(masses) + 10.0)

    def test_pan_only(self):
        # Everything in the pan: 100 % passing every sieve
        result = compute_psd([0.0] * 7, FINE_SIEVES, pan_mass=100.0)
        assert result.total_mass == 100.0
        assert all(p == pytest.approx(100.0) for p in result.percent_passing)


# ---------------------------------------------------------------------------
# Conformance checking
# ---------------------------------------------------------------------------
class TestConformance:
    def test_inside_band(self):
        result = compute_psd(
            [0.0, 25.0, 90.0, 100.0, 110.0, 100.0, 55.0], FINE_SIEVES, pan_mass=20.0
        )
        band = get_fine_band("II")
        conforms = check_conformance(result, band)
        assert len(conforms) == len(FINE_SIEVES)
        # The result.conforms list should be populated too
        assert result.conforms == conforms

    def test_outside_band_flagged(self):
        # Pathological sample: everything retained on the coarsest sieve
        # (10 mm). Then 4.75 mm passing = 0 %, well below Zone II's 90–100 %.
        result = compute_psd(
            [100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], FINE_SIEVES, pan_mass=0.0
        )
        band = get_fine_band("II")
        conforms = check_conformance(result, band)
        # 4.75 mm passing = 0 %, Zone II requires 90–100 → non-conforming
        idx_475 = FINE_SIEVES.index(4.75)
        assert conforms[idx_475] is False

    def test_sieve_not_in_band_is_conforming(self):
        # Coarse sieves not present in the fine band → treated as conforming
        result = compute_psd([0.0, 50.0, 200.0, 300.0, 150.0, 50.0], COARSE_SIEVES)
        band = get_coarse_band(20)
        conforms = check_conformance(result, band)
        assert len(conforms) == len(COARSE_SIEVES)


# ---------------------------------------------------------------------------
# Grading-band lookup tables
# ---------------------------------------------------------------------------
class TestGradingBands:
    def test_fine_zones_available(self):
        assert FINE_ZONES == ["I", "II", "III", "IV"]

    def test_coarse_sizes_available(self):
        assert COARSE_NOMINAL_SIZES == [10, 20, 40]

    def test_get_fine_band(self):
        band = get_fine_band("II")
        assert 4.75 in band
        lo, hi = band[4.75]
        assert lo == 90 and hi == 100

    def test_get_coarse_band_20mm(self):
        band = get_coarse_band(20)
        # 19 mm passing for 20 mm graded aggregate: 90–100 %
        assert band[19.0] == (90, 100)
        assert band[9.5] == (40, 85)

    def test_get_coarse_band_40mm(self):
        band = get_coarse_band(40)
        assert band[37.5] == (90, 100)
        assert band[19.0] == (35, 70)

    def test_unknown_zone_raises(self):
        with pytest.raises(KeyError):
            get_fine_band("V")

    def test_unknown_coarse_size_raises(self):
        with pytest.raises(KeyError):
            get_coarse_band(25)
