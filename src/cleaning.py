"""Clean the messy raw soil data and report what was done.

The main entry point is clean_soil_data(raw), which the app calls directly.
Steps run in a fixed order, because each step relies on the previous ones:

    1. headers            -> find the right columns
    2. missing markers    -> "NA", "?", ... become NaN before parsing numbers
    3. numbers            -> "6,5", "24 mg/kg" become floats
    4. GPS                -> fix missing minus / swapped lat-lon, drop unlocatable rows
    5. impossible values  -> pH outside 0-14, negative amounts become NaN
    6. dates and names    -> one standard format each
    7. duplicates         -> only AFTER cell fixes, so copies look identical
    8. outlier flags      -> last, on clean values at correct positions

Data-validity rules live here; fertility rules are separate (Stage 9).

Run as a script to write a clean CSV for inspection into outputs/:
    .venv\\Scripts\\python -m src.cleaning
"""

import io
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.geo import latlon_to_metres, metres_to_latlon, pairwise_distances

COORDINATE_COLUMNS = ["latitude", "longitude"]


class SoilDataError(ValueError):
    """A problem with the INPUT DATA that the user can fix (bad file, wrong field...).

    The app catches only this error and shows its message. Any other exception
    is a programming error: it is not hidden, and the tests should catch it.
    """


def describe_field() -> str:
    """Where this app's field is, for messages: size, SW corner and place name."""
    return (f"a {config.FIELD_WIDTH_M:g} m x {config.FIELD_HEIGHT_M:g} m field with its south-west "
            f"corner at {config.ORIGIN_LAT:.4f}°, {config.ORIGIN_LON:.4f}° "
            f"({config.FIELD_LOCATION_NAME})")


def read_raw_bytes(data: bytes) -> pd.DataFrame:
    """Read an uploaded or bundled CSV into a table of text cells.

    Handles what Excel often produces: a UTF-8 "byte order mark" (BOM) at the
    start, and semicolons instead of commas between columns (common where a
    comma is the decimal separator; decimal commas are fixed later).

    Raises:
        SoilDataError: file too large, not UTF-8 text, empty, unreadable, or
            more rows than MAX_ROWS.
    """
    size_mb = len(data) / 1_000_000
    if size_mb > config.MAX_UPLOAD_MB:
        raise SoilDataError(f"The file is {size_mb:.1f} MB; the limit is {config.MAX_UPLOAD_MB:g} MB "
                            f"(the app is designed for one field of about 100 samples).")
    try:
        text = data.decode("utf-8-sig")  # "-sig" removes a BOM if there is one
    except UnicodeDecodeError:
        raise SoilDataError("The file is not a UTF-8 text CSV. In Excel, use "
                            "'Save As' > 'CSV UTF-8 (Comma delimited)'.") from None
    if not text.strip():
        raise SoilDataError("The file is empty.")

    header = text.splitlines()[0]
    separator = ";" if header.count(";") > header.count(",") else ","
    try:
        table = pd.read_csv(io.StringIO(text), sep=separator, dtype=str, keep_default_na=False)
    except pd.errors.ParserError as error:
        raise SoilDataError(f"The file could not be read as a table: {error}") from None
    if len(table) > config.MAX_ROWS:
        raise SoilDataError(f"The file has {len(table)} rows; the limit is {config.MAX_ROWS}.")
    if table.empty:
        raise SoilDataError("The file has a header but no data rows.")
    return table


def load_raw_csv(path: Path = config.RAW_CSV_PATH) -> pd.DataFrame:
    """Read a CSV file with every cell as text, exactly as in the file."""
    return read_raw_bytes(Path(path).read_bytes())


def step_result(step: str, fixed: int = 0, set_to_nan: int = 0, flagged: int = 0,
                rows_dropped: int = 0, details: str = "") -> dict:
    """One row of the data-quality report."""
    return {"step": step, "fixed": fixed, "set_to_nan": set_to_nan,
            "flagged": flagged, "rows_dropped": rows_dropped, "details": details}


# ---------------------------------------------------------------------------
# Step 1: headers
# ---------------------------------------------------------------------------


