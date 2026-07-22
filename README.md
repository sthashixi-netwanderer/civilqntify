# CivilQntify 🏗️📐

**CivilQntify** is a production-grade Python desktop and CLI application designed for **Concrete Mix Design**, **Structural Material Quantification**, and **Construction Cost Estimation**. 

Built for civil engineers, concrete technology specialists, and quantity surveyors, CivilQntify automates mix proportioning according to international concrete design standards (ACI, IS, DOE/BRE), analyzes aggregate particle size distributions (PSD), calculates precise material bills for structural elements, and provides real-time supplier cost estimation.

---

## 🌟 Key Features

### 1. Concrete Mix Proportioning Engine
- **ACI 211.1-22 Method** (*American Concrete Institute*): Standard absolute volume method for normal & high-density concrete, incorporating w/cm ratios, air content, paste volume, and slump adjustments.
- **IS 10262:2019 Method** (*Bureau of Indian Standards*): Target mean strength calculations, exposure class recommendations (IS 456), superplasticizer reductions, and mineral admixture (Fly Ash/GGBS) replacements.
- **BRE 331:1997 / DOE Method** (*British Department of the Environment*): Compressive strength curves, wet density estimations, and fine aggregate percentage proportioning.
- **Compressive Strength Prediction**: Reverse calculations to estimate expected 28-day strength from w/c ratios.

### 2. Particle Size Distribution (PSD) & Grading Band Analysis
- Automated sieve analysis and fineness modulus calculations.
- Grading band compliance checking (IS 383 Zones I–IV, ACI/ASTM C33, DOE bands).
- Interactive PSD grading curve visualizer using Matplotlib embedded in PySide6.

### 3. Structural Material Quantification
- Calculates required cement, fine aggregate, coarse aggregate, water, and rebar for:
  - **Slabs** (Solid, Ribbed/Waffle)
  - **Beams** & **Columns**
  - **Footings** (Isolated, Combined, Raft)
  - **Walls** & **Retaining Walls**
  - **Staircases**
- Wastage factor adjustments and volume transfer directly into cost estimation.

### 4. Cost Estimation & Live Pricing Sync
- Calculates material item cost breakdowns and total budget requirements.
- Integration with shared **Google Sheets Live Price Sheet Service** (`gspread`) to automatically fetch real-time local supplier prices.
- Editable local price overrides and currency formatting.

### 5. Live Weather Integration
- Real-time weather monitoring for construction sites via WeatherAPI.
- Concreting advice based on local temperature and relative humidity (cold weather / hot weather concreting precautions).

### 6. Exporting & Reporting
- Professional PDF report generation via ReportLab with embedded charts, input summaries, and step-by-step proportioning calculations.
- CSV and JSON exports for site logs and historical audit trails.

---

## 📁 Project Structure

```
civilqntify/
├── app/                        # PySide6 GUI Application
│   ├── main.py                 # PySide6 GUI entry point
│   ├── pricing/                # Google Sheets live pricing integration
│   ├── resources/              # App icons, SVG assets, and styling resources
│   ├── styles.py               # Dark/Light modern theme stylesheet tokens
│   ├── unit_preferences.py     # Metric / Imperial unit management
│   ├── weather/                # WeatherAPI integration and city feeds
│   ├── widgets/                # UI Tabs (Concrete, Material Quantify, Cost, PSD, History)
│   └── workers/                # QThread workers for async background processing
├── concrete_mix/               # Core Concrete Mix Design Engine
│   ├── codes/                  # Standard-specific logic (aci211.py, is10262.py, doe.py)
│   ├── engine/                 # PSD, Grading, Volume, Moisture correction engines
│   ├── estimators/             # Carbon footprint, cost, strength prediction estimators
│   ├── export/                 # PDF, CSV, JSON export generators
│   ├── models/                 # Dataclass models (MixInput, MixResult, Materials)
│   └── validation/             # Input range and standard limits validation
├── material_quantify/          # Core Material Quantification Engine
│   ├── engine/                 # Quantity calculator for structural elements
│   └── models/                 # Bill of materials and transfer models
├── history/                    # Local SQLite execution history database
├── tests/                      # Pytest unit tests (240+ test cases)
├── docs/                       # Auxiliary technical documentation & reference PDFs
│   └── standards_pdf/          # Authoritative standard PDF reference files
├── scripts/                    # Helper scripts for architecture & table generation
├── main.py                     # Root launcher for GUI
├── main_cli.py                 # Root launcher for Command Line Interface
├── AGENTS.md                   # Standards Reference Guide for developers/agents
├── 31-ACI 211.1-22.md          # ACI 211.1-22 Extracted Standard Reference
├── IS-10262-2019-NewConcreteMix-design.md # IS 10262:2019 Extracted Standard Reference
├── BRE-331-1997-DOE-Mix-Design.md # BRE 331:1997 Extracted Standard Reference
├── requirements.txt            # Python dependencies
└── civilqntify.spec            # PyInstaller spec for building executable
```

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.10** or higher
- `pip` package manager

### 1. Clone the Repository
```bash
git clone https://github.com/sthashixi-netwanderer/civilqntify.git
cd civilqntify
```

### 2. Create a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 Quick Start

### Running the Desktop GUI Application
```bash
python main.py
```
*Alternatively, run `python app/main.py`.*

### Running the Command Line Interface (CLI)
```bash
python main_cli.py --help
```

---

## 🧪 Running Unit Tests

CivilQntify includes a test suite covering all design code calculations, PSD sieve analysis, and material estimation engines:

```bash
pytest tests/
```

---

## 📚 Standard References

Development and formula implementations strictly adhere to the following standards:
- **ACI PRC-211.1-22**: *Selecting Proportions for Normal-Density and High-Density Concrete — Guide*
- **IS 10262:2019**: *Concrete Mix Proportioning — Guidelines (Bureau of Indian Standards)*
- **BRE 331:1997**: *Design of Normal Concrete Mixes (British DOE Method)*

Extracted developer documentation is available in `AGENTS.md` and the root standard markdown files.

---

## 📜 License

This project is licensed under the MIT License.
