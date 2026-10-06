"""Tests for Stage 4: the corrupted raw dataset and the corruption log."""

from pathlib import Path

import pandas as pd
import pytest

from src import config
from src.generate_data import (
    build_reference_dataset,
    make_raw_dataset,
    read_csv_as_text,
    save_csv,
    write_datasets,
)

PROBLEM_TYPES = {
    "column_names", "missing_value", "messy_string", "impossible_value",
    "outlier", "duplicate", "gps_error", "inconsistent_format",
}


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    """Write all three data files into a temporary folder."""
    paths = {
        "reference": tmp_path / "reference.csv",
        "raw": tmp_path / "raw.csv",
        "log": tmp_path / "log.csv",
    }
    write_datasets(paths["reference"], paths["raw"], paths["log"])
    return paths


@pytest.fixture
def reference(files) -> pd.DataFrame:
    return read_csv_as_text(files["reference"])


@pytest.fixture
def raw(files) -> pd.DataFrame:
    return read_csv_as_text(files["raw"])


@pytest.fixture
def log(files) -> pd.DataFrame:
    df = read_csv_as_text(files["log"])
    df["row_number"] = df["row_number"].astype(int)
    return df


# --- the reference stays clean ---------------------------------------------


def test_reference_file_unchanged_by_stage_4(files, tmp_path):
    alone = tmp_path / "reference_alone.csv"
    save_csv(build_reference_dataset(), alone)
    assert files["reference"].read_bytes() == alone.read_bytes()


def test_corruption_does_not_modify_its_input(reference):
    before = reference.copy()
    make_raw_dataset(reference)
    pd.testing.assert_frame_equal(reference, before)


# --- all 8 problem types ---------------------------------------------------


def test_all_8_problem_types_in_log(log):
    assert set(log["problem_type"]) == PROBLEM_TYPES


def test_all_8_problem_types_visible_in_raw_file(raw, reference):
    n = len(reference)
    # 1 column names
    assert list(raw.columns) != config.COLUMNS
    raw.columns = config.COLUMNS  # use clean names from here on
    body = raw.iloc[:n]
    numeric = body[config.NUMERIC_COLUMNS]
    # 2 missing markers
    for marker in ["", "NA", "n/a", "-", "?"]:
        assert (numeric == marker).any().any(), marker
    # 3 messy strings
    assert numeric.apply(lambda c: c.str.contains(",")).any().any()
    assert numeric.apply(lambda c: c.str.contains("mg/kg|dS/m")).any().any()
    assert numeric.apply(lambda c: c.str.startswith(" ")).any().any()
    # 4 impossible values
    ph = pd.to_numeric(body["pH"], errors="coerce")
    assert (ph > 14).any()
    assert numeric.apply(lambda c: c.str.match(r"^-\d")).any().any()
    # 5 outliers: nitrogen far above anything in the reference
    n_raw = pd.to_numeric(body["nitrogen"], errors="coerce")
    assert n_raw.max() > pd.to_numeric(reference["nitrogen"]).max() * 1.5
    # 6 duplicates
    assert len(raw) > n
    assert raw["sample_id"].duplicated().any()
    # 7 GPS: a positive latitude (missing minus sign) or a latitude of ~30 (swapped)
    lat = pd.to_numeric(body["latitude"], errors="coerce")
    assert (lat > 0).any()
    assert (lat > 25).any()
    # 8 dates and names
    assert body["sample_date"].str.contains("/").any()
    assert body["sample_date"].str.contains("March").any()
    assert (~body["collector"].isin(config.COLLECTORS)).any()


# --- the log is a complete and correct answer key --------------------------


def test_every_logged_change_is_in_raw_file(raw, log):
    for entry in log.itertuples():
        if entry.row_number == 0:  # header rename
            position = config.COLUMNS.index(entry.original_value)
            assert raw.columns[position] == entry.corrupted_value
        elif entry.column == "(row)":  # exact duplicate
            source = int(entry.original_value.split()[1])
            assert list(raw.iloc[entry.row_number - 1]) == list(raw.iloc[source - 1])
        else:
            position = config.COLUMNS.index(entry.column)
            assert raw.iat[entry.row_number - 1, position] == entry.corrupted_value
            assert raw.iat[entry.row_number - 1, 0] == entry.sample_id


def test_every_changed_cell_is_logged(raw, reference, log):
    body = raw.iloc[: len(reference)].to_numpy()
    truth = reference.to_numpy()
    logged = set(zip(log["row_number"], log["column"]))
    for i, j in zip(*(body != truth).nonzero()):
        assert (i + 1, config.COLUMNS[j]) in logged


def test_logged_original_values_match_reference(reference, log):
    cells = log[(log["row_number"].between(1, len(reference)))]
    for entry in cells.itertuples():
        position = config.COLUMNS.index(entry.column)
        assert reference.iat[entry.row_number - 1, position] == entry.original_value


def test_at_most_one_corruption_per_cell(log):
    cells = log[log["row_number"] > 0]
    assert not cells.duplicated(["row_number", "column"]).any()


def test_corrupted_row_share_between_10_and_15_percent(log, reference):
    affected = log.loc[log["row_number"] > 0, "sample_id"].nunique()
    assert 0.10 <= affected / len(reference) <= 0.15


# --- reproducibility -------------------------------------------------------


def test_running_twice_gives_identical_files(tmp_path):
    first, second = tmp_path / "1", tmp_path / "2"
    for folder in (first, second):
        folder.mkdir()
        write_datasets(folder / "ref.csv", folder / "raw.csv", folder / "log.csv")
    for name in ["raw.csv", "log.csv"]:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_committed_raw_and_log_are_up_to_date(tmp_path):
    write_datasets(tmp_path / "ref.csv", tmp_path / "raw.csv", tmp_path / "log.csv")
    assert config.RAW_CSV_PATH.read_bytes() == (tmp_path / "raw.csv").read_bytes()
    assert config.CORRUPTION_LOG_PATH.read_bytes() == (tmp_path / "log.csv").read_bytes()
