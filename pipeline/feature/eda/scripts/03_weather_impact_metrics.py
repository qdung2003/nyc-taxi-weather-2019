import importlib

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import round_if_needed, write_json_compact
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "03_weather_impact_metrics.json"

METRICS = [
    "avg_trip_count",
    "avg_duration_minutes",
    "avg_trip_distance",
    "avg_fare_amount",
    "avg_tip_amount",
    "avg_total_amount",
]


def pct_diff(value, baseline):
    if baseline in (None, 0):
        return None
    return round_if_needed((value - baseline) / baseline * 100)


def build_section_payload(rows, keys, group_by):
    payload = {
        "group_by": group_by,
        "row_count": len(rows),
    }
    for key in keys:
        payload[key] = []
    payload["day_count"] = []
    for metric in METRICS:
        payload[metric] = []

    for row in rows:
        row_values = dict(zip([*keys, "day_count", *METRICS], row))
        for key in keys:
            payload[key].append(row_values[key])
        payload["day_count"].append(int(row_values["day_count"] or 0))
        for metric in METRICS:
            payload[metric].append(round_if_needed(row_values[metric]))
    return payload


def build_fixed_level_sql(feature_table_quoted, column_name, level_name, cases_sql):
    return f"""
        WITH daily AS (
            SELECT
                "date",
                AVG({column_name}) AS weather_value,
                COUNT(*) AS trip_count,
                AVG(date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime)) AS avg_duration_minutes,
                AVG(trip_distance) AS avg_trip_distance,
                AVG(fare_amount) AS avg_fare_amount,
                AVG(tip_amount) AS avg_tip_amount,
                AVG(total_amount) AS avg_total_amount
            FROM {feature_table_quoted}
            GROUP BY "date"
        ),
        leveled AS (
            SELECT
                {cases_sql}
                trip_count,
                avg_duration_minutes,
                avg_trip_distance,
                avg_fare_amount,
                avg_tip_amount,
                avg_total_amount
            FROM daily
        )
        SELECT
            {level_name},
            value_range,
            COUNT(*) AS day_count,
            AVG(trip_count) AS avg_trip_count,
            AVG(avg_duration_minutes) AS avg_duration_minutes,
            AVG(avg_trip_distance) AS avg_trip_distance,
            AVG(avg_fare_amount) AS avg_fare_amount,
            AVG(avg_tip_amount) AS avg_tip_amount,
            AVG(avg_total_amount) AS avg_total_amount
        FROM leveled
        GROUP BY {level_name}, value_range, level_order
        ORDER BY level_order
    """


def build_prcp_level_sql(feature_table_quoted):
    return build_fixed_level_sql(
        feature_table_quoted,
        "prcp",
        "rain_level",
        """
                CASE
                    WHEN weather_value = 0 THEN 'no_rain'
                    WHEN weather_value <= 0.5 THEN 'light_rain'
                    WHEN weather_value <= 1.5 THEN 'medium_rain'
                    ELSE 'heavy_rain'
                END AS rain_level,
                CASE
                    WHEN weather_value = 0 THEN '0'
                    WHEN weather_value <= 0.5 THEN '(0, 0.5]'
                    WHEN weather_value <= 1.5 THEN '(0.5, 1.5]'
                    ELSE '> 1.5'
                END AS value_range,
                CASE
                    WHEN weather_value = 0 THEN 1
                    WHEN weather_value <= 0.5 THEN 2
                    WHEN weather_value <= 1.5 THEN 3
                    ELSE 4
                END AS level_order,
        """,
    )


def build_avg_temp_level_sql(feature_table_quoted):
    return build_fixed_level_sql(
        feature_table_quoted,
        "avg_temp",
        "avg_temp_level",
        """
                CASE
                    WHEN weather_value <= 0 THEN 'very_cold_temp'
                    WHEN weather_value <= 5 THEN 'cold_temp'
                    WHEN weather_value <= 10 THEN 'cool_temp'
                    WHEN weather_value <= 15 THEN 'mild_low_temp'
                    WHEN weather_value <= 20 THEN 'mild_high_temp'
                    WHEN weather_value <= 25 THEN 'warm_temp'
                    ELSE 'hot_temp'
                END AS avg_temp_level,
                CASE
                    WHEN weather_value <= 0 THEN '<= 0'
                    WHEN weather_value <= 5 THEN '(0, 5]'
                    WHEN weather_value <= 10 THEN '(5, 10]'
                    WHEN weather_value <= 15 THEN '(10, 15]'
                    WHEN weather_value <= 20 THEN '(15, 20]'
                    WHEN weather_value <= 25 THEN '(20, 25]'
                    ELSE '> 25'
                END AS value_range,
                CASE
                    WHEN weather_value <= 0 THEN 1
                    WHEN weather_value <= 5 THEN 2
                    WHEN weather_value <= 10 THEN 3
                    WHEN weather_value <= 15 THEN 4
                    WHEN weather_value <= 20 THEN 5
                    WHEN weather_value <= 25 THEN 6
                    ELSE 7
                END AS level_order,
        """,
    )


