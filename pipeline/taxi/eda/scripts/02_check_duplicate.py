# -*- coding: utf-8 -*-
import json

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "02_merge_parquet_2019.parquet"
max_unique_values = 300
output_dir = taxi_root / "eda" / "results"
output_file = output_dir / "02_check_duplicate.json"
schema_file = output_dir / "01_check_parquet_schema.json"


def to_posix(path: Path) -> str:
    return path.as_posix()


def round_if_needed(value):
    if isinstance(value, float):
        rounded_value = round(value, 2)
        if rounded_value != value:
            return rounded_value
    return value


def false_mask(length):
    return pa.array([False] * length, type=pa.bool_())


def valid_int_mask(column):
    length = len(column)

    if pa.types.is_integer(column.type):
        return pc.fill_null(pc.is_valid(column), False)

    if pa.types.is_floating(column.type):
        is_valid = pc.fill_null(pc.is_valid(column), False)
        is_nan = pc.fill_null(pc.is_nan(column), False)
        not_nan = pc.invert(is_nan)
        truncated = pc.trunc(column)
        is_integer_like = pc.fill_null(pc.equal(column, truncated), False)
        return pc.and_(is_valid, pc.and_(not_nan, is_integer_like))

    if pa.types.is_string(column.type) or pa.types.is_large_string(column.type):
        trimmed = pc.utf8_trim_whitespace(column)
        is_valid = pc.fill_null(pc.is_valid(column), False)
        is_not_blank = pc.fill_null(pc.not_equal(trimmed, ""), False)
        casted = pc.cast(trimmed, pa.int64(), safe=False)
        cast_valid = pc.fill_null(pc.is_valid(casted), False)
        return pc.and_(is_valid, pc.and_(is_not_blank, cast_valid))

    return false_mask(length)


def valid_float_mask(column):
    length = len(column)

    if pa.types.is_integer(column.type) or pa.types.is_floating(column.type):
        is_valid = pc.fill_null(pc.is_valid(column), False)

        if pa.types.is_floating(column.type):
            is_nan = pc.fill_null(pc.is_nan(column), False)
            return pc.and_(is_valid, pc.invert(is_nan))

        return is_valid

    if pa.types.is_string(column.type) or pa.types.is_large_string(column.type):
        trimmed = pc.utf8_trim_whitespace(column)
        is_valid = pc.fill_null(pc.is_valid(column), False)
        is_not_blank = pc.fill_null(pc.not_equal(trimmed, ""), False)
        casted = pc.cast(trimmed, pa.float64(), safe=False)
        cast_valid = pc.fill_null(pc.is_valid(casted), False)
        return pc.and_(is_valid, pc.and_(is_not_blank, cast_valid))

    return false_mask(length)


def valid_string_mask(column):
    if pa.types.is_string(column.type) or pa.types.is_large_string(column.type):
        return pc.fill_null(pc.is_valid(column), False)

    return false_mask(len(column))


def valid_datetime_mask(column):
    if pa.types.is_timestamp(column.type):
        return pc.fill_null(pc.is_valid(column), False)

    if pa.types.is_string(column.type) or pa.types.is_large_string(column.type):
        trimmed = pc.utf8_trim_whitespace(column)
        is_valid = pc.fill_null(pc.is_valid(column), False)
        is_not_blank = pc.fill_null(pc.not_equal(trimmed, ""), False)
        parsed = pc.strptime(trimmed, format="%Y-%m-%d %H:%M:%S.%f", unit="us", error_is_null=True)
        parsed_valid = pc.fill_null(pc.is_valid(parsed), False)
        return pc.and_(is_valid, pc.and_(is_not_blank, parsed_valid))

    return false_mask(len(column))


def valid_null_mask(column):
    return pc.fill_null(pc.is_null(column), False)


def get_valid_mask(column, expected_type):
    if expected_type in {"int8", "int16", "int32", "int64"}:
        return valid_int_mask(column)

    if expected_type in {"float", "float32", "float64", "double"}:
        return valid_float_mask(column)

    if expected_type == "string":
        return valid_string_mask(column)

    if expected_type.startswith("timestamp"):
        return valid_datetime_mask(column)

    if expected_type == "null":
        return valid_null_mask(column)

    return pc.fill_null(pc.is_valid(column), False)


