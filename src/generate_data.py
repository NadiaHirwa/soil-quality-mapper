"""Generate the synthetic soil dataset.

Stage 2: sampling locations (local metres).
Stage 3a: soil values from spatial patterns (local metres).
Stage 3b: latitude/longitude, dates, collectors and the reference CSV.
Stage 4: a corrupted copy (raw CSV) and a log of every change.

Run as a script to write all three data files:
    .venv\\Scripts\\python -m src.generate_data
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.geo import metres_to_latlon


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


# ---------------------------------------------------------------------------
# Stage 3a: spatial pattern building blocks
# ---------------------------------------------------------------------------


def distance_to_point(
    x: np.ndarray, y: np.ndarray, centre: tuple[float, float]
) -> np.ndarray:
    """Straight-line (Euclidean) distance from each (x, y) to one centre point."""
    cx, cy = centre
    return np.sqrt((x - cx) ** 2 + (y - cy) ** 2)


def distance_to_line(
    x: np.ndarray,
    y: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
) -> np.ndarray:
    """Shortest distance from each (x, y) to the straight line through start and end.

    The line is treated as infinitely long (it crosses the whole field).
    Formula: |cross product| / line length, where the cross product measures
    how far the point sits to the side of the line.
    """
    (x1, y1), (x2, y2) = start, end
    line_length = np.hypot(x2 - x1, y2 - y1)
    cross = (x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)
    return np.abs(cross) / line_length


def gaussian_patch(distance: np.ndarray, strength: float, sigma: float) -> np.ndarray:
    """Effect that is `strength` at distance 0 and fades smoothly with distance.

    effect = strength * exp(-d^2 / (2 * sigma^2))
    At d = sigma about 61% of the strength remains; at d = 3*sigma about 1%.
    """
    return strength * np.exp(-(distance**2) / (2 * sigma**2))


def linear_trend(x: np.ndarray, slope: float, centre: float) -> np.ndarray:
    """Effect that changes steadily along x, equal to 0 at x = centre."""
    return slope * (x - centre)


# ---------------------------------------------------------------------------
# Stage 3a: soil property values
# ---------------------------------------------------------------------------


def add_soil_values(points: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Add pH, nitrogen, phosphorus and salinity columns to sample points.

    Each property follows: value = baseline + spatial effect + noise,
    then is clipped to its physical limits. All settings come from config.

    Args:
        points: DataFrame with columns x_m and y_m (from jittered_grid_points).
        rng: The same random generator used to make the points, so the whole
            dataset is reproducible from one seed.

    Returns:
        A new DataFrame: the input columns plus pH, nitrogen, phosphorus,
        salinity. The input DataFrame is not changed.
    """
    x = points["x_m"].to_numpy()
    y = points["y_m"].to_numpy()
    n = len(points)

    # pH: lower in a round patch (north-west).
    ph_effect = gaussian_patch(
        distance_to_point(x, y, config.PH_PATCH_CENTRE_M),
        config.PH_PATCH_STRENGTH,
        config.PH_PATCH_SIGMA_M,
    )
    ph = config.PH_BASELINE + ph_effect + rng.normal(0, config.PH_NOISE_SD, n)

    # Nitrogen: higher in a round patch (north-east).
    n_effect = gaussian_patch(
        distance_to_point(x, y, config.N_PATCH_CENTRE_M),
        config.N_PATCH_STRENGTH_MG_KG,
        config.N_PATCH_SIGMA_M,
    )
    nitrogen = config.N_BASELINE_MG_KG + n_effect + rng.normal(0, config.N_NOISE_SD_MG_KG, n)

    # Phosphorus: smooth trend, increasing from west to east.
    p_effect = linear_trend(x, config.P_TREND_MG_KG_PER_M, config.FIELD_WIDTH_M / 2)
    phosphorus = config.P_BASELINE_MG_KG + p_effect + rng.normal(0, config.P_NOISE_SD_MG_KG, n)

    # Salinity: higher along a strip, fading with distance from a line.
    sal_effect = gaussian_patch(
        distance_to_line(x, y, config.SALINITY_LINE_START_M, config.SALINITY_LINE_END_M),
        config.SALINITY_STRIP_STRENGTH_DS_M,
        config.SALINITY_STRIP_SIGMA_M,
    )
    salinity = (
        config.SALINITY_BASELINE_DS_M + sal_effect
        + rng.normal(0, config.SALINITY_NOISE_SD_DS_M, n)
    )

    # Clip AFTER adding noise: noise is what could push a value past a limit.
    result = points.copy()
    result["pH"] = np.clip(ph, config.PH_MIN, config.PH_MAX)
    result["nitrogen"] = np.clip(nitrogen, config.CONCENTRATION_MIN, None)
    result["phosphorus"] = np.clip(phosphorus, config.CONCENTRATION_MIN, None)
    result["salinity"] = np.clip(salinity, config.CONCENTRATION_MIN, None)
    return result


# ---------------------------------------------------------------------------
# Stage 3b: dates, collectors, final table and CSV
# ---------------------------------------------------------------------------


