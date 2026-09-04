# Mix-Design Tab vs Standards — Gap Audit

Source standards (project root):
- `BRE-331-1997-DOE-Mix-Design.md` (BRE 331:1997, DOE method)
- `31-ACI 211.1-22.md` (ACI PRC-211.1-22)
- `IS-10262-2019-NewConcreteMix-design.md` (IS 10262:2019)

App code audited:
- `app/widgets/concrete_tab.py` (Mix Design tab UI)
- `concrete_mix/codes/is10262.py`, `concrete_mix/codes/aci211.py`, `concrete_mix/codes/doe.py`
- `concrete_mix/codes/tables/is_tables.py`, `aci_tables.py`, `doe_tables.py`
- `concrete_mix/engine/target_strength.py`, `concrete_mix/models/mix_input.py`

Status: review only — no calculation code was changed to produce this document.

## Implementation log (Phase 1 — 2026-09-03, tested, 324 engine tests green)

- **IS-9 (partial, enforced):** exposure minimum grade now blocks the design
  (`codes/is10262.py` via `required_min_fck_mpa()` in `tables/is_tables.py`;
  raises citing IS 456 Table 5). Cement-only content above 450 kg/m³ emits a
  compliance warning citing IS 456 Cl 8.2.4.2 / Annex A-1(j) — deliberately a
  warning, not a silent cap, since cutting cement would break the w/c–strength
  design. Zone IV + reinforced emits the Table 5 Note 4 warning.
- **IS-12 (fixed):** admixture mass/volume gated on `dosage_percent > 0`
  (`codes/is10262.py`); the water-reduction step stays gated on reduction > 0.
- **DOE-2 (fixed):** `sub_angular` now maps to uncrushed in both DOE mappers
  (`codes/doe.py`, BRE 331 §1.2.4); also removed the bare `"angular"`
  substring test that re-caught `sub_angular`. Only sub-angular behavior
  changes; all other shapes map as before.
- **DOE-1a (fixed):** slump control caps at 180 mm in DOE mode via new
  `UnitSpinBox.set_metric_range()` (`app/widgets/unit_spin.py`,
  `app/widgets/concrete_tab.py:_on_code_changed`); IS/ACI keep 10–250 mm.
- **Deferred to Phase 2 (needs new inputs / behavior design, not done rashly):**
  ACI F/W/C exposure system + F3 SCM caps, NMSA structural-dimension limits,
  Table 5.3.3.1 water adjustments, yield/post-trial rules; DOE air-entrainment,
  pfa/ggbs efficiency, trial-mix procedure, CA-split ratios, Vebe input;
  IS high-strength/SCC/mass branches, pump CA −10% (needs placing-method
  input), site-SD statistics, admixture-liquid water in w/c.

## Implementation log (Phase 2a — ACI freezing exposure, 2026-09-03)

- **ACI-5/ACI-6/ACI-9 (F-class slice, enforced):** new `freezing_exposure_class`
  (F0–F3, default F0) across `MixDesignInput`, `design_mix_simple`, history
  serializers, and the ACI tab (`frost_combo`, ACI-only, history-safe).
  F1–F3 without air entrainment, below-minimum specified strength
  (F1 24.1 / F2 31.0 / F3 34.5 MPa), and F3 SCM over-caps (fly ash/pozzolan
  25%, slag 50%, silica fume 10%, total 50%, ash+silica 35% per ACI 301 Table
  4.2.1.1(b)) all fail fast with the table cited. F1–F3 air comes from Table
  4.7.3.1; the F-class w/c cap competes under lowest-governs (§4.7.1). The
  ≥5000 psi 1.0-point air footnote is surfaced as guidance, never applied
  silently. F0 (default) preserves the legacy path byte-identically.
- 12 new F-class tests; 336 engine tests green.
- **Still deferred:** W (permeability) and C (chloride) exposure classes,
  NMSA dimension limits, Table 5.3.3.1 water adjustments, yield/post-trial
  rules (all need further inputs or alter long-standing outputs).

## Implementation log (Phase 2b — ACI water + corrosion exposure, 2026-09-03)

