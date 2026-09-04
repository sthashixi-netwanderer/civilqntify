"""BRE 331:1997 Figure 6 — chart-panel readout and workability ranges.

Figure 6 is organised as 3 NMSA pages (10/20/40 mm, §1.2.5) × 4
workability columns (Table 3 ranges), each panel carrying one curve per
% passing 600 µm (15/40/60/80/100). These tests pin:

- the standard's own worked-example anchor points (§7.1, §7.2, §7.3,
  §8.6, §9.4) through the bilinear panel readout;
- exactness at digitised grid nodes;
- slump/Vebe → class boundary mapping (endpoints belong to the lower
  class, matching the printed overlapping ranges);
- chart monotonicity (finer sand → less fines; higher w/c or
  workability → more fines; larger NMSA → fewer fines);
- input clamping to the chart frame;
- the DOE workability-range selector UI sync.
"""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from concrete_mix.codes.tables.doe_tables import (
    figure6_panel_label,
    get_fine_aggregate_proportion as fine_prop,
    resolve_workability_class,
    slump_to_workability_class,
    vebe_to_workability_class,
    workability_class_label,
)


def prop(nmsa, wc, p600, cls):
    return fine_prop(nmsa, wc, p600, workability_class=cls)


class TestFigure6WorkedExamples:
    """Standard's own examples must read back off the chart panels.

    Tolerances reflect chart-reading precision: the digitised panels
    reproduce each example within ~1 pp of the value quoted in the text.
    """

    def test_example_1_unrestricted(self):
        # §7.1: 20 mm, slump 10–30 (class 1), wc 0.47, 70% → 27%
        assert prop(20, 0.47, 70.0, 1) == pytest.approx(27.7, abs=0.05)

    def test_example_2_max_wc(self):
        # §7.2: 40 mm, slump 30–60 (class 2), wc 0.50, 90% → 22%
        assert prop(40, 0.50, 90.0, 2) == pytest.approx(21.8, abs=0.05)

    def test_example_3_min_cement(self):
        # §7.3: 40 mm, slump 0–10 (class 0), wc ~0.40, 90% → 15–18%
        assert 15.0 <= prop(40, 0.40, 90.0, 0) <= 18.0

    def test_section_8_air_entrained(self):
        # §8.6 Table 8: 20 mm, slump 10–30 (class 1), wc ~0.46, 50% → ~32%
        assert prop(20, 0.455, 50.0, 1) == pytest.approx(32.9, abs=0.3)

    def test_section_9_pfa(self):
        # §9.4: 20 mm, class 1, W/(C+F) ~0.36, 70% → ~26%
        assert prop(20, 0.3625, 70.0, 1) == pytest.approx(25.8, abs=0.3)


class TestFigure6GridExactness:
    def test_grid_nodes_read_back(self):
        # Exact nodes of the printed grid (w/c 0.2/0.4/0.6/0.8 × curves
        # 15/40/60/80/100) must read back exactly.
        assert prop(40, 0.8, 100.0, 0) == pytest.approx(21.0)
        assert prop(20, 0.6, 80.0, 2) == pytest.approx(29.0)
        assert prop(10, 0.2, 100.0, 0) == pytest.approx(23.0)
        assert prop(10, 0.8, 15.0, 3) == pytest.approx(80.0)
        assert prop(40, 0.2, 15.0, 0) == pytest.approx(28.0)

    def test_interpolated_wc_gridpoints(self):
        # Midpoints between grid columns (0.2 spacing).
        # 10 mm, class 3, p600 60 at w/c 0.5: (45+50)/2 = 47.5
        assert prop(10, 0.5, 60.0, 3) == pytest.approx(47.5)
        # 20 mm, class 0, p600 15 at w/c 0.3: (35+41)/2 = 38.0
        assert prop(20, 0.3, 15.0, 0) == pytest.approx(38.0)

    def test_mid_curve_interpolation(self):
        # 20 mm, class 1, wc 0.5, p600 70: between the 60/80 curves and
        # the 0.4/0.6 columns → 26.5 + 0.5×(30.0−26.5) = 28.25 → 28.2 (1 dp)
        assert prop(20, 0.5, 70.0, 1) == pytest.approx(28.25, abs=0.06)

    def test_off_grid_wc_interpolates_between_columns(self):
        # 20 mm, class 1, wc 0.47 (§7.1 read): α=0.35 between 0.4/0.6
        assert prop(20, 0.47, 70.0, 1) == pytest.approx(27.7, abs=0.05)