def standardise_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list[str], list[str]]:
    """Strip spaces, ignore case, and map headers back to the 9 standard names.

    Unknown extra columns are ignored. A missing optional column (anything
    except config.REQUIRED_COLUMNS) is added empty, so its values count as
    missing.

    Returns:
        (table with the 9 standard columns, report row, ignored columns,
        optional columns that were added empty).

    Raises:
        SoilDataError: if a required column cannot be found.
    """
    standard = {name.lower(): name for name in config.COLUMNS}
    new_names = [standard.get(str(c).strip().lower(), c) for c in df.columns]
    fixed = sum(old != new for old, new in zip(df.columns, new_names))

    out = df.copy()
    out.columns = new_names
    missing_required = [c for c in config.REQUIRED_COLUMNS if c not in out.columns]
    if missing_required:
        raise SoilDataError(
            f"The file is missing required column(s): {', '.join(missing_required)}. "
            f"Expected columns: {', '.join(config.COLUMNS)}. "
            f"Found: {', '.join(map(str, df.columns))}.")

    ignored = [str(c) for c in out.columns if c not in config.COLUMNS]
    added = [c for c in config.COLUMNS if c not in out.columns]
    for column in added:
        out[column] = np.nan
    details = "; ".join(filter(None, [
        f"ignored unknown column(s): {', '.join(ignored)}" if ignored else "",
        f"missing column(s) added empty: {', '.join(added)}" if added else "",
    ]))
    return out[config.COLUMNS], step_result("1 headers", fixed=fixed, details=details), ignored, added


# ---------------------------------------------------------------------------
# Step 2: spaces and missing markers
# ---------------------------------------------------------------------------


def normalise_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Trim spaces from every cell and turn missing-value markers into NaN."""
    markers = {m.lower() for m in config.MISSING_MARKERS}
    out = df.copy()
    trimmed = 0
    for column in out.columns:
        # astype(object): an all-empty column (e.g. one added by step 1) would
        # otherwise be a float column, and .str would fail on it.
        text = out[column].map(lambda v: v if pd.isna(v) else str(v)).astype(object)
        stripped = text.str.strip()
        trimmed += int((stripped != text).sum())
        is_missing = stripped.isna() | stripped.str.lower().isin(markers)
        out[column] = stripped.mask(is_missing)
    set_to_nan = int(out.isna().sum().sum())
    return out, step_result("2 spaces + missing markers", fixed=trimmed,
                            set_to_nan=set_to_nan, details="trimmed spaces; markers -> NaN")


# ---------------------------------------------------------------------------
# Step 3: numbers stored as text
# ---------------------------------------------------------------------------


def parse_number(text: object) -> float:
    """Turn messy number text into a float; NaN if impossible.

    Removes units (mg/kg, dS/m) and changes a decimal comma to a point:
    "24 mg/kg" -> 24.0, "6,5" -> 6.5, "abc" -> NaN.
    """
    if pd.isna(text):
        return np.nan
    cleaned = str(text)
    for unit in set(config.UNITS.values()):
        cleaned = cleaned.replace(unit, "")
    cleaned = cleaned.replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return np.nan


def parse_numbers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Convert soil and coordinate columns from text to floats."""
    out = df.copy()
    fixed = set_to_nan = 0
    for column in config.NUMERIC_COLUMNS + COORDINATE_COLUMNS:
        text = out[column]
        numbers = text.map(parse_number).astype(float)
        has_text = text.notna()
        # "Fixed" = needed more than a plain float() to read (units, comma).
        plain = text.map(lambda t: _is_plain_number(t))
        fixed += int((has_text & numbers.notna() & ~plain).sum())
        set_to_nan += int((has_text & numbers.isna()).sum())
        out[column] = numbers
    return out, step_result("3 numbers", fixed=fixed, set_to_nan=set_to_nan,
                            details="units removed, decimal comma -> point; unreadable -> NaN")


def _is_plain_number(text: object) -> bool:
    """True if text is already a normal number like "6.5"."""
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Step 4: GPS
# ---------------------------------------------------------------------------


