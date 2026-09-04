"""Regression tests for values published in the final-year report.

If an application calculation changes, these tests force the report validation
artifacts to be regenerated from ``report_validation.generate_validation_dataset``.
"""

from __future__ import annotations

import pytest

from report_validation import ACCEPTANCE_LIMIT_PERCENT, generate_validation_dataset


@pytest.fixture(scope="module")
def report_data():
    return generate_validation_dataset()


def _app_values(example: dict) -> dict[str, float]:
    return {row["key"]: row["app_result"] for row in example["parameters"]}


def test_report_aci_values_come_from_current_engine(report_data):
    values = _app_values(report_data["standard_examples"]["aci"])
    assert values == pytest.approx(
        {
            # Table 26.4.3.1(b): 2500 psi + 1000 psi = 3500 psi = 24.13 MPa,
            # reported ceiled to whole MPa (app policy, conservative).
            "target_mean_strength_mpa": 25.0,
            "w_c_ratio": 0.6114492753623189,
            "water_kg": 178.0,
            "cement_kg": 291.1,
            "fine_aggregate_kg": 775.1,
            "coarse_aggregate_kg": 1141.7,
            "air_volume_percent": 1.0,
        }
    )


def test_report_is_values_come_from_current_engine(report_data):
    values = _app_values(report_data["standard_examples"]["is"])
    assert values == pytest.approx(
        {
            # Clause 4.2 / Annex A: 40 + 1.65 x 5 = 48.25 -> 49 MPa
            # (app policy: target ceiled to whole MPa for all codes).
            # Reported quantities follow the annexes' whole-kg convention.
            "target_mean_strength_mpa": 49.0,
            "w_c_ratio": 0.36,
            "water_kg": 148.0,
            "cement_kg": 415.0,
            "fine_aggregate_kg": 646.0,
            "coarse_aggregate_kg": 1235.0,
            "admixture_kg": 4.15,
            "air_volume_percent": 1.0,
        }
    )


def test_report_doe_values_come_from_current_engine(report_data):
    values = _app_values(report_data["standard_examples"]["doe"])
    assert values == pytest.approx(
        {
            "target_mean_strength_mpa": 35.0,
            "w_c_ratio": 0.5,
            "water_kg": 160.0,
            "cement_kg": 320.0,
            # Figure 6 digitisation (21.8% fines vs the standard's chart
            # reading of 22%): 400/1445 vs the text's 405/1440.
            "fine_aggregate_kg": 400.0,
            "coarse_aggregate_kg": 1445.0,
        }
    )


def test_report_quantification_values_come_from_current_pipeline(report_data):
    values = _app_values(report_data["quantification"])
    assert values == pytest.approx(
        {
            "gross_concrete_volume_m3": 10.3,
            "total_cement_kg": 2998.3,
            "total_cement_bags": 71.0,
            "total_water_liters": 1833.4,
            "total_fine_aggregate_kg": 7983.5,
            "total_coarse_aggregate_kg": 11759.5,
        }
    )


def test_report_cost_values_come_from_shared_app_service(report_data):
    estimate = report_data["cost"]["estimate"]
    assert estimate["total_material_cost"] == pytest.approx(101984.75000000001)
    assert estimate["material_cost_per_m3"] == pytest.approx(971.2833333333334)
    assert estimate["total_project_cost"] == pytest.approx(145864.35937500003)
    assert estimate["cost_per_bag"] == pytest.approx(203.43704236401678)


def test_all_published_validation_checks_meet_acceptance_limit(report_data):
    # report_validation 2026 now reports "Exact match" when manual == app (0% error);
    # older artifact used "Met".  Accept either, and allow exact-zero error.
    assert report_data["summary"]["status"] in ("Met", "Exact match")
    assert report_data["summary"]["maximum_error_percent"] <= ACCEPTANCE_LIMIT_PERCENT + 1e-9
    assert all(
        row["status"] == "Pass" for row in report_data["validation_rows"]
    )


def test_cross_method_table_contains_all_three_current_engine_outputs(report_data):
    methods = report_data["cross_method_comparison"]["methods"]
    assert set(methods) == {"ACI 211.1-22", "IS 10262:2019", "DOE (BRE 331)"}
    assert methods["ACI 211.1-22"]["cement_kg"] == pytest.approx(415.2)
    # IS result reports whole kg per the annexes (ceiled target 32 MPa).
    assert methods["IS 10262:2019"]["cement_kg"] == pytest.approx(398.0)
    assert methods["DOE (BRE 331)"]["cement_kg"] == pytest.approx(305.0)
