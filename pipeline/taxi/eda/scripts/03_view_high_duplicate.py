# -*- coding: utf-8 -*-
import json

from datetime import datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "03_drop_airport_fee.parquet"
output_dir = taxi_root / "eda" / "results"
output_file = output_dir / "03_view_high_duplicate.json"
profile_file = output_dir / "02_check_duplicate.json"

tail_fraction = 1 / 101
positive_bin_count = 100
year_start = datetime(2019, 1, 1)
year_end = datetime(2020, 1, 1)


def to_posix(path: Path) -> str:
    return path.as_posix()


def round_if_needed(value):
    if isinstance(value, float):
        rounded_value = round(value, 2)
        if rounded_value != value:
            return rounded_value
    return value


def serialize_number(value):
    if value is None:
        return None

    if isinstance(value, (np.integer, int)):
        return int(value)

    if isinstance(value, (np.floating, float)):
        return round_if_needed(float(value))

    return value


def serialize_timestamp_from_us(value):
    if value is None:
        return None

    timestamp = pa.scalar(int(value), type=pa.timestamp("us")).as_py()
    return timestamp.isoformat(sep=" ")


def get_filtered_numeric_column(table_column):
    valid_mask = pc.fill_null(pc.is_valid(table_column), False)

    if pa.types.is_floating(table_column.type):
        nan_mask = pc.fill_null(pc.is_nan(table_column), False)
        valid_mask = pc.and_(valid_mask, pc.invert(nan_mask))

    return pc.filter(table_column, valid_mask)


def get_filtered_timestamp_column(table_column):
    valid_mask = pc.fill_null(pc.is_valid(table_column), False)
    filtered_column = pc.filter(table_column, valid_mask)
    return pc.cast(filtered_column, pa.int64())


def chunked_array_to_numpy(chunks):
    if not chunks:
        return np.array([])

    combined_column = pa.chunked_array(chunks).combine_chunks()
    return np.asarray(combined_column.to_numpy(zero_copy_only=False))


def build_positive_bins(positive_values, max_chart, total_rows):
    if positive_values.size == 0:
        return {
            "milestone": [],
            "quantity": [],
            "quantity_percent": [],
        }

    if max_chart <= 0:
        return {
            "milestone": [],
            "quantity": [],
            "quantity_percent": [],
        }

    bin_edges = np.linspace(0, max_chart, positive_bin_count + 1)
    sorted_values = np.sort(positive_values)
    quantity = []

    for index in range(1, len(bin_edges)):
        previous_edge = bin_edges[index - 1]
        current_edge = bin_edges[index]
        left_position = np.searchsorted(sorted_values, previous_edge, side="right")
        right_position = np.searchsorted(sorted_values, current_edge, side="right")
        quantity.append(int(right_position - left_position))

    return {
        "milestone": [serialize_number(edge) for edge in bin_edges[1:-1]],
        "quantity": quantity,
        "quantity_percent": [
            round_if_needed((current_quantity / total_rows * 100) if total_rows else 0)
            for current_quantity in quantity
        ],
    }


def profile_numeric_column(numpy_values, total_rows):
    if numpy_values.size == 0:
        return {
            "min_value": None,
            "zero_quantity": 0,
            "negative_quantity": 0,
            "positive_range": {
                "max_chart": None,
                "milestone": [],
                "quantity": [],
                "quantity_percent": [],
            },
            "above_max_chart_quantity": 0,
            "max_value": None,
        }

    negative_values = numpy_values[numpy_values < 0]
    zero_values = numpy_values[numpy_values == 0]
    positive_values = numpy_values[numpy_values > 0]

    if positive_values.size > 0:
        max_chart = np.quantile(positive_values, 1 - tail_fraction)
        max_value = positive_values.max()
        positive_main = positive_values[positive_values <= max_chart]
        above_max_chart_quantity = int(np.sum(positive_values > max_chart))
        positive_range = build_positive_bins(positive_main, max_chart, total_rows)
    else:
        max_chart = None
        above_max_chart_quantity = 0
        positive_range = {
            "milestone": [],
            "quantity": [],
            "quantity_percent": [],
        }

    return {
        "min_value": serialize_number(numpy_values.min()),
        "negative_quantity": int(negative_values.size),
        "zero_quantity": int(zero_values.size),
        "positive_range": {
            "max_chart": serialize_number(max_chart),
            **positive_range,
        },
        "above_max_chart_quantity": above_max_chart_quantity,
        "max_value": serialize_number(numpy_values.max()),
    }

profile_report = json.loads(profile_file.read_text(encoding="utf-8"))

high_duplicate_columns = profile_report["high_duplicate_columns"]
total_rows = profile_report["total_rows"]
columns_to_check = [column["column_name"] for column in high_duplicate_columns]
type_value_by_column = {
    column["column_name"]: column["type_value"]
    for column in high_duplicate_columns
}
numeric_columns = [
    column_name
    for column_name in columns_to_check
    if not type_value_by_column[column_name].startswith("timestamp")
]
datetime_columns = [
    column_name
    for column_name in columns_to_check
    if type_value_by_column[column_name].startswith("timestamp")
]

parquet = pq.ParquetFile(input_file)
row_group_count = parquet.metadata.num_row_groups
progress_kwargs = {
    "unit": "group",
    "leave": True,
    "dynamic_ncols": True,
    "mininterval": 0.2,
}
year_start_us = int(pa.scalar(year_start, type=pa.timestamp("us")).cast(pa.int64()).as_py())
year_end_us = int(pa.scalar(year_end, type=pa.timestamp("us")).cast(pa.int64()).as_py())

