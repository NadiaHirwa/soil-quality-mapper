"""Fertility classes, limiting factors, parcels and the parcel report.

Fertility rules are separate from the data-validity (cleaning) rules. Every
threshold lives in config.FERTILITY_BANDS with its source or "assumption".

Classes are coded 0 = Good, 1 = Moderate, 2 = Poor, so "worst" = largest code.
Overall class of a grid cell = worst of the four properties (Liebig's law
of the minimum): a cell is only as good as its most limiting property.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import config
from src.cleaning import clean_soil_data
from src.geo import latlon_to_metres
from src.interpolation import best_power, cross_validate, interpolate_property, make_grid, property_samples

NO_DATA = -1  # class code for a missing (NaN) value


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_property(values: np.ndarray, prop: str) -> np.ndarray:
    """Class code (0 Good, 1 Moderate, 2 Poor) for every value of one property.

    Uses the bands in config.FERTILITY_BANDS[prop]; each band is
    [lower, upper), so a value on a boundary goes to the band starting there.
    NaN values get NO_DATA (-1). Works on arrays of any shape.
    """
    values = np.asarray(values, dtype=float)
    codes = np.full(values.shape, NO_DATA, dtype=int)
    for lower, upper, class_name in config.FERTILITY_BANDS[prop]:
        in_band = (values >= lower) & (values < upper)
        codes[in_band] = config.FERTILITY_CLASSES.index(class_name)
    return codes


def property_classes(grids: dict[str, np.ndarray]) -> np.ndarray:
    """Class codes of all four properties stacked: shape (4, rows, cols)."""
    return np.stack([classify_property(grids[p], p) for p in config.NUMERIC_COLUMNS])


def limiting_mask(codes: np.ndarray) -> np.ndarray:
    """True where a property is at the cell's worst class AND that class is not Good.

    Args:
        codes: Output of property_classes, shape (4, rows, cols).
    """
    worst = codes.max(axis=0)
    return (codes == worst) & (worst > 0)


def classify_fertility(grids: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Overall class and limiting factor for every grid cell (vectorised).

    Overall class = worst of the four property classes (law of the minimum).
    Limiting factor code (see config.LIMITING_FACTOR_LABELS):
        0 = none (cell is Good), 1-4 = pH, nitrogen, phosphorus, salinity,
        5 = several properties share the worst class.

    Returns:
        (class_grid, limiting_grid), both shaped like the input grids.
    """
    codes = property_classes(grids)
    class_grid = codes.max(axis=0)
    mask = limiting_mask(codes)
    n_limiting = mask.sum(axis=0)
    single = mask.argmax(axis=0) + 1  # which property, as code 1-4
    limiting_grid = np.where(n_limiting == 0, 0, np.where(n_limiting == 1, single, 5))
    return class_grid, limiting_grid


# ---------------------------------------------------------------------------
# Parcels
# ---------------------------------------------------------------------------


def parcel_layout(size: float = config.PARCEL_SIZE_M) -> tuple[int, int]:
    """(number of parcel columns, number of parcel rows): 5 x 4 for 100 m parcels."""
    return round(config.FIELD_WIDTH_M / size), round(config.FIELD_HEIGHT_M / size)


def parcel_index(x: np.ndarray, y: np.ndarray, size: float = config.PARCEL_SIZE_M) -> np.ndarray:
    """Parcel number (0-based) for points at (x, y) metres.

    Numbering rule: reading order on the map, starting at the NORTH-WEST
    corner, going east along a row, then the next row to the south. So P01
    is top-left and P20 bottom-right. A point exactly on an inner boundary
    belongs to the parcel to its east / north; points on the field edge stay
    in the edge parcel.
    """
    n_cols, n_rows = parcel_layout(size)
    col = np.clip(np.floor(np.asarray(x) / size).astype(int), 0, n_cols - 1)
    row_from_south = np.clip(np.floor(np.asarray(y) / size).astype(int), 0, n_rows - 1)
    row_from_north = n_rows - 1 - row_from_south
    return row_from_north * n_cols + col


