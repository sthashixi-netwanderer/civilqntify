"""Regression coverage for the Module 1 -> Module 2 handoff (audit C4/C6).

The concrete mix result is the only record that survives between a design and
its material bill, so any field a design computes and the transfer silently
drops is data the site never receives. These tests pin that handoff closed:

- every ``MixDesignResult`` field is either carried into
  ``MixDesignTransferData`` or listed with a reason it is intentionally not;
- the SCM identity and the DOE single-size coarse split survive to the bill;
- a split design produces per-size invoice lines that sum to the coarse
  aggregate total, and an unsplit design keeps exactly one line;
- the CLI documents itself (``--help``) and forwards the SCM it collected.
"""
from __future__ import annotations

from dataclasses import fields
import json
import subprocess
import sys
from pathlib import Path

import pytest

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.is10262 import IS10262MixDesign
from concrete_mix.models.materials import SCM, SCMType, FineAggregate
from concrete_mix.models.mix_input import MixDesignInput
from concrete_mix.models.mix_result import MixDesignResult
from material_quantify.cost import (
    ProjectMaterialPrices, estimate_project_cost,
)
from material_quantify.engine.quantifier import MaterialQuantifier
from material_quantify.models.transfer_data import MixDesignTransferData

REPO_ROOT = Path(__file__).resolve().parents[1]


# Every MixDesignResult field, declared against where it lands. The transfer
# renames fields (cement_kg -> cement_kg_per_m3), so a name-set difference
# cannot prove anything: the mapping has to be written out. Adding a field to
# MixDesignResult without adding a line here fails
# test_c04_every_result_field_is_declared.
CARRIED_AS: dict[str, str] = {
    "code_used": "code_used",
    "target_mean_strength_mpa": "target_mean_strength_mpa",
    "w_c_ratio": "w_c_ratio",
    "water_kg": "water_kg_per_m3",
    "cement_kg": "cement_kg_per_m3",
    "scm_kg": "scm_kg_per_m3",
    "scm_type": "scm_type",
    "fine_aggregate_kg": "fine_aggregate_kg_per_m3",
    "coarse_aggregate_kg": "coarse_aggregate_kg_per_m3",
    "air_volume_percent": "air_volume_percent",
    "ca_split_kg": "ca_split_kg",
    "adjusted_water_kg": "field_water_kg_per_m3",
    "field_fine_aggregate_kg": "field_fine_aggregate_kg_per_m3",
    "field_coarse_aggregate_kg": "field_coarse_aggregate_kg_per_m3",
    "admixture_kg": "admixture_kg_per_m3",
    "admixture_type": "admixture_type",
}

# Fields the bill has no use for, with the reason. A bare drop has to be
# argued for here rather than discovered later on an invoice.
INTENTIONALLY_NOT_CARRIED: dict[str, str] = {
    "steps": "Calculation trace; belongs to the report and history",
    "warnings": "Design-time advice, already rendered into the report",
    "cost_per_m3": "Superseded by the cost tab, which prices the bill",
    "carbon_kg_co2_per_m3": "Carbon figure, not a material quantity",
    "volume_m3": "The pour volume is an input to quantification, not a property",
    "admixture_dosage_percent": (
        "Dosing is a batching instruction, already in the mix report"
    ),
    "water_reduction_percent": (
        "Water reduction is a design choice, already in the mix report"
    ),
}


def _inp(code: str, **overrides) -> MixDesignInput:
    """Build a minimal valid input for each engine."""
    base = dict(
        target_strength_mpa=30.0,
        characteristic_strength_mpa=30.0,
        slump_mm=50.0,
        fine_aggregate=FineAggregate(pct_passing_600um=70.0),
    )
    base.update(overrides)
    return MixDesignInput(code=code, **base)


def _split_design() -> MixDesignResult:
    """A DOE design that subdivides its coarse aggregate into single sizes."""
    return DOEMixDesign().design(
        _inp(
            "doe",
            ca_split="10+20",
            scms=(SCM(type=SCMType.GGBFS, specific_gravity=2.90,
                      replacement_percent=30.0),),
        )
    )


