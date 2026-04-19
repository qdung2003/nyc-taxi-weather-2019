from pathlib import Path


here = Path(__file__).resolve()
for candidate in here.parents:
    if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
        PROJECT_ROOT = candidate
        break
else:
    raise RuntimeError("Cannot discover project root from paths.py")


# Main project folders
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
TAXI_DIR = PIPELINE_DIR / "taxi"
WEATHER_DIR = PIPELINE_DIR / "weather"

# Runtime data folders (outside source tree)
DATA_DIR = PROJECT_ROOT / "data"

# Single unified DuckDB for both taxi + weather domains.
WAREHOUSE_DB_FILE = DATA_DIR / "taxi_and_weather.db"
DUCKDB_TEMP_DIR = DATA_DIR / "duckdb_temp"

# Temp paths
TAXI_RAW_TEMP_DIR = DATA_DIR / "taxi_raw_temp"

# Online urls
TAXI_RAW_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
WEATHER_RAW_URL = "https://drive.google.com/file/d/1c3XJIYoh4xh_wAecUMiAW0ac1wXF6yU2/view?usp=drive_link"


