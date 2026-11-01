# BS 3892-1:1997 — Pulverized-Fuel Ash, Part 1: Specification for Pulverized-Fuel Ash for Use with Portland Cement

**Source standard:** BS 3892 : Part 1 : 1997 (Third edition, April 1997; effective 15 April 1997), British Standards Institution. ICS 91.100. ISBN 0 580 26785 7.

**Status in this project:** read-only ground truth. BRE 331:1997 clause 9.1 states *"For the purposes of this publication the pfa is assumed to comply with BS 3892:Part 1"* — this is the pfa grade behind the DOE engine's clause 9 design (`concrete_mix/codes/doe.py`, k = 0.30, Table 9 Part B) and the conformity evaluator (`concrete_mix/validation/bs3892.py`, dialog `app/widgets/bs3892_compliance_dialog.py`).

Transcribed from a licensed BSI copy (ACTS Lebanon, IHS, 17 May 2005 — Uncontrolled Copy). Figures B.1 and D.1 are transcribed from the scanned pages as descriptions; all tabulated values are verified against the printed tables.

---

## Foreword (extracts relevant to concrete use)

This British Standard supersedes BS 3892 : Part 1 : 1993. Pulverized-fuel ash (pfa) is extracted from the flue gases of furnaces fired by pulverized bituminous or other hard coal. It is a fine material, predominantly of spherical glassy particles, the bulk of which passes a 45 µm mesh sieve. To utilize its water reducing and pozzolanic properties, the finer fraction has been developed for specific use as a cementitious component of concrete with requirements additional to those of BS EN 450.

Pulverized-fuel ash has been used in composite cements conforming to BS 6588 and BS 6610 and as a cementitious component of concrete for many years. Guidance on its direct use in concrete can be found in BS 5328 : Part 1, BS 6543 and BS 8110 : Part 1.

The principal changes from the 1993 edition include: requirements specified as characteristic values (except strength factor and loss on ignition, which have absolute limits), conformity assessed by a statistical procedure for continuous inspection operated by the pfa producer (*autocontrol*, annex G) including the concept of major defects, and limits for acceptance inspection testing at delivery.

BS 3892 : Part 2 specifies a grade of pfa of higher sieve residue and loss on ignition to be used as a type 1 (nearly inert) addition in concrete. BS 3892 : Part 3 specifies a grade of pfa for use in cementitious grouts.

---

## Specification

### 1 Scope

This Part of BS 3892 specifies requirements for the composition, production and chemical and physical properties of processed pulverized-fuel ash (pfa) for use as a cementitious component in combination with Portland cement.

> NOTE. Requirements are specified as characteristic values except for strength factor and loss on ignition for which an absolute upper limit is given.

### 2 References

**2.1 Normative references** — incorporated by dated or undated reference (listed on page 16 of the standard): BS 12 : 1996, BS 1016 : Part 105 : 1992, BS 4551 : 1980, BS 6100 : Section 6.1 : 1984, BS 6588 : 1996, BS 6610 : 1996, BS EN 196-1 : 1995, BS EN 196-2 : 1995, BS EN 196-3 : 1995, BS EN 196-6 : 1992, BS EN 196-7 : 1992, BS EN 196-21 : 1992, ISO 565 : 1990, ISO 3310-1 : 1990.

**2.2 Informative references** — publications providing information or guidance; the latest editions apply.

### 3 Definitions

For the purposes of this Part of BS 3892, the definitions given in BS 6100 : Section 6.1 apply, together with the following.

- **3.1 characteristic value** — That value of a property corresponding to an acceptable percentage of defects, generally 10 %.
- **3.2 lot** — Quantity of pfa produced under conditions presumed uniform. After specified tests, this quantity is regarded as a whole, conforming or not conforming to the requirements.
- **3.3 spot sample** — Sample taken at the same time and from one and the same place relating to the intended tests. It can be obtained by combining one or more immediately consecutive increments.
- **3.4 hard coal** — Coal blend giving a gross calorific value of not less than 24 MJ/kg on a dry ash-free basis when tested in accordance with BS 1016 : Part 105.

### 4 Composition, production and processing

Pfa is a fine powder of mainly spherical glass particles having pozzolanic properties which shall consist essentially of reactive silicon dioxide (SiO₂) and aluminium oxide (Al₂O₃), the remainder being iron (III) oxide (Fe₂O₃) and other oxides.

