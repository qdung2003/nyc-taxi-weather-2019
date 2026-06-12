from tqdm import tqdm
from pipeline.services.helpers import (
    column_profile_file_name,
    reset_csv_dir,
    write_csv,
    write_csv_rows,
    write_high_unique_column_csv,
)
from pipeline.services.queries import (
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    profile_high_unique_column,
    quote_identifier,
    read_column_names_csv,
    run_with_conn,
)
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.unique_settings import (
    POSITIVE_BIN_COUNT,
)
from pipeline.constants.modules import ETL02_INGEST


output_file = TAXI_EDA_RESULTS_DIR / "03_high_duplicates"
profile_dir = TAXI_EDA_RESULTS_DIR / "02_low_duplicates"
TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def main(conn):
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)
    taxi_raw_quoted = quote_identifier(TABLE_TAXI_RAW)
    row_count = conn.execute(
        f"SELECT count(*) FROM {taxi_raw_quoted}"
    ).fetchone()[0]

    column_type_rows = conn.execute(f"DESCRIBE {taxi_raw_quoted}").fetchall()
    high_unique_column_names = read_column_names_csv(profile_dir / "high_unique_columns.csv")

    high_unique_data_types = get_column_data_types(column_type_rows, high_unique_column_names)
    high_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        taxi_raw_quoted,
        high_unique_column_names,
        high_unique_data_types,
        row_count,
    )
    reset_csv_dir(output_file)
    high_unique_columns = []
    for index, (column_name, data_type, valid_type_percent) in enumerate(
        tqdm(
            zip(
                high_unique_column_names,
                high_unique_data_types,
                high_unique_valid_type_percentages,
            ),
            desc="EDA 03 - profiling high-duplicate columns",
            unit="col",
            total=len(high_unique_column_names),
            leave=False,
        ),
        start=1,
    ):
        high_unique_column = profile_high_unique_column(
            conn,
            TABLE_TAXI_RAW,
            column_name,
            data_type,
            valid_type_percent,
            row_count,
        )
        profile_kind, profile_csv = write_high_unique_column_csv(
            output_file,
            high_unique_column,
            file_name=column_profile_file_name(column_name, index),
        )
        high_unique_column["profile_kind"] = profile_kind
        high_unique_column["profile_csv"] = profile_csv
        high_unique_columns.append(high_unique_column)
    high_unique_column_count = len(high_unique_columns)

    write_csv(
        output_file,
        ["metadata"],
        [(
            ["key", "value"],
            [
                ["tail_ratio", "positive_bin_count", "high_unique_column_count"],
                ["1/101", POSITIVE_BIN_COUNT, high_unique_column_count],
            ],
        )],
    )
    write_csv_rows(
        output_file / "high_unique_columns.csv",
        [
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {
                        "month_counts",
                        "month_percentages",
                        "bin_edges",
                        "bin_counts",
                        "bin_percentages",
                        "filter",
                    }
                },
                **(row.get("filter") if isinstance(row.get("filter"), dict) else {}),
            }
            for row in high_unique_columns
        ],
    )
    print(f"EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)




