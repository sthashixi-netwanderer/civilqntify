# CivilQntify v1.0.7 Release Notes

## 🚀 What's New in v1.0.7

### 📊 IS 10262 Trial Mixes Dialog Enhancements

- **Mix Ratio Column**: Added "Ratio (C:FA:CA)" column to the IS 10262:2019 Clause 5.8 Trial Mixes dialog, displaying the cement : fine aggregate : coarse aggregate ratio normalized to cement = 1 (e.g., `1 : 1.5 : 2.9`).
- **Water Volume Column**: Added "Water Vol (L)" column showing the water volume calculated from the W/C ratio (`water = cement × W/C`), providing direct visibility into water requirements for each trial mix.
- **Ratio Format**: Simplified ratio display to 1 decimal place for easier readability and direct field use.
- **Enhanced Exports**: Updated clipboard copy and CSV export to include the new ratio and water volume columns.

### 🏛️ Standards Implementation Verification

- **IS 10262:2019 Grading Zones**: Verified that the fine aggregate grading zones from IS 383:2016 Table 9 are correctly used to determine coarse aggregate volume fractions per IS 10262:2019 Table 5.
- **No Water Content Adjustment**: Confirmed that IS 10262:2019 does not prescribe water content adjustments based on fine aggregate grading zone (only affects CA volume fraction).

### 📦 Platform Packaging & Release Pipeline
- **Continuous Integration & Automated Builds**:
  - Windows standalone single-file binary (`CivilQntify.exe`).
  - Linux Debian package (`.deb` for Ubuntu/Debian/Mint) and RPM package (`.rpm` for Fedora/RHEL/CentOS).
- **Test Suite**: 348+ automated unit and integration tests passing with 100% success.

---

## Previous Releases

### v1.0.6
- Material Quantification by Mix Ratio
- Standards-Compliant Concrete Mix Design Logic
- Standard-Specific Chemical Admixtures & SCM Proportions
- Platform Packaging & Release Pipeline
