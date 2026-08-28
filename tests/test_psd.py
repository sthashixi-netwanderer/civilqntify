"""Tests for the particle-size-distribution calculation engine.

Verifies sieve-analysis math (ACI 211.1-22 §4.3.5 / IS 383 grading) and the
grading-band lookup tables.
"""

from __future__ import annotations

import pytest

from concrete_mix.codes.tables.grading_bands import (
    ASTM_COARSE_BANDS,
    ASTM_COARSE_NOMINAL_SIZES,
    ASTM_FINE_BAND,
    COARSE_BANDS,
    COARSE_NOMINAL_SIZES,
    FINE_ZONES,
    IS_COARSE_GRADED_BANDS,
    IS_COARSE_SINGLE_SIZED_BANDS,
    IS_GRADED_NOMINAL_SIZES,
    IS_SINGLE_SIZED_NOMINAL_SIZES,
    get_astm_coarse_band,
    get_astm_fine_band,
    get_coarse_band,
    get_fine_band,
    get_is_coarse_band,
)
from concrete_mix.engine.psd import (
    ASTM_COARSE_SIEVES,
    ASTM_FINE_SIEVES,
    COARSE_SIEVES,
    FINE_SIEVES,
    IS_COARSE_SIEVES,
    IS_FINE_SIEVES,
    STANDARD_SIEVES,
    STANDARD_SIEVES_BY_CODE,
    check_conformance,
    compute_psd,
)


# ---------------------------------------------------------------------------
# Standard sieve sets
# ---------------------------------------------------------------------------
class TestStandardSieves:
    def test_is_sieves_match_is_383_designations(self):
        assert IS_FINE_SIEVES == [
            10.0, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150
        ]
        assert IS_COARSE_SIEVES == [
            80.0, 63.0, 40.0, 20.0, 16.0, 12.5, 10.0, 4.75, 2.36
        ]

    def test_astm_sieves_match_c33_tables(self):
        assert ASTM_FINE_SIEVES == [
            9.5, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150
        ]
        assert ASTM_COARSE_SIEVES == [
            100.0,
            90.0,
            75.0,
            63.0,
            50.0,
            37.5,
            25.0,
            19.0,
            12.5,
            9.5,
            4.75,
            2.36,
            1.18,
            0.300,
        ]

    def test_standard_sieve_mapping_keeps_codes_separate(self):
        assert STANDARD_SIEVES_BY_CODE == {
            "is383": {"fine": IS_FINE_SIEVES, "coarse": IS_COARSE_SIEVES},
            "astm_c33": {
                "fine": ASTM_FINE_SIEVES,
                "coarse": ASTM_COARSE_SIEVES,
            },
        }
        assert FINE_SIEVES is IS_FINE_SIEVES
        assert COARSE_SIEVES is ASTM_COARSE_SIEVES
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
        masses = [
            0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 100.0,
            200.0, 100.0, 300.0, 150.0, 50.0, 25.0, 10.0,
        ]
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
        result = compute_psd(
            [
                0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 100.0,
                200.0, 100.0, 300.0, 150.0, 50.0, 25.0, 10.0,
            ],
            COARSE_SIEVES,
        )
        band = get_coarse_band(20)
        conforms = check_conformance(result, band)
        assert len(conforms) == len(COARSE_SIEVES)


