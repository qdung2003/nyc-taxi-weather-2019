from pipeline.services.queries import run_with_conn

TABLE_NAME = "taxi_upper_bounds_test"
SOURCE_TABLE = "taxi_upper_bounds_source"


def create_upper_bounds_table(conn) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{SOURCE_TABLE}" (
            tpep_pickup_datetime TIMESTAMP,
            tpep_dropoff_datetime TIMESTAMP,
            trip_distance DOUBLE,
            fare_amount DOUBLE
        )
        """
    )
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_NAME}"')
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_NAME}" AS
        SELECT
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
                THEN fare_amount / NULLIF(trip_distance, 0.0)
            END AS fare_per_mile,
            CASE
                WHEN tpep_pickup_datetime IS NOT NULL
                 AND tpep_dropoff_datetime IS NOT NULL
                 AND tpep_pickup_datetime < tpep_dropoff_datetime
                 AND date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) > 0
                THEN fare_amount / NULLIF(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)::DOUBLE / 60.0, 0.0)
            END AS fare_per_minute
        FROM "{SOURCE_TABLE}"
        """
    )


def main(conn):
    create_upper_bounds_table(conn)
    source_row_count = conn.execute(f'SELECT COUNT(*) FROM "{SOURCE_TABLE}"').fetchone()[0]
    row_count = conn.execute(f'SELECT COUNT(*) FROM "{TABLE_NAME}"').fetchone()[0]
    print("-" * 30)
    print(f"Source table {SOURCE_TABLE}: {source_row_count:,} rows.")
    print(f"Table {TABLE_NAME} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