def _scm_design(code: str) -> MixDesignResult:
    """A design of each standard that uses a GGBFS replacement."""
    scms = (SCM(type=SCMType.GGBFS, specific_gravity=2.90,
                replacement_percent=30.0),)
    if code == "aci211":
        return ACI211MixDesign().design(_inp("aci211", scms=scms))
    if code == "is10262":
        return IS10262MixDesign().design(_inp("is10262", scms=scms))
    return DOEMixDesign().design(_inp("doe", scms=scms))


# -- Completeness ------------------------------------------------------


def test_c04_every_result_field_is_declared():
    """No MixDesignResult field may be silently lost on the way to the bill."""
    result_fields = {f.name for f in fields(MixDesignResult) if f.init}
    transfer_fields = {f.name for f in fields(MixDesignTransferData) if f.init}

    undeclared = sorted(result_fields - set(CARRIED_AS)
                        - set(INTENTIONALLY_NOT_CARRIED))
    assert not undeclared, (
        "MixDesignResult fields appear in neither CARRIED_AS nor "
        f"INTENTIONALLY_NOT_CARRIED: {undeclared}"
    )
    # A stale entry hides a rename, so it must not name a field that no
    # longer exists.
    stale = sorted(set(CARRIED_AS) - result_fields)
    assert not stale, f"CARRIED_AS names absent MixDesignResult fields: {stale}"
    stale_notes = sorted(set(INTENTIONALLY_NOT_CARRIED) - result_fields)
    assert not stale_notes, (
        f"INTENTIONALLY_NOT_CARRIED names absent fields: {stale_notes}"
    )
    # Every declared destination must actually exist, or the mapping is a lie.
    bad_targets = sorted(set(CARRIED_AS.values()) - transfer_fields)
    assert not bad_targets, f"CARRIED_AS points at absent fields: {bad_targets}"
    # And the mapping must say something, not just assert presence.
    assert all(why.strip() for why in INTENTIONALLY_NOT_CARRIED.values())


def test_c04_declared_mapping_is_not_decorative():
    """The mapping must be the one the constructor actually implements."""
    import inspect

    from material_quantify.models import transfer_data as td_mod

    source = inspect.getsource(td_mod.MixDesignTransferData.from_mix_design_result)
    for result_field, transfer_field in CARRIED_AS.items():
        if result_field == "scm_type":
            continue  # read as result.scm_type, covered below
        assert f"result.{result_field}" in source or result_field in (
            "code_used",
        ), f"from_mix_design_result never reads result.{result_field}"
    assert "result.scm_type" in source
    assert "result.ca_split_kg" in source


@pytest.mark.parametrize("code", ["aci211", "is10262", "doe"])
def test_c04_scm_identity_reaches_the_bill(code):
    """A GGBFS design must name GGBFS downstream, not 'SCM (unspecified)'."""
    result = _scm_design(code)
    assert result.scm_kg > 0
    assert result.scm_type == SCMType.GGBFS.value

    td = MixDesignTransferData.from_mix_design_result(result)
    assert td.scm_type == "ggbfs"

    bill = MaterialQuantifier(td).quantify_by_volume(10)
    priced = estimate_project_cost(
        bill, prices=ProjectMaterialPrices(scm_per_kg=2.0)
    )
    scm_row = next(r for r in priced["material_breakdown"] if r["name"] == "SCM")
    assert scm_row["material_type"] == "ggbfs"
    assert priced["is_complete"]


def test_c04_design_without_scm_stays_unspecified_rather_than_guessing():
    """No SCM must not invent one."""
    result = DOEMixDesign().design(_inp("doe"))
    assert result.scm_type is None
    td = MixDesignTransferData.from_mix_design_result(result)
    assert td.scm_type == "SCM (unspecified)"


def test_c04_scaled_result_keeps_scm_type():
    """scaled_to_volume must not drop the SCM it is re-emitting."""
    scaled = _scm_design("doe").scaled_to_volume(25.0)
    assert scaled.scm_type == "ggbfs"
    assert scaled.volume_m3 == 25.0