def parcel_id(index: int) -> str:
    """0 -> "P01", 19 -> "P20"."""
    return f"P{index + 1:02d}"


def parcel_bounds(size: float = config.PARCEL_SIZE_M) -> pd.DataFrame:
    """One row per parcel: parcel_id, x_min_m, x_max_m, y_min_m, y_max_m, area_ha."""
    n_cols, n_rows = parcel_layout(size)
    rows = []
    for index in range(n_cols * n_rows):
        row_from_north, col = divmod(index, n_cols)
        y_min = (n_rows - 1 - row_from_north) * size
        rows.append({"parcel_id": parcel_id(index),
                     "x_min_m": col * size, "x_max_m": (col + 1) * size,
                     "y_min_m": y_min, "y_max_m": y_min + size,
                     "area_ha": size * size / 10_000})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Parcel report
# ---------------------------------------------------------------------------


def parcel_overall_class(shares: np.ndarray) -> int:
    """Worst class covering at least PARCEL_MIN_CLASS_SHARE of the parcel.

    Args:
        shares: Fraction of the parcel in Good, Moderate, Poor (sums to 1).
    """
    for code in (2, 1):  # Poor first, then Moderate
        if shares[code] >= config.PARCEL_MIN_CLASS_SHARE:
            return code
    return 0


def main_limiting_factor(mask_in_parcel: np.ndarray, worst_cells: np.ndarray) -> list[str]:
    """Properties that limit most often in the cells at the parcel's class.

    Args:
        mask_in_parcel: limiting_mask values for the parcel, shape (4, n_cells).
        worst_cells: True for the parcel cells that have the parcel's class.
    """
    counts = mask_in_parcel[:, worst_cells].sum(axis=1)
    if counts.max() == 0:
        return []
    return [p for p, c in zip(config.NUMERIC_COLUMNS, counts) if c == counts.max()]


def parcel_note(limiting: list[str], n_samples: int) -> str:
    """Short generic note for one parcel (never a recommendation)."""
    if limiting:
        note = " ".join(config.FERTILITY_NOTES[p] for p in limiting)
    else:
        note = "No limiting factor at these thresholds."
    if n_samples < config.PARCEL_FEW_SAMPLES:
        note += f" Only {n_samples} sample(s) inside: estimate less certain."
    return f"{note} {config.REPORT_DISCLAIMER}"


def parcel_report(
    grids: dict[str, np.ndarray],
    class_grid: np.ndarray,
    samples: pd.DataFrame,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
) -> pd.DataFrame:
    """One row per parcel with statistics, class shares, class and limiting factor.

    Args:
        grids: Property name -> interpolated grid.
        class_grid: Overall class per grid cell (from classify_fertility).
        samples: Cleaned samples (to count real samples inside each parcel).
        grid_x, grid_y: Grid coordinates in metres (from make_grid).

    Returns:
        DataFrame: parcel_id, bounds, area_ha, <prop>_mean/min/max,
        pct_good, pct_moderate, pct_poor, overall_class, main_limiting_factor,
        n_samples, note.
    """
    cell_parcel = parcel_index(grid_x, grid_y)
    mask = limiting_mask(property_classes(grids))

    sx, sy = latlon_to_metres(samples["latitude"].to_numpy(), samples["longitude"].to_numpy())
    n_parcels = len(parcel_bounds())
    samples_per_parcel = np.bincount(parcel_index(sx, sy), minlength=n_parcels)

    rows = []
    for bounds in parcel_bounds().itertuples(index=False):
        index = int(bounds.parcel_id[1:]) - 1
        inside = cell_parcel == index
        row = bounds._asdict()
        for prop in config.NUMERIC_COLUMNS:
            values = grids[prop][inside]
            row[f"{prop}_mean"] = round(float(values.mean()), 2)
            row[f"{prop}_min"] = round(float(values.min()), 2)
            row[f"{prop}_max"] = round(float(values.max()), 2)

        classes = class_grid[inside]
        shares = np.array([(classes == code).mean() for code in range(3)])
        for name, share in zip(config.FERTILITY_CLASSES, shares):
            row[f"pct_{name.lower()}"] = round(100 * float(share), 1)

        overall = parcel_overall_class(shares)
        limiting = main_limiting_factor(mask[:, inside], classes == overall) if overall else []
        row["overall_class"] = config.FERTILITY_CLASSES[overall]
        row["main_limiting_factor"] = ", ".join(limiting) if limiting else "none"
        row["n_samples"] = int(samples_per_parcel[index])
        row["note"] = parcel_note(limiting, row["n_samples"])
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Whole pipeline in one call (Stage 10)
# ---------------------------------------------------------------------------


