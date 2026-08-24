# CivilQntify v1.0.5 Release Notes

## 🚀 What's New in v1.0.5

### 📊 Particle Size Distribution (PSD) & Gradation Curve Enhancements
- **Gradation Plot Layout & Warning Clearance**:
  - Embedded `PSDResultPanel` inside a dedicated `QScrollArea` to ensure that results, charts, warning banners, and corrective recommendations never overlap or clip, regardless of screen resolution or window size.
  - Dedicated `_plot_group` exclusively to the chart canvas with proper minimum height and margins.
  - Placed the out-of-band warning banner and suggested adjustments banner below the plot group with clean vertical spacing.
- **$D_{10}$, $D_{30}$, and $D_{60}$ Characteristic Diameters**:
  - Automatically plots effective size ($D_{10}$), curvature size ($D_{30}$), and uniformity size ($D_{60}$) directly on the semi-log gradation curve when computed.
  - Draws straight reference lines from the % Passing axis ($10\%$, $30\%$, $60\%$) to the curve and vertical drop lines down to the Sieve Size axis.
  - Formats diameter annotations ($D_{10}$, $D_{30}$, $D_{60}$) with decimal precision matching standard sieve ranges ($\ge 10\text{ mm}$ to 1 d.p., $1\text{--}10\text{ mm}$ to 2 d.p., $< 1\text{ mm}$ to 2-3 d.p.).
- **$12.5\text{ mm}$ Coarse Sieve & Band Support**:
  - Integrated the standard $12.5\text{ mm}$ ($1/2\text{ in.}$) sieve into the coarse aggregate series (`COARSE_SIEVES`) per **IS 383:2016 Table 7** and **ASTM C33/C33M Table 3**.
  - Added the dedicated `$12.5\text{ mm}$ graded` reference band and updated intermediate limits for $10\text{ mm}$ and $20\text{ mm}$ nominal size bands.
  - Sieve analysis input tables and reference band dropdowns automatically include the $12.5\text{ mm}$ fraction.
- **Improved Gradation Conformance & Corrective blend recommendations**:
  - Enhanced calculation and visualization of Uniformity Coefficient ($C_u$), Coefficient of Curvature ($C_c$), out-of-band sieve indicators, and automatic blend adjustment suggestions.

### 🎨 UI/UX & Nomenclature Polish
- **Human-Readable Labels**: Replaced raw internal enumeration keys (e.g., snake_case exposure classes, aggregate shapes, cement types, and SCMs) with standardized, human-readable display names across the GUI, validation warnings, text reports, and PDF exports.
- **Two-Line Chart Titles**: Prevented title clipping for long aggregate standard references on compact displays.
- **Scrollable Results Panels**: Standardized scrolling behavior across all result panels (Mix Design, PSD, Material Quantification, and Cost Estimation).

### 📦 Packaging & Installation
- **Windows**: Standalone single-file executable `CivilQntify.exe` (no installation required).
- **Linux**: Debian package (`.deb` for Ubuntu/Debian/Mint) and RPM package (`.rpm` for Fedora/RHEL/CentOS).
- **Verified Compatibility**: Fully tested across Python 3.11/3.12/3.13 with 265 automated unit and integration tests.
