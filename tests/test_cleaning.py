"""Tests for Stage 5: cleaning the raw data, checked against the reference."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.cleaning import (
    clean_soil_data,
    collector_lookup,
    compare_with_reference,
    fix_gps,
    load_raw_csv,
    local_outlier_scores,
    normalise_name,
    parse_date,
    parse_number,
)

FLAG_COLUMNS = [f"{c}_outlier" for c in config.NUMERIC_COLUMNS]


@pytest.fixture(scope="module")
def cleaned():
    return clean_soil_data(load_raw_csv(config.RAW_CSV_PATH))


@pytest.fixture(scope="module")
def clean(cleaned) -> pd.DataFrame:
    return cleaned[0]


@pytest.fixture(scope="module")
def reference() -> pd.DataFrame:
    df = pd.read_csv(config.REFERENCE_CSV_PATH)
    df["sample_date"] = pd.to_datetime(df["sample_date"])
    return df


@pytest.fixture(scope="module")
def log() -> pd.DataFrame:
    return pd.read_csv(config.CORRUPTION_LOG_PATH, dtype=str, keep_default_na=False)


def by_id(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index("sample_id").sort_index()


# --- small building blocks -------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("6.5", 6.5), ("6,5", 6.5), ("24 mg/kg", 24.0), ("0.4 dS/m", 0.4), ("-3", -3.0),
])
def test_parse_number(text, expected):
    assert parse_number(text) == pytest.approx(expected)


def test_parse_number_unreadable_is_nan():
    assert np.isnan(parse_number("abc"))


@pytest.mark.parametrize("text", ["2026-03-04", "04/03/2026", "4 March 2026"])
def test_parse_date_all_formats_day_first(text):
    assert parse_date(text) == pd.Timestamp("2026-03-04")


def test_collector_variants_map_to_official_name():
    lookup = collector_lookup()
    for variant in ["grace ingabire", " Grace  Ingabire ", "G. Ingabire", "g ingabire"]:
        assert lookup[normalise_name(variant)] == "Grace Ingabire"


def test_gps_row_far_outside_is_dropped():
    df = pd.DataFrame({"latitude": [-1.949, 10.0], "longitude": [30.451, 10.0]})
    out, result = fix_gps(df)
    assert len(out) == 1 and result["rows_dropped"] == 1


def test_outlier_score_spots_single_spike_but_not_smooth_trend():
    # A smooth trend along x (like a real gradient), small noise, one spike.
    # (Noise matters: with zero noise MAD = 0 and the method cannot judge.)
    x = np.arange(20, dtype=float) * 10
    y = np.zeros(20)
    values = 5 + 0.1 * x + np.random.default_rng(0).normal(0, 0.5, 20)
    values[10] += 50
    scores = local_outlier_scores(x, y, values, k=4)
    assert scores.argmax() == 10
    assert np.delete(scores, 10).max() < config.OUTLIER_MAD_FACTOR


# --- shape and types -------------------------------------------------------


def test_100_unique_samples_and_expected_columns(clean):
    assert len(clean) == 100
    assert clean["sample_id"].is_unique
    assert list(clean.columns) == config.COLUMNS + FLAG_COLUMNS


def test_dtypes(clean):
    for column in config.NUMERIC_COLUMNS + ["latitude", "longitude"]:
        assert pd.api.types.is_float_dtype(clean[column]), column
    assert pd.api.types.is_datetime64_any_dtype(clean["sample_date"])
    for column in FLAG_COLUMNS:
        assert pd.api.types.is_bool_dtype(clean[column]), column


# --- checked against the reference -----------------------------------------


def test_kept_values_equal_reference(clean, reference):
    summary = compare_with_reference(clean, reference)
    assert summary["wrong"].sum() == 0
    assert summary.attrs["samples_missing"] == 0


def test_every_nan_is_a_logged_corruption(clean, log):
    nan_causes = {"missing_value", "impossible_value", "messy_string"}
    logged = set(zip(log["sample_id"], log["column"], log["problem_type"]))
    for column in config.COLUMNS:
        for sample_id in clean.loc[clean[column].isna(), "sample_id"]:
            assert any((sample_id, column, cause) in logged for cause in nan_causes), (sample_id, column)


def test_planted_outliers_flagged_and_nothing_else(clean, log):
    planted = log[log["problem_type"] == "outlier"]
    expected = {(row.sample_id, f"{row.column}_outlier") for row in planted.itertuples()}
    flagged = {(sid, col) for col in FLAG_COLUMNS for sid in clean.loc[clean[col], "sample_id"]}
    assert flagged == expected


def test_zero_reference_values_flagged():
    reference_text = pd.read_csv(config.REFERENCE_CSV_PATH, dtype=str, keep_default_na=False)
    clean, _ = clean_soil_data(reference_text)
    assert not clean[FLAG_COLUMNS].any().any()


def test_gps_fixes_recover_reference_exactly(clean, reference, log):
    fixed_ids = log.loc[log["problem_type"] == "gps_error", "sample_id"].unique()
    c, r = by_id(clean).loc[fixed_ids], by_id(reference).loc[fixed_ids]
    assert (c["latitude"] == r["latitude"]).all()
    assert (c["longitude"] == r["longitude"]).all()


def test_dates_and_collectors_match_reference(clean, reference):
    c, r = by_id(clean), by_id(reference)
    assert (c["sample_date"] == r["sample_date"]).all()
    assert (c["collector"] == r["collector"]).all()


def test_conflicting_duplicates_reported(cleaned):
    conflicts = cleaned[1]["conflicts"]
    assert set(conflicts["sample_id"]) == {"S080", "S035"}


# --- idempotence -----------------------------------------------------------


def test_cleaning_the_reference_changes_nothing(reference):
    reference_text = pd.read_csv(config.REFERENCE_CSV_PATH, dtype=str, keep_default_na=False)
    clean, report = clean_soil_data(reference_text)
    counts = report["steps"][["fixed", "set_to_nan", "flagged", "rows_dropped"]]
    assert (counts == 0).all().all()
    pd.testing.assert_frame_equal(clean[config.COLUMNS], reference, check_dtype=False)
