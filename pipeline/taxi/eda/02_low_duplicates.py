from tqdm import tqdm
from pipeline.services.helpers import (
    reset_csv_dir,
    write_csv,
)
from pipeline.services.queries import (
    build_low_unique_column_arrays,
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
    
    valid_type_percents = calculate_valid_type_percentages(
        conn,
        taxi_raw_quoted,
        column_names,
        data_types,
        row_count,
    )


    low_unique_column_names = []
    low_unique_data_types = []
    low_unique_unique_counts = []
    low_unique_valid_type_percents = []
    high_unique_column_names = []
    high_unique_data_types = []
    high_unique_valid_type_percents = []


    for column_name, data_type, unique_count, valid_type_percent in zip(
        column_names,
        data_types,
        unique_counts,
        valid_type_percents,
    ):
        if unique_count <= MAX_UNIQUE_VALUES:
            low_unique_column_names.append(column_name)
            low_unique_data_types.append(data_type)
            low_unique_unique_counts.append(unique_count)
            low_unique_valid_type_percents.append(valid_type_percent)
        else:
            high_unique_column_names.append(column_name)
            high_unique_data_types.append(data_type)
            high_unique_valid_type_percents.append(valid_type_percent)


    print(
        "Phase 2/3: Counting values for low-cardinality columns "
        f"({len(low_unique_column_names)}/{len(column_names)})..."
    )

    reset_csv_dir(output_file)
    (
        low_unique_array_column_names,
        low_unique_array_values,
        low_unique_array_counts,
        low_unique_array_percentages,
    ) = build_low_unique_column_arrays(
        conn,
        taxi_raw_quoted,
        low_unique_column_names,
        row_count,
    )

    print("Phase 3/3: Writing CSV tables...")
    write_csv(
        output_file,
        ["metadata", "low_unique_columns", "low_unique_column_arrays", "high_unique_columns"],
        [(
            ["key", "value"],
            [
                [
                    "warehouse_database_path",
                    "table",
                    "row_count",
                    "max_unique_values",
                    "low_unique_column_count",
                    "high_unique_column_count",
                ],
                [
                    WAREHOUSE_DB_FILE.as_posix(),
                    TABLE_TAXI_RAW,
                    row_count,
                    MAX_UNIQUE_VALUES,
                    len(low_unique_column_names),
                    len(high_unique_column_names),
                ],
            ],
        ),
        (
            ["column_name", "data_type", "unique_count", "valid_type_percent"],
            [
                low_unique_column_names,
                low_unique_data_types,
                low_unique_unique_counts,
                low_unique_valid_type_percents,
            ],
        ),
        (
            ["column_name", "value", "count", "percentage"],
            [
                low_unique_array_column_names,
                low_unique_array_values,
                low_unique_array_counts,
                low_unique_array_percentages,
            ],
        ),
        (
            ["column_name", "data_type", "valid_type_percent"],
            [
                high_unique_column_names,
                high_unique_data_types,
                high_unique_valid_type_percents,
            ],
        ),
        ],
    )
    print(f"EDA 02 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)




