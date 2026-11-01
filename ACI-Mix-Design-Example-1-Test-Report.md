# ACI PRC-211.1-22 — Test Report for `aci-mix-design-example-1.pdf`

**Test date:** 27 October 2026
**Specimen:** `aci-mix-design-example-1.pdf` — 39-slide "ACI Method Example" by Barham Haidar (M.Sc.), 2018
**Converted fixture:** [`ACI-Mix-Design-Example-1.md`](./ACI-Mix-Design-Example-1.md)
**Reference standard:** [`31-ACI 211.1-22.md`](./31-ACI%20211.1-22.md) (primary), with ACI 318 target-strength tables as cited by that guide
**Scope:** ACI only — `concrete_mix/codes/aci211.py`, ACI tables, ACI moisture/trial path, and the ACI branch of the Concrete tab. IS 10262 and DOE were **not** tested.
**App changes made for this report:** **none.** The two Markdown files are the only additions; no application, test, or reference file was modified.

---

## 1. Bottom line

| Result           | Count | Meaning                                                                                                                                                                 |
| ---------------- | ----: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PASS**         |    14 | The ACI engine reproduces the standard's proportioning arithmetic and the PDF's Step 3–7 logic once the PDF's 1991 table values and arithmetic slips are separated out. |
| **FAIL**         |     2 | One real input-contract bug (moisture basis) and one input-coverage gap (no ACI w/c or f′cr entry in the UI).                                                           |
| **NOT TESTABLE** |     1 | PDF Example 2 needs a 75 mm NMSA and a flexural-strength input; the app has neither.                                                                                    |

The **only defect that produces wrong concrete** is the moisture input contract. The engine's moisture formula is correct for ACI 211.1-22 clause 5.3.9.1; the problem is that the UI and public API describe the input as *free moisture above SSD*, while the model and formula require *total moisture content* (ASTM C566). As a result, the documented default **0% moisture does not mean SSD** — it silently dries the aggregate and adds water.

The PDF itself contains several arithmetic errors (not app defects): `0.64 × 1600` is `1024`, not `1020`; `1020 / (2.64 × 1000)` is `0.386`, not `0.396`; the `0.732 m³` and `690 kg/m³` results follow from that typo. Details in clause 6.

---

## 2. How the test was run

### 2.1 Example 1 input

| Input | Value | Notes |
|---|---|---|
| Code | `aci211` | ACI PRC-211.1-22 engine |
| Mean/characteristic strength | 35 MPa | The PDF says **mean** strength; the app field is **characteristic** strength |
| Slump | 50 mm | Within ACI Table 5.3.1 typical ranges (2 in.) |
| NMSA | 20 mm | Maps to the ¾ in. column; the PDF says "20 mm (or 19 mm)" |
| Cement | Type I, SG 3.15 | PDF assumes 3.15 |
| Fine aggregate | SG 2.58, FM 2.60 | PDF values |
| Coarse aggregate | SG 2.64, bulk density 1600 kg/m³, angular | PDF values; absorption 0 in the PDF |
| Air entrainment | Off | PDF: "No air entrainment is required" |
| Production data | Off | PDF: no statistical data |
| w/c | **0.48 (engine override)** | PDF Step 4 selects 0.48 "from past experience" |

The engine was called with `w_c_ratio=0.48` to isolate Steps 3–7. This is necessary because the PDF's 35 MPa is a mean strength, while the app's strength input is a characteristic strength and therefore applies ACI 318 overdesign (35 → f′cr 44 → w/c 0.3836). That overdesign is correct for a characteristic-strength input; it is not comparable to the PDF's mean-strength statement. See clause 5.2.

### 2.2 Example 1 result

**Engine call**

```
ACI211MixDesign().design(MixDesignInput(
    code="aci211", target_strength_mpa=35.0, characteristic_strength_mpa=35.0,
    slump_mm=50.0, w_c_ratio=0.48, has_production_data=False,
    cement=Cement(type=CementType.TYPE_I, specific_gravity=3.15),
    fine_aggregate=FineAggregate(specific_gravity=2.58, fineness_modulus=2.60,
                                 absorption_percent=0.0, moisture_content_percent=0.0),
    coarse_aggregate=CoarseAggregate(specific_gravity=2.64, nominal_max_size_mm=20,
                                     bulk_density_kg_m3=1600.0,
                                     absorption_percent=0.0, moisture_content_percent=0.0),
    air_entrained=False,
))
```

