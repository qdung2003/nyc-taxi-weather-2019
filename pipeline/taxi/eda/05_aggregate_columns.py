from tqdm import tqdm
from pipeline.constants.modules import ETL03_AGGREGATE
from pipeline.constants.columns import AGGREGATE_COLUMNS
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tmp_tables import TMP_TAXI03
from pipeline.services.helpers import (
    reset_csv_dir,
    write_aggregate_columns_csvs,
    write_csv,
)
from pipeline.services.queries import (
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    profile_high_unique_column,
    quote_identifier,
    run_with_conn,
)


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = TAXI_EDA_RESULTS_DIR / "05_aggregate_columns"


def main(conn):
    ensure_table_exists(conn, TMP_TAXI03, ETL03_AGGREGATE.create_etl03_add_aggregate_columns)
    tmp_taxi03_quoted = quote_identifier(TMP_TAXI03)

    row_count = int(
        conn.execute(f"SELECT count(*) FROM {tmp_taxi03_quoted}").fetchone()[0]
        or 0
    )
    column_type_rows = conn.execute(f"DESCRIBE {tmp_taxi03_quoted}").fetchall()
    column_names = [
        str(row[0])
        for row in column_type_rows
        if str(row[0]) in AGGREGATE_COLUMNS
    ]
    data_types = get_column_data_types(column_type_rows, column_names)
    valid_type_percentages = calculate_valid_type_percentages(
        conn,
        tmp_taxi03_quoted,
        column_names,
        data_types,
        row_count,
    )
    aggregate_columns = [
        profile_high_unique_column(
            conn,
            TMP_TAXI03,
            column_name,
            data_type,
            valid_type_percent,
            row_count,
            temp_prefix="tmp_eda05",
        )
        for column_name, data_type, valid_type_percent in tqdm(
            zip(column_names, data_types, valid_type_percentages),
            desc="EDA 05 - profiling aggregate columns",
            unit="col",
            total=len(column_names),
            leave=False,
        )
    ]

    reset_csv_dir(output_file)
    write_csv(output_file, ["metadata"], [(["key", "value"], [["aggregate_column_count"], [len(aggregate_columns)]])])
    write_aggregate_columns_csvs(output_file, aggregate_columns)
    print(f"EDA 05 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
