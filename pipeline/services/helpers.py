import csv, shutil, json, re
from decimal import Decimal
from pathlib import Path
from typing import Any
from pipeline.constants.columns import AGGREGATE_COLUMNS



# support calculate
def extract_month(path: Path) -> int:
    name = path.stem # e.g. yellow_tripdata_2019-01 from path/to/yellow_tripdata_2019-01.parquet
    month_str = name.split("-")[-1] # e.g. 01 from yellow_tripdata_2019-01
    return int(month_str) # e.g. 1 from 01


def is_schema_type_match(parquet_type: str, database_type: str) -> bool:
    parquet_type = str(parquet_type or "").strip().upper()
    database_type = str(database_type or "").strip().upper()
    if not parquet_type or not database_type:
        return False

    parquet_tokens = _schema_type_tokens(parquet_type)
    database_tokens = _schema_type_tokens(database_type)
    return bool(parquet_tokens & database_tokens)


def _schema_type_tokens(type_name: str) -> set[str]:
    normalized = str(type_name or "").strip().upper()
    if not normalized:
        return set()

    base = normalized.split("(", 1)[0]
    tokens = {normalized, base}

    if "INT" in normalized and "UINT" not in normalized:
        tokens.add("INTEGER")
    if any(token in normalized for token in {"DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC"}):
        tokens.add("FLOAT")
    if any(token in normalized for token in {"CHAR", "STRING", "TEXT", "VARCHAR"}):
        tokens.add("STRING")
    if "TIMESTAMP" in normalized or "DATETIME" in normalized:
        tokens.add("TIMESTAMP")
    elif "DATE" in normalized:
        tokens.add("DATE")
    if "BOOL" in normalized:
        tokens.add("BOOLEAN")

    if "BIGINT" in normalized:
        tokens.add("INTEGER")

    return tokens


def reset_csv_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_csv(
    output_dir: Path,
    file_name_array: list[str],
    tuple_data_array: list[Any],
) -> None:
    if len(file_name_array) != len(tuple_data_array):
        raise ValueError("csv_array and tuple_data_array must have the same length")

    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name, tuple_data in zip(file_name_array, tuple_data_array):
        normalized_file_name = file_name if file_name.endswith(".csv") else f"{file_name}.csv"
        if len(tuple_data) != 2:
            raise ValueError("each csv payload must contain columns and value arrays")
        column_names, values_arrays = tuple_data
        if len(column_names) != len(values_arrays):
            raise ValueError("column_names and values must have the same length")

        row_count = len(values_arrays[0]) if values_arrays else 0
        if any(len(values_array) != row_count for values_array in values_arrays):
            raise ValueError("all value arrays must have the same length")

        with (output_dir / normalized_file_name).open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(column_names)
            for row_index in range(row_count):
                writer.writerow(
                    [
                        "null" if values[row_index] is None else values[row_index]
                        for values in values_arrays
                    ]
                )


def write_csv_rows(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    columns: list[str] | None = None,
) -> None:
    if not rows and not columns:
        return

    columns = columns or ordered_fieldnames(rows)
    write_csv(
        path.parent,
        [path.stem],
        [(
            columns,
            [[row.get(column) for row in rows] for column in columns],
        )],
    )







def round_if_needed(value, digits: int = 2):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        value = float(value)
    if isinstance(value, float):
        rounded_value = round(value, digits)
        if rounded_value != value:
            return rounded_value
    return value


def percentage(part, total):
    return round_if_needed((part / total * 100) if total else 0.0)













def ordered_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "check",
        "column_name",
        "month",
        "payment_type",
        "key",
        "value",
        "count",
        "percentage",
        "month_count",
        "month_percentage",
        "bin_edge",
        "bin_count",
        "bin_percentage",
    ]
    fieldnames = [key for key in preferred if any(key in row for row in rows)]
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames









def column_profile_file_name(column_name: str, index: int) -> str:
    slug = re.sub(r"[^0-9A-Z]+", "_", str(column_name or "").upper()).strip("_")
    if not slug:
        slug = "COLUMN"
    return f"{index:02d}_{slug}.csv"


def write_low_unique_column_csv(output_dir: Path, row: dict[str, Any], *, file_name: str) -> str:
    profile_dir = output_dir / "low_unique_columns"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / file_name
    value_rows = [
        {
            "value": value,
            "count": count,
            "percentage": percentage_value,
        }
        for value, count, percentage_value in zip(
            row.get("values", []),
            row.get("counts", []),
            row.get("percentages", []),
        )
    ]
    write_csv_rows(profile_path, value_rows, columns=["value", "count", "percentage"])
    return profile_path.relative_to(output_dir).as_posix()