class TestWorkabilityDerivation:
    def test_slump_and_vebe_agree_with_explicit_class(self):
        via_slump = fine_prop(20, 0.5, 70.0, slump_mm=20.0)
        via_vebe = fine_prop(20, 0.5, 70.0, vebe_s=8.0)
        via_class = prop(20, 0.5, 70.0, 1)
        assert via_slump == via_vebe == via_class

    def test_vebe_preferred_over_slump(self):
        # Vebe 2 s (class 3) wins over slump 5 mm (class 0)
        assert fine_prop(20, 0.5, 70.0, slump_mm=5.0, vebe_s=2.0) == prop(
            20, 0.5, 70.0, 3
        )

    def test_missing_basis_raises(self):
        with pytest.raises(ValueError, match="slump_mm or vebe_s"):
            fine_prop(20, 0.5, 70.0)

    def test_bad_class_raises(self):
        with pytest.raises(ValueError, match="outside \\[0, 3\\]"):
            prop(20, 0.5, 70.0, 4)


class TestResolveWorkabilityClass:
    """Slump/Vebe → chart column, with the disagreement cross-check."""

    def test_slump_only(self):
        assert resolve_workability_class(45.0, None) == (2, "")

    def test_vebe_only(self):
        assert resolve_workability_class(None, 4.0) == (2, "")

    def test_both_agree(self):
        # Slump 45 mm and Vebe 4 s both select class 2 — no warning.
        assert resolve_workability_class(45.0, 4.0) == (2, "")

    def test_disagreement_vebe_governs_with_warning(self):
        # Slump 50 mm → class 2; Vebe 8 s → class 1. Vebe governs.
        cls, warning = resolve_workability_class(50.0, 8.0)
        assert cls == 1
        assert "Vebe governs" in warning
        assert "30–60" in warning and "6–12" in warning

    def test_neither_raises(self):
        with pytest.raises(ValueError, match="slump_mm or vebe_s"):
            resolve_workability_class(None, None)

    def test_boundary_pair_agree(self):
        # Slump 10 mm (lower rule → class 0) with Vebe 13 s (class 0).
        assert resolve_workability_class(10.0, 13.0) == (0, "")


class TestWorkabilityBoundaries:
    """Endpoints belong to the lower printed range (columns read L→R)."""

    def test_slump_boundaries(self):
        assert slump_to_workability_class(0.0) == 0
        assert slump_to_workability_class(10.0) == 0
        assert slump_to_workability_class(10.1) == 1
        assert slump_to_workability_class(30.0) == 1
        assert slump_to_workability_class(30.1) == 2
        assert slump_to_workability_class(60.0) == 2
        assert slump_to_workability_class(60.1) == 3
        assert slump_to_workability_class(180.0) == 3

    def test_vebe_boundaries(self):
        assert vebe_to_workability_class(15.0) == 0
        assert vebe_to_workability_class(12.1) == 0
        assert vebe_to_workability_class(12.0) == 1
        assert vebe_to_workability_class(6.1) == 1
        assert vebe_to_workability_class(6.0) == 2
        assert vebe_to_workability_class(3.1) == 2
        assert vebe_to_workability_class(3.0) == 3


class TestFigure6Monotonicity:
    def test_higher_wc_needs_more_fines(self):
        assert prop(20, 0.3, 60.0, 1) < prop(20, 0.8, 60.0, 1)

    def test_finer_sand_needs_fewer_fines(self):
        assert prop(20, 0.5, 15.0, 1) > prop(20, 0.5, 100.0, 1)

    def test_higher_workability_needs_more_fines(self):
        assert prop(20, 0.5, 60.0, 0) < prop(20, 0.5, 60.0, 3)

    def test_larger_nmsa_needs_fewer_fines(self):
        assert prop(10, 0.5, 60.0, 1) > prop(20, 0.5, 60.0, 1) > prop(
            40, 0.5, 60.0, 1
        )


class TestFigure6Clamping:
    def test_wc_clamped_to_chart_frame(self):
        assert prop(20, 0.9, 60.0, 1) == prop(20, 0.8, 60.0, 1)
        # Printed grid starts at w/c 0.2 — lower inputs read on 0.2.
        assert prop(20, 0.1, 60.0, 1) == prop(20, 0.2, 60.0, 1)

    def test_p600_clamped_to_outer_curves(self):
        assert prop(20, 0.5, 120.0, 1) == prop(20, 0.5, 100.0, 1)
        assert prop(20, 0.5, 5.0, 1) == prop(20, 0.5, 15.0, 1)


class TestFigure6Labels:
    def test_panel_label(self):
        assert figure6_panel_label(20, 1) == "20 mm · Slump 10–30 mm / Vebe 6–12 s"

    def test_class_label(self):
        assert workability_class_label(0) == "Slump 0–10 mm (Vebe >12 s)"


