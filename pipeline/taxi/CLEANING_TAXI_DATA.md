# Data Cleaning Strategy - NYC Yellow Taxi 2019

## 1. Documentation Sources (Wayback)

The 2019 data is referenced against official TLC documentation:

1. [Data Dictionary - Yellow Trip Records (2019)](https://web.archive.org/web/20190808095554/https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
2. [Taxi Fare Rates (2019)](https://web.archive.org/web/20190801021305/https://www.nyc.gov/site/tlc/passengers/taxi-fare.page)
3. [TLC Passenger FAQ](https://web.archive.org/web/20260122112926/https://www.nyc.gov/site/tlc/passengers/passenger-frequently-asked-questions.page)
4. [Trip Record User Guide](https://web.archive.org/web/20190810080518/https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf)

---

## 2. Cleaning Plan Summary

| # | Column | Filter Range | Evidence (text) | Link |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `VendorID` | `[1, 2]` | Valid TPEP/LPEP provider codes. | 1 |
| 2 | `passenger_count` | `[1, 5]` | Taxis carry up to 5 passengers under TLC rules, excluding lap children. | 3 |
| 3 | `RatecodeID` | `[1, 6]` | Valid RatecodeID values are 1-6. | 1 |
| 4 | `store_and_fwd_flag` | `['Y', 'N']` | The flag only accepts `Y` or `N`. | 1 |
| 5 | `PULocationID`, `DOLocationID` | `[1, 263]` | “...pickup or drop-off... populated by numbers ranging from 1-263.” | 4 |
| 6 | `payment_type` | `[1, 4]` | Keep the main groups; remove 5 (Unknown) and 6 (Void). | 1 + Decision |
| 7 | `trip_distance` | `(0, 19.8]` | Keep values greater than 0 and cap by the EDA 07 upper bound. | Decision |
| 8 | `fare_amount` | `[0, 52.28]` | Keep non-negative values and cap by the upper bound. | Decision |
| 9 | `extra` | `{0.0, 0.5, 1.0}` | Keep valid surcharge levels. | 2 + Decision |
| 10 | `mta_tax` | `{0.5}` | “Plus 50 cents MTA State Surcharge...” | 2 + Decision |
| 11 | `improvement_surcharge` | `{0.3}` | “Plus $0.3 Improvement Surcharge.” | 2 + Decision |
| 12 | `congestion_surcharge` | `{0, 0.75, 2.5}` | “Plus $2.50 (Yellow Taxi) ...”; normalize `null -> 0`. | 2 + EDA |
| 13 | `tip_amount` | `[0, 12.35]` | Constrain by `payment_type` and cap by the upper bound. | Decision |
| 14 | `tolls_amount` | `[0, 6.45]` | Keep non-negative values and cap by the upper bound. | Decision |
| 15 | `total_amount` | `[0, 77.07]` | Keep non-negative values and cap by the upper bound. | Decision |

Upper bounds are read from `second_pass_value` in `pipeline/taxi/eda/results/07_before_upper_bounds.json`; if that file is missing or invalid, ETL 04 computes the bounds directly from `tmp_taxi03`.

---

## 3. Detailed Rules

### Rule 1: Surcharge and amount filtering
Money columns are first constrained by business rules, then long-tailed columns are handled with dynamic upper bounds.
- `extra` only keeps valid surcharge levels `{0, 0.5, 1.0}`.
- `fare_amount`, `tip_amount`, `tolls_amount`, and `total_amount` are capped in ETL 04.

### Rule 2: Tip vs Payment Type
TLC mainly records automatic tips through credit-card payments.
- **Rule**: Remove rows where `payment_type` is in `{2, 3, 4}` but `tip_amount > 0`, because automatic tips are primarily associated with credit-card payments.

### Rule 3: Dynamic Upper Bounds
Use **EDA 07** results to get upper bounds for `trip_distance`, `fare_amount`, `tip_amount`, `tolls_amount`, and `total_amount`. If the EDA 07 JSON is unavailable, `04_apply_upper_bounds.py` computes the upper bounds from the `tmp_taxi03` temp table.

---

## 4. Script Execution Flow

The ETL process has 5 main stages:

1. **`01_download_yellow_tripdata.py`**: Download the 12 monthly raw files from TLC CloudFront.
2. **`02_ingest_data.py`**: Load all 12 files into the DuckDB `taxi_raw` table.
3. **`03_apply_business_rules.py`**:
    - Keep 2019 records and require `pickup < dropoff`.
    - Remove the `airport_fee` column.
    - Apply the base business rules to the intermediate table.
4. **`04_apply_upper_bounds.py`**: Remove outliers using dynamic upper bounds.
5. **`05_optimize_dtypes.py`**:
    - Cast columns to smaller types so the final DuckDB table is more compact.
    - Save the result to the DuckDB `taxi_clean` table.

---

## 5. Data Type Optimization Strategy

The cleaned data is optimized by converting wide types to smaller DuckDB types such as `UTINYINT`, `USMALLINT`, `FLOAT`, `TIMESTAMP`, and `BOOLEAN`. The final `taxi_clean` table is used directly by Feature ETL and EDA, and no cleaned Parquet output is committed to the repository.
