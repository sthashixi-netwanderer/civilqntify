# CivilQntify project validation and integration audit

**Date:** 2026-10-14  
**Baseline:** commit `7496ecf` (`v1.0.12`)  
**Method:** read-only source inspection, standards-reference comparison, existing automated tests, isolated numerical/API probes, offscreen Qt probes, temporary SQLite databases and mocked networking. Application code was not changed. This report is the only intentional repository change.

## Executive verdict

**No: the project is not completely integrated or reliably correct. I would not sign it off as production-validated engineering or procurement software in its current state.**

There is substantial working functionality, clear domain separation, extensive standards citations and a large regression suite. However, confirmed defects can change trial-batch recommendations, circumvent durability checks, understate procurement quantities and costs, transfer stale laboratory results, or restore different inputs from history. Some failures are silent, which is more serious than a visible crash in this domain.

This review identified **46 distinct findings**, grouped below. These are findings from the paths inspected, not a claim that every possible defect has been found. Passing software tests is not equivalent to standards certification, material suitability, or approval for construction. Mix proportions still require competent engineering review and physical trials.

### Severity definitions

- **P1 / High:** fix before relying on the affected production workflow. Includes materially incorrect quantities/recommendations, broken primary workflows and damaged calculation provenance.
- **P2 / Medium:** confirmed correctness, robustness, security, portability or reporting defect, sometimes limited to a less-common/API path.
- Severity is a remediation priority, not a formal structural-safety assessment. No remote exploit or structural failure was demonstrated.

## What was actually validated

### Test results and execution caveats

