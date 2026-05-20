from pipeline.services.helpers import write_json_compact
from pipeline.services.queries import (
    build_high_unique_columns,
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    get_column_groups,
    quote_identifier,
    run_with_conn,
)
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.unique_settings import (
    POSITIVE_BIN_COUNT,
)
from pipeline.constants.modules import ETL02_INGEST


output_file = TAXI_EDA_RESULTS_DIR / "03_high_duplicates.json"
profile_file = TAXI_EDA_RESULTS_DIR / "02_low_duplicates.json"
TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

COMPACT_ARRAY_PATHS = [
    ("high_unique_columns", "*", "month_counts"),
    ("high_unique_columns", "*", "month_percentages"),
    ("high_unique_columns", "*", "bin_edges"),
    ("high_unique_columns", "*", "bin_counts"),
    ("high_unique_columns", "*", "bin_percentages"),
]

def main(conn):
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)
    
    taxi_raw_quoted = quote_identifier(TABLE_TAXI_RAW)
    row_count = int(
        conn.execute(f"SELECT count(*) FROM {taxi_raw_quoted}").fetchone()[0]
        or 0
    )

    column_type_rows = conn.execute(f"DESCRIBE {taxi_raw_quoted}").fetchall()
    column_names = [str(row[0]) for row in column_type_rows]

    _, high_unique_column_names = get_column_groups(
        conn,
        taxi_raw_quoted,
        column_names,
        profile_file=profile_file,
    )
    high_unique_data_types = get_column_data_types(column_type_rows, high_unique_column_names)
    high_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        taxi_raw_quoted,
        high_unique_column_names,
        high_unique_data_types,
        row_count,
    )
    high_unique_columns = build_high_unique_columns(
        conn,
        TABLE_TAXI_RAW,
        high_unique_column_names,
        high_unique_data_types,
        high_unique_valid_type_percentages,
        row_count,
    )
    high_unique_column_count = len(high_unique_columns)

    report = {
        "tail_ratio": "1/101",
        "positive_bin_count": POSITIVE_BIN_COUNT,
        "high_unique_column_count": high_unique_column_count,
        "high_unique_columns": high_unique_columns,
    }
    write_json_compact(
        output_file,
        report,
        compact_array_paths=COMPACT_ARRAY_PATHS,
        align_compact_array_key_labels=True,
        align_compact_array_items=True,
        parallel_array_groups=[
            ("month_counts", "month_percentages"),
            ("bin_edges", "bin_counts", "bin_percentages"),
        ],
    )
    print(f"EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
