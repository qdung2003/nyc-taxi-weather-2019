"""Query and profiling helpers shared across EDA and ETL scripts."""
from datetime import datetime
from pathlib import Path
import csv
import json
from tqdm import tqdm
from pipeline.services.connect import connect_warehouse
from pipeline.services.helpers import percentage, round_if_needed
from pipeline.constants.columns import AGGREGATE_COLUMNS, MONEY_COLUMNS
from pipeline.constants.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL
from pipeline.constants.times import YEAR
from pipeline.constants.unique_settings import (
    MAX_UNIQUE_VALUES,
    POSITIVE_BIN_COUNT,
    TAIL_RATIO,
)
from pipeline.constants.upper_bounds_settings import (
    FIRST_PASS_BIN_COUNT,
    SECOND_PASS_BIN_COUNT,
    FIRST_PASS_THRESHOLD_PERCENT,
    SECOND_PASS_THRESHOLD_PERCENT,
)


# support
def quote_identifier(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def sql_table_ref(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        return stripped
    if stripped.startswith("(") or (stripped.startswith('"') and stripped.endswith('"')):
        return stripped
    return quote_identifier(stripped)


def run_with_conn(func) -> None:
    conn = connect_warehouse()
    try:
        func(conn)
    finally:
        conn.close()



def _is_valid_column_split(
    column_names: list[str],
    low_unique_columns: list[str],
    high_unique_columns: list[str],
) -> bool:
    profile_column_names = low_unique_columns + high_unique_columns
    return len(profile_column_names) == len(column_names) and set(profile_column_names) == set(column_names)


def _column_split(column_names: list[str], low_unique_columns: list[str], high_unique_columns: list[str]):
    low_unique_included = set(low_unique_columns)
    high_unique_included = set(high_unique_columns)
    return (
        [column_name for column_name in column_names if column_name in low_unique_included],
        [column_name for column_name in column_names if column_name in high_unique_included],
    )




def ensure_table_exists(conn, table_name: str, create_func) -> None:
    table_name_literal = table_name.replace("'", "''")
    if conn.execute(
        f"""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = '{table_name_literal}'
        LIMIT 1
        """
    ).fetchone() is None:
        print(f"Missing table '{table_name}', creating...")
        create_func(conn)


def calculate_valid_type_percentages(
    conn,
    source_table_quoted: str,
    column_names: list[str],
    data_types: list[str],
    row_count: int,
) -> list[float]:
    column_type_pairs = [
        (column_name, data_type)
        for column_name, data_type in zip(column_names, data_types)
        if column_name and data_type
    ]
    if not row_count or not column_type_pairs:
        return [0.0 for _ in column_names]

    clauses = []
    for column_name, data_type in column_type_pairs:
        column_name_literal = column_name.replace("'", "''")
        clauses.append(
            f"""
            SELECT
                '{column_name_literal}' AS column_name,
                ROUND(
                    COUNT(*) FILTER (
                        WHERE TRY_CAST({quote_identifier(column_name)} AS {data_type}) IS NOT NULL
                    ) * 100.0 / {row_count},
                    2
                ) AS valid_type_percent
            FROM {source_table_quoted}
            """
        )

    rows = conn.execute(" UNION ALL ".join(clauses)).fetchall()
    valid_type_percent_by_column = {
        str(column_name): float(valid_type_percent or 0.0)
        for column_name, valid_type_percent in rows
    }
    return [valid_type_percent_by_column.get(column_name, 0.0) for column_name in column_names]


# low_unique_column
def count_limited_unique_values(
    conn,
    source_table_quoted: str,
    column_quoted: str,
    max_unique_values: int = MAX_UNIQUE_VALUES,
) -> int:
    unique_count = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT DISTINCT {column_quoted}
            FROM {source_table_quoted}
            LIMIT {max_unique_values + 1}
        )
        """
    ).fetchone()[0]
    return int(unique_count or 0)


def build_low_unique_columns(
    conn,
    source_table_quoted: str,
    column_names: list[str],
    data_types: list[str],
    unique_counts: list[int],
    valid_type_percentages: list[float],
    row_count: int,
    *,
    desc: str = "Phase 2 value_counts",
    leave: bool = True,
) -> list[dict]:
    low_unique_columns = []
    for column_name, data_type, unique_count, valid_type_percent in tqdm(
        zip(column_names, data_types, unique_counts, valid_type_percentages),
        desc=desc,
        unit="col",
        total=len(column_names),
        leave=leave,
    ):
        column_name_quoted = quote_identifier(column_name)
        rows = conn.execute(
            f"""
            SELECT {column_name_quoted}, COUNT(*)
            FROM {source_table_quoted}
            GROUP BY {column_name_quoted}
            """
        ).fetchall()

        def sort_key(item):
            value = round_if_needed(item[0])
            if value is None:
                return (2, 0.0, "")
            if isinstance(value, (int, float)):
                return (0, float(value), "")
            return (1, 0.0, str(value))

        sorted_rows = sorted(rows, key=sort_key)

        values = []
        counts = []
        percentages = []
        for value, count in sorted_rows:
            values.append(round_if_needed(value))
            counts.append(int(count))
            percentages.append(percentage(count, row_count))

        low_unique_columns.append(
            {
                "column_name": column_name,
                "data_type": data_type,
                "unique_count": unique_count,
                "valid_type_percent": valid_type_percent,
                "values": values,
                "counts": counts,
                "percentages": percentages,
            }
        )

    return low_unique_columns


def get_column_groups(
    conn,
    source_table_quoted: str,
    column_names: list[str],
    *,
    profile_file: Path | None = None,
    desc: str = "EDA 03 - detecting column groups",
) -> tuple[list[str], list[str]]:
    if profile_file and profile_file.is_file():
        profile_report = json.loads(profile_file.read_text(encoding="utf-8"))
        low_unique_columns = [
            str(column_meta.get("column_name"))
            for column_meta in profile_report.get("low_unique_columns", [])
            if column_meta.get("column_name") is not None
        ]
        high_unique_column_meta = profile_report.get("high_unique_columns")
        if high_unique_column_meta is not None:
            high_unique_columns = [
                str(column_meta.get("column_name"))
                for column_meta in high_unique_column_meta
                if column_meta.get("column_name") is not None
            ]
            if _is_valid_column_split(column_names, low_unique_columns, high_unique_columns):
                return _column_split(column_names, low_unique_columns, high_unique_columns)
    if profile_file:
        profile_dir = profile_file.with_suffix("") if profile_file.suffix else profile_file
        low_unique_csv = profile_dir / "low_unique_columns.csv"
        high_unique_csv = profile_dir / "high_unique_columns.csv"
        if low_unique_csv.exists() and high_unique_csv.exists():
            low_unique_columns = read_column_names_csv(low_unique_csv)
            high_unique_columns = read_column_names_csv(high_unique_csv)
            if _is_valid_column_split(column_names, low_unique_columns, high_unique_columns):
                return _column_split(column_names, low_unique_columns, high_unique_columns)

    low_unique_columns = []
    high_unique_columns = []
    for column_name in tqdm(
        column_names,
        desc=desc,
        unit="col",
        total=len(column_names),
        leave=False,
        disable=TQDM_DISABLE,
        dynamic_ncols=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        unique_count = count_limited_unique_values(
            conn,
            source_table_quoted,
            quote_identifier(column_name),
            MAX_UNIQUE_VALUES,
        )
        if unique_count <= MAX_UNIQUE_VALUES:
            low_unique_columns.append(column_name)
        else:
            high_unique_columns.append(column_name)
    return low_unique_columns, high_unique_columns


def read_column_names_csv(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        column_name_field = "column_name" if "column_name" in (reader.fieldnames or []) else "column name"
        return [
            str(row[column_name_field])
            for row in reader
            if row.get(column_name_field)
        ]


def get_column_data_types(column_type_rows, column_names: list[str]) -> list[str]:
    column_name_set = set(column_names)
    return [
        str(row[1])
        for row in column_type_rows
        if str(row[0]) in column_name_set
    ]

# high_unique_column
def build_high_unique_columns(
    conn,
    source_table: str,
    column_names: list[str],
    data_types: list[str],
    valid_type_percentages: list[float],
    row_count: int,
    *,
    desc: str = "EDA 03 - profiling high-duplicate columns",
    temp_prefix: str = "tmp_eda03",
) -> list[dict]:
    high_unique_columns = []
    for column_name, data_type, valid_type_percent in tqdm(
        zip(column_names, data_types, valid_type_percentages),
        desc=desc,
        unit="col",
        total=len(column_names),
        leave=False,
        disable=TQDM_DISABLE,
        dynamic_ncols=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        high_unique_column = {
            "column_name": column_name,
            "data_type": data_type,
            "valid_type_percent": valid_type_percent,
        }
        type_str = str(data_type).lower()
        if "timestamp" in type_str or type_str == "date":
            high_unique_column.update(profile_datetime_column(conn, source_table, column_name, row_count))
        elif any(
            numeric_type in type_str
            for numeric_type in ["integer", "float", "double", "decimal", "numeric", "real"]
        ):
            high_unique_column.update(
                profile_numeric_column(
                    conn,
                    source_table,
                    column_name,
                    row_count,
                    tail_ratio=TAIL_RATIO,
                    positive_bin_count=POSITIVE_BIN_COUNT,
                    temp_prefix=temp_prefix,
                )
            )
        high_unique_columns.append(high_unique_column)
    return high_unique_columns


# numeric_datetime_column
def profile_numeric_column(
    conn,
    source_table: str,
    col_name: str,
    total_rows: int,
    *,
    tail_ratio: float = 1 / 101,
    positive_bin_count: int = 100,
    temp_prefix: str = "tmp_profile",
):
    col = quote_identifier(col_name)
    source_table_quoted = sql_table_ref(source_table)
    temp_col_table = quote_identifier(f"{temp_prefix}_{col_name}_v")

    conn.execute(f"DROP TABLE IF EXISTS {temp_col_table}")
    conn.execute(
        f"""
        CREATE TEMP TABLE {temp_col_table} AS
        SELECT CAST({col} AS DOUBLE) AS v
        FROM {source_table_quoted}
        WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
          AND NOT isnan(CAST({col} AS DOUBLE))
        """
    )

    min_value, max_value, negative_quantity, zero_quantity, positive_count = conn.execute(
        f"""
        SELECT
            MIN(v) AS min_value,
            MAX(v) AS max_value,
            COUNT(*) FILTER (WHERE v < 0) AS negative_quantity,
            COUNT(*) FILTER (WHERE v = 0) AS zero_quantity,
            COUNT(*) FILTER (WHERE v > 0) AS positive_count
        FROM {temp_col_table}
        """
    ).fetchone()

    if int(positive_count or 0) > 0:
        min_positive_value = conn.execute(
            f"""
            SELECT MIN(v)
            FROM {temp_col_table}
            WHERE v > 0
            """
        ).fetchone()[0]
        max_chart, above_max_chart_quantity = conn.execute(
            f"""
            WITH q AS (
                SELECT quantile_cont(v, {1 - tail_ratio:.12f}) AS max_chart
                FROM {temp_col_table}
                WHERE v > 0
            )
            SELECT
                q.max_chart,
                COUNT(*) FILTER (WHERE v > q.max_chart) AS above_max_chart_quantity
            FROM {temp_col_table}
            CROSS JOIN q
            GROUP BY q.max_chart
            """
        ).fetchone()
        positive_lower = float(min_positive_value or 0.0)
        positive_upper = float(max_chart)
        if positive_upper <= positive_lower:
            bin_edges, bin_counts = [positive_lower, positive_upper], [0] * positive_bin_count
        else:
            bin_edges, bin_counts, _ = build_current_histogram(
                conn,
                temp_col_table,
                positive_lower,
                positive_upper,
                positive_bin_count,
            )
        positive_range = {
            "bin_edges": [round_if_needed(x) for x in bin_edges[1:]],
            "bin_counts": bin_counts,
            "bin_percentages": [
                round_if_needed((count / total_rows * 100) if total_rows else 0)
                for count in bin_counts
            ],
        }
    else:
        max_chart = None
        above_max_chart_quantity = 0
        positive_range = {"bin_edges": [], "bin_counts": [], "bin_percentages": []}

    negative_count = int(negative_quantity or 0)
    zero_count = int(zero_quantity or 0)
    result = {
        "min_value": round_if_needed(min_value),
        "negative_count": negative_count,
        "zero_count": zero_count,
        "chart_max_value": round_if_needed(max_chart),
        "bin_edges": positive_range.get("bin_edges", []),
        "bin_counts": positive_range.get("bin_counts", []),
        "bin_percentages": positive_range.get("bin_percentages", []),
        "above_chart_max_value_count": int(above_max_chart_quantity or 0),
        "max_value": round_if_needed(max_value),
        "range_count": len(positive_range.get("bin_counts", [])) + 2,
    }
    conn.execute(f"DROP TABLE IF EXISTS {temp_col_table}")
    return result


def profile_datetime_column(
    conn,
    source_table: str,
    col_name: str,
    total_rows: int,
    *,
    year_start: datetime = datetime(YEAR, 1, 1),
    year_end: datetime = datetime(YEAR + 1, 1, 1),
):
    col = quote_identifier(col_name)
    source_table_quoted = sql_table_ref(source_table)
    month_count_exprs = ",\n            ".join(
        f"COUNT(*) FILTER (WHERE ts >= TIMESTAMP '{year_start:%Y-%m-%d %H:%M:%S}' "
        f"AND ts < TIMESTAMP '{year_end:%Y-%m-%d %H:%M:%S}' "
        f"AND EXTRACT(MONTH FROM ts) = {month}) AS month_{month:02d}"
        for month in range(1, 13)
    )

    row = conn.execute(
        f"""
        WITH typed AS (
            SELECT TRY_CAST({col} AS TIMESTAMP) AS ts
            FROM {source_table_quoted}
        )
        SELECT
            MIN(ts) AS min_value,
            MAX(ts) AS max_value,
            COUNT(*) FILTER (
                WHERE ts < TIMESTAMP '{year_start:%Y-%m-%d %H:%M:%S}'
            ) AS before_year_quantity,
            COUNT(*) FILTER (
                WHERE ts >= TIMESTAMP '{year_end:%Y-%m-%d %H:%M:%S}'
            ) AS after_year_quantity,
            {month_count_exprs}
        FROM typed
        WHERE ts IS NOT NULL
        """
    ).fetchone()

    min_value, max_value, before_year_quantity, after_year_quantity, *month_quantity = row
    month_quantity = [int(count or 0) for count in month_quantity]

    return {
        "min_value": min_value.isoformat(sep=" ") if min_value else None,
        "before_year_count": int(before_year_quantity or 0),
        "month_counts": month_quantity,
        "month_percentages": [percentage(count, total_rows) for count in month_quantity],
        "after_year_count": int(after_year_quantity or 0),
        "max_value": max_value.isoformat(sep=" ") if max_value else None,
        "month_count": len(month_quantity),
    }




















# upper_bounds
UPPER_BOUND_PASSES = (
    (FIRST_PASS_BIN_COUNT, FIRST_PASS_THRESHOLD_PERCENT),
    (SECOND_PASS_BIN_COUNT, SECOND_PASS_THRESHOLD_PERCENT),
)


def compute_upper_bounds(
    conn,
    table_name: str,
    context: str,
) -> tuple[list[dict], list[dict]]:
    table_quoted = quote_identifier(table_name)
    total_rows = int(
        conn.execute(f"SELECT COUNT(*) FROM {table_quoted}").fetchone()[0] or 0
    )
    profile_money_columns = [
        _compute_upper_bound_profile(conn, table_quoted, column_name, total_rows, context, False)
        for column_name in MONEY_COLUMNS
    ]
    profile_aggregate_columns = [
        _compute_upper_bound_profile(conn, table_quoted, column_name, total_rows, context, True)
        for column_name in AGGREGATE_COLUMNS
    ]
    return profile_money_columns, profile_aggregate_columns


def _compute_upper_bound_profile(
    conn,
    table_quoted: str,
    column_name: str,
    total_rows: int,
    context: str,
    trim_lower: bool,
) -> dict:
    if context not in {"eda08", "etl05"}:
        raise ValueError(f"Unsupported upper-bounds context: {context}")

    col = quote_identifier(column_name)
    hist_min_value, hist_max_value, zero_count = conn.execute(
        f"""
        SELECT
            MIN({col}) FILTER (WHERE {col} > 0.0 AND NOT isnan({col})),
            MAX({col}) FILTER (WHERE {col} > 0.0 AND NOT isnan({col})),
            COUNT(*) FILTER (WHERE {col} = 0.0)
        FROM {table_quoted}
        """
    ).fetchone()
    raw_min_value, raw_max_value = conn.execute(
        f"""
        SELECT
            MIN({col}),
            MAX({col})
        FROM {table_quoted}
        """
    ).fetchone()
    output_min_value = None if raw_min_value is None else round_if_needed(float(raw_min_value))
    output_max_value = None if raw_max_value is None else round_if_needed(float(raw_max_value))
    hist_min_value = float(hist_min_value or 0.0)
    hist_max_value = float(hist_max_value or 0.0)
    zero_count = int(zero_count or 0)
    source_sql = f"""
    SELECT {col} AS v
    FROM {table_quoted}
    WHERE {col} IS NOT NULL
      AND NOT isnan({col})
    """
    temp_name = f"tmp_{context}_{column_name}_v"
    source_table = quote_identifier(temp_name)
    conn.execute(f"DROP TABLE IF EXISTS {source_table}")
    conn.execute(f"CREATE TEMP TABLE {source_table} AS {source_sql}")
    try:
        bin_edges, bin_counts, pass_values = iterative_trim(
            conn,
            source_table,
            hist_min_value,
            hist_max_value,
            trim_lower,
        )

        first_pass_min_value, first_pass_max_value = (
            pass_values[0] if pass_values else (hist_min_value, hist_max_value)
        )
        second_pass_min_value, second_pass_max_value = (
            pass_values[1] if pass_values else (hist_min_value, hist_max_value)
        )

        below_chart_min_value_count = 0
        if trim_lower:
            below_chart_min_value_count = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {source_table}
                    WHERE v > 0.0 AND v < {second_pass_min_value:.16f}
                    """
                )
                .fetchone()[0]
                or 0
            )
        above_chart_max_value_count = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {source_table}
                WHERE v > {second_pass_max_value:.16f}
                """
            )
            .fetchone()[0]
            or 0
        )
        profile = {
            "column_name": column_name,
            "min_value": output_min_value,
            "max_value": output_max_value,
            "zero_count": zero_count,
            "first_pass_max_value": round_if_needed(float(first_pass_max_value)),
            "second_pass_max_value": round_if_needed(float(second_pass_max_value)),
            "bin_edges": [round_if_needed(float(value)) for value in bin_edges],
            "bin_counts": bin_counts,
            "bin_percentages": [percentage(count, total_rows) for count in bin_counts],
            "above_chart_max_value_count": int(above_chart_max_value_count or 0),
            "range_count": len(bin_counts) + 3,
        }
        if trim_lower:
            profile["first_pass_min_value"] = round_if_needed(float(first_pass_min_value))
            profile["second_pass_min_value"] = round_if_needed(float(second_pass_min_value))
            profile["below_chart_min_value_count"] = int(below_chart_min_value_count or 0)
        return profile
    finally:
        conn.execute(f"DROP TABLE IF EXISTS {source_table}")


def iterative_trim(
    conn,
    table_1_column,
    min_value,
    max_value,
    trim_lower: bool,
):
    bin_edges = []
    bin_counts = []
    pass_values = []

    for bin_count, threshold_percent in UPPER_BOUND_PASSES:
        threshold_ratio = threshold_percent / 100.0
        while True:
            current_bin_edges, current_bin_counts, current_total_count = build_current_histogram(
                conn,
                table_1_column,
                min_value,
                max_value,
                bin_count,
            )

            if not current_bin_counts or current_total_count <= 0:
                return min_value, max_value, bin_edges, bin_counts, pass_values

            left_index = 0
            right_index = len(current_bin_counts) - 1

            if trim_lower:
                while (
                    left_index <= right_index
                    and (current_bin_counts[left_index] / current_total_count) < threshold_ratio
                ):
                    left_index += 1

            while (
                right_index >= left_index
                and (current_bin_counts[right_index] / current_total_count) < threshold_ratio
            ):
                right_index -= 1

            needs_left_trim = trim_lower and left_index > 0
            needs_right_trim = right_index < len(current_bin_counts) - 1
            if not needs_left_trim and not needs_right_trim:
                break

            if needs_left_trim:
                next_min_value = float(current_bin_edges[left_index])
            if needs_right_trim:
                next_max_value = float(current_bin_edges[right_index + 1])

            if (
                (
                    abs(min_value - next_min_value) <= 1e-12
                    and abs(max_value - next_max_value) <= 1e-12
                )
                or next_max_value <= next_min_value
            ):
                return min_value, max_value, bin_edges, bin_counts, pass_values

            min_value = next_min_value
            max_value = next_max_value


        pass_values.append((min_value, max_value))

    
    bin_edges, bin_counts, _ = build_current_histogram(
        conn,
        table_1_column,
        min_value,
        max_value,
        10,
    )

    return bin_edges, bin_counts, pass_values


def build_current_histogram(
    conn,
    table_1_column,
    min_value: float,
    max_value: float,
    bin_count: int,
):
    width = (max_value - min_value) / bin_count
    bin_edges = [min_value + i * width for i in range(bin_count + 1)]
    bin_edges[-1] = max_value
    bin_counts = [0] * bin_count
    if max_value <= 0 or width <= 0:
        return bin_edges, bin_counts, 0

    buckets_and_counts = conn.execute(
        f"""
        SELECT
            LEAST(
                {bin_count},
                GREATEST(1, FLOOR((v - {min_value:.16f}) / {width:.16f}) + 1)
            ) AS b,
            COUNT(*) AS c
        FROM {table_1_column}
        WHERE v >= {min_value:.16f}
          AND v <= {max_value:.16f}
        GROUP BY b
        ORDER BY b
        """
    ).fetchall()

    
    for bucket, count in buckets_and_counts:
        bucket_index = int(bucket) - 1
        if 0 <= bucket_index < bin_count:
            bin_counts[bucket_index] = int(count)
    return bin_edges, bin_counts, sum(bin_counts)