def campaign_days(start: str = config.CAMPAIGN_START, end: str = config.CAMPAIGN_END) -> list[str]:
    """Return the weekdays (Mon-Fri) from start to end as ISO strings "YYYY-MM-DD"."""
    return list(pd.bdate_range(start, end).strftime("%Y-%m-%d"))


def assign_dates(x_m: np.ndarray, days: list[str], width: float = config.FIELD_WIDTH_M) -> list[str]:
    """Give each sample a date: the team crosses the field from west to east.

    The field is cut into equal north-south strips, one per day. With 5 days
    and a 500 m field, day 1 covers x = 0-100 m, day 2 covers 100-200 m, ...
    """
    strip = (np.asarray(x_m) / width * len(days)).astype(int)
    strip = np.minimum(strip, len(days) - 1)  # guard: x exactly at the east edge
    return [days[i] for i in strip]


def assign_collectors(
    y_m: np.ndarray,
    dates: list[str],
    rng: np.random.Generator,
    collectors: list[str] = config.COLLECTORS,
    height: float = config.FIELD_HEIGHT_M,
) -> list[str]:
    """Give each sample a collector.

    Each day the strip is split into south, middle and north bands, one per
    collector. Which collector takes which band is shuffled every day with
    rng, as a team rotating tasks would.
    """
    band = (np.asarray(y_m) / height * len(collectors)).astype(int)
    band = np.minimum(band, len(collectors) - 1)  # guard: y exactly at the north edge

    # One shuffled collector order per day, drawn in date order.
    order_for_day = {day: rng.permutation(collectors) for day in sorted(set(dates))}
    return [str(order_for_day[day][b]) for day, b in zip(dates, band)]