# ---------------------------------------------------------------------------
# Grading-band lookup tables
# ---------------------------------------------------------------------------
class TestGradingBands:
    def test_fine_zones_available(self):
        assert FINE_ZONES == ["I", "II", "III", "IV"]

    def test_reference_choices_available_by_standard(self):
        assert ASTM_COARSE_NOMINAL_SIZES == [10, 20, 40]
        assert IS_GRADED_NOMINAL_SIZES == [40, 20, 16, 12.5]
        assert IS_SINGLE_SIZED_NOMINAL_SIZES == [63, 40, 20, 16, 12.5, 10]
        assert COARSE_NOMINAL_SIZES is ASTM_COARSE_NOMINAL_SIZES
        assert COARSE_BANDS is ASTM_COARSE_BANDS

    def test_get_is_fine_zone_band(self):
        band = get_fine_band("II")
        assert band[10.0] == (100, 100)
        assert band[4.75] == (90, 100)

    def test_get_astm_fine_table_1_band(self):
        assert get_astm_fine_band() is ASTM_FINE_BAND
        assert ASTM_FINE_BAND == {
            9.5: (100, 100),
            4.75: (95, 100),
            2.36: (80, 100),
            1.18: (50, 85),
            0.600: (25, 60),
            0.300: (5, 30),
            0.150: (0, 10),
        }

    def test_get_coarse_band_10mm_is_exact_astm_size_8(self):
        assert get_coarse_band(10) == {
            12.5: (100, 100),
            9.5: (85, 100),
            4.75: (10, 30),
            2.36: (0, 10),
            1.18: (0, 5),
        }

    def test_get_coarse_band_20mm_is_exact_astm_size_67(self):
        assert get_coarse_band(20) == {
            25.0: (100, 100),
            19.0: (90, 100),
            9.5: (20, 55),
            4.75: (0, 10),
            2.36: (0, 5),
        }

    def test_get_coarse_band_40mm_is_exact_astm_size_467(self):
        assert get_coarse_band(40) == {
            50.0: (100, 100),
            37.5: (95, 100),
            19.0: (35, 70),
            9.5: (10, 30),
            4.75: (0, 5),
        }

    def test_unspecified_astm_cells_are_not_requirements(self):
        assert 100.0 not in get_coarse_band(40)
        assert 12.5 not in get_coarse_band(20)
        assert 0.300 not in get_coarse_band(10)

    def test_is_graded_table_7_bands_are_exact(self):
        assert IS_COARSE_GRADED_BANDS == {
            40: {
                80.0: (100, 100),
                40.0: (90, 100),
                20.0: (30, 70),
                10.0: (10, 35),
                4.75: (0, 5),
            },
            20: {
                40.0: (100, 100),
                20.0: (90, 100),
                10.0: (25, 55),
                4.75: (0, 10),
            },
            16: {
                20.0: (100, 100),
                16.0: (90, 100),
                10.0: (30, 70),
                4.75: (0, 10),
            },
            12.5: {
                20.0: (100, 100),
                12.5: (90, 100),
                10.0: (40, 85),
                4.75: (0, 10),
            },
        }
        assert get_is_coarse_band("graded", 20) == IS_COARSE_GRADED_BANDS[20]

    def test_is_single_sized_table_7_bands_are_exact(self):
        assert IS_COARSE_SINGLE_SIZED_BANDS == {
            63: {
                80.0: (100, 100),
                63.0: (85, 100),
                40.0: (0, 30),
                20.0: (0, 5),
                10.0: (0, 5),
            },
            40: {
                63.0: (100, 100),
                40.0: (85, 100),
                20.0: (0, 20),
                10.0: (0, 5),
            },
            20: {
                40.0: (100, 100),
                20.0: (85, 100),
                10.0: (0, 20),
                4.75: (0, 5),
            },
            16: {
                20.0: (100, 100),
                16.0: (85, 100),
                10.0: (0, 30),
                4.75: (0, 5),
            },
            12.5: {
                16.0: (100, 100),
                12.5: (85, 100),
                10.0: (0, 45),
                4.75: (0, 10),
            },
            10: {
                12.5: (100, 100),
                10.0: (85, 100),
                4.75: (0, 20),
                2.36: (0, 5),
            },
        }
        assert get_is_coarse_band("single", 10) == IS_COARSE_SINGLE_SIZED_BANDS[10]

    def test_astm_specific_getter_matches_backward_compatible_getter(self):
        assert get_astm_coarse_band(20) == get_coarse_band(20)

    def test_unknown_zone_raises(self):
        with pytest.raises(KeyError):
            get_fine_band("V")

    def test_unknown_coarse_size_raises(self):
        with pytest.raises(KeyError):
            get_coarse_band(25)
