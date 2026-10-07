"""Plotting functions for the soil project.

Every function returns a Matplotlib Figure and never calls plt.show(), so
the same figure can be saved to a file or shown in Streamlit. Whoever
displays a figure must close it afterwards (plt.close(fig)).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import patheffects
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.image import AxesImage
from matplotlib.ticker import MaxNLocator

from src import config
from src.geo import latlon_to_metres

# One theme for every plot in the project, set in one place.
sns.set_theme(style=config.SEABORN_STYLE, context=config.SEABORN_CONTEXT)


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


# Display settings for each soil property: (column, title with units).
SOIL_PROPERTIES = list(config.PROPERTY_LABELS.items())


def plot_soil_properties(
    samples: pd.DataFrame,
    width: float = config.FIELD_WIDTH_M,
    height: float = config.FIELD_HEIGHT_M,
) -> Figure:
    """Show four scatter plots (one per soil property), points coloured by value.

    Args:
        samples: DataFrame with x_m, y_m, pH, nitrogen, phosphorus, salinity.
        width: Field width in metres.
        height: Field height in metres.

    Returns:
        The Matplotlib Figure with a 2 x 2 grid of panels.
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    for ax, (column, title) in zip(axes.flat, SOIL_PROPERTIES):
        dots = ax.scatter(
            samples["x_m"], samples["y_m"], c=samples[column],
            cmap="viridis", s=40, edgecolor="black", linewidth=0.3,
        )
        fig.colorbar(dots, ax=ax, shrink=0.85)
        ax.set_xlim(0, width)
        ax.set_ylim(0, height)
        ax.set_aspect("equal")
        ax.set_title(title)
        ax.set_xlabel("x (m, east)")
        ax.set_ylabel("y (m, north)")

    fig.suptitle("Simulated soil properties at the 100 sample points (synthetic data)")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Stage 8: helpers shared by the maps
# ---------------------------------------------------------------------------

# A thin white outline that keeps dark text readable on any map colour.
HALO = [patheffects.withStroke(linewidth=4, foreground="white")]


def property_values(
    samples: pd.DataFrame, prop: str, exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS
) -> pd.Series:
    """Values of one property, with flagged outliers set to NaN if excluded."""
    values = samples[prop].astype(float)
    flag_column = f"{prop}_outlier"
    if exclude_outliers and flag_column in samples:
        values = values.mask(samples[flag_column].astype(bool))
    return values


def sample_groups(
    samples: pd.DataFrame, prop: str, exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS
) -> dict[str, np.ndarray]:
    """Positions in metres, shape (n, 2), of three groups of samples.

    used    - has a value and was used for interpolation
    missing - no value for this property (missing or impossible in the raw data)
    outlier - flagged outlier, left out because exclude_outliers is True
    """
    x, y = latlon_to_metres(samples["latitude"].to_numpy(), samples["longitude"].to_numpy())
    xy = np.column_stack([x, y])
    missing = samples[prop].isna().to_numpy()
    flag_column = f"{prop}_outlier"
    if flag_column in samples:
        flagged = samples[flag_column].to_numpy(dtype=bool)
    else:
        flagged = np.zeros(len(samples), dtype=bool)
    outlier = flagged & ~missing & exclude_outliers
    used = ~missing & ~outlier
    return {"used": xy[used], "missing": xy[missing], "outlier": xy[outlier]}