class TestFigure6EngineStep:
    def test_step_11_cites_chart_panel(self):
        from concrete_mix.codes.doe import DOEMixDesign
        from concrete_mix.models.materials import (
            Cement,
            CementType,
            CoarseAggregate,
            FineAggregate,
        )
        from concrete_mix.models.mix_input import MixDesignInput

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(
                nominal_max_size_mm=20, specific_gravity=2.6
            ),
            fine_aggregate=FineAggregate(
                specific_gravity=2.6, pct_passing_600um=70.0
            ),
            has_production_data=False,
            defective_percent=2.5,
            w_c_ratio=0.55,
        )
        object.__setattr__(inp, "min_cement_kg", 290.0)
        result = DOEMixDesign().design(inp)
        s11 = next(s for s in result.steps if s.step_number == 11)
        assert "20 mm" in s11.formula
        assert "10–30" in s11.formula
        assert abs(s11.result - 27.7) < 0.3


class TestEngineP600Required:
    """% passing 600 µm is a required DOE input (Figure 6, Item 5.1)."""

    def test_missing_p600_raises(self):
        from concrete_mix.codes.doe import DOEMixDesign
        from concrete_mix.models.materials import (
            Cement,
            CementType,
            CoarseAggregate,
            FineAggregate,
        )
        from concrete_mix.models.mix_input import MixDesignInput

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=20.0,
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20),
            fine_aggregate=FineAggregate(pct_passing_600um=None),
        )
        with pytest.raises(ValueError, match="600 µm"):
            DOEMixDesign().design(inp)


class TestEngineWorkabilityConflict:
    """Slump/Vebe disagreement surfaces as a warning, Vebe governs."""

    def test_conflict_warning_in_result(self):
        from concrete_mix.codes.doe import DOEMixDesign
        from concrete_mix.models.materials import (
            Cement,
            CementType,
            CoarseAggregate,
            FineAggregate,
        )
        from concrete_mix.models.mix_input import MixDesignInput

        inp = MixDesignInput(
            code="doe",
            target_strength_mpa=30.0,
            slump_mm=50.0,  # class 2 …
            cement=Cement(type=CementType.OPC_43),
            coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20),
            fine_aggregate=FineAggregate(pct_passing_600um=70.0),
            vebe_s=8.0,  # … vs class 1
        )
        result = DOEMixDesign().design(inp)
        assert any("Vebe governs" in w for w in result.warnings)
        s11 = next(s for s in result.steps if s.step_number == 11)
        # Class 1 panel was read, not the slump's class 2 panel.
        assert "10–30" in s11.formula


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def doe_tab(qapp):
    from app.widgets.concrete_tab import ConcreteMixTab

    tab = ConcreteMixTab()
    tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
    return tab


