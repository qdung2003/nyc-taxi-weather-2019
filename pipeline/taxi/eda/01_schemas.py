import pyarrow.parquet as pq
from pipeline.constants.modules import DOWNLOAD_YELLOW_TRIPDATA
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR, TAXI_RAW_TEMP_DIR
from pipeline.services.helpers import (
    extract_month,
    is_schema_type_match,
    reset_csv_dir,
    write_csv,
)
from pipeline.services.queries import run_with_conn


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_dir = TAXI_EDA_RESULTS_DIR / "01_schemas"


def main(conn):
    link_parquet_files = sorted(
        DOWNLOAD_YELLOW_TRIPDATA.ensure_taxi_raw_files(),
        key=extract_month,
    )

    mismatch_files = []
    mismatches = []
    mismatch_column_names = []
    mismatch_parquet_types = []

    reference_parquet_link = link_parquet_files[0]
    reference_parquet_file = reference_parquet_link.name
    reference_schema = pq.ParquetFile(reference_parquet_link).schema_arrow
    column_names = [field.name for field in reference_schema]
    parquet_types = [str(field.type) for field in reference_schema]

    escaped_path = reference_parquet_link.as_posix().replace("'", "''")
    rows = conn.execute(
        f"""
        DESCRIBE
        SELECT *
        FROM read_parquet('{escaped_path}')
        """
    ).fetchall()
    database_types = [str(row[1]) for row in rows]

    reference_pairs = set(zip(column_names, parquet_types))
    all_match = True

    for link_parquet_file in link_parquet_files:
        if link_parquet_file.name == reference_parquet_file:
            continue

        current_schema = pq.ParquetFile(link_parquet_file).schema_arrow
        current_column_names = [field.name for field in current_schema]
        current_parquet_types = [str(field.type) for field in current_schema]
        current_pairs = set(zip(current_column_names, current_parquet_types))
        if current_pairs == reference_pairs:
            continue

        all_match = False
        missing_pairs = sorted(reference_pairs - current_pairs, key=lambda item: item[0])
        extra_pairs = sorted(current_pairs - reference_pairs, key=lambda item: item[0])

        for column_name, column_type in missing_pairs:
            mismatch_files.append(link_parquet_file.name)
            mismatches.append("missing")
            mismatch_column_names.append(column_name)
            mismatch_parquet_types.append(column_type)
        for column_name, column_type in extra_pairs:
            mismatch_files.append(link_parquet_file.name)
            mismatches.append("extra")
            mismatch_column_names.append(column_name)
            mismatch_parquet_types.append(column_type)

    reset_csv_dir(output_dir)
    write_csv(
        output_dir,
        ["metadata", "files", "schema", "mismatches"],
        [
            (
                ["key", "value"],
                [
                    ["files_directory", "file_count", "reference_file", "column_count", "all_match"],
                    [
                        TAXI_RAW_TEMP_DIR.as_posix(),
                        len(link_parquet_files),
                        reference_parquet_file,
                        len(column_names),
                        "yes" if all_match else "no",
                    ],
                ],
            ),
            (
                ["index", "file"],
                [
                    [extract_month(link_parquet_file) for link_parquet_file in link_parquet_files],
                    [link_parquet_file.name for link_parquet_file in link_parquet_files],
                ],
            ),
            (
                ["column_name", "parquet_type", "database_type", "match"],
                [
                    column_names,
                    parquet_types,
                    database_types,
                    [
                        "yes" if is_schema_type_match(parquet_type, database_type) else "no"
                        for parquet_type, database_type in zip(parquet_types, database_types)
                    ],
                ],
            ),
            (
                ["file", "mismatch", "column_name", "parquet_type"],
                [
                    mismatch_files,
                    mismatches,
                    mismatch_column_names,
                    mismatch_parquet_types,
                ],
            ),
        ],
    )
    print(f"EDA 01 saved: {output_dir.name}")


if __name__ == "__main__":
    run_with_conn(main)
