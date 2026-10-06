"""Soil Quality Mapper - Streamlit app.

Run with:
    .venv\\Scripts\\streamlit run app.py

Streamlit reruns this whole script from top to bottom on every click.
Slow steps (loading, cleaning, cross-validation) are wrapped in
@st.cache_data so they only run again when their inputs change.
"""

import io

import pandas as pd
import streamlit as st

from src import config
from src.cleaning import clean_soil_data, load_raw_csv
from src.interpolation import best_power, cross_validate, property_samples
from src.plots import SOIL_PROPERTIES

PROPERTY_LABELS = dict(SOIL_PROPERTIES)  # e.g. "nitrogen" -> "Nitrogen (mg/kg)"
SOURCE_BUNDLED = "Bundled sample data"
SOURCE_UPLOAD = "Upload CSV"
POWER_AUTO = "Auto (cross-validation)"
POWER_MANUAL = "Manual"


# ---------------------------------------------------------------------------
# Cached helpers: each runs again only when its arguments change
# ---------------------------------------------------------------------------


@st.cache_data
def load_bundled_data() -> pd.DataFrame:
    """The raw CSV shipped with the project, every cell as text."""
    return load_raw_csv(config.RAW_CSV_PATH)


@st.cache_data
def read_uploaded_csv(file_bytes: bytes) -> pd.DataFrame:
    """An uploaded CSV, read exactly like the bundled one (cells as text)."""
    return pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)


@st.cache_data
def run_cleaning(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cleaning pipeline (Stage 5)."""
    return clean_soil_data(raw)


@st.cache_data
def run_cross_validation(clean: pd.DataFrame, prop: str, exclude_outliers: bool) -> pd.DataFrame:
    """LOOCV table for one property (Stage 6)."""
    xy, values = property_samples(clean, prop, exclude_outliers)
    return cross_validate(xy, values)


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Soil Quality Mapper", layout="wide")
st.title("Soil Quality Mapper")
st.caption(
    "Grid cartography and soil quality assessment. The bundled data is a "
    "**synthetic** 500 m x 400 m field near Rwamagana, Eastern Province, Rwanda "
    "(simulated for this project, not a real farm)."
)

# ---------------------------------------------------------------------------
# Sidebar: the controls
# ---------------------------------------------------------------------------

st.sidebar.header("Settings")

source = st.sidebar.radio("Data source", [SOURCE_BUNDLED, SOURCE_UPLOAD])
uploaded = None
if source == SOURCE_UPLOAD:
    uploaded = st.sidebar.file_uploader(
        "CSV with the 9 standard columns", type="csv",
        help="Same columns as data/soil_samples_raw.csv. It goes through the same cleaning.",
    )

prop = st.sidebar.selectbox(
    "Soil property", config.NUMERIC_COLUMNS, format_func=lambda p: PROPERTY_LABELS[p]
)

power_mode = st.sidebar.radio("IDW power", [POWER_AUTO, POWER_MANUAL])
# session_state survives reruns. The slider's own state is discarded while it
# is hidden (Auto mode), so we keep a copy to restore it when it comes back.
if "manual_power" not in st.session_state:
    st.session_state.manual_power = 2.0
manual_power = None
if power_mode == POWER_MANUAL:
    manual_power = st.sidebar.slider(
        "Power p", min_value=min(config.IDW_POWERS), max_value=max(config.IDW_POWERS),
        value=st.session_state.manual_power, step=0.5,
    )
    st.session_state.manual_power = manual_power

exclude_outliers = st.sidebar.checkbox(
    "Exclude flagged outliers from maps", value=config.EXCLUDE_OUTLIERS_FROM_MAPS,
    help="Flagged values stay in the data but are left out of interpolation.",
)

# ---------------------------------------------------------------------------
# Load and clean the data (friendly errors instead of a crash)
# ---------------------------------------------------------------------------

if source == SOURCE_UPLOAD and uploaded is None:
    st.info("Upload a CSV file in the sidebar, or switch back to the bundled sample data.")
    st.stop()

try:
    raw = load_bundled_data() if uploaded is None else read_uploaded_csv(uploaded.getvalue())
    clean, report = run_cleaning(raw)
    if clean.empty:
        raise ValueError("no rows are left after cleaning (check the coordinates).")
except Exception as error:  # any bad upload: explain it instead of crashing the app
    st.error(f"Could not read or clean this file: {error}")
    st.stop()

# ---------------------------------------------------------------------------
# Main area: tabs
# ---------------------------------------------------------------------------

tab_data, tab_maps, tab_validation, tab_fertility, tab_export = st.tabs(
    ["Data & cleaning", "Maps", "Validation", "Fertility & parcels", "Export"]
)

with tab_data:
    col_in, col_out, col_dropped = st.columns(3)
    col_in.metric("Rows in", report["rows_in"])
    col_out.metric("Rows out", report["rows_out"])
    col_dropped.metric("Rows dropped", report["rows_in"] - report["rows_out"])

    st.subheader("Raw data (as loaded)")
    st.dataframe(raw, height=250)

    st.subheader("Cleaning report")
    st.dataframe(report["steps"], hide_index=True)

    st.subheader("Conflicting duplicates (first entry kept)")
    if report["conflicts"].empty:
        st.write("None found.")
    else:
        st.dataframe(report["conflicts"], hide_index=True)

    st.subheader("Clean data")
    st.dataframe(clean, height=250)

with tab_maps:
    st.info("Heat maps of the interpolated soil properties will appear here (Stage 8).")

with tab_validation:
    st.subheader(f"Leave-one-out cross-validation: {PROPERTY_LABELS[prop]}")
    cv_table = run_cross_validation(clean, prop, exclude_outliers)
    chosen = best_power(cv_table) if manual_power is None else manual_power
    how = "lowest RMSE" if manual_power is None else "set manually"
    st.write(f"IDW power used for the map: **p = {chosen}** ({how}).")
    st.dataframe(cv_table.round(4), hide_index=True)
    st.caption(
        "RMSE and MAE are in the property's units. rmse_vs_baseline below 1 means "
        "IDW predicts better than simply using the mean of the other samples."
    )

with tab_fertility:
    st.info("Fertility classes and parcel evaluation will appear here (Stage 9).")

with tab_export:
    st.info("Downloadable parcel reports will appear here (Stages 9-10).")
