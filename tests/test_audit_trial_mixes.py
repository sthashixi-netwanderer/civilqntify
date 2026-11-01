"""Regression coverage for the trial-mix workflows (audit C2/C3).

Two defects reached 1.0 through the test suite because only one side of each
branch was covered:

- the ACI trial adjustment computed fine aggregate as a pure remainder and
  aborted when the non-coarse constituents already exceeded 1 m3. That is
  exactly what clause 5.3.10.3 linear extrapolation produces when a trial cube comes
  in well below target, so the fix has to be proved on the case that used to
  crash: a valid measurement, badly failing;
- the DOE moisture-condition picker offered air-dried and surface-wet
  unconditionally, though BS 1881 Part 125 (c) and (d) are mutually exclusive
  against the aggregate absorption, so one of them always raised.

Both are covered here for the input that must work, not just the input that
must be rejected.
"""
from __future__ import annotations

import pytest

from concrete_mix.codes.aci211 import ACI211MixDesign
from concrete_mix.codes.aci_trial import evaluate_aci_trial
from concrete_mix.codes.doe import DOEMixDesign
from concrete_mix.codes.doe_trial import (
    MOISTURE_CONDITIONS,
    available_moisture_conditions,
    calculate_doe_trial_batches,
)
from concrete_mix.models.materials import (
    Admixture,
    AdmixtureType,
    CoarseAggregate,
    FineAggregate,
)
from concrete_mix.models.mix_input import MixDesignInput


# ------------------------------------------------------------------ ACI C2


def _aci_case(target: float, cube: float):
    """Design at *target* MPa and evaluate one *cube* MPa trial batch."""
    inp = MixDesignInput(
        code="aci211",
        target_strength_mpa=target,
        slump_mm=50.0,
        coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20.0),
        fine_aggregate=FineAggregate(fineness_modulus=2.7),
        admixture=Admixture(type=AdmixtureType.PCE, dosage_percent=1.0,
                            water_reduction_percent=25.0),
    )
    result = ACI211MixDesign().design(inp)
    measured = evaluate_aci_trial(
        result, inp, {"volume_m3": 0.05, "cube_strength_mpa": cube}
    )
    return result, measured


@pytest.mark.parametrize("target,cube", [
    (40.0, 28.0),
    (45.0, 20.0),
    (50.0, 25.0),
    (60.0, 30.0),
])
def test_c02_far_below_target_cube_yields_a_next_trial_not_a_crash(target, cube):
    """clause 5.3.10.3 extrapolating cement hard must still return a next batch."""
    _, measured = _aci_case(target, cube)
    next_trial = measured["next_trial"]
    assert next_trial is not None, (
        f"target {target} MPa with a {cube} MPa cube produced no next trial; "
        "hard cement extrapolation is precisely the case that used to abort"
    )
    assert next_trial["per_m3"]["fine_agg_ssd"] >= 0.0


def test_c02_overshoot_is_warned_not_raised():
    """A zero fine aggregate must be explained, not silently returned."""
    result, measured = _aci_case(45.0, 20.0)
    assert measured["next_trial"]["per_m3"]["fine_agg_ssd"] == 0.0
    overshoot = [w for w in measured["warnings"] if "exceed 1" in w]
    assert overshoot, (
        "a zero fine aggregate came back with no explanation: "
        f"{measured['warnings']}"
    )
    # The warning has to name the standard's own failure mode, not just
    # report a number.
    assert "5.3.10.3" in overshoot[0]


@pytest.mark.parametrize("target,cube", [(30.0, 24.0), (30.0, 30.0), (35.0, 32.0)])
def test_c02_ordinary_trials_are_unaffected(target, cube):
    """The normal path must stay free of the overshoot warning."""
    _, measured = _aci_case(target, cube)
    assert not any("exceed 1" in w for w in measured["warnings"]), (
        f"target {target} / cube {cube} wrongly flagged an overshoot: "
        f"{measured['warnings']}"
    )
    assert measured["next_trial"]["per_m3"]["fine_agg_ssd"] > 0.0