numeric_stats = {
    column_name: {
        "min_value": None,
        "max_value": None,
        "negative_quantity": 0,
        "zero_quantity": 0,
        "positive_chunks": [],
    }
    for column_name in numeric_columns
}
datetime_stats = {
    column_name: {
        "min_value": None,
        "max_value": None,
        "before_2019_quantity": 0,
        "month_quantity": [0] * 12,
        "after_2019_quantity": 0,
    }
    for column_name in datetime_columns
}

with tqdm(total=row_group_count, desc="Profiling high-duplicate columns", **progress_kwargs) as progress_bar:
    for row_group_index in range(row_group_count):
        table = parquet.read_row_group(row_group_index, columns=columns_to_check)

        for column_name in numeric_columns:
            filtered_column = get_filtered_numeric_column(table[column_name])

            if len(filtered_column) == 0:
                continue

            current_min = pc.min(filtered_column).as_py()
            current_max = pc.max(filtered_column).as_py()
            stats = numeric_stats[column_name]

            if current_min is not None:
                if stats["min_value"] is None or current_min < stats["min_value"]:
                    stats["min_value"] = current_min

            if current_max is not None:
                if stats["max_value"] is None or current_max > stats["max_value"]:
                    stats["max_value"] = current_max

            stats["negative_quantity"] += pc.sum(
                pc.cast(pc.less(filtered_column, 0), pa.int64())
            ).as_py() or 0
            stats["zero_quantity"] += pc.sum(
                pc.cast(pc.equal(filtered_column, 0), pa.int64())
            ).as_py() or 0

            positive_column = pc.filter(filtered_column, pc.greater(filtered_column, 0))
            if len(positive_column) > 0:
                if isinstance(positive_column, pa.ChunkedArray):
                    stats["positive_chunks"].extend(positive_column.chunks)
                else:
                    stats["positive_chunks"].append(positive_column)

        for column_name in datetime_columns:
            filtered_column = get_filtered_timestamp_column(table[column_name])

            if len(filtered_column) == 0:
                continue

            current_min = pc.min(filtered_column).as_py()
            current_max = pc.max(filtered_column).as_py()
            stats = datetime_stats[column_name]

            if current_min is not None:
                if stats["min_value"] is None or current_min < stats["min_value"]:
                    stats["min_value"] = current_min

            if current_max is not None:
                if stats["max_value"] is None or current_max > stats["max_value"]:
                    stats["max_value"] = current_max

            stats["before_2019_quantity"] += pc.sum(
                pc.cast(pc.less(filtered_column, year_start_us), pa.int64())
            ).as_py() or 0
            stats["after_2019_quantity"] += pc.sum(
                pc.cast(pc.greater_equal(filtered_column, year_end_us), pa.int64())
            ).as_py() or 0

            in_2019_mask = pc.and_(
                pc.greater_equal(filtered_column, year_start_us),
                pc.less(filtered_column, year_end_us),
            )
            in_2019_column = pc.filter(filtered_column, in_2019_mask)

            if len(in_2019_column) > 0:
                in_2019_timestamps = pc.cast(in_2019_column, pa.timestamp("us"))
                month_numbers = pc.month(in_2019_timestamps).to_pylist()

                for month in month_numbers:
                    stats["month_quantity"][int(month) - 1] += 1

        progress_bar.update(1)

columns_report = []

for column_name in columns_to_check:
    type_value = type_value_by_column[column_name]

    if type_value.startswith("timestamp"):
        stats = datetime_stats[column_name]
        columns_report.append(
            {
                "column_name": column_name,
                "type_value": type_value,
                "min_value": serialize_timestamp_from_us(stats["min_value"]),
                "before_2019_quantity": stats["before_2019_quantity"],
                "month_quantity": stats["month_quantity"],
                "month_percent": [
                    round_if_needed((quantity / total_rows * 100) if total_rows else 0)
                    for quantity in stats["month_quantity"]
                ],
                "after_2019_quantity": stats["after_2019_quantity"],
                "max_value": serialize_timestamp_from_us(stats["max_value"]),
            }
        )
        continue

    stats = numeric_stats[column_name]
    positive_values = chunked_array_to_numpy(stats["positive_chunks"])
    numeric_values = np.array([])

    if stats["min_value"] is not None or stats["max_value"] is not None:
        # Build a minimal array only to reuse the existing numeric profiling helper.
        parts = []
        if stats["negative_quantity"] > 0 and stats["min_value"] is not None:
            parts.append(np.array([stats["min_value"]], dtype=np.float64))
        if stats["zero_quantity"] > 0:
            parts.append(np.array([0.0], dtype=np.float64))
        if positive_values.size > 0:
            parts.append(positive_values.astype(np.float64, copy=False))
        if parts:
            numeric_values = np.concatenate(parts)

    profile = profile_numeric_column(numeric_values, total_rows)
    profile["negative_quantity"] = stats["negative_quantity"]
    profile["zero_quantity"] = stats["zero_quantity"]
    profile["min_value"] = serialize_number(stats["min_value"])
    profile["max_value"] = serialize_number(stats["max_value"])

    columns_report.append(
        {
            "column_name": column_name,
            "type_value": type_value,
            **profile,
        }
    )

report = {
    "input_file": to_posix(input_file),
    "profile_file": to_posix(profile_file),
    "tail_fraction": tail_fraction,
    "positive_bin_count": positive_bin_count,
    "columns": columns_report,
}

output_dir.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


print(f"Saved report: {output_file}")
