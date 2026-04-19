import json
import numpy as np
from datetime import datetime
from tqdm import tqdm
from pipeline.services.helpers import round_if_needed, serialize_number
from pipeline.services.queries import quote_identifier, connect_and_check
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.paths import WAREHOUSE_DB_FILE, TAXI_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


output_dir = TAXI_DIR / "eda" / "results"
output_file = output_dir / "03_view_high_duplicate.json"
profile_file = output_dir / "02_check_duplicate.json"
output_dir.mkdir(parents=True, exist_ok=True)

tail_fraction = 1 / 101
positive_bin_count = 100
year_start = datetime(2019, 1, 1)
year_end = datetime(2020, 1, 1)


def build_positive_bins(conn, source_table: str, col_name: str, max_chart: float, total_rows: int):
    if max_chart is None or max_chart <= 0:
        return {"milestone": [], "quantity": [], "quantity_percent": []}

    edges = np.linspace(0.0, max_chart, positive_bin_count + 1)
    col = quote_identifier(col_name)
    rows = conn.execute(
        f"""
        WITH positive AS (
            SELECT CAST({col} AS DOUBLE) AS v
            FROM {quote_identifier(source_table)}
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
              AND CAST({col} AS DOUBLE) > 0.0
              AND CAST({col} AS DOUBLE) <= {float(max_chart):.16f}
        ),
        bucketed AS (
            SELECT
                LEAST(
                    {positive_bin_count},
                    GREATEST(1, CAST(CEIL(v / {float(max_chart):.16f} * {positive_bin_count}) AS INTEGER))
                ) AS b
            FROM positive
        )
        SELECT b, COUNT(*)
        FROM bucketed
        GROUP BY b
        """
    ).fetchall()
    quantity = [0] * positive_bin_count
    for b, c in rows:
        quantity[int(b) - 1] = int(c)

    return {
        "milestone": [serialize_number(x) for x in edges[1:-1]],
        "quantity": quantity,
        "quantity_percent": [
            round_if_needed((qv / total_rows * 100) if total_rows else 0)
            for qv in quantity
        ],
    }


def profile_numeric_column(conn, source_table: str, col_name: str, total_rows: int):
    col = quote_identifier(col_name)
    
    # Single query to get all basic stats
    stats_query = f"""
    SELECT
        MIN(CAST({col} AS DOUBLE)) FILTER (
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
        ) AS min_value,
        MAX(CAST({col} AS DOUBLE)) FILTER (
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
        ) AS max_value,
        COUNT(*) FILTER (
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
              AND CAST({col} AS DOUBLE) < 0
        ) AS negative_quantity,
        COUNT(*) FILTER (
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
              AND CAST({col} AS DOUBLE) = 0
        ) AS zero_quantity,
        COUNT(*) FILTER (
            WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
              AND NOT isnan(CAST({col} AS DOUBLE))
              AND CAST({col} AS DOUBLE) > 0
        ) AS positive_count
    FROM {quote_identifier(source_table)}
    """
    
    min_value, max_value, negative_quantity, zero_quantity, positive_count = conn.execute(stats_query).fetchone()

    if int(positive_count or 0) > 0:
        # First get the quantile value
        quantile_query = f"""
        SELECT quantile_cont(CAST({col} AS DOUBLE), {1 - tail_fraction:.12f}) AS max_chart
        FROM {quote_identifier(source_table)}
        WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
          AND NOT isnan(CAST({col} AS DOUBLE))
          AND CAST({col} AS DOUBLE) > 0
        """
        max_chart = conn.execute(quantile_query).fetchone()[0]
        
        # Then get count above threshold using the quantile value
        count_query = f"""
        SELECT COUNT(*) AS above_max_chart_quantity
        FROM {quote_identifier(source_table)}
        WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
          AND NOT isnan(CAST({col} AS DOUBLE))
          AND CAST({col} AS DOUBLE) > 0
          AND CAST({col} AS DOUBLE) > {max_chart:.12f}
        """
        above_max_chart_quantity = conn.execute(count_query).fetchone()[0]
        positive_range = build_positive_bins(conn, source_table, col_name, float(max_chart), total_rows)
    else:
        max_chart = None
        above_max_chart_quantity = 0
        positive_range = {"milestone": [], "quantity": [], "quantity_percent": []}

    return {
        "min_value": serialize_number(min_value),
        "negative_quantity": int(negative_quantity or 0),
        "zero_quantity": int(zero_quantity or 0),
        "positive_range": {"max_chart": serialize_number(max_chart), **positive_range},
        "above_max_chart_quantity": int(above_max_chart_quantity or 0),
        "max_value": serialize_number(max_value),
    }


