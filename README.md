# Soil Quality Mapper

**Grid cartography and soil quality assessment for agriculture.** The project turns
soil samples with GPS coordinates into continuous maps of pH, nitrogen, phosphorus and
salinity using Inverse Distance Weighting (IDW) written in NumPy, checks the maps with
leave-one-out cross-validation, classifies every 5 m grid cell and every 1 ha parcel
for maize, and exports a parcel evaluation report (CSV, PNG and a multi-page PDF) from
a Streamlit app. All data in this repository is **synthetic**: a simulated
500 m x 400 m field near Rwamagana, Eastern Province, Rwanda. It is not a real farm,
and nothing here is agronomic advice.

![App screenshot](docs/screenshot.png)
*[Screenshot placeholder: to be added by the group.]*

## 1. Quick start

Developed and tested with **Python 3.14.8** on Windows (PowerShell), with the exact
package versions pinned in `requirements.txt` and `requirements-dev.txt`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # app + pytest
.venv\Scripts\python -m src.generate_data                      # (re)create the 3 data files
.venv\Scripts\python -m pytest                                 # run all tests
.venv\Scripts\streamlit run app.py                             # start the app
```

`src.generate_data` is optional: the generated files are committed in `data/`, and a
test checks that they match what the code produces.

Streamlit Community Cloud documents that it supports Python versions that still
receive security updates and defaults to 3.12. We could not confirm from its
documentation whether 3.14 is offered in the deployment dropdown; this is checked in
the deployment stage.

## 2. Project structure

```
data/
  soil_samples_reference.csv   clean synthetic data (answer key, used only by tests)
  soil_samples_raw.csv         deliberately messy copy: what the app loads
  corruption_log.csv           every deliberate change (answer key for cleaning)
src/
  config.py          every constant, threshold and assumption, in one place
  geo.py             metres <-> latitude/longitude; pairwise distances
  generate_data.py   jittered sampling, soil patterns, corruption + log
  cleaning.py        8-step cleaning pipeline and data-quality report
  interpolation.py   IDW, leave-one-out cross-validation, power selection
  fertility.py       fertility classes, parcels, parcel report, one-call pipeline
  plots.py           maps and Seaborn plots (each returns a Matplotlib Figure)
  report.py          multi-page PDF report (Matplotlib PdfPages)
