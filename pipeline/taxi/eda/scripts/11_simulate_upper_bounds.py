import json
import numpy as np
from tqdm import tqdm
from pipeline.services.helpers import serialize_number
from pipeline.services.queries import quote_identifier
from pipeline.services.queries import connect_and_check
from pipeline.services.views import VIEW_TAXI_BUSINESS_RULES
from pipeline.services.paths import WAREHOUSE_DB_FILE, TAXI_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
output_json = output_dir / "11_simulate_upper_bounds.json"

TARGET_COLUMNS = ["trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"]
FIRST_PASS_BIN_COUNT = 100
SECOND_PASS_BIN_COUNT = 10
FIRST_PASS_THRESHOLD_PERCENT = 0.05
SECOND_PASS_THRESHOLD_PERCENT = 0.5


def prepare_column_source(conn, col_name: str):
    col = quote_identifier(col_name)
    source_table = "tmp_eda11_values"
    conn.execute(f'DROP TABLE IF EXISTS "{source_table}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{source_table}" AS
        SELECT CAST({col} AS DOUBLE) AS v
        FROM {quote_identifier(VIEW_TAXI_BUSINESS_RULES)}
        WHERE TRY_CAST({col} AS DOUBLE) IS NOT NULL
          AND NOT isnan(CAST({col} AS DOUBLE))
        """
    )

    scan_max, zero_count = conn.execute(
        f"""
        SELECT
            MAX(v) FILTER (WHERE v > 0.0) AS scan_max,
            COUNT(*) FILTER (WHERE v = 0.0) AS zero_count
        FROM "{source_table}"
        """
    ).fetchone()
    return source_table, float(scan_max or 1.0), int(zero_count or 0)


def build_histogram_counts(conn, source_table: str, upper_bound: float, bin_count: int):
    edges = np.linspace(0.0, upper_bound, bin_count + 1)
    counts = np.zeros(bin_count, dtype=np.int64)
    if upper_bound <= 0:
        return edges, counts

    rows = conn.execute(
        f"""
        WITH positive AS (
            SELECT v
            FROM "{source_table}"
            WHERE v > 0.0
              AND v <= {upper_bound:.16f}
        ),
        bucketed AS (
            SELECT LEAST({bin_count}, GREATEST(1, CAST(CEIL(v / {upper_bound:.16f} * {bin_count}) AS INTEGER))) AS b
            FROM positive
        )
        SELECT b, COUNT(*)
        FROM bucketed
        GROUP BY b
        """
    ).fetchall()
    for b, c in rows:
        counts[int(b) - 1] = int(c)
    return edges, counts


def trim_upper_bound(edges, quantity, threshold_percent, denominator_non_zero: int):
    if len(quantity) == 0 or denominator_non_zero <= 0:
        return float(edges[-1])
    quantity_percent_raw = quantity / denominator_non_zero * 100
    keep_index = -1
    for i in range(len(quantity) - 1, -1, -1):
        if quantity_percent_raw[i] >= threshold_percent:
            keep_index = i
            break
    if keep_index == -1:
        keep_index = 0
    return float(edges[keep_index + 1])


def iterative_trim(conn, source_table, initial_upper, bin_count, threshold_percent, denominator_non_zero):
    current_upper = float(initial_upper)
    while True:
        edges, quantity = build_histogram_counts(conn, source_table, current_upper, bin_count)
        if denominator_non_zero <= 0:
            percent_full = np.zeros_like(quantity, dtype=float)
        else:
            percent_full = quantity / denominator_non_zero * 100

        if len(percent_full) > 0 and float(percent_full[-1]) >= threshold_percent:
            return current_upper, edges, quantity, percent_full

        new_upper = trim_upper_bound(edges, quantity, threshold_percent, denominator_non_zero)
        if np.isclose(new_upper, current_upper):
            raise RuntimeError(
                f"Cannot reach threshold {threshold_percent}% with bin_count={bin_count} "
                f"from upper={current_upper:.6f}; last_bin_percent={float(percent_full[-1]) if len(percent_full) > 0 else 0.0:.6f}"
            )
        current_upper = float(new_upper)


def compute_simulation_payload(conn, total_rows: int) -> dict:
    columns_report = []
    for col_name in tqdm(
        TARGET_COLUMNS,
        desc="EDA 11 - simulate upper bounds",
        disable=TQDM_DISABLE,
        leave=False,
        dynamic_ncols=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        source_table, scan_max, zero_count = prepare_column_source(conn, col_name)
        denominator_non_zero = int(total_rows) - int(zero_count)

        first_max, _, _, _ = iterative_trim(
            conn=conn,
            source_table=source_table,
            initial_upper=scan_max,
            bin_count=FIRST_PASS_BIN_COUNT,
            threshold_percent=FIRST_PASS_THRESHOLD_PERCENT,
            denominator_non_zero=denominator_non_zero,
        )
        second_max, _, _, _ = iterative_trim(
            conn=conn,
            source_table=source_table,
            initial_upper=first_max,
            bin_count=SECOND_PASS_BIN_COUNT,
            threshold_percent=SECOND_PASS_THRESHOLD_PERCENT,
            denominator_non_zero=denominator_non_zero,
        )

        second_edges, second_quantity = build_histogram_counts(
            conn, source_table, second_max, SECOND_PASS_BIN_COUNT
        )
        if denominator_non_zero <= 0:
            second_percent = np.zeros_like(second_quantity, dtype=float)
        else:
            second_percent = second_quantity / denominator_non_zero * 100

        milestone = second_edges[1:-1] if len(second_edges) > 2 else np.array([], dtype=float)
        expanded_bins = []
        for i in range(SECOND_PASS_BIN_COUNT):
            expanded_bins.append(
                {
                    "index": i + 1,
                    "left": serialize_number(second_edges[i]),
                    "right": serialize_number(second_edges[i + 1]),
                    "quantity": int(second_quantity[i]) if i < len(second_quantity) else 0,
                    "quantity_percent": round(float(second_percent[i]), 5) if i < len(second_percent) else 0.0,
                }
            )

        columns_report.append(
            {
                "column_name": col_name,
                "scan_max_value": serialize_number(scan_max),
                "first_pass_threshold_percent": FIRST_PASS_THRESHOLD_PERCENT,
                "first_pass_max_value": serialize_number(first_max),
                "second_pass_threshold_percent": SECOND_PASS_THRESHOLD_PERCENT,
                "final_upper_bound": serialize_number(second_max),
                "max_value": serialize_number(second_max),
                "milestone": [serialize_number(v) for v in milestone],
                "quantity": second_quantity.tolist(),
                "quantity_percent": [round(float(v), 5) for v in second_percent],
                "expanded_bins": expanded_bins,
            }
        )

    return {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": VIEW_TAXI_BUSINESS_RULES,
        "generated_by": "eda/scripts/11_simulate_upper_bounds.py",
        "first_pass_bin_count": FIRST_PASS_BIN_COUNT,
        "second_pass_bin_count": SECOND_PASS_BIN_COUNT,
        "first_pass_threshold_percent": FIRST_PASS_THRESHOLD_PERCENT,
        "second_pass_threshold_percent": SECOND_PASS_THRESHOLD_PERCENT,
        "columns": columns_report,
    }


def main(conn):

    total_rows = int(conn.execute(f"SELECT count(*) FROM {quote_identifier(VIEW_TAXI_BUSINESS_RULES)}").fetchone()[0] or 0)
    payload = compute_simulation_payload(conn, total_rows=total_rows)
    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved JSON: {output_json}")

