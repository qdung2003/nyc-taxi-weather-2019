# Data Cleaning Strategy - NYC Yellow Taxi 2019

This document describes the current Taxi ETL cleaning rules implemented in
`pipeline/taxi/etl/`.

## Data Sources

- NYC TLC Yellow Taxi Trip Record parquet files for `YEAR` from `pipeline/constants/times.py`.
- NYC TLC Yellow Taxi data dictionary and fare documentation are used as the rule reference.

## Cleaning Summary

| # | Column(s) | Rule |
| :--- | :--- | :--- |
| 1 | `tpep_pickup_datetime`, `tpep_dropoff_datetime` | Keep trips fully inside `YEAR`; require pickup before dropoff. |
| 2 | `VendorID` | Keep `1` and `2`. |
| 3 | `passenger_count` | Keep `1..5`. |
| 4 | `RatecodeID` | Keep `1..6`. |
| 5 | `store_and_fwd_flag` | Keep `Y` and `N`. |
| 6 | `PULocationID`, `DOLocationID` | Keep taxi zone IDs `1..263`. |
| 7 | `payment_type` | Keep `1..4`. |
| 8 | `congestion_surcharge` | Treat null as `0`; keep `0`, `0.75`, `2.5`. |
| 9 | `trip_distance` | Keep values greater than `0`; later capped by upper bounds. |
| 10 | `fare_amount`, `extra` | Validate fare after the 2.5 USD congestion-shift check; keep normalized `extra` in `{0, 0.5, 1.0}`. |
| 11 | `mta_tax` | Keep `0.5`. |
| 12 | `tip_amount`, `tolls_amount` | Keep non-negative values. |
| 13 | `improvement_surcharge` | Keep `0.3`. |
| 14 | `total_amount` | Keep non-negative values; later capped by upper bounds. |
| 15 | `payment_type`, `tip_amount` | Remove non-card payments `2, 3, 4` when `tip_amount > 0`. |

## ETL Flow

1. `01_download_yellow_tripdata.py`
   Downloads the 12 monthly Yellow Taxi parquet files for the configured year.

2. `02_ingest_data.py`
   Ingests raw parquet files into DuckDB table `taxi_raw`.

3. `03_apply_business_rules.py`
   Creates temp table `tmp_taxi03` by selecting the final Taxi columns and applying the strict business filters above.

4. `04_apply_upper_bounds.py`
   Creates temp table `tmp_taxi04` by applying dynamic upper bounds to:
   `trip_distance`, `fare_amount`, `tip_amount`, `tolls_amount`, and `total_amount`.

   It first tries to read `pipeline/taxi/eda/results/07_before_upper_bounds.json`.
   If that file is missing or invalid, it computes the upper bounds directly from `tmp_taxi03`.

5. `05_optimize_dtypes.py`
   Creates final DuckDB table `taxi_clean` with compact types such as `UTINYINT`, `USMALLINT`, `FLOAT`, `TIMESTAMP`, and boolean `store_and_fwd_flag`.

## Notes

- ETL 03 filters rows; it does not rewrite `fare_amount`, `extra`, or `congestion_surcharge`.
- ETL 04 is the outlier-removal step for distance and money columns.
- The final cleaned Taxi dataset is stored in DuckDB, not as a committed output file.
