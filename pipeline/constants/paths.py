from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
for candidate in CURRENT_FILE.parents:
    if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
        PROJECT_ROOT = candidate
        break
else:
    raise RuntimeError("Cannot discover project root from paths.py")


# Main project folders
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
TAXI_DIR = PIPELINE_DIR / "taxi"
WEATHER_DIR = PIPELINE_DIR / "weather"
FEATURE_DIR = PIPELINE_DIR / "feature"

# Runtime data folders (outside source tree)
DATA_DIR = PROJECT_ROOT / "data"

# Single unified DuckDB for both taxi + weather domains.
WAREHOUSE_DB_FILE = DATA_DIR / "taxi_and_weather.db"
DUCKDB_TEMP_DIR = DATA_DIR / "duckdb_temp"

# Temp paths
TAXI_RAW_TEMP_DIR = DATA_DIR / "taxi_raw_temp"
WEATHER_RAW_CSV = DATA_DIR / "NYC_Central_Park_weather_1869-2022.csv"

# EDA results
TAXI_EDA_RESULTS_DIR = TAXI_DIR / "eda" / "results"
WEATHER_EDA_RESULTS_DIR = WEATHER_DIR / "eda" / "results"
FEATURE_EDA_RESULTS_DIR = FEATURE_DIR / "eda" / "results"

# Online urls
TAXI_RAW_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
WEATHER_RAW_URL = "https://drive.google.com/file/d/1c3XJIYoh4xh_wAecUMiAW0ac1wXF6yU2/view?usp=drive_link"
