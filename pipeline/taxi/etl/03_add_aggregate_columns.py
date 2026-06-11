from pipeline.constants.modules import ETL02_INGEST
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.tmp_tables import TMP_TAXI03
from pipeline.services.queries import ensure_table_exists, run_with_conn


def create_etl03_add_aggregate_columns(conn) -> None:
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)
    print("Adding aggregate columns...")
    conn.execute(f'DROP TABLE IF EXISTS "{TMP_TAXI03}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{TMP_TAXI03}" AS
        SELECT
            *,
            CASE
                WHEN tpep_pickup_datetime IS NOT NULL
                 AND tpep_dropoff_datetime IS NOT NULL
                 AND tpep_pickup_datetime < tpep_dropoff_datetime
                THEN date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)::DOUBLE / 60.0
            END AS trip_duration,
            CASE
                WHEN tpep_pickup_datetime IS NOT NULL
                 AND tpep_dropoff_datetime IS NOT NULL
                 AND tpep_pickup_datetime < tpep_dropoff_datetime
                 AND trip_distance > 0
                 AND date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) > 0
                THEN trip_distance / NULLIF(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)::DOUBLE / 3600.0, 0.0)
            END AS average_speed,
            CASE
                WHEN trip_distance > 0
                THEN fare_amount::DOUBLE / NULLIF(trip_distance::DOUBLE, 0.0)
            END AS fare_per_mile,
            CASE
                WHEN tpep_pickup_datetime IS NOT NULL
                 AND tpep_dropoff_datetime IS NOT NULL
                 AND tpep_pickup_datetime < tpep_dropoff_datetime
                 AND date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) > 0
                THEN fare_amount / NULLIF(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)::DOUBLE / 60.0, 0.0)
            END AS fare_per_minute
        FROM "{TABLE_TAXI_RAW}"
        """
    )


def main(conn) -> None:
    create_etl03_add_aggregate_columns(conn)

    row_count = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI03}"').fetchone()[0] or 0)

    print("-" * 30)
    print("Step taxi_etl_03_add_aggregate_columns complete.")
    print(f"Output rows:  {row_count:,}")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