def field_bounds(margin_m: float = config.GPS_BOX_MARGIN_M) -> tuple[float, float, float, float]:
    """Return (lat_min, lat_max, lon_min, lon_max) of the field plus a margin."""
    lat_min, lon_min = metres_to_latlon(-margin_m, -margin_m)
    lat_max, lon_max = metres_to_latlon(config.FIELD_WIDTH_M + margin_m,
                                        config.FIELD_HEIGHT_M + margin_m)
    return float(lat_min), float(lat_max), float(lon_min), float(lon_max)


def in_field(lat: pd.Series, lon: pd.Series) -> pd.Series:
    """True where (lat, lon) lies inside the field box. NaN counts as outside."""
    lat_min, lat_max, lon_min, lon_max = field_bounds()
    return lat.between(lat_min, lat_max) & lon.between(lon_min, lon_max)


def fix_gps(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fix only certain GPS errors; drop rows that still cannot be located.

    - Missing minus: if -latitude puts the point inside the field, use it.
    - Swapped: if swapping latitude and longitude puts it inside, swap.
    Anything else outside the field box is dropped (we cannot place it).
    """
    out = df.copy()
    lat, lon = out["latitude"], out["longitude"]
    outside = ~in_field(lat, lon)

    minus_fix = outside & in_field(-lat, lon)
    swap_fix = outside & ~minus_fix & in_field(lon, lat)

    out.loc[minus_fix, "latitude"] = -lat[minus_fix]
    out.loc[swap_fix, ["latitude", "longitude"]] = out.loc[swap_fix, ["longitude", "latitude"]].to_numpy()

    keep = in_field(out["latitude"], out["longitude"])
    out = out[keep].reset_index(drop=True)
    details = f"{int(minus_fix.sum())} missing minus restored, {int(swap_fix.sum())} lat/lon swaps"
    return out, step_result("4 GPS", fixed=int(minus_fix.sum() + swap_fix.sum()),
                            rows_dropped=int((~keep).sum()), details=details)


# ---------------------------------------------------------------------------
# Step 5: physically impossible values
# ---------------------------------------------------------------------------


def remove_impossible(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Set impossible values to NaN. No guessing: 592 is NOT turned into 5.92."""
    out = df.copy()
    impossible = {
        "pH": ~out["pH"].between(config.PH_MIN, config.PH_MAX) & out["pH"].notna(),
        "nitrogen": out["nitrogen"] < config.CONCENTRATION_MIN,
        "phosphorus": out["phosphorus"] < config.CONCENTRATION_MIN,
        "salinity": out["salinity"] < config.CONCENTRATION_MIN,
    }
    for column, mask in impossible.items():
        out.loc[mask, column] = np.nan
    counts = {c: int(m.sum()) for c, m in impossible.items() if m.sum()}
    return out, step_result("5 impossible values", set_to_nan=sum(counts.values()),
                            details=", ".join(f"{c}: {n}" for c, n in counts.items()))


# ---------------------------------------------------------------------------
# Step 6: dates and collector names
# ---------------------------------------------------------------------------


def parse_date(text: object) -> pd.Timestamp:
    """Read a date in any accepted format (config.DATE_FORMATS); NaT if none fit."""
    if pd.isna(text):
        return pd.NaT
    for date_format in config.DATE_FORMATS:
        try:
            return pd.Timestamp(datetime.strptime(str(text), date_format))
        except ValueError:
            continue
    return pd.NaT


def normalise_name(name: str) -> str:
    """Lowercase, remove dots, single spaces: " G. Ingabire " -> "g ingabire"."""
    return " ".join(name.replace(".", " ").lower().split())


def collector_lookup(collectors: list[str] = config.COLLECTORS) -> dict[str, str]:
    """Map accepted name variants to the official name.

    Accepts the full name and "first initial + surname", in any case/spacing.
    """
    lookup = {}
    for official in collectors:
        first, last = official.split(" ", 1)
        lookup[normalise_name(official)] = official
        lookup[normalise_name(f"{first[0]} {last}")] = official
    return lookup


def standardise_dates_and_names(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Parse dates into real dates and map collector names to the official list."""
    out = df.copy()
    lookup = collector_lookup()

    dates = out["sample_date"].map(parse_date)
    iso = dates.map(lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else None)
    dates_fixed = int((out["sample_date"].notna() & dates.notna() & (iso != out["sample_date"])).sum())
    dates_nan = int((out["sample_date"].notna() & dates.isna()).sum())
    out["sample_date"] = pd.to_datetime(dates)

    names = out["collector"].map(lambda n: lookup.get(normalise_name(n)) if pd.notna(n) else None)
    names_fixed = int((names.notna() & (names != out["collector"])).sum())
    names_nan = int((out["collector"].notna() & names.isna()).sum())
    out["collector"] = names

    details = (f"dates fixed {dates_fixed}, unreadable {dates_nan}; "
               f"names fixed {names_fixed}, unknown {names_nan}")
    return out, step_result("6 dates + collectors", fixed=dates_fixed + names_fixed,
                            set_to_nan=dates_nan + names_nan, details=details)


# ---------------------------------------------------------------------------
# Step 7: duplicates
# ---------------------------------------------------------------------------


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Drop exact duplicates; for conflicting ones keep the FIRST entry.

    Returns:
        (clean table, report row, conflicts table listing every value that
        differed between the kept and the dropped copy).
    """
    exact = df.duplicated(keep="first")
    out = df[~exact]

    conflicting = out["sample_id"].duplicated(keep="first")
    conflicts = []
    for _, dropped in out[conflicting].iterrows():
        kept = out[out["sample_id"] == dropped["sample_id"]].iloc[0]
        for column in config.COLUMNS:
            if not (pd.isna(kept[column]) and pd.isna(dropped[column])) and kept[column] != dropped[column]:
                conflicts.append({"sample_id": dropped["sample_id"], "column": column,
                                  "kept_value": kept[column], "dropped_value": dropped[column]})
    out = out[~conflicting].reset_index(drop=True)

    details = f"{int(exact.sum())} exact, {int(conflicting.sum())} conflicting (kept first)"
    result = step_result("7 duplicates", rows_dropped=int(exact.sum() + conflicting.sum()),
                         details=details)
    columns = ["sample_id", "column", "kept_value", "dropped_value"]
    return out, result, pd.DataFrame(conflicts, columns=columns)


# ---------------------------------------------------------------------------
# Step 8: local (spatial) outlier flags
# ---------------------------------------------------------------------------


def local_outlier_scores(
    x: np.ndarray, y: np.ndarray, values: np.ndarray, k: int = config.OUTLIER_NEIGHBOURS
) -> np.ndarray:
    """How unusual each value is compared with its k nearest neighbours.

    residual = value - median of its k nearest neighbours (that have a value)
    score    = |residual| / MAD of all residuals
    A score of 0 means "exactly like its neighbours". NaN values get NaN.
    """
    values = np.asarray(values, dtype=float)
    has_value = ~np.isnan(values)

    # Distance from every sample to every other sample, as an (n, n) table.
    distances = pairwise_distances(np.column_stack([x, y]), np.column_stack([x, y]))
    np.fill_diagonal(distances, np.inf)   # a sample is not its own neighbour
    distances[:, ~has_value] = np.inf     # skip samples without a value

    # Row i of `nearest` holds the indices of sample i's k closest neighbours.
    nearest = np.argsort(distances, axis=1)[:, :k]
    neighbour_values = values[nearest]
    too_far = ~np.isfinite(np.take_along_axis(distances, nearest, axis=1))
    neighbour_values[too_far] = np.nan    # fewer than k neighbours with a value

    with warnings.catch_warnings():       # a row of all-NaN neighbours -> NaN, quietly
        warnings.simplefilter("ignore", RuntimeWarning)
        residuals = values - np.nanmedian(neighbour_values, axis=1)

    r = residuals[~np.isnan(residuals)]
    mad = np.median(np.abs(r - np.median(r))) if len(r) else 0.0
    if mad == 0:
        return np.where(np.isnan(residuals), np.nan, 0.0)  # no spread: nothing stands out
    return np.abs(residuals) / mad


def flag_outliers(df: pd.DataFrame, factor: float = config.OUTLIER_MAD_FACTOR) -> tuple[pd.DataFrame, dict]:
    """Add a boolean <property>_outlier column per soil property. Nothing is deleted.

    A property with fewer than MIN_SAMPLES_FOR_OUTLIER_CHECK values is not
    checked (a sample needs 6 neighbours to be compared with), and gets no flags.
    """
    out = df.copy()
    x, y = latlon_to_metres(out["latitude"].to_numpy(), out["longitude"].to_numpy())
    details = []
    total = 0
    for column in config.NUMERIC_COLUMNS:
        n_values = int(out[column].notna().sum())
        if n_values < config.MIN_SAMPLES_FOR_OUTLIER_CHECK:
            out[f"{column}_outlier"] = False
            details.append(f"{column}: not checked (only {n_values} values)")
            continue
        scores = local_outlier_scores(x, y, out[column].to_numpy())
        flags = np.nan_to_num(scores, nan=0.0) > factor
        out[f"{column}_outlier"] = flags
        total += int(flags.sum())
        details.append(f"{column}: {int(flags.sum())}")
    return out, step_result("8 outlier flags", flagged=total, details=", ".join(details))


# ---------------------------------------------------------------------------
# The whole pipeline
# ---------------------------------------------------------------------------


def clean_soil_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run all cleaning steps in order and build a data-quality report.

    Args:
        raw: The raw table with cells as text (see load_raw_csv).

    Returns:
        (clean, report). clean has the 9 standard columns plus one boolean
        <property>_outlier column per soil property. report is a dict with
        rows_in, rows_out, steps (DataFrame, one row per step), conflicts
        (DataFrame of conflicting duplicate values), ignored_columns,
        added_columns, rows_outside_field and duplicates_removed.
    """
    df, r1, ignored_columns, added_columns = standardise_headers(raw)
    df, r2 = normalise_missing(df)
    df, r3 = parse_numbers(df)
    df, r4 = fix_gps(df)
    df, r5 = remove_impossible(df)
    df, r6 = standardise_dates_and_names(df)
    df, r7, conflicts = remove_duplicates(df)
    df, r8 = flag_outliers(df)

    report = {
        "rows_in": len(raw),
        "rows_out": len(df),
        "steps": pd.DataFrame([r1, r2, r3, r4, r5, r6, r7, r8]),
        "conflicts": conflicts,
        "ignored_columns": ignored_columns,
        "added_columns": added_columns,
        "rows_outside_field": r4["rows_dropped"],
        "duplicates_removed": r7["rows_dropped"],
    }
    return df, report


def compare_with_reference(clean: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Score the cleaning against the clean reference, per column.

    For each column, counts samples whose value was recovered exactly, lost
    (NaN), flagged as an outlier, or wrong (different from the reference).
    """
    ref = reference.copy()
    ref["sample_date"] = pd.to_datetime(ref["sample_date"])
    merged = clean.merge(ref, on="sample_id", suffixes=("", "_ref"))

    rows = []
    for column in config.COLUMNS[1:]:
        value, truth = merged[column], merged[f"{column}_ref"]
        flagged = merged.get(f"{column}_outlier", pd.Series(False, index=merged.index))
        lost = value.isna()
        if column in config.NUMERIC_COLUMNS + COORDINATE_COLUMNS:
            equal = np.isclose(value.astype(float), truth.astype(float), atol=1e-9)
        else:
            equal = (value == truth).to_numpy()
        rows.append({
            "column": column,
            "recovered": int((~lost & ~flagged & equal).sum()),
            "lost_nan": int(lost.sum()),
            "flagged": int(flagged.sum()),
            "wrong": int((~lost & ~flagged & ~equal).sum()),
        })
    summary = pd.DataFrame(rows)
    summary.attrs["samples_missing"] = len(reference) - len(merged)
    return summary


def main() -> None:
    """Clean the raw file, print the report and save a preview CSV in outputs/."""
    clean, report = clean_soil_data(load_raw_csv())
    print(f"Rows in: {report['rows_in']}   rows out: {report['rows_out']}\n")
    print(report["steps"].to_string(index=False))
    print("\nConflicting duplicates (kept first):")
    print(report["conflicts"].to_string(index=False))

    config.OUTPUTS_DIR.mkdir(exist_ok=True)
    clean.to_csv(config.CLEAN_CSV_PREVIEW_PATH, index=False)
    print(f"\nPreview written to {config.CLEAN_CSV_PREVIEW_PATH}")


if __name__ == "__main__":
    main()