- **ACI-6 (W/C slice, enforced):** new `water_exposure_class` (W0–W2) and
  `corrosion_exposure_class` (C0–C2, non-prestressed scope — the tab collects
  no prestressing input, stated in code and UI) across `MixDesignInput`,
  `design_mix_simple`, history serializers, and two ACI-only tab combos.
  W2 blocks below 27.6 MPa and caps w/c at 0.50; C2 blocks below 34.5 MPa
  and caps w/c at 0.40; all caps compete under lowest-governs (§4.7.1),
  verified by a combined F2+C2+manual-override test. W1 surfaces the
  4.2.2.6(a) practice note; C1/C2 surface their chloride caps (0.30% /
  0.15%) as constituent-testing guidance — honestly not auto-computed,
  since chlorides cannot be derived from proportions. W0/C0 defaults add
  zero warnings (legacy outputs unchanged).
- 10 new W/C tests; 346 engine tests green.
- **Still deferred:** NMSA dimension limits (needs geometry inputs — UI
  proposal below, not yet coded), Table 5.3.3.1 water adjustments,
  yield/post-trial rules, prestressed chloride scope.

## Proposal (not coded): NMSA structural-dimension inputs

Per ACI 318 26.4.2.1(a)(5) / PRC-211.1-22 §4.3.2, NMSA must not exceed the
minimum of: form width / 5, slab depth / 3, clear bar spacing × 3/4.
Proposed UI (ACI Step 1, all optional): narrowest form dimension (mm),
slab depth (mm), minimum clear bar spacing (mm). Empty = not checked
(legacy behavior); any filled field validates the selected NMSA and blocks
with the governing limit cited. Engine fields would be
`form_width_mm`, `slab_depth_mm`, `bar_spacing_mm` (all None by default).

## Implementation log (Phase 2c — ACI NMSA dimension limits, 2026-09-03)

- **ACI-2 (enforced):** proposal above implemented as specified —
  `check_nmsa_limits()` in `tables/aci_tables.py`; optional
  `form_width_mm` / `slab_depth_mm` / `bar_spacing_mm` on `MixDesignInput`
  (non-positive rejected), `design_mix_simple`, history round-trip, and
  three ACI-only `length_mm` tab inputs where 0 = unchecked (same pattern
  as the DOE min/max-cement spins). Breaches fail fast citing the
  governing limit; multiple breaches are all listed. Boundary values pass
  (`>` semantics, not `≥`). No dimensions → legacy behavior untouched.
- 9 new NMSA tests; 355 engine tests green.
- **Still deferred:** Table 5.3.3.1 water adjustments, yield/post-trial
  rules, prestressed chloride scope, DOE air/pfa/ggbs/trial-mix/CA-splits/
  Vebe, IS high-strength/SCC/mass/pump-mix/site statistics.

## Implementation log (all remaining phases, 2026-09-03)

Engine + UI + serializers + history round-trip throughout. Full suite
(engine + offscreen UI) green; only pre-existing ruff notes remain.

### ACI — complete except lightweight/recycled/SCC/pervious scope blocks
- **Table 5.3.3.1 (§5.3.3.1):** auto-applied from explicit inputs only —
  concrete temperature (±2%/10 °F off the 22.5 °C baseline), manufactured
  sand (+5%), fly-ash (−3%/10%) and slag (−5%/10%) table rates, with a 3.1
  adjustment step; silica/metakaolin warn (no table rate, §4.7.6). Slump/air
  rows deliberately NOT auto-applied (Table 5.3.3 interpolation already
  encodes them; Example 1 pins unadjusted water for rounded gravel) but are
  available via `water_adjustment_531()` for trial refinement. WRA <5% /
  HRWRA <12% dosage warnings (§4.7.6). New tab inputs: temperature, mfg-sand
  flag; water preview reflects adjustments.
- **Yield + post-trial (§4.7.9/§5.3.10):** always-on theoretical-density
  step 10 (ASTM C138 basis); optional measured density/slump/air/strength
  inputs drive steps 10.1–10.4 (yield/Ry check with 0.98–1.02 tolerance,
  water re-estimate ±10 lb/in, air ∓5 lb/%, cement-efficiency strength
  re-estimate). New "Trial Check" tab group (ACI-only).
- **Prestressed scope:** flag + checkbox; C-table prestressed chloride
  guidance (0.06%).
- Exposure F/W/C classes and NMSA dimension limits: see Phase 2a–2c above.

### DOE (BRE 331) — complete
- **Air entrainment (§8):** `air_pct` input + tab spin; modified target ÷
  (1−0.055a), water from one class lower, density −10·a·RDA, 3–7% range
  warning, BS 1881 air-first note, FA−5% guidance. Verified against the
  §8.6 Table 8 example (W 145, C 320, FA 600, CA within 5 kg, w/c within
  half a chart division).
