"""Tests for Stage 9: fertility classes, parcels and the parcel report."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from src import config
from src.cleaning import clean_soil_data, load_raw_csv
from src.fertility import (
    classify_fertility,
    classify_property,
    parcel_bounds,
    parcel_index,
    parcel_report,
)
from src.interpolation import interpolate_property, make_grid
from src.plots import plot_fertility_map, plot_limiting_factor_map

GOOD, MODERATE, POOR = 0, 1, 2

# A value that is Good for each property, used to build test grids.
GOOD_VALUES = {"pH": 6.5, "nitrogen": 30.0, "phosphorus": 20.0, "salinity": 0.5}


# --- thresholds: values exactly on a boundary -------------------------------


@pytest.mark.parametrize("prop, value, expected", [
    ("pH", 5.09, POOR), ("pH", 5.1, MODERATE), ("pH", 5.59, MODERATE), ("pH", 5.6, GOOD),
    ("pH", 7.39, GOOD), ("pH", 7.4, MODERATE), ("pH", 7.89, MODERATE), ("pH", 7.9, POOR),
    ("nitrogen", 9.99, POOR), ("nitrogen", 10.0, MODERATE), ("nitrogen", 24.99, MODERATE),
    ("nitrogen", 25.0, GOOD),
    ("phosphorus", 8.99, POOR), ("phosphorus", 9.0, MODERATE), ("phosphorus", 15.99, MODERATE),
    ("phosphorus", 16.0, GOOD),
    ("salinity", 1.99, GOOD), ("salinity", 2.0, MODERATE), ("salinity", 3.99, MODERATE),
    ("salinity", 4.0, POOR),
])
def test_boundaries_go_to_the_class_that_starts_there(prop, value, expected):
    assert classify_property(np.array([value]), prop)[0] == expected


def test_nan_gets_no_class():
    assert classify_property(np.array([np.nan]), "pH")[0] == -1


def test_classify_property_keeps_shape():
    values = np.full((3, 4), 6.5)
    assert classify_property(values, "pH").shape == (3, 4)


# --- law of the minimum -----------------------------------------------------


def good_grids(shape=(2, 3)) -> dict[str, np.ndarray]:
    return {p: np.full(shape, v) for p, v in GOOD_VALUES.items()}


def test_one_poor_property_makes_the_cell_poor():
    grids = good_grids()
    grids["phosphorus"][0, 1] = 5.0  # Poor
    class_grid, limiting_grid = classify_fertility(grids)
    assert class_grid[0, 1] == POOR
    assert config.LIMITING_FACTOR_LABELS[limiting_grid[0, 1]] == "Phosphorus"
    # Every other cell is untouched: Good with no limiting factor.
    others = np.ones_like(class_grid, dtype=bool)
    others[0, 1] = False
    assert (class_grid[others] == GOOD).all() and (limiting_grid[others] == 0).all()


def test_worst_class_wins_over_moderate():
    grids = good_grids()
    grids["nitrogen"][1, 2] = 15.0   # Moderate
    grids["salinity"][1, 2] = 5.0    # Poor
    class_grid, limiting_grid = classify_fertility(grids)
    assert class_grid[1, 2] == POOR
    assert config.LIMITING_FACTOR_LABELS[limiting_grid[1, 2]] == "Salinity"


def test_two_properties_at_the_worst_class_are_several():
    grids = good_grids()
    grids["pH"][0, 0] = 4.5          # Poor
    grids["nitrogen"][0, 0] = 5.0    # Poor
    _, limiting_grid = classify_fertility(grids)
    assert config.LIMITING_FACTOR_LABELS[limiting_grid[0, 0]] == "Several"


# --- parcels ----------------------------------------------------------------


def test_20_parcels_of_1_ha():
    bounds = parcel_bounds()
    assert len(bounds) == 20
    assert bounds["area_ha"].sum() == pytest.approx(20.0)
    assert list(bounds["parcel_id"]) == [f"P{i:02d}" for i in range(1, 21)]


def test_numbering_starts_north_west():
    bounds = parcel_bounds().set_index("parcel_id")
    assert (bounds.loc["P01", "x_min_m"], bounds.loc["P01", "y_max_m"]) == (0, config.FIELD_HEIGHT_M)
    assert (bounds.loc["P20", "x_max_m"], bounds.loc["P20", "y_min_m"]) == (config.FIELD_WIDTH_M, 0)


def test_every_grid_cell_belongs_to_exactly_one_parcel():
    grid_x, grid_y = make_grid()
    index = parcel_index(grid_x, grid_y)
    assert index.shape == grid_x.shape  # one parcel number per cell
    assert set(np.unique(index)) == set(range(20))  # all parcels used, none extra


# --- report on real data ----------------------------------------------------


@pytest.fixture(scope="module")
def setup():
    clean = clean_soil_data(load_raw_csv(config.RAW_CSV_PATH))[0]
    grid_x, grid_y = make_grid()
    grids = {p: interpolate_property(clean, p) for p in config.NUMERIC_COLUMNS}
    class_grid, limiting_grid = classify_fertility(grids)
    report = parcel_report(grids, class_grid, clean, grid_x, grid_y)
    return clean, grid_x, grid_y, grids, class_grid, limiting_grid, report


def test_report_columns(setup):
    report = setup[-1]
    expected = (["parcel_id", "x_min_m", "x_max_m", "y_min_m", "y_max_m", "area_ha"]
                + [f"{p}_{s}" for p in config.NUMERIC_COLUMNS for s in ("mean", "min", "max")]
                + ["pct_good", "pct_moderate", "pct_poor", "overall_class",
                   "main_limiting_factor", "poor_area_warning", "n_samples", "note"])
    assert list(report.columns) == expected
    assert len(report) == 20


def test_parcel_mean_matches_hand_calculation(setup):
    _, grid_x, grid_y, grids, _, _, report = setup
    # P07: second row from the north (y 200-300), second column (x 100-200).
    # Inner boundaries belong to the parcel east / north, so x < 200 and y < 300.
    inside = (grid_x >= 100) & (grid_x < 200) & (grid_y >= 200) & (grid_y < 300)
    row = report.set_index("parcel_id").loc["P07"]
    for prop in config.NUMERIC_COLUMNS:
        assert row[f"{prop}_mean"] == pytest.approx(grids[prop][inside].mean(), abs=0.005)


def test_sample_counts_sum_to_located_samples(setup):
    clean, report = setup[0], setup[-1]
    assert report["n_samples"].sum() == len(clean)


def test_class_shares_sum_to_100(setup):
    report = setup[-1]
    totals = report[["pct_good", "pct_moderate", "pct_poor"]].sum(axis=1)
    assert np.allclose(totals, 100, atol=0.2)  # rounding to 0.1 %


def test_every_note_has_the_disclaimer(setup):
    assert setup[-1]["note"].str.contains("Not agronomic advice").all()


# --- maps ---------------------------------------------------------------------


def test_fertility_and_limiting_maps_draw_parcels(setup):
    _, grid_x, grid_y, _, class_grid, limiting_grid, _ = setup
    for fig in (plot_fertility_map(grid_x, grid_y, class_grid),
                plot_limiting_factor_map(grid_x, grid_y, limiting_grid)):
        ax = fig.axes[0]
        assert len(ax.patches) == 20  # one rectangle per parcel
        labels = {t.get_text() for t in ax.texts}
        assert {f"P{i:02d}" for i in range(1, 21)} <= labels
        assert ax.get_legend() is not None
        plt.close(fig)


def test_small_poor_area_is_warned_even_when_class_is_moderate(setup):
    # P06 has a Poor (acidic) patch smaller than the 10% rule.
    report = setup[-1].set_index("parcel_id")
    p06 = report.loc["P06"]
    assert 0 < p06["pct_poor"] < 100 * config.PARCEL_MIN_CLASS_SHARE
    assert p06["overall_class"] == "Moderate"  # the 10% rule alone hides it ...
    assert p06["poor_area_warning"] == f"Contains Poor area: {p06['pct_poor']:.1f}% (pH limiting)"
    assert p06["note"].startswith(p06["poor_area_warning"])  # ... the warning shows it


def test_no_warning_without_poor_area(setup):
    report = setup[-1]
    no_poor = report[report["pct_poor"] == 0]
    assert (no_poor["poor_area_warning"] == "").all()
    assert (report["poor_area_warning"] != "").sum() == (report["pct_poor"] > 0).sum()
