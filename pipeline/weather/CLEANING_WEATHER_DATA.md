# Data Cleaning Strategy - NYC Central Park Weather 2019

## 1. Documentation Source (Data Source)

The data is referenced from the historical Central Park weather station dataset in NYC:

- **Kaggle**: [New York City Weather (1869-2022)](https://www.kaggle.com/datasets/danbraswell/new-york-city-weather-18692022)

---

## 2. Cleaning Plan Summary

| # | Column | Filter Rule | Unit Conversion | Reason / Constraint |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `DATE` | Keep year 2019 | YYYY-MM-DD | Analyze 2019 only. |
| 2 | `PRCP` | `v >= 0` | Inch -> Cm (x 2.54) | Precipitation cannot be negative. |
| 3 | `SNOW` | `v >= 0` | Inch -> Cm (x 2.54) | Snowfall cannot be negative. |
| 4 | `SNWD` | `v >= 0` | Inch -> Cm (x 2.54) | Snow depth cannot be negative. |
| 5 | `TMIN` | `v > -459.67°F` | °F -> °C | Physical lower bound: absolute zero. |
| 6 | `TMAX` | `v > -459.67°F` | °F -> °C | Physical lower bound: absolute zero. |

---

## 3. Detailed Rules

### Rule 1: Unit Conversion
To align with international standards and make analysis easier, the data is converted from imperial units to metric units:
- **Rain/Snow**: multiply by `2.54` to convert inches to centimeters (cm).
- **Temperature**: use `Celsius = (Fahrenheit - 32) * 5/9`.
- **Rounding**: all numeric weather measurements are rounded to `2` decimal places.

### Rule 2: Missing Data Handling
- Rows missing important weather metric values (`PRCP`, `SNOW`, `SNWD`, `TMIN`, `TMAX`) are removed to keep the cleaned table consistent.

---

## 4. Script Execution Flow

The Weather ETL process uses DuckDB and has 4 main steps:

1. **`01_download_weather.py`**:
    - Download the raw CSV from the online source into the runtime data directory (`DATA_DIR/NYC_Central_Park_weather_1869-2022.csv`).

2. **`02_ingest_data.py`**:
    - Use DuckDB `read_csv_auto` to ingest the raw CSV directly into the `TABLE_WEATHER_RAW` table inside `taxi_and_weather.db`.

3. **`03_apply_business_rules.py`**:
    - Read from `TABLE_WEATHER_RAW` and create the `tmp_weather03` temp table.
    - Apply **Business Rules**: filter rows to 2019, remove null metric rows, filter negative values, and block physically impossible temperatures.
    - Convert units (inches to cm, Fahrenheit to Celsius) and round to 2 decimals using SQL CTEs.

4. **`04_optimize_dtypes.py`**:
    - Cast the temp table into the physical target table `TABLE_WEATHER_CLEAN`.
    - Store weather metrics as `FLOAT` and the date column as `DATE`.

---

## 5. Data Type Optimization Strategy

Clean Weather data is stored in the same **DuckDB** file as Taxi data, in the `weather_clean` table. Metrics are standardized to metric units and stored as `FLOAT`, so Feature ETL can join directly with `taxi_clean` without reading intermediate Parquet files.