def build_reference_dataset(seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    """Create the full clean dataset (9 columns, 100 rows) from one seed.

    Steps: sampling points -> soil values -> lat/lon -> dates -> collectors
    -> round -> select columns. All random draws use one generator, in a
    fixed order, so the same seed always gives the same table.
    """
    rng = np.random.default_rng(seed)
    samples = add_soil_values(jittered_grid_points(rng), rng)

    lat, lon = metres_to_latlon(samples["x_m"], samples["y_m"])
    samples["latitude"] = lat
    samples["longitude"] = lon
    samples["sample_date"] = assign_dates(samples["x_m"], campaign_days())
    samples["collector"] = assign_collectors(samples["y_m"], samples["sample_date"].tolist(), rng)

    # x_m and y_m are dropped here: a real dataset only has GPS coordinates.
    return samples[config.COLUMNS].round(config.ROUNDING)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV with "\n" line endings (same file on every OS)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def read_csv_as_text(path: Path) -> pd.DataFrame:
    """Read a CSV keeping every cell as the exact text in the file.

    keep_default_na=False stops pandas turning "NA", "" etc. into NaN, so we
    see the file exactly as a person opening it would.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------
# Stage 4: corrupt a COPY of the reference data into a messy raw file
# ---------------------------------------------------------------------------


def format_number(value: float, column: str) -> str:
    """Round a number to the column's precision and return it as text."""
    return str(round(value, config.ROUNDING[column]))


def corrupt_value(
    problem_type: str, kind: str, value: str, column: str, rng: np.random.Generator
) -> str:
    """Return a corrupted version of one clean cell (all values are text).

    Examples: ("messy_string", "decimal_comma", "6.5") -> "6,5"
              ("impossible_value", "missing_decimal_point", "6.44") -> "644"
    """
    if problem_type == "missing_value":
        return kind  # the kind is the marker itself, e.g. "NA" or ""

    if kind == "extra_spaces":
        return f"  {value} "
    if kind == "decimal_comma":
        return value.replace(".", ",")
    if kind == "unit_in_cell":
        return f"{value} {config.UNITS[column]}"

    if kind == "missing_decimal_point":
        return value.replace(".", "")
    if kind == "negative":
        return "-" + value

    if kind == "times_factor":
        return format_number(float(value) * config.OUTLIER_FACTOR, column)

    if kind == "missing_minus":
        return value.lstrip("-")

    if kind == "date_dd_mm_yyyy":
        return pd.Timestamp(value).strftime("%d/%m/%Y")
    if kind == "date_long":
        date = pd.Timestamp(value)
        return f"{date.day} {date.strftime('%B %Y')}"  # e.g. "2 March 2026"

    if kind == "name_lowercase":
        return value.lower()
    if kind == "name_extra_spaces":
        return f" {value}  "
    if kind == "name_initials":
        first, last = value.split(" ", 1)
        return f"{first[0]}. {last}"  # "Grace Ingabire" -> "G. Ingabire"

    raise ValueError(f"Unknown corruption kind: {kind}")


def pick_free_cell(
    rows: np.ndarray,
    columns: list[str],
    used: set[tuple[int, str]],
    rng: np.random.Generator,
    preferred_row: int | None = None,
    also_needs: str | None = None,
) -> tuple[int, str]:
    """Choose a (row, column) cell that has not been corrupted yet.

    Only the chosen corrupted rows are considered. If preferred_row is given
    and has a free cell, that row is used (this makes sure every chosen row
    gets at least one problem). also_needs names a second column that must be
    free in the same row (used by the lat/lon swap).
    """
    def is_free(r: int, c: str) -> bool:
        return (r, c) not in used and (also_needs is None or (r, also_needs) not in used)

    candidates = [(r, c) for r in rows for c in columns if is_free(r, c)]
    preferred = [(r, c) for r, c in candidates if r == preferred_row]
    options = preferred or candidates
    row, column = options[rng.integers(len(options))]
    return int(row), column


def make_raw_dataset(
    reference: pd.DataFrame,
    seed: int = config.CORRUPTION_SEED,
    rate: float = config.CORRUPTION_RATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corrupt a copy of the reference table and log every change.

    Args:
        reference: The clean table, read as text (see read_csv_as_text).
            It is NOT changed.
        seed: Seed for the corruption's own random generator.
        rate: Fraction of samples (rows) that get at least one problem.

    Returns:
        (raw, log): the messy table and the corruption log. In the log,
        row_number counts data rows from 1; row 0 means the header.
    """
    rng = np.random.default_rng(seed)
    raw = reference.copy()
    log = []

    def add_log(row: int, column: str, problem: str, original: str, corrupted: str) -> None:
        sample_id = raw.at[row, "sample_id"] if row >= 0 else ""
        log.append([sample_id, row + 1, column, problem, original, corrupted])

    # Step 1: choose which rows will be corrupted.
    n_rows = round(rate * len(raw))
    rows = rng.choice(len(raw), size=n_rows, replace=False)

    # Step 2: cell problems (types 2, 3, 4, 5, 7, 8), at most one per cell.
    used: set[tuple[int, str]] = set()
    plan = [config.CORRUPTION_PLAN[i] for i in rng.permutation(len(config.CORRUPTION_PLAN))]
    for i, (problem, kind, columns) in enumerate(plan):
        preferred = rows[i] if i < n_rows else None  # first n_rows jobs: one per row
        also = "longitude" if kind == "swap_lat_lon" else None
        row, column = pick_free_cell(rows, columns, used, rng, preferred, also)

        if kind == "swap_lat_lon":
            lat, lon = raw.at[row, "latitude"], raw.at[row, "longitude"]
            raw.at[row, "latitude"], raw.at[row, "longitude"] = lon, lat
            add_log(row, "latitude", problem, lat, lon)
            add_log(row, "longitude", problem, lon, lat)
            used.update({(row, "latitude"), (row, "longitude")})
        else:
            original = raw.at[row, column]
            raw.at[row, column] = corrupt_value(problem, kind, original, column, rng)
            add_log(row, column, problem, original, raw.at[row, column])
            used.add((row, column))

    # Step 3: duplicates (type 6), appended at the end like a second data entry.
    n_dups = config.N_EXACT_DUPLICATES + config.N_CONFLICTING_DUPLICATES
    sources = rng.choice(rows, size=n_dups, replace=False)
    for k, source in enumerate(sources):
        new_row = len(raw)
        raw.loc[new_row] = raw.loc[source]
        if k < config.N_EXACT_DUPLICATES:
            add_log(new_row, "(row)", "duplicate", f"row {source + 1}", "exact copy")
        else:
            # Conflicting: same sample_id, one numeric value different.
            clean = [c for c in config.NUMERIC_COLUMNS if (source, c) not in used]
            column = clean[rng.integers(len(clean))]
            original = raw.at[source, column]
            changed = float(original) * rng.uniform(1.1, 1.3)
            raw.at[new_row, column] = format_number(changed, column)
            add_log(new_row, column, "duplicate", original, raw.at[new_row, column])

    # Step 4: messy header names (type 1). Logged as row 0 (the header).
    for original, messy in config.HEADER_RENAMES.items():
        add_log(-1, original, "column_names", original, messy)
    raw = raw.rename(columns=config.HEADER_RENAMES)

    log_df = pd.DataFrame(log, columns=config.LOG_COLUMNS)
    log_df = log_df.sort_values("row_number", kind="stable").reset_index(drop=True)
    return raw, log_df


def write_datasets(
    reference_path: Path = config.REFERENCE_CSV_PATH,
    raw_path: Path = config.RAW_CSV_PATH,
    log_path: Path = config.CORRUPTION_LOG_PATH,
) -> None:
    """Write the reference CSV, then the raw CSV and log made from a copy of it."""
    save_csv(build_reference_dataset(), reference_path)

    # Read the reference back as text, so untouched raw cells are identical
    # to the reference file character for character.
    raw, log = make_raw_dataset(read_csv_as_text(reference_path))
    save_csv(raw, raw_path)
    save_csv(log, log_path)


def main() -> None:
    """Generate all three data files in data/."""
    write_datasets()
    for path in [config.REFERENCE_CSV_PATH, config.RAW_CSV_PATH, config.CORRUPTION_LOG_PATH]:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
