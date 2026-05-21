import importlib

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import round_if_needed, write_json_compact
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "02_daily_weather_metrics.json"


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

    payload = {
        "group_by": "date",
        "row_count": len(rows),
        "date": [],
        "prcp": [],
        "avg_temp": [],
        "temp_range": [],
        "trip_count": [],
        "avg_duration_minutes": [],
        "avg_trip_distance": [],
        "avg_fare_amount": [],
        "avg_tip_amount": [],
        "avg_total_amount": [],
    }
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
        payload["date"].append(date.isoformat() if hasattr(date, "isoformat") else str(date))
        payload["prcp"].append(round_if_needed(prcp))
        payload["avg_temp"].append(round_if_needed(avg_temp))
        payload["temp_range"].append(round_if_needed(temp_range))
        payload["trip_count"].append(int(trip_count or 0))
        payload["avg_duration_minutes"].append(round_if_needed(avg_duration_minutes))
        payload["avg_trip_distance"].append(round_if_needed(avg_trip_distance))
        payload["avg_fare_amount"].append(round_if_needed(avg_fare_amount))
        payload["avg_tip_amount"].append(round_if_needed(avg_tip_amount))
        payload["avg_total_amount"].append(round_if_needed(avg_total_amount))
    write_json_compact(
        output_file,
        payload,
        compact_all_scalar_arrays=True,
        align_compact_array_items=True,
        align_compact_array_key_labels=True,
        parallel_array_groups=[
            (
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
            ),
        ],
    )
    print(f"Feature EDA 02 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
