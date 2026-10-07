"""Tests for Stage 11: bad or unusual input files give clear messages, not crashes.

Every expected input problem must raise SoilDataError (which the app shows
to the user) with a message that says what is wrong.
"""

import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from src import config
from src.cleaning import SoilDataError, clean_soil_data, read_raw_bytes
from src.fertility import assess_field
from src.plots import plot_all_property_maps, plot_distributions
from src.report import build_pdf_report, pdf_page_count


@pytest.fixture(scope="module")
def reference_text() -> pd.DataFrame:
    """The clean reference data with every cell as text (like an uploaded file)."""
    return pd.read_csv(config.REFERENCE_CSV_PATH, dtype=str, keep_default_na=False)


def to_bytes(df: pd.DataFrame, sep: str = ",", bom: bool = False) -> bytes:
    text = df.to_csv(index=False, sep=sep, lineterminator="\n")
    return ("﻿" if bom else "").encode("utf-8") + text.encode("utf-8")


# --- file format --------------------------------------------------------------


def test_excel_style_semicolons_decimal_commas_and_bom(reference_text):
    # Excel in many countries: ";" between columns, "," as decimal mark, a BOM.
    excel = reference_text.copy()
    for column in config.NUMERIC_COLUMNS + ["latitude", "longitude"]:
        excel[column] = excel[column].str.replace(".", ",", regex=False)
    raw = read_raw_bytes(to_bytes(excel, sep=";", bom=True))
    assert list(raw.columns) == config.COLUMNS  # BOM did not stick to "sample_id"
    clean, _ = clean_soil_data(raw)
    reference = pd.read_csv(config.REFERENCE_CSV_PATH)
    assert np.allclose(clean["pH"], reference["pH"])
    assert np.allclose(clean["latitude"], reference["latitude"])


def test_bom_with_commas(reference_text):
    raw = read_raw_bytes(to_bytes(reference_text, bom=True))
    assert raw.columns[0] == "sample_id"


def test_non_utf8_file_explains_how_to_save():
    with pytest.raises(SoilDataError, match="UTF-8"):
        read_raw_bytes("sample_id,pH\nS001,6.5 é\n".encode("utf-16"))


def test_empty_file():
    with pytest.raises(SoilDataError, match="empty"):
        read_raw_bytes(b"")


def test_header_only():
    with pytest.raises(SoilDataError, match="no data rows"):
        read_raw_bytes(",".join(config.COLUMNS).encode())


def test_file_too_large():
    with pytest.raises(SoilDataError, match="MB"):
        read_raw_bytes(b"x" * int((config.MAX_UPLOAD_MB + 0.1) * 1_000_000))


def test_too_many_rows(reference_text):
    big = pd.concat([reference_text] * (config.MAX_ROWS // len(reference_text) + 1))
    with pytest.raises(SoilDataError, match=f"limit is {config.MAX_ROWS}"):
        read_raw_bytes(to_bytes(big))


# --- columns ----------------------------------------------------------------------


def test_missing_required_column_is_named(reference_text):
    with pytest.raises(SoilDataError, match="latitude"):
        assess_field(reference_text.drop(columns=["latitude"]))


def test_extra_columns_are_ignored_and_reported(reference_text):
    extra = reference_text.assign(farmer_comment="ok", Depth_cm="20")
    a = assess_field(extra)
    assert a.cleaning["ignored_columns"] == ["farmer_comment", "Depth_cm"]
    assert list(a.clean.columns[:9]) == config.COLUMNS
    assert len(a.parcels) == 20


def test_missing_optional_column_is_added_empty(reference_text):
    a = assess_field(reference_text.drop(columns=["collector"]))
    assert a.cleaning["added_columns"] == ["collector"]
    assert a.clean["collector"].isna().all()
    assert len(a.parcels) == 20


# --- too little data --------------------------------------------------------------


def test_few_samples_skip_outlier_check_but_still_map(reference_text):
    # 5 samples: enough for a map (>= 3) but not for the outlier check (< 7).
    a = assess_field(reference_text.iloc[[0, 9, 45, 90, 99]])
    assert not a.clean.filter(like="_outlier").to_numpy().any()
    assert "not checked" in a.cleaning["steps"].iloc[-1]["details"]
    assert a.unavailable == []
    assert len(a.parcels) == 20


def test_too_few_samples_for_a_map(reference_text):
    with pytest.raises(SoilDataError, match=f"at least {config.MIN_SAMPLES_FOR_MAP}"):
        assess_field(reference_text.iloc[:2])


def test_duplicates_only(reference_text):
    copies = pd.concat([reference_text.iloc[[0]]] * 30, ignore_index=True)
    with pytest.raises(SoilDataError, match="duplicate"):
        assess_field(copies)


def test_all_samples_at_one_location(reference_text):
    same_place = reference_text.copy()
    same_place["latitude"] = same_place["latitude"].iloc[0]
    same_place["longitude"] = same_place["longitude"].iloc[0]
    with pytest.raises(SoilDataError, match="location"):
        assess_field(same_place)


# --- a property with no values --------------------------------------------------------


@pytest.fixture(scope="module")
def no_ph(reference_text):
    data = reference_text.copy()
    data["pH"] = ""
    return assess_field(data)


def test_property_without_values_is_not_available(no_ph):
    assert no_ph.unavailable == ["pH"]
    assert np.isnan(no_ph.grids["pH"]).all()
    for prop in ["nitrogen", "phosphorus", "salinity"]:
        assert not np.isnan(no_ph.grids[prop]).any()  # the other maps still work
    assert len(no_ph.parcels) == 20
    assert no_ph.parcels["note"].str.startswith("Not assessed (too few values): pH").all()


def test_plots_and_pdf_handle_a_missing_property(no_ph):
    plt.close("all")
    fig = plot_all_property_maps(no_ph.grid_x, no_ph.grid_y, no_ph.grids, no_ph.clean, no_ph.powers)
    assert "not available" in fig.axes[0].texts[0].get_text()
    plt.close(fig)
    plt.close(plot_distributions(no_ph.clean))
    pdf = build_pdf_report(no_ph, "test")
    # Same number of pages: the pH map page is replaced by a "not available" page.
    assert len(re.findall(rb"/Type /Page[^s]", pdf)) == pdf_page_count(20)
    assert plt.get_fignums() == []


def test_no_property_with_values(reference_text):
    data = reference_text.copy()
    for prop in config.NUMERIC_COLUMNS:
        data[prop] = "NA"
    with pytest.raises(SoilDataError, match="No soil property"):
        assess_field(data)


# --- wrong field ----------------------------------------------------------------------


def test_points_outside_the_field_explain_the_configured_field(reference_text):
    elsewhere = reference_text.copy()
    elsewhere["latitude"] = (elsewhere["latitude"].astype(float) + 1.0).astype(str)  # ~110 km north
    with pytest.raises(SoilDataError) as error:
        assess_field(elsewhere)
    message = str(error.value)
    assert "configured for one specific field" in message
    assert f"{config.ORIGIN_LAT:.4f}" in message and "Rwamagana" in message


def test_some_points_outside_are_dropped_and_counted(reference_text):
    partly = reference_text.copy()
    partly.loc[:4, "latitude"] = "5.0"  # 5 rows far away
    a = assess_field(partly)
    assert a.cleaning["rows_outside_field"] == 5
    assert len(a.clean) == 95
