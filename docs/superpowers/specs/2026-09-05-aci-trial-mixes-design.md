# ACI PRC-211.1-22 Trial Batching — Design

Date: 2026-09-05
Status: Approved (user approved plan + Appendix A.5 trial series inclusion)

## Purpose

Implement ACI PRC-211.1-22 trial batching for the ACI 211.1 design code,
mirroring the DOE trial-mixes workbook pattern: a §5.3.9 batch weight
summary, the §5.3.10 post-trial adjustment loop, and the Appendix A.5
trial series, with records persisted to history.

## Standard basis (extracted reference: `31-ACI 211.1-22.md`)

- **§4.1 / Chapter 8** — trial batching demonstrates the required
  properties; iterate adjust → re-trial until within tolerance (ASTM C94
  slump/air tolerances where unspecified). Procedure per ASTM C192;
  three-point curve establishes the material-specific w/cm–strength
  relationship.
- **§5.3.9 / Table 5.3.9.1** — batch weight summary:
  `w_batched = w_SSD × (1 + MC%) / (1 + A%)`; free water = batched −
  SSD-equivalent; water to batch = mixing water − free water; total
  batch weight equals total mixture weight.
- **§5.3.10** — Adjustment 1 (re-estimate water = net water ÷ yield, then
  ±10 lb/yd³ per inch of slump; WRA note), Adjustment 2 (air: ∓5 lb/yd³
  per 1 %, re-estimate dosage), Adjustment 3 (cement efficiency psi per
  lb/yd³; Δcement = (f'cr − measured)/eff, w/cm held, sand offset),
  §5.3.10.4 (recalculate next trial from Step 5; coarse aggregate held
  unless workability requires Table 5.3.6 change).
- **Appendix A.5** — trial batch series (mixtures above/below design
  cement content at constant water).
- **§9.2.9** — the worked Example 1 post-trial computation: test ground
  truth (free water 1.07/2.55 lb/ft³, net water 12.12 lb/ft³ = 327
  lb/yd³, gravimetric air 1.9 %, next trial 342/552/1927/1100 lb/yd³).
- **Table 8** (Kosmatka & Wilson 2016) — qualitative adjustment guide;
  the extracted arrow grid is garbled, so the app surfaces the property
  list and the Chapter 8 caution, not invented directions.

## App policy (documented deviations)

- Relative yield per ASTM C138: Ry = theoretical ÷ measured density
  (tolerance 0.98–1.02). §9.2.9.2 prints the reciprocal convention;
  both give Ry = 1.0095 for the example.
- Adjustment 1 divides the net trial water by the measured yield;
  §9.2.9 treats the 1 ft³ trial as exactly 1 ft³, so the workbook's
  re-estimated water differs from the printed 342 lb/yd³ by the ~0.9 %
  yield correction.
- When both slump and strength adjustments fire, the next-trial
  cementitious content is the Step-5 value (water ÷ w/cm) plus the
  Adjustment-3 cement delta; the standard gives no combination rule.
- The next trial uses the measured air content when available (direct
  measurement, else gravimetric from the density measurement), matching
  §9.2.9.5's "using measured air from trial".

## Implementation

1. **`concrete_mix/codes/aci_trial.py`** (pure functions):
   `calculate_aci_trial_batches` (Table 5.3.9.1 summary, optional A.5
   series at constant water), `evaluate_aci_trial` (free-water reversal,
   Ry + gravimetric air, Adjustments 1–3, §5.3.10.4 next-trial
   proportions), `TEST_CHECKLIST` (ASTM C192/C1064/C143/C138/C173/C231/
   C31), `TABLE_8_GUIDANCE`.
2. **`app/widgets/aci_trial_mixes_dialog.py`** — `ACITrialMixesDialog`:
   schedule table (design + series rows), §5.3.10 feedback inputs and
   rich-text adjustment rendering, ASTM checklist, save/CSV/copy.
3. **ResultPanel** — ACI trial prompt frame for ACI results with the
   workbook opener; reuses `_design_calc_id` for parent chaining.
4. **History** — `aci_trial` record type (`HistoryDB.save_aci_trial`,
   serializer, filter/summary/detail views; view-only like `doe_trial`).
5. **Tests** — `tests/test_aci_trial.py` (§9.2.9 parity: batching
   weights, free-water reversal, Ry/air, Adjustment 1 slump correction,
   cement efficiency ≈ 80.7 lb/yd³, next-trial proportions and
   absolute-volume closure, A.5 series water constancy) and
   `tests/test_aci_trial_ui.py` (frame gating per code, dialog
   population, evaluation rendering, chained record save).

The existing "Trial Check (optional) — ACI §5.3.10" group on the design
form remains: it feeds design-time steps 10.1–10.4, while the workbook
implements the post-trial workflow at batch scale.
