import json
from decimal import Decimal
from pathlib import Path



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
