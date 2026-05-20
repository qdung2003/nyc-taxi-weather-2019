from pipeline.constants.modules import WEATHER03_BUSINESS
from pipeline.constants.tables import TABLE_WEATHER_CLEAN
from pipeline.constants.tmp_tables import TMP_WEATHER03
from pipeline.services.queries import ensure_table_exists, run_with_conn


def create_weather04_optimize_dtypes(conn) -> None:
    ensure_table_exists(conn, TMP_WEATHER03, WEATHER03_BUSINESS.create_weather03_business_rules)

    print(f"Creating table '{TABLE_WEATHER_CLEAN}'...")
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_WEATHER_CLEAN}"')
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_WEATHER_CLEAN}" AS
        SELECT
            CAST("DATE" AS DATE) AS "DATE",
            CAST(PRCP AS FLOAT) AS PRCP,
            CAST(SNOW AS FLOAT) AS SNOW,
            CAST(SNWD AS FLOAT) AS SNWD,
            CAST(TMIN AS FLOAT) AS TMIN,
            CAST(TMAX AS FLOAT) AS TMAX
        FROM "{TMP_WEATHER03}"
        """
    )


def main(conn):
    create_weather04_optimize_dtypes(conn)
    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_WEATHER_CLEAN}"').fetchone()[0]

    print("-" * 30)
    print(f"Step {TABLE_WEATHER_CLEAN} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
