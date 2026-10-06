"""Convert between local field metres and GPS latitude/longitude.

Uses a "local flat approximation": near the field, one degree of latitude
or longitude is treated as a fixed number of metres. This is accurate to
millimetres for a 500 m field, but would NOT be suitable for a whole country.

Both conversions use the cosine of the ORIGIN latitude (a constant), so the
two functions are exact inverses of each other.
"""

import numpy as np

from src import config


def metres_per_degree(origin_lat: float = config.ORIGIN_LAT) -> tuple[float, float]:
    """Return (metres per degree of latitude, metres per degree of longitude)."""
    per_deg_lat = config.METRES_PER_DEG_LAT
    per_deg_lon = config.METRES_PER_DEG_LON_AT_EQUATOR * np.cos(np.radians(origin_lat))
    return per_deg_lat, per_deg_lon


def metres_to_latlon(
    x_m: np.ndarray,
    y_m: np.ndarray,
    origin_lat: float = config.ORIGIN_LAT,
    origin_lon: float = config.ORIGIN_LON,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert local metres (x east, y north of the origin) to (latitude, longitude).

    Example: 400 m north of the origin is 400 / 110574 = 0.003618 degrees
    further north.
    """
    per_deg_lat, per_deg_lon = metres_per_degree(origin_lat)
    lat = origin_lat + np.asarray(y_m) / per_deg_lat
    lon = origin_lon + np.asarray(x_m) / per_deg_lon
    return lat, lon


def latlon_to_metres(
    lat: np.ndarray,
    lon: np.ndarray,
    origin_lat: float = config.ORIGIN_LAT,
    origin_lon: float = config.ORIGIN_LON,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert (latitude, longitude) to local metres (x east, y north of the origin).

    Exact inverse of metres_to_latlon. Used again in Stage 6 for interpolation.
    """
    per_deg_lat, per_deg_lon = metres_per_degree(origin_lat)
    x_m = (np.asarray(lon) - origin_lon) * per_deg_lon
    y_m = (np.asarray(lat) - origin_lat) * per_deg_lat
    return x_m, y_m


def pairwise_distances(a_xy: np.ndarray, b_xy: np.ndarray) -> np.ndarray:
    """Distance in metres from every point in a_xy to every point in b_xy.

    Args:
        a_xy: Array of shape (n, 2) with columns x, y.
        b_xy: Array of shape (m, 2) with columns x, y.

    Returns:
        Array of shape (n, m): entry [i, j] is the distance from a_xy[i] to b_xy[j].

    No Python loops: NumPy "broadcasting" lines up an (n, 1) column against a
    (1, m) row, so all n x m differences are computed in one step.
    """
    a_xy, b_xy = np.asarray(a_xy, dtype=float), np.asarray(b_xy, dtype=float)
    dx = a_xy[:, 0][:, None] - b_xy[:, 0][None, :]
    dy = a_xy[:, 1][:, None] - b_xy[:, 1][None, :]
    return np.hypot(dx, dy)