Pfa shall be obtained by electrostatic or mechanical precipitation of dust-like particles from the flue gases of power station furnaces fired with pulverized bituminous or other hard coal. Ash from other coals or obtained by other means is not considered in this standard.

Pfa conforming to this specification shall be produced by processing the run-of-station pfa in such a way that it meets the requirements specified in clauses 5 to 12 and does not contribute materials that have a deleterious effect on the properties of fresh or hardened concrete or give rise to a health or safety risk.

### 5 Moisture content

The moisture content of the pfa shall be **not more than 0.5 %** when determined in accordance with the method described in annex C.

### 6 Fineness

The fineness of the pfa expressed as the proportion by mass retained on a 45 µm test sieve shall be **not more than 12.0 %** when determined in accordance with the method described in annex D.

> App note: BRE 331 clause 9.1 quotes the residue restriction as 12.5 % (the 1993-edition wording); the 1997 edition limits the characteristic value to 12.0 % and the Table G.3 major-defect allowance (+0.5 %) reaches 12.5 %. This project implements the 1997 values.

### 7 Particle density

The particle density of the pfa shall be **not less than 2000 kg/m³** when determined in accordance with 4.5.3 of BS EN 196-6 : 1992.

### 8 Water requirement

The water requirement of a combination by mass of **30 % pfa and 70 % Portland cement**, conforming to BS 12 : 1996 standard strength class 42.5, intimately mixed together shall be **not greater than 95 %** of that for the Portland cement alone when determined in accordance with the method described in annex E.

The alkali content of the Portland cement shall be not less than 0.5 % and not more than 0.9 % when determined in accordance with clause 7 of BS EN 196-21 : 1992.

### 9 Strength factor

The strength factor of the combination of pfa and Portland cement given in clause 8 shall have a **minimum limit value of 0.80** when determined in accordance with the method described in annex F.

### 10 Initial setting time

The initial setting time, when determined in accordance with BS EN 196-3, of a paste of standard consistence made from the combination of pfa and Portland cement given in clause 8 shall be **not less than** the initial setting time of the Portland cement when tested alone.

### 11 Soundness

The soundness of a paste made from the combination of pfa and Portland cement given in clause 8 shall have an **expansion of not more than 10 mm** when determined in accordance with BS EN 196-3.

### 12 Chemical composition

- **12.1 Sulfuric anhydride** — The content of sulfuric anhydride, SO₃, shall be **not more than 2.0 % (m/m)** when determined in accordance with clause 8 of BS EN 196-2 : 1995.
- **12.2 Loss on ignition** — The loss on ignition shall have a **maximum limit value of 7 % (m/m)** when determined in accordance with clause 7 of BS EN 196-2 : 1995 but using an ignition time of 1 h.
- **12.3 Chloride** — The chloride ion content shall be **not more than 0.10 % (m/m)** when determined in accordance with clause 4 of BS EN 196-21 : 1992.
- **12.4 Calcium oxide** — The calcium oxide content shall be **not more than 10.0 % (m/m)** when determined in accordance with clause 13 of BS EN 196-2 : 1995.

### 13 Marking

Pulverized-fuel ash shall be marked on the bag or the delivery note and on any certificate with: a) the name, trademark or other means of identification of the producer and the works at which the pfa was produced; b) the name of the material, i.e. pulverized-fuel ash; c) the number and date of this British Standard, i.e. BS 3892 : Part 1 : 1997.

> Marking the standard represents a producer's declaration of conformity — a claim by or on behalf of the producer. It is not third-party certification.

### 14 Information to be provided

**14.1 Test certificate** — If requested, results of the following tests on samples of the pfa relating to the material delivered: a) moisture content; b) fineness (45 µm sieve residue); c) particle density; d) water requirement; e) strength factor; f) initial setting time; g) soundness; h) the source of the Portland cement used in the tests d) to g) and its initial setting time and soundness (BS EN 196-3) and compressive strength at 28 days (BS EN 196-1) in the laboratory which is testing the pfa; i) sulfuric anhydride content; j) loss on ignition; k) chloride content; l) calcium oxide content.

**14.2 Additional information** — if requested at the time of ordering: a) variability of the chloride content when its mean level exceeds 0.05 % by mass; b) total acid soluble alkali content (7.5.2 of BS EN 196-21 : 1992 or XRF calibrated against NA.5.2 of BS EN 196-21 : 1992); c) water soluble alkali content; d) variability of the alkali content.

### 15 Sampling and testing for acceptance inspection at delivery