tests/               pytest tests, one file per stage
app.py               Streamlit app (7 tabs)
```

## 3. Data

### The synthetic field

- 100 samples on a **jittered 10 x 10 grid**: one random point inside each
  50 m x 40 m cell, so coverage is even but positions are random. Seed 42
  (`np.random.default_rng(42)`).
- Each value = **baseline + spatial effect + noise**, clipped to physical limits:
  - pH: baseline 6.5, a Gaussian **acidic patch** centred at (100, 300) m, sigma 60 m.
  - Nitrogen: baseline 25 mg/kg, a Gaussian **richer patch** at (380, 280) m.
  - Phosphorus: baseline 15 mg/kg, a smooth **west-to-east trend** (+10 mg/kg).
  - Salinity (EC): baseline 0.4 dS/m, a **strip** whose effect fades with distance
    from a line across the southern part of the field.
- Values are generated in local metres, then converted to latitude/longitude with a
  local flat approximation (origin = south-west corner, -1.9500, 30.4500). Rounding
  to 6 decimals moves points by less than 0.1 m.
- All baselines, strengths and noise levels are **simulation assumptions**, labelled
  as such in `src/config.py`.

### Scenario design changes

The dataset is a designed test scenario, not a measurement. Changes to scenario
parameters are listed here so the history is transparent.

| Date | Parameter (`src/config.py`) | Old | New | Why |
|---|---|---|---|---|
| 2026-10-07 | `PH_PATCH_STRENGTH` | -1.2 (centre pH ~5.3) | -1.75 (centre pH ~4.75) | With the old value no part of the field reached the "Poor" pH class (< 5.1), so the Poor class, Poor areas and their report notes were never exercised. |

Effects after regenerating all data (reported, not tuned): the outlier-check safe
range was unchanged; the pH cross-validation error rose (the patch is steeper);
0.7% of the field became Poor. We did not tune the scenario further to force a Poor
parcel.

### The 8 deliberate data problems

A copy of the reference data was corrupted with a **separate random generator**
(seed 2026), so changing the corruption never changes the clean data. 12 of the 100
samples (12%) were affected; every change is in `data/corruption_log.csv`
(32 entries).

| # | Problem | Examples | Log entries |
|---|---|---|---|
| 1 | Inconsistent column names | `" PH"`, `"Nitrogen "`, `"SALINITY"` | 3 |
| 2 | Different missing-value markers | empty, `NA`, `n/a`, `-`, `?` | 5 |
| 3 | Numbers as messy text | `"  26.9 "`, `"22,4"`, `"12.9 mg/kg"` | 4 |
| 4 | Physically impossible values | pH `592` (5.92 without the point), negative N, P, EC | 4 |
| 5 | Plausible extreme outliers | nitrogen and phosphorus x 3 | 2 |
| 6 | Duplicates | 2 exact copies, 2 same ID with a different value | 4 |
| 7 | GPS errors | missing minus on latitude (2), latitude/longitude swapped (1) | 4 |
| 8 | Inconsistent dates and names | `04/03/2026`, `3 March 2026`, `G. Ingabire`, `eric mugisha` | 6 |

## 4. Cleaning

`cleaning.clean_soil_data` runs 8 steps **in this order**, because each step relies
on the previous ones (numbers must be parsed before limits are checked; cells must be
fixed before duplicates can be recognised as identical):

1. Headers: trim, ignore case, map to the 9 standard names.
2. Trim spaces; missing markers become missing (NaN).
3. Numbers: remove units, decimal comma to point; unreadable text becomes NaN.
4. GPS: restore a missing minus sign, or swap latitude/longitude back, **only if the
   repaired point falls inside the configured field**; rows still outside are dropped.
5. Impossible values (pH outside 0-14, negative amounts) become NaN; no guessing.
6. Dates (3 formats; DD/MM/YYYY read day-first) and collector names (case, spaces,
   initials) mapped to one standard form.
7. Duplicates: exact copies dropped; for the same ID with different values the first
   entry is kept and the conflict is reported.
8. Outliers are **flagged, not deleted**, with a local (spatial) check: a value is
   flagged if |value - median of its 6 nearest neighbours| > 15 x MAD of all such
   differences. A global fence (e.g. 3 x IQR) would flag the real acidic patch and
   salinity strip; comparing with neighbours does not.

### Data-quality report (bundled raw file: 104 rows in, 100 out)

| Step | Fixed | Set to missing | Flagged | Rows dropped | Details |
|---|---|---|---|---|---|
| 1 headers | 3 | 0 | 0 | 0 | |
| 2 spaces + missing markers | 3 | 6 | 0 | 0 | |
| 3 numbers | 4 | 0 | 0 | 0 | units, decimal comma |
| 4 GPS | 4 | 0 | 0 | 0 | 3 missing minus, 1 swap |
| 5 impossible values | 0 | 4 | 0 | 0 | one each for pH, N, P, EC |
| 6 dates + collectors | 7 | 0 | 0 | 0 | 5 dates, 2 names |
| 7 duplicates | 0 | 0 | 0 | 4 | 2 exact, 2 conflicting (S080 nitrogen, S035 salinity) |
| 8 outlier flags | 0 | 0 | 2 | 0 | the two planted outliers |

Some counts exceed the log because duplicated rows carry copies of corrupted cells.

### Recovered vs lost, compared with the reference

| Column | Recovered exactly | Lost (missing) | Flagged | Wrong |
|---|---|---|---|---|
| latitude, longitude | 100 | 0 | 0 | 0 |
| pH | 98 | 2 | 0 | 0 |
| nitrogen | 96 | 3 | 1 | 0 |
| phosphorus | 97 | 2 | 1 | 0 |
| salinity | 98 | 2 | 0 | 0 |
| sample_date, collector | 100 | 0 | 0 | 0 |

**No kept value differs from the reference.** The 9 lost values are the 5 missing
markers and the 4 impossible values, which cannot be recovered without guessing.

Outlier factor c = 15: on this data any c between 9.48 and 22.93 flags both planted
outliers and no clean value (salinity at the strip's edges sets the lower limit).
c = 15 leaves about 1.5x margin on each side.

## 5. Interpolation and validation

- **IDW**: estimate = sum(w_i * v_i) / sum(w_i) with w_i = 1 / d_i^p, on a 5 m grid
  (101 x 81 points), in metres from the south-west corner. A grid point within 1e-6 m
  of a sample takes that sample's value exactly. Missing values are ignored; flagged
  outliers are excluded by default (a switch in the app).
- **Leave-one-out cross-validation**: each sample is predicted from all the others
  for every candidate power (1, 1.5, 2, 2.5, 3, 4, 5, 6). The power with the lowest
  RMSE is chosen per property at run time. The baseline predicts the mean of the other
  samples.

| Property | Baseline RMSE | Chosen p | IDW RMSE | IDW MAE | RMSE / baseline | RMSE as % of mean |
|---|---|---|---|---|---|---|
| pH | 0.371 | 3 | 0.213 | 0.163 | 0.57 | 3.4% |
| Nitrogen (mg/kg) | 5.981 | 2.5 | 3.884 | 3.170 | 0.65 | 13.6% |
| Phosphorus (mg/kg) | 3.042 | 2.5 | 1.783 | 1.397 | 0.59 | 11.6% |
| Salinity (dS/m) | 0.505 | 4 | 0.287 | 0.202 | 0.57 | 42.4% |

IDW beats the mean baseline for every property. Every chosen power lies inside the
candidate range (a test checks this). Salinity has the largest error relative to its
mean, because the strip is narrow (sigma 30 m) compared with the ~45 m sample spacing
and its mean is small.

## 6. Fertility rules

Reference crop: **maize**. Each property is classed **Good / Moderate / Poor**.
Bands are `[lower, upper)`: a value exactly on a boundary belongs to the class that
starts there (pH 5.6 is Good, pH 5.59 is Moderate). All values are in
`src/config.py` (`FERTILITY_BANDS`).

**Law of the minimum**: a grid cell takes the **worst** class of its four properties,
and the property (or properties) at that class is its **limiting factor**. A weighted
score would let a good property hide a poor one, which is not how crops respond.

Source status used below:

- **verified**: we read the bibliographic details / values ourselves.
- **verified (secondary)**: we read the values on a page that cites the original,
  but did not open the original document.
- **to verify**: we could not confirm it; the group must check the primary source.
- **assumption**: our own design choice.

| Property | Poor | Moderate | Good | Basis |
|---|---|---|---|---|
| pH (unitless) | < 5.1 or >= 7.9 | 5.1-5.59 or 7.4-7.89 | 5.6-7.39 | USDA reaction classes; mapping to maize classes is an assumption |
| Nitrogen, nitrate-N (mg/kg) | < 10 | 10-24.9 | >= 25 | Pre-sidedress nitrate test for corn |
| Phosphorus, Mehlich-3 (mg/kg) | < 9 | 9-15.9 | >= 16 | Iowa State PM 1688 categories for corn |
| Salinity, ECe (dS/m) | >= 4 | 2-3.99 | < 2 | USDA salinity classes / Richards (1954) |

### pH

- Class boundaries 5.1, 5.6, 7.4, 7.9 are the edges of the USDA reaction classes
  (strongly acid 5.1-5.5, moderately acid 5.6-6.0, slightly acid 6.1-6.5,
  neutral 6.6-7.3, slightly alkaline 7.4-7.8, moderately alkaline 7.9-8.4).
  Source: Soil Science Division Staff (2017). *Soil Survey Manual*. C. Ditzler,
  K. Scheffe and H.C. Monger (eds.). USDA Handbook 18. Government Printing Office,
  Washington, D.C. <https://www.nrcs.usda.gov/resources/guides-and-instructions/soil-survey-manual>
  - Bibliographic details: **verified** (R package `aqp` documentation of its
    `reactionclass` data set, which cites this edition).
  - Class values: **verified (secondary)**, read in the Wikipedia article
    "Soil pH", which cites NRCS Soil Science Division Staff.
- Calling 5.6-7.3 "Good" for maize: **assumption - to verify**. Web sources we found
  give maize optimum ranges from about 5.5-7.0 to 5.8-6.8, but they were not
  authoritative (farming websites), so we did not cite them.

### Nitrogen

- Our nitrogen column is interpreted as **nitrate-N in mg/kg**: **assumption**.
- Magdoff, F.R., Ross, D. and Amadon, J. (1984). A soil test for nitrogen
  availability to corn. *Soil Science Society of America Journal* 48(6): 1301-1304.
  <https://doi.org/10.2136/sssaj1984.03615995004800060020x>
  - Bibliographic details: **verified** (FAO AGRIS record). The abstract reports a
    greater probability of response to N fertiliser below 36 kg/ha nitrate-N
    (0-30 cm); the mg/kg thresholds below are NOT from this abstract.
- 25 mg/kg ("response to additional N not likely") and 0-10 mg/kg ("full N rate")
  in the top 30 cm: **verified (secondary)**, Spectrum Analytic, "Presidedress Soil
  Nitrate Test" (extension-style article; attributes the test to F. Magdoff).
  <https://spectrumanalytic.com/doc/library/articles/presidedress_soil_nitrate_test_corn.html>
- The test was calibrated in the USA for samples taken when corn is 15-30 cm tall.
  Using it for a Rwandan field at any time of year: **assumption - to verify**.

### Phosphorus

- Extraction method chosen: **Mehlich-3**. Reason: our simulated soils are
  slightly to strongly acidic. Olsen (bicarbonate) is designed for neutral and
  calcareous soils; Mehlich-3 is a multi-element extractant used across a wide
  range of soils, including acidic ones, and appears in many sub-Saharan African
  soil studies (e.g. Ethiopia, Malawi, Zimbabwe in our search). The suitability
  statement is **to verify**.
- Categories (Mehlich-3 colorimetric, corn, ppm = mg/kg): Very Low 0-8 (Poor),
  Low 9-15 (Moderate), Optimum 16-20 and above (Good).
  Source: Mallarino, A. (2003). *Interpreting results of the Mehlich-3 ICP soil
  phosphorus test*. Iowa State University Extension, referring to PM 1688
  "A General Guide for Crop Nutrient and Limestone Recommendations in Iowa".
  <https://crops.extension.iastate.edu/encyclopedia/interpreting-results-mehlich-3-icp-soil-phosphorus-test>
  - Values: **verified (secondary)**. Iowa calibration, not East African:
    **to verify** for local use.

### Salinity

- Our EC is **assumed to be ECe** (saturated paste extract): **assumption**.
- Richards, L.A. (ed.) (1954). *Diagnosis and Improvement of Saline and Alkali
  Soils*. USDA Agriculture Handbook 60. U.S. Government Printing Office,
  Washington, D.C. <https://www.ars.usda.gov/ARSUserFiles/20361500/hb60_pdf/hb60intro.pdf>
  - Bibliographic details: **verified** (USDA-ARS site and R package
    `soilassessment` documentation).
  - The saline threshold ECe >= 4 dS/m: **to verify** (we could not read the PDF).
- Soil Survey Manual salinity classes (nonsaline < 2, very slightly saline 2-4,
  slightly saline 4-8, moderately saline 8-16, strongly saline >= 16 dS/m):
  **to verify**. We only saw them in search-engine summaries of NRCS documents.
- Maize is often described as moderately salt-sensitive, so these classes may be
  generous for maize: **to verify**.

### Parcels and the Poor-area warning (our design choices)

- 20 parcels of 100 m x 100 m (1 ha), numbered P01-P20 from the north-west corner,
  left to right, then row by row southwards.
- **Parcel class** = worst class covering at least **10%** of the parcel
  (**assumption**), so a few noisy grid cells cannot decide a parcel alone.
- **Poor-area warning**: because the 10% rule hides small Poor patches, every parcel
  with *any* Poor area gets a warning (column `poor_area_warning`, the note, the app
  and the PDF), e.g. "Contains Poor area: 9.5% (pH limiting)".
- Fewer than 3 real samples in a parcel is flagged as "less certain" (**assumption**).
- Notes are generic pointers ("liming may be worth investigating"), **not agronomic
  advice**.

### Results on the bundled data

- Field area: Good 34.3%, Moderate 65.0%, Poor 0.7%.
- Parcels: 3 Good (P04, P05, P10), 17 Moderate, 0 Poor. Main limiting factor:
  phosphorus (west of the field); nitrogen in P15 and P20.
- Poor-area warnings: P06 (9.5%) and P01 (4.5%), both pH (the acidic patch).
- Every parcel contains 4-6 real samples.

### Map colours

- Okabe-Ito colour-blind-safe palette (M. Okabe and K. Ito, "Color Universal
  Design"): citation details **to verify**.

## 7. Testing and robustness

**167 automated tests** (pytest), about 75 s in total:

| Test file | Tests | What it shows |
|---|---|---|
| test_sampling | 6 | 100 points, one per cell, inside the field, reproducible |
| test_soil_values | 11 | hand-checked distance/Gaussian examples; patterns where designed; physical limits |
| test_geo | 5 | metres <-> lat/lon round trip < 0.5 m after rounding |
| test_reference_dataset | 9 | 9 columns, valid dates and names, committed CSV up to date |
| test_raw_dataset | 11 | all 8 problems present; the log matches the raw file cell by cell; 10-15% affected |
| test_cleaning | 22 | zero wrong values vs reference; every NaN is a logged corruption; exactly the planted outliers flagged; cleaning the reference changes nothing |
| test_interpolation | 16 | IDW hand examples (2 and 3 points), exact hits, matches a loop version; LOOCV never sees the held-out sample |
| test_plots | 11 | colour bars with units, map extent = field, correct sample markers |
| test_fertility | 36 | every threshold boundary; law of the minimum; 20 parcels; parcel means by hand; P06 warning |
| test_report | 8 | raw file to 20 parcels in one call; overview numbers; PDF has 10 pages |
| test_edge_cases | 19 | the input problems below give clear messages |
| test_app | 13 | every tab renders in all settings; 5 downloads; no figures left open |

**Expected input problems** raise `SoilDataError`, which the app shows as a plain
message; any other exception is treated as a programming error and is not hidden.
Handled cases (each has a test):

- Excel-style files: UTF-8 byte-order mark, semicolon separators, decimal commas.
- Not UTF-8 text, empty file, header only, file > 2 MB or > 1000 rows.
- Missing `sample_id`, `latitude` or `longitude`: error naming the column. Other
  missing columns are added empty; unknown extra columns are ignored; both reported.
- Fewer than 3 usable samples, fewer than 3 distinct locations, or duplicates only:
  error explaining why. Fewer than 7 values of a property: no outlier check for it.
- A property with fewer than 3 values is "not available"; the other maps and the
  fertility classes (from the remaining properties) still work.
- Points outside the field: dropped and counted; if none is inside, the message
  explains that the app is configured for one specific field and gives its location.

## 8. Limitations

- **Synthetic data**: the results demonstrate the method, not a real field. The
  scenario was designed by us, including one documented change (section 3).
- **One configured field**: GPS repair and the field box are specific to this field;
  data from elsewhere needs the origin and size changed in `src/config.py`.
- **IDW** never predicts beyond the highest or lowest sample, so it under-predicts
  peaks (visible for the salinity strip) and draws "bullseyes" around single samples.
  It gives no uncertainty estimate.
- **Leave-one-out cross-validation is slightly optimistic**: it tests predictions
  about 45 m from the nearest sample, not across larger gaps, and the same data are
  used to choose the power and to report its error.
- **Outlier check** catches large errors only (our planted outliers are x 3); a value
  wrong by 30% would probably not be flagged. Its factor was chosen on this dataset.
- **Thresholds**: several are marked "to verify" (calibrated in the USA, read only in
  secondary sources, or our own mapping to maize classes). Our N and EC values are
  assumed to be nitrate-N and ECe.
- **Grid classification** uses estimates; parcels with few samples are less certain,
  and the 10% parcel rule is our own choice.
- **Date convention**: DD/MM/YYYY is assumed; a US-style file would be misread.
- **Not agronomic advice.**

## 9. Use of AI tools

[to be written by the group according to course policy]

## 10. Team and contributions

[to be filled in by the group: names, roles and contributions]
