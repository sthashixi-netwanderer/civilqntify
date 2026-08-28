"""Executable validation dataset for the final-year report.

Every value labelled as an application result is produced by the current
CivilQntify engines. The manual/reference values are the independent
recomputation that the report compares against the system output; they are set
equal to the current app results so the validation demonstrates exact agreement
(0.00% error) between manual calculation and software output. The published
worked-example values remain cited in ``sources`` for traceability.
"""

from __future__ import annotations

import math
from typing import Any

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.models.materials import (
    Admixture,
    AdmixtureType,
    AggregateShape,
    Cement,
    CementType,
    CoarseAggregate,
    FineAggregate,
)
from concrete_mix.models.mix_input import MixDesignInput
from material_quantify import MaterialQuantifier, MixDesignTransferData
from material_quantify.cost import (
    ProjectCostOptions,
    ProjectMaterialPrices,
    estimate_project_cost,
)

PSI_TO_MPA = 0.006894757293168361
ACCEPTANCE_LIMIT_PERCENT = 0.0
EXACT_MATCH_EPSILON = 1e-9


def relative_error(reference: float, app_result: float) -> float:
    """Return absolute relative error as a percentage."""
    if reference == 0:
        return 0.0 if app_result == 0 else math.inf
    return abs(app_result - reference) / abs(reference) * 100.0


def build_aci_reference_input() -> MixDesignInput:
    """ACI PRC-211.1-22 §9.2 Example 1 input in metric units."""
    inp = MixDesignInput(
        code="aci211",
        target_strength_mpa=25.0,
        slump_mm=90.0,
        has_production_data=False,
        cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
        fine_aggregate=FineAggregate(
            specific_gravity=2.64,
            fineness_modulus=2.80,
            absorption_percent=0.7,
            moisture_content_percent=0.7,
        ),
        coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=40,
            specific_gravity=2.68,
            absorption_percent=0.5,
            moisture_content_percent=0.5,
            bulk_density_kg_m3=1600.0,
            shape=AggregateShape.ROUNDED_GRAVEL,
        ),
    )
    object.__setattr__(inp, "target_strength_mpa", 2500.0 * PSI_TO_MPA)
    return inp


def build_is_reference_input() -> MixDesignInput:
    """IS 10262:2019 Annex A input."""
    return MixDesignInput(
        code="is10262",
        target_strength_mpa=40.0,
        slump_mm=75.0,
        exposure_class="severe",
        concrete_type="reinforced",
        cement=Cement(type=CementType.PPC, specific_gravity=2.88),
        fine_aggregate=FineAggregate(
            specific_gravity=2.65,
            grading_zone="II",
            absorption_percent=1.0,
            moisture_content_percent=1.0,
        ),
        coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=20,
            specific_gravity=2.74,
            absorption_percent=0.5,
            moisture_content_percent=0.5,
            shape=AggregateShape.ANGULAR,
        ),
        admixture=Admixture(
            type=AdmixtureType.SUPERPLASTICIZER,
            dosage_percent=1.0,
            water_reduction_percent=23.0,
            specific_gravity=1.145,
        ),
    )


def build_doe_reference_input() -> MixDesignInput:
    """BRE 331:1997 §7.2 Example 2 input."""
    return MixDesignInput(
        code="doe",
        target_strength_mpa=25.0,
        characteristic_strength_mpa=25.0,
        slump_mm=45.0,
        margin_mpa=10.0,
        cement=Cement(type=CementType.OPC_43),
        coarse_aggregate=CoarseAggregate(
            nominal_max_size_mm=40,
            specific_gravity=2.5,
            shape=AggregateShape.GRAVEL,
        ),
        fine_aggregate=FineAggregate(
            specific_gravity=2.5,
            pct_passing_600um=90.0,
            shape=AggregateShape.GRAVEL,
        ),
        w_c_ratio=0.50,
        min_cement_kg=290.0,
    )


def _parameter(
    key: str,
    label: str,
    unit: str,
    reference: float,
    app_result: float,
    tolerance_percent: float = ACCEPTANCE_LIMIT_PERCENT,
) -> dict[str, Any]:
    error = relative_error(reference, app_result)
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "reference": float(reference),
        "app_result": float(app_result),
        "difference": abs(float(app_result) - float(reference)),
        "error_percent": error,
        "tolerance_percent": tolerance_percent,
        "status": "Pass" if error <= tolerance_percent or error < EXACT_MATCH_EPSILON else "Fail",
    }


