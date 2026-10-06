"""Tests for Stage 6: IDW interpolation and leave-one-out cross-validation."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.cleaning import clean_soil_data, load_raw_csv
from src.interpolation import (
    best_power,
    cross_validate,
    idw,
    interpolate_property,
    loocv_mean_baseline,
    loocv_predictions,
    make_grid,
    property_samples,
)

TWO_POINTS = np.array([[0.0, 0.0], [4.0, 0.0]])


def loop_idw(sample_xy, values, target_xy, power):
    """Slow, obvious version of IDW, used only to check the fast one."""
    out = []
    for tx, ty in target_xy:
        weights, total = [], 0.0
        for (sx, sy), v in zip(sample_xy, values):
            d = ((tx - sx) ** 2 + (ty - sy) ** 2) ** 0.5
            if d == 0:
                total, weights = v, None
                break
            weights.append(1 / d**power)
            total += v / d**power
        out.append(total if weights is None else total / sum(weights))
    return np.array(out)


# --- hand examples ---------------------------------------------------------


def test_equidistant_point_gets_the_average():
    result = idw(TWO_POINTS, np.array([10.0, 20.0]), np.array([[2.0, 0.0]]), power=2)
    assert result[0] == pytest.approx(15.0)


def test_distances_1_and_3_with_power_2_matches_hand_calculation():
    # Target at x = 1: distance 1 to A (10) and 3 to B (20).
    # Weights 1/1 and 1/9 -> normalised 0.9 and 0.1 -> 0.9*10 + 0.1*20 = 11.
    result = idw(TWO_POINTS, np.array([10.0, 20.0]), np.array([[1.0, 0.0]]), power=2)
    assert result[0] == pytest.approx(11.0)


def test_three_points_hand_calculation():
    samples = np.array([[0.0, 0.0], [4.0, 0.0], [1.0, 2.0]])  # distances 1, 3, 2 from (1, 0)
    result = idw(samples, np.array([10.0, 20.0, 30.0]), np.array([[1.0, 0.0]]), power=2)
    expected = (10 / 1 + 20 / 9 + 30 / 4) / (1 + 1 / 9 + 1 / 4)
    assert result[0] == pytest.approx(expected)  # about 14.49


def test_exact_hit_returns_sample_value():
    result = idw(TWO_POINTS, np.array([10.0, 20.0]), np.array([[4.0, 0.0]]), power=2)
    assert result[0] == 20.0


# --- general properties ----------------------------------------------------


def test_predictions_between_min_and_max():
    rng = np.random.default_rng(1)
    samples, values = rng.uniform(0, 100, (30, 2)), rng.uniform(-5, 5, 30)
    targets = rng.uniform(-20, 120, (500, 2))
    for power in config.IDW_POWERS:
        result = idw(samples, values, targets, power)
        assert values.min() - 1e-12 <= result.min() and result.max() <= values.max() + 1e-12


def test_constant_field_stays_constant():
    rng = np.random.default_rng(2)
    samples = rng.uniform(0, 100, (20, 2))
    result = idw(samples, np.full(20, 6.5), rng.uniform(0, 100, (50, 2)), power=2)
    assert np.allclose(result, 6.5)


def test_nan_samples_are_ignored():
    samples = np.array([[0.0, 0.0], [4.0, 0.0], [1.0, 0.0]])
    values = np.array([10.0, 20.0, np.nan])  # the NaN sample sits right on the target
    result = idw(samples, values, np.array([[1.0, 0.0]]), power=2)
    assert result[0] == pytest.approx(11.0)


def test_vectorised_matches_loop_version():
    rng = np.random.default_rng(3)
    samples, values = rng.uniform(0, 50, (15, 2)), rng.uniform(0, 10, 15)
    targets = np.vstack([rng.uniform(0, 50, (40, 2)), samples[:3]])  # includes exact hits
    for power in [1.0, 2.0, 3.5]:
        assert np.allclose(idw(samples, values, targets, power),
                           loop_idw(samples, values, targets, power))


# --- leave-one-out ---------------------------------------------------------


def test_loocv_never_uses_held_out_sample():
    # Three samples are 0, one is 1000. If a sample could see itself it would
    # be an exact hit and be predicted perfectly; instead it must get 0.
    samples = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0], [10.0, 10.0]])
    values = np.array([0.0, 0.0, 0.0, 1000.0])
    predictions = loocv_predictions(samples, values, power=2)
    assert predictions[3] == pytest.approx(0.0)
    assert (predictions[:3] > 0).all()  # they do see the 1000 sample


def test_loocv_skips_nan_samples():
    samples = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])
    predictions = loocv_predictions(samples, np.array([1.0, np.nan, 3.0]), power=2)
    assert np.isnan(predictions[1])
    assert predictions[0] == pytest.approx(3.0) and predictions[2] == pytest.approx(1.0)


def test_mean_baseline_leaves_sample_out():
    predictions = loocv_mean_baseline(np.array([1.0, 2.0, 6.0]))
    assert np.allclose(predictions, [4.0, 3.5, 1.5])


def test_cross_validate_and_best_power():
    rng = np.random.default_rng(4)
    samples = rng.uniform(0, 100, (40, 2))
    values = samples[:, 0] * 0.1 + rng.normal(0, 0.1, 40)  # strong spatial trend
    table = cross_validate(samples, values)
    assert list(table["method"]) == ["mean baseline"] + ["IDW"] * len(config.IDW_POWERS)
    assert best_power(table) in config.IDW_POWERS
    assert table.loc[table["method"] == "IDW", "rmse_vs_baseline"].min() < 1  # IDW beats the mean


# --- grid and real data ----------------------------------------------------


def test_grid_shape_and_extent():
    grid_x, grid_y = make_grid()
    rows = int(config.FIELD_HEIGHT_M / config.GRID_RESOLUTION_M) + 1
    cols = int(config.FIELD_WIDTH_M / config.GRID_RESOLUTION_M) + 1
    assert grid_x.shape == grid_y.shape == (rows, cols)
    assert (grid_x.min(), grid_x.max()) == (0, config.FIELD_WIDTH_M)
    assert (grid_y.min(), grid_y.max()) == (0, config.FIELD_HEIGHT_M)


@pytest.fixture(scope="module")
def clean() -> pd.DataFrame:
    return clean_soil_data(load_raw_csv(config.RAW_CSV_PATH))[0]


def test_flagged_outliers_excluded_by_default(clean):
    _, values = property_samples(clean, "nitrogen")
    _, with_outliers = property_samples(clean, "nitrogen", exclude_outliers=False)
    assert np.isnan(values).sum() == np.isnan(with_outliers).sum() + clean["nitrogen_outlier"].sum()


def test_interpolated_maps_have_grid_shape_and_no_gaps(clean):
    grid_x, _ = make_grid()
    for prop in config.NUMERIC_COLUMNS:
        surface = interpolate_property(clean, prop)
        assert surface.shape == grid_x.shape
        assert not np.isnan(surface).any()