**App result:** water **187.0**, cement **389.6**, coarse aggregate **1024.0**, fine aggregate **726.1**, air **2.0%**, density **2326.7 kg/m³**.

**Absolute-volume closure:** `0.187000 + 0.123677 + 0.387879 + 0.281444 + 0.020000 = 1.000000 m³` — the app closes the 1 m³ balance exactly at 6 d.p. using the unrounded cement mass (389.583 kg; the displayed 389.6 and 726.1 give 0.999995).

The offscreen UI (`ConcreteMixTab`, `QT_QPA_PLATFORM=offscreen`) reproduces the water (187.0) and air (2.0%) values for the same inputs, but cannot reproduce the rest of this line: it has no ACI w/c override, so 35 MPa *characteristic* strength yields f′cr 44 and w/c 0.3836; with absorptions FA 1.0% / CA 0.5% the design masses become cement 487.5, CA 1029.1, FA 641.0. See clause 5.2.

---

## 3. Pass/fail matrix

| # | Check | Reference | Expected | App | Verdict |
|---|---|---|---|---|---|
| A1 | Slump propagates unchanged | ACI 211.1-22 Table 5.3.1 / Step 1 | 50 mm | 50 mm | **PASS** |
| A2 | 20 mm NMSA maps to the ¾ in. column | Tables 5.3.3 and 5.3.6 | 20 mm (¾ in.) | 20 mm | **PASS** |
| A3 | Water content, 20 mm, 50 mm slump, non-air | Table 5.3.3 | 315 lb/yd³ = 186.9 → 187 kg/m³ | **187.0 kg/m³** | **PASS** |
| A4 | Entrapped air, 20 mm, non-air | Table 5.3.3 | 2.0% | **2.0%** | **PASS** |
| A5 | w/c at the PDF's strength | Table 5.3.4 | 0.48 at 5000 psi (34.5 MPa); ≈0.475 at 35 MPa | 0.48 with override; 0.4749 at 35 MPa | **PASS** |
| A6 | Cement = water ÷ w/c | clause 5.3.5 | 187 / 0.48 = 389.58 | **389.6 kg/m³** | **PASS** |
| A7 | CA = Table 5.3.6 volume × rodded density × (1 + A) | clause 5.3.6 | 0.64 × 1600 × 1.00 = 1024.0 | **1024.0 kg/m³** | **PASS** |
| A8 | FA by absolute volume | clause 5.3.7 | 726.1 (app's other masses) | **726.1 kg/m³**, ΣV = 1.000000 | **PASS** |
| A9 | Density = sum of constituent masses | clause 5.3.8 | 187.0 + 389.6 + 1024.0 + 726.1 | **2326.7 kg/m³** | **PASS** |
| A10 | Target strength, no production data | ACI 318 Table 26.4.3.1(b) / 211.1-22 Table 4.7.4.1 | 35 MPa = 5076 psi > 5000 psi → 1.10×35 + 4.83 = 43.33 → 44 (app ceil policy) | **44 MPa** | **PASS** (standard; PDF 35 is a mean) |
| A11 | Moisture formula with **total** MC | clause 5.3.9.1 / clause 9.2.8 | 1956 / 1377 / 202 lb/yd³ | **1955.8 / 1376.8 / 202.4** | **PASS** |
| A12 | Moisture input basis (UI/API vs formula) | clause 4.7.8.3, clause 5.3.9.1 | one consistent basis; 0% = SSD as labelled | formula expects total; UI supplies free; **0% is oven-dry** | **FAIL** |
| A13 | ACI w/c (or f′cr) entry in the UI | clause 4.7.2 / clause 5.3.4 | user can specify 0.48 | engine accepts; **UI has no ACI control** | **FAIL** (coverage) |
| A14 | PDF Example 2 full run | Tables 5.3.3/5.3.6, MR→f′c | 75 mm NMSA, 4.7 MPa MR | 75 mm not offered; no MR input | **NOT TESTABLE** |
| A15 | Example 2 target strength | ACI 318 Table 26.4.3.1(b) | 34.5 MPa = 5003 psi > 5000 psi → 1.10×34.5 + 4.83 = 42.78 → 43 | **42.78 → 43** | **PASS** (ceil policy) |
| A16 | Example 2 air-entrained w/c at 42.8 MPa | Table 5.3.4 | 0.33 at 6000 psi; table gives <0.33 at 7000 psi (app stores the 0.33 boundary) | **0.33** (conservative upper bound) | **PASS** |
| A17 | Units and reporting | — | MPa, mm, kg/m³ | MPa, mm, kg/m³ | **PASS** |

---

## 4. Evidence — the passes

### 4.1 Water and air (A3, A4)

ACI 211.1-22 Table 5.3.3, ¾ in. column, 1–2 in. slump, non-air-entrained: **315 lb/yd³**. The app's table stores the converted entry **187 kg/m³** (315 × 0.5933 = 186.9), and the entrapped-air row is **2%**. Both match the 2022 standard.

The PDF's **190 kg/m³** is the metric value from the **1991** table (Table 14.5, 19 mm column). It is not a 2022 value, so the app should not be changed to 190. This is an edition difference, not a defect.

### 4.2 w/c and cement (A5, A6)

ACI 211.1-22 Table 5.3.4 gives:

| f′c (psi) | f′c (MPa) | Non-air w/c |
|---|---:|---:|
| 5000 | 34.5 | 0.48 |
| 4000 | 27.6 | 0.57 |

The PDF's "35 MPa" (5076 psi) is read off the **5000 psi** row, so 0.48 is the correct tabulated value for that row. The app returns 0.48 at 34.5 MPa and 0.4749 at 35 MPa (linear interpolation between 34.5 and 41.4 MPa). With the 0.48 override, cement = `187.0 / 0.48 = 389.58`, matching the PDF's `190 / 0.48 = 395.83` except for the water-table edition.

### 4.3 Coarse aggregate (A7)

`0.64 × 1600 = 1024.0 kg/m³`. The PDF prints **1020**; that is an arithmetic error in the slide, not a different table value. The app's factor (0.64 at FM 2.60) is exactly Table 5.3.6.

With a non-zero absorption the app correctly converts the dry-rodded mass to SSD: `0.64 × 1600 × (1 + 0.5%) = 1029.1 kg/m³`, per clause 5.3.6. The PDF's Example 1 does not state an absorption, so the test used 0.

### 4.4 Fine aggregate and density (A8, A9)

The app's absolute-volume closure:

```
V_water   = 187.0 / 1000            = 0.187000
V_cement  = 389.583 / (3.15 × 1000) = 0.123677
V_CA      = 1024.0 / (2.64 × 1000)  = 0.387879
V_air     = 2.0 / 100               = 0.020000
V_FA      = 1 − sum                 = 0.281444
m_FA      = 0.281444 × 2.58 × 1000  = 726.13
ΣV        = 0.187000 + 0.123677 + 0.387879 + 0.281444 + 0.020000
          = 1.000000
```

Sum of masses = **2326.7 kg/m³**. The volumes recomputed from the PDF's printed masses sum to **0.9892 m³**, not 1.0000, because of the CA-volume typo; see clause 6.

### 4.5 Target strength (A10)

ACI 318 Table 26.4.3.1(b) / 211.1-22 Table 4.7.4.1 has three bands. 35 MPa = 5076 psi, just above the 5000 psi break (34.47 MPa), so the over-5000 psi rule applies: `f′cr = 1.10 f′c + 700 psi = 1.10 × 35 + 4.83 = 43.33 MPa`, rounded up by project policy to **44 MPa**. The app's Step 1 agrees.

The PDF's 35 MPa is explicitly a **mean** strength, so the PDF does not need this overdesign. The app's input is a characteristic strength; applying the ACI 318 margin is correct. This is an input-interpretation difference, not a calculation error. It is also why the 0.48 override is needed to reproduce Steps 3–7.

For reference, the PDF's adapted Table 7 states the over-5000 psi rule as `f′c + 1400 psi` (+9.6 MPa), which would give 44.65 → 45 MPa; the app follows the current Table 4.7.4.1 (`1.10 f′c + 700 psi`). This is a table-edition difference, not an app error.

### 4.6 Moisture with total moisture (A11)

ACI PRC-211.1-22 clause 9.2.8 (Example 1) uses **total** moisture content of 2% (CA) and 6% (FA), with absorptions 0.5% and 0.7%:

| Item | Standard | App |
|---|---:|---:|
| Batched CA | 1956 lb/yd³ | **1955.8** |
| Batched FA | 1377 lb/yd³ | **1376.8** |
| Water to batch | 202 lb/yd³ | **202.4** |

This confirms the engine's `(1 + MC) / (1 + A)` formula and the trial workbook are correct **when MC is total moisture**. That is exactly the problem with A12: the UI does not supply total moisture.

---

## 5. Failures and gaps

### 5.1 A12 — Moisture input contract (real defect)

**What the app says the input is**

- `app/widgets/concrete_tab.py` (FA tooltip, ACI branch):
  > "Free moisture on fine aggregate above SSD condition. … 0% = SSD condition (no adjustment needed) … FA SSD = 1124 lb/yd³, field moisture = +3% → FA field = 1124 × 1.03 = 1158 lb/yd³."
- Same wording for coarse aggregate.
- `docs/USER_MANUAL.md` lines 266 and 278: "FA Free Moisture (%)", "CA Free Moisture (%)".
- `concrete_mix/__init__.py` (the `design_mix_simple` docstring): "fine_agg_moisture: Fine aggregate free moisture (%)", "coarse_agg_moisture: Coarse aggregate free moisture (%)".

**What the model and formula actually expect**

- `concrete_mix/models/materials.py` lines 118–123:
  > "ACI clause 4.7.8: both are water mass / oven-dry aggregate mass, not signed free moisture."
- `concrete_mix/engine/moisture_correction.py`:
  ```
  w_batched = w_SSD × (1 + MC%) / (1 + A%)
  ```
  where the docstring correctly says **MC is total (free + absorbed) moisture**.

**Consequence 1 — the default is not SSD.**

Design at 35 MPa, no data, absorptions 1.0% (FA) and 0.5% (CA), moisture left at the documented **0% = SSD**:

| Quantity | Design (SSD) | App field at 0% moisture | Correct at 0% free (SSD) |
|---|---:|---:|---:|
| Water | 187.0 | **198.5** | 187.0 |
| Coarse aggregate | 1029.1 | **1024.0** | 1029.1 |
| Fine aggregate | 641.0 | **634.6** | 641.0 |

The app treats `MC = 0` as **oven-dry**, so it subtracts 1% / 0.5% of aggregate and adds **+11.5 kg/m³ of water**. A user who follows the "0% = SSD" label gets a batch that is too wet and short of aggregate.

**Consequence 2 — the PDF's Example 2 Step 8 is not reproduced.**

PDF inputs: SSD CA 1416, SSD FA 511, water 122, free moisture 1.5% (CA) and 5% (FA) above SSD. The PDF states no absorption; the app requires one, so the test used the app defaults CA 0.5% / FA 1.0%. (A correct free-moisture implementation would be independent of absorption, because the free moisture is defined on the SSD mass.)

| Quantity | PDF (free, above SSD) | App with those inputs | Correct free-moisture result |
|---|---:|---:|---:|
| Batched CA | 1437 | **1430.1** | 1437.2 |
| Batched FA | 537 | **531.2** | 536.6 |
| Water to batch | 75 | **87.7** | 75.2 |

Against the exact free-moisture values the error is **−7.1 kg CA, −5.3 kg FA, +12.5 kg water** per m³; against the PDF's whole-kg printout (1437 / 537 / 75) it reads −6.9 / −5.8 / +12.7. The water error is 10.2% of the 122 kg/m³ design water (6.7% of the app's 187 kg/m³ Example 1 water).