def test_c04_cli_overrides_the_flattened_engine_label():
    """The CLI's own 'Fly Ash Class C' must survive the engine's fly_ash."""
    result = MixDesignResult("ACI PRC-211.1-22", 35, 0.5, 175, 350, scm_kg=100)
    assert result.scm_type is None
    td = MixDesignTransferData.from_mix_design_result(
        result, scm_type="fly_ash_c",
    )
    assert td.scm_type == "fly_ash_c"


# -- Single-size coarse split -----------------------------------------


def test_c04_split_reaches_the_bill_and_sums_to_the_total():
    result = _split_design()
    assert result.ca_split_kg
    assert sum(result.ca_split_kg.values()) == pytest.approx(
        result.coarse_aggregate_kg
    )

    td = MixDesignTransferData.from_mix_design_result(
        result, coarse_agg_bulk_density_kg_m3=1600.0,
    )
    assert td.ca_split_kg == result.ca_split_kg

    bill = MaterialQuantifier(td).quantify_by_volume(20.0, wastage_percent=5.0)
    assert bill.coarse_aggregate_split_kg is not None
    assert sum(bill.coarse_aggregate_split_kg.values()) == pytest.approx(
        bill.total_coarse_aggregate_kg
    )
    assert set(bill.coarse_aggregate_split_kg) == {"10 mm", "20 mm"}
    # Per-size masses scale exactly with the pour, keeping the engine's own
    # 1 : 2 clause 5.5 split (the engine applies its 5 kg rounding grid, so the
    # ratio is 1 : 2 to within that grid, not exactly).
    for size, kg in result.ca_split_kg.items():
        share = kg / sum(result.ca_split_kg.values())
        assert bill.coarse_aggregate_split_kg[size] == pytest.approx(
            bill.total_coarse_aggregate_kg * share, abs=1.0
        )


def test_c04_split_is_scaled_on_the_field_mass_not_the_ssd_mass():
    """Aggregate moisture must be reflected once, not silently dropped."""
    result = _split_design()
    td = MixDesignTransferData.from_mix_design_result(
        result, coarse_agg_bulk_density_kg_m3=1600.0,
    )
    # Field coarse aggregate carries 5% more surface water than the SSD basis.
    wet = td.with_overrides(
        field_coarse_aggregate_kg_per_m3=td.coarse_aggregate_kg_per_m3 * 1.05
    )
    dry_bill = MaterialQuantifier(td).quantify_by_volume(10.0, 0.0)
    wet_bill = MaterialQuantifier(wet).quantify_by_volume(10.0, 0.0)
    assert wet_bill.total_coarse_aggregate_kg == pytest.approx(
        dry_bill.total_coarse_aggregate_kg * 1.05
    )
    assert sum(wet_bill.coarse_aggregate_split_kg.values()) == pytest.approx(
        wet_bill.total_coarse_aggregate_kg
    )
    assert wet_bill.coarse_aggregate_split_kg["10 mm"] == pytest.approx(
        dry_bill.coarse_aggregate_split_kg["10 mm"] * 1.05
    )


def test_c04_split_invoice_has_one_line_per_size():
    result = _split_design()
    bill = MaterialQuantifier(
        MixDesignTransferData.from_mix_design_result(
            result, coarse_agg_bulk_density_kg_m3=1600.0,
        )
    ).quantify_by_volume(20.0, 5.0)
    cost = estimate_project_cost(bill)
    names = [row["name"] for row in cost["material_breakdown"]]
    assert "Coarse Aggregate" not in names, "blended line hides the split"
    assert names.count("Coarse Aggregate 10 mm") == 1
    assert names.count("Coarse Aggregate 20 mm") == 1

    ca_rows = [r for r in cost["material_breakdown"]
               if r["name"].startswith("Coarse Aggregate ")]
    others = [r for r in cost["material_breakdown"]
              if not r["name"].startswith("Coarse Aggregate ")]
    assert sum(r["total"] for r in ca_rows) == pytest.approx(
        cost["total_material_cost"] - sum(r["total"] for r in others)
    )
    # The two sizes' bulk volumes together are the bill's coarse aggregate.
    assert sum(r["qty"] for r in ca_rows) == pytest.approx(
        bill.total_coarse_aggregate_bulk_m3, rel=1e-3
    )
    # One quoted rate is being applied to every size; say so rather than let
    # the invoice imply a tendered per-size price.
    assert any(
        "single-size split" in w and "no separate per-size rate" in w
        for w in cost["warnings"]
    ), cost["warnings"]


