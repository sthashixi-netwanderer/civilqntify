# CivilQntify - Integration & Correctness Feedback Report

**Date:** 2026-10-14
**Scope:** whole-project audit - engines, GUI, quantification, costing, persistence,
exports, CLI, CI, documentation.
**Method:** every claim below was reproduced by executing code. Nothing is reported
from reading alone. Areas that were checked and found correct are listed in section 5.

---

## 1. Verdict

The engineering *inside* each module is good. The standards implementations are
careful, the absolute-volume and moisture arithmetic is right, the persistence layer
round-trips cleanly, CI is properly configured, and the test suite is genuinely
strong. Roughly 95% of what the validation report asked for was fixed correctly, and
I confirmed by mutation testing that the new tests actually fail when the fixes are
reverted - they are real regression tests, not oracles rewritten to match the code.

The problem is **not** the fixes. The problem is that the fixes were made and verified
**module by module, in isolation**, and nobody then checked whether the modules still
fit together, whether the guards added to fix defect *N* break legitimate inputs, or
whether the documentation still matches the software. Five of the seven findings below
are integration failures, not calculation failures.

Two of them are regressions introduced *by* the remediation itself.

---

## 2. Critical findings

### C1 - The application does not survive a normal commit. **Build-breaking.**

`concrete_mix/export/batching.py` is **untracked**, but four tracked modules import it:

```
concrete_mix/export/json_export.py:8    from concrete_mix.export.batching import batching_schedule
concrete_mix/export/text_report.py:8    from concrete_mix.export.batching import ...
concrete_mix/export/pdf_report.py:30    from concrete_mix.export.batching import ...
concrete_mix/export/csv_export.py:9     from concrete_mix.export.batching import batching_schedule
```

The working tree has 61 modified tracked files plus 9 untracked paths. `git commit -am`
- the ordinary reflex - captures all 61 and skips all 9.

Reproduced end to end:

```
$ # overlay the 61 edits onto a clean HEAD checkout, then 'git add -u'
files captured by 'commit -am': 61
batching.py captured?           0

$ # clone that commit, as CI would
batching.py in clone? ABSENT
$ python -c "import concrete_mix"
ModuleNotFoundError: No module named 'concrete_mix.export.batching'
```

`import concrete_mix` - the root package - raises. Every export format is dead. The
1121 passing tests pass only because the file happens to be sitting on this disk.

**Fix:** `git add concrete_mix/export/batching.py material_quantify/resources/` before
committing anything, and add a guard so it cannot recur - e.g. a CI step that runs
`python -c "import concrete_mix, concrete_mix.export.pdf_report, material_quantify"`
on a clean checkout (the existing `compileall` step does not follow imports).

### C2 - ACI trial evaluation is blocked on ordinary first-trial results. **Regression.**

`concrete_mix/codes/aci_trial.py:178` now raises instead of clamping:

```python
if vol > 1.0:
    raise ValueError("Trial constituents exceed 1 m3 before fine aggregate fill")
v_fine = 1.0 - vol          # HEAD had: v_fine = max(0.0, 1.0 - vol)
```

The volume overshoot comes from 5.3.10.3's linear cement-efficiency extrapolation,
which blows up when a trial cube lands well below target. Reproduced:

```
f'c=40, cube 28 (72% of f'm)               ValueError: Trial constituents exceed 1 m3 ...
f'c=45, NO cube strength, low density      ValueError: Trial constituents exceed 1 m3 ...
f'c=30, cube 24                            OK
```

The first case is the *entire point* of the dialog - run a trial, it comes in weak,
increase the cement. The user clicks "Evaluate" and gets a modal warning about batch
volumes that has nothing to do with their problem. `ACITrialMixesDialog._on_evaluate`
catches it (`aci_trial_mixes_dialog.py:404`) so nothing crashes, but no 5.3.10
adjustment is produced.

The message is also wrong about the cause, which makes it worse than a crash: it
describes constituent volumes when the defect is an unbounded linear extrapolation.