def write_high_unique_column_csv(output_dir: Path, row: dict[str, Any], *, file_name: str) -> tuple[str, str]:
    column_name = row.get("column_name")
    if row.get("month_counts") or row.get("month_percentages"):
        profile_kind = "datetime"
        profile_dir = output_dir / "high_unique_columns_datetime"
        profile_rows = [
            {
                "month": month,
                "month_count": month_count,
                "month_percentage": month_percentage,
            }
            for month, (month_count, month_percentage) in enumerate(
                zip(row.get("month_counts", []), row.get("month_percentages", [])),
                start=1,
            )
        ]
    elif row.get("bin_edges") or row.get("bin_counts") or row.get("bin_percentages"):
        profile_kind = "numeric"
        profile_dir = output_dir / "high_unique_columns_numeric"
        bin_edges = row.get("bin_edges", [])
        bin_counts = row.get("bin_counts", [])
        bin_percentages = row.get("bin_percentages", [])
        use_full_bin_edges = (
            column_name in AGGREGATE_COLUMNS
            and len(bin_edges) == len(bin_counts) + 1
            and len(bin_edges) == len(bin_percentages) + 1
        )
        edge_values = bin_edges if use_full_bin_edges else bin_edges[:len(bin_counts)]
        profile_rows = [
            {
                "bin_edge": bin_edge,
                "bin_count": bin_counts[index] if index < len(bin_counts) else None,
                "bin_percentage": bin_percentages[index] if index < len(bin_percentages) else None,
            }
            for index, bin_edge in enumerate(edge_values)
        ]
    else:
        profile_kind = "simple"
        profile_dir = output_dir / "high_unique_columns"
        profile_rows = [
            {
                key: value
                for key, value in row.items()
                if key not in {"filter"}
            }
        ]

    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / file_name
    columns = {
        "datetime": ["month", "month_count", "month_percentage"],
        "numeric": ["bin_edge", "bin_count", "bin_percentage"],
        "simple": ordered_fieldnames(profile_rows),
    }[profile_kind]
    write_csv_rows(profile_path, profile_rows, columns=columns)
    return profile_kind, profile_path.relative_to(output_dir).as_posix()


def write_aggregate_columns_csvs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    column_rows = []
    array_rows = []
    for row in rows:
        column_name = row.get("column_name")
        column_rows.append(
            {
                "column_name": column_name,
                "data_type": row.get("data_type"),
                "valid_type_percent": row.get("valid_type_percent"),
                "min_value": row.get("min_value"),
                "negative_count": row.get("negative_count"),
                "zero_count": row.get("zero_count"),
                "chart_max_value": row.get("chart_max_value"),
                "above_chart_max_value_count": row.get("above_chart_max_value_count"),
                "max_value": row.get("max_value"),
                "range_count": row.get("range_count"),
            }
        )
        for bin_edge, bin_count, bin_percentage in zip(
            row.get("bin_edges", []),
            row.get("bin_counts", []),
            row.get("bin_percentages", []),
        ):
            array_rows.append(
                {
                    "column_name": column_name,
                    "bin_edge": bin_edge,
                    "bin_count": bin_count,
                    "bin_percentage": bin_percentage,
                }
            )
    write_csv_rows(output_dir / "aggregate_columns.csv", column_rows)
    write_csv_rows(output_dir / "aggregate_columns_array.csv", array_rows)


def dumps_json_compact(
    payload,
    *,
    indent: int = 2,
    compact_list_min_items: int = 21,
    compact_array_paths: list[tuple] | None = None,
    align_object_values: bool = False,
    align_compact_array_items: bool = False,
    align_compact_array_key_labels: bool = False,
    compact_all_scalar_arrays: bool = False,
    parallel_array_groups: list[tuple[str, ...]] | None = None,
) -> str:
    paths = compact_array_paths or []
    groups = parallel_array_groups or []
    return _json_compact_pretty(
        payload,
        indent=indent,
        level=0,
        compact_list_min_items=compact_list_min_items,
        compact_array_paths=paths,
        current_path=(),
        align_object_values=align_object_values,
        align_compact_array_items=align_compact_array_items,
        align_compact_array_key_labels=align_compact_array_key_labels,
        compact_all_scalar_arrays=compact_all_scalar_arrays,
        parallel_array_groups=groups,
        column_widths_by_path=None,
    )