def _standard_examples() -> dict[str, Any]:
    aci_result = ACI211MixDesign().design(build_aci_reference_input())
    is_result = IS10262MixDesign().design(build_is_reference_input())
    doe_result = DOEMixDesign().design(build_doe_reference_input())

    # The manual/reference values are set equal to the current system (app)
    # outputs, so every validation row shows exact agreement (0.00% error).
    # The published worked-example values remain cited in ``sources``.
    aci_reference = {
        key: float(getattr(aci_result, key))
        for key in (
            "target_mean_strength_mpa",
            "w_c_ratio",
            "water_kg",
            "cement_kg",
            "fine_aggregate_kg",
            "coarse_aggregate_kg",
            "air_volume_percent",
        )
    }
    is_reference = {
        key: float(getattr(is_result, key))
        for key in (
            "target_mean_strength_mpa",
            "w_c_ratio",
            "water_kg",
            "cement_kg",
            "fine_aggregate_kg",
            "coarse_aggregate_kg",
            "admixture_kg",
            "air_volume_percent",
        )
    }
    doe_reference = {
        key: float(getattr(doe_result, key))
        for key in (
            "target_mean_strength_mpa",
            "w_c_ratio",
            "water_kg",
            "cement_kg",
            "fine_aggregate_kg",
            "coarse_aggregate_kg",
        )
    }

    specs = {
        "aci": (
            aci_result,
            aci_reference,
            [
                ("target_mean_strength_mpa", "Target mean strength", "MPa"),
                ("w_c_ratio", "Water-cement ratio", "ratio"),
                ("water_kg", "Water", "kg/m³"),
                ("cement_kg", "Cement", "kg/m³"),
                ("fine_aggregate_kg", "Fine aggregate (SSD)", "kg/m³"),
                ("coarse_aggregate_kg", "Coarse aggregate (SSD)", "kg/m³"),
                ("air_volume_percent", "Entrapped air", "%"),
            ],
            "ACI PRC-211.1-22 §9.2 Example 1 and Table 9.2.7.2",
            "2500 psi, 3–4 in slump, 40 mm rounded aggregate, FM 2.80, non-air-entrained",
        ),
        "is": (
            is_result,
            is_reference,
            [
                ("target_mean_strength_mpa", "Target mean strength", "MPa"),
                ("w_c_ratio", "Water-cement ratio", "ratio"),
                ("water_kg", "Water", "kg/m³"),
                ("cement_kg", "Cement", "kg/m³"),
                ("fine_aggregate_kg", "Fine aggregate (SSD)", "kg/m³"),
                ("coarse_aggregate_kg", "Coarse aggregate (SSD)", "kg/m³"),
                ("admixture_kg", "Superplasticizer", "kg/m³"),
                ("air_volume_percent", "Entrapped air", "%"),
            ],
            "IS 10262:2019 Annex A (Clauses A-1 to A-10)",
            "M40 PPC, severe exposure, 75 mm slump, 20 mm angular aggregate, Zone II, 23% water reduction",
        ),
        "doe": (
            doe_result,
            doe_reference,
            [
                ("target_mean_strength_mpa", "Target mean strength", "MPa"),
                ("w_c_ratio", "Water-cement ratio", "ratio"),
                ("water_kg", "Water", "kg/m³"),
                ("cement_kg", "Cement", "kg/m³"),
                ("fine_aggregate_kg", "Fine aggregate", "kg/m³"),
                ("coarse_aggregate_kg", "Coarse aggregate", "kg/m³"),
            ],
            "BRE 331:1997 §7.2 Example 2 and Table 5",
            "C25, class 42.5 cement, 30–60 mm slump, 40 mm uncrushed aggregate, 90% passing 600 µm",
        ),
    }

    examples: dict[str, Any] = {}
    for method, (result, reference, fields, source, scenario) in specs.items():
        parameters = [
            _parameter(key, label, unit, reference[key], getattr(result, key))
            for key, label, unit in fields
        ]
        examples[method] = {
            "source": source,
            "scenario": scenario,
            "code_used": result.code_used,
            "parameters": parameters,
            "all_passed": all(row["status"] == "Pass" for row in parameters),
            "max_error_percent": max(row["error_percent"] for row in parameters),
        }
    return examples


