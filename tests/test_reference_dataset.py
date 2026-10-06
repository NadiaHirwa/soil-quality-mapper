"""Tests for Stage 3b: the clean reference dataset and its CSV."""

from pathlib import Path

import pandas as pd
import pytest

from src import config
from src.generate_data import build_reference_dataset, campaign_days, save_csv
from src.geo import metres_to_latlon


@pytest.fixture
def csv_df(tmp_path: Path) -> pd.DataFrame:
    """Generate the dataset, save it to a temporary CSV and read it back."""
    path = tmp_path / "reference.csv"
    save_csv(build_reference_dataset(), path)
    return pd.read_csv(path)


def test_exact_columns_in_order(csv_df):
    assert list(csv_df.columns) == config.COLUMNS


def test_100_rows_no_missing_unique_ids(csv_df):
    assert len(csv_df) == 100
    assert not csv_df.isna().any().any()
    assert csv_df["sample_id"].is_unique


def test_points_inside_field_bounding_box(csv_df):
    # The north-east corner (x = width, y = height) has the largest lat and lon.
    lat_max, lon_max = metres_to_latlon(config.FIELD_WIDTH_M, config.FIELD_HEIGHT_M)
    # Allow half of the last decimal place for rounding.
    tol = 0.5e-6
    assert csv_df["latitude"].between(config.ORIGIN_LAT - tol, lat_max + tol).all()
    assert csv_df["longitude"].between(config.ORIGIN_LON - tol, lon_max + tol).all()


def test_latitude_is_negative_south_of_equator(csv_df):
    assert (csv_df["latitude"] < 0).all()


def test_dates_are_weekdays_inside_campaign(csv_df):
    dates = pd.to_datetime(csv_df["sample_date"], format="%Y-%m-%d")
    assert dates.between(config.CAMPAIGN_START, config.CAMPAIGN_END).all()
    assert (dates.dt.dayofweek < 5).all()  # 0 = Monday ... 4 = Friday
    assert set(csv_df["sample_date"]) <= set(campaign_days())


def test_collectors_from_configured_list(csv_df):
    assert set(csv_df["collector"]) <= set(config.COLLECTORS)


def test_rounding_precision(csv_df):
    for column, decimals in config.ROUNDING.items():
        assert (csv_df[column].round(decimals) == csv_df[column]).all(), column


def test_generating_twice_gives_identical_files(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    save_csv(build_reference_dataset(), a)
    save_csv(build_reference_dataset(), b)
    assert a.read_bytes() == b.read_bytes()


def test_committed_reference_csv_is_up_to_date():
    # Catches the case where the code changed but the CSV was not regenerated.
    saved = pd.read_csv(config.REFERENCE_CSV_PATH)
    fresh = build_reference_dataset()
    pd.testing.assert_frame_equal(saved, fresh, check_dtype=False)
