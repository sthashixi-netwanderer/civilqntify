#!/usr/bin/env python3
"""CivilQntify — CLI Workflow.

Full interactive workflow:
  1. Concrete Mix Design (ACI 211.1 or IS 10262:2019)
  2. Data handoff prompt
  3. Material Quantification with user-editable overrides

Run:  python main_cli.py
"""

from __future__ import annotations

import sys

from concrete_mix import design_mix_simple, generate_report, validate_mix_input, MixDesignResult
from concrete_mix.codes.tables.is_tables import (
    WATER_CONTENT,
    CA_VOLUME_FRACTION,
    calculate_target_strength,
)
from concrete_mix.models.materials import CementType
from material_quantify import MaterialQuantifier, StructuralElement
from material_quantify.models.transfer_data import MixDesignTransferData


# ── Helpers ────────────────────────────────────────────────────────

def _prompt_float(prompt: str, default: float | None = None, lo: float = 0.0, hi: float = 1e9) -> float:
    """Prompt for a float value with optional default and range."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            val = float(raw)
            if not lo <= val <= hi:
                print(f"    Value must be between {lo} and {hi}.")
                continue
            return val
        except ValueError:
            print("    Enter a valid number.")


def _prompt_int(prompt: str, default: int | None = None, lo: int = 1, hi: int = 99999) -> int:
    """Prompt for an integer value."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            val = int(raw)
            if not lo <= val <= hi:
                print(f"    Value must be between {lo} and {hi}.")
                continue
            return val
        except ValueError:
            print("    Enter a valid integer.")


