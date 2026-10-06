"""Project-wide constants.

Every fixed number used by the project lives here, so it is easy to find,
explain and change in one place.
"""

from pathlib import Path

# Size of the simulated field, in metres (x = east-west, y = north-south).
FIELD_WIDTH_M = 500.0
FIELD_HEIGHT_M = 400.0

# The field is split into a grid of cells; we take one sample per cell.
# 10 x 10 cells -> each cell is 50 m wide and 40 m tall -> 100 samples.
GRID_COLS = 10
GRID_ROWS = 10

# Seed for the random number generator, so results are reproducible.
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Simulated soil properties
#
# Model for each property: value = baseline + spatial effect + noise.
# ALL numbers below are SIMULATION ASSUMPTIONS chosen to look plausible.
# They are not measured values and not agronomic facts.
# ---------------------------------------------------------------------------

# --- pH (unitless) ---
PH_BASELINE = 6.5            # assumption: slightly acidic field average
PH_NOISE_SD = 0.15           # assumption: small sample-to-sample variation
PH_PATCH_CENTRE_M = (100.0, 300.0)  # assumption: acidic patch, north-west
PH_PATCH_STRENGTH = -1.2     # assumption: pH ~5.3 at the patch centre
PH_PATCH_SIGMA_M = 60.0      # assumption: patch radius scale

# --- Nitrogen (mg/kg, plant-available) ---
N_BASELINE_MG_KG = 25.0      # assumption: field average
N_NOISE_SD_MG_KG = 3.0       # assumption
N_PATCH_CENTRE_M = (380.0, 280.0)   # assumption: richer patch, north-east
N_PATCH_STRENGTH_MG_KG = 20.0       # assumption: ~45 mg/kg at the centre
N_PATCH_SIGMA_M = 70.0       # assumption

# --- Phosphorus (mg/kg, plant-available) ---
# Smooth west-to-east trend, no patch. The trend is centred on the middle of
# the field, so P_BASELINE_MG_KG is also the field average.
P_BASELINE_MG_KG = 15.0      # assumption: field average
P_NOISE_SD_MG_KG = 1.5       # assumption
P_TREND_MG_KG_PER_M = 0.02   # assumption: +10 mg/kg from west edge to east edge

# --- Salinity (EC, dS/m) ---
# A strip along a line across the lower (southern) part of the field.
SALINITY_BASELINE_DS_M = 0.4        # assumption: non-saline background
SALINITY_NOISE_SD_DS_M = 0.08       # assumption
SALINITY_LINE_START_M = (0.0, 80.0)     # assumption: west end of the line
SALINITY_LINE_END_M = (500.0, 120.0)    # assumption: east end (slight tilt)
SALINITY_STRIP_STRENGTH_DS_M = 1.6  # assumption: ~2.0 dS/m on the line
SALINITY_STRIP_SIGMA_M = 30.0       # assumption: strip half-width scale

# ---------------------------------------------------------------------------
# Physical limits (these ARE facts, not assumptions)
# ---------------------------------------------------------------------------
PH_MIN = 0.0
PH_MAX = 14.0
CONCENTRATION_MIN = 0.0      # N, P and salinity cannot be negative

# ---------------------------------------------------------------------------
# Location (Stage 3b)
#
# SIMULATED location: a rounded point in Rwanda's Eastern Province, used only
# to give the synthetic field realistic GPS coordinates. It is NOT a real farm.
# Rwanda is south of the equator, so latitude is negative.
# ---------------------------------------------------------------------------
ORIGIN_LAT = -1.95           # south-west corner of the field (decimal degrees)
ORIGIN_LON = 30.45

# Local flat approximation (standard values, fine for a field-sized area).
METRES_PER_DEG_LAT = 110_574.0
METRES_PER_DEG_LON_AT_EQUATOR = 111_320.0  # multiply by cos(latitude)

# ---------------------------------------------------------------------------
# Sampling campaign (Stage 3b) - simulation assumptions
# ---------------------------------------------------------------------------
CAMPAIGN_START = "2026-03-02"  # Monday
CAMPAIGN_END = "2026-03-06"    # Friday -> 5 weekdays, field crossed west to east

# Fictional collector names (not real people).
COLLECTORS = ["Alice Uwase", "Eric Mugisha", "Grace Ingabire"]

# ---------------------------------------------------------------------------
# Output format (Stage 3b)
# ---------------------------------------------------------------------------
# Decimal places, matching realistic GPS / lab reporting precision.
ROUNDING = {
    "latitude": 6,     # 1e-6 degree ~ 0.1 m
    "longitude": 6,
    "pH": 2,
    "nitrogen": 1,
    "phosphorus": 1,
    "salinity": 2,
}

# Final column order of the dataset.
COLUMNS = [
    "sample_id", "latitude", "longitude", "pH", "nitrogen",
    "phosphorus", "salinity", "sample_date", "collector",
]

# Paths are built from this file's location, so they work from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REFERENCE_CSV_PATH = DATA_DIR / "soil_samples_reference.csv"
