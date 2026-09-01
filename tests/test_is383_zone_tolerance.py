"""IS 383:2016 Table 9 limits and the Clause 6.3 zone-classification
tolerance.

Table 9 values are asserted verbatim against
docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md — this file
locks the corrected 2016 zone table (the code previously carried
pre-2016-style limits for Zones II–IV).
"""

from __future__ import annotations

import pytest

from concrete_mix.codes.tables.is_tables import GRADING_ZONE_LIMITS
from concrete_mix.engine.grading import (
    classify_is383_zone,
    determine_grading_zone,
)

# Zone keyed by the 600 µm sieve (Table 9's discriminating sieve).
ZONE_BY_P600 = {"I": (15, 34), "II": (35, 59), "III": (60, 79), "IV": (80, 100)}


class TestTable9Verbatim:
    def test_zone_i(self):
        assert GRADING_ZONE_LIMITS["I"] == {
            10.0: (100, 100),
            4.75: (90, 100),
            2.36: (60, 95),
            1.18: (30, 70),
            0.600: (15, 34),
            0.300: (5, 20),
            0.150: (0, 10),
        }

    def test_zone_ii(self):
        assert GRADING_ZONE_LIMITS["II"] == {
            10.0: (100, 100),
            4.75: (90, 100),
            2.36: (75, 100),
            1.18: (55, 90),
            0.600: (35, 59),
            0.300: (8, 30),
            0.150: (0, 10),
        }

    def test_zone_iii(self):
        assert GRADING_ZONE_LIMITS["III"] == {
            10.0: (100, 100),
            4.75: (90, 100),
            2.36: (85, 100),
            1.18: (75, 100),
            0.600: (60, 79),
            0.300: (12, 40),
            0.150: (0, 10),
        }

    def test_zone_iv(self):
        assert GRADING_ZONE_LIMITS["IV"] == {
            10.0: (100, 100),
            4.75: (95, 100),
            2.36: (95, 100),
            1.18: (90, 100),
            0.600: (80, 100),
            0.300: (15, 50),
            0.150: (0, 15),
        }


def _passing(zone: str, **overrides: float) -> dict[float, float]:
    """A fully in-zone grading for *zone* with optional per-sieve overrides."""
    nominal = {
        "I": (100, 95, 85, 60, 25, 10, 2),
        "II": (100, 98, 90, 70, 45, 20, 5),
        "III": (100, 96, 92, 85, 70, 25, 4),
        "IV": (100, 99, 97, 95, 88, 30, 10),
    }[zone]
    sieves = (10.0, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150)
    values = dict(zip(sieves, nominal))
    for sieve, value in overrides.items():
        values[float(sieve)] = value
    return values


class TestClassifyZone:
    def test_zone_keyed_by_600um(self):
        for zone, (lo, hi) in ZONE_BY_P600.items():
            assert classify_is383_zone(_passing(zone)).zone == zone
            # mid-range 600 µm value
            mid = (lo + hi) / 2
            p = _passing("II", **{"0.600": mid})
            assert classify_is383_zone(p).zone == zone

    def test_in_zone_conforms_fully(self):
        for zone in ZONE_BY_P600:
            c = classify_is383_zone(_passing(zone))
            assert c.conforms, (zone, c.violations)
            assert c.deviations == ()
            assert not c.tolerance_used
            assert not c.crushed_sand_relief_used

    def test_missing_600um_means_no_zone(self):
        p = _passing("II")
        del p[0.600]
        c = classify_is383_zone(p)
        assert c.zone is None
        assert not c.conforms

    def test_determine_grading_zone_uses_classifier(self):
        assert determine_grading_zone(_passing("III")) == "III"