**Consequence 3 — IS shares the same contract; DOE shares the field.**

`IS10262` calls the identical `correct_for_moisture` / `adjust_water_for_aggregate_moisture` pair with the same `moisture_content_percent` fields (`is10262.py` lines ≈860–891), so the mismatch applies there too, although only ACI was in scope for this test. DOE's design engine does not moisture-correct at all; its **trial workbook** (`doe_trial.py` lines 389–441) reads the same fields as total moisture on the oven-dry mass — "air-dried needs moisture at or below absorption", "surface-wet needs moisture above absorption" — so a "free moisture" value entered for a DOE trial is interpreted on a different basis again, with the moisture-condition combo as the only guard. Separately, `app/widgets/material_quantify_tab.py` tells the user "Field mass = SSD mass × (1 + free moisture%)", the **free** convention, so the app currently carries two different field-mass conventions.

**Why the existing tests did not catch it**

- `tests/test_aci_trial.py` passes **total** moisture (2%/6%) directly to the engine, which is correct and passes.
- No test asserts the user-facing contract: "0% free moisture must leave the SSD masses unchanged."
- No test drives the UI moisture spin boxes and compares the resulting field masses with the PDF.

**What to do**

1. **Pick one basis and make the boundary explicit.** Recommended: keep the UI/API wording "free moisture above SSD" (it matches the PDF, the tooltips, and the 0% = SSD default), and convert to the model's total-moisture basis at the boundary:
   ```
   MC_total = A + (1 + A/100) × f_free
   ```
   This is exact for free moisture expressed on the SSD mass (the PDF's convention). It gives:
   - `f = 0` → `MC = A` → batched = SSD, water = design water;
   - PDF Ex2 → CA 1437.2, FA 536.6, water 75.2.

   **Scope caveat:** this conversion is the ACI/PDF convention. IS 10262 defines free moisture as `total − absorption` in percentage points on the oven-dry mass, so an IS boundary would be `MC_total = A + f_free` with its own field-mass ratio; do not apply the ACI formula to IS without checking. DOE's trial workbook already consumes total MC.
2. Alternative: relabel the inputs and docs to **"Total moisture content (ASTM C566)"**, keep the existing formula, and change the default from 0% to the absorption value (SSD). This is a larger UX change because 0% would then mean oven-dry.
3. Apply the conversion in **one** place used by both the UI and `design_mix_simple`, or document that `MixDesignInput.moisture_content_percent` is total and keep free moisture only at the public boundary. Do not leave two conventions.
4. Allow the free-moisture input to go **negative down to `−100·A/(100+A)`** (oven-dry aggregate), or remove the "negative = dry" branch from the tooltip. For A = 1.0% that bound is −0.990%, and for A = 0.5% it is −0.4975%; the current spin range is 0–20, so the advertised dry-aggregate case is unreachable.
5. Add regression tests:
   - 0% free moisture with A = 1.0/0.5 → field masses = SSD, water = design water (no Step 9 change).
   - PDF Example 2 Step 8 → 1437 / 537 / 75 within 1 kg.
   - ACI clause 9.2.8 total-moisture path → 1956 / 1377 / 202 (already covered).
   - A UI-level test that reads the spin boxes and checks the field result, not just the engine.
6. Update `docs/USER_MANUAL.md`, all moisture/absorption tooltips, and the `design_mix_simple` docstring to state the chosen basis and the formula.

**Files involved**

- `app/widgets/concrete_tab.py` — tooltips (≈686–786), moisture spin ranges (≈1831, 1945), pass-through (≈3790–3793)
- `concrete_mix/models/materials.py` — validator comment (≈118–123)
- `concrete_mix/engine/moisture_correction.py` — formula (≈15–31, 43–69)
- `concrete_mix/__init__.py` — `design_mix_simple` docstring
- `app/widgets/material_quantify_tab.py` — field-mass tooltips (≈407, 433)
- `docs/USER_MANUAL.md` — lines 266, 278
- `tests/test_aci_trial.py` — existing total-moisture coverage

### 5.2 A13 — No ACI w/c or f′cr entry in the UI (coverage gap)

The PDF's Step 4 selects **w/c = 0.48 from past experience**. ACI 211.1-22 clause 4.7.2 explicitly contemplates a w/cm specified by contract, and clause 5.3.4 allows a w/cm selected by strength or by established data.

- The **engine** supports it: `design_mix_simple(..., w_c_ratio=0.48)` and `MixDesignInput(w_c_ratio=0.48)` work.
- The **UI** does not: `max_wc_override_spin` is shown only for DOE (`setVisible(is_doe)`), and `w_c_ratio` is written into `kwargs` only in the DOE branch (`app/widgets/concrete_tab.py` ≈3253, 3898). The ACI branch never sends it.
- Consequence: entering 35 MPa in the ACI tab always produces f′cr 44 and w/c 0.3836 (cement 487.5), which cannot reproduce the PDF's 0.48 / 395 kg/m³. A user can only approximate it by back-solving f′c ≈ 26.7 MPa to get f′cr = 35, which is not discoverable.

**What to do:** add an ACI control for either
- **Specified w/c** (pass `w_c_ratio` in the ACI branch), or
- **Design for f′cr** (a mean-strength override that bypasses the Table 4.7.4.1 margin).

The first is smaller and matches the PDF; the second is more general for "mean strength" examples. Either one should be reflected in the result steps and the history record.

### 5.3 A14 — Example 2 is not executable (coverage gap)

PDF Example 2 needs:

| Requirement | PDF value | App |
|---|---|---|
| NMSA | 75 mm (3 in.) | App's ACI combo offers 10 / 20 / 40 mm only (12.5 mm is IS-only) |
| Strength input | 4.7 MPa flexural (M<sub>R</sub>) | No M<sub>R</sub> input; no MR→f′c conversion |
| CA volume | 0.78 at 75 mm / FM 2.75 | App table has no 75 mm row (standard Table 5.3.6 does); 0.78 is the FM 2.80 value — strict interpolation at 2.75 is 0.785 |
| Water | 122 kg/m³ at 80 mm air-entrained | App has no 75/80 mm column; 40 mm gives 148 kg/m³ |
| +10% CA for pavement | 1287 × 1.10 = 1416 kg | No automatic Table 5.3.6 "less workable" adjustment |
| Moisture | free 1.5% / 5% above SSD | Same A12 defect |

**What to do (optional, depends on intended scope):**

- Add the missing standard NMSA columns to the ACI water/air/CA tables and the combo: 25 mm (1 in.), 50 mm (2 in.) and 75 mm (3 in.), plus an exact 37.5 mm (1-1/2 in.) entry if the current 40 mm stand-in is to be replaced.
- Add a modulus-of-rupture input with the ACI 318 / K = 0.7–0.8 conversion, or document that pavement MR must be converted externally.
- Add the Table 5.3.6 note's ~10% increase for pavement/less-workable concrete as an explicit checkbox or factor.

If the project intentionally limits ACI NMSA to 10/20/40 (the three ASTM PSD bands in `AGENTS.md`), then document that Example 2 is outside the app's supported envelope rather than treating it as a failure. The PSD three-band rule does not by itself forbid additional **mix-design** NMSA columns, but the scope decision is the team's.

---

## 6. Source-document errors (do not "fix" the app for these)

The PDF is a useful teaching example but its arithmetic is not self-consistent. The following are **errors or loose statements in the source**, verified against its own numbers and the standard.

| # | Source statement | Correct value | Consequence |
|---|---|---|---|
| 1 | `0.64 × 1600 = 1020 kg/m³` | **1024 kg/m³** | CA mass is 4 kg low |
| 2 | `1020 / (2.64 × 1000) = 0.396 m³` | **0.3864 m³** | The printed 0.396 is a transposition; 0.396 m³ × 2640 = 1045.4 kg, not 1020 |
| 3 | Total volume except FA = `0.732 m³` | **0.722 m³** with 0.386 | The 0.732 uses the 0.396 typo |
| 4 | FA volume `1.000 − 0.732 = 0.268 m³`; FA `690 kg/m³` | **0.2782 m³; 717.9 kg/m³** | FA is ~28 kg low |
| 5 | Density `2295 kg/m³` | **2322.9 kg/m³** with its own water/cement/CA and balanced FA | Density is ~28 kg low |
| 6 | Aggregate masses labelled "dry" | ACI design weights are **SSD**; the calculation uses SSD SGs | Label is loose; the arithmetic uses SSD |
| 7 | "35 MPa (5076.31)" | 5076.31 psi is just the conversion of 35 MPa | Not a second strength |
| 8 | w/c `0.35` at 42.8 MPa, "quesstimate" | Table 9 gives **0.39 at 35 MPa** and a dash at 40 MPa; **0.35 is below every tabulated air-entrained value** | A guess beyond the table's range — richer and less workable than any listed mix, not an interpolation |

Two items that *look* like errors are not:

- Slide 29's **335 kg/m³** minimum cement is not in the body of Table 8 (282 / 324 / 354 / 366 kg/m³ for the 40/20/14/10 mm rows), but it **is** the table's footnote value for a very cold climate — exactly Example 2's exposure. The slide's check (349 kg/m³ designed ≥ 335 kg/m³ minimum) is therefore correct.
- Slide 18's "the table does not show the w/c ratio beyond 35 MPa" is true for the **air-entrained** column, whose 40 MPa cell is a dash; only the non-air column lists 0.42 at 40 MPa. The statement is imprecise, not contradictory.

For reference, recomputing each volume from the PDF's **printed masses** (rather than its rounded volume lines) gives:

```
0.190000 + 0.125397 + 0.386364 + 0.267442 + 0.020000 = 0.989203 m³
```

so the printed masses are about 1.1% under 1 m³. The PDF's own rounded volume lines (0.190 + 0.126 + 0.396 + 0.020 + 0.268) add to 1.000 by construction. The app's batch closes at 1.000000 m³.

**Do not change the app to match 1020, 0.396, 690, or 2295.** If a regression fixture is wanted, use the PDF's *procedure* with corrected arithmetic (or the standard's clause 9.2 example), not its printed totals.

