import json
from pathlib import Path

import pyarrow.parquet as pq


taxi_root = Path(__file__).resolve().parents[2]
input_dir = taxi_root / "raw"
parquet_files = sorted(input_dir.glob("yellow_tripdata_2019-*.parquet"))
output_dir = taxi_root / "eda" / "results"
output_file = output_dir / "01_check_parquet_schema.json"


def to_posix(path: Path) -> str:
    return path.as_posix()


schemas_by_file = {}
type_maps_by_file = {}
name_order_mismatches = []
type_mismatches = []

for parquet_file in parquet_files:
    parquet = pq.ParquetFile(parquet_file)
    schema = parquet.schema_arrow
    column_names = schema.names
    schemas_by_file[parquet_file.name] = column_names
    type_maps_by_file[parquet_file.name] = {
        field.name: str(field.type) for field in schema
    }

reference_file = parquet_files[0].name if parquet_files else None
reference_schema = schemas_by_file.get(reference_file, [])
reference_type_map = type_maps_by_file.get(reference_file, {})
all_match = True

for file_name, schema in schemas_by_file.items():
    if schema != reference_schema:
        all_match = False
        missing_columns = [column for column in reference_schema if column not in schema]
        extra_columns = [column for column in schema if column not in reference_schema]
        name_order_mismatches.append(
            {
                "file_name": file_name,
                "missing_columns": missing_columns,
                "extra_columns": extra_columns,
            }
        )

for file_name, type_map in type_maps_by_file.items():
    if file_name == reference_file:
        continue

    current_type_mismatches = []

    for column_name in reference_schema:
        if column_name not in type_map:
            continue

        reference_type = reference_type_map.get(column_name)
        current_type = type_map.get(column_name)

        if current_type != reference_type:
            current_type_mismatches.append(
                {
                    "column_name": column_name,
                    "reference_type": reference_type,
                    "current_type": current_type,
                }
            )

    if current_type_mismatches:
        all_match = False
        type_mismatches.append(
            {
                "file_name": file_name,
                "columns": current_type_mismatches,
            }
        )

report = {
    "input_directory": to_posix(input_dir),
    "parquet_files": [parquet_file.name for parquet_file in parquet_files],
    "reference_file": reference_file,
    "column_count": len(reference_schema),
    "all_match": all_match,
    "reference_schema": {
        column_name: reference_type_map.get(column_name)
        for column_name in reference_schema
    },
    "name_order_mismatches": name_order_mismatches,
    "type_mismatches": type_mismatches,
}

output_dir.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"Saved report: {output_file}")

