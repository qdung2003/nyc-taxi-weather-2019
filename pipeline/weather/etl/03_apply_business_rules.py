from pipeline.constants.modules import WEATHER02_INGEST
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.constants.times import YEAR
from pipeline.constants.tmp_tables import TMP_WEATHER03
from pipeline.services.queries import ensure_table_exists, run_with_conn


def create_weather03_business_rules(conn) -> None:
    ensure_table_exists(conn, TABLE_WEATHER_RAW, WEATHER02_INGEST.create_weather_raw_table)

    print("Applying weather business rules...")
    conn.execute(f'DROP TABLE IF EXISTS "{TMP_WEATHER03}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{TMP_WEATHER03}" AS
        SELECT
            "DATE",
            ROUND("PRCP" * 2.54, 2) AS PRCP,
            ROUND("SNOW" * 2.54, 2) AS SNOW,
            ROUND("SNWD" * 2.54, 2) AS SNWD,
            ROUND(("TMIN" - 32.0) * 5.0 / 9.0, 2) AS TMIN,
            ROUND(("TMAX" - 32.0) * 5.0 / 9.0, 2) AS TMAX
        FROM "{TABLE_WEATHER_RAW}"
        WHERE "DATE" >= DATE '{YEAR}-01-01'
          AND "DATE" < DATE '{YEAR + 1}-01-01'
          AND "PRCP" >= 0
          AND "SNOW" >= 0
          AND "SNWD" >= 0
          AND "TMIN" > -459.67
          AND "TMAX" > -459.67
        """
    )


def main(conn):
    create_weather03_business_rules(conn)

    input_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TABLE_WEATHER_RAW}"').fetchone()[0] or 0)
    output_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_WEATHER03}"').fetchone()[0] or 0)
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print("Step weather_etl_03_business_rules complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