- **pfa (§9):** Table 9B water cuts (interpolated), k = 0.30 C6/C7/C8
  calculations, (C+F) durability comparisons, Figure 6 on W/(C+F).
  Verified against the §9.4 example (C 280, F 120, FA 490, C8 0.36).
- **ggbs (§10):** ≤40% mass-for-mass path with −5 kg water; >40% blocked
  with consult-the-supplier error (§10.3); other SCM types blocked (no BRE
  procedure). Tab ggbs range capped at 40% for DOE.
- **Trial quantities (§6.1):** always-on 0.05 m³ reference-batch step with
  oven-dry conversions and absorption water. **CA splits (§5.5):** 1:2 and
  1:1.5:3 with NMSA validation. **Vebe:** alternative workability basis
  end-to-end (water, validation, Figure 6 class).

### IS 10262 — complete
- **Small items:** pump −10% CA (§5.5.2; HS −5% per §6.2.7; mass warns),
  good/fair site control (+1 MPa, Table 2 Note 1, incl. target-strength
  mode), site-record SD override with ≥30-result(monthly-check) caveat,
  `std_from_samples`/`pooled_std_dev` record helpers (Cl. 4.2.1.2),
  admixture-liquid water counted at durability caps (Cl. 5.1 note, hard
  block on breach). New tab inputs: placing, site control, admix. water.
- **High-strength (§6):** auto-route at M65+; Tables 7/8/10/6/9, 40 mm
  blocked, Zone IV blocked / III discouraged, M80+ 10 mm nudge, aggregate
  quality + PCE-HRWRA guidance, trial clause 6.2.9.
- **Mass concrete (§9):** explicit flag or 80/150 mm auto-route (40/80/150
  valid; 80/150 IS-only with ACI/DOE guards); Tables 11/12/13, §9.2
  +20/+25% wet-sieve target (strength reporting only, w/c from base),
  §9.6.1 bump rule, §9.10/Table 15 mortar check, trial clause 9.11.
- **SCC (§§7–8):** target SF class + measured slump-flow/L-box/SR/V-funnel
  acceptance against §7.2 bands, §8.3 envelope checks (FA 48–60%,
  water 150–210, powder 400–600 with hard block above, PCE-HRWRA note).
  New "SCC (optional)" tab group. The §8.2 (a)–(p) lab-iteration loop
  itself remains a site procedure — the engine enforces its gates.

### Deliberately not built (no standard-compliant closed form exists)
- Liquid-admixture water *fractions* (need solids content — user supplies
  kg/m³ instead); ggbs k-factor design (BRE: consult manufacturer);
- full (a)–(p) generative SCC proportioning (lab-iterative by definition);
- lightweight/recycled/SCC/pervious ACI scope blocks (no density inputs
  collected to discriminate them).

## Implementation log (DOE any-grade Figure 3 pick, 2026-09-03)

- **User-supplied Figure 3 equations verified first:** 14,010 randomized +
  boundary + property checks (4 seeds, fcu ∈ [1, 100], n ∈ [1, 60])
  against Line A (n<20: s = 0.4×fc for fc≤20, else 8 MPa) and Line B
  (n≥20: s = 0.2×fc for fc≤20, else 4 MPa) — 0 failures, including
  continuity at fc = 20, monotonicity, and Line A ≥ Line B. (Line B above
  fc = 20 reads s = 4 MPa, completing the truncated spec by continuity.)
- **25 MPa structural floor lifted for DOE only** (IS/ACI unchanged):
  `MixDesignInput` accepts DOE fc ∈ [5, 100] MPa; `doe.py` and the
  target-strength path no longer block low grades.