def add_scale_bar(ax: Axes, length_m: float = config.SCALE_BAR_M) -> None:
    """Draw a scale bar of length_m metres in the lower-left corner of a map."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    start_x, start_y = x0 + 0.04 * (x1 - x0), y0 + 0.05 * (y1 - y0)
    ax.plot([start_x, start_x + length_m], [start_y, start_y], color=config.INK_COLOR,
            linewidth=3, solid_capstyle="butt", path_effects=HALO)
    ax.text(start_x + length_m / 2, start_y + 0.015 * (y1 - y0), f"{length_m:g} m",
            ha="center", va="bottom", color=config.INK_COLOR, fontsize=9, path_effects=HALO)


def add_north_arrow(ax: Axes) -> None:
    """Draw a north arrow in the top-right corner (the y axis points north)."""
    ax.annotate("", xy=(0.95, 0.93), xytext=(0.95, 0.81), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=config.INK_COLOR, linewidth=2,
                                mutation_scale=16))
    ax.text(0.95, 0.94, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontweight="bold", color=config.INK_COLOR, path_effects=HALO)


def _draw_map(
    ax: Axes,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_values: np.ndarray,
    samples: pd.DataFrame,
    prop: str,
    power: float,
    exclude_outliers: bool,
) -> AxesImage:
    """Draw one property map on ax and return the image (for the colour bar)."""
    extent = (grid_x.min(), grid_x.max(), grid_y.min(), grid_y.max())
    image = ax.imshow(grid_values, origin="lower", extent=extent, aspect="equal",
                      cmap=config.MAP_COLORMAP, interpolation="nearest")

    groups = sample_groups(samples, prop, exclude_outliers)
    ax.scatter(*groups["used"].T, s=config.SAMPLE_MARKER_SIZE, c=config.SAMPLE_COLOR,
               edgecolors=config.SAMPLE_EDGE_COLOR, linewidths=0.6,
               label=f"Sample used ({len(groups['used'])})")
    if len(groups["missing"]):
        ax.scatter(*groups["missing"].T, s=config.EXCLUDED_MARKER_SIZE, marker="x",
                   c=config.MISSING_COLOR, linewidths=2,
                   label=f"No value ({len(groups['missing'])})")
    if len(groups["outlier"]):
        ax.scatter(*groups["outlier"].T, s=config.EXCLUDED_MARKER_SIZE, marker="^",
                   c=config.OUTLIER_COLOR, edgecolors=config.SAMPLE_EDGE_COLOR, linewidths=0.8,
                   label=f"Flagged outlier, excluded ({len(groups['outlier'])})")

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.grid(False)
    ax.set_xlabel("x (m east of SW corner)")
    ax.set_ylabel("y (m north of SW corner)")
    ax.set_title(f"{config.PROPERTY_LABELS[prop]}: IDW, p = {power:g}")
    add_scale_bar(ax)
    add_north_arrow(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=3,
              frameon=False, fontsize=9)
    return image


def _origin_caption() -> str:
    """Caption that states where the metre axes start."""
    return (f"Synthetic field. Origin (SW corner): {config.ORIGIN_LAT:.4f}\N{DEGREE SIGN}, "
            f"{config.ORIGIN_LON:.4f}\N{DEGREE SIGN}. Axes in metres.")


# ---------------------------------------------------------------------------
# Stage 8: maps
# ---------------------------------------------------------------------------


def plot_property_map(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_values: np.ndarray,
    samples: pd.DataFrame,
    prop: str,
    power: float,
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> Figure:
    """Cartographic map of one interpolated property.

    Shows the IDW surface, a colour bar with units, used samples (dots),
    samples without a value (x) and excluded outliers (triangles), a scale
    bar and a north arrow.

    Args:
        grid_x, grid_y: Grid from interpolation.make_grid().
        grid_values: IDW estimates on that grid (same shape).
        samples: Cleaned data (with lat/lon and outlier flag columns).
        prop: Property column, e.g. "nitrogen".
        power: IDW power used (shown in the title).
        exclude_outliers: Whether flagged outliers were left out.
    """
    fig, ax = plt.subplots(figsize=config.FIGSIZE_MAP, layout="constrained")
    image = _draw_map(ax, grid_x, grid_y, grid_values, samples, prop, power, exclude_outliers)
    fig.colorbar(image, ax=ax, label=config.PROPERTY_LABELS[prop], shrink=0.8)
    fig.suptitle(_origin_caption(), fontsize=9, color=config.INK_COLOR)
    return fig


def plot_all_property_maps(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grids: dict[str, np.ndarray],
    samples: pd.DataFrame,
    powers: dict[str, float],
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> Figure:
    """The four property maps in a 2 x 2 layout (overview / export).

    Args:
        grids: Property name -> IDW grid.
        powers: Property name -> IDW power used for that grid.
    """
    fig, axes = plt.subplots(2, 2, figsize=config.FIGSIZE_MAP_GRID, layout="constrained")
    for ax, prop in zip(axes.flat, config.NUMERIC_COLUMNS):
        image = _draw_map(ax, grid_x, grid_y, grids[prop], samples, prop, powers[prop],
                          exclude_outliers)
        fig.colorbar(image, ax=ax, label=config.PROPERTY_LABELS[prop], shrink=0.8)
    fig.suptitle("Interpolated soil properties. " + _origin_caption())
    return fig


# ---------------------------------------------------------------------------
# Stage 8: validation and exploration plots (Seaborn)
# ---------------------------------------------------------------------------


def plot_observed_vs_predicted(
    observed: np.ndarray, predicted: np.ndarray, prop: str, power: float
) -> Figure:
    """Leave-one-out predictions against the true values, with a 1:1 line.

    Points on the dashed line were predicted perfectly; points above it were
    over-estimated, points below it under-estimated.
    """
    observed, predicted = np.asarray(observed, float), np.asarray(predicted, float)
    ok = ~np.isnan(observed) & ~np.isnan(predicted)
    errors = predicted[ok] - observed[ok]
    rmse, mae = np.sqrt(np.mean(errors**2)), np.mean(np.abs(errors))

    fig, ax = plt.subplots(figsize=config.FIGSIZE_SMALL, layout="constrained")
    sns.scatterplot(x=observed[ok], y=predicted[ok], ax=ax, color=config.POINT_COLOR,
                    s=32, edgecolor="white", linewidth=0.5)
    low = min(observed[ok].min(), predicted[ok].min())
    high = max(observed[ok].max(), predicted[ok].max())
    pad = 0.05 * (high - low)
    limits = (low - pad, high + pad)
    ax.plot(limits, limits, linestyle="--", color=config.REFERENCE_LINE_COLOR, linewidth=1.2,
            label="1:1 line (perfect prediction)")
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_aspect("equal")
    label = config.PROPERTY_LABELS[prop]
    ax.set_xlabel(f"Observed {label}")
    ax.set_ylabel(f"Predicted {label}")
    ax.set_title(f"Leave-one-out, IDW p = {power:g}\nRMSE = {rmse:.3g}, MAE = {mae:.3g}")
    ax.legend(loc="upper left", fontsize=9)
    return fig


def plot_rmse_vs_power(cv_table: pd.DataFrame, prop: str, chosen_power: float) -> Figure:
    """LOOCV error for each IDW power, with the chosen power and the mean baseline.

    Args:
        cv_table: Output of interpolation.cross_validate for one property.
        prop: Property name (for labels).
        chosen_power: Power used for the map (marked with a vertical line).
    """
    idw_rows = cv_table[cv_table["method"] == "IDW"]
    baseline = float(cv_table.loc[cv_table["method"] == "mean baseline", "rmse"].iloc[0])

    fig, ax = plt.subplots(figsize=config.FIGSIZE_SMALL, layout="constrained")
    sns.lineplot(data=idw_rows, x="power", y="rmse", marker="o", color=config.POINT_COLOR,
                 linewidth=2, ax=ax, label="IDW (leave-one-out)")
    ax.axhline(baseline, linestyle=":", linewidth=1.5, color=config.REFERENCE_LINE_COLOR,
               label=f"Mean baseline ({baseline:.3g})")
    ax.axvline(chosen_power, linestyle="--", linewidth=1.2, color=config.HIGHLIGHT_COLOR,
               label=f"Power used (p = {chosen_power:g})")
    ax.set_ylim(bottom=0)
    ax.set_xlabel("IDW power p")
    ax.set_ylabel(f"RMSE, {config.PROPERTY_LABELS[prop]}")
    ax.set_title("Prediction error by IDW power (lower is better)")
    ax.legend(loc="lower left", fontsize=9)
    return fig


def plot_correlation_heatmap(
    samples: pd.DataFrame, exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS
) -> Figure:
    """Pearson correlation between the four soil properties, annotated.

    Flagged outliers are left out when exclude_outliers is True, because a
    single extreme value can change a correlation a lot.
    """
    values = pd.DataFrame({p: property_values(samples, p, exclude_outliers)
                           for p in config.NUMERIC_COLUMNS})
    corr = values.corr(method="pearson")

    fig, ax = plt.subplots(figsize=config.FIGSIZE_SMALL, layout="constrained")
    sns.heatmap(corr, annot=True, fmt=".2f", cmap=config.CORRELATION_COLORMAP,
                vmin=-1, vmax=1, center=0, square=True, linewidths=2, linecolor="white",
                cbar_kws={"label": "Pearson r"}, ax=ax)
    ax.set_title("Correlation between soil properties")
    ax.tick_params(axis="x", rotation=0)
    return fig


def plot_distributions(
    samples: pd.DataFrame, exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS
) -> Figure:
    """Histogram + KDE (smoothed curve) of each soil property, 2 x 2."""
    fig, axes = plt.subplots(2, 2, figsize=config.FIGSIZE_DISTRIBUTIONS, layout="constrained")
    for ax, prop in zip(axes.flat, config.NUMERIC_COLUMNS):
        values = property_values(samples, prop, exclude_outliers).dropna()
        sns.histplot(values, kde=True, bins=15, color=config.POINT_COLOR,
                     edgecolor="white", ax=ax)
        ax.set_xlabel(config.PROPERTY_LABELS[prop])
        ax.set_ylabel("Number of samples")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))  # counts are whole numbers
        ax.set_title(f"n = {len(values)}")
    fig.suptitle("Distribution of each soil property")
    return fig