**15.1** When required by the purchaser, a spot sample shall be taken per 3.6 and 6.2, 6.3, 6.4 or 6.5 of BS EN 196-7 : 1992 before or at delivery; laboratory sample prepared and packed per clauses 8 and 9; sampling report per clause 10 of BS EN 196-7 : 1992. Testing may be delayed up to 5 weeks with confirmed continuous storage per 9.2.

**15.2** For water requirement, strength factor, initial setting time and soundness, the Portland cement source, CEN Standard sand and compaction procedure shall be those in use by the producer when the combination was originally tested, or as agreed between purchaser and producer.

**15.3** For chemical composition, sample preparation per clause 6 of BS EN 196-2 : 1995 except no magnet pass is required, and the pfa shall be dried per annex C.

**15.4** The limiting values applicable to acceptance inspection shall be **the same as the major defect levels, as defined in table G.3.**

---

## Annex A (informative) — Product guidance (extracts)

- **A.1 Safety warning** — dry pfa/cement precautions; wet-mortar dermatitis risk; eye/ skin first aid.
- **A.2 Storage** — waterproof bulk silos; bagged pfa stored clear of the ground, interlocked, not more than eight high, protected; use in order of receipt.
- **A.3 Heat generation** — pozzolanic reaction generates heat more slowly than Portland-cement hydration; a higher pfa proportion can limit both the rate and peak temperature.
- **A.4 Sulfate resistance** — considerable sulfate resistance is conferred where the pfa proportion is **between 25 % and 40 %** by mass of the combination (BS 5328 : Part 1, BRE Digest 363).
- **A.5 Alkali–silica reaction** — see BRE Digest 330, BS 5328 : Parts 1 and 4, Concrete Society TR 30, BS 8110 : Part 1, Department of Transport Specification for Highway Works.
- **A.6 Chloride ingress** — combinations with **at least 25 %** pfa are recognized in BS 6349 : Part 1 as beneficial against chloride attack of reinforcement.
- **A.7 Colour** — light to dark grey with brown shades; exposed-concrete colour may darken on mixing (carbon particles behave as pigment).

## Annex B (informative) — Equivalence of within-mixer combinations to Portland pulverized-fuel ash cements

**B.1 General** — Procedure for a combination of two materials manufactured, delivered and batched separately. A combination of pfa conforming to this standard and Portland cement conforming to BS 12 has chemical and physical properties conforming to BS 6588 or BS 6610 (provided the proportions are within the limits of those standards). For Portland cement of standard strength class 52.5 with initial setting time less than 60 min, conformity of setting time must be demonstrated for the declared range.

**B.2 Principles** — Conformity criteria are the same as BS 6588/BS 6610: the overall percentage of defects in the lot is estimated from test results; conformity requires the estimate not to exceed the acceptable percentage of defects (table 8 of BS 6588 : 1996 / table 6 of BS 6610 : 1996). Example procedure for BS 6588 strength class 32.5: a) strength-vs-proportion relationship per B.3; b) monthly composite tests over 6–12 months per B.4; c) standard deviation from weekly spot samples per B.5; d) limits on proportions per B.6. New pfa source: standard deviation from a minimum of 40 spot samples over ≥ 2 weeks.

**B.3 Strength vs blend proportions** — Composite pfa sample from ≥ 8 spot samples over ≥ 1 calendar month. Strength tests at 2 or 7 days and 28 days per BS EN 196 : Part 1 on blends:

| mass of pfa (%) | 0 | 20 | 35 | 50 |
|---|---|---|---|---|
| mass of Portland cement (%) | 100 | 80 | 65 | 50 |

Re-establish at least once every 2 years.

**B.4 Monthly tests** — Monthly bulk average pfa and each Portland cement source blended **30 : 70**; tests per BS EN 196 : Part 1 : 1995 at 2 or 7 days and 28 days. Mean strength x̄ = average of the most recent monthly tests over 6–12 months.

**B.5 Standard deviation** — Weekly spot samples of pfa and the nominated (most variable) Portland cement, blended 30 : 70, tested per BS EN 196 : Part 1; s from the period matching B.4. Nominated cement reviewed at least every 2 years.

**B.6 Limits for conformity to strength class 32.5** — Conformity criteria:

```
x̄ ≥ L + kA·s        and        x̄ ≤ U − kA·s
```

