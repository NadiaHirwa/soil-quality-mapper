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

# ---------------------------------------------------------------------------
# Corruption into a messy raw file (Stage 4)
# ---------------------------------------------------------------------------
RAW_CSV_PATH = DATA_DIR / "soil_samples_raw.csv"
CORRUPTION_LOG_PATH = DATA_DIR / "corruption_log.csv"

# Separate seed: changing the corruption never changes the clean data.
CORRUPTION_SEED = 2026
# Fraction of the original samples (rows) that get at least one problem.
CORRUPTION_RATE = 0.12

NUMERIC_COLUMNS = ["pH", "nitrogen", "phosphorus", "salinity"]
UNITS = {"nitrogen": "mg/kg", "phosphorus": "mg/kg", "salinity": "dS/m"}
OUTLIER_FACTOR = 3.0         # assumption: outlier = 3 x the true value

# Problem 1: header renames (original name -> messy name).
HEADER_RENAMES = {"pH": " PH", "nitrogen": "Nitrogen ", "salinity": "SALINITY"}

# Problem 6: duplicate rows appended at the end of the file.
N_EXACT_DUPLICATES = 2
N_CONFLICTING_DUPLICATES = 2

# Problems 2, 3, 4, 5, 7, 8: one entry = one corrupted cell.
# (problem type, kind, columns it may be applied to)
# For "missing_value" the kind IS the marker written in the cell.
CORRUPTION_PLAN = [
    ("missing_value", "", NUMERIC_COLUMNS),       # empty cell
    ("missing_value", "NA", NUMERIC_COLUMNS),
    ("missing_value", "n/a", NUMERIC_COLUMNS),
    ("missing_value", "-", NUMERIC_COLUMNS),
    ("missing_value", "?", NUMERIC_COLUMNS),
    ("messy_string", "extra_spaces", NUMERIC_COLUMNS),
    ("messy_string", "decimal_comma", NUMERIC_COLUMNS),
    ("messy_string", "unit_in_cell", ["nitrogen", "phosphorus", "salinity"]),
    ("messy_string", "unit_in_cell", ["nitrogen", "phosphorus", "salinity"]),
    ("impossible_value", "missing_decimal_point", ["pH"]),   # 6.4 -> 64
    ("impossible_value", "negative", ["nitrogen"]),
    ("impossible_value", "negative", ["phosphorus"]),
    ("impossible_value", "negative", ["salinity"]),
    ("outlier", "times_factor", ["nitrogen"]),
    ("outlier", "times_factor", ["phosphorus"]),
    ("gps_error", "missing_minus", ["latitude"]),
    ("gps_error", "missing_minus", ["latitude"]),
    ("gps_error", "swap_lat_lon", ["latitude"]),   # also changes longitude
    ("inconsistent_format", "date_dd_mm_yyyy", ["sample_date"]),
    ("inconsistent_format", "date_dd_mm_yyyy", ["sample_date"]),
    ("inconsistent_format", "date_long", ["sample_date"]),
    ("inconsistent_format", "name_lowercase", ["collector"]),
    ("inconsistent_format", "name_extra_spaces", ["collector"]),
    ("inconsistent_format", "name_initials", ["collector"]),
]

LOG_COLUMNS = [
    "sample_id", "row_number", "column", "problem_type",
    "original_value", "corrupted_value",
]

# ---------------------------------------------------------------------------
# Cleaning (Stage 5) - our design decisions
# ---------------------------------------------------------------------------
# Cell texts that mean "no value" (compared ignoring upper/lower case).
MISSING_MARKERS = ["", "NA", "n/a", "-", "?"]

# Accepted date formats, tried in this order. DD/MM/YYYY is read DAY-FIRST
# (Rwanda convention): "04/03/2026" means 4 March 2026, not 3 April.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d %B %Y"]

# A coordinate may lie this far outside the field and still count as inside
# (allows for small GPS error). Rows still outside are dropped.
GPS_BOX_MARGIN_M = 10.0      # assumption

# Local (spatial) outlier check: compare each value with the median of its
# nearest neighbours; flag if |value - median| > factor x MAD of all
# residuals. Both numbers are assumptions; see README for how c was chosen.
OUTLIER_NEIGHBOURS = 6       # assumption: k nearest neighbours
OUTLIER_MAD_FACTOR = 15.0    # assumption: c (works for ~9.5 < c < ~22.9)

OUTPUTS_DIR = PROJECT_ROOT / "outputs"   # git-ignored inspection files
CLEAN_CSV_PREVIEW_PATH = OUTPUTS_DIR / "soil_samples_clean.csv"

# ---------------------------------------------------------------------------
# Interpolation (Stage 6)
# ---------------------------------------------------------------------------
GRID_RESOLUTION_M = 5.0      # assumption: map grid spacing (101 x 81 points)

# Candidate IDW powers, compared by leave-one-out cross-validation. The best
# one (lowest RMSE) is chosen per property when the app runs.
IDW_POWERS = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

# A target this close to a sample counts as "on" the sample: return its value.
IDW_EXACT_TOLERANCE_M = 1e-6

# Design decision: values flagged as outliers are left OUT of interpolation
# by default (they are suspicious); the app may switch this off.
EXCLUDE_OUTLIERS_FROM_MAPS = True
