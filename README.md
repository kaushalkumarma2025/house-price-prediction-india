# Gurgaon House Price Prediction

An end-to-end machine learning pipeline to predict residential property prices in Gurgaon, India. The project covers data cleaning, feature engineering, EDA, outlier treatment, missing value imputation, baseline modelling, and feature selection — built from raw scraped data to a production-ready dataset.

---

## Project Structure

```
HOUSE_PRICE_PREDICTION_INDIA/
│
├── Data/
│   ├── Raw/
│   │   ├── flats.csv
│   │   └── houses.csv
│   └── processed/
│       ├── flats_basic_cleaned.csv
│       ├── houses_basic_cleaned.csv
│       ├── Gurgaon_merged.csv
│       ├── Gurgaon_merged_v2.csv
│       ├── Gurgaon_merged_v3.csv
│       ├── Gurgaon_cleaned_final.csv
│       └── Gurgaon_cleaned_final_1.csv
│
├── notebooks/
│   ├── 01_basic_cleaning_flats.ipynb
│   ├── 02_basic_cleaning_houses.ipynb
│   ├── 03_Merging_houses_flats.ipynb
│   ├── 04_Feature_Engineering.ipynb
│   ├── 05_EDA_univariate_analysis.ipynb
│   ├── 06_pandas_profiling.ipynb
│   ├── 07_EDA_Multivariate_analysis.ipynb
│   ├── 08_Outliers.ipynb
│   ├── 09_Missing_Imputation.ipynb
│   ├── 10_baseline_model.ipynb
│   └── 11_feature_selection.ipynb
│
└── Outputs/
    └── pandas_profiling_report.html
```

---

## Pipeline Overview

```
Raw Data (flats.csv + houses.csv)
        ↓
01 + 02: Basic Cleaning (separate)
        ↓
03: Merge + Sector Extraction
        ↓
04: Feature Engineering
        ↓
05 + 06 + 07: EDA (Univariate, Profiling, Multivariate)
        ↓
08: Outlier Treatment
        ↓
09: Missing Value Imputation
        ↓
10: Baseline Model
        ↓
11: Feature Selection
```

---

## Notebooks

### 01 — Basic Cleaning: Flats (`01_basic_cleaning_flats.ipynb`)

**Input:** `Data/Raw/flats.csv`
**Output:** `Data/processed/flats_basic_cleaned.csv`

- Dropped non-informative columns: `link`, `property_id`
- Removed listings with `Price on Request`
- Standardised `price` column — converted Lac to Crore (uniform unit: ₹ Crore)
- Extracted numeric `price_per_sqft` from raw strings (stripped ₹, commas, unit suffixes)
- Derived `area` column from price and price_per_sqft: `area = (price × 10⁷) / price_per_sqft`
- Cleaned `bedRoom`, `bathroom`, `balcony` — extracted integers, replaced "No" with 0
- Standardised `floorNum` — mapped "Ground" → 0, "Basement" → -1, extracted numeric floor
- Cleaned society names — stripped star ratings using regex
- Added `property_type = 'flat'` column
- Handled null rows in bedRoom/bathroom by dropping incomplete records

---

### 02 — Basic Cleaning: Houses (`02_basic_cleaning_houses.ipynb`)

**Input:** `Data/Raw/houses.csv`
**Output:** `Data/processed/houses_basic_cleaned.csv`

- Same cleaning steps as flats with minor differences:
  - Source column for price_per_sqft was named `rate` (renamed)
  - `noOfFloor` used instead of `floorNum` (reconciled in merge step)
  - Dropped duplicates explicitly
- Added `property_type = 'house'` column

---

### 03 — Merging (`03_Merging_houses_flats.ipynb`)

**Input:** `flats_basic_cleaned.csv` + `houses_basic_cleaned.csv`
**Output:** `Gurgaon_merged.csv`

- Concatenated flats and houses into a single DataFrame using `pd.concat`
- Resolved floor column mismatch: filled `floorNum` from `noOfFloor` where missing, then dropped `noOfFloor`
- **Sector Extraction:** Parsed sector name from `property_name` column by splitting on "in" and stripping "Gurgaon"
- Mapped ~40 known locality/colony names to their corresponding Gurgaon sectors (e.g., `"dlf phase 1" → "sector 26"`, `"mg road" → "sector 28"`)
- Dropped `property_name` and `address` columns after extraction
- Filled missing `society` with `'independent'`

---

### 04 — Feature Engineering (`04_Feature_Engineering.ipynb`)

**Input:** `Gurgaon_merged.csv`
**Output:** `Gurgaon_merged_v2.csv`

