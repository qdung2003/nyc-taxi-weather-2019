import importlib

from pipeline.constants.tables import (
    TABLE_TAXI_CLEAN,
    TABLE_TAXI_WEATHER_FEATURES,
    TABLE_WEATHER_CLEAN,
)
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


def create_taxi_weather_features(conn) -> None:
    taxi_optimize = importlib.import_module("pipeline.taxi.etl.05_optimize_dtypes")
    weather_optimize = importlib.import_module("pipeline.weather.etl.04_optimize_dtypes")

    ensure_table_exists(conn, TABLE_TAXI_CLEAN, taxi_optimize.create_etl05_optimize_dtypes)
    ensure_table_exists(conn, TABLE_WEATHER_CLEAN, weather_optimize.create_weather04_optimize_dtypes)

    taxi_clean = quote_identifier(TABLE_TAXI_CLEAN)
    weather_clean = quote_identifier(TABLE_WEATHER_CLEAN)
    feature_table = quote_identifier(TABLE_TAXI_WEATHER_FEATURES)

    print(f"Creating table '{TABLE_TAXI_WEATHER_FEATURES}'...")
    conn.execute(f"DROP TABLE IF EXISTS {feature_table}")
    conn.execute(
        f"""
        CREATE TABLE {feature_table} AS
        WITH taxi_features AS (
            SELECT
                CAST(tpep_pickup_datetime AS DATE) AS "date",
                tpep_pickup_datetime,
                tpep_dropoff_datetime,
                trip_distance,
                fare_amount,
                tip_amount,
                total_amount
            FROM {taxi_clean}
            WHERE CAST(tpep_pickup_datetime AS DATE) = CAST(tpep_dropoff_datetime AS DATE)
        ),
        weather_features AS (
            SELECT
                "date",
                prcp,
                (tmin + tmax) / 2.0 AS avg_temp,
                tmax - tmin AS temp_range
            FROM {weather_clean}
            WHERE snow = 0
              AND snwd = 0
        )
        SELECT
            t."date",
            t.tpep_pickup_datetime,
            t.tpep_dropoff_datetime,
            t.trip_distance,
            t.fare_amount,
            t.tip_amount,
            t.total_amount,
            w.prcp,
            w.avg_temp,
            w.temp_range
        FROM taxi_features t
        INNER JOIN weather_features w
            ON t."date" = w."date"
        """
    )


def main(conn) -> None:
    create_taxi_weather_features(conn)
    row_count = conn.execute(
        f"SELECT count(*) FROM {quote_identifier(TABLE_TAXI_WEATHER_FEATURES)}"
    ).fetchone()[0]

    print("-" * 30)
    print(f"Step {TABLE_TAXI_WEATHER_FEATURES} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
