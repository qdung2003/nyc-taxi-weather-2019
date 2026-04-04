# -*- coding: utf-8 -*-
import json
import pandas as pd
from pathlib import Path


weather_root = Path(__file__).resolve().parents[2]
input_file = weather_root / "etl" / "results" / "01_get_weather_2019.csv"
output_dir = weather_root / "eda" / "results"
output_file = output_dir / "02_check_date.json"


def to_posix(path: Path) -> str:
    return path.as_posix()


# Read the CSV with DATE parsed
df = pd.read_csv(input_file, parse_dates=["DATE"])
total_rows = len(df)
column_name = "DATE"

# Analysis
unique_dates = df[column_name].dt.date.unique()
unique_count = len(unique_dates)
min_date = min(unique_dates)
max_date = max(unique_dates)

# Check for full year 2019 (365 days)
is_full_year = (
    unique_count == 365 and
    min_date.year == 2019 and
    max_date.year == 2019 and
    min_date.month == 1 and
    min_date.day == 1 and
    max_date.month == 12 and
    max_date.day == 31
)

# Check for uniqueness (no duplicates)
is_unique = (unique_count == total_rows)

report = {
    "input_file": to_posix(input_file),
    "date_dimension_check": {
        "column_name": column_name,
        "total_rows": total_rows,
        "unique_count": unique_count,
        "min_date": min_date.strftime("%Y-%m-%d"),
        "max_date": max_date.strftime("%Y-%m-%d"),
        "is_unique": "yes" if is_unique else "no",
        "full_year": "yes" if is_full_year else "no"
    }
}

output_dir.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"Saved report: {output_file}")
