# Data Cleaning Strategy - NYC Central Park Weather 2019

This document describes the current Weather ETL cleaning rules implemented in
`pipeline/weather/etl/`.

## Data Source

- NYC Central Park weather dataset, 1869-2022.
- The raw CSV is stored at `data/NYC_Central_Park_weather_1869-2022.csv`.
- The configured year comes from `pipeline/constants/times.py`.

## Cleaning Summary

| # | Column | Rule | Conversion |
| :--- | :--- | :--- | :--- |
| 1 | `DATE` | Keep rows inside `YEAR`. | Cast to `DATE` in the final table. |
| 2 | `PRCP` | Keep `>= 0`. | Inches to centimeters: `value * 2.54`, rounded to 2 decimals. |
| 3 | `SNOW` | Keep `>= 0`. | Inches to centimeters: `value * 2.54`, rounded to 2 decimals. |
| 4 | `SNWD` | Keep `>= 0`. | Inches to centimeters: `value * 2.54`, rounded to 2 decimals. |
| 5 | `TMIN` | Keep `> -459.67 Fahrenheit`. | Fahrenheit to Celsius: `(value - 32) * 5 / 9`, rounded to 2 decimals. |
| 6 | `TMAX` | Keep `> -459.67 Fahrenheit`. | Fahrenheit to Celsius: `(value - 32) * 5 / 9`, rounded to 2 decimals. |

## ETL Flow

1. `01_download_weather.py`
   Downloads the raw Central Park weather CSV into the runtime `data/` directory.

2. `02_ingest_data.py`
   Ingests the CSV into DuckDB table `weather_raw`.

3. `03_apply_business_rules.py`
   Creates temp table `tmp_weather03`, filters rows for the configured year, removes invalid negative precipitation/snow values, filters physically impossible temperatures, converts units to metric, and rounds numeric values to 2 decimals.

4. `04_optimize_dtypes.py`
   Creates final DuckDB table `weather_clean`, casting `DATE` to `DATE` and weather metrics to `FLOAT`.

## Notes

- Rows with null values in the filtered columns do not pass the SQL comparisons and are removed.
- Weather cleaning is intentionally simpler than Taxi cleaning: it validates ranges and standardizes units before writing the final DuckDB table.
