"""Tests for gradation correction recommendations (blending mass balance)."""

from __future__ import annotations

import pytest

from concrete_mix.engine.grading import recommend_gradation_corrections


def test_too_coarse_sieve_prediction():
    """37.5 mm at 40.4% vs 90–100 band → add finer material.

    Target = midpoint 95%; x = (95 − 40.4) / (100 − 40.4) ≈ 0.916.
    """
    corrections = recommend_gradation_corrections(
        [37.5], [40.4], {37.5: (90.0, 100.0)}
    )
    assert len(corrections) == 1
    c = corrections[0]
    assert c.too_coarse is True
    assert c.target == 95.0
    assert c.deviation_pp == 90.0 - 40.4
    assert c.blend_fraction == pytest.approx(0.9161, abs=1e-3)
    assert "passes the 37.5 mm sieve" in c.action
    # Far off spec → re-screen/re-crush guidance takes priority
    assert "re-screen" in c.action


def test_too_fine_sieve_prediction():
    """4.75 mm at 8.4% vs 0–5 band → add coarse / wash fines.

    Target = midpoint 2.5%; x = (8.4 − 2.5) / 8.4 ≈ 0.702.
    """
    corrections = recommend_gradation_corrections(
        [4.75], [8.4], {4.75: (0.0, 5.0)}
    )
    assert len(corrections) == 1
    c = corrections[0]
    assert c.too_coarse is False
    assert c.target == 2.5
    assert c.deviation_pp == 8.4 - 5.0
    assert c.blend_fraction == pytest.approx(0.7024, abs=1e-3)
    assert "retained on the 4.75 mm sieve" in c.action
    assert "washing" in c.action


def test_moderate_correction_has_no_rescreen_prefix():
    """A small deviation should recommend plain blending.

    600 µm at 36% vs 10–30 band: target 20%, x = (36 − 20) / 36 ≈ 0.44.
    """
    corrections = recommend_gradation_corrections(
        [0.600], [36.0], {0.600: (10.0, 30.0)}
    )
    assert len(corrections) == 1
    c = corrections[0]
    assert c.blend_fraction == pytest.approx(0.4444, abs=1e-3)
    assert "re-screen" not in c.action
    assert "washing" not in c.action
    assert "blend in" in c.action


def test_conforming_gradation_returns_no_corrections():
    assert (
        recommend_gradation_corrections(
            [4.75, 2.36], [95.0, 20.0], {4.75: (90.0, 100.0), 2.36: (10.0, 30.0)}
        )
        == []
    )


def test_sieves_missing_from_band_are_ignored():
    corrections = recommend_gradation_corrections(
        [112.0], [3.0], {4.75: (0.0, 5.0)}
    )
    assert corrections == []


def test_multiple_violations_all_predicted():
    """The 40 mm graded case: 37.5 too coarse + 4.75 / 2.36 too fine."""
    band = {37.5: (90.0, 100.0), 4.75: (0.0, 5.0), 2.36: (0.0, 5.0)}
    corrections = recommend_gradation_corrections(
        [37.5, 4.75, 2.36], [40.4, 8.4, 6.0], band
    )
    assert [c.sieve_mm for c in corrections] == [37.5, 4.75, 2.36]
    assert [c.too_coarse for c in corrections] == [True, False, False]
