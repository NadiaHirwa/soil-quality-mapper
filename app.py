"""Soil Quality Mapper - Streamlit app.

Run with:
    .venv\\Scripts\\streamlit run app.py

Streamlit reruns this whole script from top to bottom on every click.
The full pipeline (clean -> IDW -> validate -> classify -> report) runs in
one cached call, and every plot is cached as a finished PNG, so a click only
recomputes what its settings actually change.
"""

import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from src import config
from src.cleaning import load_raw_csv
from src.fertility import FieldAssessment, assess_field, field_summary
from src.interpolation import loocv_predictions, property_samples
from src.plots import (
    build_pdf_report,
    plot_all_property_maps,
    plot_correlation_heatmap,
    plot_distributions,
    plot_fertility_map,
    plot_limiting_factor_map,
    plot_observed_vs_predicted,
    plot_property_map,
    plot_rmse_vs_power,
)

PROPERTY_LABELS = config.PROPERTY_LABELS  # e.g. "nitrogen" -> "Nitrogen (mg/kg)"
SOURCE_BUNDLED = "Bundled sample data"
SOURCE_UPLOAD = "Upload CSV"
POWER_AUTO = "Auto (cross-validation)"
POWER_MANUAL = "Manual"
TAB_LABELS = ["Overview", "Data & cleaning", "Maps", "Validation", "Fertility & parcels",
              "Export", "About & method"]

# One-line "how to read this" caption for every plot.
HOW_TO_READ = {
    "distributions": "How to read: bar height = number of samples in each value range; "
                     "the curve is a smoothed version of the bars.",
    "correlation": "How to read: +1 = rise together, -1 = one rises as the other falls, "
                   "0 = no linear relation. Correlation does not mean cause.",
    "property_map": "How to read: colour = estimated value (units on the colour bar); white dots = "
                    "samples used; red x = no value; orange triangle = flagged outlier left out.",
    "all_maps": "How to read: each map has its own colour scale, so compare colours within a "
                "map, not between maps.",
    "rmse_curve": "How to read: lower = better predictions; the dashed line is the power used; "
                  "the dotted line is the error of simply predicting the mean.",
    "observed_predicted": "How to read: each dot is one sample predicted from all the others; "
                          "dots on the dashed 1:1 line are predicted perfectly.",
    "fertility_map": "How to read: each 5 m cell gets the worst class of its four properties; "
                     "black squares are the 1 ha parcels.",
    "limiting_map": "How to read: the property that sets each cell's class; 'Several' = two or "
                    "more properties share the worst class.",
}


# ---------------------------------------------------------------------------
# Cached data and pipeline: each runs again only when its arguments change
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
def run_assessment(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool) -> FieldAssessment:
    """The whole pipeline: clean -> IDW -> validate -> classify -> parcel report."""
    return assess_field(raw, manual_power, exclude_outliers)


@st.cache_data
def run_loocv_predictions(
    clean: pd.DataFrame, prop: str, power: float, exclude_outliers: bool
) -> tuple[np.ndarray, np.ndarray]:
    """(observed, leave-one-out predicted) values for one property and power."""
    xy, values = property_samples(clean, prop, exclude_outliers)
    return values, loocv_predictions(xy, values, power)


# ---------------------------------------------------------------------------
# Cached plot images: build the figure, save it as PNG, CLOSE it, cache the bytes
# ---------------------------------------------------------------------------


