"""BS 882 verified Tables 3/4/6 and independent shape checks."""

import pytest

from concrete_mix.codes.tables.bs882 import (
    get_bs_coarse_band, get_bs_fine_band,
)
from concrete_mix.engine.psd import compute_psd
from concrete_mix.validation.bs882 import (
    BS882QualityInputs, classify_bs882_sand,
    evaluate_bs882_coarse, evaluate_bs882_fine,
)


def psd(passing: dict[float, float]):
    sizes = sorted(passing, reverse=True)
    cumulative = [100 - passing[s] for s in sizes]
    masses = [cumulative[0]] + [
        b - a for a, b in zip(cumulative, cumulative[1:])
    ]
    return compute_psd(masses, sizes, passing[sizes[-1]])


@pytest.mark.parametrize('kind,size,expected', [
    ('graded', 40, {50: (100, 100), 37.5: (90, 100), 20: (35, 70),
                    14: (25, 55), 10: (10, 40), 5: (0, 5)}),
    ('graded', 20, {37.5: (100, 100), 20: (90, 100), 14: (40, 80),
                    10: (30, 60), 5: (0, 10)}),
    ('graded', 14, {20: (100, 100), 14: (90, 100), 10: (50, 85), 5: (0, 10)}),
    ('single', 40, {50: (100, 100), 37.5: (85, 100), 20: (0, 25), 10: (0, 5)}),
    ('single', 20, {37.5: (100, 100), 20: (85, 100), 14: (0, 70),
                    10: (0, 25), 5: (0, 5)}),
    ('single', 14, {20: (100, 100), 14: (85, 100), 10: (0, 50), 5: (0, 10)}),
    ('single', 10, {14: (100, 100), 10: (85, 100), 5: (0, 25), 2.36: (0, 5)}),
    ('single', 5, {10: (100, 100), 5: (45, 100), 2.36: (0, 30)}),
])
def test_verified_table3(kind, size, expected):
    assert get_bs_coarse_band(kind, size) == expected
    for boundary in (0, 1):
        sample = psd({s: limits[boundary] for s, limits in expected.items()})
        assert evaluate_bs882_coarse(
            sample, expected, BS882QualityInputs()
        )[0].status == 'pass'


@pytest.mark.parametrize('grade,additional', [
    ('Overall', [(60, 100), (30, 100), (15, 100), (5, 70)]),
    ('C', [(60, 100), (30, 90), (15, 54), (5, 40)]),
    ('M', [(65, 100), (45, 100), (25, 80), (5, 48)]),
    ('F', [(80, 100), (70, 100), (55, 100), (5, 70)]),
])
def test_table4_combines_overall_with_additional(grade, additional):
    expected = {10: (100, 100), 5: (89, 100), .15: (0, 15)}
    expected.update(dict(zip([2.36, 1.18, .6, .3], additional)))
    assert get_bs_fine_band(grade) == expected


def test_overlapping_classification_and_missing_data():
    passing = {10: 100, 5: 95, 2.36: 90, 1.18: 80, .6: 40, .3: 20, .15: 10}
    assert classify_bs882_sand(passing) == ('C', 'M')
    del passing[5]
    assert classify_bs882_sand(passing) == ()
    assert evaluate_bs882_fine(psd(passing), BS882QualityInputs())[0].status == 'not_evaluated'


def test_crushed_rock_exception_not_for_heavy_floors():
    assert get_bs_fine_band('C', crushed_rock=True)[.15] == (0, 20)
    assert get_bs_fine_band('C', crushed_rock=True, heavy_duty_floor=True)[.15] == (0, 15)
    fine = psd({10: 100, 5: 95, 2.36: 90, 1.18: 90, .6: 90, .3: 60, .15: 10})
    checks = evaluate_bs882_fine(fine, BS882QualityInputs(heavy_duty_floor=True))
    assert any(c.clause.startswith('5.2.2') and c.failed for c in checks)
    assert any(c.status == 'not_evaluated' and 'consecutive' in c.title for c in checks)


@pytest.mark.parametrize('kind,source,heavy,limit', [
    ('coarse', 'uncrushed_gravel', False, 2),
    ('coarse', 'partially_crushed_gravel', False, 2),
    ('coarse', 'crushed_gravel', False, 2),
    ('coarse', 'crushed_rock', False, 4),
    ('fine', 'uncrushed_gravel', False, 4),
    ('fine', 'crushed_rock', False, 16),
    ('fine', 'crushed_rock', True, 9),
])
def test_table6_independent_washed_fines(kind, source, heavy, limit):
    sample = psd({10: 100, 5: 95, 2.36: 90, 1.18: 80, .6: 40, .3: 20, .15: 10, .075: 9})
    for measured, status in [(None, 'not_evaluated'), (limit, 'pass'), (limit + .01, 'fail')]:
        inputs = BS882QualityInputs(source, heavy, measured)
        checks = (evaluate_bs882_fine(sample, inputs) if kind == 'fine' else
                  evaluate_bs882_coarse(sample, get_bs_coarse_band('single', 5), inputs))
        assert next(c for c in checks if 'Table 6' in c.clause).status == status


@pytest.mark.parametrize('source,limit', [('uncrushed_gravel', 50), ('crushed_gravel', 40), ('crushed_rock', 40)])
def test_independent_flakiness_limits(source, limit):
    sample = psd({10: 100, 5: 80, 2.36: 10})
    for fi, status in [(None, 'not_evaluated'), (limit, 'pass'), (limit + 1, 'fail')]:
        checks = evaluate_bs882_coarse(sample, get_bs_coarse_band('single', 5),
                                      BS882QualityInputs(source_type=source, flakiness_index_pct=fi))
        assert next(c for c in checks if c.clause.startswith('4.2')).status == status


@pytest.mark.parametrize('value', [-1, 101, float('nan'), float('inf')])
def test_invalid_quality_percent_rejected(value):
    with pytest.raises(ValueError):
        evaluate_bs882_fine(psd({10: 100}), BS882QualityInputs(washed_fines_pct=value))


def test_missing_coarse_measurement_not_pass_and_dash_ignored():
    band = get_bs_coarse_band('single', 40)
    sample = psd({50: 100, 37.5: 90, 20: 20})
    assert evaluate_bs882_coarse(sample, band, BS882QualityInputs())[0].status == 'not_evaluated'
    sample = psd({50: 100, 37.5: 90, 20: 20, 14: 15, 10: 3, 5: 2})
    assert evaluate_bs882_coarse(sample, band, BS882QualityInputs())[0].status == 'pass'