def build_temp_range_level_sql(feature_table_quoted):
    return build_fixed_level_sql(
        feature_table_quoted,
        "temp_range",
        "temp_range_level",
        """
                CASE
                    WHEN weather_value <= 5 THEN 'low_range'
                    WHEN weather_value <= 10 THEN 'medium_range'
                    WHEN weather_value <= 15 THEN 'high_range'
                    ELSE 'very_high_range'
                END AS temp_range_level,
                CASE
                    WHEN weather_value <= 5 THEN '<= 5'
                    WHEN weather_value <= 10 THEN '(5, 10]'
                    WHEN weather_value <= 15 THEN '(10, 15]'
                    ELSE '> 15'
                END AS value_range,
                CASE
                    WHEN weather_value <= 5 THEN 1
                    WHEN weather_value <= 10 THEN 2
                    WHEN weather_value <= 15 THEN 3
                    ELSE 4
                END AS level_order,
        """,
    )


def value_by_key(payload, key_name, key_value, metric):
    keys = payload.get(key_name, [])
    values = payload.get(metric, [])
    for index, value in enumerate(keys):
        if value == key_value:
            return values[index]
    return None


def value_by_two_keys(payload, first_key, first_value, second_key, second_value, metric):
    first_values = payload.get(first_key, [])
    second_values = payload.get(second_key, [])
    metric_values = payload.get(metric, [])
    for index, (left, right) in enumerate(zip(first_values, second_values)):
        if left == first_value and right == second_value:
            return metric_values[index]
    return None


def build_summary(rain_status, rain_weekend, rain_level):
    summary = {
        "row_count": len(METRICS),
        "metric": [],
        "rain_pct": [],
        "weekday_rain_pct": [],
        "weekend_rain_pct": [],
        "light_rain_pct": [],
        "medium_rain_pct": [],
        "heavy_rain_pct": [],
    }
    for metric in METRICS:
        no_rain = value_by_key(rain_status, "rain_status", "no_rain", metric)
        rain = value_by_key(rain_status, "rain_status", "rain", metric)
        weekday_no_rain = value_by_two_keys(
            rain_weekend,
            "day_type",
            "weekday",
            "rain_status",
            "no_rain",
            metric,
        )
        weekday_rain = value_by_two_keys(
            rain_weekend,
            "day_type",
            "weekday",
            "rain_status",
            "rain",
            metric,
        )
        weekend_no_rain = value_by_two_keys(
            rain_weekend,
            "day_type",
            "weekend",
            "rain_status",
            "no_rain",
            metric,
        )
        weekend_rain = value_by_two_keys(
            rain_weekend,
            "day_type",
            "weekend",
            "rain_status",
            "rain",
            metric,
        )
        level_values = rain_level.get(metric, [])
        level_baseline = level_values[0] if len(level_values) > 0 else None
        level_2 = level_values[1] if len(level_values) > 1 else None
        level_3 = level_values[2] if len(level_values) > 2 else None
        level_4 = level_values[3] if len(level_values) > 3 else None

        summary["metric"].append(metric)
        summary["rain_pct"].append(pct_diff(rain, no_rain))
        summary["weekday_rain_pct"].append(pct_diff(weekday_rain, weekday_no_rain))
        summary["weekend_rain_pct"].append(pct_diff(weekend_rain, weekend_no_rain))
        summary["light_rain_pct"].append(pct_diff(level_2, level_baseline))
        summary["medium_rain_pct"].append(pct_diff(level_3, level_baseline))
        summary["heavy_rain_pct"].append(pct_diff(level_4, level_baseline))
    return summary


