"""Concrete Mix Design Module — ACI 211.1 and IS 10262:2019.

A pure-Python library for calculating concrete mix proportions per
international structural codes.

Usage:
    from concrete_mix import design_mix, MixDesignInput

    result = design_mix(
        code="is10262",
        target_strength_mpa=25.0,
        slump_mm=50.0,
    )
    print(result.cement_kg, result.water_kg)
"""

from concrete_mix.engine.psd_link import PSDLinkage, derive_mix_design_params
from concrete_mix.engine.proportioner import design_mix, get_code_implementation
from concrete_mix.engine.target_strength import (
    TargetStrengthResult,
    calculate_target_strength,
)
from concrete_mix.estimators.carbon import carbon_savings_vs_opc, estimate_carbon
from concrete_mix.estimators.cost import MaterialPrices, estimate_cost
from concrete_mix.export.csv_export import export_to_csv
from concrete_mix.export.json_export import export_to_json
from concrete_mix.export.pdf_report import generate_pdf_report
from concrete_mix.export.text_report import generate_report
from concrete_mix.models.materials import (
    SCM,
    Admixture,
    Cement,
    CementType,
    CoarseAggregate,
    FineAggregate,
    SCMType,
)
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import CalculationStep, MixDesignResult
from concrete_mix.codes.is10262 import calculate_is10262_trial_mixes

from concrete_mix.validation.validators import validate_mix_input

# Mapping from Ghana cement grades to calculation codes
GHANA_CEMENT_MAP = {
    "GRADE_32_5R": {"is10262": "OPC_33", "aci211": "TYPE_I"},
    "GRADE_42_5R": {"is10262": "OPC_43", "aci211": "TYPE_III"},
    "GRADE_42_5N": {"is10262": "OPC_43", "aci211": "TYPE_I"},
    "GRADE_52_5N": {"is10262": "OPC_53", "aci211": "TYPE_I"},
}


def map_cement_type(ghana_code: str, standard: str) -> str:
    """Map Ghana cement grade to the calculation code for the given standard.

    Args:
        ghana_code: Ghana cement grade code (e.g., "GRADE_42_5R")
        standard: Design standard ("is10262" or "aci211")

    Returns:
        The calculation code for the specified standard
    """
    if ghana_code in GHANA_CEMENT_MAP:
        return GHANA_CEMENT_MAP[ghana_code].get(standard, ghana_code)
    return ghana_code


