"""Immutable material models for concrete mix design."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# Ghana Standards Authority (GSA) cement designations per GS 1022
# Maps IS/ASTM cement types to Ghana jurisdiction equivalents
GHANA_CEMENT_EQUIVALENTS: dict[str, dict[str, str]] = {
    "OPC_33": {"ghana_grade": "Grade 32.5N", "gs_spec": "GS 1022", "use": "General purpose, plastering, masonry"},
    "OPC_43": {"ghana_grade": "Grade 42.5N", "gs_spec": "GS 1022", "use": "Structural concrete, reinforced work"},
    "OPC_53": {"ghana_grade": "Grade 52.5N", "gs_spec": "GS 1022", "use": "High-strength, pre-stressed concrete"},
    "PPC": {"ghana_grade": "Portland Pozzolana Cement", "gs_spec": "GS 1022 Part 2", "use": "Marine works, mass concreting, durability"},
    "PSC": {"ghana_grade": "Portland Slag Cement", "gs_spec": "GS 1022 Part 3", "use": "Sulfate resistance, marine, sewage"},
    "TYPE_I": {"ghana_grade": "Grade 42.5N (Ordinary)", "gs_spec": "GS 1022 / ASTM C150 Type I", "use": "General construction"},
    "TYPE_II": {"ghana_grade": "Grade 42.5N (Moderate Sulfate)", "gs_spec": "GS 1022 / ASTM C150 Type II", "use": "Moderate sulfate exposure"},
    "TYPE_III": {"ghana_grade": "Grade 52.5R (High Early)", "gs_spec": "GS 1022 / ASTM C150 Type III", "use": "Rapid strength gain, cold weather"},
    "TYPE_IV": {"ghana_grade": "Grade 32.5N (Low Heat)", "gs_spec": "GS 1022 / ASTM C150 Type IV", "use": "Mass concrete, dams"},
    "TYPE_V": {"ghana_grade": "Grade 42.5N (High Sulfate)", "gs_spec": "GS 1022 / ASTM C150 Type V", "use": "Severe sulfate exposure"},
}

# IS 383 grading zone descriptions in plain language
GRADING_ZONE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "I": {
        "name": "Zone I — Coarse Sand",
        "description": "Coarsest sand grading. Particles are mostly larger."
            " Contains fewer fines (small particles)."
            " Good for concrete where lower water demand is desired."
            " Concrete is slightly harsher but more workable with less water.",
        "typical_use": "Structural concrete, lean mixes",
    },
    "II": {
        "name": "Zone II — Medium Sand (Recommended)",
        "description": "Medium grading, the most commonly used zone."
            " Well-balanced particle distribution."
            " Standard reference zone for IS 10262 mix design."
            " Suitable for most general-purpose concrete work.",
        "typical_use": "General purpose concrete (recommended for most work)",
    },
    "III": {
        "name": "Zone III — Fine Sand",
        "description": "Finer sand with more small particles."
            " Requires more water to achieve workability."
            " May produce harsher mix unless more cement is added."
            " Use with caution — check water demand.",
        "typical_use": "Plastering, mortar, finishing work",
    },
    "IV": {
        "name": "Zone IV — Very Fine Sand",
        "description": "Finest grading. Contains very high proportion of fines."
            " Significantly increases water demand."
            " Not typically suitable for structural concrete."
            " If used, expect higher cement content to compensate.",
        "typical_use": "Mortar, non-structural applications only",
    },
}


class CementType(str, Enum):
    """Cement types per IS/ACI standards with Ghana (GSA) equivalents."""
    # Ghana cement grades with IS/ACI equivalents
    GRADE_32_5R = "Grade 32.5R"    # General Purpose (OPC_33 / TYPE_I)
    GRADE_42_5R = "Grade 42.5R"    # High Early Strength (OPC_43 / TYPE_III)
    GRADE_42_5N = "Grade 42.5N"    # Normal Hardening (OPC_43 / TYPE_I)
    GRADE_52_5N = "Grade 52.5N"    # Extra High Strength (OPC_53)
    # IS cement grades
    OPC_33 = "OPC_33"
    OPC_43 = "OPC_43"
    OPC_53 = "OPC_53"
    PPC = "PPC"       # Portland Pozzolana Cement
    PSC = "PSC"       # Portland Slag Cement
    # ACI cement types
    TYPE_I = "TYPE_I"     # Normal
    TYPE_II = "TYPE_II"   # Moderate sulfate resistance
    TYPE_III = "TYPE_III" # High early strength
    TYPE_IV = "TYPE_IV"   # Low heat of hydration
    TYPE_V = "TYPE_V"     # High sulfate resistance


class AggregateShape(str, Enum):
    """Aggregate particle shape per IS 10262:2019 Table 6.

    Affects water demand: angular crushed rock needs more water
    than rounded natural gravel for the same workability.
    """
    ROUNDED_GRAVEL = "rounded_gravel"       # Natural rounded — lowest water demand
    GRAVEL = "gravel"                        # Natural gravel — base condition
    SUB_ANGULAR = "sub_angular"             # Partly crushed — moderate increase
    ANGULAR = "angular"                      # Crushed angular — higher water demand
    CRUSHED_FRAGMENTS = "crushed_fragments"  # Fully crushed — highest water demand


class SCMType(str, Enum):
    """Supplementary Cementitious Material types."""
    FLY_ASH = "fly_ash"
    GGBFS = "ggbfs"
    SILICA_FUME = "silica_fume"
    METAKAOLIN = "metakaolin"


@dataclass(frozen=True)
class Cement:
    """Cement material properties."""
    type: CementType = CementType.OPC_43
    specific_gravity: float = 3.15

    def __post_init__(self) -> None:
        if not 2.8 <= self.specific_gravity <= 3.5:
            raise ValueError(
                f"Cement specific gravity {self.specific_gravity} outside valid range [2.8, 3.5]"
            )


@dataclass(frozen=True)
class FineAggregate:
    """Fine aggregate (sand) properties.

    fineness_modulus: Used by ACI 211.1 (typically 2.3-3.1)
    grading_zone: Used by IS 10262 (Zone I-IV)
    shape: Used by DOE method to determine crushed/uncrushed type
    """
    specific_gravity: float = 2.65
    absorption_percent: float = 1.0
    moisture_content_percent: float = 0.0
    fineness_modulus: float = 2.70  # ACI method
    grading_zone: Optional[str] = None  # IS method: "I", "II", "III", "IV"
    pct_passing_600um: Optional[float] = None  # DOE method: % passing 600 µm
    shape: AggregateShape = AggregateShape.GRAVEL  # DOE method: crushed/uncrushed

    def __post_init__(self) -> None:
        if not 2.2 <= self.specific_gravity <= 3.0:
            raise ValueError(
                f"Fine aggregate specific gravity {self.specific_gravity} outside valid range [2.2, 3.0]"
            )
        if self.fineness_modulus is not None and not 1.0 <= self.fineness_modulus <= 4.0:
            raise ValueError(
                f"Fineness modulus {self.fineness_modulus} outside valid range [1.0, 4.0]"
            )
        if self.grading_zone is not None and self.grading_zone not in ("I", "II", "III", "IV"):
            raise ValueError(
                f"Grading zone '{self.grading_zone}' not valid. Must be I, II, III, or IV"
            )
        if self.pct_passing_600um is not None and not 0 <= self.pct_passing_600um <= 100:
            raise ValueError(
                f"pct_passing_600um {self.pct_passing_600um} outside valid range [0, 100]"
            )


@dataclass(frozen=True)
class CoarseAggregate:
    """Coarse aggregate properties."""
    specific_gravity: float = 2.70
    nominal_max_size_mm: int = 20
    absorption_percent: float = 0.5
    moisture_content_percent: float = 0.0
    bulk_density_kg_m3: float = 1600.0
    shape: AggregateShape = AggregateShape.GRAVEL

    def __post_init__(self) -> None:
        if not 2.2 <= self.specific_gravity <= 3.2:
            raise ValueError(
                f"Coarse aggregate specific gravity {self.specific_gravity} outside valid range [2.2, 3.2]"
            )
        if self.nominal_max_size_mm not in (10, 19, 20, 40):
            raise ValueError(
                f"Nominal max size {self.nominal_max_size_mm}mm not supported. Use 10, 19, 20, or 40"
            )


@dataclass(frozen=True)
class SCM:
    """Supplementary Cementitious Material."""
    type: SCMType = SCMType.FLY_ASH
    specific_gravity: float = 2.20
    replacement_percent: float = 20.0  # % of cement replaced

    def __post_init__(self) -> None:
        if not 5.0 <= self.replacement_percent <= 70.0:
            raise ValueError(
                f"SCM replacement {self.replacement_percent}% outside valid range [5, 70]"
            )


class AdmixtureType(str, Enum):
    """Chemical admixture types per IS 10262:2019 Annex G.

    Water reduction ranges per Annex G:
    - PLASTICIZER: 0.3-0.5% dosage → 8-12% water reduction
    - SMFC/SNFC: 0.5-1.5% dosage → 15-30% water reduction
    - PCE: lower dosages → 30%+ water reduction
    """
    PLASTICIZER = "plasticizer"               # Lignosulphonates - 8-12% water reduction
    SMFC = "smfc"                             # Sulfonated melamine-formaldehyde condensate
    SNFC = "snfc"                             # Sulfonated naphthalene-formaldehyde condensate
    PCE = "pce"                               # Polyether-polycarboxylates - highest water reduction
    SUPERPLASTICIZER = "superplasticizer"     # Generic superplasticizer (15-30% water reduction)
    HRWRA = "hrwra"                           # High Range Water Reducing Admixture


# IS 10262:2019 Annex G — Typical admixture properties
ADMIXTURE_PROPERTIES: dict[str, dict[str, float]] = {
    "plasticizer": {"min_dosage": 0.3, "max_dosage": 0.5, "min_reduction": 8.0, "max_reduction": 12.0},
    "smfc": {"min_dosage": 0.5, "max_dosage": 1.5, "min_reduction": 15.0, "max_reduction": 30.0},
    "snfc": {"min_dosage": 0.5, "max_dosage": 1.5, "min_reduction": 15.0, "max_reduction": 30.0},
    "pce": {"min_dosage": 0.3, "max_dosage": 1.0, "min_reduction": 25.0, "max_reduction": 35.0},
    "superplasticizer": {"min_dosage": 0.5, "max_dosage": 1.5, "min_reduction": 15.0, "max_reduction": 30.0},
    "hrwra": {"min_dosage": 0.5, "max_dosage": 1.5, "min_reduction": 20.0, "max_reduction": 35.0},
}


@dataclass(frozen=True)
class Admixture:
    """Chemical admixture per IS 10262:2019 Annex G.

    Attributes:
        type: Admixture type (plasticizer, smfc, snfc, pce, superplasticizer, hrwra)
        dosage_percent: % by weight of cementitious material
        water_reduction_percent: % water reduction achieved
        specific_gravity: Specific gravity of admixture (typically 1.05-1.20)

    IS 10262:2019 Annex G reference:
        - Plasticizers: 0.3-0.5% dosage, 8-12% water reduction
        - Superplasticizers (SMFC/SNFC): 0.5-1.5% dosage, 15-30% water reduction
        - PCE type: lower dosages, 30%+ water reduction
    """
    type: AdmixtureType | str = AdmixtureType.SUPERPLASTICIZER
    dosage_percent: float = 1.0  # % by weight of cementitious material
    water_reduction_percent: float = 0.0  # % water reduction achieved
    specific_gravity: float = 1.145  # Typical range: 1.05-1.20

    def __post_init__(self) -> None:
        if not 0.0 <= self.water_reduction_percent <= 40.0:
            raise ValueError(
                f"Water reduction {self.water_reduction_percent}% outside valid range [0, 40]"
            )
        if not 0.1 <= self.specific_gravity <= 2.0:
            raise ValueError(
                f"Admixture specific gravity {self.specific_gravity} outside valid range [0.1, 2.0]"
            )
        # Validate dosage against IS 10262:2019 Annex G typical ranges
        type_str = self.type_string
        if type_str in ADMIXTURE_PROPERTIES:
            props = ADMIXTURE_PROPERTIES[type_str]
            if not props["min_dosage"] <= self.dosage_percent <= props["max_dosage"]:
                import warnings as warn
                warn.warn(
                    f"Admixture dosage {self.dosage_percent}% is outside typical range "
                    f"[{props['min_dosage']}-{props['max_dosage']}%] for {type_str} per IS 10262:2019 Annex G",
                    stacklevel=2,
                )

    @property
    def type_string(self) -> str:
        """Return admixture type as string."""
        if isinstance(self.type, AdmixtureType):
            return self.type.value
        return str(self.type)

    def get_typical_properties(self) -> dict[str, float] | None:
        """Get typical dosage and water reduction ranges from IS 10262:2019 Annex G."""
        return ADMIXTURE_PROPERTIES.get(self.type_string)
