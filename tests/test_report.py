"""Tests for Stage 10: the one-call pipeline, the overview numbers and the PDF report."""

import re
from datetime import date

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from src import config
from src.cleaning import load_raw_csv
from src.fertility import assess_field, field_summary
from src.report import build_pdf_report, pdf_page_count


@pytest.fixture(scope="module")
def assessment():
    return assess_field(load_raw_csv(config.RAW_CSV_PATH))


# --- end-to-end pipeline ----------------------------------------------------


def test_raw_file_to_parcel_report_in_one_call(assessment):
    assert len(assessment.parcels) == 20
    assert len(assessment.clean) == 100
    assert set(assessment.grids) == set(config.NUMERIC_COLUMNS)
    for grid in assessment.grids.values():
        assert grid.shape == assessment.class_grid.shape
        assert not np.isnan(grid).any()


def test_uploaded_clean_file_takes_the_same_path():
    reference = pd.read_csv(config.REFERENCE_CSV_PATH, dtype=str, keep_default_na=False)
    a = assess_field(reference)
    assert len(a.parcels) == 20
    assert (a.cleaning["steps"][["fixed", "set_to_nan", "flagged", "rows_dropped"]] == 0).all().all()


def test_manual_power_is_used_for_every_property():
    a = assess_field(load_raw_csv(config.RAW_CSV_PATH), manual_power=3.5)
    assert set(a.powers.values()) == {3.5}


def test_file_without_usable_rows_raises_value_error():
    raw = pd.read_csv(config.REFERENCE_CSV_PATH, dtype=str, keep_default_na=False)
    raw["latitude"] = "10.0"  # every point far outside the field
    with pytest.raises(ValueError):
        assess_field(raw)


# --- overview numbers ---------------------------------------------------------


def test_overview_numbers_match_class_grid_and_parcels(assessment):
    summary = field_summary(assessment)
    for code, name in enumerate(config.FERTILITY_CLASSES):
        assert summary["pct_area"][name] == pytest.approx(100 * (assessment.class_grid == code).mean())
        assert summary["parcels_by_class"][name] == (assessment.parcels["overall_class"] == name).sum()
    assert sum(summary["pct_area"].values()) == pytest.approx(100)
    assert sum(summary["parcels_by_class"].values()) == summary["n_parcels"] == 20
    assert summary["samples_used"] == len(assessment.clean)
    assert summary["rows_in"] == assessment.cleaning["rows_in"]


def test_main_limiting_factor_is_a_property_or_none(assessment):
    factor = field_summary(assessment)["main_limiting_factor"]
    assert factor == "none" or all(p in config.NUMERIC_COLUMNS for p in factor.split(", "))


# --- PDF report -------------------------------------------------------------------


def test_pdf_builds_with_expected_pages_and_closes_figures(assessment):
    plt.close("all")
    pdf = build_pdf_report(assessment, "test data", created=date(2026, 1, 1))
    assert pdf.startswith(b"%PDF")
    pages = len(re.findall(rb"/Type /Page[^s]", pdf))
    assert pages == pdf_page_count(len(assessment.parcels)) == 10
    assert plt.get_fignums() == []


def test_pdf_page_count_rule():
    rows = config.PDF_TABLE_ROWS_PER_PAGE
    assert pdf_page_count(rows) == 9        # table fits on one page
    assert pdf_page_count(rows + 1) == 10   # one more row needs a second page