def main(conn):
    feature_etl = importlib.import_module("pipeline.feature.etl.01_join_taxi_weather")
    ensure_table_exists(
        conn,
        TABLE_TAXI_WEATHER_FEATURES,
        feature_etl.create_taxi_weather_features,
    )
    feature_table_quoted = quote_identifier(TABLE_TAXI_WEATHER_FEATURES)

    rain_status_rows = conn.execute(
        f"""
        WITH daily AS (
            SELECT
                "date",
                CASE WHEN prcp > 0 THEN 'rain' ELSE 'no_rain' END AS rain_status,
                COUNT(*) AS trip_count,
                AVG(date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime)) AS avg_duration_minutes,
                AVG(trip_distance) AS avg_trip_distance,
                AVG(fare_amount) AS avg_fare_amount,
                AVG(tip_amount) AS avg_tip_amount,
                AVG(total_amount) AS avg_total_amount
            FROM {feature_table_quoted}
            GROUP BY "date", rain_status
        )
        SELECT
            rain_status,
            COUNT(*) AS day_count,
            AVG(trip_count) AS avg_trip_count,
            AVG(avg_duration_minutes) AS avg_duration_minutes,
            AVG(avg_trip_distance) AS avg_trip_distance,
            AVG(avg_fare_amount) AS avg_fare_amount,
            AVG(avg_tip_amount) AS avg_tip_amount,
            AVG(avg_total_amount) AS avg_total_amount
        FROM daily
        GROUP BY rain_status
        ORDER BY CASE rain_status WHEN 'no_rain' THEN 1 ELSE 2 END
        """
    ).fetchall()

    rain_weekend_rows = conn.execute(
        f"""
        WITH daily AS (
            SELECT
                "date",
                CASE WHEN prcp > 0 THEN 'rain' ELSE 'no_rain' END AS rain_status,
                CASE
                    WHEN date_part('dayofweek', "date") IN (0, 6) THEN 'weekend'
                    ELSE 'weekday'
                END AS day_type,
                COUNT(*) AS trip_count,
                AVG(date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime)) AS avg_duration_minutes,
                AVG(trip_distance) AS avg_trip_distance,
                AVG(fare_amount) AS avg_fare_amount,
                AVG(tip_amount) AS avg_tip_amount,
                AVG(total_amount) AS avg_total_amount
            FROM {feature_table_quoted}
            GROUP BY "date", rain_status, day_type
        )
        SELECT
            day_type,
            rain_status,
            COUNT(*) AS day_count,
            AVG(trip_count) AS avg_trip_count,
            AVG(avg_duration_minutes) AS avg_duration_minutes,
            AVG(avg_trip_distance) AS avg_trip_distance,
            AVG(avg_fare_amount) AS avg_fare_amount,
            AVG(avg_tip_amount) AS avg_tip_amount,
            AVG(avg_total_amount) AS avg_total_amount
        FROM daily
        GROUP BY day_type, rain_status
        ORDER BY
            CASE day_type WHEN 'weekday' THEN 1 ELSE 2 END,
            CASE rain_status WHEN 'no_rain' THEN 1 ELSE 2 END
        """
    ).fetchall()

    rain_level_rows = conn.execute(build_prcp_level_sql(feature_table_quoted)).fetchall()

    avg_temp_level_rows = conn.execute(build_avg_temp_level_sql(feature_table_quoted)).fetchall()

    temp_range_level_rows = conn.execute(build_temp_range_level_sql(feature_table_quoted)).fetchall()

    rain_status = build_section_payload(rain_status_rows, ["rain_status"], "rain_status")
    rain_weekend = build_section_payload(
        rain_weekend_rows,
        ["day_type", "rain_status"],
        "day_type, rain_status",
    )
    rain_level = build_section_payload(rain_level_rows, ["rain_level", "value_range"], "rain_level")
    avg_temp_level = build_section_payload(avg_temp_level_rows, ["avg_temp_level", "value_range"], "avg_temp_level")
    temp_range_level = build_section_payload(temp_range_level_rows, ["temp_range_level", "value_range"], "temp_range_level")

    payload = {
        "weather_columns": ["prcp", "avg_temp", "temp_range"],
        "sections": [
            "rain_status",
            "rain_weekend",
            "rain_level",
            "avg_temp_level",
            "temp_range_level",
            "impact_summary",
        ],
        "rain_status": rain_status,
        "rain_weekend": rain_weekend,
        "rain_level": rain_level,
        "avg_temp_level": avg_temp_level,
        "temp_range_level": temp_range_level,
        "impact_summary": build_summary(rain_status, rain_weekend, rain_level),
    }
    write_json_compact(
        output_file,
        payload,
        compact_all_scalar_arrays=True,
        align_compact_array_items=False,
        align_compact_array_key_labels=True,
        parallel_array_groups=[
            ("rain_status", "day_count", *METRICS),
            ("day_type", "rain_status", "day_count", *METRICS),
            ("rain_level", "value_range", "day_count", *METRICS),
            ("avg_temp_level", "value_range", "day_count", *METRICS),
            ("temp_range_level", "value_range", "day_count", *METRICS),
            (
                "metric",
                "rain_pct",
                "weekday_rain_pct",
                "weekend_rain_pct",
                "light_rain_pct",
                "medium_rain_pct",
                "heavy_rain_pct",
            ),
        ],
    )
    print(f"Feature EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
