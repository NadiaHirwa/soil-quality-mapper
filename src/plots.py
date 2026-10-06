"""Plotting functions for the soil project."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from src import config


def plot_sampling_coverage(
    points: pd.DataFrame,
    width: float = config.FIELD_WIDTH_M,
    height: float = config.FIELD_HEIGHT_M,
    n_cols: int = config.GRID_COLS,
    n_rows: int = config.GRID_ROWS,
) -> Figure:
    """Plot sample locations on top of the grid cell lines.

    Used to check visually that there is exactly one point per cell and
    that the whole field is covered.

    Args:
        points: DataFrame with columns x_m and y_m (metres).
        width: Field width in metres.
        height: Field height in metres.
        n_cols: Number of grid columns.
        n_rows: Number of grid rows.

    Returns:
        The Matplotlib Figure (so it can be saved or shown in Streamlit).
    """
    fig, ax = plt.subplots(figsize=(8, 6.4))

    # Grid cell boundaries (light grey lines), with axis ticks on the same
    # positions so each label marks a cell edge.
    x_edges = np.linspace(0, width, n_cols + 1)
    y_edges = np.linspace(0, height, n_rows + 1)
    for x in x_edges:
        ax.axvline(x, color="lightgrey", linewidth=0.8)
    for y in y_edges:
        ax.axhline(y, color="lightgrey", linewidth=0.8)
    ax.set_xticks(x_edges)
    ax.set_yticks(y_edges)

    ax.scatter(points["x_m"], points["y_m"], s=18, color="tab:green", zorder=3)

    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect("equal")  # 1 m on x looks the same as 1 m on y
    ax.set_xlabel("x (m, east)")
    ax.set_ylabel("y (m, north)")
    ax.set_title(f"Jittered sampling: {len(points)} points, {n_cols} x {n_rows} cells")
    fig.tight_layout()
    return fig