class TestDOEWorkabilitySelectorUI:
    def test_selector_visible_only_for_doe(self, qapp):
        from app.widgets.concrete_tab import ConcreteMixTab

        tab = ConcreteMixTab()
        assert tab.doe_workability_combo.isHidden() is True
        tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
        assert tab.doe_workability_combo.isHidden() is False

    def test_range_pick_sets_specified_slump(self, doe_tab):
        doe_tab.doe_workability_combo.setCurrentIndex(
            doe_tab.doe_workability_combo.findData(2)
        )
        assert doe_tab.slump_spin.value() == pytest.approx(45.0)
        assert doe_tab.vebe_spin.value() == 0.0

    def test_slump_edit_moves_range(self, doe_tab):
        # set_display_value simulates typing (UnitSpinBox.setValue is
        # silent by design — programmatic metric sets block signals).
        doe_tab.slump_spin.set_display_value(120.0)
        assert doe_tab.doe_workability_combo.currentData() == 3
        doe_tab.slump_spin.set_display_value(5.0)
        assert doe_tab.doe_workability_combo.currentData() == 0

    def test_history_restore_syncs_range(self, doe_tab):
        """Silent UnitSpinBox.setValue (history path) still syncs."""
        from concrete_mix.models.materials import (
            Cement,
            CementType,
            CoarseAggregate,
            FineAggregate,
        )
        from concrete_mix.models.mix_input import MixDesignInput

        doe_tab.apply_mix_input(
            MixDesignInput(
                code="doe",
                target_strength_mpa=30.0,
                slump_mm=45.0,
                cement=Cement(type=CementType.OPC_43),
                coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20),
                fine_aggregate=FineAggregate(pct_passing_600um=70.0),
            )
        )
        assert doe_tab.doe_workability_combo.currentData() == 2

    def test_history_restore_with_vebe_repoints_slump(self, doe_tab):
        """A Vebe-governed saved design restores with its governing slump."""
        from concrete_mix.models.materials import (
            Cement,
            CementType,
            CoarseAggregate,
            FineAggregate,
        )
        from concrete_mix.models.mix_input import MixDesignInput

        doe_tab.apply_mix_input(
            MixDesignInput(
                code="doe",
                target_strength_mpa=30.0,
                slump_mm=75.0,  # stale user slump saved alongside Vebe
                cement=Cement(type=CementType.OPC_43),
                coarse_aggregate=CoarseAggregate(nominal_max_size_mm=20),
                fine_aggregate=FineAggregate(pct_passing_600um=70.0),
                vebe_s=8.0,  # class 1 governs → rep slump 20 mm
            )
        )
        assert doe_tab.vebe_spin.value() == pytest.approx(8.0)
        assert doe_tab.slump_spin.value() == pytest.approx(20.0)
        assert doe_tab.doe_workability_combo.currentData() == 1

    def test_vebe_governs_range_and_water(self, doe_tab):
        doe_tab.vebe_spin.setValue(8.0)
        assert doe_tab.doe_workability_combo.currentData() == 1
        assert "10–30" in doe_tab.water_content_label.text()

    def test_vebe_input_repoints_slump(self, doe_tab):
        """Entering a Vebe time updates the slump to the governing value.

        The design is class-based, so the slump field must reflect the
        representative slump of the Vebe-selected class (the slump the
        design uses), not a stale user value.
        """
        doe_tab.slump_spin.setValue(75.0)  # class 3
        doe_tab.vebe_spin.setValue(8.0)  # class 1 governs
        assert doe_tab.slump_spin.value() == pytest.approx(20.0)
        # Vebe = 0 means "use slump" and must not touch the field.
        doe_tab.vebe_spin.setValue(0.0)
        assert doe_tab.slump_spin.value() == pytest.approx(20.0)

    def test_vebe_conflict_note_in_water_label(self, doe_tab):
        # Vebe governs the class; a manual slump edit that lands in a
        # different class is flagged in the live water readout.
        # (set_display_value simulates typing — UnitSpinBox.setValue is
        # silent by design.)
        doe_tab.vebe_spin.setValue(8.0)  # class 1, slump auto → 20
        doe_tab.slump_spin.set_display_value(75.0)  # user insists on class 3
        assert "disagree" in doe_tab.water_content_label.text()

    def test_range_labels_carry_table3_water(self, doe_tab):
        labels = [
            doe_tab.doe_workability_combo.itemText(i)
            for i in range(doe_tab.doe_workability_combo.count())
        ]
        assert len(labels) == 4
        assert all("kg/m³" in label for label in labels)


class TestFigure6PreviewUI:
    """Live fines readout under the % passing 600 µm field."""

    def test_hidden_for_non_doe(self, qapp):
        from app.widgets.concrete_tab import ConcreteMixTab

        tab = ConcreteMixTab()
        tab.code_combo.setCurrentIndex(tab.code_combo.findData("is10262"))
        assert tab._lbl_fig6_prop.isHidden() is True
        assert tab.fig6_prop_label.isHidden() is True
        tab.code_combo.setCurrentIndex(tab.code_combo.findData("doe"))
        assert tab.fig6_prop_label.isHidden() is False

    def test_p600_entry_updates_readout(self, doe_tab):
        """Entering the 600 µm passing re-reads Figure 6 live.

        The readout must equal design step 11 for the same form state
        and move when the sand grading changes.
        """
        from concrete_mix import design_mix_simple

        doe_tab.strength_spin.set_display_value(30.0)
        doe_tab.slump_spin.set_display_value(20.0)  # class 1 chart
        doe_tab.pct_passing_600um_spin.setValue(70.0)
        text = doe_tab.fig6_prop_label.text()
        assert "10–30" in text  # slump-selected chart column
        r = design_mix_simple(**doe_tab._build_kwargs())
        s11 = next(s for s in r.steps if s.step_number == 11)
        assert text.startswith(f"{s11.result:.1f} %")
        # Coarser sand (30% passing) must lower the fines proportion.
        doe_tab.pct_passing_600um_spin.setValue(30.0)
        assert doe_tab.fig6_prop_label.text() != text

    def test_vebe_switches_chart_column(self, doe_tab):
        doe_tab.pct_passing_600um_spin.setValue(70.0)
        doe_tab.slump_spin.set_display_value(20.0)
        assert "10–30" in doe_tab.fig6_prop_label.text()
        doe_tab.vebe_spin.setValue(2.0)  # class 3 chart governs
        assert "60–180" in doe_tab.fig6_prop_label.text()
