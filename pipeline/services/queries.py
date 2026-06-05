"""Helpers for reading DuckDB tables/views in Arrow chunks for EDA scripts."""
from datetime import datetime
from pathlib import Path
import csv
import json
from tqdm import tqdm
from pipeline.services.connect import connect_warehouse
from pipeline.services.helpers import round_if_needed
from pipeline.constants.columns import MONEY_COLUMNS
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


def run_with_conn(func) -> None:
    conn = connect_warehouse()
    try:
        func(conn)
    finally:
        conn.close()


def ensure_table_exists(conn, table_name: str, create_func) -> None:
    table_name_literal = table_name.replace("'", "''")
    exists = conn.execute(
        f"""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = '{table_name_literal}'
        LIMIT 1
        """
    ).fetchone() is not None
    if not exists:
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
        (index, column_name, data_type)
        for index, (column_name, data_type) in enumerate(zip(column_names, data_types))
        if column_name and data_type
    ]
    if not row_count or not column_type_pairs:
        return [0.0 for _ in column_names]

    clauses = []
    for index, column_name, data_type in column_type_pairs:
        column_name_literal = column_name.replace("'", "''")
        clauses.append(
            f"""
            SELECT
                {index} AS column_index,
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
    valid_type_percentages = [0.0 for _ in column_names]
    for column_index, _column_name, valid_type_percent in rows:
        valid_type_percentages[int(column_index)] = float(valid_type_percent or 0.0)
    return valid_type_percentages


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
    valid_type_percentages: list[float],
    row_count: int,
    *,
    desc: str = "Phase 2 value_counts",
    leave: bool = True,
) -> list[dict]:
    low_unique_columns = []
    for column_name, data_type, valid_type_percent in tqdm(
        zip(column_names, data_types, valid_type_percentages),
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
            percentages.append(round_if_needed((count / row_count * 100) if row_count else 0))

        low_unique_columns.append(
            {
                "column_name": column_name,
                "data_type": data_type,
                "unique_count": len(sorted_rows),
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
            profile_column_names = low_unique_columns + high_unique_columns
            if len(profile_column_names) == len(column_names) and set(profile_column_names) == set(column_names):
                low_unique_column_set = set(low_unique_columns)
                high_unique_column_set = set(high_unique_columns)
                return (
                    [column_name for column_name in column_names if column_name in low_unique_column_set],
                    [column_name for column_name in column_names if column_name in high_unique_column_set],
                )
    if profile_file:
        profile_dir = profile_file.with_suffix("") if profile_file.suffix else profile_file
        low_unique_csv = profile_dir / "low_unique_columns.csv"
        high_unique_csv = profile_dir / "high_unique_columns.csv"
        if low_unique_csv.exists() and high_unique_csv.exists():
            low_unique_columns = read_column_names_csv(low_unique_csv)
            high_unique_columns = read_column_names_csv(high_unique_csv)
            profile_column_names = low_unique_columns + high_unique_columns
            if len(profile_column_names) == len(column_names) and set(profile_column_names) == set(column_names):
                low_unique_column_set = set(low_unique_columns)
                high_unique_column_set = set(high_unique_columns)
                return (
                    [column_name for column_name in column_names if column_name in low_unique_column_set],
                    [column_name for column_name in column_names if column_name in high_unique_column_set],
                )

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
    source_table_quoted = quote_identifier(source_table)
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
        bin_edges, bin_counts = build_histogram_counts(
            conn,
            temp_col_table,
            float(max_chart),
            positive_bin_count,
        )
        positive_range = {
            "bin_edges": [round_if_needed(x) for x in bin_edges[1:]],
            "bin_counts": bin_counts,
            "bin_percentages": [
                round_if_needed((qv / total_rows * 100) if total_rows else 0)
                for qv in bin_counts
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
    source_table_quoted = quote_identifier(source_table)
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
        "month_percentages": [
            round_if_needed((qv / total_rows * 100) if total_rows else 0)
            for qv in month_quantity
        ],
        "after_year_count": int(after_year_quantity or 0),
        "max_value": max_value.isoformat(sep=" ") if max_value else None,
        "month_count": len(month_quantity),
    }


# upper_bounds
def compute_upper_bounds(
    conn,
    table_name: str,
    *,
    temp_prefix: str = "tmp_upper_bounds",
) -> list[dict]:
    total_rows = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0] or 0)
    money_temp_table = quote_identifier(f"{temp_prefix}_money")
    money_select_sql = ",\n            ".join(
        f"TRY_CAST({quote_identifier(column_name)} AS DOUBLE) AS {quote_identifier(column_name)}"
        for column_name in MONEY_COLUMNS
    )
    conn.execute(f"DROP TABLE IF EXISTS {money_temp_table}")
    conn.execute(
        f"""
        CREATE TEMP TABLE {money_temp_table} AS
        SELECT
            {money_select_sql}
        FROM {table_name}
        """
    )

    stats_exprs = []
    for column_name in MONEY_COLUMNS:
        col = quote_identifier(column_name)
        stats_exprs.append(
            f"MAX({col}) FILTER (WHERE {col} > 0.0 AND NOT isnan({col})) "
            f"AS {quote_identifier(column_name + '_max')}"
        )
        stats_exprs.append(
            f"COUNT(*) FILTER (WHERE {col} = 0.0) "
            f"AS {quote_identifier(column_name + '_zero_count')}"
        )
    stats_row = conn.execute(
        f"""
        SELECT
            {", ".join(stats_exprs)}
        FROM {money_temp_table}
        """
    ).fetchone()
    column_stats = {}
    stats_index = 0
    for column_name in MONEY_COLUMNS:
        column_stats[column_name] = (
            float(stats_row[stats_index] or 1.0),
            int(stats_row[stats_index + 1] or 0),
        )
        stats_index += 2

    profiles = []
    try:
        for column_name in MONEY_COLUMNS:
            max_value, zero_count = column_stats[column_name]
            source_table, max_value, zero_count = prepare_column_source(
                conn,
                column_name,
                money_temp_table,
                temp_prefix=temp_prefix,
                source_is_numeric=True,
                stats=(max_value, zero_count),
            )
            try:
                no_zero_count = int(total_rows) - int(zero_count)
                second_pass_value, bin_edges, bin_counts, _bin_percentages, pass_values = iterative_trim(
                    conn,
                    source_table,
                    max_value,
                    no_zero_count,
                    return_pass_values=True,
                )
                first_pass_value = pass_values[0] if pass_values else max_value
                profiles.append(
                    {
                        "column_name": column_name,
                        "max_value": round_if_needed(float(max_value)),
                        "first_pass_value": round_if_needed(float(first_pass_value)),
                        "second_pass_value": round_if_needed(float(second_pass_value)),
                        "zero_count": int(zero_count or 0),
                        "bin_edges": [
                            round_if_needed(float(value))
                            for value in bin_edges[1:]
                        ],
                        "bin_counts": bin_counts,
                        "bin_percentages": [
                            round_if_needed((count / total_rows * 100) if total_rows else 0)
                            for count in bin_counts
                        ],
                        "range_count": len(bin_counts) + 1,
                    }
                )
            finally:
                conn.execute(f"DROP TABLE IF EXISTS {source_table}")
    finally:
        conn.execute(f"DROP TABLE IF EXISTS {money_temp_table}")
    return profiles


def prepare_column_source(
    conn,
    col_name: str,
    table_name: str,
    temp_prefix: str | None = None,
    *,
    source_is_numeric: bool = False,
    stats: tuple[float, int] | None = None,
):
    col = quote_identifier(col_name)
    value_expr = col if source_is_numeric else f"TRY_CAST({col} AS DOUBLE)"
    source_sql = f"""
    SELECT {value_expr} AS v
    FROM {table_name}
    WHERE {value_expr} IS NOT NULL
      AND NOT isnan({value_expr})
    """
    if temp_prefix:
        source_col_from = quote_identifier(f"{temp_prefix}_{col_name}_v")
        conn.execute(f"DROP TABLE IF EXISTS {source_col_from}")
        conn.execute(f"CREATE TEMP TABLE {source_col_from} AS {source_sql}")
    else:
        source_col_from = f"({source_sql})"
    if stats is not None:
        scan_max, zero_count = stats
        return source_col_from, float(scan_max or 1.0), int(zero_count or 0)

    scan_max, zero_count = conn.execute(
        f"""
        SELECT
            MAX(v) FILTER (WHERE v > 0.0) AS scan_max,
            COUNT(*) FILTER (WHERE v = 0.0) AS zero_count
        FROM {source_col_from}
        """
    ).fetchone()
    return source_col_from, float(scan_max or 1.0), int(zero_count or 0)


def iterative_trim(
    conn,
    sql_string,
    max_value,
    no_zero_count: int,
    *,
    return_pass_values: bool = False,
):
    max_value = float(max_value)
    bin_edges = []
    bin_counts = []
    bin_percentages = []
    pass_values = []

    for bin_count, threshold_percent in (
        (FIRST_PASS_BIN_COUNT, FIRST_PASS_THRESHOLD_PERCENT),
        (SECOND_PASS_BIN_COUNT, SECOND_PASS_THRESHOLD_PERCENT),
    ):
        while True:
            bin_edges, bin_counts = build_histogram_counts(conn, sql_string, max_value, bin_count)
            if not bin_counts or no_zero_count <= 0:
                bin_percentages = [0.0 for _ in bin_counts]
                break

            last_bin_percent = bin_counts[-1] / no_zero_count * 100
            if last_bin_percent >= threshold_percent:
                bin_percentages = [(qv / no_zero_count * 100) for qv in bin_counts]
                break

            new_upper = trim_upper_bound(bin_edges, bin_counts, threshold_percent, no_zero_count)
            if abs(max_value - new_upper) <= 1e-12:
                bin_percentages = [(qv / no_zero_count * 100) for qv in bin_counts]
                break
            max_value = float(new_upper)
        pass_values.append(max_value)

    if return_pass_values:
        return max_value, bin_edges, bin_counts, bin_percentages, pass_values
    return max_value, bin_edges, bin_counts, bin_percentages


def build_histogram_counts(conn, sql_string: str, upper_bound: float, bin_count: int):
    bin_edges = [i * (upper_bound / bin_count) for i in range(bin_count + 1)]
    bin_counts = [0] * bin_count
    if upper_bound <= 0:
        return bin_edges, bin_counts

    rows = conn.execute(
        f"""
        SELECT
            LEAST(
                {bin_count},
                GREATEST(1, CAST(CEIL(v / {upper_bound:.16f} * {bin_count}) AS INTEGER))
            ) AS b,
            COUNT(*) AS c
        FROM {sql_string}
        WHERE v > 0.0
          AND v <= {upper_bound:.16f}
        GROUP BY b
        """
    ).fetchall()
    for bucket, count in rows:
        bucket_index = int(bucket) - 1
        if 0 <= bucket_index < bin_count:
            bin_counts[bucket_index] = int(count)
    return bin_edges, bin_counts


def trim_upper_bound(bin_edges, bin_counts, threshold_percent, no_zero_count: int):
    if len(bin_counts) == 0 or no_zero_count <= 0:
        return float(bin_edges[-1])
    keep_index = -1
    for i in range(len(bin_counts) - 1, -1, -1):
        if bin_counts[i] / no_zero_count * 100 >= threshold_percent:
            keep_index = i
            break
    if keep_index == -1:
        keep_index = 0
    return float(bin_edges[keep_index + 1])
