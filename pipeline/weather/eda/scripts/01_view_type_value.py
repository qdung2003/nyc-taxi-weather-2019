import csv
import json
from pathlib import Path


weather_root = Path(__file__).resolve().parents[2]
input_file = weather_root / "etl" / "results" / "01_weather_2019.csv"
output_dir = weather_root / "eda" / "results"
output_file = output_dir / "01_view_type_value.json"

output_dir.mkdir(parents=True, exist_ok=True)

# Read CSV and analyze data types
column_stats = {}

with input_file.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    columns = reader.fieldnames or []
    
    # Initialize stats for each column
    for col in columns:
        column_stats[col] = {
            "quantity_int": 0,
            "quantity_float": 0,
            "quantity_different": 0,
            "total": 0,
        }
    
    # Process each row
    for row in reader:
        for col in columns:
            if col == "DATE":
                continue
            
            value = row[col].strip()
            column_stats[col]["total"] += 1
            
            # Try to convert to int
            try:
                int(value)
                column_stats[col]["quantity_int"] += 1
            except ValueError:
                # Try to convert to float
                try:
                    float(value)
                    column_stats[col]["quantity_float"] += 1
                except ValueError:
                    # Neither int nor float
                    column_stats[col]["quantity_different"] += 1

# Create report (exclude DATE column)
report = []
for col in columns:
    if col == "DATE":
        continue
    
    stats = column_stats[col]
    total = stats["total"]
    
    report.append({
        "column_name": col,
        "quantity_int": stats["quantity_int"],
        "quantity_float": stats["quantity_float"],
        "quantity_different": stats["quantity_different"],
        "percent_int": round(stats["quantity_int"] / total * 100, 2) if total > 0 else 0,
        "percent_float": round(stats["quantity_float"] / total * 100, 2) if total > 0 else 0,
        "percent_different": round(stats["quantity_different"] / total * 100, 2) if total > 0 else 0,
    })

# Write to JSON file
output_file.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"Created: {output_file}")
print(f"Analyzed {len(report)} columns")