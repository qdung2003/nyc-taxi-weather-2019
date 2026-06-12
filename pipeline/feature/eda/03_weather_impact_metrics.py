import importlib

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import reset_csv_dir, round_if_needed, write_csv
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "03_weather_impact_metrics"

METRICS = [
    "avg_trip_count",
    "avg_duration_minutes",
    "avg_trip_distance",
    "avg_fare_amount",
    "avg_tip_amount",
    "avg_total_amount",
]

WEATHER_COLUMNS = ["prcp", "avg_temp", "temp_range"]


def pct_diff(value, baseline):
    if baseline in (None, 0):
        return None
    return round_if_needed((value - baseline) / baseline * 100)


def build_section_rows(rows, keys):
    section_rows = []
    for row in rows:
        row_values = dict(zip([*keys, "day_count", *METRICS], row))
        section_row = {
            key: row_values[key]
            for key in keys
        }
        section_row["day_count"] = int(row_values["day_count"] or 0)
        for metric in METRICS:
            section_row[metric] = round_if_needed(row_values[metric])
        section_rows.append(section_row)
    return section_rows


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


def value_by_key(rows, key_name, key_value, metric):
    for row in rows:
        if row.get(key_name) == key_value:
            return row.get(metric)
    return None


def value_by_two_keys(rows, first_key, first_value, second_key, second_value, metric):
    for row in rows:
        if row.get(first_key) == first_value and row.get(second_key) == second_value:
            return row.get(metric)
    return None


def build_summary(rain_status, rain_weekend, rain_level):
    summary = []
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
        level_baseline = value_by_key(rain_level, "rain_level", "no_rain", metric)
        level_2 = value_by_key(rain_level, "rain_level", "light_rain", metric)
        level_3 = value_by_key(rain_level, "rain_level", "medium_rain", metric)
        level_4 = value_by_key(rain_level, "rain_level", "heavy_rain", metric)

        summary.append(
            {
                "metric": metric,
                "rain_pct": pct_diff(rain, no_rain),
                "weekday_rain_pct": pct_diff(weekday_rain, weekday_no_rain),
                "weekend_rain_pct": pct_diff(weekend_rain, weekend_no_rain),
                "light_rain_pct": pct_diff(level_2, level_baseline),
                "medium_rain_pct": pct_diff(level_3, level_baseline),
                "heavy_rain_pct": pct_diff(level_4, level_baseline),
            }
        )
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

    rain_status = build_section_rows(rain_status_rows, ["rain_status"])
    rain_weekend = build_section_rows(
        rain_weekend_rows,
        ["day_type", "rain_status"],
    )
    rain_level = build_section_rows(rain_level_rows, ["rain_level", "value_range"])
    avg_temp_level = build_section_rows(avg_temp_level_rows, ["avg_temp_level", "value_range"])
    temp_range_level = build_section_rows(temp_range_level_rows, ["temp_range_level", "value_range"])
    impact_rain_summary = build_summary(rain_status, rain_weekend, rain_level)

    reset_csv_dir(output_file)
    write_csv(
        output_file,
        [
            "metadata",
            "rain_status",
            "rain_weekend",
            "rain_level",
            "avg_temp_level",
            "temp_range_level",
            "impact_rain_summary",
        ],
        [
            (
                ["key", "value"],
                [["weather_column_count", "metric_count"], [len(WEATHER_COLUMNS), len(METRICS)]],
            ),
            (
                ["rain_status", "day_count", *METRICS],
                [
                    [row["rain_status"] for row in rain_status],
                    [row["day_count"] for row in rain_status],
                    *[[row[metric] for row in rain_status] for metric in METRICS],
                ],
            ),
            (
                ["day_type", "rain_status", "day_count", *METRICS],
                [
                    [row["day_type"] for row in rain_weekend],
                    [row["rain_status"] for row in rain_weekend],
                    [row["day_count"] for row in rain_weekend],
                    *[[row[metric] for row in rain_weekend] for metric in METRICS],
                ],
            ),
            (
                ["rain_level", "value_range", "day_count", *METRICS],
                [
                    [row["rain_level"] for row in rain_level],
                    [row["value_range"] for row in rain_level],
                    [row["day_count"] for row in rain_level],
                    *[[row[metric] for row in rain_level] for metric in METRICS],
                ],
            ),
            (
                ["avg_temp_level", "value_range", "day_count", *METRICS],
                [
                    [row["avg_temp_level"] for row in avg_temp_level],
                    [row["value_range"] for row in avg_temp_level],
                    [row["day_count"] for row in avg_temp_level],
                    *[[row[metric] for row in avg_temp_level] for metric in METRICS],
                ],
            ),
            (
                ["temp_range_level", "value_range", "day_count", *METRICS],
                [
                    [row["temp_range_level"] for row in temp_range_level],
                    [row["value_range"] for row in temp_range_level],
                    [row["day_count"] for row in temp_range_level],
                    *[[row[metric] for row in temp_range_level] for metric in METRICS],
                ],
            ),
            (
                [
                    "metric",
                    "rain_pct",
                    "weekday_rain_pct",
                    "weekend_rain_pct",
                    "light_rain_pct",
                    "medium_rain_pct",
                    "heavy_rain_pct",
                ],
                [
                    [row["metric"] for row in impact_rain_summary],
                    [row["rain_pct"] for row in impact_rain_summary],
                    [row["weekday_rain_pct"] for row in impact_rain_summary],
                    [row["weekend_rain_pct"] for row in impact_rain_summary],
                    [row["light_rain_pct"] for row in impact_rain_summary],
                    [row["medium_rain_pct"] for row in impact_rain_summary],
                    [row["heavy_rain_pct"] for row in impact_rain_summary],
                ],
            ),
        ],
    )
    print(f"Feature EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