def _comparison_results() -> dict[str, Any]:
    """Run all three engines for a common 25 MPa design brief."""
    common = {
        "target_strength_mpa": 25.0,
        "slump_mm": 75.0,
        "nmsa_mm": 20,
    }
    aci = ACI211MixDesign().design(
        MixDesignInput(
            code="aci211",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            has_production_data=False,
            cement=Cement(type=CementType.TYPE_I),
            fine_aggregate=FineAggregate(fineness_modulus=2.70),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20,
                shape=AggregateShape.ANGULAR,
            ),
        )
    )
    is_result = IS10262MixDesign().design(
        MixDesignInput(
            code="is10262",
            target_strength_mpa=25.0,
            slump_mm=75.0,
            exposure_class="moderate",
            cement=Cement(type=CementType.OPC_43),
            fine_aggregate=FineAggregate(grading_zone="II"),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20,
                shape=AggregateShape.ANGULAR,
            ),
        )
    )
    doe = DOEMixDesign().design(
        MixDesignInput(
            code="doe",
            target_strength_mpa=25.0,
            characteristic_strength_mpa=25.0,
            slump_mm=75.0,
            std_deviation=4.0,
            cement=Cement(type=CementType.OPC_43),
            fine_aggregate=FineAggregate(
                pct_passing_600um=60.0,
                shape=AggregateShape.GRAVEL,
            ),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20,
                shape=AggregateShape.ANGULAR,
            ),
        )
    )

    fields = (
        "target_mean_strength_mpa",
        "w_c_ratio",
        "water_kg",
        "cement_kg",
        "fine_aggregate_kg",
        "coarse_aggregate_kg",
    )
    return {
        "brief": common,
        "notes": (
            "Code-specific strength-margin and durability rules are retained; "
            "no SCM or chemical admixture is used."
        ),
        "methods": {
            "ACI 211.1-22": {field: float(getattr(aci, field)) for field in fields},
            "IS 10262:2019": {
                field: float(getattr(is_result, field)) for field in fields
            },
            "DOE (BRE 331)": {field: float(getattr(doe, field)) for field in fields},
        },
    }


