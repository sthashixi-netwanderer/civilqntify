"""BS 812-103.1 method wrapper: washed/dry reconciliation + reporting."""

import pytest

from concrete_mix.engine.bs812 import (
    compute_bs812_psd, report_whole_percent, washed_fines_percent,
)


@pytest.fixture
def washed_data():
    # M1 = 1000 g; M2 = 990 g; dry: 500, 300, 170, 5 on 75 µm, 15 pan.
    return dict(mass_retained=[500, 300, 170, 5], sieve_sizes=[10, 5, 2.36, .075],
                pan_mass=15, original_dry_mass=1000, washed_dry_mass=990)


def test_washed_fines_used_once(washed_data):
    r = compute_bs812_psd(method='washed', **washed_data)
    assert r.total_mass == 1000
    assert r.pan_mass == 15 + 10
    assert r.percent_passing == pytest.approx([50, 20, 3, 2.5])
    assert r.fineness_modulus is None
    assert (r.d10, r.uniformity_coefficient, r.coefficient_of_curvature) == (None, None, None)
    assert r.mass_retained == [500, 300, 170, 5]  # raw stays raw


def test_missing_m2_rejected(washed_data):
    del washed_data['washed_dry_mass']
    with pytest.raises(ValueError, match='M2'):
        compute_bs812_psd(method='washed', **washed_data)


def test_dry_method_without_washing(washed_data):
    r = compute_bs812_psd(method='dry', original_dry_mass=990, **{
        k: washed_data[k] for k in ('mass_retained', 'sieve_sizes', 'pan_mass')})
    assert r.pan_mass == 15
    assert r.total_mass == 990


def test_nonfinite_negative_mismatch_rejected(washed_data):
    with pytest.raises(ValueError):
        compute_bs812_psd(method='dry', mass_retained=[-5], sieve_sizes=[10],
                          pan_mass=0, original_dry_mass=100)
    with pytest.raises(ValueError):
        compute_bs812_psd(method='dry', mass_retained=[float('nan')], sieve_sizes=[10],
                          pan_mass=0, original_dry_mass=100)
    with pytest.raises(ValueError, match='match'):
        compute_bs812_psd(method='dry', mass_retained=[1], sieve_sizes=[10, 5],
                          pan_mass=0, original_dry_mass=100)


@pytest.mark.parametrize('changes', [
    {'pan_mass': 14},  # unexplained residue loss cannot become fines
    {'original_dry_mass': 0},
    {'original_dry_mass': float('inf')},
    {'washed_dry_mass': 1001},
    {'washed_dry_mass': float('nan')},
    {'pan_mass': float('inf')},
    {'sieve_sizes': [10, 5, 2.36, .15]},  # washed method requires 75 µm
    {'sieve_sizes': [10, 5, 5, .075]},
    {'sieve_sizes': [.075, 5, 2.36, 10]},
    {'sieve_sizes': [10, 5, 2.36, float('nan')]},
    {'method': 'unknown'},
    {'method': 'dry'},  # M2 must not silently be ignored
])
def test_invalid_or_unreconciled_washed_analysis(washed_data, changes):
    data = dict(washed_data, method='washed')
    data.update(changes)
    with pytest.raises(ValueError):
        compute_bs812_psd(**data)


def test_table6_washed_only_differs_from_psd_pan(washed_data):
    assert washed_fines_percent(1000, 990) == pytest.approx(1)
    assert compute_bs812_psd(method='washed', **washed_data).percent_passing[-1] == pytest.approx(2.5)


def test_nonfinite_measurements_rejected():
    with pytest.raises(ValueError):
        washed_fines_percent(float('nan'), 990)
    with pytest.raises(ValueError):
        washed_fines_percent(1000, -1)


@pytest.mark.parametrize('value,expected', [(2.4, 2), (2.5, 3), (2.6, 3), (-2.5, -3), (-2.4, -2)])
def test_half_up_whole_percent(value, expected):
    assert report_whole_percent(value) == expected