def test_c04_unsplit_design_keeps_one_blended_invoice_line():
    bill = MaterialQuantifier(
        MixDesignTransferData.from_mix_design_result(
            DOEMixDesign().design(_inp("doe")),
            coarse_agg_bulk_density_kg_m3=1600.0,
        )
    ).quantify_by_volume(20.0, 5.0)
    assert bill.coarse_aggregate_split_kg is None
    cost = estimate_project_cost(bill)
    names = [row["name"] for row in cost["material_breakdown"]]
    assert names.count("Coarse Aggregate") == 1
    assert not any("single-size split" in w for w in cost["warnings"])


def test_c04_bill_report_and_history_round_trip_carry_the_split():
    from history.serializers import deserialize_bill, serialize_bill

    bill = MaterialQuantifier(
        MixDesignTransferData.from_mix_design_result(
            _split_design(), coarse_agg_bulk_density_kg_m3=1600.0,
        )
    ).quantify_by_volume(12.0, 3.0)
    report = bill.format_report()
    assert "single size" in report
    assert "10 mm" in report and "20 mm" in report

    restored = deserialize_bill(json.loads(serialize_bill(bill)))
    assert restored == bill
    assert restored.transfer_data.ca_split_kg == bill.transfer_data.ca_split_kg

    # A legacy bill saved before the split existed must still load.
    legacy = json.loads(serialize_bill(bill))
    legacy.pop("coarse_aggregate_split_kg")
    legacy["transfer_data"].pop("ca_split_kg")
    restored_legacy = deserialize_bill(legacy)
    assert restored_legacy.coarse_aggregate_split_kg is None
    assert restored_legacy.transfer_data.ca_split_kg is None


def test_c04_transfer_display_shows_scm_type_and_split():
    td = MixDesignTransferData.from_mix_design_result(_split_design())
    labels = [row[0] for row in td.to_display_dict()]
    assert "SCM type" in labels
    assert "Coarse Aggregate (10 mm)" in labels
    assert "Coarse Aggregate (20 mm)" in labels


# -- CLI ---------------------------------------------------------------


def test_c06_cli_help_documents_the_workflow():
    proc = subprocess.run(
        [sys.executable, "main_cli.py", "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Concrete mix design" in proc.stdout
    for flag in ("--volume", "--target-strength", "--slump", "--wastage",
                 "--standard"):
        assert flag in proc.stdout, f"{flag} missing from --help"
    assert "aci211" in proc.stdout and "is10262" in proc.stdout


def test_c06_cli_supplied_flags_seed_the_prompts():
    """Flags must reach the prompts, not be parsed and discarded."""
    import main_cli

    main_cli._CLI_DEFAULTS.clear()
    try:
        args = main_cli.build_parser().parse_args(
            ["--volume", "12.5", "--wastage", "7", "--standard", "doe",
             "--slump", "90", "--target-strength", "40"]
        )
        main_cli._apply_cli_defaults(args)
        assert main_cli._CLI_DEFAULTS["volume_m3"] == 12.5
        assert main_cli._CLI_DEFAULTS["slump_mm"] == 90.0
        assert main_cli._CLI_DEFAULTS["target_strength_mpa"] == 40.0
        assert main_cli._CLI_DEFAULTS["code"] == "doe"
        assert main_cli._wastage_default() == 7.0
    finally:
        main_cli._CLI_DEFAULTS.clear()


def test_c06_cli_forwards_the_scm_type_it_collected():
    """The CLI collects an SCM key; it must reach the transfer data."""
    import inspect

    import main_cli

    source = inspect.getsource(main_cli.run_quantification)
    assert 'scm_type=params.get("scm_type")' in source, (
        "run_quantification drops the SCM type it was handed"
    )
    assert callable(getattr(main_cli, "build_parser", None))
    assert callable(getattr(main_cli, "main", None))
