import importlib

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import reset_csv_dir, round_if_needed, write_csv
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "02_daily_weather_metrics"


def main(conn):
    feature_etl = importlib.import_module("pipeline.feature.etl.01_join_taxi_weather")
    ensure_table_exists(
        conn,
        TABLE_TAXI_WEATHER_FEATURES,
        feature_etl.create_taxi_weather_features,
    )
    feature_table_quoted = quote_identifier(TABLE_TAXI_WEATHER_FEATURES)

    rows = conn.execute(
        f"""
        SELECT
            "date",
            prcp,
            avg_temp,
            temp_range,
            COUNT(*) AS trip_count,
            AVG(date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime)) AS avg_duration_minutes,
            AVG(trip_distance) AS avg_trip_distance,
            AVG(fare_amount) AS avg_fare_amount,
            AVG(tip_amount) AS avg_tip_amount,
            AVG(total_amount) AS avg_total_amount
        FROM {feature_table_quoted}
        GROUP BY "date", prcp, avg_temp, temp_range
        ORDER BY "date"
        """
    ).fetchall()

    daily_rows = []
    for (
        date,
        prcp,
        avg_temp,
        temp_range,
        trip_count,
        avg_duration_minutes,
        avg_trip_distance,
        avg_fare_amount,
        avg_tip_amount,
        avg_total_amount,
    ) in rows:
        daily_rows.append(
            {
                "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                "prcp": round_if_needed(prcp),
                "avg_temp": round_if_needed(avg_temp),
                "temp_range": round_if_needed(temp_range),
                "trip_count": int(trip_count or 0),
                "avg_duration_minutes": round_if_needed(avg_duration_minutes),
                "avg_trip_distance": round_if_needed(avg_trip_distance),
                "avg_fare_amount": round_if_needed(avg_fare_amount),
                "avg_tip_amount": round_if_needed(avg_tip_amount),
                "avg_total_amount": round_if_needed(avg_total_amount),
            }
        )

    reset_csv_dir(output_file)
    write_csv(
        output_file,
        ["metadata", "daily_weather_metrics"],
        [
            (
                ["key", "value"],
                [["group_by", "row_count"], ["date", len(rows)]],
            ),
            (
                [
                    "date",
                    "prcp",
                    "avg_temp",
                    "temp_range",
                    "trip_count",
                    "avg_duration_minutes",
                    "avg_trip_distance",
                    "avg_fare_amount",
                    "avg_tip_amount",
                    "avg_total_amount",
                ],
                [
                    [row["date"] for row in daily_rows],
                    [row["prcp"] for row in daily_rows],
                    [row["avg_temp"] for row in daily_rows],
                    [row["temp_range"] for row in daily_rows],
                    [row["trip_count"] for row in daily_rows],
                    [row["avg_duration_minutes"] for row in daily_rows],
                    [row["avg_trip_distance"] for row in daily_rows],
                    [row["avg_fare_amount"] for row in daily_rows],
                    [row["avg_tip_amount"] for row in daily_rows],
                    [row["avg_total_amount"] for row in daily_rows],
                ],
            ),
        ],
    )
    print(f"Feature EDA 02 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
