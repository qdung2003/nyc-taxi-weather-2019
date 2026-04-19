import shutil
from pipeline.services.tables import TABLE_WEATHER_RAW
from pipeline.services.paths import DATA_DIR

def main(conn):
    # Path to the downloaded raw weather data
    raw_csv = DATA_DIR / "NYC_Central_Park_weather_1869-2022.csv"

    if not raw_csv.exists():
        raise SystemExit(
            f"File not found: {raw_csv}. "
            "Please run etl.py first to download the weather data."
        )

    print(f"Loading raw CSV into '{TABLE_WEATHER_RAW}'...")
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_WEATHER_RAW}"')
    
    # Since weather data is a single CSV file, we can ingest it directly with one statement
    # instead of looping and batching like with the monthly taxi parquet files.
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_WEATHER_RAW}" AS
        SELECT *
        FROM read_csv_auto('{raw_csv.as_posix()}')
        """
    )
    
    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_WEATHER_RAW}"').fetchone()[0]
    print("-" * 30)
    print(f"Step {TABLE_WEATHER_RAW} complete: {row_count:,} rows.")
    print("-" * 30)

    if raw_csv.exists():
        raw_csv.unlink()
        print(f"Removed temp file: {raw_csv}")


