"""Tests for Stage 3a: simulated soil property patterns."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.generate_data import (
    add_soil_values,
    distance_to_line,
    distance_to_point,
    gaussian_patch,
    jittered_grid_points,
)


def make_samples(seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    """Points and soil values from one generator, exactly as the project does it."""
    rng = np.random.default_rng(seed)
    return add_soil_values(jittered_grid_points(rng), rng)


# --- building blocks -------------------------------------------------------


def test_gaussian_full_strength_at_centre():
    assert gaussian_patch(np.array([0.0]), strength=5.0, sigma=10.0)[0] == pytest.approx(5.0)


def test_gaussian_below_2_percent_at_3_sigma():
    effect = gaussian_patch(np.array([30.0]), strength=5.0, sigma=10.0)[0]
    assert effect / 5.0 < 0.02


def test_distance_to_point_hand_example():
    # 3-4-5 triangle: from (0, 0) to (3, 4) is 5 m.
    d = distance_to_point(np.array([3.0]), np.array([4.0]), (0.0, 0.0))
    assert d[0] == pytest.approx(5.0)


def test_distance_to_horizontal_line():
    # Line y = 10; point (7, 13) is 3 m above it.
    d = distance_to_line(np.array([7.0]), np.array([13.0]), (0.0, 10.0), (100.0, 10.0))
    assert d[0] == pytest.approx(3.0)


# --- generated soil values -------------------------------------------------


def test_values_within_physical_limits():
    s = make_samples()
    assert s["pH"].between(config.PH_MIN, config.PH_MAX).all()
    for column in ["nitrogen", "phosphorus", "salinity"]:
        assert (s[column] >= config.CONCENTRATION_MIN).all()


def near_far_means(values: pd.Series, distance: np.ndarray, sigma: float) -> tuple[float, float]:
    """Mean of values within 1 sigma of a feature, and beyond 3 sigma."""
    near = values[distance < sigma]
    far = values[distance > 3 * sigma]
    assert len(near) >= 3 and len(far) >= 3  # enough points for a fair comparison
    return near.mean(), far.mean()


def test_ph_lower_near_patch():
    s = make_samples()
    d = distance_to_point(s["x_m"], s["y_m"], config.PH_PATCH_CENTRE_M)
    near, far = near_far_means(s["pH"], d, config.PH_PATCH_SIGMA_M)
    assert near < far


def test_nitrogen_higher_near_patch():
    s = make_samples()
    d = distance_to_point(s["x_m"], s["y_m"], config.N_PATCH_CENTRE_M)
    near, far = near_far_means(s["nitrogen"], d, config.N_PATCH_SIGMA_M)
    assert near > far


def test_salinity_higher_near_strip():
    s = make_samples()
    d = distance_to_line(
        s["x_m"], s["y_m"], config.SALINITY_LINE_START_M, config.SALINITY_LINE_END_M
    )
    near, far = near_far_means(s["salinity"], d, config.SALINITY_STRIP_SIGMA_M)
    assert near > far


def test_phosphorus_increases_west_to_east():
    s = make_samples()
    west = s.loc[s["x_m"] < config.FIELD_WIDTH_M / 3, "phosphorus"].mean()
    east = s.loc[s["x_m"] > 2 * config.FIELD_WIDTH_M / 3, "phosphorus"].mean()
    assert east > west


def test_same_seed_gives_identical_values():
    pd.testing.assert_frame_equal(make_samples(42), make_samples(42))


def test_input_points_not_changed():
    rng = np.random.default_rng(config.RANDOM_SEED)
    points = jittered_grid_points(rng)
    before = points.copy()
    add_soil_values(points, rng)
    pd.testing.assert_frame_equal(points, before)