- **SD shown in the steps:** calculation Step 1 now records the Figure 3
  line, the n-basis, and the exact equation applied
  (e.g. "Figure 3 Line A (fc=15 MPa, n=10 (<20 results)): s = 0.4 × 15 =
  6.00 [N/mm²]"), with plateau branches spelled out above fc = 20.
  Tab banner, strength floor (5 MPa), tooltips, and validator texts
  updated; target-strength panel already displayed SD + margin.
- M15 end-to-end: s = 6.0 → fm = 24.84, w/c 0.71. 8 new tests (seeded
  randomized compliance, boundaries, low-grade designs, floor behavior).

## Implementation log (25 MPa floor removed for all codes, 2026-09-03)

- **No app-imposed structural floor anywhere:** `MixDesignInput` and the
  target-strength path accept any grade in [5, 100] MPa for IS, ACI and
  DOE alike (5 MPa sanity floor; below that is soil-cement territory).
- **Durability still guards via the standards themselves:** IS 456 Table 5
  minimum grades (e.g. M20/severe still blocked), ACI F/W/C exposure
  minima, DOE Figure 3 lines — verified by dedicated tests proving bad
  low-grade combos still fail (M20/severe, M20/F2).
- Tab control (5–100 MPa), banner, tooltips, strength help, and IS/ACI
  validator wordings updated to stop claiming a 25 MPa requirement.
- Floor tests rewritten as acceptance tests (M20 IS → 26.6, M20 ACI →
  25.9, M20 DOE → 26.56); ACI Example 1 now constructs at 17.24 MPa
  directly (setattr hack removed).

## Implementation log (probit k-factor + all-codes floor removal, 2026-09-03)

- **`defective_k_factor()`** (`concrete_mix/utils/statistics.py`): standalone
  reusable Z-score via `scipy.stats.norm.ppf` at cumulative (1 − p);
  accepts percentages [1, 100) or proportions (0, 1), full float precision
  (5% → 1.6448536270, 3% → 1.8807936082). scipy declared in
  requirements.txt and installed into `.venv` (1.18.1).
- **DOE `get_k_value()`** now computes dynamically and rounds to **2dp**
  (BRE 331 §4.4 precision point): 10→1.28, 5→1.64, 2.5→1.96, 1→2.33 —
  identical to the old table at every tabulated point, exact everywhere
  else (15% → 1.04 instead of clamped 1.28; sub-1% percents read as
  percents; garbage raises instead of clamping). K_VALUES table deleted.

---

## Final verification status (2026-09-04 — all phases implemented, 728 tests green)

Previous revisions of this document listed per-clause gaps (IS-1…IS-12,
DOE-1…DOE-11, ACI-1…ACI-13) as "missing in the app". Those tables described
the pre-implementation state and are superseded by the implementation logs
above. Status of every item today:

| Item | Standard clause | Status |
|---|---|---|
| IS target strength (Cl. 4.2, Table 2) | f'ck = fck + 1.65·S or fck + X, higher governs | Ceiled to whole MPa, app policy (M40: 48.25 → 49; M30: 38.25 → 39). The standard states no rounding; rounding up is conservative. Annex A app quantities sit slightly above the printed example (C 415 vs 412) |
| IS exposure grade floor (IS 456 Table 5) | M15–M40 minimums | Enforced, fail-fast |
| IS max cement 450 kg/m³ (IS 456 Cl 8.2.4.2) | Cement-only content | Compliance warning (deliberate: silent capping would break w/c design) |
| IS pump CA −10% (Cl. 5.5.2; HS −5% §6.2.7) | Placing-method input | Implemented (`pump_ca_reduction_percent` 0–10, UI + history) |
| IS site control / SD statistics (Cl. 4.1–4.2.1) | Fair-control +1 MPa, ≥30-result records, pooled SD | Implemented with caveats surfaced in UI |
| IS admixture water in w/c (Cl. 5.1 note) | Liquid admixture water at durability caps | Counted; hard block on breach |
| IS high-strength (§6), mass (§9), SCC (§§7–8) | M65+ / 40–150 mm / SCC gates | Auto-routed branches with trial-clause citations; §8.2 (a)–(p) lab loop stays a site procedure |
| IS admixture volume gate (Annex A A-9e) | Dosage > 0 with reduction = 0 | Fixed (gated on dosage) |
| ACI f'cr, no-data table (Table 4.7.4.1) | +1000 / +1200 psi, 1.10fc + 700 | Exact piecewise; reported ceil to whole MPa, app policy (Ex. 1: 24.13 → 25). External check: +1000 below 3000 psi / +1200 for 3000–5000 psi confirmed |
| ACI statistics (Tables 4.7.4.3/4.7.4.4) | k-factor 15–29 tests, both f'cr branches, >5000 psi branch | Implemented; user-SD path included |
| ACI exposure F/W/C (Tables 4.7.3a–d) | Strength floors, w/c caps, air, cement types, F3 SCM caps, lowest-governs | Enforced incl. S-class floors S1 27.6 / S2 31.0 / S3 34.5 MPa |
| ACI NMSA limits (§4.3.2) | Form/5, slab/3, bars×3/4 | Optional inputs, fail-fast with governing limit cited |
| ACI Table 5.3.3.1 water adjustments | Temp / mfg sand / ash / slag rates | Auto-applied from explicit inputs only; WRA/HRWRA dosage warnings |
| ACI yield + post-trial (§4.7.9/§5.3.10) | Yield/Ry, water/air/strength re-estimates | Always-on density step + optional Trial Check group |
| ACI Table 5.3.4 Note 1 | Small-NMSA strength effect above 41.4 MPa air-entrained | Warning raised |
| ACI Appendix B note | SG > 3.0 outside normal-density scope | Warning (SG range widened to 5.5 for high-density inputs) |
| DOE Figure 3 SD pick (§4.4) | Line A/B equations | Dynamic k to 2 dp; 14,010 randomized + boundary checks, 0 failures |
| DOE slump cap / Vebe (§1.2.2, Table 3) | 180 mm cap; slump-or-Vebe input | 180 mm cap in DOE mode + full Vebe path |
| DOE sub-angular mapping (§1.2.4) | Rounded + irregular = uncrushed | Fixed in both mappers |
| DOE air (§8), pfa (§9), ggbs (§10) | (fc+M)/(1−0.055a); k = 0.30; ≤40% ggbs | Implemented; verified vs §8.6 (W 145, C 320) and §9.4 (C 280, F 120) examples |
| DOE trial batch (§6.1), CA splits (§5.5) | 0.05 m³ reference batch; 1:2 / 1:1.5:3 | Implemented |
| Grading-zone / sieve guards | Unknown zone; empty stack; 600 µm tie-break | Fail-fast with documented tie-break |
| Cross-cutting grade floor (was: app blocks fc < 25 MPa) | Product deviation from all three scopes | REMOVED for all codes (5 MPa sanity floor only); durability minimums still guard via the standards themselves |

Deliberately not built (no standard-compliant closed form exists): liquid-admixture
water *fractions* (user supplies kg/m³); ggbs k-factor design (BRE: consult
manufacturer); generative §8.2 (a)–(p) SCC proportioning (lab-iterative);
lightweight / recycled / pervious / ACI-SCC scope blocks; prestressed chloride
scope beyond guidance; Table 5.3.3.1 slump/air rows (already encoded in Table
5.3.3 interpolation — available via `water_adjustment_531()` for trials).

## Implementation log (F1–F9 correctness pass + report goldens, 2026-09-04)

- **F1:** IS target exactness — `calculate_target_strength` no longer ceils;
  Annex A exact (48.25 → w/c 0.36, CA 0.648), Annex B exact (332/142/155),
  mass §9.2 wet-sieve raise exact (37.92).
- **F2:** Sulfate fail-fast floors S1 27.6 / S2 31.0 / S3 34.5 MPa plus
  cement-type guidance (`S_CLASS_LIMITS`, `S_CLASS_CEMENT_GUIDANCE`).
- **F3:** Aggregate SG range widened to 5.5 with Appendix B warning above 3.0.
- **F4:** Table 5.3.4 Note 1 warning for air-entrained f'cr above 41.4 MPa.
- **F6:** `pump_ca_reduction_percent` (0–10) end-to-end: engine, UI, history.
- **F7:** Unknown grading zones and empty sieve stacks raise instead of
  silently defaulting; 600 µm tie-break documented.
- **F8/F9:** Stale-coefficient docstrings corrected; SCC honestly relabeled
  as an acceptance/envelope overlay, not generative proportioning.
- **Report goldens:** the 5 `test_report_validation.py` expectations that
  encoded the old whole-MPa (ACI 25.0) and ceil (IS 49.0) policies were
  updated to the corrected engine outputs (ACI 24.2 / IS 48.25 and all
  downstream quantification/cost/cross-method figures) after verifying each
  new value against its standard clause. Full suite: 728 passed.

## Implementation log (whole-MPa target ceil for all codes, 2026-09-04)

- **Policy change (user-requested):** every target strength is now rounded UP
  to whole MPa in all three codes — IS `calculate_target_strength`
  (48.25 → 49), ACI `calculate_target_mean_strength` both branches
  (24.13 → 25), DOE already ceiled per C2. The ceiled value chains into
  w/c selection (conservative direction). Known accepted effect: whole-MPa
  steps can absorb sub-MPa distinctions such as the Table 4.7.4.3
  k-modification at n = 29 (test now pins n = 15, where the distinction
  survives the ceil: 38 vs 36).
- **Consequence for printed examples:** app quantities sit slightly above
  the standards' exact-value worked examples — Annex A C 415 vs 412, Annex B
  total 481 vs 474, ACI Ex.1 C 291 vs 287 — all conservative, disclosed in
  the test comments. AGENTS.md records the policy under Key Tables.
