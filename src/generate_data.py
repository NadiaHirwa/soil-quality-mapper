"""Generate the synthetic soil dataset.

Stage 2: sampling locations only (local metres). Soil values and
latitude/longitude are added in Stage 3.
"""

import numpy as np
import pandas as pd

from src import config


def make_sample_ids(n: int) -> list[str]:
    """Return sample IDs "S001", "S002", ... up to n."""
    return [f"S{i:03d}" for i in range(1, n + 1)]


def jittered_grid_points(
    rng: np.random.Generator,
    width: float = config.FIELD_WIDTH_M,
    height: float = config.FIELD_HEIGHT_M,
    n_cols: int = config.GRID_COLS,
    n_rows: int = config.GRID_ROWS,
) -> pd.DataFrame:
    """Place one random point inside each cell of a regular grid.

    The field (width x height metres) is divided into n_cols x n_rows equal
    cells. Inside each cell we pick one point uniformly at random. This
    guarantees even coverage of the field while keeping positions random.

    Points are numbered row by row, starting at the bottom-left cell
    (x = 0, y = 0) and moving east, then north.

    Args:
        rng: NumPy random generator, e.g. np.random.default_rng(42).
        width: Field width in metres (x direction).
        height: Field height in metres (y direction).
        n_cols: Number of cells across (x direction).
        n_rows: Number of cells up (y direction).

    Returns:
        DataFrame with columns sample_id, x_m, y_m (one row per cell).
    """
    cell_w = width / n_cols
    cell_h = height / n_rows

    # Column and row index of every cell, listed row by row:
    # col = 0,1,...,9, 0,1,...,9, ...   row = 0,0,...,0, 1,1,...,1, ...
    rows, cols = np.divmod(np.arange(n_cols * n_rows), n_cols)

    # Bottom-left corner of each cell + a random offset inside the cell.
    # rng.uniform(0, 1) gives values in [0, 1), so points never reach the
    # next cell's edge.
    n = n_cols * n_rows
    x = cols * cell_w + rng.uniform(0, 1, n) * cell_w
    y = rows * cell_h + rng.uniform(0, 1, n) * cell_h

    return pd.DataFrame({"sample_id": make_sample_ids(n), "x_m": x, "y_m": y})
