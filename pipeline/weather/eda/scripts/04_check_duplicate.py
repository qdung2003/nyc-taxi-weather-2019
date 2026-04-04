# -*- coding: utf-8 -*-
import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


weather_root = Path(__file__).resolve().parents[2]
input_file = weather_root / "etl" / "results" / "02_convert_type.parquet"
max_unique_values = 300
output_dir = weather_root / "eda" / "results"
output_file = output_dir / "04_check_duplicate.json"


def to_posix(path: Path) -> str:
    return path.as_posix()


def round_if_needed(value):
    if isinstance(value, float):
        rounded = round(value, 2)
        if rounded != value:
            return rounded
    return value


def is_valid_for_dtype(series_raw: pd.Series, dtype_str: str) -> pd.Series:
    if dtype_str in {"int8", "int16", "int32", "int64", "Int8", "Int16", "Int32", "Int64"}:
        def try_int(v):
            if pd.isna(v) or str(v).strip() == "":
                return False
            try:
                f = float(v)
                return f == int(f)
            except (ValueError, TypeError):
                return False
        return series_raw.map(try_int)

    if dtype_str in {"float16", "float32", "float64"}:
        def try_float(v):
            if pd.isna(v) or str(v).strip() == "":
                return False
            try:
                float(v)
                return True
            except (ValueError, TypeError):
                return False
        return series_raw.map(try_float)

    if "datetime" in dtype_str or dtype_str == "DATE":
        def try_datetime(v):
            if pd.isna(v) or str(v).strip() == "":
                return False
            try:
                pd.to_datetime(v)
                return True
            except (ValueError, TypeError):
                return False
        return series_raw.map(try_datetime)

    return series_raw.notna()


# Read parquet with preserved dtypes
df_typed = pd.read_parquet(input_file)
reference_schema = {
    col: ("DATE" if col == "DATE" else str(df_typed[col].dtype))
    for col in df_typed.columns
}
column_names = list(df_typed.columns)
total_rows = len(df_typed)

# For parquet, use typed data as raw source for validation
df_raw = df_typed.copy()

# Compute valid counts per column
valid_counts = {}
for col in tqdm(column_names, desc="Checking valid type counts"):
    mask = is_valid_for_dtype(df_raw[col], reference_schema[col])
    valid_counts[col] = int(mask.sum())

# Classify columns by cardinality
low_cardinality_column_names = []
high_cardinality_column_names = []

for col in column_names:
    unique_count = df_typed[col].nunique(dropna=False)
    if unique_count <= max_unique_values:
        low_cardinality_column_names.append(col)
    else:
        high_cardinality_column_names.append(col)

# Build low-cardinality details
low_duplicate_columns = []
for col in low_cardinality_column_names:
    vc = df_typed[col].value_counts(dropna=False)
    unique_vals = df_typed[col].unique().tolist()
    sorted_vals = sorted(
        unique_vals,
        key=lambda v: (v is None or (isinstance(v, float) and np.isnan(v)), str(v)),
    )
    vc_dict = vc.to_dict()

    values = []
    quantity = []
    quantity_percent = []
    for v in sorted_vals:
        count = int(vc_dict.get(v, 0))
        safe_v = None if (v is None or (isinstance(v, float) and np.isnan(v))) else round_if_needed(v)
        values.append(safe_v)
        quantity.append(count)
        quantity_percent.append(round_if_needed(count / total_rows * 100 if total_rows else 0))

    low_duplicate_columns.append({
        "column_name": col,
        "type_value": reference_schema[col],
        "unique_count": len(sorted_vals),
        "correct_type_percent": round_if_needed(valid_counts[col] / total_rows * 100 if total_rows else 0),
        "values": values,
        "quantity": quantity,
        "quantity_percent": quantity_percent,
    })

high_duplicate_columns = [
    {
        "column_name": col,
        "type_value": reference_schema[col],
        "correct_type_percent": round_if_needed(valid_counts[col] / total_rows * 100 if total_rows else 0),
    }
    for col in high_cardinality_column_names
]

report = {
    "input_file": to_posix(input_file),
    "row_count": total_rows,
    "column_count": len(column_names),
    "max_unique_values": max_unique_values,
    "low_duplicate_columns": low_duplicate_columns,
    "high_duplicate_columns": high_duplicate_columns,
}

output_dir.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"Saved report: {output_file}")
