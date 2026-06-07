import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any



# support calculate
def extract_month(path: Path) -> int:
    name = path.stem # e.g. yellow_tripdata_2019-01 from path/to/yellow_tripdata_2019-01.parquet
    month_str = name.split("-")[-1] # e.g. 01 from yellow_tripdata_2019-01
    return int(month_str) # e.g. 1 from 01


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


def is_schema_type_match(parquet_type: str | None, database_type: str | None) -> bool:
    parquet_type = str(parquet_type or "").strip().upper()
    database_type = str(database_type or "").strip().upper()
    if not parquet_type or not database_type:
        return False

    parquet_to_database_candidates = {
        "INT64": {"BIGINT", "INTEGER", "INT", "INT8"},
        "DOUBLE": {"DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC"},
        "STRING": {"VARCHAR", "TEXT", "STRING"},
        "DATE32[DAY]": {"DATE"},
        "TIMESTAMP[US]": {"TIMESTAMP", "DATETIME"},
        "BOOLEAN": {"BOOLEAN", "BOOL"},
    }
    candidates = parquet_to_database_candidates.get(parquet_type)
    if candidates is None:
        return parquet_type == database_type
    return any(
        database_type == candidate or database_type.startswith(f"{candidate}(")
        for candidate in candidates
    )


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


def write_csv(path: Path, rows: list[dict[str, Any]], *, preserve_header_underscores: bool = True) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ordered_fieldnames(rows)
    output_fieldnames = (
        fieldnames
        if preserve_header_underscores
        else [fieldname.replace("_", " ") for fieldname in fieldnames]
    )
    output_rows = [
        {
            output_fieldname: "null" if fieldname in row and row[fieldname] is None else row.get(fieldname)
            for fieldname, output_fieldname in zip(fieldnames, output_fieldnames)
        }
        for row in rows
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)


def reset_csv_dir(path: Path) -> None:
    import shutil

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_metadata_csv(
    output_dir: Path,
    metadata: dict[str, Any] | None = None,
    *,
    keys: list[str] | None = None,
    values: list[Any] | None = None,
) -> None:
    if metadata is not None:
        keys = list(metadata.keys())
        values = list(metadata.values())
    if keys is None or values is None:
        raise ValueError("write_metadata_csv requires either metadata or both keys and values")
    if len(keys) != len(values):
        raise ValueError("write_metadata_csv keys and values must have the same length")

    rows = [
        {
            "key": key,
            "value": ("yes" if value else "no") if isinstance(value, bool) else value,
        }
        for key, value in zip(keys, values)
    ]
    write_csv(output_dir / "metadata.csv", rows, preserve_header_underscores=True)


def write_key_value_csv(output_dir: Path, name: str, values: dict[str, Any]) -> None:
    write_csv(
        output_dir / f"{name}.csv",
        [{"key": key, "value": value} for key, value in values.items()],
    )


def write_low_unique_csvs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    columns = []
    value_rows = []
    for row in rows:
        column_name = row.get("column_name")
        columns.append(
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {"values", "counts", "percentages"}
                },
            }
        )
        for value, count, percentage_value in zip(
            row.get("values", []),
            row.get("counts", []),
            row.get("percentages", []),
        ):
            value_rows.append(
                {
                    "column_name": column_name,
                    "value": value,
                    "count": count,
                    "percentage": percentage_value,
                }
            )
    write_csv(output_dir / "low_unique_columns.csv", columns)
    write_csv(output_dir / "low_unique_columns_array.csv", value_rows)


def write_high_unique_csvs(
    output_dir: Path,
    rows: list[dict[str, Any]],
    *,
    base_name: str = "high_unique",
) -> None:
    simple_rows = []
    datetime_rows = []
    datetime_array_rows = []
    numeric_rows = []
    numeric_array_rows = []

    for row in rows:
        column_name = row.get("column_name")
        common = {
            **{
                key: value
                for key, value in row.items()
                if key not in {
                    "month_counts",
                    "month_percentages",
                    "bin_edges",
                    "bin_counts",
                    "bin_percentages",
                    "filter",
                }
            },
        }
        filter_values = row.get("filter")
        if isinstance(filter_values, dict):
            for key, value in filter_values.items():
                common[key] = value

        if row.get("month_counts") or row.get("month_percentages"):
            datetime_rows.append(common)
            for month, (month_count, month_percentage) in enumerate(
                zip(row.get("month_counts", []), row.get("month_percentages", [])),
                start=1,
            ):
                datetime_array_rows.append(
                    {
                        "column_name": column_name,
                        "month": month,
                        "month_count": month_count,
                        "month_percentage": month_percentage,
                    }
                )
        elif row.get("bin_edges") or row.get("bin_counts") or row.get("bin_percentages"):
            numeric_rows.append(common)
            for bin_edge, bin_count, bin_percentage in zip(
                row.get("bin_edges", []),
                row.get("bin_counts", []),
                row.get("bin_percentages", []),
            ):
                numeric_array_row = {
                    "column_name": column_name,
                    "bin_edge": bin_edge,
                    "bin_count": bin_count,
                    "bin_percentage": bin_percentage,
                }
                numeric_array_rows.append(numeric_array_row)
        else:
            simple_rows.append(common)

    if simple_rows:
        write_csv(output_dir / f"{base_name}_columns.csv", simple_rows)
    if datetime_rows:
        write_csv(output_dir / f"{base_name}_columns_datetime.csv", datetime_rows)
        write_csv(output_dir / f"{base_name}_columns_datetime_array.csv", datetime_array_rows)
    if numeric_rows:
        write_csv(output_dir / f"{base_name}_columns_numeric.csv", numeric_rows)
        write_csv(output_dir / f"{base_name}_columns_numeric_array.csv", numeric_array_rows)


# format json
def write_json_compact(
    output_path: Path,
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
) -> None:
    text = dumps_json_compact(
        payload,
        indent=indent,
        compact_list_min_items=compact_list_min_items,
        compact_array_paths=compact_array_paths,
        align_object_values=align_object_values,
        align_compact_array_items=align_compact_array_items,
        align_compact_array_key_labels=align_compact_array_key_labels,
        compact_all_scalar_arrays=compact_all_scalar_arrays,
        parallel_array_groups=parallel_array_groups,
    )
    output_path.write_text(text + "\n", encoding="utf-8")


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


