"""Tests for concrete_mix.estimators.strength_from_ratio."""

from concrete_mix.estimators.strength_from_ratio import (
    estimate_strength_from_ratio,
    _manual_std_dev,
    _manual_target,
    _grade_from_fck,
)


class TestManualStdDev:
    """Tiered standard deviation for the Manual code path."""

    def test_low_strength(self):
        assert _manual_std_dev(10.0) == 3.5

    def test_boundary_15(self):
        assert _manual_std_dev(15.0) == 4.0

    def test_mid_range(self):
        assert _manual_std_dev(20.0) == 4.0

    def test_boundary_25(self):
        assert _manual_std_dev(25.0) == 4.0

    def test_high_strength(self):
        assert _manual_std_dev(30.0) == 5.0

    def test_very_high(self):
        assert _manual_std_dev(60.0) == 5.0


class TestManualTarget:
    """f_target = f_ck + 1.65 × s_d."""

    def test_basic(self):
        assert abs(_manual_target(30.0, 5.0) - 38.25) < 0.001

    def test_low(self):
        assert abs(_manual_target(10.0, 3.5) - 15.775) < 0.001


class TestGradeFromFck:
    """Map characteristic strength to IS grade label."""

    def test_m10(self):
        assert _grade_from_fck(10.0) == "M10"

    def test_m15(self):
        assert _grade_from_fck(17.0) == "M15"

    def test_m25(self):
        assert _grade_from_fck(25.0) == "M25"

    def test_m40(self):
        assert _grade_from_fck(40.0) == "M40"

    def test_m80_plus(self):
        assert _grade_from_fck(85.0) == "M80"


class TestEstimateStrengthManual:
    """Full function — manual code path. User's f_ck drives the target."""

    def test_m25_input(self):
        """User enters fck=25 MPa (M25), typical 1:1.5:2.8 mix."""
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=25.0, code="manual")
        # W/C from ratio: 0.30 + 0.03*(1.5+2.8) = 0.429
        assert r["implied_wc_ratio"] == 0.43
        # f_ck is the user's input, unchanged
        assert r["characteristic_strength_fck"] == 25.0
        # Manual margin: s_d=4.0 (25 MPa is in 15-25 range), target = 25 + 1.65*4 = 31.6
        assert r["standard_deviation"] == 4.0
        assert abs(r["target_strength_f_target"] - 31.6) < 0.01

    def test_m30_input(self):
        """User enters fck=30 MPa (M30)."""
        r = estimate_strength_from_ratio(1.0, 2.0, 3.0, fck=30.0, code="manual")
        assert r["characteristic_strength_fck"] == 30.0
        # Manual margin: s_d=5.0 (>25), target = 30 + 1.65*5 = 38.25
        assert r["standard_deviation"] == 5.0
        assert abs(r["target_strength_f_target"] - 38.25) < 0.01

    def test_m10_input(self):
        """User enters fck=10 MPa (M10)."""
        r = estimate_strength_from_ratio(1.0, 4.0, 8.0, fck=10.0, code="manual")
        assert r["characteristic_strength_fck"] == 10.0
        # Manual margin: s_d=3.5 (<15), target = 10 + 1.65*3.5 = 15.775
        assert r["standard_deviation"] == 3.5
        assert abs(r["target_strength_f_target"] - 15.775) < 0.01

    def test_all_values_rounded_2dp(self):
        r = estimate_strength_from_ratio(1.0, 2.0, 3.0, fck=25.0)
        for key in ("implied_wc_ratio", "characteristic_strength_fck",
                     "standard_deviation", "target_strength_f_target"):
            val = r[key]
            assert val == round(val, 2), f"{key} not rounded: {val}"

    def test_return_keys(self):
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=25.0)
        expected_keys = {
            "implied_wc_ratio", "characteristic_strength_fck",
            "standard_deviation", "target_strength_f_target",
            "margin_formula", "cement_kg", "water_kg",
            "fine_aggregate_kg", "coarse_aggregate_kg",
        }
        assert set(r.keys()) == expected_keys

    def test_fck_passthrough(self):
        """User's f_ck should pass through unchanged."""
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=42.5)
        assert r["characteristic_strength_fck"] == 42.5


class TestEstimateStrengthIS10262:
    """IS 10262 target margin path."""

    def test_m25_is10262(self):
        """M25: IS Table 2 std dev = 4.0, X = 5.5."""
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=25.0, code="is10262")
        assert r["characteristic_strength_fck"] == 25.0
        assert r["target_strength_f_target"] >= 25.0
        assert "1.65" in r["margin_formula"]

    def test_m40_is10262(self):
        """M40: IS Table 2 std dev = 5.0, X = 6.5."""
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=40.0, code="is10262")
        assert r["characteristic_strength_fck"] == 40.0
        # target = max(40+1.65*5, 40+6.5) = max(48.25, 46.5) = 48.25
        assert abs(r["target_strength_f_target"] - 48.25) < 0.01


class TestEstimateStrengthACI:
    """ACI 318 target margin path."""

    def test_m25_aci(self):
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=25.0, code="aci211")
        assert r["characteristic_strength_fck"] == 25.0
        assert r["target_strength_f_target"] >= 25.0
        assert "1.34" in r["margin_formula"]

    def test_aci_uses_s4(self):
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=30.0, code="aci211")
        assert r["standard_deviation"] == 4.0


class TestEstimateStrengthDOE:
    """DOE / BRE 331 target margin path."""

    def test_m25_doe(self):
        r = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=25.0, code="doe")
        assert r["characteristic_strength_fck"] == 25.0
        assert r["target_strength_f_target"] >= 25.0
        assert "1.64" in r["margin_formula"]


class TestWCDerivation:
    """Verify W/C = 0.30 + 0.03 × total_aggregate."""

    def test_zero_aggregate(self):
        r = estimate_strength_from_ratio(1.0, 0.0, 0.0, fck=25.0)
        assert r["implied_wc_ratio"] == 0.30

    def test_known_total(self):
        r = estimate_strength_from_ratio(1.0, 3.0, 4.0, fck=25.0)
        # total_aggregate = 7.0, W/C = 0.30 + 0.03*7.0 = 0.51
        assert r["implied_wc_ratio"] == 0.51

    def test_different_fck_same_ratio(self):
        """Same mix ratio → same W/C regardless of f_ck."""
        r1 = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=20.0)
        r2 = estimate_strength_from_ratio(1.0, 1.5, 2.8, fck=40.0)
        assert r1["implied_wc_ratio"] == r2["implied_wc_ratio"]