def profile_datetime_column(conn, source_table: str, col_name: str, total_rows: int):
    col = quote_identifier(col_name)
    
    # Single query to get all datetime stats
    datetime_query = f"""
    SELECT
        MIN(CAST({col} AS TIMESTAMP)) AS min_value,
        MAX(CAST({col} AS TIMESTAMP)) AS max_value,
        COUNT(*) FILTER (
            WHERE TRY_CAST({col} AS TIMESTAMP) IS NOT NULL
              AND CAST({col} AS TIMESTAMP) < TIMESTAMP '{year_start:%Y-%m-%d %H:%M:%S}'
        ) AS before_2019_quantity,
        COUNT(*) FILTER (
            WHERE TRY_CAST({col} AS TIMESTAMP) IS NOT NULL
              AND CAST({col} AS TIMESTAMP) >= TIMESTAMP '{year_end:%Y-%m-%d %H:%M:%S}'
        ) AS after_2019_quantity
    FROM {quote_identifier(source_table)}
    WHERE TRY_CAST({col} AS TIMESTAMP) IS NOT NULL
    """
    
    min_value, max_value, before_2019_quantity, after_2019_quantity = conn.execute(datetime_query).fetchone()

    month_quantity = [0] * 12
    rows = conn.execute(
        f"""
        SELECT EXTRACT(MONTH FROM CAST({col} AS TIMESTAMP)) AS m, COUNT(*)
        FROM {quote_identifier(source_table)}
        WHERE TRY_CAST({col} AS TIMESTAMP) IS NOT NULL
          AND CAST({col} AS TIMESTAMP) >= TIMESTAMP '{year_start:%Y-%m-%d %H:%M:%S}'
          AND CAST({col} AS TIMESTAMP) < TIMESTAMP '{year_end:%Y-%m-%d %H:%M:%S}'
        GROUP BY m
        """
    ).fetchall()
    for m, c in rows:
        month_quantity[int(m) - 1] = int(c)

    return {
        "min_value": min_value.isoformat(sep=" ") if min_value else None,
        "before_2019_quantity": int(before_2019_quantity or 0),
        "month_quantity": month_quantity,
        "month_percent": [
            round_if_needed((qv / total_rows * 100) if total_rows else 0)
            for qv in month_quantity
        ],
        "after_2019_quantity": int(after_2019_quantity or 0),
        "max_value": max_value.isoformat(sep=" ") if max_value else None,
    }


def main(conn):
    profile_report = json.loads(profile_file.read_text(encoding="utf-8"))
    high_duplicate_columns = profile_report["high_duplicate_columns"]
    total_rows = profile_report["total_rows"]
    columns_to_check = [column["column_name"] for column in high_duplicate_columns]
    type_value_by_column = {
        column["column_name"]: column["type_value"]
        for column in high_duplicate_columns
    }

    columns_report = []
    source_table = "tmp_eda03_source"
    conn.execute(f'DROP TABLE IF EXISTS "{source_table}"')
    conn.execute(
        f'CREATE TEMP TABLE "{source_table}" AS SELECT * FROM {quote_identifier(TABLE_TAXI_RAW)}'
    )

    for column_name in tqdm(
        columns_to_check,
        desc="EDA 03 - profiling high-duplicate columns",
        unit="col",
        leave=False,
        disable=TQDM_DISABLE,
        dynamic_ncols=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        type_value = type_value_by_column[column_name]
        type_str = str(type_value).lower()
        if "timestamp" in type_str:
            profile = profile_datetime_column(conn, source_table, column_name, total_rows)
            columns_report.append(
                {"column_name": column_name, "type_value": type_value, **profile}
            )
        elif any(numeric_type in type_str for numeric_type in ["integer", "float", "double", "decimal", "numeric", "real"]):
            profile = profile_numeric_column(conn, source_table, column_name, total_rows)
            columns_report.append(
                {"column_name": column_name, "type_value": type_value, **profile}
            )
        else:
            # Skip non-numeric, non-timestamp columns
            continue

    report = {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_TAXI_RAW,
        "profile_file": profile_file.as_posix(),
        "tail_fraction": tail_fraction,
        "positive_bin_count": positive_bin_count,
        "columns": columns_report,
    }
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")
