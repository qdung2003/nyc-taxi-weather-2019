# -*- coding: utf-8 -*-
from pathlib import Path

import pandas as pd


# ===== PATH SETUP =====
weather_root = Path(__file__).resolve().parents[2]

input_file = weather_root / "etl" / "results" / "01_get_weather_2019.csv"
output_file_1 = weather_root / "etl" / "results" / "02_convert_type.parquet"
output_file_2 = weather_root / "clean" / "cleaned_weather_2019.parquet"


print(f"Input file: {input_file}")
print(f"Output file (Results): {output_file_1}")
print(f"Output file (Clean): {output_file_2}")



# ===== CHECK FILE EXIST =====
if not input_file.exists():
    raise FileNotFoundError(f"Input file not found: {input_file}")


# ===== READ DATA =====
df = pd.read_csv(input_file, encoding="utf-8")
total_rows = len(df)

print(f"\nTotal rows: {total_rows}")


# ===== CLEAN + UNIT CONVERSION =====
metric_cols = ["PRCP", "SNOW", "SNWD", "TMIN", "TMAX"]
present_metrics = [c for c in metric_cols if c in df.columns]

# Parse numeric columns from CSV text
for col in present_metrics:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Drop rows with missing required metric values
before_drop_na = len(df)
if present_metrics:
    df = df.dropna(subset=present_metrics)
after_drop_na = len(df)

# Rule 1: PRCP, SNOW, SNWD >= 0
if {"PRCP", "SNOW", "SNWD"}.issubset(df.columns):
    df = df[(df["PRCP"] >= 0) & (df["SNOW"] >= 0) & (df["SNWD"] >= 0)]

# Rule 2: TMIN, TMAX > -459.67 (Fahrenheit absolute-zero check)
if {"TMIN", "TMAX"}.issubset(df.columns):
    df = df[(df["TMIN"] > -459.67) & (df["TMAX"] > -459.67)]

# Unit conversion:
# 1) PRCP, SNOW, SNWD: inch -> cm
for col in ["PRCP", "SNOW", "SNWD"]:
    if col in df.columns:
        df[col] = df[col] * 2.54

# 2) TMIN, TMAX: Fahrenheit -> Celsius
for col in ["TMIN", "TMAX"]:
    if col in df.columns:
        df[col] = (df[col] - 32.0) * 5.0 / 9.0

# Round all weather metrics to 2 decimal places
for col in ["PRCP", "SNOW", "SNWD", "TMIN", "TMAX"]:
    if col in df.columns:
        df[col] = df[col].round(2)

rows_after_rules = len(df)
rows_dropped_by_missing = before_drop_na - after_drop_na
rows_dropped_by_rules = after_drop_na - rows_after_rules


# ===== TYPE CONVERSION =====
# DATE only keeps date part
if "DATE" in df.columns:
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce").dt.date

for col in present_metrics:
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")


# ===== SAVE FILES =====
output_file_1.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(output_file_1, index=False, engine="pyarrow")

output_file_2.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(output_file_2, index=False, engine="pyarrow")


# ===== SUMMARY =====
print("\n===== SUMMARY =====")
print(df.dtypes)
print(f"\nRows dropped due to missing metrics: {rows_dropped_by_missing}")
print(f"Rows dropped by clean rules: {rows_dropped_by_rules}")
print(f"\nSaved Results to: {output_file_1}")
print(f"Saved Clean to: {output_file_2}")
print(f"File size: {output_file_2.stat().st_size / 1024:.2f} KB")
