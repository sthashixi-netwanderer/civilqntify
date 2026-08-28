# CivilQntify — Agent Reference Guide

## Purpose

This file defines mandatory reference materials for any coding agent working on the CivilQntify project. **All agents must read and comply with this guide before making any changes to the application.**

---

## Extracted Reference Documents

The following documents have been extracted from authoritative concrete design standards. **Every code change, feature implementation, formula implementation, or UI update that involves concrete mix design logic MUST reference the relevant extracted document(s).**

| File | Source Standard | Description |
|------|----------------|-------------|
| [`31-ACI 211.1-22.md`](./31-ACI%20211.1-22.md) | ACI PRC-211.1-22 | Selecting Proportions for Normal-Density and High-Density Concrete — Guide |
| [`IS-10262-2019-NewConcreteMix-design.md`](./IS-10262-2019-NewConcreteMix-design.md) | IS 10262:2019 | Concrete Mix Proportioning — Guidelines (Bureau of Indian Standards) |
| [`BRE-331-1997-DOE-Mix-Design.md`](./BRE-331-1997-DOE-Mix-Design.md) | BRE 331:1997 | Design of Normal Concrete Mixes (British DOE Method) |

---

## Mandatory Agent Instructions

### Before Any Code Change

1. **Read this AGENTS.md** to understand which standards apply.
2. **Open the relevant reference document(s)** listed above and read the sections pertinent to the feature or fix you are working on.
3. **Verify formulas, tables, constants, and procedures** in your implementation against the extracted standards.

### When Implementing Concrete Mix Design Logic

| Task | Reference Document(s) |
|------|----------------------|
| Water-cement ratio calculations | Both ACI 211.1-22 (§5, §9), IS 10262:2019 (Table 8, Fig. 1) and BRE 331:1997 (Figure 4, §9.3) |
| Target strength calculations | IS 10262:2019 (Clause 7.1, Table 1, Table 2) and BRE 331:1997 (§5.1, Figure 3) |
| Aggregate volume/proportions | Both ACI 211.1-22 (§5.3, Tables 5.3.3–5.3.6), IS 10262:2019 (Table 10, Table 13) and BRE 331:1997 (Figure 6) |
| Coarse aggregate PSD / grading bands | ASTM C33/C33M Table 2, supported project mappings: 10 mm → Size 8, 20 mm → Size 67, 40 mm → Size 467; ACI 211.1-22 (§4.3.1, §A.4.2) |
| Water content selection | Both ACI 211.1-22 (Tables 5.3.3), IS 10262:2019 (Table 7, Table 12) and BRE 331:1997 (Table 3, Table 9) |
| Admixture/sp superplasticizer logic | IS 10262:2019 (Annex G), ACI 211.1-22 (§6.3) |
| Paste volume calculations | ACI 211.1-22 (§9.5, Example 4) |
| Cementitious efficiency factor | ACI 211.1-22 (§9.4, Example 3) and BRE 331:1997 (§9, efficiency factor k=0.30) |
| High-density concrete | ACI 211.1-22 (Appendix B) |
| Mass concreting | IS 10262:2019 (Annex F) |
| SCC (Self-Compacting Concrete) | IS 10262:2019 (Annex E) |
| Moisture adjustments for aggregates | Both ACI 211.1-22 (§9.3.8) and IS 10262:2019 (D-9.1 note) |
| Exposure classes / durability requirements | IS 10262:2019 (Table 3, Table 5 of IS 456) and ACI 211.1-22 (Tables 4.7.3a–4.7.3d) |
| Fly ash / SCM replacement | Both ACI 211.1-22 (§6), IS 10262:2019 (D-7, F-7) and BRE 331:1997 (§9, §10) |
| Trial batch procedures | Both ACI 211.1-22 (§9.3.9, Appendix A.5), IS 10262:2019 (§9, Annex D/E/F) and BRE 331:1997 (§5.6, §7) |

### When Modifying UI/Display of Mix Results

- Ensure all displayed values follow the correct unit systems (ACI uses lb/ft³ and lb/yd³; IS uses kg/m³).
- Verify that rounding conventions match the standards (e.g., IS 10262 rounds to nearest whole kg for cement).
- Confirm any labels, tooltips, or help text accurately reflect the referenced standard.

