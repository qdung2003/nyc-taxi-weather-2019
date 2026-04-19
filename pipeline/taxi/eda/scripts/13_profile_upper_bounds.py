import json
from tqdm import tqdm
from pipeline.services.helpers import percent
from pipeline.services.queries import quote_identifier, connect_and_check, get_schema, get_total_rows
from pipeline.services.views import VIEW_TAXI_UPPER_BOUNDS
from pipeline.services.paths import WAREHOUSE_DB_FILE, TAXI_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "13_profile_upper_bounds.json"

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CONTINUOUS_COLUMNS = {"trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"}


def build_exact_rows(conn, source_table: str, col_name: str, total_rows: int):
    rows = conn.execute(
        f"""
        SELECT {quote_identifier(col_name)} AS value, COUNT(*) AS count
        FROM {quote_identifier(source_table)}
        GROUP BY {quote_identifier(col_name)}
        """
    ).fetchall()

    formatted = []
    for value, count in rows:
        if int(count) <= 0:
            continue
        label = "null" if value is None else str(value)
        formatted.append(
            {
                "label": label,
                "value": value,
                "count": int(count),
                "percent": percent(int(count), total_rows),
            }
        )

    def sort_key(row):
        value = row.get("value")
        if value is None:
            return (2, 0.0, row["label"])
        if isinstance(value, (int, float)):
            return (0, float(value), row["label"])
        return (1, 0.0, row["label"])

    formatted = sorted(formatted, key=sort_key)

    if col_name in {"PULocationID", "DOLocationID"}:
        visible = [r for r in formatted if r["percent"] > 1.0]
        hidden = [r for r in formatted if r not in visible]
        if hidden:
            visible.append(
                {
                    "label": f"Other ({len(hidden)} values)",
                    "count": sum(r["count"] for r in hidden),
                    "percent": round(sum(r["percent"] for r in hidden), 5),
                }
            )
        return visible

    return formatted


def build_month_rows(conn, source_table: str, col_name: str, total_rows: int):
    rows = conn.execute(
        f"""
        SELECT EXTRACT(MONTH FROM {quote_identifier(col_name)}) AS m, COUNT(*)
        FROM {quote_identifier(source_table)}
        WHERE {quote_identifier(col_name)} IS NOT NULL
        GROUP BY m
        """
    ).fetchall()
    month_count = [0] * 12
    for month, count in rows:
        month_count[int(month) - 1] = int(count)
    return [
        {"label": MONTH_LABELS[i], "count": month_count[i], "percent": percent(month_count[i], total_rows)}
        for i in range(12)
    ]


def build_continuous_rows(conn, source_table: str, col_name: str, total_rows: int):
    col = quote_identifier(col_name)
    zero_count, max_value = conn.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE {col} = 0) AS zero_count,
            MAX(CAST({col} AS DOUBLE)) FILTER (WHERE {col} > 0) AS max_value
        FROM {quote_identifier(source_table)}
        """
    ).fetchone()

    rows = []
    zero_count = int(zero_count or 0)
    if zero_count > 0:
        rows.append({"label": "= 0", "x_label": "0", "count": zero_count, "percent": percent(zero_count, total_rows)})

    if max_value is None or float(max_value) <= 0:
        return rows, len(rows)

    max_value = float(max_value)
    edges = [i * (max_value / 10.0) for i in range(11)]
    bucket_rows = conn.execute(
        f"""
        WITH positive AS (
            SELECT CAST({col} AS DOUBLE) AS v
            FROM {quote_identifier(source_table)}
            WHERE CAST({col} AS DOUBLE) > 0.0
        ),
        bucketed AS (
            SELECT LEAST(10, GREATEST(1, CAST(CEIL(v / {max_value:.16f} * 10) AS INTEGER))) AS b
            FROM positive
        )
        SELECT b, COUNT(*)
        FROM bucketed
        GROUP BY b
        """
    ).fetchall()
    bucket_count = {int(b): int(c) for b, c in bucket_rows}
    for i in range(10):
        left = edges[i]
        right = edges[i + 1]
        count = bucket_count.get(i + 1, 0)
        rows.append(
            {
                "label": f"({left:.2f}, {right:.2f}]",
                "x_label": f"{right:.2f}",
                "count": count,
                "percent": percent(count, total_rows),
            }
        )
    return rows, len(rows)


def main(conn):
    source_table = "tmp_eda13_source"
    conn.execute(f'DROP TABLE IF EXISTS "{source_table}"')
    conn.execute(
        f'CREATE TEMP TABLE "{source_table}" AS SELECT * FROM {quote_identifier(VIEW_TAXI_UPPER_BOUNDS)}'
    )

    schema = get_schema(conn, source_table)
    total_rows = get_total_rows(conn, source_table)

    columns_payload = []
    for field in tqdm(
        schema,
        desc="EDA 13 - profiling columns",
        unit="col",
        disable=TQDM_DISABLE,
        leave=False,
        dynamic_ncols=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        col = field.name
        type_text = str(field.type)

        null_count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM {quote_identifier(source_table)} WHERE {quote_identifier(col)} IS NULL"
            ).fetchone()[0]
            or 0
        )
        nan_count = 0
        if type_text in {"float", "double"}:
            nan_count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(source_table)} WHERE isnan({quote_identifier(col)})"
                ).fetchone()[0]
                or 0
            )
        valid_type_count = max(0, int(total_rows) - null_count - nan_count)
        correct_type_percent = percent(valid_type_count, int(total_rows))

        chart_rows = []
        note = ""
        unique_count = None
        range_bucket_count = None
        month_bucket_count = None

        if type_text.startswith("timestamp"):
            chart_rows = build_month_rows(conn, source_table, col, total_rows)
            month_bucket_count = 12
            note = "12-month distribution from v_taxi_04_upper_bounds"
        elif col in CONTINUOUS_COLUMNS:
            chart_rows, range_bucket_count = build_continuous_rows(conn, source_table, col, total_rows)
            note = "Zero and positive bins from v_taxi_04_upper_bounds (negative bins hidden; 10 raw bins)"
        else:
            chart_rows = build_exact_rows(conn, source_table, col, total_rows)
            unique_count = len(chart_rows)
            note = "Value distribution from v_taxi_04_upper_bounds (count=0 values hidden)"

        columns_payload.append(
            {
                "column_name": col,
                "type_value": type_text,
                "unique_count": unique_count,
                "range_bucket_count": range_bucket_count,
                "month_bucket_count": month_bucket_count,
                "correct_type_percent": correct_type_percent,
                "chart_rows": chart_rows,
                "chart_note": note,
            }
        )

    payload = {
        "summary": {
            "column_count": len(columns_payload),
            "total_rows": total_rows,
            "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
            "input_table": VIEW_TAXI_UPPER_BOUNDS,
            "clean_flow": "v_taxi_03_business_rules_then_v_taxi_04_upper_bounds",
        },
        "columns": columns_payload,
        "range_columns": sorted(list(CONTINUOUS_COLUMNS)),
    }
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved profile JSON: {output_file}")
