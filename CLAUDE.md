# CLAUDE.md

University group project (assessed work). Explain what you do and why in simple terms, and keep the code readable for students.

## Project
"Grid Cartography and Soil Quality Assessment for Agriculture."
Brief: grid spatial interpolation (pH, nitrogen, phosphorus, salinity) from sampled GPS coordinates, with heat map modelling. Deliverable: a soil map app showing 2D fertility grids and exporting parcel evaluation reports.

Libraries: Python, NumPy, Pandas, Matplotlib, Seaborn, Streamlit (lecturer approved Streamlit instead of Tkinter). Do NOT use SciPy, scikit-learn, or any library not listed without asking first.

## Locked design (do not change without asking)
- Synthetic dataset, 100 samples, one simulated 500 m x 400 m field in Rwanda's Eastern Province. It is synthetic and must not be described as a real farm.
- Sampling: jittered 10x10 grid (one random point inside each 50 m x 40 m cell). Reproducible with `np.random.default_rng(42)`.
- 9 columns: sample_id, latitude, longitude, pH, nitrogen, phosphorus, salinity, sample_date, collector.
- Units: pH unitless (0-14); nitrogen and phosphorus in mg/kg; salinity as EC in dS/m; lat/lon in decimal degrees.
- Spatial patterns: value = baseline + spatial effect + small random noise. Lower-pH patch (Gaussian, centre ~ (100, 300) m), higher-N patch, higher-salinity strip (effect fades with distance from a line), smooth phosphorus trend.
- Generate data in local metres, then convert to lat/lon. For interpolation, convert lat/lon back to local metres.
- Files:
  - `data/soil_samples_reference.csv` (clean synthetic data, for testing only)
  - `data/soil_samples_raw.csv` (deliberately messy, what the app loads)
  - `data/corruption_log.csv`
- 8 deliberate data problems, ~10-15% of rows:
  1. inconsistent column names
  2. different missing-value markers
  3. numbers stored as messy strings
  4. physically impossible values (e.g. pH > 14, negative N)
  5. a few outliers to FLAG, not delete
  6. duplicates / conflicting IDs
  7. GPS errors (missing minus sign, swapped lat/lon)
  8. inconsistent date formats and collector names
- Data validity (cleaning) rules are separate from fertility rules. Fertility thresholds come later and must be sourced or documented as assumptions.
- Interpolation: Inverse Distance Weighting written in NumPy, which must handle a grid point that exactly matches a sample point.

## Structure
`data/`, `src/` (`__init__.py`, `config.py`, `geo.py`, `generate_data.py`, `cleaning.py`, `interpolation.py`, `fertility.py`, `plots.py`, `report.py`), `tests/`, `app.py` (Streamlit), `requirements.txt`, `README.md`, `.gitignore`

## Roadmap (one stage at a time; test each stage before moving on)
1. Setup
2. Jittered sampling points (plot them to check coverage)
3. Soil patterns + lat/lon + reference CSV
4. Corrupt into raw CSV + log
5. Cleaning, checked against the reference
6. IDW (two-point hand test first)
7. Streamlit skeleton
8. Heat maps
9. Fertility rules, parcels, report
10. Connect everything in app.py
11. Error handling, edge cases, README
12. Defence preparation
13. Deploy to Streamlit Community Cloud

## Working rules
- Only do the current stage. No extra features.
- Explain each step before or after doing it so the group can defend it in the presentation.
- Git: NEVER add "Co-Authored-By" lines or any AI attribution to commit messages or PR descriptions. Write short, plain commit messages. Only commit and push when asked.
- Git: stage files by name (no `git add -A`), so nothing unexpected gets committed.
- Save preview plots into `outputs/` inside the project (git-ignored, never committed).
- Windows, PowerShell, with a `.venv` in the project folder (inside OneDrive). Run Python as `.venv\Scripts\python` (activation scripts may be blocked).

## Quality bar and teaching mode

### Teaching mode
- We are beginners. Before writing code for a stage, explain the idea in plain language with a tiny example. After writing it, walk through the code section by section and tell us what to check.
- Keep each stage small enough that we can explain every line in our defence.

### Quality bar (masters level)
- All constants (field size, seed, zone centres, baselines, noise levels) live in `src/config.py`, not scattered in code.
- Every function has a docstring and type hints; prefer small, pure functions.
- Every stage gets automated tests in `tests/` using pytest (dev-only: put pytest in `requirements-dev.txt`, not `requirements.txt`).
- Stage 6 includes leave-one-out cross-validation of IDW (RMSE and MAE), compared with a mean-value baseline, and is used to choose the IDW power.
- Stage 5 produces a data-quality report (problems found, fixed, flagged, dropped), checked against the reference CSV.
- Every scientific assumption (e.g. fertility thresholds) is cited or explicitly labelled as an assumption in the README.
- The README will end up as a short methods write-up: data, methods, validation results, limitations.