def to_png(fig: Figure) -> bytes:
    """Save a figure as PNG bytes and close it to free its memory."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=config.APP_FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


@st.cache_data
def property_map_png(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool, prop: str) -> bytes:
    a = run_assessment(raw, manual_power, exclude_outliers)
    return to_png(plot_property_map(a.grid_x, a.grid_y, a.grids[prop], a.clean, prop,
                                    a.powers[prop], exclude_outliers))


@st.cache_data
def all_maps_png(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool) -> bytes:
    a = run_assessment(raw, manual_power, exclude_outliers)
    return to_png(plot_all_property_maps(a.grid_x, a.grid_y, a.grids, a.clean, a.powers,
                                         exclude_outliers))


@st.cache_data
def fertility_map_png(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool) -> bytes:
    a = run_assessment(raw, manual_power, exclude_outliers)
    return to_png(plot_fertility_map(a.grid_x, a.grid_y, a.class_grid))


@st.cache_data
def limiting_map_png(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool) -> bytes:
    a = run_assessment(raw, manual_power, exclude_outliers)
    return to_png(plot_limiting_factor_map(a.grid_x, a.grid_y, a.limiting_grid))


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


@st.cache_data
def pdf_report(raw: pd.DataFrame, manual_power: float | None, exclude_outliers: bool, data_source: str) -> bytes:
    a = run_assessment(raw, manual_power, exclude_outliers)
    return build_pdf_report(a, data_source)


def figure(png: bytes, how_to_read: str, width: int | None = None) -> None:
    """Show a cached plot image with its one-line 'how to read' caption."""
    if width is None:
        st.image(png)
    else:
        st.image(png, width=width)
    st.caption(how_to_read)


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Soil Quality Mapper", layout="wide")
st.title("Soil Quality Mapper")
st.caption(f"Grid cartography and soil quality assessment for maize. {config.FIELD_DESCRIPTION}")

# ---------------------------------------------------------------------------
# Sidebar: the controls
# ---------------------------------------------------------------------------

st.sidebar.header("Settings")

source = st.sidebar.radio("Data source", [SOURCE_BUNDLED, SOURCE_UPLOAD])
uploaded = None
if source == SOURCE_UPLOAD:
    uploaded = st.sidebar.file_uploader(
        "CSV with the 9 standard columns", type="csv",
        help="Same columns as data/soil_samples_raw.csv. It goes through the same cleaning, "
             "interpolation and fertility assessment.",
    )

prop = st.sidebar.selectbox(
    "Soil property (Maps and Validation tabs)", config.NUMERIC_COLUMNS,
    format_func=lambda p: PROPERTY_LABELS[p],
)

power_mode = st.sidebar.radio("IDW power", [POWER_AUTO, POWER_MANUAL])
# session_state survives reruns. The slider's own state is discarded while it
# is hidden (Auto mode), so we keep a copy to restore it when it comes back.
if "manual_power" not in st.session_state:
    st.session_state.manual_power = 2.0
manual_power = None
if power_mode == POWER_MANUAL:
    manual_power = st.sidebar.slider(
        "Power p (all properties)", min_value=min(config.IDW_POWERS),
        max_value=max(config.IDW_POWERS), value=st.session_state.manual_power, step=0.5,
    )
    st.session_state.manual_power = manual_power

exclude_outliers = st.sidebar.checkbox(
    "Exclude flagged outliers from maps", value=config.EXCLUDE_OUTLIERS_FROM_MAPS,
    help="Flagged values stay in the data but are left out of interpolation.",
)
st.sidebar.caption(config.REPORT_DISCLAIMER)

# ---------------------------------------------------------------------------
# Load data and run the pipeline (friendly errors instead of a crash)
# ---------------------------------------------------------------------------

if source == SOURCE_UPLOAD and uploaded is None:
    st.info("Upload a CSV file in the sidebar, or switch back to the bundled sample data.")
    st.stop()

if uploaded is None:
    data_source = "Bundled sample data (data/soil_samples_raw.csv)"
else:
    data_source = f"Uploaded file: {uploaded.name}"

try:
    raw = load_bundled_data() if uploaded is None else read_uploaded_csv(uploaded.getvalue())
    assessment = run_assessment(raw, manual_power, exclude_outliers)
except Exception as error:  # any bad upload: explain it instead of crashing the app
    st.error(f"Could not read or process this file: {error}")
    st.stop()

clean = assessment.clean
cleaning = assessment.cleaning
parcels = assessment.parcels
summary = field_summary(assessment)
power = assessment.powers[prop]
power_note = "set manually" if manual_power is not None else "lowest cross-validation RMSE"

# ---------------------------------------------------------------------------
# Main area: tabs
# ---------------------------------------------------------------------------

(tab_overview, tab_data, tab_maps, tab_validation, tab_fertility, tab_export,
 tab_about) = st.tabs(TAB_LABELS)

with tab_overview:
    st.write(
        "This app turns soil samples with GPS positions into maps and a parcel evaluation. "
        "It cleans the raw data, interpolates pH, nitrogen, phosphorus and salinity onto a "
        "5 m grid (Inverse Distance Weighting), checks the maps by cross-validation, and "
        "classifies every cell and 1 ha parcel for maize. "
        f"**The bundled data is synthetic.** {config.REPORT_DISCLAIMER}"
    )
    area = summary["pct_area"]
    cols = st.columns(6)
    cols[0].metric("Samples used", summary["samples_used"],
                   help=f"From {summary['rows_in']} raw rows, after cleaning.")
    cols[1].metric("Field area Good", f"{area['Good']:.1f}%")
    cols[2].metric("Field area Moderate", f"{area['Moderate']:.1f}%")
    cols[3].metric("Field area Poor", f"{area['Poor']:.1f}%")
    cols[4].metric("Poor parcels", f"{summary['parcels_by_class']['Poor']} of {summary['n_parcels']}")
    cols[5].metric("Main limiting factor", summary["main_limiting_factor"])
    figure(fertility_map_png(raw, manual_power, exclude_outliers), HOW_TO_READ["fertility_map"],
           width=620)

with tab_data:
    st.subheader("Cleaning summary")
    col_in, col_out, col_dropped = st.columns(3)
    col_in.metric("Rows in", cleaning["rows_in"])
    col_out.metric("Rows out", cleaning["rows_out"])
    col_dropped.metric("Rows dropped", cleaning["rows_in"] - cleaning["rows_out"])
    st.dataframe(cleaning["steps"], hide_index=True)
    st.caption("Each step: cells fixed, cells set to missing, values flagged as outliers "
               "(kept, not deleted) and rows dropped. Steps run in this order.")

    st.subheader("Conflicting duplicates (first entry kept)")
    if cleaning["conflicts"].empty:
        st.write("None found.")
    else:
        st.dataframe(cleaning["conflicts"], hide_index=True)

    st.subheader("Raw data (as loaded)")
    st.dataframe(raw, height=250)
    st.subheader("Clean data")
    st.dataframe(clean, height=250)
    st.caption("The *_outlier columns mark values flagged by the local outlier check.")

    st.subheader("Explore the data")
    col_dist, col_corr = st.columns([3, 2])
    with col_dist:
        figure(distributions_png(clean, exclude_outliers), HOW_TO_READ["distributions"])
    with col_corr:
        figure(correlation_png(clean, exclude_outliers), HOW_TO_READ["correlation"])

with tab_maps:
    st.subheader(f"Interpolated map: {PROPERTY_LABELS[prop]}")
    st.write(f"IDW power p = **{power:g}** ({power_note}). Axes are metres from the field's "
             "south-west corner; north is up. The map is most reliable close to the samples.")
    figure(property_map_png(raw, manual_power, exclude_outliers, prop), HOW_TO_READ["property_map"],
           width=820)
    with st.expander("All four properties"):
        figure(all_maps_png(raw, manual_power, exclude_outliers), HOW_TO_READ["all_maps"])

with tab_validation:
    st.subheader(f"Leave-one-out cross-validation: {PROPERTY_LABELS[prop]}")
    st.write(f"IDW power used for the map: **p = {power:g}** ({power_note}).")
    col_curve, col_scatter = st.columns(2)
    with col_curve:
        figure(rmse_curve_png(assessment.cv_tables[prop], prop, power), HOW_TO_READ["rmse_curve"])
    with col_scatter:
        figure(observed_predicted_png(clean, prop, power, exclude_outliers),
               HOW_TO_READ["observed_predicted"])
    st.dataframe(assessment.cv_tables[prop].round(4), hide_index=True)
    st.caption("RMSE and MAE are in the property's units. rmse_vs_baseline below 1 means IDW "
               "predicts better than the mean of the other samples.")

with tab_fertility:
    st.warning(config.REPORT_DISCLAIMER)
    st.write("Each 5 m grid cell gets the **worst** class of its four properties (law of the "
             "minimum). Thresholds are for maize; sources and their status are in the "
             "About & method tab and the README.")
    col_class, col_limit = st.columns(2)
    with col_class:
        figure(fertility_map_png(raw, manual_power, exclude_outliers), HOW_TO_READ["fertility_map"])
    with col_limit:
        figure(limiting_map_png(raw, manual_power, exclude_outliers), HOW_TO_READ["limiting_map"])

    st.subheader("Parcel evaluation (100 m x 100 m, 1 ha each)")
    st.dataframe(parcels, hide_index=True)
    st.caption(
        f"Parcel class = worst class covering at least {config.PARCEL_MIN_CLASS_SHARE:.0%} of the "
        f"parcel. P01 is the north-west parcel; numbering runs left to right, then row by row "
        f"southwards. n_samples = real samples inside; fewer than {config.PARCEL_FEW_SAMPLES} "
        f"means a less certain estimate. Means are of the interpolated grid."
    )

with tab_export:
    st.write("Download the results. All files reflect the current settings in the sidebar.")
    col_report, col_data = st.columns(2)
    with col_report:
        st.markdown("**Parcel evaluation**")
        # The PDF takes ~3 s to build, so we pass a function: Streamlit only
        # calls it when the button is clicked (deferred data generation).
        st.download_button("Parcel evaluation report (PDF)",
                           data=lambda: pdf_report(raw, manual_power, exclude_outliers, data_source),
                           file_name="parcel_report.pdf", mime="application/pdf")
        st.download_button("Parcel table (CSV)", data=parcels.to_csv(index=False).encode("utf-8"),
                           file_name="parcel_report.csv", mime="text/csv")
        st.download_button("Fertility map (PNG)",
                           data=fertility_map_png(raw, manual_power, exclude_outliers),
                           file_name="fertility_map.png", mime="image/png")
    with col_data:
        st.markdown("**Data**")
        st.download_button("Cleaned dataset (CSV)",
                           data=clean.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
                           file_name="soil_samples_clean.csv", mime="text/csv")
        st.download_button("Cleaning report (CSV)",
                           data=cleaning["steps"].to_csv(index=False).encode("utf-8"),
                           file_name="cleaning_report.csv", mime="text/csv")
    st.caption(config.REPORT_DISCLAIMER)

with tab_about:
    st.subheader("Method")
    st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(config.METHOD_STEPS, start=1)))
    st.subheader("Key assumptions")
    st.markdown("\n".join(f"- {line}" for line in config.KEY_ASSUMPTIONS))
    st.subheader("Fertility thresholds for maize")
    st.dataframe(pd.DataFrame(
        [{"property": PROPERTY_LABELS[p], "class": cls, "from": lower, "to (not incl.)": upper}
         for p in config.NUMERIC_COLUMNS for lower, upper, cls in config.FERTILITY_BANDS[p]]
    ), hide_index=True)
    st.caption("Each band runs from 'from' up to but not including 'to'. Sources and their status "
               "(verified / to verify / assumption) are listed in the README, 'Fertility rules'.")
    st.subheader("Known limitations")
    st.markdown("\n".join(f"- {line}" for line in config.LIMITATIONS))
    st.caption(config.REPORT_DISCLAIMER)
