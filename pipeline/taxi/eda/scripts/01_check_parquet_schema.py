import json
import pyarrow.parquet as pq
from pipeline.services.helpers import extract_month
from pipeline.services.paths import TAXI_DIR, TAXI_RAW_TEMP_DIR


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "01_check_parquet_schema.json"


def main(conn):

    link_parquet_files = sorted(
        TAXI_RAW_TEMP_DIR.glob("yellow_tripdata_2019-*.parquet"), # Get all parquet files matching the pattern yellow_tripdata_2019-*.parquet
        key=extract_month, # Sort files by month number (e.g. 1 for 01, 2 for 02, etc.) to have a consistent order
    )

    if not link_parquet_files:
        print(f"INFO: No parquet files found in {TAXI_RAW_TEMP_DIR}. Skipping parquet schema check.")
        return

    file_and_columns_types = {}
    files_mismatches = []

    for link_parquet_file in link_parquet_files:
        parquet_file_obj = pq.ParquetFile(link_parquet_file) # Open the parquet file to read its schema
        schema = parquet_file_obj.schema_arrow # Get the Arrow schema of the parquet file, which contains column names and types
        file_and_columns_types[link_parquet_file.name] = {
            field.name: str(field.type) for field in schema # Create a dictionary mapping column names to their types as strings for the current parquet file
        }

    reference_file = link_parquet_files[0].name
    reference_columns_types = file_and_columns_types[reference_file]
    escaped_path = link_parquet_files[0].as_posix().replace("'", "''")
    rows = conn.execute(
        f"""
        DESCRIBE
        SELECT *
        FROM read_parquet('{escaped_path}')
        """
    ).fetchall()
    database_columns_types = {str(row[0]): str(row[1]) for row in rows}
    reference_pairs = set(reference_columns_types.items())
    all_match = True

    # Compare only key:value pairs (column_name -> type).
    for file_name, columns_types in file_and_columns_types.items():
        if file_name == reference_file: # Skip comparing the reference file with itself
            continue

        current_pairs = set(columns_types.items())
        if current_pairs == reference_pairs:
            continue

        all_match = False
        missing_pairs = sorted(reference_pairs - current_pairs, key=lambda item: item[0])
        extra_pairs = sorted(current_pairs - reference_pairs, key=lambda item: item[0])
        missing_columns_types_pairs = {}
        for column_name, column_type in missing_pairs:
            missing_columns_types_pairs[str(column_name)] = str(column_type)

        extra_columns_types_pairs = {}
        for column_name, column_type in extra_pairs:
            extra_columns_types_pairs[str(column_name)] = str(column_type)

        file_mismatches = {
            "missing": missing_columns_types_pairs,
            "extra": extra_columns_types_pairs,
        }

        files_mismatches.append(
            {
                "file_name": file_name,
                "file_mismatches": file_mismatches,
            }
        )

    report = {
        "input_directory": TAXI_RAW_TEMP_DIR.as_posix(),
        "parquet_files": [link_parquet_file.name for link_parquet_file in link_parquet_files],
        "reference_file": reference_file,
        "column_count": len(reference_columns_types),
        "all_match": all_match,
        "reference_columns_types": reference_columns_types,
        "database_columns_types": database_columns_types,
        "files_mismatches": files_mismatches,
    }
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")
