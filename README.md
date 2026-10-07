# soil-quality-mapper

Grid cartography and soil quality assessment for agriculture: IDW interpolation of
pH, nitrogen, phosphorus and salinity from sampled GPS points, heat maps, fertility
classes and parcel reports, in a Streamlit app.

All data in this repository is **synthetic** (a simulated 500 m x 400 m field in
Rwanda's Eastern Province). It is not a real farm.

*(The full methods write-up is completed in Stage 11.)*

## Fertility rules

Reference crop: **maize**. Each property is classed **Good / Moderate / Poor**; the
overall class of a grid cell is the **worst** of the four (Liebig's law of the
minimum). Bands are `[lower, upper)`: a value exactly on a boundary belongs to the
class that starts there (e.g. pH 5.6 is Good, pH 5.59 is Moderate). All values are
in `src/config.py` (`FERTILITY_BANDS`).

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

### Parcel rules (our design choices)

- Parcels are 100 m x 100 m (1 ha); 20 parcels numbered P01-P20 from the
  north-west corner, left to right, then row by row southwards.
- Parcel class = worst class that covers at least **10%** of the parcel:
  **assumption**, so that a few noisy grid cells cannot decide a parcel alone.
- Fewer than 3 real samples in a parcel is flagged as "less certain": **assumption**.
- Notes in the report are generic pointers ("liming may be worth investigating"),
  **not agronomic advice**.

### Map colours

- Okabe-Ito colour-blind-safe palette (M. Okabe and K. Ito, "Color Universal
  Design"): citation details **to verify**.

## Scenario design changes

The dataset is a designed test scenario, not a measurement. Changes to scenario
parameters are listed here so the history is transparent.

| Date | Parameter (`src/config.py`) | Old | New | Why |
|---|---|---|---|---|
| 2026-10-07 | `PH_PATCH_STRENGTH` | -1.2 (centre pH ~5.3) | -1.75 (centre pH ~4.75) | With the old value no part of the field reached the "Poor" pH class (< 5.1), so the Poor class, Poor areas and their report notes were never exercised. The stronger patch adds a strongly acidic zone. |

Effects after regenerating all data (reported, not tuned):

- Outlier check: safe range for c is still 9.48 < c < 22.93 (salinity sets the lower
  limit); c = 15 is unchanged. Zero clean reference values flagged.
- LOOCV: pH RMSE rose (best 0.213 at p = 3, baseline 0.371) because the patch is
  steeper; other properties unchanged.
- Fertility: 0.7% of the field is now Poor (inside P01 and P06). No parcel is Poor,
  because the Poor share in P06 (9.5%) is just under the 10% parcel rule. We did not
  tune the scenario further to force a Poor parcel.