class TestClause63Tolerance:
    def test_single_sieve_deviation_within_5pct_is_tolerated(self):
        # Zone II 2.36 limit is 75–100; 72 is 3 points below → tolerated.
        c = classify_is383_zone(_passing("II", **{"2.36": 72.0}))
        assert c.zone == "II"
        assert c.conforms
        assert c.tolerance_used
        assert len(c.deviations) == 1
        assert "2.36" in c.deviations[0]

    def test_single_sieve_deviation_beyond_5pct_fails(self):
        # 6 points below the 75 lower limit of Zone II.
        c = classify_is383_zone(_passing("II", **{"2.36": 69.0, "1.18": 65.0}))
        assert c.zone == "II"
        assert not c.conforms
        assert c.violations

    def test_cumulative_10pct_cap(self):
        # Two tolerated deviations (3 + 3 = 6 ≤ 10) still conform …
        c = classify_is383_zone(
            _passing("II", **{"2.36": 72.0, "1.18": 52.0})
        )
        assert c.conforms
        assert len(c.deviations) == 2
        # … but 4 + 4 + 4 = 12 > 10 → the sieve crossing the cumulative
        # cap becomes a violation.
        c2 = classify_is383_zone(
            _passing(
                "II",
                **{"2.36": 71.0, "1.18": 51.0, "0.300": 3.5},
            )
        )
        assert not c2.conforms

    def test_zone_i_coarse_limit_not_tolerated(self):
        # Zone I: tolerance never applies on its coarse (lower) limits.
        # 2.36 at 55 is 5 points below the Zone I lower limit of 60 — the
        # exact amount that would be tolerated elsewhere.
        p = _passing("I", **{"2.36": 55.0, "1.18": 40.0})
        c = classify_is383_zone(p)
        assert c.zone == "I"
        assert not c.conforms
        assert any("2.36" in v for v in c.violations)

    def test_zone_i_fine_side_deviation_is_tolerated(self):
        # Zone I upper limits are NOT the coarse limit — a too-fine
        # deviation on the fine side is tolerated (0.300 limit 5–20 → 23).
        c = classify_is383_zone(_passing("I", **{"0.300": 23.0, "0.150": 9.0}))
        assert c.conforms
        assert c.tolerance_used

    def test_zone_iv_finer_limit_not_tolerated(self):
        # Zone IV: tolerance never applies on its finer (upper) limits.
        # 0.300 limit is 15–50; 54 is 4 points above — would be tolerated
        # in Zones I–III but not on the fine limit of Zone IV.
        p = _passing("IV", **{"0.300": 54.0, "0.150": 14.0})
        c = classify_is383_zone(p)
        assert c.zone == "IV"
        assert not c.conforms
        assert any("300" in v for v in c.violations)

    def test_zone_iv_coarse_side_deviation_is_tolerated(self):
        # Zone IV lower limits are not the finer limit — 0.300 at 12
        # (limit 15) is 3 points low → tolerated.
        c = classify_is383_zone(_passing("IV", **{"0.300": 12.0}))
        assert c.conforms
        assert c.tolerance_used

    def test_crushed_stone_sand_150um_relief(self):
        # Zone II 150 µm limit is 10 %; 14 % fails for natural sand …
        c = classify_is383_zone(_passing("II", **{"0.150": 14.0}))
        assert not c.conforms
        # … but conforms for crushed stone sand (Table 9 Note 1: 20 %).
        c2 = classify_is383_zone(_passing("II", **{"0.150": 14.0}), crushed_sand=True)
        assert c2.conforms
        assert c2.crushed_sand_relief_used
        assert not c2.tolerance_used  # relief, not the 6.3 tolerance

    def test_crushed_stone_sand_relief_caps_at_20(self):
        c = classify_is383_zone(_passing("II", **{"0.150": 24.0}), crushed_sand=True)
        assert not c.conforms

    def test_tolerance_not_applied_at_600um(self):
        # The zone itself comes from the 600 µm sieve — a value inside a
        # different zone's 600 µm range classifies to that zone instead of
        # being "tolerated" (45 → Zone II, 65 → Zone III).
        assert classify_is383_zone(_passing("II", **{"0.600": 65.0})).zone == "III"


class TestNearestZoneForFractional600um:
    def test_fractional_gap_assigns_nearest_zone(self):
        # 34.5 sits in the 34–35 gap between Zones I and II.
        c = classify_is383_zone(_passing("II", **{"0.600": 34.5}))
        assert c.zone in ("I", "II")


class TestPSDLinkZoneFields:
    def test_linkage_carries_zone_conformance(self):
        from concrete_mix.engine.psd import IS_FINE_SIEVES, compute_psd
        from concrete_mix.engine.psd_link import derive_mix_design_params

        # Zone II with 2.36 at 72 % — a tolerated Clause 6.3 deviation.
        result = compute_psd(
            [0, 20, 260, 20, 250, 250, 150], IS_FINE_SIEVES, pan_mass=50.0
        )
        linkage = derive_mix_design_params(result)
        assert linkage.grading_zone == "II"
        assert linkage.zone_conforms
        assert len(linkage.zone_deviations) == 1
        assert not linkage.zone_crushed_sand_relief

    def test_linkage_warns_beyond_tolerance(self):
        from concrete_mix.engine.psd import IS_FINE_SIEVES, compute_psd
        from concrete_mix.engine.psd_link import derive_mix_design_params

        result = compute_psd(
            [0, 20, 290, 40, 200, 250, 150], IS_FINE_SIEVES, pan_mass=50.0
        )
        linkage = derive_mix_design_params(result)
        assert linkage.grading_zone == "II"
        assert not linkage.zone_conforms
        assert any("Clause 6.3" in w for w in linkage.warnings)