def test_c02_clamping_is_not_a_silent_wrong_answer():
    """The clamp must not quietly turn an impossible batch into a valid one."""
    _, measured = _aci_case(45.0, 20.0)
    cement = measured["next_trial"]["per_m3"]["cement"]
    # ACI Table 5.3.6 caps binder at about 540 kg/m3 for most exposures; a
    # linear extrapolation far past that is what the warning is about.
    assert cement > 600.0
    assert measured["warnings"], "an implausible binder was not flagged"


# ------------------------------------------------------------------ DOE C3


def _moisture_input(fa_mc, ca_mc, fa_abs=1.0, ca_abs=0.5) -> MixDesignInput:
    return MixDesignInput(
        code="doe",
        target_strength_mpa=30.0,
        characteristic_strength_mpa=30.0,
        slump_mm=50.0,
        fine_aggregate=FineAggregate(absorption_percent=fa_abs,
                                     moisture_content_percent=fa_mc,
                                     pct_passing_600um=70.0),
        coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20.0,
                                         absorption_percent=ca_abs,
                                         moisture_content_percent=ca_mc),
    )


def test_c03_surface_wet_is_offered_when_the_aggregate_holds_free_water():
    """The condition the DOE picker must offer for wet aggregate."""
    available = available_moisture_conditions(_moisture_input(3.0, 2.0))
    assert available["surface_wet"] == (True, "")
    # Dryer than absorption is what air-dried needs, so it must be refused.
    assert available["air_dried"][0] is False
    assert "surface-wet" in available["air_dried"][1].lower()


def test_c03_air_dried_is_offered_when_the_aggregate_is_drier_than_absorption():
    """The other half of the same exclusion."""
    available = available_moisture_conditions(_moisture_input(0.2, 0.1))
    assert available["air_dried"] == (True, "")
    assert available["surface_wet"][0] is False
    assert "air-dried" in available["surface_wet"][1].lower()


def test_c03_dry_conditions_are_always_available():
    """SSD and oven-dry carry no moisture precondition (BS 1881 Part 125)."""
    for fa_mc, ca_mc in ((0.0, 0.0), (3.0, 2.0), (0.2, 0.1)):
        available = available_moisture_conditions(
            _moisture_input(fa_mc=fa_mc, ca_mc=ca_mc)
        )
        for condition in ("ssd", "oven_dry"):
            assert available[condition] == (True, ""), (
                f"{condition} wrongly gated at {fa_mc}/{ca_mc}% moisture"
            )


@pytest.mark.parametrize("fa_mc,ca_mc", [
    (0.0, 0.0), (0.2, 0.1), (3.0, 2.0), (0.8, 0.4), (1.4, 0.7),
])
def test_c03_air_dried_and_surface_wet_are_mutually_exclusive(fa_mc, ca_mc):
    """One MC below absorption and one above would offer both conditions.

    Where the two aggregates disagree, the wetter one decides: the batch
    cannot be air-dried if any aggregate is wetter than its absorption, and
    cannot be surface-wet if any is drier. Offering both would mean one of
    them always raises.
    """
    available = available_moisture_conditions(
        _moisture_input(fa_mc=fa_mc, ca_mc=ca_mc, fa_abs=1.0, ca_abs=0.5)
    )
    offered = [c for c in ("air_dried", "surface_wet") if available[c][0]]
    assert len(offered) == 1, (
        f"at {fa_mc}/{ca_mc}% moisture the picker offers {offered}; at most "
        "one of the two mutually exclusive conditions may be offered"
    )


def test_c03_at_absorption_both_degenerate_to_ssd_and_are_accepted():
    """MC == absorption is the SSD condition; the engine accepts both."""
    inp = _moisture_input(fa_mc=1.0, ca_mc=0.5, fa_abs=1.0, ca_abs=0.5)
    available = available_moisture_conditions(inp)
    assert available["air_dried"][0] and available["surface_wet"][0]
    result = DOEMixDesign().design(inp)
    for condition in ("air_dried", "surface_wet"):
        assert calculate_doe_trial_batches(
            result, inp, moisture_condition=condition,
        )["batches"]


def test_c03_all_four_conditions_get_a_verdict():
    """Every BS 1881 Part 125 condition must be judged, not omitted."""
    available = available_moisture_conditions(_moisture_input(0.2, 0.1))
    assert set(available) == set(MOISTURE_CONDITIONS)