where kA is the acceptability constant (table G.4, identical to table 8 of BS 6588 : 1996; Pa = 10 % upper, Pa = 5 % lower), L the specified lower limit, U the specified upper limit, x̄ the B.4 mean strength and s the B.5 standard deviation. Construct the B.3 diagram of 28-day strength vs proportion; mark (L + kA·s) and (U − kA·s); mark the mean strength x̄ at proportion 30 : 70 and draw a line through it parallel to the relationship. Conformity is achieved at proportions where the line exceeds (L + kA·s) but is less than (U − kA·s). Repeat for the 2-day or 7-day results (no upper limit applicable); the conforming range must satisfy both.

**Figure B.1 — Determination of conformity limits for combinations** (transcribed from the scanned figure): a plot of **28-day strength** (y-axis) against **pfa × 100 / (pfa + Portland cement) — proportion %** (x-axis, marked 0, 50, 100). A falling curve, the *strength/proportion relationship*, runs from upper left; a second dashed curve, the *transposed relationship*, is the same curve shifted through the *mean strength* point (marked ×). Four horizontal lines cross the plot, top to bottom: *Upper strength limit U*; *U − k_A·s* (chain-dashed); *L + k_A·s* (chain-dashed); *Lower strength limit L*. Verticals dropped from the intersections of the transposed relationship with the two chain-dashed lines bound the *range of conforming proportions* (double-headed arrow on the proportion axis).

**B.7 Certificates** — issued monthly per pfa source with a specific Portland cement source; contents a)–g): identification, period, sampling means, blend composition, latest composite test results (including setting time and strength), derived blend compositions with the equivalent strength class, signature.

**B.8 Inspection testing** — spot samples per BS EN 196 : Part 7 : 1992; combined in the blend ratio in use; tested per clause 11 of BS 6588 : 1996 or clause 11 of BS 6610 : 1996.

## Annex C (normative) — Method of determining the moisture content

**C.1 Principle** — dried at (105 ± 5) °C; loss in mass by weighing.
**C.2 Apparatus** — ventilated electric oven (105 ± 5) °C; balance 100 g to 0.001 g; shallow container ≈ 20 g capacity, non-corrodible, to 150 °C; desiccator.
**C.3 Sample preparation** — remix a BS EN 196-7 spot sample, quarter down to 2 laboratory samples of ≈ 25 g.
**C.4 Procedure** — weigh ≈ 10 g to 0.01 g; dry (105 ± 5) °C for (60 ± 5) min; cool in desiccator; re-weigh.
**C.5 Calculation** — `Moisture content = (m − d)/d × 100` where m = mass before drying (g), d = mass dried (g).
**C.6 Reporting** — mean of two results to the nearest **0.1 %**.

## Annex D (normative) — Method of determining the fineness

**D.1 Principle** — wet sieving on a 45 µm test sieve; percentage by mass retained. Reference method: other methods must demonstrate equivalence; in dispute only this method applies.

**D.2 Apparatus** — sieve frame (cylindrical, 50 mm diameter, 75 mm depth, replaceable cloth); 45 µm stainless steel sieve cloth per ISO 565, free of grease/irregularities (ISO 3310-1); **spray nozzle** per D.2.3 and figure D.1; pressure gauge ≥ 160 kPa in 5 kPa steps; oven; balance; desiccator.

**Figure D.1 — Spray nozzle** (transcribed from the scanned figure, dimensions in millimetres): a nozzle of **ø17.5 mm** inside diameter with a spray head drilled with **17 holes of ø0.5 mm** — one hole central on the longitudinal axis; a further **eight holes at 6 mm centre-to-centre on a ø6 mm circle, drilled at about 5° from the longitudinal axis**; and an **outer row of eight holes at 11 mm centre-to-centre on a ø11 mm circle, at about 10° from the longitudinal axis**.

**D.3 Calibration of test sieve** — calibrate with the standard reference ash or BCR No. 69 CRM (correcting its stated 45 µm residue by adding 0.07 % absolute). Recalibrate at intervals not exceeding 100 tests or 3 months. Two results shall not differ by more than 0.3 % absolute. Correction factor `F = r₃/r₂` (r₂ = measured residue of reference material %, r₃ = known residue %), to the nearest 0.001; reject the cloth outside 0.800–1.200.

**D.4 Procedure** — transfer 1.0–1.1 g (to 0.001 g) of dried pfa to the calibrated sieve; wet gently; spray pressure 70–80 kPa, nozzle ≤ 15 mm above the frame; rotate at ≈ 1 rev/s for (60 ± 10) s; rinse with alcohol/acetone or blot; dry at (105 ± 5) °C to constant mass; cool; weigh the residue to 0.001 g (two methods given); repeat — two corrected values within 0.3 % absolute.

