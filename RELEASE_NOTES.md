# CivilQntify v1.0.6 Release Notes

## 🚀 What's New in v1.0.6

### 📐 Material Quantification by Mix Ratio
- **Mix Ratio Quantification Subtab**: Added a dedicated subtab within the Material Quantification interface allowing users to estimate cement bags, sand volume/weight, coarse aggregate volume/weight, and water directly from specified concrete mix ratios ($1:1.5:3$, $1:2:4$, $1:3:6$, or custom ratio) and volume of work.
- **Standard Density & Bag Factor**: Conforms to standard civil engineering constants with $1\text{ bag of cement} = 50\text{ kg} = 0.035\text{ m}^3$, cement density of $1440\text{ kg/m}^3$, and dry mortar/concrete volume conversion factors ($1.54\text{--}1.57$).

### 🏛️ Standards-Compliant Concrete Mix Design Logic
- **Structural Concrete Assumption ($\ge 25\text{ MPa}$)**:
  - Aligned all supported mix proportioning standards (**IS 10262:2019**, **ACI PRC-211.1-22**, and **BRE 331:1997 / DOE**) to enforce the structural concrete assumption with characteristic compressive strength $f_{ck} / f'_c / f_c \ge 25\text{ MPa}$.
- **Standard-Specific Aggregate Parameters**:
  - **BRE 331 (DOE)**: Strictly conforms to BRE 331 §1.2.4 & Table 2/3 classification (Uncrushed / Crushed). Aggregate shape dropdown is hidden when DOE is selected to avoid mixing non-DOE terms.
  - **IS 10262:2019**: Utilizes Table 6 aggregate shape adjustments and Table 5 coarse aggregate volume fractions.
  - **ACI 211.1-22**: Utilizes dry-rodded coarse aggregate bulk density and Fineness Modulus per Table 5.3.6.
- **IS 10262:2019 Section 5.8 Trial Mixes Guidance**:
  - Integrated interactive prompt and guidance dialog detailing Trial 1 (initial trial for slump and density), Trial 2 (water adjustment $\pm 3\%$), and Trials 3 & 4 (W/C variations $\pm 10\%$) with target strength curve interpolation per IS 10262 Clause 5.8.
- **PSD Integration with DOE and IS Standards**:
  - Fine aggregate Particle Size Distribution (PSD) analysis now automatically computes and exports the exact $\% \text{ passing } 600\ \mu\text{m}$ sieve required for BRE 331 Figure 6, as well as grading zones for IS 383 / IS 10262.

### 🧪 Standard-Specific Chemical Admixtures & SCM Proportions
- **Chemical Admixtures**:
  - **IS 10262:2019 (Annex G / IS 9103)**: Superplasticizers (PCE / SNFC / SMFC), Plasticizers (Lignosulfonate), Retarders, Accelerators, and Air-Entraining admixtures with Annex G water reduction rules and volumetric SG deduction.
  - **ACI 211.1-22 (§4.5, §6.3, ASTM C494 / ASTM C260)**: ASTM Types A, B, C, D, E, F (HRWRA $12\text{--}40\%$), G, and Air-Entraining admixtures with absolute volume deduction.
  - **BRE 331:1997 (§5.3 / BS 5075 / BS EN 934-2)**: Water-reducing plasticiser ($8\text{--}15\%$) and superplasticiser ($15\text{--}30\%$) integrated into free-water selection and batch weights.
- **Supplementary Cementitious Materials (SCM)**:
  - Standard-specific selection: IS 3812 / IS 455 / IS 15388 / IS 16354 (Fly ash, GGBFS, Silica fume, Metakaolin); ASTM C618 / C989 / C1240 (Fly ash Class F/C, Slag, Silica fume, Metakaolin); BRE 331 Part 3 (pfa with $k=0.30$, ggbs).

### 📦 Platform Packaging & Release Pipeline
- **Continuous Integration & Automated Builds**:
  - Windows standalone single-file binary (`CivilQntify.exe`).
  - Linux Debian package (`.deb` for Ubuntu/Debian/Mint) and RPM package (`.rpm` for Fedora/RHEL/CentOS).
- **Test Suite**: 348 automated unit and integration tests passing with 100% success.
