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
PH_PATCH_STRENGTH = -1.75    # assumption: pH ~4.75 at the centre (strongly acidic zone; was -1.2, see README)
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
IDW_POWERS = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0]

# A target this close to a sample counts as "on" the sample: return its value.
IDW_EXACT_TOLERANCE_M = 1e-6

# Design decision: values flagged as outliers are left OUT of interpolation
# by default (they are suspicious); the app may switch this off.
EXCLUDE_OUTLIERS_FROM_MAPS = True

# ---------------------------------------------------------------------------
# Plots (Stage 8)
# ---------------------------------------------------------------------------
# Labels with units, used on colour bars, axes and in the app.
PROPERTY_LABELS = {
    "pH": "pH (unitless)",
    "nitrogen": "Nitrogen (mg/kg)",
    "phosphorus": "Phosphorus (mg/kg)",
    "salinity": "Salinity, EC (dS/m)",
}

SEABORN_STYLE = "whitegrid"          # one theme for every plot
SEABORN_CONTEXT = "notebook"

MAP_COLORMAP = "viridis"             # perceptually uniform sequential
CORRELATION_COLORMAP = "vlag"        # diverging: blue - white - red

FIGSIZE_MAP = (8.0, 6.2)
FIGSIZE_MAP_GRID = (14.0, 12.5)
FIGSIZE_SMALL = (6.0, 4.5)
FIGSIZE_DISTRIBUTIONS = (11.0, 7.5)

SAMPLE_MARKER_SIZE = 16              # used samples (small dots)
EXCLUDED_MARKER_SIZE = 46            # missing / outlier markers (larger)
SAMPLE_COLOR = "white"
SAMPLE_EDGE_COLOR = "#222222"
MISSING_COLOR = "#e45756"            # red x: no value for this property
OUTLIER_COLOR = "#ff9f1c"            # orange triangle: flagged and excluded

INK_COLOR = "#222222"                # text, scale bar, north arrow
POINT_COLOR = "#3a6ea5"              # scatter points / curve in seaborn plots
REFERENCE_LINE_COLOR = "#888888"     # 1:1 line and mean baseline
HIGHLIGHT_COLOR = "#e45756"          # chosen IDW power

SCALE_BAR_M = 100.0                  # length of the map scale bar

# Resolution of plot images shown in the app.
APP_FIGURE_DPI = 130

# ---------------------------------------------------------------------------
# Fertility rules (Stage 9) - reference crop: MAIZE
#
# Each property is split into bands [lower, upper): a value exactly on a
# boundary belongs to the band that STARTS there. Codes: 0 Good, 1 Moderate,
# 2 Poor (higher = worse). Sources and their status are listed in README.md
# ("Fertility rules"). "to verify" = the group must check the primary source.
# ---------------------------------------------------------------------------
FERTILITY_CLASSES = ["Good", "Moderate", "Poor"]
INF = float("inf")

FERTILITY_BANDS = {
    # pH: boundaries follow the USDA Soil Survey Manual reaction classes
    # (Soil Science Division Staff 2017) - verified (secondary).
    # Mapping classes to maize Good/Moderate/Poor is an ASSUMPTION - to verify:
    # Good = moderately acid to neutral (5.6-7.3), Moderate = strongly acid
    # (5.1-5.5) or slightly alkaline (7.4-7.8), Poor = beyond those.
    "pH": [(-INF, 5.1, "Poor"), (5.1, 5.6, "Moderate"), (5.6, 7.4, "Good"),
           (7.4, 7.9, "Moderate"), (7.9, INF, "Poor")],
    # Nitrogen = nitrate-N (mg/kg), interpreted with the pre-sidedress nitrate
    # test for corn (Magdoff et al. 1984): ~25 mg/kg = sufficient, < 10 = low.
    # Values verified (secondary, extension guide). Using a US maize test for
    # this field is an ASSUMPTION - to verify for Rwandan conditions.
    "nitrogen": [(-INF, 10.0, "Poor"), (10.0, 25.0, "Moderate"), (25.0, INF, "Good")],
    # Phosphorus = Mehlich-3 P (mg/kg = ppm), Iowa State PM 1688 categories for
    # corn: Very Low 0-8 -> Poor, Low 9-15 -> Moderate, Optimum and above
    # (>= 16) -> Good. Verified (secondary). Iowa calibration - to verify locally.
    "phosphorus": [(-INF, 9.0, "Poor"), (9.0, 16.0, "Moderate"), (16.0, INF, "Good")],
    # Salinity = ECe in dS/m (EC of the saturated paste extract) - our EC is
    # ASSUMED to be ECe. Soil Survey Manual classes: nonsaline < 2 -> Good,
    # very slightly saline 2-4 -> Moderate, >= 4 (saline, Richards 1954) -> Poor.
    # Numbers seen only in search summaries of NRCS documents - to verify.
    "salinity": [(-INF, 2.0, "Good"), (2.0, 4.0, "Moderate"), (4.0, INF, "Poor")],
}