parquet = pq.ParquetFile(input_file)
schema = parquet.schema_arrow
column_names = schema.names
unique_values_by_column = {column_name: set() for column_name in column_names}
total_rows = 0
low_cardinality_column_names = []
high_cardinality_column_names = []
valid_counts = {column_name: 0 for column_name in column_names}
active_unique_columns = set(column_names)

schema_report = json.loads(schema_file.read_text(encoding="utf-8"))

reference_schema = schema_report["reference_schema"]
row_group_count = parquet.metadata.num_row_groups
progress_kwargs = {
    "unit": "group",
    "leave": True,
    "dynamic_ncols": True,
    "mininterval": 0.2,
}

with tqdm(total=row_group_count, desc="Checking unique values by column", **progress_kwargs) as progress_bar:
    for row_group_index in range(row_group_count):
        table = parquet.read_row_group(row_group_index)
        total_rows += table.num_rows

        for column_name in column_names:
            expected_type = reference_schema.get(column_name)
            valid_mask = get_valid_mask(table[column_name], expected_type)
            valid_counts[column_name] += pc.sum(pc.cast(valid_mask, "int64")).as_py() or 0

        for column_name in list(active_unique_columns):
            current_unique_values = unique_values_by_column[column_name]

            unique_values = pc.unique(table[column_name]).to_pylist()
            current_unique_values.update(unique_values)

            if len(current_unique_values) > max_unique_values:
                active_unique_columns.remove(column_name)

        progress_bar.update(1)

for column_name in column_names:
    unique_count = len(unique_values_by_column[column_name])

    if unique_count <= max_unique_values:
        low_cardinality_column_names.append(column_name)
    else:
        high_cardinality_column_names.append(column_name)

value_counts_by_column = {
    column_name: {value: 0 for value in unique_values_by_column[column_name]}
    for column_name in low_cardinality_column_names
}

if low_cardinality_column_names:
    with tqdm(total=row_group_count, desc="Counting low-cardinality values", **progress_kwargs) as progress_bar:
        for row_group_index in range(row_group_count):
            table = parquet.read_row_group(row_group_index, columns=low_cardinality_column_names)

            for column_name in low_cardinality_column_names:
                for value in table[column_name].to_pylist():
                    value_counts_by_column[column_name][value] += 1

            progress_bar.update(1)

low_duplicate_columns = []
for column_name in low_cardinality_column_names:
    unique_values = unique_values_by_column[column_name]
    sorted_values = sorted(unique_values, key=lambda value: (value is None, str(value)))
    values = []
    quantity = []
    quantity_percent = []

    for value in sorted_values:
        count = value_counts_by_column[column_name][value]
        values.append(round_if_needed(value))
        quantity.append(count)
        quantity_percent.append(
            round_if_needed((count / total_rows * 100) if total_rows else 0)
        )

    low_duplicate_columns.append({
        "column_name": column_name,
        "type_value": reference_schema.get(column_name),
        "unique_count": len(unique_values),
        "correct_type_percent": round_if_needed((valid_counts[column_name] / total_rows * 100) if total_rows else 0),
        "values": values,
        "quantity": quantity,
        "quantity_percent": quantity_percent,
    })

high_duplicate_columns = [
    {
        "column_name": column_name,
        "type_value": reference_schema.get(column_name),
        "correct_type_percent": round_if_needed((valid_counts[column_name] / total_rows * 100) if total_rows else 0),
    }
    for column_name in high_cardinality_column_names
]

report = {
    "input_file": to_posix(input_file),
    "schema_file": to_posix(schema_file),
    "max_unique_values": max_unique_values,
    "total_rows": total_rows,
    "low_duplicate_columns": low_duplicate_columns,
    "high_duplicate_columns": high_duplicate_columns,
}

output_dir.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"Saved report: {output_file}")