**D.5 Calculation** — `Corrected sieve residue = (r/m) × F × 100` (r = residue mass g, m = sample mass g, F = correction factor). Worked example from the standard: F = 1.053, m = 1.079 g, r = 0.102 g → (0.102/1.079) × 1.053 × 100 = **10.0 %**.

**D.6 Reporting** — mean of the two corrected values to the nearest **0.1 %**.

## Annex E (normative) — Method of determining the water requirement

**E.1 Principle** — the reduction in water required when pfa is added to a mortar is measured by comparing the flow of a control and test mix.

**E.2 Apparatus** — mixer per 4.4 of BS EN 196-1 : 1995; flexible scraper; balance to 1.0 g; flow table per annex A of BS 4551 : 1980 with mould and tamper.

**E.3 Materials** — CEN Standard sand (5.1 of BS EN 196-1 : 1995); reference Portland cement BS 12 : 1996 class 42.5; deionized or distilled water.

**E.4 Mix proportions** — Table E.1:

**Table E.1 — Mix proportions**

| Material | Control mortar | Test mortar |
|---|---|---|
| Reference Portland cement | (450 ± 1) g | (315 ± 1) g |
| Pfa to be tested | nil | (135 ± 1) g |
| CEN standard sand | (1350 ± 5) g | (1350 ± 5) g |
| Water | (225 ± 1) g | to give flow value ± 5 units of control mortar |

**E.5 Procedure** — mixing per 6.3 of BS EN 196-1 : 1995; flow per clause 12 of BS 4551 : 1980; lift the mould (60 ± 5) s after mixing; operate the table **15 times** in (15 ± 2) s (reduced from BS 4551's 25 — a NOTE permits omitting the consistence determination); adjust test-mortar water to a flow value ± 5 units of control.

**E.6 Calculation** — `Water requirement = X/225 × 100` where X = mass of water in the test mortar (g).

**E.7 Reporting** — to the nearest **1 %**.

## Annex F (normative) — Method of determining the strength factor

**F.1 Principle** — the strength of a control mortar at 28 days is compared to the strength of a test mortar containing the pfa at the same age.

**F.2 Apparatus** — as BS EN 196-1 : 1995 for compressive strength. **F.3 Materials** — as E.3. **F.4 Mix proportions** — as table E.1.

**F.5 Procedure** — after mixing per annex E and within (60 ± 5) s of the flow test, return the mortar to the uncleaned bowl and remix (30 ± 3) s at low speed; prepare specimens per 7.2 and clause 8 of BS EN 196-1 : 1995; test a minimum of four half prisms at 28 days per clause 9.

**F.6 Calculation** — `Strength factor = A/B` (A = test-mortar strength N/mm², B = control-mortar strength N/mm²), to the nearest **0.01**. **F.7 Reporting** — to the nearest 0.01.

## Annex G (informative) — Conformity criteria

**G.1 Introduction** — a statistically formulated conformity criterion includes: a) requirements as characteristic values (clauses 5 to 12); b) the acceptable percentage Pa of defects — the **10 % fractile** (or, for the strength factor, the **5 % fractile**); c) the probability of acceptance of a non-conforming lot (consumer's risk, **5 %** for continuous inspection). Additionally (G.1.2), pfa with one or more **major defects** does not conform (G.6).

**G.2 Application** — conformity is continuously assessed by the pfa producer (autocontrol); series of samples over not less than 6 months and not more than 12 months (new production: as declared, ≥ 2 weeks).

**G.3 General procedure** — continuous inspection with spot samples per BS EN 196-7 : 1992; an observed value outside clauses 5 to 12 is a **defect**; minor vs major defects are distinguished.

**G.4 Conformity criteria** — the overall percentage of defects is estimated from the results; conformity requires the estimate not to exceed the acceptable percentage (for calculation, the acceptability constant kA is used — G.7).

**Table G.1 — Minimum testing frequencies**

| Property | Number of samples |
|---|---|
| Fineness, Water requirement, Strength factor, Loss on ignition | 2 per week |
| Initial setting time, Soundness | 1 per week |
| Moisture content, Particle density, Sulfuric anhydride, Chloride, Calcium oxide | 1 per month |

**Table G.2 — Parameters determining the conformity procedure** (physical and chemical properties, all limits): continuous inspection procedure by attributes (by variables is allowed); percentage of defects Pa = **10 %**; consumer's risk = **5 %**.

**G.5 Physical and chemical properties** — assessed one property at a time, by attributes (variables allowed, preferable for initial setting time and chloride near the limit).

**G.6 Limits for major defects** — a quantity of pfa yielding one or more major-defect samples does not conform. A major defect is a deviation from clauses 5 to 12 so large that usability is likely to be reduced and in extreme cases failure may be produced. If a test result deviates by **more than** the value in table G.3, it is a major defect.

**Table G.3 — Major defects** (deviation from the clauses 5–12 requirements, in excess of):

| Property | Deviation in excess of |
|---|---|
| Moisture content | + 0.1 % |
| Fineness | + 0.5 % |
| Particle density | − 50 kg/m³ |
| Water requirement | + 2 % |
| Initial setting time | − 15 min |
| Soundness | + 1 mm |
| Sulfuric anhydride content | + 0.5 % (m/m) |
| Chloride content | + 0.01 % (m/m) |
| Calcium oxide content | + 1.0 % (m/m) |

**G.7 Sampling plans** — a) continuous inspection by variables: x̄ − kA·s ≥ L and x̄ + kA·s ≤ U; b) by attributes: cD ≤ cA (defect count vs acceptable number).