---

## 7. What to fix, in priority order

| Priority | Item | Why | Effort |
|---|---|---|---|
| **P0** | Moisture basis (A12) | Produces wrong field water and aggregate weights; the documented 0% = SSD default is wrong | Medium — boundary conversion + labels/tests |
| **P1** | ACI w/c or f′cr entry (A13) | The PDF's Step 4 cannot be reproduced in the UI; ACI 211.1-22 clause 4.7.2 allows a specified w/cm | Small–medium |
| **P2** | 75 mm NMSA / MR / +10% CA (A14) | Example 2 cannot run; optional depending on supported envelope | Medium |
| **P3** | Doc/test cleanup | Prevent regression; align manual, tooltips, docstrings, and the two field-mass conventions | Small |

**Suggested acceptance test for P0**

```
Given FA absorption 1.0%, CA absorption 0.5%, and free moisture 0% / 0%,
when the ACI mix is calculated,
then field water == design water,
     field FA == design FA (SSD),
     field CA == design CA (SSD),
     and no "moisture-corrected water" step is emitted.

Given PDF Example 2's SSD masses (CA 1416, FA 511, water 122),
     free moisture 1.5% / 5%, absorptions 0.5% / 1.0%,
then field CA ≈ 1437 kg, field FA ≈ 537 kg, water to batch ≈ 75 kg.
```

