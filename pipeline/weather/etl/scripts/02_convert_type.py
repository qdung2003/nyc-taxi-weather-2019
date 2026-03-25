import json
from pathlib import Path
import pandas as pd


# ===== PATH SETUP =====
weather_root = Path(__file__).resolve().parents[2]

input_file = weather_root / "etl" / "results" / "01_weather_2019.csv"
metadata_file = weather_root / "eda" / "results" / "01_view_type_value.json"
output_file = weather_root / "etl" / "results" / "02_convert_type.parquet"

print(f"Input file: {input_file}")
print(f"Metadata file: {metadata_file}")
print(f"Output file: {output_file}")


# ===== CHECK FILE EXIST =====
if not input_file.exists():
    raise FileNotFoundError(f"Input file not found: {input_file}")

if not metadata_file.exists():
    print(f"Warning: Metadata file not found: {metadata_file}")
    print("👉 Continue without metadata...")
    column_types = []
else:
    with metadata_file.open("r", encoding="utf-8") as f:
        column_types = json.load(f)


# ===== READ DATA =====
df = pd.read_csv(input_file, encoding="utf-8")
total_rows = len(df)

print(f"\nTotal rows: {total_rows}")


# ===== TYPE CONVERSION =====

# DATE → chỉ giữ ngày (không time)
if "DATE" in df.columns:
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce").dt.date


# Helper convert an toàn
def safe_convert(series, dtype):
    return pd.to_numeric(series, errors="coerce").astype(dtype)


# Integer columns
for col in ["TMIN", "TMAX"]:
    if col in df.columns:
        df[col] = safe_convert(df[col], "Int32")  # nullable int


# Float columns
for col in ["PRCP", "SNOW", "SNWD"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")


# ===== SAVE PARQUET =====
output_file.parent.mkdir(parents=True, exist_ok=True)

df.to_parquet(output_file, index=False, engine="pyarrow")


# ===== SUMMARY =====
print("\n===== SUMMARY =====")
print(df.dtypes)
print(f"\nSaved to: {output_file}")
print(f"File size: {output_file.stat().st_size / 1024:.2f} KB")