"""Project-wide constants.

Every fixed number used by the project lives here, so it is easy to find,
explain and change in one place.
"""

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
