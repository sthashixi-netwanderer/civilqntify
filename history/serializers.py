"""JSON serialization helpers for CivilQntify data models.

Converts between dataclass instances and JSON-serializable dicts for
SQLite storage and retrieval.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from enum import Enum
import warnings
from datetime import datetime, timezone
from typing import Any


INPUT_SCHEMA_VERSION = 2


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    return value


def _model_dict(model: Any) -> dict:
    """Follow dataclass fields so newly added behavior is not silently lost."""
    return _json_value(asdict(model))


def _model_kwargs(cls: Any, data: dict) -> dict:
    return {f.name: data[f.name] for f in fields(cls) if f.init and f.name in data}


def mix_input_defaulted_fields(data: dict) -> list[str]:
    """Identify missing saved inputs before restoring model defaults."""
    from concrete_mix.models.mix_input import MixDesignInput
    return [f.name for f in fields(MixDesignInput) if f.init and f.name not in data]


def serialize_mix_input(inp: Any) -> str:
    data = _model_dict(inp)
    data["schema_version"] = INPUT_SCHEMA_VERSION
    return json.dumps(data, allow_nan=False)


def deserialize_mix_input(data: dict) -> Any:
    from concrete_mix.models.mix_input import MixDesignInput
    from concrete_mix.models.materials import (
        Cement, FineAggregate, CoarseAggregate, SCM, Admixture,
        CementType, AggregateShape, SCMType, AdmixtureType,
    )

    def material(cls, saved):
        kwargs = _model_kwargs(cls, saved)
        enums = {Cement: ("type", CementType), FineAggregate: ("shape", AggregateShape),
                 CoarseAggregate: ("shape", AggregateShape), SCM: ("type", SCMType),
                 Admixture: ("type", AdmixtureType)}
        name, enum = enums[cls]
        if name in kwargs:
            try:
                kwargs[name] = enum(kwargs[name])
            except ValueError:
                pass  # Preserve supported free-text types, including DOE shapes.
        return cls(**kwargs)

    version = data.get("schema_version", 1)
    if type(version) is not int or version not in (1, INPUT_SCHEMA_VERSION):
        raise ValueError(f"Unsupported mix input schema version: {version}")
    missing = mix_input_defaulted_fields(data)
    if missing:
        warnings.warn("Saved mix inputs are incomplete; model defaults used for: "
                      + ", ".join(missing), UserWarning, stacklevel=2)
    kwargs = _model_kwargs(MixDesignInput, data)
    for name, cls in (("cement", Cement), ("fine_aggregate", FineAggregate),
                      ("coarse_aggregate", CoarseAggregate)):
        if name in data:
            kwargs[name] = material(cls, data[name])
    kwargs["scms"] = tuple(material(SCM, s) for s in data.get("scms", []))
    kwargs["admixture"] = (material(Admixture, data["admixture"])
                           if data.get("admixture") else None)
    return MixDesignInput(**kwargs)


def serialize_mix_result(result: Any) -> str:
    return json.dumps(_model_dict(result), allow_nan=False)


def deserialize_mix_result(data: dict) -> Any:
    from concrete_mix.models.mix_result import MixDesignResult, CalculationStep
    kwargs = _model_kwargs(MixDesignResult, data)
    kwargs["steps"] = tuple(CalculationStep(**_model_kwargs(CalculationStep, s))
                            for s in data.get("steps", []))
    kwargs["warnings"] = tuple(data.get("warnings", []))
    return MixDesignResult(**kwargs)


def serialize_bill(bill: Any) -> str:
    return json.dumps(_model_dict(bill), allow_nan=False)


def deserialize_bill(data: dict) -> Any:
    from material_quantify.models.bill import MaterialBill
    from material_quantify.models.transfer_data import MixDesignTransferData

    # Compatibility for historical bills whose transfer blob was partial.
    defaults = dict(code_used="Manual", cement_kg_per_m3=350, water_kg_per_m3=175,
                    fine_aggregate_kg_per_m3=700, coarse_aggregate_kg_per_m3=1200,
                    scm_kg_per_m3=0.0, admixture_kg_per_m3=0.0, air_volume_percent=2.0,
                    w_c_ratio=0.5, target_mean_strength_mpa=25.0,
                    field_water_kg_per_m3=0.0, field_fine_aggregate_kg_per_m3=0.0,
                    field_coarse_aggregate_kg_per_m3=0.0, cement_bag_weight_kg=50.0,
                    coarse_agg_bulk_density_kg_m3=1600.0, fine_agg_specific_gravity=2.65,
                    coarse_agg_specific_gravity=2.70)
    defaults.update(data.get("transfer_data", {}))
    kwargs = _model_kwargs(MaterialBill, data)
    kwargs.setdefault("total_scm_kg", 0.0)
    kwargs.setdefault("total_admixture_kg", 0.0)
    kwargs["transfer_data"] = MixDesignTransferData(**_model_kwargs(MixDesignTransferData, defaults))
    return MaterialBill(**kwargs)


def serialize_cost_data(data: dict) -> str:
    """Serialize cost estimation result dict to JSON string."""
    return json.dumps(data, default=str)


def serialize_transfer_data(td: Any) -> str:
    """Serialize MixDesignTransferData to JSON string."""
    return json.dumps(_transfer_data_dict(td), default=str)


def serialize_psd_input(inp: dict) -> str:
    """Serialize a PSD tab input dict to a JSON string.

    The dict is assembled by the PSD widget and carries the standard,
    aggregate type, reference band, per-sieve masses and (for ASTM C33)
    the quality-requirement inputs.
    """
    return json.dumps(inp, default=str)


def serialize_psd_result(result: Any) -> str:
    """Serialize a PSDResult to a JSON string."""
    from dataclasses import asdict

    return json.dumps(asdict(result), default=str)


def serialize_doe_trial_payload(payload: dict) -> str:
    """Serialize a DOE (BRE 331 clause 6) trial-mix input/result dict to JSON.

    Both payloads are plain JSON-serialisable dicts assembled by the
    DOE trial mixes dialog (measurements, batch schedule, clause 6.3
    evaluation); floats and None values pass through directly.
    """
    return json.dumps(payload, default=str)


def serialize_aci_trial_payload(payload: dict) -> str:
    """Serialize an ACI (PRC-211.1-22 clause 5.3.9–5.3.10) trial payload to JSON.

    Same plain-dict convention as the DOE trial payloads (measurements,
    Table 5.3.9.1 schedule, clause 5.3.10 adjustments).
    """
    return json.dumps(payload, default=str)


def deserialize_psd_result(data: dict) -> Any:
    """Deserialize a dict back to PSDResult."""
    from concrete_mix.engine.psd import PSDResult

    fields = {f: data.get(f) for f in (
        "sieve_sizes", "mass_retained", "pan_mass", "total_mass",
        "percent_retained", "cumulative_percent_retained", "percent_passing",
        "fineness_modulus", "d10", "d30", "d60",
        "uniformity_coefficient", "coefficient_of_curvature", "conforms",
    )}
    return PSDResult(**fields)


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _transfer_data_dict(td) -> dict:
    return _model_dict(td)


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
