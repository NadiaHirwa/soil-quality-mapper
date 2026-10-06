"""Tests for Stage 3b: metres <-> latitude/longitude conversion."""

import numpy as np
import pytest

from src import config
from src.geo import latlon_to_metres, metres_per_degree, metres_to_latlon


def field_grid() -> tuple[np.ndarray, np.ndarray]:
    """Points every 10 m across the whole field, including all edges."""
    xs = np.linspace(0, config.FIELD_WIDTH_M, 51)
    ys = np.linspace(0, config.FIELD_HEIGHT_M, 41)
    x, y = np.meshgrid(xs, ys)
    return x.ravel(), y.ravel()


def test_origin_maps_to_origin():
    lat, lon = metres_to_latlon(np.array([0.0]), np.array([0.0]))
    assert lat[0] == pytest.approx(config.ORIGIN_LAT)
    assert lon[0] == pytest.approx(config.ORIGIN_LON)


def test_hand_example_400_m_north():
    lat, _ = metres_to_latlon(np.array([0.0]), np.array([400.0]))
    assert lat[0] - config.ORIGIN_LAT == pytest.approx(400 / 110_574)


def test_round_trip_exact_inverse():
    x, y = field_grid()
    x2, y2 = latlon_to_metres(*metres_to_latlon(x, y))
    assert np.max(np.hypot(x2 - x, y2 - y)) < 1e-6


def test_round_trip_after_6_decimal_rounding_under_half_metre():
    # This is what really happens: coordinates are saved with 6 decimals.
    x, y = field_grid()
    lat, lon = metres_to_latlon(x, y)
    x2, y2 = latlon_to_metres(np.round(lat, 6), np.round(lon, 6))
    error = np.hypot(x2 - x, y2 - y)
    assert error.max() < 0.5


def test_metres_per_degree_longitude_near_equator():
    _, per_deg_lon = metres_per_degree(config.ORIGIN_LAT)
    # Close to the equator, so only slightly less than 111,320 m.
    assert 111_000 < per_deg_lon < 111_320