@dataclass
class FieldAssessment:
    """Everything the app and the PDF report need, from one raw table."""

    clean: pd.DataFrame
    cleaning: dict                       # report from cleaning.clean_soil_data
    exclude_outliers: bool
    manual_power: float | None           # None = powers chosen by LOOCV
    powers: dict[str, float]             # IDW power used per property
    cv_tables: dict[str, pd.DataFrame]   # LOOCV table per property
    grid_x: np.ndarray
    grid_y: np.ndarray
    grids: dict[str, np.ndarray]         # IDW map per property
    class_grid: np.ndarray
    limiting_grid: np.ndarray
    parcels: pd.DataFrame                # parcel report


def assess_field(
    raw: pd.DataFrame,
    manual_power: float | None = None,
    exclude_outliers: bool = config.EXCLUDE_OUTLIERS_FROM_MAPS,
) -> FieldAssessment:
    """raw table -> clean -> interpolate -> classify -> parcel report.

    Bundled and uploaded data both go through exactly this path.

    Args:
        raw: Raw table with cells as text (see cleaning.load_raw_csv).
        manual_power: IDW power for every property; None = best by LOOCV.
        exclude_outliers: Leave flagged outliers out of the maps.

    Raises:
        ValueError: if cleaning fails or leaves no usable rows.
    """
    clean, cleaning = clean_soil_data(raw)
    if clean.empty:
        raise ValueError("no rows are left after cleaning (check the coordinates).")

    grid_x, grid_y = make_grid()
    powers, cv_tables, grids = {}, {}, {}
    for prop in config.NUMERIC_COLUMNS:
        xy, values = property_samples(clean, prop, exclude_outliers)
        cv_tables[prop] = cross_validate(xy, values)
        powers[prop] = manual_power if manual_power is not None else best_power(cv_tables[prop])
        grids[prop] = interpolate_property(clean, prop, powers[prop], exclude_outliers)

    class_grid, limiting_grid = classify_fertility(grids)
    parcels = parcel_report(grids, class_grid, clean, grid_x, grid_y)
    return FieldAssessment(clean, cleaning, exclude_outliers, manual_power, powers, cv_tables,
                           grid_x, grid_y, grids, class_grid, limiting_grid, parcels)


def field_summary(assessment: FieldAssessment) -> dict:
    """Key numbers for the Overview tab and the PDF title page.

    main_limiting_factor counts, for each property, the grid cells where it is
    at the cell's (non-Good) worst class; the property with most cells wins.
    """
    class_grid = assessment.class_grid
    counts = limiting_mask(property_classes(assessment.grids)).sum(axis=(1, 2))
    if counts.max() == 0:
        main_factor = "none"
    else:
        main_factor = ", ".join(p for p, c in zip(config.NUMERIC_COLUMNS, counts) if c == counts.max())
    parcel_classes = assessment.parcels["overall_class"]
    return {
        "rows_in": assessment.cleaning["rows_in"],
        "samples_used": len(assessment.clean),
        "pct_area": {name: 100 * float((class_grid == code).mean())
                     for code, name in enumerate(config.FERTILITY_CLASSES)},
        "parcels_by_class": {name: int((parcel_classes == name).sum())
                             for name in config.FERTILITY_CLASSES},
        "n_parcels": len(assessment.parcels),
        "main_limiting_factor": main_factor,
    }
