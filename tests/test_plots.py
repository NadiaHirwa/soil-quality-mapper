"""Tests for Stage 8: maps and validation plots."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

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

UNITS = {"pH": "unitless", "nitrogen": "mg/kg", "phosphorus": "mg/kg", "salinity": "dS/m"}


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.fixture(scope="module")
def clean() -> pd.DataFrame:
    return clean_soil_data(load_raw_csv(config.RAW_CSV_PATH))[0]


@pytest.fixture(scope="module")
def grid():
    return make_grid()


def collection_size(ax, label_start: str) -> int:
    """Number of points in the scatter whose legend label starts with label_start."""
    sizes = [len(c.get_offsets()) for c in ax.collections if c.get_label().startswith(label_start)]
    return sum(sizes)


# --- maps ------------------------------------------------------------------


@pytest.mark.parametrize("prop", config.NUMERIC_COLUMNS)
def test_property_map_axes_units_and_extent(clean, grid, prop):
    grid_x, grid_y = grid
    fig = plot_property_map(grid_x, grid_y, interpolate_property(clean, prop, power=2),
                            clean, prop, power=2)
    assert len(fig.axes) == 2  # map + colour bar
    map_ax, colorbar_ax = fig.axes
    assert UNITS[prop] in colorbar_ax.get_ylabel()
    assert map_ax.get_xlim() == (0, config.FIELD_WIDTH_M)
    assert map_ax.get_ylim() == (0, config.FIELD_HEIGHT_M)
    assert list(map_ax.images[0].get_extent()) == [0, config.FIELD_WIDTH_M, 0, config.FIELD_HEIGHT_M]


@pytest.mark.parametrize("exclude", [True, False])
def test_map_shows_right_number_of_used_and_excluded_samples(clean, grid, exclude):
    grid_x, grid_y = grid
    prop = "nitrogen"
    fig = plot_property_map(grid_x, grid_y, interpolate_property(clean, prop, power=2),
                            clean, prop, power=2, exclude_outliers=exclude)
    ax = fig.axes[0]
    missing = clean[prop].isna()
    flagged = clean[f"{prop}_outlier"] & ~missing
    expected_outliers = int(flagged.sum()) if exclude else 0
    assert collection_size(ax, "No value") == missing.sum()
    assert collection_size(ax, "Flagged outlier") == expected_outliers
    assert collection_size(ax, "Sample used") == len(clean) - missing.sum() - expected_outliers


def test_all_property_maps_has_four_maps_with_colour_bars(clean, grid):
    grid_x, grid_y = grid
    grids = {p: interpolate_property(clean, p, power=2) for p in config.NUMERIC_COLUMNS}
    powers = {p: 2.0 for p in config.NUMERIC_COLUMNS}
    fig = plot_all_property_maps(grid_x, grid_y, grids, clean, powers)
    assert len(fig.axes) == 8  # 4 maps + 4 colour bars
    colorbar_labels = " ".join(ax.get_ylabel() for ax in fig.axes)
    for unit in set(UNITS.values()):
        assert unit in colorbar_labels


# --- validation and exploration plots --------------------------------------


def test_observed_vs_predicted(clean):
    xy, values = property_samples(clean, "pH")
    fig = plot_observed_vs_predicted(values, loocv_predictions(xy, values, 2.5), "pH", 2.5)
    assert len(fig.axes) == 1
    title = fig.axes[0].get_title()
    assert "RMSE" in title and "MAE" in title


def test_rmse_vs_power_has_one_point_per_power(clean):
    xy, values = property_samples(clean, "salinity")
    table = cross_validate(xy, values)
    fig = plot_rmse_vs_power(table, "salinity", best_power(table))
    ax = fig.axes[0]
    assert len(fig.axes) == 1
    idw_line = ax.lines[0]
    assert len(idw_line.get_xdata()) == len(config.IDW_POWERS)
    assert "dS/m" in ax.get_ylabel()


def test_correlation_heatmap_is_annotated(clean):
    fig = plot_correlation_heatmap(clean)
    assert len(fig.axes) == 2  # heat map + colour bar
    n = len(config.NUMERIC_COLUMNS)
    assert len(fig.axes[0].texts) == n * n  # one number per cell
    assert fig.axes[1].get_ylabel() == "Pearson r"


def test_distributions_has_one_panel_per_property(clean):
    fig = plot_distributions(clean)
    assert len(fig.axes) == len(config.NUMERIC_COLUMNS)
    for ax, prop in zip(fig.axes, config.NUMERIC_COLUMNS):
        assert UNITS[prop] in ax.get_xlabel()
