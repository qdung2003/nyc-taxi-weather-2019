from tqdm import tqdm
from pipeline.services.helpers import reset_csv_dir, write_high_unique_csvs, write_low_unique_csvs, write_metadata_csv
from pipeline.services.queries import (
    build_low_unique_columns,
    calculate_valid_type_percentages,
    count_limited_unique_values,
    ensure_table_exists,
    quote_identifier,
    run_with_conn,
)
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR, WAREHOUSE_DB_FILE
from pipeline.constants.unique_settings import MAX_UNIQUE_VALUES
from pipeline.constants.modules import ETL02_INGEST


output_file = TAXI_EDA_RESULTS_DIR / "02_low_duplicates"
TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def main(conn):
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)
    taxi_raw_quoted = quote_identifier(TABLE_TAXI_RAW)

    row_count = conn.execute(
        f"SELECT count(*) FROM {taxi_raw_quoted}"
    ).fetchone()[0]

    column_type_rows = conn.execute(f"DESCRIBE {taxi_raw_quoted}").fetchall()
    column_names = [row[0] for row in column_type_rows]
    data_types = [str(row[1]) for row in column_type_rows]
    
    print(f"Input table: {TABLE_TAXI_RAW}")
    print(f"Total rows: {row_count:,}")
    print("Phase 1/3: Computing unique_count per column...")

    unique_counts = []
    for column_name in tqdm(column_names, desc="Phase 1 unique_count", unit="col", leave=True):
        column_name_quoted = quote_identifier(column_name)
        unique_counts.append(
            count_limited_unique_values(
                conn,
                taxi_raw_quoted,
                column_name_quoted,
                MAX_UNIQUE_VALUES,
            )
        )


    low_cardinality_column_names = []
    low_cardinality_data_types = []
    high_cardinality_column_names = []
    high_cardinality_data_types = []


    for column_name, data_type, unique_count in zip(column_names, data_types, unique_counts):
        if unique_count <= MAX_UNIQUE_VALUES:
            low_cardinality_column_names.append(column_name)
            low_cardinality_data_types.append(data_type)
        else:
            high_cardinality_column_names.append(column_name)
            high_cardinality_data_types.append(data_type)


    print(
        "Phase 2/3: Counting values for low-cardinality columns "
        f"({len(low_cardinality_column_names)}/{len(column_names)})..."
    )
    
    low_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        taxi_raw_quoted,
        low_cardinality_column_names,
        low_cardinality_data_types,
        row_count,
    )
    low_unique_columns = build_low_unique_columns(
        conn,
        taxi_raw_quoted,
        low_cardinality_column_names,
        low_cardinality_data_types,
        low_valid_type_percentages,
        row_count,
    )


    high_unique_columns = []
    
    if high_cardinality_column_names:
        high_valid_type_percentages = calculate_valid_type_percentages(
            conn,
            taxi_raw_quoted,
            high_cardinality_column_names,
            high_cardinality_data_types,
            row_count,
        )

        for column_name, data_type, valid_type_percent in zip(
            high_cardinality_column_names,
            high_cardinality_data_types,
            high_valid_type_percentages,
        ):
            high_unique_columns.append(
                {
                    "column_name": column_name,
                    "data_type": data_type,
                    "valid_type_percent": valid_type_percent,
                }
            )


    print("Phase 3/3: Writing CSV tables...")
    reset_csv_dir(output_file)
    write_metadata_csv(
        output_file,
        {
            "warehouse_database_path": WAREHOUSE_DB_FILE.as_posix(),
            "table": TABLE_TAXI_RAW,
            "row_count": row_count,
            "max_unique_values": MAX_UNIQUE_VALUES,
            "low_unique_column_count": len(low_unique_columns),
            "high_unique_column_count": len(high_unique_columns),
        },
    )
    write_low_unique_csvs(output_file, low_unique_columns)
    write_high_unique_csvs(output_file, high_unique_columns)
    print(f"EDA 02 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)











