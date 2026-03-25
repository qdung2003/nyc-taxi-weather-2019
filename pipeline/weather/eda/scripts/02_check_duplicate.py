import json
from pathlib import Path
import pandas as pd
import numpy as np


weather_root = Path(__file__).resolve().parents[2]
input_file = weather_root / "etl" / "results" / "02_convert_type.parquet"
output_dir = weather_root / "eda" / "results"
output_file = output_dir / "02_check_duplicate.json"

output_dir.mkdir(parents=True, exist_ok=True)


def convert_to_json_serializable(value):
    """Convert numpy/pandas types to JSON-serializable Python types"""
    if pd.isna(value):
        return None
    elif isinstance(value, (np.integer, int)):
        return int(value)
    elif isinstance(value, (np.floating, float)):
        return float(value)
    else:
        return str(value)


try:
    # Read parquet file
    df = pd.read_parquet(input_file)
    total_rows = len(df)
    
    report = []
    
    for col in df.columns:
        # Get unique values and their counts
        value_counts = df[col].value_counts().sort_index()
        unique_count = len(value_counts)
        
        # Prepare arrays
        values = [convert_to_json_serializable(v) for v in value_counts.index]
        quantities = [int(q) for q in value_counts.values]
        quantities_percent = [round(float(p), 2) for p in (value_counts.values / total_rows * 100)]
        
        # Get data type
        type_value = str(df[col].dtype)
        
        report.append({
            "column_name": col,
            "type_value": type_value,
            "unique_count": unique_count,
            "values": values,
            "quantity": quantities,
            "quantity_percent": quantities_percent
        })
    
    # Write to JSON file
    output_file.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    
    print(f"Read: {input_file}")
    print(f"Total rows: {total_rows}")
    print(f"Analyzed {len(report)} columns")
    print(f"\nSaved to: {output_file}")

except FileNotFoundError as fe:
    print(f"File not found: {fe}")
except Exception as e:
    print(f"Unexpected error: {e}")