### C3 - The DOE trial dialog offers a moisture condition the app cannot honour. **Regression.**

`concrete_mix/codes/doe_trial.py:379`:

```python
else:  # surface_wet - condition (d)
    if fa_mc < fa_abs or ca_mc < ca_abs:
        raise ValueError("Surface-wet moisture is below absorption; use air_dried")
```

`FineAggregate.absorption_percent` defaults to 1.0, `CoarseAggregate` to 0.5, and
`moisture_content_percent` defaults to 0.0 in both - the app's own defaults. The dialog
adds "Surface-wet / saturated" as an unconditioned combo item
(`app/widgets/doe_trial_mixes_dialog.py:180`). Reproduced:

```
default FA: absorption 1.0  moisture 0.0
default CA: absorption 0.5  moisture 0.0
  air_dried    OK
  surface_wet  ValueError: Surface-wet moisture is below absorption; use air_dried
```

The user picks a documented BS 1881 Part 125 condition from a drop-down the app itself
populated, and is told off. The remedy - raise the moisture field above absorption - is
not reachable from the message and not surfaced by the dialog.

### C4 - The design -> quantification handoff is lossy, and silently so.

`MixDesignResult` carries three pieces of code-mandated information that
`MixDesignTransferData.from_mix_design_result()` (`material_quantify/models/transfer_data.py:63`)
does not copy. Two are **structural breakdowns**, not labels:

| Computed by the engine | Carried into the bill? |
|---|---|
| `scm_kg` (+ SCM *identity*) | mass only - `scm_type` never set, falls back to `"SCM (unspecified)"` |
| `ca_split_kg` (BRE 5.5 single-size split) | no - dropped entirely |
| `admixture_type`, `admixture_dosage_percent`, `water_reduction_percent` | no - `admixture_kg` only |

**The DOE coarse-aggregate split.** The engine computes it correctly and the result
panel shows it:

```
DESIGN    ca_split_kg = {'10 mm': 435, '20 mm': 875.0}   total CA = 1310.0
          sum(split) == total: True
INVOICE   'Coarse Aggregate' qty=8.43 m3 - a single undifferentiated line
```

A site supervisor cannot order 10 mm and 20 mm stone separately from this bill. The
split BRE 5.5 requires is computed, displayed, and then thrown away one layer later.

**The SCM type.** `app/main.py:239` papers over the gap for the one GUI path:

```python
transfer.scm_type = params.get("scm_type") or "SCM (unspecified)"
```

The other four callers do not. Same mix, same volume, same price, two different
invoice lines:

```
CONSTRUCTOR      invoice line: SCM  material_type='SCM (unspecified)'  total=GH176.00
GUI-PATCHED      invoice line: SCM  material_type='ggbfs'              total=GH176.00
```

The history layer stores SCM identity correctly (`scms[0].type` round-trips), so the
data exists at both ends - the plumbing between them is simply missing.

**Multi-SCM mixes collapse to one priced line.** The engine accepts a blend; the bill
has a single `total_scm_kg`:

```
scms = 15% fly ash + 10% GGBS
INVOICE: SCM  qty=102.2 kg  unit=GH2.00  total=GH204.40
```

Two materials with materially different market prices are invoiced as one line at one
rate.

**Admixture identity.** Four different admixtures at four dosages:

```
plasticizer       0.5%   -> GH257.09
superplasticizer  1.0%   -> GH514.18
pce               0.8%   -> GH411.59
hrwra             1.2%   -> GH616.76
```

The cost is *right* here (mass x rate), but the bill cannot tell a buyer which
admixture it is ordering, and `admixture_type` never crosses the boundary.

**Why the suite is green anyway.** `tests/test_audit_quantity_cost_fixes.py` builds its
fixtures with `replace(data, scm_type="GGBS")` and its Q05 test drives
`MainWindow._on_send_to_quant` - the one path that applies the patch. Both test the
seam that works and bypass the constructor that doesn't. There is no test anywhere
asserting that `from_mix_design_result` preserves its inputs.

