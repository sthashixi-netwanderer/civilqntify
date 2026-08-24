"""Human-readable display names for internal enumeration keys.

Internal keys (enum values, dict keys) use snake_case for code clarity,
but must never be shown raw to users in the GUI, warnings, or reports.
This module provides a single mapping used across UI, validation, and
export layers.

Nomenclature sources:
- Cement grades: IS 269 / IS 8112 / IS 12269 ("OPC 33/43/53"),
  ASTM C150 ("Type I..V")
- Aggregate shapes: IS 10262:2019 Table 4 / BRE 331:1997 Table 3
- Exposure classes: IS 456:2000 Table 3
- SCM types: IS 3812 (fly ash), IS 16714 (GGBFS), IS 15388 (silica fume)
- Admixture types: IS 10262:2019 Annex G, ASTM C494
"""

from __future__ import annotations

_DISPLAY_NAMES: dict[str, str] = {
    # ── Cement types ──
    # IS grades (IS 269:2015 nomenclature)
    "OPC_33": "OPC 33",
    "OPC_43": "OPC 43",
    "OPC_53": "OPC 53",
    "PPC": "PPC",
    "PSC": "PSC",
    # ASTM C150 types
    "TYPE_I": "Type I",
    "TYPE_II": "Type II",
    "TYPE_III": "Type III",
    "TYPE_IV": "Type IV",
    "TYPE_V": "Type V",
    # Ghana (GSA) grades
    "GRADE_32_5R": "32.5R",
    "GRADE_42_5R": "42.5R",
    "GRADE_42_5N": "42.5N",
    "GRADE_52_5N": "52.5N",
    # ── Aggregate shapes (IS 10262:2019 Table 4) ──
    "rounded_gravel": "Rounded gravel",
    "gravel": "Gravel",
    "sub_angular": "Sub-angular",
    "angular": "Angular",
    "crushed_fragments": "Crushed fragments",
    # ── Exposure classes (IS 456:2000 Table 3) ──
    "mild": "Mild",
    "moderate": "Moderate",
    "severe": "Severe",
    "very_severe": "Very Severe",
    "extreme": "Extreme",
    # ── SCM types ──
    "fly_ash": "Fly Ash",
    "ggbfs": "GGBFS",
    "silica_fume": "Silica Fume",
    "metakaolin": "Metakaolin",
    # ── Admixture types (IS 10262:2019 Annex G) ──
    "plasticizer": "Plasticizer",
    "smfc": "SMFC Superplasticizer",
    "snfc": "SNFC Superplasticizer",
    "pce": "PCE Superplasticizer",
    "superplasticizer": "Superplasticizer",
    "hrwra": "HRWR Admixture",
}


def display_name(key: str | None) -> str:
    """Return a human-readable name for an internal enumeration key.

    Falls back to replacing underscores with spaces for unmapped keys,
    so unknown values degrade gracefully instead of leaking snake_case.
    """
    if not key:
        return ""
    return _DISPLAY_NAMES.get(key, key.replace("_", " "))