**Table G.4 — Acceptability constant kA**

| n | Pa = 5 % | Pa = 10 % |
|---|---|---|
| 40 to 49 | 2.13 | 1.70 |
| 50 to 59 | 2.07 | 1.65 |
| 60 to 79 | 2.02 | 1.61 |
| 80 to 99 | 1.97 | 1.56 |
| 100 to 149 | 1.93 | 1.53 |
| 150 to 199 | 1.87 | 1.48 |
| ≥ 200 | 1.84 | 1.45 |

**Table G.5 — Acceptable number of defects cA**

| n | cA |
|---|---|
| 0 to 39 | 0 |
| 40 to 54 | 1 |
| 55 to 69 | 2 |
| 70 to 84 | 3 |
| 85 to 99 | 4 |
| 100 to 109 | 5 |

NOTE. If n ≥ 110, cA = 0.075 (n − 30).

---

## List of references (normative)

BS 12 : 1996 *Specification for Portland cement* · BS 1016 : Part 105 : 1992 *Gross calorific value of coal and coke* · BS 4551 : 1980 *Methods of testing mortars, screeds and plasters* · BS 6100 : Section 6.1 : 1984 *Binders* · BS 6588 : 1996 *Specification for Portland pulverized-fuel ash cements* · BS 6610 : 1996 *Specification for pozzolanic pulverized-fuel ash cement* · BS EN 196-1 : 1995 *Determination of strength* · BS EN 196-2 : 1995 *Chemical analysis of cement* · BS EN 196-3 : 1995 *Determination of setting time and soundness* · BS EN 196-6 : 1992 *Determination of fineness* · BS EN 196-7 : 1992 *Methods of taking and preparing samples of cement* · BS EN 196-21 : 1992 *Determination of the chloride, carbon dioxide and alkali content of cement* · ISO 565 : 1990 · ISO 3310-1 : 1990.

Informative: BS 3892 : Part 2 : 1984 · BS 5328 : Parts 1 (1997) and 4 (1990) · BS 6349 : Part 1 : 1984 · BS 6543 : 1985 · BS 8110 : Part 1 : 1997 · BS EN 450 : 1995 · DD ENV 197-1 : 1994 · BRE Digests 362, 363, 330 · Concrete Society TR No. 30 · Department of Transport Specification for Highway Works.

---

## Where this standard is implemented in the app

| Standard clause | Implementation |
|---|---|
| Clauses 5–12 characteristic values | `concrete_mix/validation/bs3892.py` → `evaluate_bs3892_pfa()` |
| Table G.3 major defects / G.6 | `MAJOR_DEFECT_ALLOWANCE` + `major_defects()` in the same module |
| 15.4 acceptance limits = G.3 levels | failure details and dialog note (`app/widgets/bs3892_compliance_dialog.py`) |
| Annexes C–F methods, E.1 proportions | dialog tooltips; reporting precision (0.1 % / 1 % / 0.01) |
| BRE 331 clause 9 use of this grade | `concrete_mix/codes/doe.py` pfa path (k = 0.30, Table 9 Part B, C6–C9) |
