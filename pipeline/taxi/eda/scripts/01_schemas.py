import pyarrow.parquet as pq
from pipeline.services.helpers import extract_month, write_json_compact
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR, TAXI_RAW_TEMP_DIR
from pipeline.services.queries import run_with_conn
from pipeline.constants.modules import DOWNLOAD_YELLOW_TRIPDATA


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = TAXI_EDA_RESULTS_DIR / "01_schemas.json"


def main(conn):
    link_parquet_files = sorted(
        DOWNLOAD_YELLOW_TRIPDATA.ensure_taxi_raw_files(),
        key=extract_month,
    )

    file_and_columns_types = {}
    files_mismatches = []

    for link_parquet_file in link_parquet_files:
        parquet_file_obj = pq.ParquetFile(link_parquet_file)
        schema = parquet_file_obj.schema_arrow
        file_and_columns_types[link_parquet_file.name] = {
            field.name: str(field.type) for field in schema
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

    for file_name, columns_types in file_and_columns_types.items():
        if file_name == reference_file:
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
        "files_directory": TAXI_RAW_TEMP_DIR.as_posix(),
        "file_count": len(link_parquet_files),
        "files": [link_parquet_file.name for link_parquet_file in link_parquet_files],
        "reference_file": reference_file,
        "column_count": len(reference_columns_types),
        "all_match": all_match,
        "reference_schema": reference_columns_types,
        "database_schema": database_columns_types,
        "files_mismatches": files_mismatches,
    }
    write_json_compact(output_file, report)
    print(f"EDA 01 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)