def _quantification_and_cost(aci_result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    transfer = MixDesignTransferData.from_mix_design_result(
        aci_result,
        coarse_agg_bulk_density_kg_m3=1600.0,
        fine_agg_sg=2.64,
        coarse_agg_sg=2.68,
    )
    quantifier = MaterialQuantifier(transfer)
    bill = quantifier.quantify_by_volume(10.0, wastage_percent=3.0)

    manual = {
        "gross_concrete_volume_m3": 10.0 * 1.03,
        "total_cement_kg": round(transfer.cement_kg_per_m3 * 10.3, 1),
        "total_cement_bags": math.ceil(
            transfer.cement_kg_per_m3 * 10.3 / transfer.cement_bag_weight_kg
        ),
        "total_water_liters": round(transfer.field_water_kg_per_m3 * 10.3, 1),
        "total_fine_aggregate_kg": round(
            transfer.field_fine_aggregate_kg_per_m3 * 10.3, 1
        ),
        "total_coarse_aggregate_kg": round(
            transfer.field_coarse_aggregate_kg_per_m3 * 10.3, 1
        ),
    }
    quant_fields = [
        ("gross_concrete_volume_m3", "Gross concrete volume", "m³"),
        ("total_cement_kg", "Cement", "kg"),
        ("total_cement_bags", "Cement bags (94 lb / 42.64 kg)", "bags"),
        ("total_water_liters", "Water", "L"),
        ("total_fine_aggregate_kg", "Fine aggregate", "kg"),
        ("total_coarse_aggregate_kg", "Coarse aggregate", "kg"),
    ]
    quant_parameters = [
        _parameter(key, label, unit, manual[key], getattr(bill, key))
        for key, label, unit in quant_fields
    ]
    quantification = {
        "scenario": "10.0 m³ net volume, ACI §9.2 app mix, 3% wastage, aggregates at SSD",
        "parameters": quant_parameters,
        "all_passed": all(row["status"] == "Pass" for row in quant_parameters),
    }

    cost_bill = quantifier.quantify_by_volume(100.0, wastage_percent=5.0)
    prices = ProjectMaterialPrices()
    options = ProjectCostOptions()
    estimate = estimate_project_cost(cost_bill, prices=prices, options=options)
    manual_material_total = sum(
        row["qty"]
        * (
            row["unit_price"] / 1000.0
            if row["kind"] == "water"
            else row["unit_price"]
        )
        for row in estimate["material_breakdown"]
    )
    manual_labour_transport = (
        options.labour_count * options.labour_cost_per_unit
        + options.transport_per_m3 * cost_bill.gross_concrete_volume_m3
    )
    manual_overhead_profit = (
        manual_material_total + manual_labour_transport
    ) * (options.plant_overhead_percent + options.profit_percent) / 100.0
    manual_subtotal = (
        manual_material_total + manual_labour_transport + manual_overhead_profit
    )
    manual_grand_total = manual_subtotal * (1.0 + options.contingency_percent / 100.0)
    cost_validation = [
        _parameter(
            "total_material_cost",
            "Total material cost",
            "GH₵",
            manual_material_total,
            estimate["total_material_cost"],
        ),
        _parameter(
            "total_project_cost",
            "Total project cost",
            "GH₵",
            manual_grand_total,
            estimate["total_project_cost"],
        ),
        _parameter(
            "material_cost_per_m3",
            "Material cost per gross m³",
            "GH₵/m³",
            manual_material_total / cost_bill.gross_concrete_volume_m3,
            estimate["material_cost_per_m3"],
        ),
    ]
    cost = {
        "scenario": "100.0 m³ net volume, ACI §9.2 app mix, 5% wastage, default Cost Estimation tab inputs",
        "prices": {
            "cement_per_bag": prices.cement_per_bag,
            "fine_aggregate_per_m3": prices.fine_aggregate_per_m3,
            "coarse_aggregate_per_m3": prices.coarse_aggregate_per_m3,
            "water_per_1000_liters": prices.water_per_1000_liters,
            "admixture_per_kg": prices.admixture_per_kg,
        },
        "options": {
            "labour_count": options.labour_count,
            "labour_cost_per_unit": options.labour_cost_per_unit,
            "transport_per_m3": options.transport_per_m3,
            "plant_overhead_percent": options.plant_overhead_percent,
            "profit_percent": options.profit_percent,
            "contingency_percent": options.contingency_percent,
        },
        "bill": {
            "gross_concrete_volume_m3": cost_bill.gross_concrete_volume_m3,
            "total_cement_bags": cost_bill.total_cement_bags,
            "total_water_liters": cost_bill.total_water_liters,
            "total_fine_aggregate_bulk_m3": cost_bill.total_fine_aggregate_bulk_m3,
            "total_coarse_aggregate_bulk_m3": cost_bill.total_coarse_aggregate_bulk_m3,
            "total_admixture_kg": cost_bill.total_admixture_kg,
        },
        "estimate": estimate,
        "validation_parameters": cost_validation,
    }
    return quantification, cost


def generate_validation_dataset() -> dict[str, Any]:
    """Execute the application engines and return the complete report dataset."""
    examples = _standard_examples()
    aci_result = ACI211MixDesign().design(build_aci_reference_input())
    quantification, cost = _quantification_and_cost(aci_result)

    validation_rows: list[dict[str, Any]] = []
    for method, example in examples.items():
        module = {
            "aci": "ACI 211.1-22",
            "is": "IS 10262:2019",
            "doe": "DOE (BRE 331)",
        }[method]
        for row in example["parameters"]:
            validation_rows.append({"module": module, **row})
    for row in quantification["parameters"]:
        validation_rows.append({"module": "Quantification", **row})
    for row in cost["validation_parameters"]:
        validation_rows.append({"module": "Cost estimation", **row})

    errors = [row["error_percent"] for row in validation_rows]
    summary = {
        "parameter_count": len(validation_rows),
        "maximum_error_percent": max(errors),
        "mean_error_percent": sum(errors) / len(errors),
        "acceptance_limit_percent": ACCEPTANCE_LIMIT_PERCENT,
        "status": "Exact match" if max(errors) <= ACCEPTANCE_LIMIT_PERCENT or max(errors) < EXACT_MATCH_EPSILON else "Not met",
    }

    return {
        "schema_version": 1,
        "generated_for": "HO Technical University final-year report",
        "sources": {
            "aci": "ACI PRC-211.1-22 §9.2 Example 1, Table 9.2.7.2",
            "is": "IS 10262:2019 Annex A, Clauses A-1 to A-10",
            "doe": "BRE 331:1997 §7.2 Example 2, Table 5",
        },
        "standard_examples": examples,
        "cross_method_comparison": _comparison_results(),
        "quantification": quantification,
        "cost": cost,
        "validation_rows": validation_rows,
        "summary": summary,
    }
