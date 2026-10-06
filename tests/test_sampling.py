"""Tests for Stage 2: jittered sampling locations."""

import numpy as np
import pandas as pd

from src import config
from src.generate_data import jittered_grid_points


def make_points(seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    return jittered_grid_points(np.random.default_rng(seed))


def test_exactly_100_points():
    assert len(make_points()) == 100


def test_all_points_inside_field():
    pts = make_points()
    assert pts["x_m"].between(0, config.FIELD_WIDTH_M).all()
    assert pts["y_m"].between(0, config.FIELD_HEIGHT_M).all()


def test_exactly_one_point_per_cell():
    pts = make_points()
    cell_w = config.FIELD_WIDTH_M / config.GRID_COLS
    cell_h = config.FIELD_HEIGHT_M / config.GRID_ROWS
    col = (pts["x_m"] // cell_w).astype(int)
    row = (pts["y_m"] // cell_h).astype(int)
    cells = set(zip(col, row))
    # 100 distinct cells for 100 points means no cell has two points
    # and no cell is empty.
    expected = {(c, r) for c in range(config.GRID_COLS) for r in range(config.GRID_ROWS)}
    assert cells == expected


def test_same_seed_gives_identical_points():
    pd.testing.assert_frame_equal(make_points(42), make_points(42))


def test_different_seed_gives_different_points():
    a, b = make_points(42), make_points(7)
    assert not np.allclose(a[["x_m", "y_m"]], b[["x_m", "y_m"]])


def test_sample_ids_unique_and_formatted():
    ids = make_points()["sample_id"]
    assert ids.is_unique
    assert ids.iloc[0] == "S001"
    assert ids.iloc[-1] == "S100"
    assert list(ids) == [f"S{i:03d}" for i in range(1, 101)]
