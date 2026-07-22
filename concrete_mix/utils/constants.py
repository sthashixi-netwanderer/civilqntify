"""Physical constants for concrete mix design calculations."""

# Density of water (kg/m³)
WATER_DENSITY_KG_M3 = 1000.0

# Specific gravities (dimensionless, multiply by 1000 for kg/m³)
SG_WATER = 1.0
SG_CEMENT_DEFAULT = 3.15
SG_FINE_AGG_DEFAULT = 2.65
SG_COARSE_AGG_DEFAULT = 2.70
SG_FLY_ASH = 2.20
SG_GGBFS = 2.90
SG_SILICA_FUME = 2.20

# Air content defaults (percent by volume)
AIR_ENTRAPPED_10MM = 1.5  # 10mm NMSA
AIR_ENTRAPPED_20MM = 1.0  # 20mm NMSA
AIR_ENTRAPPED_40MM = 0.8  # 40mm NMSA

# Standard deviation (σ) defaults by grade (IS 10262:2019 Table 1)
IS_STD_DEV = {
    "M10": 3.5,
    "M15": 3.5,
    "M20": 4.0,
    "M25": 4.0,
    "M30": 5.0,
    "M35": 5.0,
    "M40": 5.0,
    "M45": 5.0,
    "M50": 5.0,
    "M55": 5.0,
    "M60": 5.0,
    "M65": 6.0,
    "M70": 6.0,
    "M75": 6.0,
    "M80": 6.0,
}

# Embodied carbon factors (kg CO₂ per kg of material)
CARBON_CEMENT_OPC = 0.90
CARBON_FLY_ASH = 0.05
CARBON_GGBFS = 0.08
CARBON_SILICA_FUME = 0.10
CARBON_FINE_AGG = 0.005
CARBON_COARSE_AGG = 0.007
CARBON_ADMIXTURE = 0.20
CARBON_WATER = 0.0003

# Default material prices (per kg, USD — configurable by user)
DEFAULT_PRICE_CEMENT = 0.12
DEFAULT_PRICE_FINE_AGG = 0.02
DEFAULT_PRICE_COARSE_AGG = 0.02
DEFAULT_PRICE_FLY_ASH = 0.05
DEFAULT_PRICE_GGBFS = 0.06
DEFAULT_PRICE_SILICA_FUME = 0.15
DEFAULT_PRICE_ADMIXTURE = 2.00
DEFAULT_PRICE_WATER = 0.001
