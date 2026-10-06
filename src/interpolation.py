"""Inverse Distance Weighting (IDW) interpolation with cross-validation.

IDW estimate at a target point = weighted average of the samples, with
weight = 1 / distance^power, normalised so the weights sum to 1.

All maths is done in local metres (converted from lat/lon with geo.py).
"""

import numpy as np
import pandas as pd

from src import config
from src.geo import latlon_to_metres, pairwise_distances


# ---------------------------------------------------------------------------
# Inputs: grid and samples
# ---------------------------------------------------------------------------


def make_grid(
    width: float = config.FIELD_WIDTH_M,
    height: float = config.FIELD_HEIGHT_M,
    resolution: float = config.GRID_RESOLUTION_M,
) -> tuple[np.ndarray, np.ndarray]:
    """Regular grid of points covering the field, edges included.

    Returns:
        (grid_x, grid_y), two 2D arrays of shape (rows, cols). With a 500 x 400 m
        field and 5 m spacing that is 81 rows (y) x 101 columns (x).
    """
    xs = np.arange(0, width + resolution / 2, resolution)
    ys = np.arange(0, height + resolution / 2, resolution)
    return np.meshgrid(xs, ys)


def property_samples(
    clean: pd.DataFrame,
    prop: str,
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample positions (metres) and values for one property.

    Flagged outliers become NaN when exclude_outliers is True, so they are
    ignored like missing values.

    Returns:
        (xy, values): xy has shape (n, 2); values has shape (n,), may contain NaN.
    """
    x, y = latlon_to_metres(clean["latitude"].to_numpy(), clean["longitude"].to_numpy())
    values = clean[prop].to_numpy(dtype=float).copy()
    flag_column = f"{prop}_outlier"
    if exclude_outliers and flag_column in clean:
        values[clean[flag_column].to_numpy(dtype=bool)] = np.nan
    return np.column_stack([x, y]), values


# ---------------------------------------------------------------------------
# IDW
# ---------------------------------------------------------------------------


def idw_from_distances(distances: np.ndarray, values: np.ndarray, power: float) -> np.ndarray:
    """IDW estimates, given the (targets x samples) distance table.

    If a target is within IDW_EXACT_TOLERANCE_M of a sample, the sample's
    value is returned exactly (avoids dividing by zero). An infinite distance
    gives weight 0, which is how LOOCV hides a sample.
    """
    exact = distances <= config.IDW_EXACT_TOLERANCE_M
    with np.errstate(divide="ignore"):
        weights = 1.0 / distances**power
    # Rows with an exact hit: only the matching sample(s) count.
    has_exact = exact.any(axis=1)
    weights[has_exact] = exact[has_exact].astype(float)
    # Normalise so each row of weights sums to 1, then take the weighted average.
    return (weights @ values) / weights.sum(axis=1)


def idw(sample_xy: np.ndarray, values: np.ndarray, target_xy: np.ndarray, power: float) -> np.ndarray:
    """Global IDW: estimate a value at every target from all valid samples.

    Args:
        sample_xy: Sample positions, shape (n, 2), metres.
        values: Sample values, shape (n,). NaN samples are ignored.
        target_xy: Points to estimate, shape (m, 2), metres.
        power: IDW power p (weight = 1 / distance^p).

    Returns:
        Estimates, shape (m,).

    Raises:
        ValueError: if no sample has a value.
    """
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    if not valid.any():
        raise ValueError("No samples with a value to interpolate from.")
    distances = pairwise_distances(target_xy, np.asarray(sample_xy)[valid])
    return idw_from_distances(distances, values[valid], power)


# ---------------------------------------------------------------------------
# Leave-one-out cross-validation
# ---------------------------------------------------------------------------


def loocv_predictions(sample_xy: np.ndarray, values: np.ndarray, power: float) -> np.ndarray:
    """Predict each sample from all the OTHER samples (leave-one-out).

    The sample-to-sample distance table has its diagonal set to infinity, so
    a sample gets weight 0 in its own prediction. NaN samples are skipped
    and get a NaN prediction.
    """
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    xy, v = np.asarray(sample_xy)[valid], values[valid]

    distances = pairwise_distances(xy, xy)
    np.fill_diagonal(distances, np.inf)   # hide each sample from itself

    predictions = np.full(len(values), np.nan)
    predictions[valid] = idw_from_distances(distances, v, power)
    return predictions


def loocv_mean_baseline(values: np.ndarray) -> np.ndarray:
    """Baseline: predict each sample as the mean of all the OTHER samples."""
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    total, n = values[valid].sum(), valid.sum()
    predictions = np.full(len(values), np.nan)
    predictions[valid] = (total - values[valid]) / (n - 1)
    return predictions


def rmse(errors: np.ndarray) -> float:
    """Root mean square error (big misses count more). NaNs are ignored."""
    return float(np.sqrt(np.nanmean(np.square(errors))))


def mae(errors: np.ndarray) -> float:
    """Mean absolute error (average size of a miss). NaNs are ignored."""
    return float(np.nanmean(np.abs(errors)))


def cross_validate(
    sample_xy: np.ndarray, values: np.ndarray, powers: list[float] = config.IDW_POWERS
) -> pd.DataFrame:
    """LOOCV RMSE and MAE for each IDW power, plus the mean baseline.

    Returns:
        DataFrame with columns method, power, rmse, mae, rmse_vs_baseline
        (IDW RMSE divided by baseline RMSE: below 1 means IDW beats the mean).
    """
    values = np.asarray(values, dtype=float)
    baseline_errors = loocv_mean_baseline(values) - values
    rows = [{"method": "mean baseline", "power": np.nan,
             "rmse": rmse(baseline_errors), "mae": mae(baseline_errors)}]
    for power in powers:
        errors = loocv_predictions(sample_xy, values, power) - values
        rows.append({"method": "IDW", "power": power, "rmse": rmse(errors), "mae": mae(errors)})
    table = pd.DataFrame(rows)
    table["rmse_vs_baseline"] = table["rmse"] / table.loc[0, "rmse"]
    return table


def best_power(cv_table: pd.DataFrame) -> float:
    """The IDW power with the lowest RMSE in a cross_validate table."""
    idw_rows = cv_table[cv_table["method"] == "IDW"]
    return float(idw_rows.loc[idw_rows["rmse"].idxmin(), "power"])


def cross_validation_table(
    clean: pd.DataFrame,
    powers: list[float] = config.IDW_POWERS,
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> pd.DataFrame:
    """cross_validate for every soil property, stacked in one table."""
    tables = []
    for prop in config.NUMERIC_COLUMNS:
        xy, values = property_samples(clean, prop, exclude_outliers)
        table = cross_validate(xy, values, powers)
        table.insert(0, "property", prop)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


# ---------------------------------------------------------------------------
# Map for one property
# ---------------------------------------------------------------------------


def interpolate_property(
    clean: pd.DataFrame,
    prop: str,
    power: float | None = None,
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> np.ndarray:
    """IDW map of one property on the make_grid() grid.

    Args:
        clean: Cleaned data (from cleaning.clean_soil_data).
        prop: Column name, e.g. "pH".
        power: IDW power. If None, it is chosen now by LOOCV from
            config.IDW_POWERS, so it adapts to whatever data is loaded.
        exclude_outliers: Leave flagged outliers out (default from config).

    Returns:
        2D array with the same shape as the grid from make_grid().
    """
    xy, values = property_samples(clean, prop, exclude_outliers)
    if power is None:
        power = best_power(cross_validate(xy, values))
    grid_x, grid_y = make_grid()
    targets = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    return idw(xy, values, targets, power).reshape(grid_x.shape)
