"""Soil Quality Mapper - Streamlit app.

Run with:
    .venv\\Scripts\\streamlit run app.py

Streamlit reruns this whole script from top to bottom on every click.
Slow steps (loading, cleaning, cross-validation, interpolation) are wrapped
in @st.cache_data so they only run again when their inputs change.
"""

import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from src import config
from src.cleaning import clean_soil_data, load_raw_csv
from src.interpolation import (
    best_power,
    cross_validate,
    interpolate_property,
    loocv_predictions,
    make_grid,
    property_samples,
)
from src.plots import (
    plot_all_property_maps,
    plot_correlation_heatmap,
    plot_distributions,
    plot_observed_vs_predicted,
    plot_property_map,
    plot_rmse_vs_power,
)

PROPERTY_LABELS = config.PROPERTY_LABELS  # e.g. "nitrogen" -> "Nitrogen (mg/kg)"
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


@st.cache_data
def run_loocv_predictions(
    clean: pd.DataFrame, prop: str, power: float, exclude_outliers: bool
) -> tuple[np.ndarray, np.ndarray]:
    """(observed, leave-one-out predicted) values for one property and power."""
    xy, values = property_samples(clean, prop, exclude_outliers)
    return values, loocv_predictions(xy, values, power)


@st.cache_data
def run_interpolation(clean: pd.DataFrame, prop: str, power: float, exclude_outliers: bool) -> np.ndarray:
    """IDW grid for one property (Stage 6)."""
    return interpolate_property(clean, prop, power=power, exclude_outliers=exclude_outliers)


def power_for(clean: pd.DataFrame, prop: str, manual_power: float | None, exclude_outliers: bool) -> float:
    """The manual power if one is set, otherwise the best power by LOOCV."""
    if manual_power is not None:
        return manual_power
    return best_power(run_cross_validation(clean, prop, exclude_outliers))


# ---------------------------------------------------------------------------
# Cached plot images
#
# Turning a figure into an image is the slowest part of a rerun (about 3.5 s
# for all plots). Each function below builds one figure, saves it as PNG
# bytes, CLOSES the figure (so figures never pile up in memory), and caches
# the bytes. A rerun only redraws plots whose inputs actually changed.
# ---------------------------------------------------------------------------


def to_png(fig: Figure) -> bytes:
    """Save a figure as PNG bytes and close it to free its memory."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=config.APP_FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


@st.cache_data
def map_png(clean: pd.DataFrame, prop: str, power: float, exclude_outliers: bool) -> bytes:
    grid_x, grid_y = make_grid()
    grid_values = run_interpolation(clean, prop, power, exclude_outliers)
    return to_png(plot_property_map(grid_x, grid_y, grid_values, clean, prop, power, exclude_outliers))


@st.cache_data
def all_maps_png(clean: pd.DataFrame, manual_power: float | None, exclude_outliers: bool) -> bytes:
    grid_x, grid_y = make_grid()
    powers = {p: power_for(clean, p, manual_power, exclude_outliers) for p in config.NUMERIC_COLUMNS}
    grids = {p: run_interpolation(clean, p, powers[p], exclude_outliers) for p in config.NUMERIC_COLUMNS}
    return to_png(plot_all_property_maps(grid_x, grid_y, grids, clean, powers, exclude_outliers))


@st.cache_data
def rmse_curve_png(cv_table: pd.DataFrame, prop: str, power: float) -> bytes:
    return to_png(plot_rmse_vs_power(cv_table, prop, power))


@st.cache_data
def observed_predicted_png(clean: pd.DataFrame, prop: str, power: float, exclude_outliers: bool) -> bytes:
    observed, predicted = run_loocv_predictions(clean, prop, power, exclude_outliers)
    return to_png(plot_observed_vs_predicted(observed, predicted, prop, power))


@st.cache_data
def distributions_png(clean: pd.DataFrame, exclude_outliers: bool) -> bytes:
    return to_png(plot_distributions(clean, exclude_outliers))


@st.cache_data
def correlation_png(clean: pd.DataFrame, exclude_outliers: bool) -> bytes:
    return to_png(plot_correlation_heatmap(clean, exclude_outliers))


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

# Results shared by several tabs.
cv_table = run_cross_validation(clean, prop, exclude_outliers)
power = power_for(clean, prop, manual_power, exclude_outliers)
power_note = "set manually" if manual_power is not None else "lowest cross-validation RMSE"

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

    st.subheader("Explore the data")
    col_dist, col_corr = st.columns([3, 2])
    with col_dist:
        st.image(distributions_png(clean, exclude_outliers))
    with col_corr:
        st.image(correlation_png(clean, exclude_outliers))
    st.caption(
        "Correlation does not mean cause: two properties can correlate simply "
        "because their patterns happen to overlap in space."
    )

with tab_maps:
    col_map, col_help = st.columns([3, 1])
    with col_map:
        st.image(map_png(clean, prop, power, exclude_outliers))
    with col_help:
        st.markdown(
            f"**How to read this map**\n\n"
            f"- Colour = estimated {PROPERTY_LABELS[prop]}; the colour bar gives the units.\n"
            f"- White dots are the samples used. The map is most reliable close to them.\n"
            f"- Red x: no value for this property. Orange triangle: flagged outlier left out.\n"
            f"- Values between samples are IDW estimates (p = {power:g}, {power_note}).\n"
            f"- Axes are metres from the field's south-west corner; north is up."
        )

    with st.expander("All four properties"):
        st.image(all_maps_png(clean, manual_power, exclude_outliers))

with tab_validation:
    st.subheader(f"Leave-one-out cross-validation: {PROPERTY_LABELS[prop]}")
    st.write(f"IDW power used for the map: **p = {power:g}** ({power_note}).")
    col_curve, col_scatter = st.columns(2)
    with col_curve:
        st.image(rmse_curve_png(cv_table, prop, power))
    with col_scatter:
        st.image(observed_predicted_png(clean, prop, power, exclude_outliers))
    st.dataframe(cv_table.round(4), hide_index=True)
    st.caption(
        "RMSE and MAE are in the property's units. rmse_vs_baseline below 1 means "
        "IDW predicts better than simply using the mean of the other samples."
    )

with tab_fertility:
    st.info("Fertility classes and parcel evaluation will appear here (Stage 9).")

with tab_export:
    st.info("Downloadable parcel reports will appear here (Stages 9-10).")
