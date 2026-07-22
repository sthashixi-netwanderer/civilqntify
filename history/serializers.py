"""JSON serialization helpers for CivilQntify data models.

Converts between dataclass instances and JSON-serializable dicts for
SQLite storage and retrieval.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def serialize_mix_input(inp: Any) -> str:
    """Serialize a MixDesignInput to JSON string."""
    d = {
        "code": inp.code,
        "target_strength_mpa": inp.target_strength_mpa,
        "characteristic_strength_mpa": inp.characteristic_strength_mpa,
        "slump_mm": inp.slump_mm,
        "cement": _cement_dict(inp.cement),
        "fine_aggregate": _fine_agg_dict(inp.fine_aggregate),
        "coarse_aggregate": _coarse_agg_dict(inp.coarse_aggregate),
        "scms": [_scm_dict(s) for s in inp.scms],
        "admixture": _admixture_dict(inp.admixture) if inp.admixture else None,
        "exposure_class": inp.exposure_class,
        "concrete_type": inp.concrete_type,
        "air_entrained": inp.air_entrained,
        "w_c_ratio": inp.w_c_ratio,
        "volume_m3": inp.volume_m3,
        "has_production_data": inp.has_production_data,
        "sulfate_exposure_class": inp.sulfate_exposure_class,
        "defective_percent": getattr(inp, "defective_percent", 5.0),
        "age_days": getattr(inp, "age_days", 28),
    }
    return json.dumps(d, default=str)


def deserialize_mix_input(data: dict) -> Any:
    """Deserialize a dict back to MixDesignInput."""
    from concrete_mix.models.mix_input import MixDesignInput
    from concrete_mix.models.materials import (
        Cement, FineAggregate, CoarseAggregate, SCM, Admixture,
    )

    cement = Cement(
        type=data["cement"]["type"],
        specific_gravity=data["cement"]["specific_gravity"],
    )
    fa = data["fine_aggregate"]
    fine_agg = FineAggregate(
        specific_gravity=fa["specific_gravity"],
        fineness_modulus=fa.get("fineness_modulus", 2.7),
        absorption_percent=fa.get("absorption_percent", 1.0),
        moisture_content_percent=fa.get("moisture_content_percent", 0.0),
        grading_zone=fa.get("grading_zone"),
        pct_passing_600um=fa.get("pct_passing_600um"),
    )
    ca = data["coarse_aggregate"]
    coarse_agg = CoarseAggregate(
        specific_gravity=ca["specific_gravity"],
        nominal_max_size_mm=ca["nominal_max_size_mm"],
        absorption_percent=ca.get("absorption_percent", 1.0),
        moisture_content_percent=ca.get("moisture_content_percent", 0.0),
        shape=ca["shape"],
        bulk_density_kg_m3=ca.get("bulk_density_kg_m3", 1600),
    )
    scms = []
    for s in data.get("scms", []):
        scms.append(SCM(type=s["type"], specific_gravity=s["specific_gravity"],
                         replacement_percent=s["replacement_percent"]))
    adm = None
    if data.get("admixture"):
        a = data["admixture"]
        adm = Admixture(type=a["type"], dosage_percent=a["dosage_percent"],
                         water_reduction_percent=a.get("water_reduction_percent", 0.0),
                         specific_gravity=a.get("specific_gravity", 1.1))

    return MixDesignInput(
        code=data["code"],
        target_strength_mpa=data["target_strength_mpa"],
        characteristic_strength_mpa=data.get("characteristic_strength_mpa"),
        slump_mm=data["slump_mm"],
        cement=cement,
        fine_aggregate=fine_agg,
        coarse_aggregate=coarse_agg,
        scms=tuple(scms),
        admixture=adm,
        exposure_class=data.get("exposure_class"),
        concrete_type=data.get("concrete_type", "reinforced"),
        air_entrained=data.get("air_entrained", False),
        w_c_ratio=data.get("w_c_ratio"),
        volume_m3=data.get("volume_m3", 1.0),
        has_production_data=data.get("has_production_data", True),
        sulfate_exposure_class=data.get("sulfate_exposure_class", "S0"),
        defective_percent=data.get("defective_percent", 5.0),
        age_days=data.get("age_days", 28),
    )


def serialize_mix_result(result: Any) -> str:
    """Serialize a MixDesignResult to JSON string."""
    steps = []
    for s in result.steps:
        steps.append({
            "step_number": s.step_number,
            "description": s.description,
            "formula": s.formula,
            "inputs": _safe_inputs(s.inputs),
            "result": s.result,
            "unit": s.unit,
            "clause_ref": s.clause_ref,
        })
    d = {
        "code_used": result.code_used,
        "target_mean_strength_mpa": result.target_mean_strength_mpa,
        "w_c_ratio": result.w_c_ratio,
        "water_kg": result.water_kg,
        "cement_kg": result.cement_kg,
        "scm_kg": result.scm_kg,
        "fine_aggregate_kg": result.fine_aggregate_kg,
        "coarse_aggregate_kg": result.coarse_aggregate_kg,
        "air_volume_percent": result.air_volume_percent,
        "volume_m3": result.volume_m3,
        "steps": steps,
        "warnings": list(result.warnings),
        "cost_per_m3": result.cost_per_m3,
        "carbon_kg_co2_per_m3": result.carbon_kg_co2_per_m3,
        "adjusted_water_kg": result.adjusted_water_kg,
        "field_fine_aggregate_kg": result.field_fine_aggregate_kg,
        "field_coarse_aggregate_kg": result.field_coarse_aggregate_kg,
        "admixture_kg": result.admixture_kg,
        "admixture_type": result.admixture_type,
        "admixture_dosage_percent": result.admixture_dosage_percent,
        "water_reduction_percent": result.water_reduction_percent,
    }
    return json.dumps(d, default=str)


def deserialize_mix_result(data: dict) -> Any:
    """Deserialize a dict back to MixDesignResult."""
    from concrete_mix.models.mix_result import MixDesignResult, CalculationStep

    steps = []
    for s in data.get("steps", []):
        steps.append(CalculationStep(
            step_number=s["step_number"],
            description=s["description"],
            formula=s["formula"],
            inputs=s.get("inputs", {}),
            result=s["result"],
            unit=s["unit"],
            clause_ref=s.get("clause_ref", ""),
        ))
    return MixDesignResult(
        code_used=data["code_used"],
        target_mean_strength_mpa=data["target_mean_strength_mpa"],
        w_c_ratio=data["w_c_ratio"],
        water_kg=data["water_kg"],
        cement_kg=data["cement_kg"],
        scm_kg=data.get("scm_kg", 0.0),
        fine_aggregate_kg=data.get("fine_aggregate_kg", 0.0),
        coarse_aggregate_kg=data.get("coarse_aggregate_kg", 0.0),
        air_volume_percent=data.get("air_volume_percent", 0.0),
        volume_m3=data.get("volume_m3", 1.0),
        steps=tuple(steps),
        warnings=tuple(data.get("warnings", [])),
        cost_per_m3=data.get("cost_per_m3"),
        carbon_kg_co2_per_m3=data.get("carbon_kg_co2_per_m3"),
        adjusted_water_kg=data.get("adjusted_water_kg"),
        field_fine_aggregate_kg=data.get("field_fine_aggregate_kg"),
        field_coarse_aggregate_kg=data.get("field_coarse_aggregate_kg"),
        admixture_kg=data.get("admixture_kg"),
        admixture_type=data.get("admixture_type"),
        admixture_dosage_percent=data.get("admixture_dosage_percent"),
        water_reduction_percent=data.get("water_reduction_percent"),
    )


def serialize_bill(bill: Any) -> str:
    """Serialize a MaterialBill to JSON string."""
    d = {
        "net_concrete_volume_m3": bill.net_concrete_volume_m3,
        "wastage_percent": bill.wastage_percent,
        "gross_concrete_volume_m3": bill.gross_concrete_volume_m3,
        "total_cement_kg": bill.total_cement_kg,
        "total_cement_bags": bill.total_cement_bags,
        "cement_bag_weight_kg": bill.cement_bag_weight_kg,
        "total_water_kg": bill.total_water_kg,
        "total_water_liters": bill.total_water_liters,
        "total_fine_aggregate_kg": bill.total_fine_aggregate_kg,
        "total_fine_aggregate_bulk_m3": bill.total_fine_aggregate_bulk_m3,
        "total_coarse_aggregate_kg": bill.total_coarse_aggregate_kg,
        "total_coarse_aggregate_bulk_m3": bill.total_coarse_aggregate_bulk_m3,
        "total_scm_kg": bill.total_scm_kg,
        "total_admixture_kg": bill.total_admixture_kg,
        "transfer_data": _transfer_data_dict(bill.transfer_data),
    }
    return json.dumps(d, default=str)


def deserialize_bill(data: dict) -> Any:
    """Deserialize a dict back to MaterialBill."""
    from material_quantify.models.bill import MaterialBill
    from material_quantify.models.transfer_data import MixDesignTransferData

    td_data = data.get("transfer_data", {})
    td = MixDesignTransferData(
        code_used=td_data.get("code_used", "Manual"),
        cement_kg_per_m3=td_data.get("cement_kg_per_m3", 350),
        water_kg_per_m3=td_data.get("water_kg_per_m3", 175),
        fine_aggregate_kg_per_m3=td_data.get("fine_aggregate_kg_per_m3", 700),
        coarse_aggregate_kg_per_m3=td_data.get("coarse_aggregate_kg_per_m3", 1200),
        scm_kg_per_m3=td_data.get("scm_kg_per_m3", 0.0),
        admixture_kg_per_m3=td_data.get("admixture_kg_per_m3", 0.0),
        air_volume_percent=td_data.get("air_volume_percent", 2.0),
        w_c_ratio=td_data.get("w_c_ratio", 0.5),
        target_mean_strength_mpa=td_data.get("target_mean_strength_mpa", 25.0),
        field_water_kg_per_m3=td_data.get("field_water_kg_per_m3", 0.0),
        field_fine_aggregate_kg_per_m3=td_data.get("field_fine_aggregate_kg_per_m3", 0.0),
        field_coarse_aggregate_kg_per_m3=td_data.get("field_coarse_aggregate_kg_per_m3", 0.0),
        cement_bag_weight_kg=td_data.get("cement_bag_weight_kg", 50.0),
        coarse_agg_bulk_density_kg_m3=td_data.get("coarse_agg_bulk_density_kg_m3", 1600.0),
        fine_agg_specific_gravity=td_data.get("fine_agg_specific_gravity", 2.65),
        coarse_agg_specific_gravity=td_data.get("coarse_agg_specific_gravity", 2.70),
    )
    return MaterialBill(
        net_concrete_volume_m3=data["net_concrete_volume_m3"],
        wastage_percent=data["wastage_percent"],
        gross_concrete_volume_m3=data["gross_concrete_volume_m3"],
        total_cement_kg=data["total_cement_kg"],
        total_cement_bags=data["total_cement_bags"],
        cement_bag_weight_kg=data["cement_bag_weight_kg"],
        total_water_kg=data["total_water_kg"],
        total_water_liters=data["total_water_liters"],
        total_fine_aggregate_kg=data["total_fine_aggregate_kg"],
        total_fine_aggregate_bulk_m3=data["total_fine_aggregate_bulk_m3"],
        total_coarse_aggregate_kg=data["total_coarse_aggregate_kg"],
        total_coarse_aggregate_bulk_m3=data["total_coarse_aggregate_bulk_m3"],
        total_scm_kg=data.get("total_scm_kg", 0.0),
        total_admixture_kg=data.get("total_admixture_kg", 0.0),
        transfer_data=td,
    )


def serialize_cost_data(data: dict) -> str:
    """Serialize cost estimation result dict to JSON string."""
    return json.dumps(data, default=str)


def serialize_transfer_data(td: Any) -> str:
    """Serialize MixDesignTransferData to JSON string."""
    return json.dumps(_transfer_data_dict(td), default=str)


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _cement_dict(c) -> dict:
    return {"type": c.type.value if hasattr(c.type, "value") else str(c.type),
            "specific_gravity": c.specific_gravity}

def _fine_agg_dict(fa) -> dict:
    d = {
        "specific_gravity": fa.specific_gravity,
        "fineness_modulus": fa.fineness_modulus,
        "absorption_percent": fa.absorption_percent,
        "moisture_content_percent": fa.moisture_content_percent,
        "grading_zone": fa.grading_zone,
    }
    if hasattr(fa, "pct_passing_600um"):
        d["pct_passing_600um"] = fa.pct_passing_600um
    return d

def _coarse_agg_dict(ca) -> dict:
    return {
        "specific_gravity": ca.specific_gravity,
        "nominal_max_size_mm": ca.nominal_max_size_mm,
        "absorption_percent": ca.absorption_percent,
        "moisture_content_percent": ca.moisture_content_percent,
        "shape": ca.shape.value if hasattr(ca.shape, "value") else str(ca.shape),
        "bulk_density_kg_m3": ca.bulk_density_kg_m3,
    }

def _scm_dict(s) -> dict:
    return {"type": s.type.value if hasattr(s.type, "value") else str(s.type),
            "specific_gravity": s.specific_gravity,
            "replacement_percent": s.replacement_percent}

def _admixture_dict(a) -> dict:
    return {"type": a.type.value if hasattr(a.type, "value") else str(a.type),
            "dosage_percent": a.dosage_percent,
            "water_reduction_percent": a.water_reduction_percent,
            "specific_gravity": a.specific_gravity}

def _transfer_data_dict(td) -> dict:
    return {
        "code_used": td.code_used,
        "cement_kg_per_m3": td.cement_kg_per_m3,
        "water_kg_per_m3": td.water_kg_per_m3,
        "fine_aggregate_kg_per_m3": td.fine_aggregate_kg_per_m3,
        "coarse_aggregate_kg_per_m3": td.coarse_aggregate_kg_per_m3,
        "scm_kg_per_m3": td.scm_kg_per_m3,
        "admixture_kg_per_m3": td.admixture_kg_per_m3,
        "air_volume_percent": td.air_volume_percent,
        "w_c_ratio": td.w_c_ratio,
        "target_mean_strength_mpa": td.target_mean_strength_mpa,
        "field_water_kg_per_m3": td.field_water_kg_per_m3,
        "field_fine_aggregate_kg_per_m3": td.field_fine_aggregate_kg_per_m3,
        "field_coarse_aggregate_kg_per_m3": td.field_coarse_aggregate_kg_per_m3,
        "cement_bag_weight_kg": td.cement_bag_weight_kg,
        "coarse_agg_bulk_density_kg_m3": td.coarse_agg_bulk_density_kg_m3,
        "fine_agg_specific_gravity": td.fine_agg_specific_gravity,
        "coarse_agg_specific_gravity": td.coarse_agg_specific_gravity,
    }

def _safe_inputs(inputs: dict) -> dict:
    """Make inputs JSON-safe by converting non-serializable values."""
    safe = {}
    for k, v in inputs.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            safe[k] = v
        elif isinstance(v, (list, tuple)):
            safe[k] = [_safe_val(x) for x in v]
        elif isinstance(v, dict):
            safe[k] = {str(kk): _safe_val(vv) for kk, vv in v.items()}
        else:
            safe[k] = str(v)
    return safe

def _safe_val(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool, type(None))):
        return v
    return str(v)
