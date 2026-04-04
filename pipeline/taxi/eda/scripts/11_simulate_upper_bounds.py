# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "04_apply_business_rules.parquet"
output_json = taxi_root / "eda" / "results" / "11_simulate_upper_bounds.json"

TQDM_DISABLE = not sys.stderr.isatty()
TARGET_COLUMNS = ["trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"]
FIRST_PASS_BIN_COUNT = 100
SECOND_PASS_BIN_COUNT = 10
FIRST_PASS_THRESHOLD_PERCENT = 0.05
SECOND_PASS_THRESHOLD_PERCENT = 0.5


def get_filtered_numeric_column(col):
    valid_mask = pc.fill_null(pc.is_valid(col), False)
    if pa.types.is_floating(col.type):
        nan_mask = pc.fill_null(pc.is_nan(col), False)
        valid_mask = pc.and_(valid_mask, pc.invert(nan_mask))
    return pc.filter(col, valid_mask)


def load_positive_values_and_zero_count(parquet: pq.ParquetFile, col_name: str):
    chunks = []
    zero_count = 0
    for rg in range(parquet.metadata.num_row_groups):
        arr = parquet.read_row_group(rg, columns=[col_name])[col_name]
        zero_count += int(pc.sum(pc.cast(pc.fill_null(pc.equal(arr, 0.0), False), pa.int64())).as_py() or 0)
        filtered = get_filtered_numeric_column(arr)
        if len(filtered) == 0:
            continue
        positive = pc.filter(filtered, pc.greater(filtered, 0.0))
        if len(positive) == 0:
            continue
        if isinstance(positive, pa.ChunkedArray):
            np_arr = positive.combine_chunks().to_numpy(zero_copy_only=False)
        else:
            np_arr = positive.to_numpy(zero_copy_only=False)
        if np_arr.size > 0:
            chunks.append(np_arr.astype(np.float64, copy=False))

    if not chunks:
        return np.array([], dtype=np.float64), zero_count
    if len(chunks) == 1:
        return chunks[0], zero_count
    return np.concatenate(chunks), zero_count


def build_histogram_from_values(values: np.ndarray, upper_bound: float, bin_count: int):
    edges = np.linspace(0.0, upper_bound, bin_count + 1)
    histogram = np.zeros(len(edges) - 1, dtype=np.int64)
    if values.size == 0:
        return edges, histogram
    clipped = values[values <= upper_bound]
    if clipped.size == 0:
        return edges, histogram
    histogram, _ = np.histogram(clipped, bins=edges)
    return edges, histogram


def trim_upper_bound(edges, quantity, threshold_percent, denominator_non_zero: int):
    if len(quantity) == 0 or denominator_non_zero <= 0:
        return edges[-1]

    quantity_percent_raw = quantity / denominator_non_zero * 100
    keep_index = -1
    for i in range(len(quantity) - 1, -1, -1):
        if quantity_percent_raw[i] >= threshold_percent:
            keep_index = i
            break
    if keep_index == -1:
        keep_index = 0
    return edges[keep_index + 1]


def iterative_trim(
    values: np.ndarray,
    initial_upper: float,
    bin_count: int,
    threshold_percent: float,
    denominator_non_zero: int,
):
    current_upper = float(initial_upper)
    last_full_edges = np.array([0.0], dtype=float)
    last_full_quantity = np.array([], dtype=np.int64)
    last_full_percent = np.array([], dtype=float)

    while True:
        edges, quantity = build_histogram_from_values(values, current_upper, bin_count)
        if denominator_non_zero <= 0:
            percent_full = np.zeros_like(quantity, dtype=float)
        else:
            percent_full = quantity / denominator_non_zero * 100

        last_full_edges = edges
        last_full_quantity = quantity
        last_full_percent = percent_full

        if len(percent_full) > 0 and float(percent_full[-1]) >= threshold_percent:
            break

        new_upper = trim_upper_bound(edges, quantity, threshold_percent, denominator_non_zero)
        if np.isclose(new_upper, current_upper):
            raise RuntimeError(
                f"Cannot reach threshold {threshold_percent}% with bin_count={bin_count} "
                f"from upper={current_upper:.6f}; last_bin_percent={float(percent_full[-1]) if len(percent_full) > 0 else 0.0:.6f}"
            )
        current_upper = float(new_upper)

    return current_upper, last_full_edges, last_full_quantity, last_full_percent


def serialize_number(value):
    if value is None:
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if np.isinf(value):
            return None
        return round(float(value), 2)
    return value


def compute_simulation_payload(parquet: pq.ParquetFile) -> dict:
    columns_report = []

    for col_name in tqdm(
        TARGET_COLUMNS,
        desc="EDA 11 - simulate upper bounds",
        disable=TQDM_DISABLE,
        leave=False,
        dynamic_ncols=True,
        mininterval=0.5,
    ):
        values, zero_count = load_positive_values_and_zero_count(parquet, col_name)
        if values.size == 0:
            scan_max = 1.0
        else:
            scan_max = float(np.max(values))
        
        denominator_non_zero = int(parquet.metadata.num_rows) - int(zero_count)

        first_max, _, _, _ = iterative_trim(
            values=values,
            initial_upper=scan_max,
            bin_count=FIRST_PASS_BIN_COUNT,
            threshold_percent=FIRST_PASS_THRESHOLD_PERCENT,
            denominator_non_zero=denominator_non_zero,
        )
        second_max, _, _, _ = iterative_trim(
            values=values,
            initial_upper=first_max,
            bin_count=SECOND_PASS_BIN_COUNT,
            threshold_percent=SECOND_PASS_THRESHOLD_PERCENT,
            denominator_non_zero=denominator_non_zero,
        )

        second_edges, second_quantity = build_histogram_from_values(values, second_max, SECOND_PASS_BIN_COUNT)
        if denominator_non_zero <= 0:
            second_percent = np.zeros_like(second_quantity, dtype=float)
        else:
            second_percent = second_quantity / denominator_non_zero * 100
        last_second_percent = float(second_percent[-1]) if len(second_percent) > 0 else 0.0
        if last_second_percent < SECOND_PASS_THRESHOLD_PERCENT:
            raise RuntimeError(
                f"Second pass final check failed for {col_name}: "
                f"last_bin_percent={last_second_percent:.6f} < {SECOND_PASS_THRESHOLD_PERCENT} "
                f"(upper={second_max:.6f}, denominator_non_zero={denominator_non_zero})"
            )

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
        "input_file": input_file.as_posix(),
        "generated_by": "eda/scripts/11_simulate_upper_bounds.py",
        "first_pass_bin_count": FIRST_PASS_BIN_COUNT,
        "second_pass_bin_count": SECOND_PASS_BIN_COUNT,
        "first_pass_threshold_percent": FIRST_PASS_THRESHOLD_PERCENT,
        "second_pass_threshold_percent": SECOND_PASS_THRESHOLD_PERCENT,
        "columns": columns_report,
    }


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    parquet = pq.ParquetFile(input_file)
    payload = compute_simulation_payload(parquet)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved JSON: {output_json}")


if __name__ == "__main__":
    main()