---

## 8. Reproducibility notes

- The PDF conversion is `ACI-Mix-Design-Example-1.md`; slide numbers in this report refer to that file.
- The engine test used the repository's current working tree (`concrete_mix/codes/aci211.py` and `concrete_mix/codes/tables/aci_tables.py`), not a released wheel.
- The UI test used `QT_QPA_PLATFORM=offscreen` with a temporary `XDG_CONFIG_HOME`/`HOME` so it did not touch the user's settings or history database.
- No app code, test, or reference file was changed. The only additions are this report and the converted Markdown fixture.
- The working tree already contained unrelated uncommitted changes (custom window chrome and other work) before this test; they were not reverted or altered.

---

## 9. Verdict

**The ACI engine's proportioning arithmetic passes the standard.** Water, air, cement, coarse aggregate, fine aggregate, density, target strength, and the moisture formula (with total moisture) all match ACI PRC-211.1-22 / ACI 318. The PDF's differences are explained by its 1991 tables and by arithmetic slips in the slides, not by app errors.

**The app's moisture input contract fails.** The UI and public API advertise free moisture above SSD, but the model and formula require total moisture. This is not a cosmetic label issue: with the documented 0% = SSD default, the app adds about 11.5 kg/m³ of water and shortens the aggregate; with the PDF's Example 2 free moistures, it overstates batch water by about 12.5 kg/m³. Fix the boundary (recommended: `MC_total = A + (1 + A/100) × f_free`) and add the 0% / Example 2 regression tests before relying on the field-batch output.

**Two coverage gaps remain:** the ACI UI cannot accept a specified w/c or f′cr, and Example 2's 75 mm NMSA / flexural-strength input is outside the app's current envelope. Neither is a formula defect, but both should be either implemented or explicitly documented as out of scope.