def design_mix_simple(
    code: str,
    target_strength_mpa: float,
    slump_mm: float,
    nmsa: int | float = 20,
    characteristic_strength_mpa: float | None = None,
    ca_volume_fraction_override: float | None = None,
    cement_type: str = "OPC_43",
    cement_sg: float = 3.15,
    fine_agg_sg: float = 2.65,
    fine_agg_fm: float = 2.70,
    fine_agg_grading_zone: str | None = None,
    fine_agg_absorption: float = 1.0,
    fine_agg_moisture: float = 0.0,
    coarse_agg_sg: float = 2.70,
    coarse_agg_absorption: float = 0.5,
    coarse_agg_moisture: float = 0.0,
    coarse_agg_bulk_density: float = 1600.0,
    aggregate_shape: str = "gravel",
    coarse_agg_type: str | None = None,
    fine_agg_shape: str | None = None,
    fine_agg_type: str | None = None,
    air_entrained: bool = False,
    exposure_class: str | None = None,
    concrete_type: str = "reinforced",
    scm_replacement_percent: float = 0.0,
    scm_type: str = "fly_ash",
    scm_sg: float = 2.20,
    admixture_type: str = "",
    admixture_dosage: float = 1.0,
    admixture_water_reduction: float = 0.0,
    admixture_sg: float = 1.15,
    volume_m3: float = 1.0,
    has_production_data: bool = True,
    sulfate_exposure_class: str = "S0",
    freezing_exposure_class: str = "F0",
    water_exposure_class: str = "W0",
    corrosion_exposure_class: str = "C0",
    form_width_mm: float | None = None,
    slab_depth_mm: float | None = None,
    bar_spacing_mm: float | None = None,
    concrete_temp_c: float = 22.5,
    manufactured_sand: bool = False,
    prestressed: bool = False,
    trial_density_kg_m3: float | None = None,
    trial_slump_mm: float | None = None,
    trial_air_pct: float | None = None,
    trial_strength_mpa: float | None = None,
    num_strength_tests: int | None = None,
    target_paste_volume_pct: float | None = None,
    air_pct: float = 0.0,
    vebe_s: float | None = None,
    ca_split: str | None = None,
    placing_method: str = "chute",
    pump_ca_reduction_percent: float | None = None,
    site_control: str = "good",
    admixture_water_kg: float = 0.0,
    mass_concrete: bool = False,
    scc_class: str | None = None,
    scc_slump_flow_mm: float | None = None,
    scc_lbox_ratio: float | None = None,
    scc_segregation_pct: float | None = None,
    scc_vfunnel_s: float | None = None,
    w_c_ratio: float | None = None,
    defective_percent: float = 5.0,
    age_days: int = 28,
    min_cement_kg: float | None = None,
    max_cement_kg: float | None = None,
    fine_agg_pct_passing_600um: float | None = None,
    std_deviation: float | None = None,
    margin_mpa: float | None = None,
    num_test_cubes: int | None = None,
    n_cubes: int | None = None,  # alias for num_test_cubes
) -> MixDesignResult:
    """Simplified API for quick mix design calculations.

    Args:
        code: "aci211", "is10262", or "doe"
        target_strength_mpa: Required compressive strength (MPa)
        slump_mm: Required slump (mm)
        nmsa: Nominal max aggregate size (mm), default 20
        cement_type: Cement type string ("OPC_43", "OPC_53", "TYPE_I", etc.)
        cement_sg: Cement specific gravity, default 3.15
        fine_agg_sg: Fine aggregate specific gravity, default 2.65
        fine_agg_fm: Fineness Modulus (ACI method), default 2.70
        fine_agg_grading_zone: Grading zone (IS method), e.g. "II"
        fine_agg_absorption: Fine aggregate absorption (%), default 1.0
        fine_agg_moisture: Fine aggregate free moisture (%), default 0.0
        coarse_agg_sg: Coarse aggregate specific gravity, default 2.70
        coarse_agg_absorption: Coarse aggregate absorption (%), default 0.5
        coarse_agg_moisture: Coarse aggregate free moisture (%), default 0.0
        coarse_agg_bulk_density: Dry rodded bulk density (kg/m³), default 1600
        aggregate_shape: Coarse aggregate shape (IS/DOE), default "gravel"
        fine_agg_shape: Fine aggregate shape (DOE only). If None, uses aggregate_shape.
            DOE uses weighted formula W = 2/3 Wf + 1/3 Wc when types differ.
        air_entrained: Air-entrained concrete (ACI only)
        exposure_class: IS 456 exposure class
        scm_replacement_percent: SCM replacement % (0 = no SCM)
        scm_type: SCM type ("fly_ash", "ggbfs", "silica_fume")
        scm_sg: SCM specific gravity (default depends on scm_type)
        admixture_type: Admixture type string (e.g. "superplasticizer")
        admixture_dosage: Admixture dosage (% by weight of cement)
        admixture_water_reduction: Water reduction from admixture (%)
        volume_m3: Target volume (default 1.0)
        has_production_data: Whether ≥30 test results exist (ACI only) / ≥20 results exist (DOE)
        sulfate_exposure_class: ACI 318 sulfate class ("S0"-""S3")
        freezing_exposure_class: ACI 301 freezing-and-thawing class ("F0"-"F3")
        water_exposure_class: ACI 301 water-contact class ("W0"-"W2")
        corrosion_exposure_class: ACI 301 corrosion class ("C0"-"C2", non-prestressed)
        form_width_mm: narrowest form dimension, mm (ACI NMSA check, optional)
        slab_depth_mm: slab depth, mm (ACI NMSA check, optional)
        bar_spacing_mm: min clear bar spacing, mm (ACI NMSA check, optional)
        concrete_temp_c: fresh concrete temperature, °C (ACI T5.3.3.1; 22.5 = baseline)
        manufactured_sand: fine aggregate is manufactured sand (ACI +5% water)
        prestressed: prestressed reinforcement present (ACI chloride scope)
        trial_density_kg_m3: measured trial fresh density (ACI §5.3.10 yield check)
        trial_slump_mm: measured trial slump (ACI §5.3.10.1)
        trial_air_pct: measured trial air (ACI §5.3.10.2)
        trial_strength_mpa: measured trial 28-day strength (ACI §5.3.10.3)
        air_pct: entrained air % (DOE §8; 0 = non-air-entrained)
        vebe_s: Vebe time in seconds as workability basis (DOE; None = slump)
        ca_split: "10+20" or "10+20+40" CA subdivision (DOE §5.5)
        placing_method: "chute" or "pump" (IS §5.5.2 CA reduction)
        site_control: "good" or "fair" (IS Table 2 Note 1, fair adds 1 MPa)
        admixture_water_kg: liquid-admixture water in kg/m³ (IS Cl. 5.1 note)
        mass_concrete: design as mass concrete (IS §9; NMSA 40/80/150)
        scc_class: target slump-flow class "SF1"/"SF2"/"SF3" (IS §7.2.1)
        scc_slump_flow_mm: measured slump-flow (IS SCC acceptance)
        scc_lbox_ratio: measured L-box ratio (IS SCC, ≥0.80 passes)
        scc_segregation_pct: measured sieve-segregation SR % (IS SCC)
        scc_vfunnel_s: measured V-funnel time in s (IS SCC)
        w_c_ratio: Water-cement ratio manual override (or durability limit for DOE)
        defective_percent: Percentage of defectives (DOE only)
        age_days: Age in days for target strength (DOE only)
        min_cement_kg: Minimum cement content (DOE only)
        max_cement_kg: Maximum cement content (DOE only)
        fine_agg_pct_passing_600um: Fine aggregate % passing 600µm (DOE only)
        std_deviation: User-provided standard deviation in MPa (DOE only).
            If provided, overrides automatic calculation from Figure 3.
        num_test_cubes: DOE structural — number of test cubes (n) cast for
            strength testing. When supplied, BRE 331:1997 Figure 3 structural
            rule applies: n<20 → s=8 MPa (Line A), n≥20 → s=4 MPa (Line B).
            n_cubes is an alias.
            This app assumes DOE mixes are for structural elements (fc≥25 MPa).

    Returns:
        MixDesignResult with all proportions
    """
    from concrete_mix.models.materials import (
        SCM,
        Admixture,
        AggregateShape,
        Cement,
        CementType,
        CoarseAggregate,
        FineAggregate,
        SCMType,
    )

    # Resolve cement type
    try:
        ct = CementType(cement_type)
    except ValueError:
        ct = CementType.OPC_43

    scm_type_enum = (
        SCMType(scm_type)
        if scm_type in ("fly_ash", "ggbfs", "silica_fume", "metakaolin")
        else SCMType.FLY_ASH
    )

    scms = ()
    if scm_replacement_percent > 0:
        scms = (
            SCM(
                type=scm_type_enum,
                specific_gravity=scm_sg,
                replacement_percent=scm_replacement_percent,
            ),
        )

    # BRE 331:1997 Stages 1-5 (Table 3, C3, Figure 5, Figure 6) assume no
    # chemical admixture; §5.3 introduces a water-reducing admixture only as
    # an explicit option when the C3 cement content exceeds the specified
    # maximum. "None" must therefore mean a plain mix: any stray
    # water-reduction/dosage values (e.g. left over in the UI spins after
    # switching the type back to None) are ignored, never synthesised into
    # a default superplasticizer.
    admixture = None
    _admix_type_norm = (admixture_type or "").strip().lower()
    if _admix_type_norm and _admix_type_norm != "none":
        admixture = Admixture(
            type=admixture_type,
            dosage_percent=admixture_dosage,
            water_reduction_percent=admixture_water_reduction,
            specific_gravity=admixture_sg,
        )

    # Resolve coarse aggregate shape / type
    effective_ca = coarse_agg_type if coarse_agg_type is not None else aggregate_shape
    if isinstance(effective_ca, str) and effective_ca.lower() in ("crushed", "uncrushed"):
        agg_shape = AggregateShape.ANGULAR if effective_ca.lower() == "crushed" else AggregateShape.GRAVEL
    else:
        try:
            agg_shape = AggregateShape(effective_ca)
        except ValueError:
            agg_shape = AggregateShape.GRAVEL

    # Resolve fine aggregate shape / type (DOE: separate from coarse)
    effective_fa = fine_agg_type if fine_agg_type is not None else fine_agg_shape
    if effective_fa is not None:
        if isinstance(effective_fa, str) and effective_fa.lower() in ("crushed", "uncrushed"):
            fa_agg_shape = AggregateShape.ANGULAR if effective_fa.lower() == "crushed" else AggregateShape.GRAVEL
        else:
            try:
                fa_agg_shape = AggregateShape(effective_fa)
            except ValueError:
                fa_agg_shape = agg_shape
    else:
        fa_agg_shape = agg_shape  # Default to coarse aggregate shape

    fa = FineAggregate(
        specific_gravity=fine_agg_sg,
        absorption_percent=fine_agg_absorption,
        moisture_content_percent=fine_agg_moisture,
        fineness_modulus=fine_agg_fm,
        grading_zone=fine_agg_grading_zone,
        pct_passing_600um=fine_agg_pct_passing_600um,
        shape=fa_agg_shape,
    )
    ca = CoarseAggregate(
        specific_gravity=coarse_agg_sg,
        nominal_max_size_mm=nmsa,
        absorption_percent=coarse_agg_absorption,
        moisture_content_percent=coarse_agg_moisture,
        bulk_density_kg_m3=coarse_agg_bulk_density,
        shape=agg_shape,
    )

    # Resolve DOE structural n alias
    _n_cubes = num_test_cubes if num_test_cubes is not None else n_cubes
    inp = MixDesignInput(
        code=code,
        target_strength_mpa=target_strength_mpa,
        characteristic_strength_mpa=characteristic_strength_mpa,
        ca_volume_fraction_override=ca_volume_fraction_override,
        slump_mm=slump_mm,
        cement=Cement(type=ct, specific_gravity=cement_sg),
        fine_aggregate=fa,
        coarse_aggregate=ca,
        scms=scms,
        admixture=admixture,
        exposure_class=exposure_class,
        concrete_type=concrete_type,
        air_entrained=air_entrained,
        volume_m3=volume_m3,
        has_production_data=has_production_data,
        sulfate_exposure_class=sulfate_exposure_class,
        freezing_exposure_class=freezing_exposure_class,
        water_exposure_class=water_exposure_class,
        corrosion_exposure_class=corrosion_exposure_class,
        form_width_mm=form_width_mm,
        slab_depth_mm=slab_depth_mm,
        bar_spacing_mm=bar_spacing_mm,
        concrete_temp_c=concrete_temp_c,
        manufactured_sand=manufactured_sand,
        prestressed=prestressed,
        trial_density_kg_m3=trial_density_kg_m3,
        trial_slump_mm=trial_slump_mm,
        trial_air_pct=trial_air_pct,
        trial_strength_mpa=trial_strength_mpa,
        num_strength_tests=num_strength_tests,
        target_paste_volume_pct=target_paste_volume_pct,
        air_pct=air_pct,
        vebe_s=vebe_s,
        ca_split=ca_split,
        placing_method=placing_method,
        pump_ca_reduction_percent=pump_ca_reduction_percent,
        site_control=site_control,
        admixture_water_kg=admixture_water_kg,
        mass_concrete=mass_concrete,
        scc_class=scc_class,
        scc_slump_flow_mm=scc_slump_flow_mm,
        scc_lbox_ratio=scc_lbox_ratio,
        scc_segregation_pct=scc_segregation_pct,
        scc_vfunnel_s=scc_vfunnel_s,
        w_c_ratio=w_c_ratio,
        defective_percent=defective_percent,
        age_days=age_days,
        min_cement_kg=min_cement_kg,
        max_cement_kg=max_cement_kg,
        std_deviation=std_deviation,
        margin_mpa=margin_mpa,
        num_test_cubes=_n_cubes,
    )

    res = design_mix(inp)
    object.__setattr__(res, "_input", inp)
    return res


__all__ = [
    # Main API
    "design_mix",
    "design_mix_simple",
    "get_code_implementation",
    "calculate_target_strength",
    "TargetStrengthResult",
    "derive_mix_design_params",
    "PSDLinkage",
    "calculate_is10262_trial_mixes",
    # Models
    "MixDesignInput",
    "MixDesignResult",
    "CalculationStep",
    # Materials
    "Cement",
    "CementType",
    "FineAggregate",
    "CoarseAggregate",
    "SCM",
    "SCMType",
    "Admixture",
    # Estimators
    "MaterialPrices",
    "estimate_cost",
    "estimate_carbon",
    "carbon_savings_vs_opc",
    # Export
    "export_to_csv",
    "export_to_json",
    "generate_report",
    # Validation
    "validate_mix_input",
]
