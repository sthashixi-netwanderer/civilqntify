# DOE (BRE 331:1997) Trial Mixes — Design

Date: 2026-09-05
Status: Approved for implementation (user directive: "just implement")

## Purpose

Implement BRE 331:1997 §6 trial mixes for the DOE mix design code: a trial
batch schedule generator (§6.1) plus an interactive trial-feedback workbook
(§6.3) that computes workability, density, and strength adjustments, with
trial records persisted to history.

Scope decisions (user-selected):
- Interactive trial feedback workbook + saved trial history (not a
  batch-schedule-only dialog).
- Batch schedule = designed mix + optional w/c variants at the same water
  content (BRE 331:1997 §6 intro).
- Architecture mirrors the existing IS 10262 trial mixes pattern
  (`calculate_is10262_trial_mixes` + `ISTrialMixesDialog`).

## 1. Calculation engine — `concrete_mix/codes/doe_trial.py`

Pure, Qt-free functions.

### calculate_doe_trial_batches(result, inp, volume_m3=0.05, wc_step=0.05, include_variants=False)

- Scales per-m³ design constituents to the trial volume (§6.1). Reproduces
  the §7.1 example: 0.05 m³ → cement 17.0, water 8.0, fine 25.7,
  coarse 69.2 kg (SSD).
- Optional ±w/c variant batches at the same free-water content (§6 intro):
  for each variant, re-run Stages 3–5 — C3 cement = W ÷ w/c rounded to the
  nearest 5 kg; C4 total aggregate = design wet density − C − W; C5 fine
  proportion re-read from Figure 6 at the variant ratio; min/max cement
  limits re-checked.
- Moisture-condition batching (§6.1, BS 1881 Part 125):
  - SSD (design basis) — batch as calculated.
  - Oven-dry / air-dry — aggregate batch mass × 100/(100 + A) where A is
    absorption to SSD; mixing water increased by the absorbed mass
    (§7.1: fine 25.7→25.2 kg, coarse 69.2→68.5 kg, water +1.2 kg).
  - Surface-wet — free water subtracted from added water.
  - Pre-soak note: dry aggregates mixed with ~half the water before cement
    (BS 1881 Part 125).
- Single-size coarse aggregate split (§5.5) scaled when the design has one.

### evaluate_doe_trial(result, inp, measurements)

- **Workability (§6.3.1):** measured slump/Vebe vs designed workability
  class; Table 3 water guidance for a ±1 class change; withhold-10% water
  guidance.
- **Density (§6.3.2):** factor = measured ÷ assumed density; corrected unit
  proportions = design constituents × factor ("actual masses per m³ in the
  trial mix").
- **Strength (§6.3.3, Figure 7):**
  - A = Table 2 reference strength at w/c 0.5 (cement class, aggregate
    type, test age).
  - B = designed w/c; B′ = actual w/c used (defaults to B; W_actual ÷
    C_actual when the trial water was adjusted).
  - C = measured mean cube strength.
  - D = new w/c for the target mean strength, by inverting the app's
    Figure 4 model (`wc_ratio_from_strength`, log-quadratic) through the
    trial point (B′, C) — the parallel-curve shift the standard describes.
  - Durability max-w/c cap re-checked on D.
- **Verdict (documented app policy — the standard gives no numeric
  threshold):** |D − B′| ≤ 0.05 → minor adjustment: revised proportions may
  go straight to production; > 0.05 → make a second trial mix at w/c = D
  with batches recalculated on the measured density (§6.3.3).
  The minor-adjustment case also emits recalculated production proportions
  via the C3/C4/C5 chain (round-to-5, measured density).
- pfa/ggbs designs: evaluation runs on the equivalent ratio; w/c variant
  batches are limited to plain mixes (documented limitation).

## 2. UI — `app/widgets/doe_trial_mixes_dialog.py`

`DOETrialMixesDialog(result, inp, parent)` mirroring `ISTrialMixesDialog`:

1. Batch schedule group: trial volume spin (default 0.05 m³), variants
   toggle + w/c step spin; SSD / oven-dry condition selector; table of
   per-m³ and trial-volume masses per batch; CA single-size split shown
   when present; absorption water shown for dry batching.
2. Trial feedback group (§6.3): inputs — actual water added (pre-filled
   with design water), measured slump or Vebe, measured fresh density, mean
   cube strength + test age (7/28 d). "Calculate adjustments" renders the
   workability assessment, density-corrected proportions, the A/B/B′/C/D
   chain, verdict banner, and recalculated production proportions.
3. Tests & records checklist (§6.2): BS 1881 Parts 102/104/107/108/111/116
   plus what to record.
4. Buttons: Save Trial Record, Export CSV, Copy to Clipboard, Close.

ResultPanel: parallel `_doe_trial_frame` shown only for DOE results with a
§6 summary prompt and "View DOE Trial Mixes" button → `_on_view_doe_trials`.

## 3. History

- New `tab_type = "doe_trial"`: `HistoryDB.save_doe_trial(trial_input,
  trial_result, name, parent_id)`; `parent_id` links the trial to its
  design record. Serializers add doe_trial helpers.
- History tab registers the type with a detail view showing measurements,
  the A/B/B′/C/D chain, adjusted proportions, and the parent link.

## 4. Tests

- `tests/test_doe_trial.py`: §7.1 batch quantities; §7.1 oven-dry example;
  variants keep water constant; density factor; Figure 7 D computation
  (synthetic trials); verdict thresholds; limit re-checks.
- `tests/test_doe_trial_ui.py`: offscreen Qt, mirroring
  `test_is_trial_mixes_ui.py` — DOE frame shown only for DOE results,
  dialog populates, save writes a chained `doe_trial` record.

All formulas carry BRE 331:1997 clause citations; the 0.05 w/c verdict
threshold and the Figure 4 inversion interpretation are documented app
policy per AGENTS.md.