### C5 - The user manual documents the formula the audit corrected away.

`docs/USER_MANUAL.md:490`:

```
| Fine Agg (m3/yd3) | 0-100000, default 0.0, 3 dp | Sand volume. V = mass/(SG x 1000). |
```

Finding Q02 established that sand purchasing volume is `mass / bulk_density`
(ACI 4.7.7.2), not `mass / (SG x 1000)`. `material_quantify/cost.py:67,82,131` was
corrected to the bulk-density basis. The manual still states the old formula, so a
reader following it gets roughly the wrong answer by the ratio of specific gravity to
bulk density.

Two more stale claims in the same document:

- **Section 11.2 Material Prices** lists five default rates and says they are "restored
  by Reset". `app/widgets/cost_estimation_tab.py` now has **six** (`scm_per_kg`,
  line 404) plus the `_scm_priced` checkbox (line 794) that gates it. Neither the
  sixth rate, the checkbox, nor the "PARTIAL TOTAL (SCM UNPRICED)" / INCOMPLETE
  labelling that Q03 added is documented.
- **Line 212** states `Std Deviation s = 0` means "engine default 4.0 MPa". True at the
  GUI default of n=20, false at any n<20, where the applied margin is 8 MPa. The CLI
  gets this right (`main_cli.py:133,147,285`); only the manual is wrong.

Both worked examples on lines 681 and 695 I checked against the engine and they are
**correct** - target 46 / 340 / 160 / 525 / 1375 at n=5, and target 38 / w/c 0.54 /
cement 295 at n=20. Those were not touched.

### C6 - The CLI's own quick-start command does not work.

`README.md:127` tells the reader:

```bash
python main_cli.py --help
```

`main_cli.py` never reads `sys.argv` - no `argparse`, no flag handling anywhere in the
file. Running the documented command drops straight into the interactive standard
selector:

```
$ python main_cli.py --help
  Select design standard [IS 10262 (Indian)]:
    1. ACI 211.1 (American)
```

EOF is handled correctly (exits 1 with a clean message - no infinite loop), so the
underlying CLI is sound. But the first command in the Quick Start misleads every new
user.

### C7 - README test count is off by 4.7x.

`README.md:65` - `tests/  # Pytest unit tests (240+ test cases)`. Actual collection:
**1121**. 881 tests are unmentioned.

---

## 3. The pattern behind C2-C5

Three findings share one cause, and it is worth naming because it will recur.

**The remediation was validated against reproduction cases, not against ordinary use.**
Every guard added while closing the validation report was tested with the exact input
from the report. None was tested with the input a user actually has. The result:

- A guard against physically impossible batch volumes (C2) fires on a completely
  normal weak trial.
- A guard against a negative free-water calculation (C3) fires on the app's default
  aggregates.
- A fix for a mislabelled SCM price (C4) works only on the one path someone remembered
  to patch.

A fix is not finished when its reproduction case passes. It is finished when the
defect it guards against is real *and* the guard cannot fire on valid input. For C2 and
C3 the second half was never checked - and both are reachable from a drop-down or a
single button in the shipped UI.

---

## 4. Secondary observations

- **Stale test comment.** `tests/test_audit_psd_fixes.py:279-283` says the receiver's
  `_on_code_changed` "drops that option" and works around it by re-adding 12.5 mm to
  the combo. I ran the test without the workaround - 12.5 survives as a float
  end-to-end. The branch is dead code and the comment is false; it will mislead the
  next person who touches it.
- **Dead dict.** `report_validation.py:264-268` builds a `common` brief containing
  `nmsa_mm: 20` that is never passed to any of the three `MixDesignInput` calls.
  Harmless today (each call sets 20 itself) and actively misleading tomorrow.
  Note also that `report_validation.py` is a developer harness
  (`scripts/generate_report_validation.py`), not a product feature - the app has no
  cross-method comparison.
