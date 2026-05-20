# NYC Taxi and Weather Data Pipeline

DuckDB pipeline for NYC Yellow Taxi and NYC Central Park weather data. The
project runs ETL steps, writes EDA JSON outputs, and builds a single HTML
dashboard for both domains.

## Data Sources

- Taxi: NYC TLC Yellow Taxi Trip Record Data.
- Weather: NYC Central Park weather data, 1869-2022.

## Project Structure

```text
pipeline/
  constants/              # paths, table names, module loaders, shared settings
  services/               # DuckDB connection, query helpers, JSON helpers
  taxi/
    etl/                  # Taxi ETL 01-05
    eda/scripts/          # Taxi EDA 01-08
    eda/results/          # Generated Taxi EDA JSON
  weather/
    etl/                  # Weather ETL 01-04
    eda/scripts/          # Weather EDA 01-05
    eda/results/          # Generated Weather EDA JSON
  dashboard/              # Dashboard HTML/CSS/JS and generated data.js
data/                     # Local raw data, DuckDB database, temp files
main.py                   # CLI entrypoint
```

## Setup

Requires Python 3.11+.

```powershell
uv sync
```

Run commands through the project virtual environment:

```powershell
.venv\Scripts\python.exe main.py --help
```

## CLI

Run Taxi ETL, then Taxi EDA:

```powershell
.venv\Scripts\python.exe main.py --taxi
```

Run Weather ETL, then Weather EDA:

```powershell
.venv\Scripts\python.exe main.py --weather
```

Run Taxi and Weather pipelines:

```powershell
.venv\Scripts\python.exe main.py --all
```

Run every script in one group:

```powershell
.venv\Scripts\python.exe main.py --list taxi etl
.venv\Scripts\python.exe main.py --list taxi eda
.venv\Scripts\python.exe main.py --list weather etl
.venv\Scripts\python.exe main.py --list weather eda
```

Run one or more specific steps:

```powershell
.venv\Scripts\python.exe main.py --only taxi etl 04
.venv\Scripts\python.exe main.py --only taxi eda 07 08
.venv\Scripts\python.exe main.py --only weather etl 04
.venv\Scripts\python.exe main.py --only weather eda 04 05
```

Build dashboard data and open the dashboard HTML:

```powershell
.venv\Scripts\python.exe main.py dashboard
```

## Taxi ETL

1. `01_download_yellow_tripdata.py`: download 12 monthly Yellow Taxi parquet files for `YEAR`.
2. `02_ingest_data.py`: ingest raw taxi parquet files into DuckDB.
3. `03_apply_business_rules.py`: apply taxi business rules and remove `airport_fee` from the cleaned temp table.
4. `04_apply_upper_bounds.py`: apply upper bounds for money columns using EDA 07 JSON when available, otherwise compute them.
5. `05_optimize_dtypes.py`: create the final optimized taxi table.

## Taxi EDA

1. `01_schemas.py`: compare raw taxi file schemas with the DuckDB raw table schema.
2. `02_low_duplicates.py`: profile low-cardinality columns.
3. `03_high_duplicates.py`: profile high-cardinality datetime and numeric columns.
4. `04_payments.py`: check payment and tip consistency.
5. `05_before_business_rules.py`: measure taxi business-rule impact before cleaning.
6. `06_after_business_rules.py`: profile data after business rules.
7. `07_before_upper_bounds.py`: simulate upper bounds for money columns.
8. `08_after_upper_bounds.py`: profile data after upper-bound filtering.

## Weather ETL

1. `01_download_weather.py`: download the raw Central Park weather CSV.
2. `02_ingest_data.py`: ingest the raw weather CSV into DuckDB.
3. `03_apply_business_rules.py`: filter to `YEAR`, validate weather values, and convert units.
4. `04_optimize_dtypes.py`: create the final optimized weather table.

## Weather EDA

1. `01_schemas.py`: compare the raw CSV schema with the DuckDB raw table schema.
2. `02_low_duplicates.py`: profile low-cardinality columns.
3. `03_high_duplicates.py`: profile `DATE` and `PRCP`, including selected-year filter details for `DATE`.
4. `04_before_business_rules.py`: measure weather business-rule impact before cleaning.
5. `05_after_business_rules.py`: profile data after weather business rules.

## Dashboard

The dashboard reads generated JSON from:

- `pipeline/taxi/eda/results/`
- `pipeline/weather/eda/results/`

It writes:

- `pipeline/dashboard/data.js`

Then `pipeline/dashboard/dashboard.html` renders Taxi and Weather EDA tabs in one UI.
The dashboard JavaScript is split by responsibility:

- `dashboard-state.js`: payload normalization and current domain state.
- `dashboard-templates.js`: HTML templates for EDA steps.
- `dashboard-utils.js`: shared formatting and DOM helpers.
- `dashboard-charts.js`: SVG chart rendering.
- `dashboard-renderers.js`: per-step renderers.
- `dashboard.js`: navigation and step bootstrapping.

## Runtime Data

Runtime files are stored under `data/`, including raw taxi parquet files, the raw
weather CSV, the DuckDB database, and DuckDB temp files.

Generated runtime data, local environments, and scratch files are ignored by git.
Dashboard HTML/CSS/JS files are source files; `pipeline/dashboard/data.js` is
generated.
