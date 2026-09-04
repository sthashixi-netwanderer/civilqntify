"""Tests for the standalone defective-rate 'k' factor (probit via scipy)."""

import pytest

from concrete_mix.utils.statistics import defective_k_factor


def test_percent_and_fraction_agree():
    assert defective_k_factor(5) == pytest.approx(defective_k_factor(0.05))
    assert defective_k_factor(3) == pytest.approx(defective_k_factor(0.03))
    assert defective_k_factor(2.5) == pytest.approx(defective_k_factor(0.025))


def test_known_quantiles():
    # scipy.stats.norm.ppf spot values: P(Z ≤ k) = 1 − p.
    assert defective_k_factor(5) == pytest.approx(1.6448536269514722)
    assert defective_k_factor(3) == pytest.approx(1.8807936082)
    assert defective_k_factor(1.0) == pytest.approx(2.3263478740408408)
    assert defective_k_factor(10.0) == pytest.approx(1.2815515655446004)


def test_monotone_in_defectives():
    # Fewer defectives → higher bar → larger k.
    assert defective_k_factor(1) > defective_k_factor(5) > defective_k_factor(10)


def test_sub_one_percent_needs_proportion():
    # 0.005 reads as a 0.5% proportion; a bare 0.5 would read as 50%.
    assert defective_k_factor(0.005) == pytest.approx(2.5758293035489004)
    assert defective_k_factor(0.5) == pytest.approx(0.0)


def test_invalid_rates_rejected():
    for bad in (0, 0.0, -3, -0.01, 100, 100.0, 150, float("nan")):
        with pytest.raises(ValueError, match="not usable"):
            defective_k_factor(bad)


def test_doe_k_is_two_dp():
    from concrete_mix.codes.tables.doe_tables import get_k_value

    assert get_k_value(5.0) == 1.64
    assert get_k_value(3.0) == 1.88
    assert get_k_value(2.5) == 1.96
    assert get_k_value(1.0) == 2.33
    assert get_k_value(10.0) == 1.28
    assert get_k_value(0.5) == 2.58   # sub-1% percent still reads as percent
    assert get_k_value(15.0) == 1.04  # computed, no longer clamped
    with pytest.raises(ValueError, match="not usable"):
        get_k_value(0.0)