# Limiting-factor codes: 0 none, 1-4 the property, 5 several properties tie.
LIMITING_FACTOR_LABELS = ["None (all Good)", "pH", "Nitrogen", "Phosphorus", "Salinity", "Several"]

# ---------------------------------------------------------------------------
# Parcels and report (Stage 9)
# ---------------------------------------------------------------------------
PARCEL_SIZE_M = 100.0        # 100 m x 100 m = 1 ha -> 5 x 4 = 20 parcels
# Parcel class = worst class covering at least this share of the parcel, so a
# few noisy grid cells cannot decide it alone. ASSUMPTION (our design choice).
PARCEL_MIN_CLASS_SHARE = 0.10
PARCEL_FEW_SAMPLES = 3       # fewer real samples inside -> "less certain" hint

FERTILITY_NOTES = {
    "pH": "pH limiting: liming may be worth investigating.",
    "nitrogen": "Nitrogen limiting: N supply (fertiliser or organic inputs) may be worth investigating.",
    "phosphorus": "Phosphorus limiting: P supply may be worth investigating.",
    "salinity": "Salinity limiting: drainage and salt management may be worth investigating.",
}
REPORT_DISCLAIMER = ("Indicative only, based on synthetic data and simplified thresholds. "
                     "Not agronomic advice.")

# Okabe-Ito colours (Okabe & Ito 2008), designed to be colour-blind safe.
FERTILITY_COLORS = ["#0072B2", "#F0E442", "#D55E00"]          # Good, Moderate, Poor
LIMITING_FACTOR_COLORS = ["#DDDDDD", "#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#555555"]
PARCEL_LINE_COLOR = "#222222"

# ---------------------------------------------------------------------------
# Report text (Stage 10): written once, used by the app AND the PDF report
# ---------------------------------------------------------------------------
REPORT_TITLE = "Soil Quality Mapper: parcel evaluation report"
FIELD_DESCRIPTION = ("Synthetic 500 m x 400 m field near Rwamagana, Eastern Province, Rwanda "
                     "(simulated for this project, not a real farm).")

METHOD_STEPS = [
    "Generate: 100 samples on a jittered 10 x 10 grid; each value = baseline + spatial "
    "pattern + noise. A messy copy with 8 kinds of data problems is what the app loads.",
    "Clean: standardise headers, missing markers, numbers, dates and names; repair GPS "
    "errors; set impossible values to missing; remove duplicates; flag local outliers "
    "(flagged values are kept, not deleted).",
    "Interpolate: Inverse Distance Weighting (IDW) onto a 5 m grid, in metres from the "
    "field's south-west corner.",
    "Validate: leave-one-out cross-validation; the IDW power with the lowest RMSE is used, "
    "and compared with predicting the mean of the other samples.",
    "Classify: Good / Moderate / Poor per property for maize; each grid cell takes the "
    "worst class of its four properties (law of the minimum).",
    "Report: 20 parcels of 100 m x 100 m (1 ha) with statistics, class shares, overall "
    "class, limiting factor and number of real samples.",
]

KEY_ASSUMPTIONS = [
    "Nitrogen is plant-available nitrate-N; phosphorus is Mehlich-3 P; salinity is ECe.",
    "Thresholds are for maize (see README, Fertility rules, for each source and its status).",
    "Parcel class = worst class covering at least 10% of the parcel.",
    "Outliers: |value - median of 6 nearest neighbours| > 15 x MAD of all such differences.",
    "Date DD/MM/YYYY is read day-first (Rwanda convention).",
]

LIMITATIONS = [
    "Synthetic data: the results demonstrate the method, not a real field.",
    "GPS repair is field-specific: a coordinate is only repaired if the repaired point "
    "falls inside this field.",
    "IDW never predicts beyond the highest or lowest sample, so it under-predicts peaks, "
    "and it draws 'bullseyes' around single samples.",
    "Leave-one-out cross-validation is slightly optimistic: it tests predictions about "
    "45 m from the nearest sample, not across large gaps.",
    "Several thresholds are marked 'to verify' (calibrated outside Rwanda, or read only "
    "in secondary sources).",
    "Grid cells are classified from estimates; parcels with few samples are less certain.",
]

# PDF layout
PDF_PAGE_SIZE = (11.69, 8.27)        # A4 landscape, inches
PDF_TABLE_ROWS_PER_PAGE = 12
PDF_TABLE_COLUMNS = {                # report column -> short PDF header
    "parcel_id": "Parcel", "pH_mean": "pH", "nitrogen_mean": "N (mg/kg)",
    "phosphorus_mean": "P (mg/kg)", "salinity_mean": "EC (dS/m)", "pct_good": "Good %",
    "pct_moderate": "Moderate %", "pct_poor": "Poor %", "overall_class": "Class",
    "main_limiting_factor": "Limiting factor", "n_samples": "Samples",
}
