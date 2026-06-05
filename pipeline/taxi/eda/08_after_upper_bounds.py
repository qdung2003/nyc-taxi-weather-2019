from pipeline.services.helpers import reset_csv_dir, write_high_unique_csvs, write_low_unique_csvs, write_metadata_csv
from pipeline.services.queries import (
    build_high_unique_columns,
    build_low_unique_columns,
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    get_column_groups,
    quote_identifier,
    run_with_conn,
)

from pipeline.constants.modules import ETL04_UPPER_BOUNDS
from pipeline.constants.tmp_tables import TMP_TAXI04
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = TAXI_EDA_RESULTS_DIR / "08_after_upper_bounds"


def main(conn):
    ensure_table_exists(conn, TMP_TAXI04, ETL04_UPPER_BOUNDS.create_etl04_upper_bounds)
    tmp_taxi04_quoted = quote_identifier(TMP_TAXI04)

    row_count = conn.execute(
        f"SELECT count(*) FROM {tmp_taxi04_quoted}"
    ).fetchone()[0]

    column_type_rows = conn.execute(f"DESCRIBE {tmp_taxi04_quoted}").fetchall()
    column_names = [str(row[0]) for row in column_type_rows]
    low_unique_column_names, high_unique_column_names = get_column_groups(
        conn,
        tmp_taxi04_quoted,
        column_names,
        desc="EDA 08 - detecting column groups",
    )

    low_unique_data_types = get_column_data_types(
        column_type_rows,
        low_unique_column_names,
    )
    low_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        tmp_taxi04_quoted,
        low_unique_column_names,
        low_unique_data_types,
        row_count,
    )
    low_unique_columns = build_low_unique_columns(
        conn,
        tmp_taxi04_quoted,
        low_unique_column_names,
        low_unique_data_types,
        low_unique_valid_type_percentages,
        row_count,
        desc="EDA 08 - value counts",
        leave=False,
    )

    high_unique_data_types = get_column_data_types(
        column_type_rows,
        high_unique_column_names,
    )
    high_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        tmp_taxi04_quoted,
        high_unique_column_names,
        high_unique_data_types,
        row_count,
    )
    high_unique_columns = build_high_unique_columns(
        conn,
        TMP_TAXI04,
        high_unique_column_names,
        high_unique_data_types,
        high_unique_valid_type_percentages,
        row_count,
        desc="EDA 08 - profiling high-duplicate columns",
        temp_prefix="tmp_eda08",
    )

    reset_csv_dir(output_file)
    write_metadata_csv(
        output_file,
        {
            "row_count": row_count,
            "low_unique_column_count": len(low_unique_columns),
            "high_unique_column_count": len(high_unique_columns),
        },
    )
    write_low_unique_csvs(output_file, low_unique_columns)
    write_high_unique_csvs(output_file, high_unique_columns)
    print(f"EDA 08 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)



