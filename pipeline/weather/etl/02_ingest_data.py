from pipeline.constants.modules import WEATHER01_DOWNLOAD
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.services.queries import run_with_conn


def create_weather_raw_table(conn) -> None:
    weather_raw_csv = WEATHER01_DOWNLOAD.ensure_weather_raw_file()

    print(f"Loading raw CSV into '{TABLE_WEATHER_RAW}'...")
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_WEATHER_RAW}"')
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_WEATHER_RAW}" AS
        SELECT *
        FROM read_csv_auto('{weather_raw_csv.as_posix()}')
        """
    )


def main(conn):
    create_weather_raw_table(conn)
    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_WEATHER_RAW}"').fetchone()[0]

    print("-" * 30)
    print(f"Step {TABLE_WEATHER_RAW} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