The main command was:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
```

Pytest printed **861 passed in 192.52 seconds**. However, the process did not exit within the tool's **200-second timeout**. Therefore the test assertions reported success, but this was **not a clean, successfully terminated full-suite command**. The cause of the lingering process was not isolated.

Focused reviewer runs separately reported:

- 369 calculation, trial, target-strength and worked-example tests passed.
- 63 quantity/GUI tests passed, with 3 deselected.
- 24 history/PSD-export/weather-toggle tests passed.
- 263 PSD, grading and compliance tests passed.

These are overlapping selections, **not additional unique tests to add to 861**. The terminal environment repeatedly appended `Cannot set tty process group` and returned status 2 after otherwise completed commands. Distinguish the printed pytest results from shell exit status.

The environment was Linux with **Python 3.13.9**. Release CI targets Python 3.11. A Python-3.11 grammar check was reported for 107 source files, but this is not execution under Python 3.11.

Additional bounded probes reproduced the findings below. UI probes were offscreen and used isolated settings, stubbed modal dialogs where necessary and temporary data. Networking was mocked; no live weather credentials were used. No real history was modified.

### Coverage and confidence

| Area | Assessment |
|---|---|
| ACI / IS / DOE base design engines | Existing worked examples and many tests pass; important boundary, SCM and validation defects remain. |
| Trial batching and feedback | High-risk defects confirmed in all three code families. Not validated for production use. |
| PSD reference tables | Sampled/compared supported table cells match supplied extracts. Data-state and conformance defects remain. |
| BS washed PSD and DOE 600 µm link | Specific arithmetic, evidence and reporting-precision paths verified successfully. |
| Mix → quantities → costs | Connections exist, but transfers lose properties, clamp SCM and retain stale overrides/results. |
| Quantity and cost calculations | Procurement-volume semantics and cost-unit conversion are incorrect in confirmed paths. |
| History and reproducibility | Input round trips and imported parent chains are not reliable. |
| CLI | Primary interactive input collection crashes. |
| Reports and exports | Some PDF fallback paths generate bytes; structured batching data, portability and LaTeX handling have defects. |
| Weather | HTTPS/timeouts exist, but stale response and QThread lifecycle defects remain. |
| Packaging / CI | Build automation exists; runtime dependency/version gaps and no pytest release gate remain. |
| Interactive visual/accessibility QA | Not performed. Offscreen state testing does not establish visual usability or accessibility. |
| Windows / installed binaries | Not executed. Platform issues identified by source and isolated missing-resource probes. |

## 1. Concrete calculation and trial findings

### C01 — P1: ACI air-correction direction is reversed

**Evidence:** `concrete_mix/codes/aci_trial.py:452–465`; parallel logic in `concrete_mix/codes/aci211.py:827–839`.

The code adds `2.97 × (target_air − measured_air)` kg/m³ of water. ACI clause 5.3.10.2 requires reducing water when air is increased, and increasing it when air is decreased.

**Reproduction:** an air-entrained ACI design has 5% target air; supply a measured 3%. The evaluator recommends **+5.9 kg/m³** water instead of approximately **−5.9 kg/m³**. This was independently rechecked in the parent audit.

**Impact:** wrong-direction adjustment, approximately 11.9 kg/m³ apart from the correctly signed correction. `tests/test_aci_trial.py:177–185` asserts the reversed sign, demonstrating that a passing regression test can encode an incorrect engineering rule.

**Fix:** correct both implementations and replace the test oracle with the standard's direction; verify all next-trial quantities and yield.

### C02 — P1: DOE SCM feedback changes binder even when the trial meets target strength

**Evidence:** `concrete_mix/codes/doe_trial.py:545–568,624–685`.

The trial-point ratio uses water divided by Portland cement alone. Subsequent proportioning interprets that ratio as `W/(C + 0.30F)` for pfa, or `W/(C + G)` for the supported GGBS route.

**Reproduction:** evaluate a DOE design with 30% SCM using measured strength exactly equal to its target and unchanged water. The reviewed cases changed combined binder from **405 → 355 kg/m³** for fly ash and **345 → 240 kg/m³** for GGBS. Both were labelled minor changes, with advice permitting production without further trials.

**Impact:** a successful trial can produce an unjustified major binder reduction.

**Fix:** use the same strength-basis denominator through design, feedback inversion and recalculation; distinguish pfa strength and durability/Figure-6 ratios explicitly. Reference BRE clauses 6.3.3,9.2.2,9.3.3,10.3.

### C03 — P1: IS admixture water can exceed the exposure maximum without rejection

**Evidence:** `concrete_mix/codes/is10262.py:404–414,579–603`.

The final effective-water check is conditional on `durability_governed`, which only becomes true when an earlier selected ratio was strictly above the limit.

**Reproduction:**

```python
from concrete_mix import design_mix_simple
r = design_mix_simple(
    "is10262", 25, 75,
    exposure_class="moderate", w_c_ratio=0.50,
    admixture_water_kg=5,
)
print((r.water_kg + 5) / (r.cement_kg + r.scm_kg))
```

The parent audit observed acceptance at approximately **0.5156**, above the 0.50 maximum. An initial ratio below the cap can also cross it after admixture water is counted.

**Fix:** enforce the final effective ratio against the applicable limit regardless of which earlier branch selected the ratio. Reference IS clause 5.1.1 note and clause 6.2.4.

### C04 — P1: DOE accepts a standard deviation below the required statistical minimum

**Evidence:** `concrete_mix/codes/doe.py:277–293`.

**Reproduction:** DOE 30 MPa, slump 20 mm, 60% passing 600 µm, `num_test_cubes=10`, `std_deviation=1` produces target **32 MPa**, w/c **0.60**, cement **265 kg/m³**. The Line A case uses target **44 MPa**, w/c **0.48**, cement **335 kg/m³**. A supplied deviation of 1 is also accepted with 30 results, below the Line B floor.

**Impact:** an API caller can understate the strength margin. The current GUI makes this DOE field display-only, so this particular override is primarily API-reachable.

**Fix:** enforce BRE clause 5.1: use Line A with fewer than 20 results; established deviations with at least 20 results must not be below Line B.

*Update (2026-10-30):* clause 7.4 Example 4 shows a known s from previous control data with **no record count** is used directly (Item 1.2), so `resolve_standard_deviation` now applies known s (floored at Line B) unless an explicit n < 20 states the small-sample case — Figure 3 remains the fallback when no s is known. Also fixed upstream of the max-cement refusal: the DOE engine now compares the reported Item 3.1 value (nearest 5 kg, e.g. 580) against the Item 3.2 maximum, as on the completed design form.

### Additional confirmed calculation findings

| ID | Priority | Evidence | Reproduction / impact and required correction |
|---|---|---|---|
| C05 | P2 | `concrete_mix/codes/aci_trial.py:483–525` | Strength feedback calculates and reports a water increment but never applies it. In the reviewed 30 MPa case, the ledger reports +86.9 cement and +40.4 water, but next-trial water stays 202 kg/m³ and w/c changes from about 0.465 to 0.387. Implement the stated constant-w/cm efficiency procedure consistently; ACI clause 5.3.10.3. |
| C06 | P2 | `concrete_mix/codes/is10262.py:1158–1163,1211–1217,1248–1254` | SCM trials apply a preliminary 10% binder increase a second time. Fly-ash trials labelled w/cm 0.35 and 0.43 actually produce about 0.318 and 0.391. GGBS trial variants also receive a bump the base path omits. Assert actual water/binder equals the requested trial ratio; IS clauses 5.4.1,5.8. |
| C07 | P2 | `concrete_mix/codes/is10262.py:1129–1146,1227–1232,1264–1269` | IS trials 3/4 omit the pump-related coarse-aggregate reduction. A pumped baseline coarse fraction of about 0.572 changes to unreduced fractions about 0.644/0.628. Preserve placement assumptions while varying trial w/cm; IS clauses 5.5.2,5.8. |
| C08 | P2 | `concrete_mix/codes/aci211.py:640–648,663–670`; `concrete_mix/codes/is10262.py:769–774` | Multiple SCMs are volumetrically treated using the first SCM's SG; ACI paste calculation also uses an unsuitable arithmetic-average SG. Reversing 30% fly ash / 30% GGBS changes ACI fine aggregate 846.0 → 903.6 and IS 596 → 625 kg/m³. Independently summed volumes deviate from 1 m³. Use the sum of each constituent's absolute volume. This is reachable through the multi-SCM input model, not the simplified single-SCM interface. |
| C09 | P2 | `concrete_mix/codes/doe_trial.py:93–104` | DOE trial density reconstructs from coarse SG alone instead of the combined RD used in design. With design RD 2.4 and measured density matching design at 2250 kg/m³, feedback assumes 2475 and applies factor 0.9091 instead of 1.0. Carry the actual design density; BRE Item 4.1 and clause 6.3.2. |
| C10 | P2 | `concrete_mix/codes/doe_trial.py:323–376` | Surface-wet scheduling reduces added water without increasing aggregate batch masses. A reviewed 0.05 m³ case emits fine/coarse masses 32.0/68.2 kg rather than about 33.58/69.27 kg. Correct both aggregate and water masses, with a consistent dry/SSD basis; BRE clause 6.1. |
| C11 | P2 | `concrete_mix/codes/tables/aci_tables.py:248–263`; `concrete_mix/codes/aci211.py:506–520` | Non-air-entrained ACI strength lookup silently clamps above the highest table point. Specified strengths 50,70,90 MPa yield targets 56,76,96 but identical w/c 0.34 and cement 594.1 kg/m³, with no warning. Reject or explicitly flag unsupported table use and require material-specific data. This does not establish the actual attainable strength. |
| C12 | P2 | `concrete_mix/models/materials.py:192–196`; `concrete_mix/models/mix_input.py:428–430` | Individual SCM percentages are checked, but their sum is not. Two 70% SCMs are accepted; reviewed outputs contain negative cement, including −76.5 kg/m³ for ACI and −183 for IS. Validate total replacement and constituent masses before proportioning. |
| C13 | P2 | `concrete_mix/models/materials.py:133–152,165–182` | Physical/finite checks are missing for moisture, absorption and dry-rodded density. Absorption −100% causes division by zero; negative ACI bulk density produces negative coarse mass; NaN propagates. Reject nonfinite/nonphysical values at the public model/API boundary, not only in GUI controls. |
| C14 | P2 | `concrete_mix/engine/target_strength.py:168–181` | DOE target-only computation ignores a supplied deviation and uses a missing-count default inconsistent with full design. For fc 30/no production data, target-only reports 37 MPa while full design reports 44. Share one target-strength implementation and input policy. |
| C15 | P2 | `concrete_mix/codes/doe.py:998–1005` | Cement enum `GRADE_52_5N` maps to 42.5 because the mapper tests for `53` but not `52.5`. Reviewed reference strength changes 48 → 42 MPa and cement 325 → 355 kg/m³. Use explicit enum mappings; national cement equivalence also needs engineering qualification. |
| C16 | P2 | `concrete_mix/codes/aci_trial.py:150–162,510–514` | Fine-aggregate fill omits chemical-admixture volume while emitted next-trial quantities include its mass. A reviewed 1.5% dosage / 20% water-reduction case totals approximately 1.00454 m³. Include every constituent in yield closure. |

## 2. Quantification, costing and cross-tab findings

### Q01 — P1: Cost-rate controls convert metric rates as though they were imperial

**Evidence:** `app/widgets/unit_spin.py:120–134,215–218`; `app/widgets/cost_result_panel.py:258–262`.

Rate conversion functions do not branch on the selected unit system. A metric sand rate with backend value 350 displays approximately **267.59/m³**; entering **350/m³** produces a backend value approximately **457.7825/m³**. Mass and transport rates are affected by the same pattern.

Water has a separate per-1000 scaling error: **GH₵15/1000 L** displays approximately **GH₵0.06/1000 gal**, rather than approximately **GH₵56.78/1000 US gal**. The metric-label lookup compares a `_Kind` instance with string keys, so its intended override cannot match.

**Fix:** metric conversion must be identity; reciprocal rate conversion must use the same quantity-unit factor and thousand-unit convention as the displayed rate. Share conversions between controls and result panels and test typed rates, not only programmatic metric values.

### Q02 — P1: Sand purchasing volume is actually particle absolute volume

**Evidence:** `material_quantify/engine/quantifier.py:135–149`; `material_quantify/cost.py:64–66`.

The design-mix route labels `mass/(SG × 1000)` as bulk sand volume and directly prices it per m³. That is particle absolute volume, excluding interparticle voids, not the purchased loose/bulk volume.

**Reproduction:** 700 kg sand produces **0.264 m³**. At a measured bulk density of 1600 kg/m³, purchasing volume would be **0.4375 m³**. The density is an illustrative measured input, not a universal standard constant. The ratio workflow uses bulk-volume semantics instead, so the two workflows are inconsistent.

**Fix:** distinguish absolute, dry bulk and as-delivered quantities; collect/carry the appropriate measured bulk density and moisture basis. ACI clause 4.7.7.2 distinguishes the volume concepts.

### Q03 — P1: SCM is accepted in quantities but omitted from cost

**Evidence:** `app/widgets/cost_estimation_tab.py:248–258,729–743`; `material_quantify/cost.py:16–23,63–80,103–144`.

Changing SCM from zero to 10,000 kg leaves the project cost unchanged. There is neither an SCM unit price nor an SCM breakdown line, despite UI wording indicating separate pricing.

**Fix:** price SCM by material type or mark any SCM-containing estimate explicitly incomplete. Do not present omitted materials as a complete project cost.

### Additional confirmed transfer/state findings

| ID | Priority | Evidence | Reproduction / impact and required correction |
|---|---|---|---|
| Q04 | P1 | `app/widgets/material_quantify_tab.py:439–451,1201–1212,1503–1506` | A valid IS 40 MPa / 60% GGBS design produced 308 kg/m³ SCM, but transfer silently clamps it to the widget maximum of 200. The bill then uses 200. Accept the domain's valid range or reject the transfer explicitly; never silently alter it. |
| Q05 | P1 | `app/main.py:245–254`; `app/widgets/material_quantify_tab.py:1201–1238,1503–1506` | Transfer properties are replaced with constants. A supplied coarse bulk density 1800 and fine SG 2.8 become 1600 and 2.65. A fresh ACI transfer can also be relabelled `manual`. Preserve source properties and synchronize the standard selector. |
| Q06 | P1 | `app/widgets/material_quantify_tab.py:1175–1199,1241–1250,1268–1291,1503–1509` | Enabled overrides leak between transferred designs. After cement override 500 on mix A, loading mix B with 600 shows 600 in the main field but bills 500. Initial override fields can also remain zero. Reset/reinitialize on new transfer or require explicit confirmation to retain overrides. |
| Q07 | P1 | `app/widgets/cost_estimation_tab.py:673–704,716–718`; `app/widgets/material_quantify_tab.py:1454–1456,1553–1559`; `app/widgets/quant_result_panel.py:339–342` | Stale results remain usable after replacement/invalid inputs. Transferring a 100 m³ bill after estimating 10 m³ updates inputs but leaves the old cost result. Selecting empty element mode after a valid bill warns but retains that bill and enables Send to Cost. Invalidate results, display staleness and disable downstream use. |
| Q08 | P2 | `app/widgets/material_quantify_tab.py:1454–1465,1531–1551` | An edit can be lost while a worker runs. With an injected 800 ms delay, starting at 10 m³ then editing to 20 m³ leaves a 10 m³ bill, 20 m³ input and no pending recalculation. The scheduling defect is confirmed; ordinary frequency is unknown. Track request revisions/pending work and reject obsolete completions. |
| Q09 | P2 | `app/widgets/material_quantify_tab.py:1744–1764`; `app/widgets/unit_spin.py:187–189,255–262` | Restoring one 6 × 0.3 × 0.4 m beam, quantity 1, restores correct inputs and a 0.720 m³ calculation, but row/total labels remain at the default 1.000 m³. Suppressed programmatic signals are not followed by a refresh. Recompute derived labels after restoration. |
| Q10 | P2 | `app/widgets/cost_estimation_tab.py:895–899` | Cost-history volume reconstruction depends on positive material cost/m³. A 20 m³, zero-material estimate restores into a fresh tab with volume 1 m³; re-estimation changes the reviewed total from GH₵3,084.375 to GH₵1,089.375. Store/restore explicit volume rather than infer it from cost. |

## 3. PSD correctness and integration findings

| ID | Priority | Evidence | Confirmed reproduction / impact and correction |
|---|---|---|---|
| P01 | P1 | `app/widgets/psd_widget.py:3762–3765,3782–3830,651–676` | IS/ASTM mass edits do not invalidate the previous analysis. Compute fine retained masses `[0,20,80,200,250,250,150]`, pan 50 g; change 600 µm retained mass from 250 to zero. The table shows 60% passing while Apply still transfers 45%. Invalidate results/Apply on every input mutation, as the BS branch already does. |
| P02 | P2 | `app/widgets/psd_widget.py:3977–3987,3787–3798`; `concrete_mix/engine/psd.py:185–195` | Invalid mass text silently becomes zero; NaN/infinity are not rejected by the general engine. An ASTM sample with `oops` in the first cell still passes grading/FM checks. `compute_psd([NaN,100],[10,5])` returns nonfinite results; independently rechecked. Show cell errors and reject malformed/nonfinite evidence. BS numerical validation is stronger, but UI text parsing is shared. |
| P03 | P2 | `concrete_mix/engine/psd.py:290–298`; `concrete_mix/validation/astm_c33.py:146–191`; `concrete_mix/validation/is383.py:153–200,220–265`; `concrete_mix/engine/grading.py:182–185` | Missing controls can be interpreted as passing evidence. A result with only a 100 mm sieve passes an ASTM Size 67 or IS graded-20 assessment; an IS result with only 600 µm=50% can pass fine grading. Empty conformance mappings can also yield `all_conform=True`. Normal UI stacks include the sieve rows, so this is principally a validation/API gap. Return not-assessed for incomplete required evidence. |
| P04 | P2 | `concrete_mix/validation/is383.py:220–265`; `app/widgets/psd_widget.py:3263–3266` | The IS evaluator classifies the measured zone, then inserts the selected zone into success text without checking that zone. A Zone-II sample with 45% passing 600 µm receives PASS for selected Zone III, whose limit is 60–79%. Evaluate selected-envelope conformance separately from automatic classification. |
| P05 | P2 | `concrete_mix/engine/psd_link.py:138–145`; `app/widgets/psd_widget.py:655–658,4110–4123` | Crushed-stone-sand relief is not passed to linkage classification/plotting. A valid Zone-II sample with 16% passing 150 µm passes quality evaluation under the 20% relief, but linkage says nonconforming against the base 10% limit. Carry material context through all views and handoffs. |
| P06 | P2 | `app/widgets/psd_widget.py:663–668`; `app/widgets/concrete_tab.py:3994–4006` | IS graded 12.5 mm is converted to integer 12 in Apply's payload; the receiver casts again. The form has a genuine 12.5 option, so selection cannot match. Preserve fractional nominal sizes end-to-end. |
| P07 | P2 | `concrete_mix/engine/grading.py:165–175,205–225` | IS Clause 6.3 tolerance is applied at the expressly excluded 600 µm sieve. A reviewed passing map with 600 µm=59.5% reports Zone II conformance through that tolerance. Define any reporting-rounding policy separately; do not apply a prohibited tolerance. |
| P08 | P2 | `app/widgets/psd_widget.py:4021–4041` | Success text counts `not_evaluated` checks as completed applicable requirements. An ASTM sample with 3 passes and 7 not evaluated says all 10 applicable requirements were checked. Report separate pass/fail/not-assessed counts and avoid suggesting full standard compliance. |

### PSD checks that did succeed

- Supported IS Table 7, IS Table 9, BS Tables 3/4 and ASTM Sizes 8/67/467 controls matched the supplied extracts, including no-requirement cells. The review compared 90 IS coarse cells, 28 IS fine controls, 56 BS coarse cells, 28 BS effective fine controls and 42 supported ASTM coarse cells; ASTM fine limits also matched.
- Computed IS → ASTM → BS → IS switching rebuilt the appropriate sieve series, cleared old masses/results and disabled Apply.
- BS washed arithmetic used original M1 and incorporated washed loss once. With M1=1000 g, M2=990 g, retained `[500,300,170,5]` at `[10,5,2.36,0.075]` mm and raw pan 15 g, corrected pan was 25 g and passing was 50,20,3,2.5%. Separate washing-only Table 6 fines remained 1%.
- BS measured 600 µm passing of 40.6% transferred to DOE as 41%; missing actual 600 µm evidence was not synthetically interpolated.
- BS 14/5 mm references were not silently mapped to DOE 10/20/40 mm.
- BS preserved overlapping C/M/F grading, crushed-rock/heavy-duty exceptions, independent FI evidence and the unassessed ten-consecutive-sample condition. BS edits invalidated results.
- BS used the labelled numerical-linear display policy without characteristic-diameter overlays.

## 4. CLI, persistence, exports, weather and delivery findings

### R01 — P1: All interactive CLI standard choices crash

**Evidence:** `main_cli.py:234`, with additional undefined uses at 318 and 351.

`collect_mix_inputs()` defines `is_aci` and `is_doe`, but uses `is_is` without defining it. Bounded default-input probes for all three standard choices raised `NameError: name 'is_is' is not defined`. The default IS route was independently rechecked.

**Fix:** make standard branching explicit and add a CLI input-collection smoke test for every offered standard. Import/compile/`--help` tests are insufficient.

### R02 — P1: History silently drops calculation inputs

**Evidence:** `history/serializers.py:16–68,125–177`; restoration in `app/widgets/concrete_tab.py:4462–4464,4497–4507`.

Round trips lost `ca_volume_fraction_override`, `pump_ca_reduction_percent`, `num_strength_tests`, `apply_rounded_aggregate_reduction` and `target_paste_volume_pct`. Reopening a record can restore defaults while continuing to display the original saved result.

**Fix:** version the persisted input schema, serialize every behavior-affecting field and assert full semantic round-trip equality. Make old-record defaults visible.

### R03 — P1: History import corrupts provenance and lacks atomic rollback

**Evidence:** `history/db.py:425–444`; GUI import handling `app/widgets/history_tab.py:429–435`.

Imported records receive new IDs, but keep source `parent_id` values. Probes produced a self-referencing imported child in an empty database and a child linked to an unrelated record in an occupied one. A later foreign-key failure left earlier inserts pending; a subsequent unrelated save committed the partial import. The GUI does not catch the resulting SQLite integrity exception.

**Fix:** prevalidate, allocate/map old IDs to new IDs, rewrite parent links, and import within an atomic transaction with rollback and actionable UI errors.

### R04 — P1: The source Debian package omits mandatory dependencies

**Evidence:** `scripts/build_deb.py:111`; startup imports through `concrete_mix/__init__.py:27` and `concrete_mix/utils/statistics.py:9`.

The source-package dependency declaration omits fpdf2 and SciPy, although either one's absence prevents importing the application package. This concerns the source-based Debian builder, not the frozen FPM artifacts.

**Fix:** synchronize package metadata with runtime requirements and install-test on a clean image.

### Additional confirmed delivery/infrastructure findings

| ID | Priority | Evidence | Confirmed behavior / correction |
|---|---|---|---|
| R05 | P2 | `app/widgets/weather_widget.py:687–708`; `app/weather/weather_worker.py:27–39` | Changing city during a request can label old weather with the new city's name. Mocked Accra → Agona switching ran only one request and emitted its result with Agona's name. Use immutable per-request inputs and a generation ID; discard stale responses. |
| R06 | P2 | `app/widgets/weather_widget.py:279–305,710–723` | Destroying a widget with active parented weather workers caused a subprocess abort, exit −6, with `QThread: Destroyed while thread ... is still running`. Add explicit shutdown/lifecycle ownership. Ordinary full-application shutdown was not reproduced: that separate probe timed out. |
| R07 | P2 | `app/widgets/cost_estimation_tab.py:1278–1295` | Cost PDF export loads fonts only from `/usr/share/fonts/truetype/dejavu/`. A missing-font probe produced an error and no PDF. Those paths are not normally available on Windows. Bundle licensed fonts and resolve them through resource paths, with fallback. |
| R08 | P2 | `concrete_mix/export/csv_export.py:20–36`; `concrete_mix/export/json_export.py:16–43` | Structured mix exports omit admixture quantity and moisture-adjusted water/aggregate masses. JSON also omits requested batch volume; CSV omits warnings. Traces may retain some information, but exported proportions are not complete field batching schedules. Export design/SSD and field-batch quantities distinctly; ACI Table 5.3.9.1 and IS D-9.1. |
| R09 | P2 | `history/db.py:414–417` | Export All calls `list_calculations(limit=10000)`. A 10,001-record database exports 10,000 without warning. Remove the hidden cap or paginate with explicit completeness verification. |
| R10 | P2 | `concrete_mix/export/pdf_report.py:104–129,568,756,922–927` | LaTeX escaping preserves backslash commands and corrupts Unicode placeholders. Generated-source probes retained executable TeX commands in user/importable text; on TeX-enabled installations this can interpret untrusted text as TeX, potentially including file-reading directives. Actual TeX execution was not tested because no engine is installed. Independently rechecked `m³ ≥ σ` becoming literal escaped `LATEXUNI` placeholders. Escape untrusted text completely and keep trusted math separate; harden compiler settings/process isolation. |
| R11 | P2 | `scripts/install_linux_desktop.sh:16–20` | Fresh-home installation fails because the icons destination parent is not created, leaving a partially installed launcher. A temporary empty-HOME probe exited 1. Create required directories and make installation failures atomic/actionable. |
| R12 | P2 | `.github/workflows/build_and_release.yml:130–133`; `scripts/build_deb.py:19`; `app/version.py:3` | Main-branch CI packages use 1.0.0, source Debian defaults to 1.0.8, application reports 1.0.12. Package managers cannot reliably order successive builds with unchanged versions. Derive all artifacts from one validated version source. |

## 5. Critical feedback on architecture and product claims

### What the project gets right

1. **Useful domain separation:** calculation engines/models, GUI, quantity calculation and persistence are separate enough to inspect and test independently.
2. **Standards traceability:** source citations, extracted references and worked-example tests are much better than opaque formulas without provenance.
3. **Substantial regression investment:** 861 reported passing tests is meaningful coverage, especially the offscreen UI and standard-example tests.
4. **Explicit PSD code families:** standard-specific sieve series and no-requirement cells are generally handled deliberately; the BS workflow has especially good evidence semantics.
5. **Some infrastructure safeguards exist:** network HTTPS/timeouts, a Python-3.11 source compile gate and build/smoke automation are present.
6. **Unit infrastructure is reusable:** a tested 3 × 0.4 × 0.5 m element preserved 0.600 m³ through metric → imperial → metric. This positive result does not extend to the faulty rate controls.

### The central architectural weakness

**The project has more confidence in individual functions than in the invariants between workflows.**

The recurring pattern is: one stage computes a result; the next stage reconstructs it from GUI controls, hardcoded defaults, rounded values or incomplete serialization. The calculation can be correct locally while the project workflow becomes wrong.

Examples include lost material properties, silent spinbox clipping, overrides from an earlier design, stale async responses, restored defaults paired with old results, different SCM ratio denominators and absolute volume presented as purchasing volume.

Recommended architectural direction:

- Use typed, immutable, versioned calculation snapshots as the authoritative handoff between tabs.
- Treat widgets as editors/views, not an undocumented second calculation model.
- Include input revision IDs in workers; only current revisions may update results or enable exports/transfers.
- Preserve units and quantity basis in field names/types: SSD, dry, wet/as-batched, absolute volume, loose/bulk purchasing volume.
- Represent each binder constituent with its own mass, SG, type and cost, rather than one aggregate SCM mass with an inferred SG.
- Share ratio, statistical-margin, moisture and conversion logic instead of duplicating it across full design, target-only, trial and report paths.
- Tie exports/history to the exact input snapshot and engine version used for their result.

These changes need not become a large rewrite: establish the invariants and migrate the highest-risk handoffs first.

### Claims currently exceed demonstrated capability

`README.md:22–28` advertises rebar and specialized slab/footing/wall/staircase quantification. The inspected implementation uses rectangular `L × W × D × quantity` element models, with no rebar input/model/calculation/cost path found. Rectangular decomposition may approximate some concrete volumes, but is not a dedicated ribbed/waffle, staircase or reinforcement take-off implementation.

Other documentation drift:

- README calls the product production-grade despite the confirmed blockers.
- README mentions ReportLab, while the active dependency/report paths use fpdf2 and optionally LaTeX.
- README broadly mentions real-time supplier cost estimation, but the documented/current workflow is manual price entry.
- README's 240+ tests is stale relative to 861 collected/reported passes.
- SCC is an overlay rather than demonstrated complete Annex E proportioning; ACI high-density guidance is not a comprehensive Appendix B verification.

**Recommendation:** publish a clear feature/support matrix: implemented, preliminary, guidance-only and unsupported. Do not imply complete standard compliance from partial grading evidence or a preliminary mix design.

### CI, reproducibility and security gaps

- The sole inspected workflow has no pytest gate and no `pull_request` trigger. Builds can pass despite the CLI failure and numerical defects.
- `requirements.txt` has lower bounds but no Python lock/constraints file, so release dependency resolution is not reproducible. The npm lockfile covers Wrangler, not Python runtime releases.
- Weather API keys are stored in ordinary QSettings, not an OS credential vault. User settings were not inspected, and no secret values are included in this report.
- A narrow tracked-Python credential-literal scan found no assignments, but this was not a comprehensive secret/history scan.
- There was no live package vulnerability-database audit. Dependency security is unverified, not declared clean.
- The knowledge graph was stale at an earlier commit and was not used as authoritative evidence.

## 6. Recommended remediation order

### Gate 1: Stop materially incorrect recommendations and costs

1. Correct ACI trial air/strength handling, DOE SCM feedback and IS final effective-water checks: C01–C03,C05.
2. Enforce DOE statistical minimums and finite/physical model validation: C04,C12,C13.
3. Fix rate controls, sand purchasing-volume basis and SCM costing: Q01–Q03.
4. Stop stale-result handoff and silent transfer mutation: Q04–Q08,P01.
5. Fix the CLI crash: R01.

**Exit criterion:** every corrected issue has a minimal reproduction regression test with an independently sourced expected result. Do not merely edit assertions to match the new implementation.

### Gate 2: Make calculations reproducible and evidence truthful

1. Repair history field coverage, import ID remapping/transactions and volume restoration: R02,R03,Q09,Q10.
2. Fix trial-ratio, placement, density, moisture and multi-SCM consistency: C06–C10,C14–C16.
3. Correct PSD missing-evidence semantics, selected-zone evaluation, material context, fractional sizes and status counts: P02–P08.
4. Warn/reject unsupported ACI table strengths: C11.
5. Export full design and as-batched schedules with warnings and exact source snapshots: R08.

**Exit criterion:** restored/recomputed results match originals for all supported behavior-affecting input fields; all outputs disclose what was and was not assessed.

### Gate 3: Validate the actual distributed product

1. Add Linux offscreen pytest and supported-Python-version gates before release builds.
2. Install-test source Debian and frozen artifacts on clean systems; test Windows report generation.
3. Repair dependency declarations, fonts, desktop installation and version derivation: R04,R07,R11,R12.
4. Harden weather request/lifecycle handling, LaTeX and history backup completeness: R05,R06,R09,R10.
5. Lock/reproduce runtime dependencies and perform dedicated dependency/secret scanning.
6. Align README/manual/release notes with tested capabilities and limitations.

**Exit criterion:** clean install → launch → each standard → PSD link → quantities → costs → save/restore → export succeeds on each release target, with verified numerical/evidence invariants.

## 7. Tests that are missing or insufficient

Prioritize independent properties over ever-larger examples that duplicate implementation formulas:

- **Yield closure:** sum every constituent absolute volume plus air; detect omitted admixture and each separate SCM.
- **Permutation invariance:** reordering identical SCM constituents must not change proportions.
- **Trial identity:** a trial matching design strength, density, slump and air must not produce a major unrelated change.
- **Ratio integrity:** actual water/binder or effective-binder ratio equals the trial's labelled/requested ratio.
- **Moisture conservation:** wet aggregate mass and added-water changes preserve dry solids and effective mixing water.
- **Durability invariant:** final effective water ratio satisfies the applicable maximum independently of branch history.
- **Statistical policy:** test below/at/above record-count boundaries and minimum permitted deviation.
- **Unit/rate duality:** quantity × unit price is invariant under display-unit switching; typing a metric rate must not rescale it.
- **Cost completeness:** every nonzero purchased material is priced or explicitly flagged unpriced/incomplete.
- **Transfer equality:** valid values, standards and material properties survive handoff without clipping/default substitution.
- **History semantic equality:** serialize/deserialize every dataclass field and compare the recomputed result.
- **Backup graph equality:** import into empty and occupied databases, preserve provenance and fully roll back failures.
- **Input revision integrity:** editing while a worker runs cannot publish or transfer a result for an older revision.
- **PSD evidence integrity:** malformed/nonfinite/incomplete data cannot produce an unqualified PASS.
- **PSD selected-zone integrity:** classification and selected-envelope conformance are distinct and correctly reported.
- **CLI smoke:** simulate complete default input sequences for each advertised standard.
- **Platform export smoke:** verify PDF generation without assuming Linux filesystem fonts or installed TeX.
- **Process teardown:** tests and application exit cleanly with active/mocked workers.

## 8. Standards baseline and remaining uncertainty

The audit used `AGENTS.md`, the root ACI/IS/BRE extracts, BS 882/BS 812 extracts, and supplied IS 383/ASTM C33 documents. Relevant direct checks included ACI clause 5.3.10.2–.3, IS clause 5.1.1 note and BRE clause 5.1. The supplied BS 882 scan ends after printed page 7; the supplied ASTM document is the older C33–99ae1 edition. Matching those extracts does not establish compliance with a complete current edition.

Not completed:

- Independent re-digitization and error bounds for the IS/BRE chart fits over their complete domains.
- Every possible standard table combination, mix input and exposure/SCM interaction.
- Physical concrete trials, measured strength or field material validation.
- Live weather API behavior, outages, quota/rate-limit or credential security tests.
- Windows/native interactive GUI, visual/accessibility or performance profiling.
- PyInstaller builds, package installation, live CI execution or supported-Python execution matrix.
- Actual execution of injected TeX commands; only unsafe generated-source preservation was demonstrated.
- Root-cause isolation of full-suite process nontermination.

**Bottom line:** this is a promising and substantial project, but the dominant risk is silent disagreement between stages. Fix the numerical and state-integrity blockers, make missing evidence explicit, and validate the installed end-to-end product before claiming production-grade correctness.