**Area Columns:**
- Extracted `Super_built_up_area`, `built_up_area`, `Carpet_area`, `Plot_area` from the raw `areaWithType` string using regex
- Converted all area values from sq. yards to sq. ft where applicable

**Additional Rooms:**
- Parsed `additionalRoom` column into 5 binary features: `study room`, `servant room`, `pooja room`, `store room`, `others`

**Age of Possession (`agePossession`):**
- Categorised raw possession dates and age strings into 6 clean categories:
  - `New Property` — 0 to 1 Year Old, Within 3/6 months
  - `Relatively New` — 1 to 5 Year Old
  - `Moderately Old` — 5 to 10 Year Old
  - `Old Property` — 10+ Year Old
  - `Under Construction` — By YYYY, Month-YY/YYYY format dates
  - `Undefined` — genuinely missing/unparseable

**Furnishing Type (K-Means Clustering):**
- Extracted 19 individual furnishing items (fans, ACs, wardrobes, etc.) from `furnishDetails` into a furnishings matrix
- Applied `StandardScaler` + `KMeans` with k=3 (chosen via Elbow Method on WCSS)
- Cluster centroids verified to correctly identify:
  - Cluster 2 → Unfurnished (bare minimum, 2635 properties)
  - Cluster 0 → Semi-Furnished (lights, fans, ACs)
  - Cluster 1 → Furnished (full appliances, beds, sofa, TV, fridge)
- Remapped to: `0 = Unfurnished`, `1 = Semi-Furnished`, `2 = Furnished`
- Saved as `furnishing_type`

**Luxury Score:**
- Scraped `TopFacilities` from an apartments dataset to fill missing `features`
- Applied `MultiLabelBinarizer` on amenity lists, then computed a weighted luxury score per property

---

### 05, 06, 07 — EDA

**05 — Univariate Analysis (`05_EDA_univariate_analysis.ipynb`):**
Distribution plots for all individual features — price, area, bedrooms, bathrooms, sector, agePossession, luxury_score.

**06 — Pandas Profiling (`06_pandas_profiling.ipynb`):**
Auto-generated HTML profiling report saved to `Outputs/pandas_profiling_report.html`.

**07 — Multivariate Analysis (`07_EDA_Multivariate_analysis.ipynb`):**
Correlation heatmaps, scatter plots (price vs area, price vs sector), boxplots by property type and furnishing.

---

### 08 — Outlier Treatment (`08_Outliers.ipynb`)

**Input:** `Gurgaon_merged_v2.csv`
**Output:** `Gurgaon_merged_v3.csv`

- Dropped duplicates detected post-merge
- Removed null price rows
- **Price:** IQR-based outlier detection; retained domain-valid luxury properties
- **Price per sqft:** Identified unit mismatch — some plot areas were in sq. yards, not sq. ft. Fixed by multiplying by 9 where `area < 1000`. Capped `price_per_sqft > 50,000`
- **Area:** Removed extreme values (`area > 100,000`). Manually corrected ~10 clearly erroneous area entries by cross-referencing price and property context. Dropped 10 unfixable rows
- **bedRoom:** Capped at 10 bedrooms; removed statistical outliers beyond IQR bounds
- Dropped `areaWithType`, `description`, `rating` columns (no longer needed)

---

### 09 — Missing Value Imputation (`09_Missing_Imputation.ipynb`)

**Input:** `Gurgaon_merged_v3.csv`
**Output:** `Gurgaon_cleaned_final.csv`

- Dropped `facing` column (too many nulls, low predictive value)
- `floorNum`: filled with column median
- **`built_up_area` (most complex):** Imputed using fixed area ratios derived from non-null rows:
  - If `super_built_up_area` and `carpet_area` present → `built_up_area = mean(super/built ratio, carpet/built ratio)`
  - If only `super_built_up_area` → divide by 1.135
  - If only `carpet_area` → divide by 0.844
  - If only `Plot_area` → divide by 0.556
  - Anomaly fix: properties with `built_up_area < 2000` and `price > 2.5Cr` had their area replaced with the `area` column value (data entry error)
- Dropped `Plot_area`, `super_built_up_area`, `carpet_area` after imputation (consolidated into `built_up_area`)
- **`agePossession` — 3-level mode-based imputation:**
  - Level 1: Replace `Undefined` with mode within same `sector` + `property_type`
  - Level 2: Remaining → mode within same `sector`
  - Level 3: Remaining → mode within same `property_type`
  - `undefined` (lowercase, NaN-origin) → replaced with global mode