def test_c03_no_design_record_reports_only_ssd_as_usable():
    """Without moisture data there is nothing to reason from."""
    available = available_moisture_conditions(None)
    assert available["ssd"] == (True, "")
    for condition in ("oven_dry", "air_dried", "surface_wet"):
        assert available[condition][0] is False
        assert "design input" in available[condition][1]


@pytest.mark.parametrize("fa_mc,ca_mc", [(0.2, 0.1), (3.0, 2.0), (1.0, 0.5)])
def test_c03_gating_matches_what_the_engine_actually_accepts(fa_mc, ca_mc):
    """A condition the picker offers must not then raise in the engine.

    This is the defect itself: the picker used to offer a condition the
    schedule then rejected, so the test runs the offered ones and expects a
    schedule rather than a ValueError.
    """
    inp = _moisture_input(fa_mc=fa_mc, ca_mc=ca_mc)
    result = DOEMixDesign().design(inp)
    offered = [
        c for c in MOISTURE_CONDITIONS
        if available_moisture_conditions(inp)[c][0]
    ]
    assert offered, f"no condition offered at {fa_mc}/{ca_mc}% moisture"
    for condition in offered:
        schedule = calculate_doe_trial_batches(
            result, inp, moisture_condition=condition,
        )
        assert schedule["batches"], f"{condition} produced no batches"


def test_c03_a_refused_condition_still_raises_with_both_numbers_named():
    """The refusal must be actionable, not a bare boolean."""
    inp = _moisture_input(3.0, 2.0)
    result = DOEMixDesign().design(inp)
    with pytest.raises(ValueError) as excinfo:
        calculate_doe_trial_batches(result, inp, moisture_condition="air_dried")
    message = str(excinfo.value)
    assert "3.0" in message and "2.0" in message, (
        f"error does not name the actual moisture contents: {message}"
    )
    assert "surface-wet" in message


# -------------------------------------------------------------------- GUI


@pytest.fixture()
def qt():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_c03_dialog_disables_unavailable_conditions_and_keeps_a_usable_one(
    qt, monkeypatch, tmp_path
):
    """The picker must never leave an unusable selection in place."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PyQt6.QtCore import Qt

    from app.widgets.doe_trial_mixes_dialog import DOETrialMixesDialog

    for fa_mc, ca_mc, offered, blocked in (
        (0.2, 0.1, "air_dried", "surface_wet"),
        (3.0, 2.0, "surface_wet", "air_dried"),
    ):
        inp = _moisture_input(fa_mc=fa_mc, ca_mc=ca_mc)
        dialog = DOETrialMixesDialog(DOEMixDesign().design(inp), inp)
        try:
            blocked_index = dialog._moisture_combo.findData(blocked)
            assert blocked_index >= 0, f"{blocked} missing from the picker"
            # Selecting it the way a user would is impossible once disabled,
            # so set it with signals blocked: this exercises the gating, not
            # the schedule's modal error path.
            dialog._moisture_combo.blockSignals(True)
            try:
                dialog._moisture_combo.setCurrentIndex(blocked_index)
            finally:
                dialog._moisture_combo.blockSignals(False)
            dialog._refresh_moisture_choices()

            model = dialog._moisture_combo.model()
            states = {
                dialog._moisture_combo.itemData(i): model.item(i).isEnabled()
                for i in range(dialog._moisture_combo.count())
            }
            assert states[offered] is True
            assert states[blocked] is False
            # A disabled condition must not remain the current selection.
            # The fallback is the first *enabled* condition (the SSD design
            # basis), not necessarily the other half of the excluded pair.
            current = dialog._moisture_combo.currentData()
            assert current != blocked, (
                f"picker left {blocked!r} selected at {fa_mc}/{ca_mc}% moisture"
            )
            assert states[current] is True, (
                f"picker moved to unusable {current!r} at {fa_mc}/{ca_mc}% moisture"
            )
            tip = model.item(blocked_index).data(Qt.ItemDataRole.ToolTipRole)
            assert tip, "disabled condition has no tooltip explaining why"
        finally:
            dialog.close()
            dialog.deleteLater()
            qt.processEvents()
