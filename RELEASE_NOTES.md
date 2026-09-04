# CivilQntify v1.0.9 Release Notes

## 🚀 What's New in v1.0.9

### 🖥️ Sidebar Resize Fix — Inputs Track the Splitter

- **Responsive input forms**: All sidebar forms (Mix Design, PSD sieve analysis, Material Quantification, Cost Estimation) now use wrapping form rows — fields stack below their labels when the pane narrows instead of clipping behind a horizontal scrollbar. The splitter handle tracks smoothly at any width, including mid-edit while typing (typed digits/suffixes no longer grow the form minimum and freeze the handle).
- **Shrinkable inputs**: Combo boxes, spin boxes, buttons, tables and labels across every sidebar got zero-minimum + expanding size policies, so nothing wedges the pane wider than the sidebar floor.
- **Decluttered option rows**: Redundant label + checkbox pairings (Mass concrete, Air entrainment, Prestressing, Manufactured sand) are now bare checkboxes with the detail in tooltips; long checkbox/group titles trimmed with standard-section citations preserved (`§5.7`, `§7.3`, `§11.2`).
- **Balanced splitter**: Window-resize growth is now shared between sidebar and results (1:2) instead of leaving the sidebar frozen.

### 📦 Platform & Testing

- **Version**: `1.0.9` (`app/version.py`)
- **Test Suite**: 728 automated unit and integration tests passing.

---

# CivilQntify v1.0.8 Release Notes

## 🚀 What's New in v1.0.8

### 📐 Material Quantification — Volume Visibility

- **Total Volume Moved to Top**: On both **Design Mix Proportions** and **Mix Ratios & Volume** subtabs, the `Total Volume` / `Total Volume of Work` and `Structural Elements` groups are now pinned to the top of the form, directly under the quantification mode selector. Users see the net volume basis for the bill before any per-m³ mix parameters, wastage or ratio factors.

### 🧱 IS 383:2016 Fine Aggregate — Standards Compliance

- **Table 9 Note 1 (crushed stone sand, 150 µm)**: The raised 20 % limit at 150 µm now correctly replaces the Clause 6.3 zone tolerance at that sieve — the 5 % / 10 % cumulative tolerance applies only to *other* sieves. Natural sand retains the Clause 6.3 allowance; crushed stone sand at 150 µm is evaluated against the hard 20 % cap (`concrete_mix/engine/grading.py`, `concrete_mix/codes/tables/is383_quality.py:220`).
- **Finer-than-75 µm / Mica checks**: Compliance cases updated for mixed vs. uncrushed vs. crushed source columns per IS 383 Table 2; `Mica content` and `including mica` total now correctly evaluated.

### 🎨 PSD & Compliance UI Polish

- **Quality sidebar**: `Wearing surfaces` and `Grade M65 or above` checkboxes relabeled to fit the 360 px sidebar floor; full Clause 5.4 limits now in tooltips (`app/widgets/psd_widget.py:2533`).
- **PSD widget stability**: Modal ASTM compliance dialog stubbed in tests; headless hinting disabled (`text.hinting = 'none'`) and shared `MPLCONFIGDIR` stabilised to prevent intermittent `FT_Render_Glyph` raster overflows on Qt 6.11 / matplotlib 3.11 (`tests/conftest.py`).
- **Test corrections**: Zone II band expectations updated to current IS 383 Table 9 limits; outlier PSD examples corrected.

### 📦 Platform & Testing

- **Version**: `1.0.8` (`app/version.py`)
- **Test Suite**: 518 automated unit and integration tests passing.

---

## Previous Releases

### v1.0.7

- **Mix Ratio Column**: Added "Ratio (C:FA:CA)" column to the IS 10262:2019 Clause 5.8 Trial Mixes dialog (cement = 1, e.g., `1 : 1.5 : 2.9`).
- **Water Volume Column**: Added "Water Vol (L)" column (`water = cement × W/C`) for direct water requirement visibility.
- **Exports**: Clipboard and CSV exports updated to include new columns.

### v1.0.6
- Material Quantification by Mix Ratio
- Standards-Compliant Concrete Mix Design Logic
- Standard-Specific Chemical Admixtures & SCM Proportions
- Platform Packaging & Release Pipeline