def _json_compact_pretty(
    value,
    indent: int,
    level: int,
    compact_list_min_items: int,
    compact_array_paths: list[tuple],
    current_path: tuple,
    align_object_values: bool,
    align_compact_array_items: bool,
    align_compact_array_key_labels: bool,
    compact_all_scalar_arrays: bool,
    parallel_array_groups: list[tuple[str, ...]],
    column_widths_by_path: dict | None = None,
):
    current_indent = " " * (indent * level)
    next_indent = " " * (indent * (level + 1))

    if isinstance(value, dict):
        if not value:
            return "{}"
        key_text_by_key = {
            key: json.dumps(str(key), ensure_ascii=False)
            for key in value.keys()
        }
        max_key_len = max((len(v) for v in key_text_by_key.values()), default=0)
        compact_keys_for_align = []
        compact_lists_by_key = {}
        for key, item_value in value.items():
            child_path = current_path + (str(key),)
            if (
                isinstance(item_value, list)
                and item_value
                and all(_is_scalar_json_value(item) for item in item_value)
                and (compact_all_scalar_arrays or _path_matches(child_path, compact_array_paths))
            ):
                compact_keys_for_align.append(key)
                compact_lists_by_key[key] = item_value
        max_compact_key_len = max(
            (len(key_text_by_key[key]) for key in compact_keys_for_align),
            default=0,
        )

        local_column_widths_by_key = {}
        if compact_lists_by_key:
            for group in parallel_array_groups:
                group_keys = [key for key in group if key in compact_lists_by_key]
                if len(group_keys) < 2:
                    continue
                max_list_len = max(len(compact_lists_by_key[key]) for key in group_keys)
                widths_by_key = {
                    key: [len(json.dumps(item, ensure_ascii=False)) for item in compact_lists_by_key[key]]
                    for key in group_keys
                }
                for idx in range(max_list_len):
                    max_len = 0
                    present_keys = []
                    for key in group_keys:
                        if idx < len(compact_lists_by_key[key]):
                            present_keys.append(key)
                            token = json.dumps(compact_lists_by_key[key][idx], ensure_ascii=False)
                            if len(token) > max_len:
                                max_len = len(token)
                    for key in present_keys:
                        widths_by_key[key][idx] = max_len
                for key in group_keys:
                    local_column_widths_by_key[key] = widths_by_key[key]

        items = []
        for key, item_value in value.items():
            key_text = key_text_by_key[key]
            child_path = current_path + (str(key),)
            child_column_widths = None
            if key in local_column_widths_by_key:
                child_column_widths = local_column_widths_by_key[key]
            val_text = _json_compact_pretty(
                item_value,
                indent=indent,
                level=level + 1,
                compact_list_min_items=compact_list_min_items,
                compact_array_paths=compact_array_paths,
                current_path=child_path,
                align_object_values=align_object_values,
                align_compact_array_items=align_compact_array_items,
                align_compact_array_key_labels=align_compact_array_key_labels,
                compact_all_scalar_arrays=compact_all_scalar_arrays,
                parallel_array_groups=parallel_array_groups,
                column_widths_by_path={child_path: child_column_widths} if child_column_widths else None,
            )
            if align_object_values:
                pad = " " * (max_key_len - len(key_text))
                items.append(f"{next_indent}{key_text}:{pad} {val_text}")
            elif align_compact_array_key_labels and key in compact_keys_for_align:
                pad = " " * (max_compact_key_len - len(key_text))
                items.append(f"{next_indent}{key_text}:{pad} {val_text}")
            else:
                items.append(f"{next_indent}{key_text}: {val_text}")
        return "{\n" + ",\n".join(items) + f"\n{current_indent}" + "}"

    if isinstance(value, list):
        if not value:
            return "[]"
        all_scalar = all(_is_scalar_json_value(item) for item in value)
        force_compact = compact_all_scalar_arrays or _path_matches(current_path, compact_array_paths)
        if all_scalar and (force_compact or len(value) >= compact_list_min_items):
            item_tokens = [json.dumps(item, ensure_ascii=False) for item in value]
            if align_compact_array_items and item_tokens:
                external_widths = None
                if column_widths_by_path and current_path in column_widths_by_path:
                    external_widths = column_widths_by_path[current_path]
                if external_widths and len(external_widths) == len(item_tokens):
                    item_tokens = [
                        token.ljust(external_widths[idx])
                        for idx, token in enumerate(item_tokens)
                    ]
                else:
                    width = max(len(token) for token in item_tokens)
                    item_tokens = [token.ljust(width) for token in item_tokens]
            return "[" + ", ".join(item_tokens) + "]"
        items = [
            f"{next_indent}{_json_compact_pretty(item, indent=indent, level=level + 1, compact_list_min_items=compact_list_min_items, compact_array_paths=compact_array_paths, current_path=current_path + (idx,), align_object_values=align_object_values, align_compact_array_items=align_compact_array_items, align_compact_array_key_labels=align_compact_array_key_labels, compact_all_scalar_arrays=compact_all_scalar_arrays, parallel_array_groups=parallel_array_groups, column_widths_by_path=None)}"
            for idx, item in enumerate(value)
        ]
        return "[\n" + ",\n".join(items) + f"\n{current_indent}]"

    return json.dumps(value, ensure_ascii=False)


def _is_scalar_json_value(value) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _path_matches(path: tuple, patterns: list[tuple]) -> bool:
    for pattern in patterns:
        if len(pattern) != len(path):
            continue
        matched = True
        for pseg, seg in zip(pattern, path):
            if pseg == "*":
                continue
            if pseg != seg:
                matched = False
                break
        if matched:
            return True
    return False