---

### 10 — Baseline Model (`10_baseline_model.ipynb`)

**Input:** `Gurgaon_cleaned_final.csv`
**Output:** `Gurgaon_cleaned_final_1.csv`

**Final Pre-Modelling Cleanup:**
- Manually resolved remaining `sector unknown` / `not gurgaon` sector values using society name lookup
- Extracted numeric sector numbers using regex (`sector 7` → `7.0`)
- Fixed `balcony` — replaced `'3+'` with `3`, cast to int
- Dropped `society` and `price_per_sqft` (leaked/redundant)

**Baseline Model — Linear Regression:**
- OneHotEncoded `property_type` and `agePossession` (`drop_first=True`)
- Categorised `luxury_score` into `Low / Medium / High` bins, then OneHotEncoded
- Standard scaled all features
- 80/20 train-test split (`random_state=42`)

**Results:**

| Metric | Score |
|---|---|
| R² (Test) | **0.887** |
| R² (Train) | **0.872** |
| RMSE | **0.865** |

A strong baseline — Linear Regression achieving ~89% R² on raw features without hyperparameter tuning.

---

### 11 — Feature Selection (`11_feature_selection.ipynb`)

**Input:** `Gurgaon_cleaned_final_1.csv`

Applied **8 feature importance methods** in parallel and merged results into a single comparison table:

| # | Method | Key Finding |
|---|---|---|
| 1 | Pearson Correlation | `built_up_area` (0.69), `bathroom` (0.60), `bedRoom` (0.51) |
| 2 | Random Forest Importance | `built_up_area` dominates at 60% importance |
| 3 | Gradient Boosting Importance | Same pattern — `built_up_area` at 64% |
| 4 | Permutation Importance | `built_up_area` 0.63, `property_type_house` 0.15, `sector` 0.13 |
| 5 | LASSO Coefficients | `built_up_area`, `bathroom`, `property_type_house` highest |
| 6 | RFE (Random Forest) | Confirms tree-based ranking |
| 7 | Linear Regression Coefficients | Similar to LASSO |
| 8 | SHAP Values | `built_up_area` 1.18, `sector` 0.40, `property_type_house` 0.39 |

**Final Averaged Feature Importance (normalised):**

| Feature | Score |
|---|---|
| `built_up_area` | 0.529 |
| `property_type_house` | 0.141 |
| `bathroom` | 0.105 |
| `sector` | 0.082 |
| `servant room` | 0.042 |
| `store room` | 0.025 |
| `floorNum` | 0.021 |
| `study room` | 0.020 |
| `balcony` | 0.012 |
| `agePossession_*` | ~0.004–0.010 |
| `luxury_score_*` | ~0.005–0.010 |
| `furnishing_type` | -0.009 |
| `bedRoom` | -0.013 |

**Key Insights:**
- `built_up_area` is the dominant feature by a large margin — accounts for ~53% of explained variance in tree models
- `bedRoom` scores negatively because it is dominated by `built_up_area` (multicollinearity) and `bathroom` captures the same signal more cleanly
- `furnishing_type` had a negative coefficient due to incorrect K-Means cluster labelling (fixed: cluster labels remapped based on centroid inspection)
- `sector` is the 4th most important feature — confirming location matters significantly in Gurgaon pricing
- `pooja room` and `others` consistently ranked lowest across all 8 methods — candidates for dropping

---

## Key Decisions & Lessons

| Decision | Rationale |
|---|---|
| Dropped `not gurgaon` sector rows | No location signal; non-comparable pricing dynamics outside Gurgaon |
| Used `built_up_area` not `area` | `area` was derived from price (data leakage risk); `built_up_area` is independently measured |
| K-Means for furnishing (k=3) | Elbow method confirmed 3 clusters; domain knowledge maps to unfurnished/semi/furnished |
| Mode-based imputation for `agePossession` | Sector + property_type is a stronger prior than global mode |
| Kept `bedRoom` despite negative importance | Tree models handle redundancy; dropping needs multi-method consensus |

---

## Results Summary

| Stage | Model | R² |
|---|---|---|
| Baseline | Linear Regression | 0.887 |
| Feature Selection | (next step: model selection) | TBD |

---

## Tech Stack

- Python 3.13
- pandas, numpy, matplotlib, seaborn
- scikit-learn (LinearRegression, RandomForest, GradientBoosting, LASSO, RFE, Permutation Importance)
- SHAP
- KMeans clustering
- ydata-profiling (pandas-profiling)

---

## Author

Kaushal | ML Engineer in progress