### PSD Tab — Standard-Specific Aggregate Rules

- The PSD tab must provide an explicit standard selector. Never combine one standard's sieve series with another standard's percentage-passing limits.
- **IS 383:2016:** use the Table 7 coarse sieve designations 80, 63, 40, 20, 16, 12.5, 10, 4.75, and 2.36 mm. Provide the Table 7 single-sized references (63, 40, 20, 16, 12.5, and 10 mm) and graded references (40, 20, 16, and 12.5 mm) with their exact stated limits.
- **ASTM C33/C33M:** the coarse input table must include every Table 2 laboratory-sieve column: 100, 90, 75, 63, 50, 37.5, 25.0, 19.0, 12.5, 9.5, 4.75, 2.36, 1.18 mm, and 300 µm.
- The project supports exactly three ASTM coarse reference bands: **10 mm**, **20 mm**, and **40 mm**. Do not add other ASTM size-number bands.
- Map the ASTM project references as follows: 10 mm → Size 8, 20 mm → Size 67, and 40 mm → Size 467.
- Fine aggregate must also follow the selected code: IS 383 grading Zones I–IV use a 10 mm top sieve; ASTM C33/C33M Table 1 uses a 9.5 mm top sieve and its own percentage-passing envelope.
- Use the exact minimum and maximum percentage-passing limits from the selected standard. A dash, ellipsis, or blank cell means no grading requirement: keep the sieve available for PSD input, but do not invent a 0% or 100% limit and do not use it for conformance checking.
- A visually smoothed standard band may be drawn between specified control points, but the curve must pass through every stated limit and must not overshoot, cross its opposite boundary, or imply requirements beyond the first and last specified sieves.

### When Adding New Features

- Check whether an existing section in the reference documents already covers the feature.
- Cite the standard section number in code comments or documentation where the logic originates.
- If the feature deviates from the standard, document the deviation explicitly in code comments.

---

## Key Tables & Formulas Quick Reference

### IS 10262:2019 — Target Strength

```
f'ck = fck + 1.65 × S    (if higher)
f'ck = fck + X            (if higher)
```
Use whichever value is **higher**.

### IS 10262:2019 — Volume Calculation Formula

```
Volume of material = (Mass of material) / (Specific gravity × 1000)
```

### ACI 211.1-22 — Absolute Volume Method

```
Volume of material (ft³) = Weight of material / (Specific gravity × 62.4 lb/ft³)
```

### ACI 211.1-22 — Cementitious Efficiency Factor

```
Efficiency Factor = Compressive Strength (psi) / Cementitious Material (lb)
```

### ACI 211.1-22 — Paste Volume

```
Paste Volume (%) = (Volume of cement + Volume of water) / Total concrete volume × 100
```

### BRE 331:1997 (DOE Method) — Target Strength, density & aggregate

```
fm = fc + k × s                                                 (Target mean strength)
wc_ratio = 0.5 - 0.370938 * R + 0.045970 * R^2                  (W/C ratio, where R = ln(target/ref))
density = 1144.3 * RD + 5.04 * W - 2.4590 * RD * W - 357.8      (Wet density of compacted concrete)
prop = 40.9545 - 0.1295 * nmsa + 2.5 * wc_class + 9.0909 * wc_ratio - 0.2591 * p600  (Fine agg %)
```

---

## Compliance Checklist

Before submitting any code change, verify:

- [ ] All formulas match the referenced standard(s).
- [ ] All constants (specific gravities, unit weights, etc.) are sourced from the reference documents or documented as project-specific overrides.
- [ ] Unit conversions are correct and consistent.
- [ ] Code comments reference the relevant standard section.
- [ ] UI labels and help text are accurate.
- [ ] No assumptions are made without citing the source.
- [ ] Trial batch logic follows standard procedures.

---

## Notes

- These reference documents are **read-only ground truth** for the application.
- If a conflict exists between ACI and IS standards, the application should respect the standard relevant to the user's selected code/region.
- Always prefer the extracted markdown files over raw PDFs for reference during development.