def _prompt_choice(prompt: str, choices: list[str], default: str | None = None) -> str:
    """Prompt for a choice from a list."""
    while True:
        suffix = f" [{default}]" if default else ""
        print(f"  {prompt}{suffix}:")
        for i, c in enumerate(choices, 1):
            print(f"    {i}. {c}")
        raw = input("  Enter number: ").strip()
        if raw == "" and default:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print("    Invalid selection.")


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt yes/no."""
    suffix = " [Y/n]" if default else " [y/N]"
    raw = input(f"  {prompt}{suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


# ── Mix Design Input Collection ────────────────────────────────────

def collect_mix_inputs() -> dict:
    """Collect all mix design inputs interactively."""
    print("\n" + "=" * 60)
    print("  CONCRETE MIX DESIGN — Input Parameters")
    print("=" * 60)

    # Standard
    code = _prompt_choice(
        "Select design standard",
        ["ACI 211.1 (American)", "IS 10262 (Indian)"],
        default="IS 10262 (Indian)",
    )
    is_aci = "ACI" in code
    code_key = "aci211" if is_aci else "is10262"

    # Target strength
    strength_unit = "psi" if is_aci else "MPa"
    strength_default = 3000.0 if is_aci else 25.0
    strength_lo = 2000.0 if is_aci else 10.0
    strength_hi = 10000.0 if is_aci else 80.0
    strength = _prompt_float(f"Target compressive strength ({strength_unit})", strength_default, strength_lo, strength_hi)
    if is_aci:
        target_strength_mpa = strength / 145.038
        characteristic_strength = target_strength_mpa
    else:
        # IS 10262:2019 — user enters characteristic strength (fck)
        characteristic_strength = strength
        ftm, desc = calculate_target_strength(characteristic_strength)
        print(f"\n  Target mean strength (f'ck): {desc}")
        print(f"  → f'ck = {ftm} MPa\n")
        target_strength_mpa = ftm

    # Slump (ACI only — IS 10262 uses Table 4 values by NMSA)
    slump = 75.0
    if is_aci:
        slump = _prompt_float("Slump (mm)", 75.0, 10.0, 250.0)

    # NMSA
    nmsa = _prompt_choice("Nominal max aggregate size", ["10 mm", "20 mm", "40 mm"], "20 mm")
    nmsa_val = int(nmsa.split()[0])

    # IS 10262:2019 — Show water content from Table 4 (read-only)
    if not is_aci and nmsa_val in WATER_CONTENT:
        water_content_base = WATER_CONTENT[nmsa_val]
        print(f"\n  Water content (IS 10262:2019 Table 4): {water_content_base} kg/m³")
        print(f"  — Determined by NMSA ({nmsa_val}mm), not editable.\n")

    # IS 10262:2019 — CA volume fraction selection (Table 5)
    ca_fraction_override = None
    if not is_aci and nmsa_val in CA_VOLUME_FRACTION:
        options = CA_VOLUME_FRACTION[nmsa_val]
        zone_fractions = list(options.values())
        print(f"  Select Coarse Aggregate Volume Fraction (IS 10262:2019 Table 5, NMSA {nmsa_val}mm):")
        for i, (zone, frac) in enumerate(options.items(), 1):
            print(f"    {i}. {frac:.2f}")
        print(f"  Enter number [1-{len(options)}]:")
        raw = input("  > ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(zone_fractions):
                ca_fraction_override = zone_fractions[idx]
                zone = list(options.keys())[idx]
                print(f"  → Zone {zone}: volume fraction {ca_fraction_override}\n")
            else:
                ca_fraction_override = zone_fractions[1]  # Default to Zone II
                print(f"  → Default: Zone II: volume fraction {ca_fraction_override}\n")
        except ValueError:
            ca_fraction_override = zone_fractions[1]  # Default to Zone II
            print(f"  → Default: Zone II: volume fraction {ca_fraction_override}\n")

    # Cement type
    if is_aci:
        cement_types = ["TYPE_I", "TYPE_II", "TYPE_III", "TYPE_IV", "TYPE_V"]
    else:
        cement_types = ["OPC_33", "OPC_43", "OPC_53", "PPC", "PSC"]
    cement_type = _prompt_choice("Cement type", cement_types, cement_types[1])

    # Cement SG
    cement_sg = _prompt_float("Cement specific gravity", 3.15, 2.8, 3.5)

    # Fine aggregate
    print("\n  --- Fine Aggregate ---")
    fa_sg = _prompt_float("Specific gravity", 2.65, 2.2, 3.0)
    if is_aci:
        fa_fm = _prompt_float("Fineness modulus", 2.70, 1.0, 4.0)
        fa_grading = None
    else:
        fa_fm = 2.70
        # Grading zone is derived from CA fraction selection above
        fa_grading = None  # Will be set from ca_fraction_override lookup

    fa_absorption = _prompt_float("Water absorption (%)", 1.0, 0.0, 10.0)
    fa_moisture = _prompt_float("Free moisture content (%)", 0.0, 0.0, 20.0)

    # Coarse aggregate
    print("\n  --- Coarse Aggregate ---")
    ca_sg = _prompt_float("Specific gravity", 2.70, 2.2, 3.2)
    ca_absorption = _prompt_float("Water absorption (%)", 0.5, 0.0, 10.0)
    ca_moisture = _prompt_float("Free moisture content (%)", 0.0, 0.0, 20.0)
    ca_bulk_density = _prompt_float("Dry rodded bulk density (kg/m\u00b3)", 1600.0, 1000.0, 2000.0)

    # Aggregate shape (IS only)
    agg_shape = "gravel"
    if not is_aci:
        shapes = ["Rounded Gravel", "Gravel", "Sub-angular", "Angular", "Crushed Fragments"]
        shape_choice = _prompt_choice("Aggregate shape", shapes, "Gravel")
        agg_shape = shape_choice.lower().replace(" ", "_").replace("-", "_")

    # Exposure (IS only)
    exposure_class = None
    if not is_aci:
        exp_choices = ["None", "Mild", "Moderate", "Severe", "Very Severe", "Extreme"]
        exp = _prompt_choice("Exposure class (IS 456)", exp_choices, "None")
        if exp != "None":
            exposure_class = exp.lower().replace(" ", "_")

    # Air entrainment (ACI only)
    air_entrained = False
    if is_aci:
        air_entrained = _prompt_yes_no("Air-entrained concrete?", default=False)

    # ACI-specific
    has_production_data = True
    sulfate_class = "S0"
    if is_aci:
        has_production_data = _prompt_yes_no("Has production data (\u226530 tests)?", default=True)
        sulf_choices = ["S0 (None)", "S1 (Moderate)", "S2 (Severe)", "S3 (Very Severe)"]
        sulf = _prompt_choice("Sulfate exposure class", sulf_choices, "S0 (None)")
        sulfate_class = sulf.split()[0]

    # SCM
    print("\n  --- Supplementary Cementitious Material ---")
    scm_types = ["None", "Fly Ash", "GGBFS", "Silica Fume"]
    scm_type_choice = _prompt_choice("SCM type", scm_types, "None")
    scm_pct = 0.0
    scm_type_key = "fly_ash"
    scm_sg = 2.20
    if scm_type_choice != "None":
        scm_type_key = scm_type_choice.lower().replace(" ", "_")
        scm_pct = _prompt_float("Replacement percentage (%)", 20.0, 5.0, 60.0)
        scm_sg_defaults = {"fly_ash": 2.20, "ggbfs": 2.90, "silica_fume": 2.20}
        scm_sg = _prompt_float("Specific gravity", scm_sg_defaults.get(scm_type_key, 2.20), 1.5, 4.0)

    # Admixture
    print("\n  --- Admixture ---")
    admix_types = ["None", "Superplasticizer", "Plasticizer", "Retarder", "Accelerator"]
    admix_type_choice = _prompt_choice("Admixture type", admix_types, "None")
    admix_type = ""
    admix_dosage = 1.0
    admix_wr = 0.0
    if admix_type_choice != "None":
        admix_type = admix_type_choice.lower()
        admix_dosage = _prompt_float("Dosage (% by weight of cement)", 1.0, 0.0, 5.0)
        admix_wr = _prompt_float("Water reduction (%)", 10.0, 0.0, 30.0)

    # Volume
    volume = _prompt_float("Target concrete volume (m\u00b3)", 1.0, 0.1, 10000.0)

    # Derive grading zone from CA fraction selection for IS mode
    if not is_aci and ca_fraction_override is not None and nmsa_val in CA_VOLUME_FRACTION:
        for zone, frac in CA_VOLUME_FRACTION[nmsa_val].items():
            if abs(frac - ca_fraction_override) < 0.001:
                fa_grading = zone
                break
        if fa_grading is None:
            fa_grading = "II"

    return {
        "code": code_key,
        "target_strength_mpa": target_strength_mpa,
        "characteristic_strength_mpa": characteristic_strength if not is_aci else None,
        "ca_volume_fraction_override": ca_fraction_override,
        "slump_mm": slump,
        "nmsa": nmsa_val,
        "cement_type": cement_type,
        "cement_sg": cement_sg,
        "fine_agg_sg": fa_sg,
        "fine_agg_fm": fa_fm,
        "fine_agg_grading_zone": fa_grading,
        "fine_agg_absorption": fa_absorption,
        "fine_agg_moisture": fa_moisture,
        "coarse_agg_sg": ca_sg,
        "coarse_agg_absorption": ca_absorption,
        "coarse_agg_moisture": ca_moisture,
        "coarse_agg_bulk_density": ca_bulk_density,
        "aggregate_shape": agg_shape,
        "air_entrained": air_entrained,
        "exposure_class": exposure_class,
        "scm_replacement_percent": scm_pct,
        "scm_type": scm_type_key,
        "scm_sg": scm_sg,
        "admixture_type": admix_type,
        "admixture_dosage": admix_dosage,
        "admixture_water_reduction": admix_wr,
        "volume_m3": volume,
        "has_production_data": has_production_data,
        "sulfate_exposure_class": sulfate_class,
    }


# ── Mix Design Execution ───────────────────────────────────────────

def run_mix_design(params: dict) -> MixDesignResult:
    """Execute the mix design and display the report."""
    print("\n" + "=" * 60)
    print("  CONCRETE MIX DESIGN — Calculation")
    print("=" * 60 + "\n")

    result = design_mix_simple(**params)

    # Print text report
    from concrete_mix.models.mix_input import MixDesignInput
    from concrete_mix.models.materials import (
        Cement, CementType, FineAggregate, CoarseAggregate,
        AggregateShape, SCM, SCMType, Admixture,
    )

    report = generate_report(result)
    print(report)

    return result


# ── Material Quantification Workflow ───────────────────────────────

def run_quantification(result: MixDesignResult, params: dict) -> None:
    """Run the material quantification workflow."""

    # Determine bag weight based on code
    is_aci = "ACI" in result.code_used.upper()
    bag_weight = 42.64 if is_aci else 50.0

    td = MixDesignTransferData.from_mix_design_result(
        result,
        cement_bag_weight_kg=bag_weight,
        coarse_agg_bulk_density_kg_m3=params.get("coarse_agg_bulk_density", 1600.0),
        fine_agg_sg=params.get("fine_agg_sg", 2.65),
        coarse_agg_sg=params.get("coarse_agg_sg", 2.70),
    )

    # Display transferred data
    print("\n" + "=" * 60)
    print("  TRANSFERRED MIX DESIGN DATA (per m\u00b3)")
    print("=" * 60)
    for label, value, unit in td.to_display_dict():
        print(f"  {label:<25} {value:<12} {unit}")
    print()

    # Allow overrides
    if _prompt_yes_no("Do you want to edit/override any mix design value?", default=False):
        td = _edit_transfer_data(td)

    # Quantification basis
    print("\n" + "-" * 60)
    print("  QUANTIFICATION BASIS")
    print("-" * 60)
    basis = _prompt_choice(
        "How would you like to specify concrete volume?",
        ["Total Concrete Volume", "Structural Element Dimensions"],
        "Total Concrete Volume",
    )

    quantifier = MaterialQuantifier(td)

    if basis == "Total Concrete Volume":
        vol = _prompt_float("Total concrete volume (m\u00b3)", 1.0, 0.01, 100000.0)
        wastage = _prompt_float("Wastage factor (%)", 5.0, 0.0, 30.0)
        bill = quantifier.quantify_by_volume(vol, wastage)
    else:
        elements = _collect_elements()
        wastage = _prompt_float("Wastage factor (%)", 5.0, 0.0, 30.0)
        bill = quantifier.quantify_by_elements(elements, wastage)

    # Output
    print("\n" + bill.format_report())


def _edit_transfer_data(td: MixDesignTransferData) -> MixDesignTransferData:
    """Let the user override individual mix values."""
    print("\n  Enter new values or press Enter to keep current value.")
    print("  (Only fields you change will be updated)\n")

    overrides: dict[str, float] = {}

    fields = [
        ("cement_kg_per_m3", "Cement (kg/m\u00b3)", td.cement_kg_per_m3),
        ("water_kg_per_m3", "Water - design (kg/m\u00b3)", td.water_kg_per_m3),
        ("field_water_kg_per_m3", "Water - field (kg/m\u00b3)", td.field_water_kg_per_m3),
        ("fine_aggregate_kg_per_m3", "Fine Aggregate - SSD (kg/m\u00b3)", td.fine_aggregate_kg_per_m3),
        ("field_fine_aggregate_kg_per_m3", "Fine Aggregate - field (kg/m\u00b3)", td.field_fine_aggregate_kg_per_m3),
        ("coarse_aggregate_kg_per_m3", "Coarse Aggregate - SSD (kg/m\u00b3)", td.coarse_aggregate_kg_per_m3),
        ("field_coarse_aggregate_kg_per_m3", "Coarse Aggregate - field (kg/m\u00b3)", td.field_coarse_aggregate_kg_per_m3),
        ("scm_kg_per_m3", "SCM (kg/m\u00b3)", td.scm_kg_per_m3),
        ("admixture_kg_per_m3", "Admixture (kg/m\u00b3)", td.admixture_kg_per_m3),
    ]

    for key, label, current in fields:
        raw = input(f"  {label} [{current:.1f}]: ").strip()
        if raw:
            try:
                overrides[key] = float(raw)
            except ValueError:
                print(f"    Invalid value — keeping {current:.1f}")

    if overrides:
        print(f"\n  Updated {len(overrides)} field(s).")
        return td.with_overrides(**overrides)

    print("  No changes made.")
    return td


def _collect_elements() -> list[StructuralElement]:
    """Collect structural element dimensions interactively."""
    elements: list[StructuralElement] = []
    element_types = ["Footing", "Column", "Beam", "Slab", "Wall", "Custom"]

    print("\n  Add structural elements (enter 'done' when finished):")

    while True:
        print(f"\n  --- Element #{len(elements) + 1} ---")
        etype = _prompt_choice("Element type", element_types, "Footing")
        if etype.lower() == "done":
            break

        labels = StructuralElement.DIMENSION_LABELS.get(
            etype.lower(), ("Dim 1", "Dim 2", "Dim 3")
        )

        l = _prompt_float(f"{labels[0]} (m)", lo=0.01, hi=1000.0)
        w = _prompt_float(f"{labels[1]} (m)", lo=0.01, hi=1000.0)
        d = _prompt_float(f"{labels[2]} (m)", lo=0.01, hi=1000.0)
        qty = _prompt_int("Quantity", 1, 1, 10000)

        elem = StructuralElement(etype, l, w, d, qty)
        elements.append(elem)
        print(f"    Added: {elem.summary_line()}")

        if not _prompt_yes_no("Add another element?", default=True):
            break

    if not elements:
        print("  No elements added. Using default volume = 1.0 m\u00b3.")
        elements.append(StructuralElement("custom", 1.0, 1.0, 1.0, 1))

    return elements


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    """Run the full CivilQntify CLI workflow."""
    print("=" * 60)
    print("  CivilQntify — Concrete Mix Design & Material Quantification")
    print("=" * 60)

    try:
        # Phase 1: Mix design
        params = collect_mix_inputs()
        result = run_mix_design(params)

        # Phase 2: Handoff prompt
        print("\n" + "-" * 60)
        if _prompt_yes_no(
            "Send this mix design to the Material Quantification module?",
            default=True,
        ):
            run_quantification(result, params)
        else:
            print("\n  Mix design complete. Data not sent to quantification.")

    except KeyboardInterrupt:
        print("\n\n  Aborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Error: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  CivilQntify — Done")
    print("=" * 60)


if __name__ == "__main__":
    main()