- **Sand density not in the cost payload.** `estimate_project_cost` exports
  `fine_aggregate_volume_basis` but not `fine_agg_bulk_density_kg_m3`, and both are
  rendered in the cost PDF (via the warnings list). A reader can see *that* an
  assumption was made but cannot recompute the 4.90 m3. Low severity; worth one key.
- **Stale worktree.** `.kilo/worktrees/cuddly-botany` sits inside the repo at
  `7496ecf`, detached, from 1 Oct. It is untracked and not in `.gitignore`, but it also
  does not appear in `git status`. Harmless today; `git worktree prune` when convenient.

---

## 5. What is genuinely solid

Stated plainly, because most of it is good and none of the above is a reason to doubt
the codebase:

- **The fixes are real.** I mutation-tested three of them in a scratch copy - reverting
  C01's air-correction sign produces 3 failures, removing C04's Line A/B floors produces
  14, reverting P01's invalidation produces 4. The tests fail when the fix is undone,
  which is the only property that matters.
- **Two stale test oracles were found and corrected**, not worked around. Both encoded
  the pre-fix buggy values (305 kg/m3 instead of 345; 440/885 instead of 435/875).
  I verified the old value reappears with `num_test_cubes=30`, proving 305 really was
  the understated BRE margin.
- **1121 tests pass** in 4m01s, no pathological test (slowest 5.7s), and the
  non-termination the original validation report complained about does not reproduce.
- **The GUI diff is clean.** A focused audit of all 61 `app/` changes found zero
  defects: worker revision gating, debounce coalescing, signal blocking with
  `try/finally`, weather-thread teardown (no `QThread: Destroyed while running` under
  load), and history restore all behave correctly.
- **CI is correct** - `QT_QPA_PLATFORM: offscreen` at job scope, an isolated `HOME`,
  and a real frozen-binary launch smoke test, not just a compile check.
- **Persistence is complete and honest.** `MaterialBill` and `MixDesignResult`
  round-trip field-for-field, and legacy records missing new keys deserialize to
  explicit "unverified" markers rather than silently defaulting.
- **No cross-thread SQLite.** `HistoryDB` uses a single connection and is never
  touched from a `QThread`.
- **`build_deb.py` re-stages from scratch** (`rmtree` + `copytree`), so the stale
  `build/deb_stage/` copy on disk cannot ship.
- **The engine's other guards are sound.** The DOE `ceil` boundary was swept
  exhaustively (fck 5-100 x margin 0.1-40, plus 400k random trials): zero
  off-by-one cases. All 15 `CementType` members resolve. No legitimate aggregate is
  rejected by the density bounds.

---

## 6. Recommended order

1. **Commit `concrete_mix/export/batching.py` and `material_quantify/resources/`.**
   One command; nothing else matters until the build survives a commit.
2. **Loosen C2 and C3.** Clamp rather than raise in `_fine_fill`, and gate the
   surface-wet combo item on moisture >= absorption instead of offering it blind. Both
   need a regression test for the *valid* input, not just the invalid one.
3. **Add a completeness test for `from_mix_design_result`** - assert every
   `MixDesignResult` field is either carried or explicitly listed as intentionally
   dropped. That one test would have caught C4 before it shipped, and will catch the
   next field someone adds.
4. **Carry `ca_split_kg` and `scm_type` through the transfer**, and split the bill's
   coarse aggregate into per-size lines.
5. **Update `docs/USER_MANUAL.md`** - line 490's formula, section 11.2's price table,
   and line 212's standard-deviation default.
6. **Add `argparse` to `main_cli.py`** or drop `--help` from the README.
7. **Fix the README test count**, and delete the P06 workaround branch in
   `tests/test_audit_psd_fixes.py` along with its false comment.

Steps 1-3 are small and unblock everything else. Step 4 is the only one that changes
what the customer sees.
