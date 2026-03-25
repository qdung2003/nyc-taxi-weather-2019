import csv
import json
from datetime import datetime
from pathlib import Path


weather_root = Path(__file__).resolve().parents[2]
input_file = weather_root / "raw" / "NYC_Central_Park_weather_1869-2022.csv"
output_dir = weather_root / "etl" / "results"
output_file = output_dir / "01_weather_2019.csv"
metadata_file = output_dir / "01_basic_info.json"


def to_posix(path: Path) -> str:
    return path.as_posix()


kept_row_quantity = 0
invalid_date_quantity = 0
columns = []

output_dir.mkdir(parents=True, exist_ok=True)

with input_file.open("r", encoding="utf-8", newline="") as src, output_file.open(
    "w", encoding="utf-8", newline=""
) as dst:
    reader = csv.DictReader(src)
    columns = reader.fieldnames or []
    writer = csv.DictWriter(dst, fieldnames=columns)
    writer.writeheader()

    for row in reader:
        date_value = row["DATE"]

        try:
            parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            invalid_date_quantity += 1
            continue

        if parsed_date.year == 2019:
            writer.writerow(row)
            kept_row_quantity += 1


metadata_report = {
    "input_file": to_posix(input_file),
    "output_file": to_posix(output_file),
    "row_count": kept_row_quantity,
    "column_count": len(columns),
    "columns": columns,
    "invalid_date_row_count": invalid_date_quantity,
}

metadata_file.write_text(
    json.dumps(metadata_report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"Created: {output_file}")
print(f"Saved metadata: {metadata_file}")
print(f"Rows written: {kept_row_quantity}")
print(f"Invalid DATE rows skipped: {invalid_date_quantity}")
