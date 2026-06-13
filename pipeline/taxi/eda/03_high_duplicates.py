from pipeline.services.helpers import (
    reset_csv_dir,
    write_csv,
)
from pipeline.services.queries import (
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    profile_datetime_column,
    profile_numeric_column,
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
    column_names = read_column_names_csv(profile_dir / "high_unique_columns.csv")

    print(f"Input table: {TABLE_TAXI_RAW}")
    print(f"Total rows: {row_count:,}")
    print(
        "Phase 1/3: Loading high-cardinality columns "
        f"({len(column_names)}) from EDA 02..."
    )

    data_types = get_column_data_types(column_type_rows, column_names)
    valid_type_percents = calculate_valid_type_percentages(
        conn,
        taxi_raw_quoted,
        column_names,
        data_types,
        row_count,
    )

    print("Phase 2/3: Profiling high-cardinality columns...")
    reset_csv_dir(output_file)
    datetime_column_names = []
    datetime_data_types = []
    datetime_valid_type_percents = []
    datetime_min_values = []
    datetime_max_values = []
    datetime_before_year_counts = []
    datetime_after_year_counts = []
    datetime_month_counts = []

    numeric_column_names = []
    numeric_data_types = []
    numeric_valid_type_percents = []
    numeric_min_values = []
    numeric_chart_max_values = []
    numeric_max_values = []
    numeric_negative_counts = []
    numeric_zero_counts = []
    numeric_above_chart_max_value_counts = []
    numeric_range_counts = []

    datetime_array_column_names = []
    datetime_array_months = []
    datetime_array_month_counts = []
    datetime_array_month_percentages = []

    numeric_array_column_names = []
    numeric_array_bin_edges = []
    numeric_array_bin_counts = []
    numeric_array_bin_percentages = []

    for column_name, data_type, valid_type_percent in zip(
        column_names,
        data_types,
        valid_type_percents,
    ):
        type_str = str(data_type).lower()
        if "timestamp" in type_str or type_str == "date":
            profile = profile_datetime_column(
                conn,
                TABLE_TAXI_RAW,
                column_name,
                row_count,
            )
            #########
            datetime_column_names.append(column_name)
            datetime_data_types.append(data_type)
            datetime_valid_type_percents.append(valid_type_percent)
            datetime_min_values.append(profile.get("min_value"))
            datetime_max_values.append(profile.get("max_value"))
            datetime_before_year_counts.append(profile.get("before_year_count"))
            datetime_after_year_counts.append(profile.get("after_year_count"))
            datetime_month_counts.append(profile.get("month_count"))



            for month, month_count, month_percentage in zip(
                range(1, len(profile.get("month_counts", [])) + 1),
                profile.get("month_counts", []),
                profile.get("month_percentages", []),
            ):
                datetime_array_column_names.append(column_name)
                datetime_array_months.append(month)
                datetime_array_month_counts.append(month_count)
                datetime_array_month_percentages.append(month_percentage)
        elif any(
            numeric_type in type_str
            for numeric_type in ["integer", "float", "double", "decimal", "numeric", "real"]
        ):
            profile = profile_numeric_column(
                conn,
                TABLE_TAXI_RAW,
                column_name,
                row_count,
                temp_prefix="tmp_eda03",
            )
            numeric_column_names.append(column_name)
            numeric_data_types.append(data_type)
            numeric_valid_type_percents.append(valid_type_percent)
            numeric_min_values.append(profile.get("min_value"))
            numeric_chart_max_values.append(profile.get("chart_max_value"))
            numeric_max_values.append(profile.get("max_value"))
            numeric_negative_counts.append(profile.get("negative_count"))
            numeric_zero_counts.append(profile.get("zero_count"))
            numeric_above_chart_max_value_counts.append(profile.get("above_chart_max_value_count"))
            numeric_range_counts.append(profile.get("range_count"))
            for bin_edge, bin_count, bin_percentage in zip(
                profile.get("bin_edges", []),
                profile.get("bin_counts", []),
                profile.get("bin_percentages", []),
            ):
                numeric_array_column_names.append(column_name)
                numeric_array_bin_edges.append(bin_edge)
                numeric_array_bin_counts.append(bin_count)
                numeric_array_bin_percentages.append(bin_percentage)
        else:
            print(f"Unhandled data type: column_name={column_name}, data_type={data_type}, valid_type_percent={valid_type_percent}")


    print("Phase 3/3: Writing CSV tables...")
    write_csv(
        output_file,
        [
            "metadata",
            "high_unique_columns_datetime",
            "high_unique_columns_datetime_array",
            "high_unique_columns_numeric",
            "high_unique_columns_numeric_array",
        ],
        [(
            ["key", "value"],
            [
                ["tail_ratio", "positive_bin_count", "high_unique_column_count"],
                ["1/101", POSITIVE_BIN_COUNT, len(column_names)],
            ],
        ),
        (
            [
                "column_name",
                "data_type",
                "valid_type_percent",
                "min_value",
                "max_value",
                "before_year_count",
                "after_year_count",
                "month_count",
            ],
            [
                datetime_column_names,
                datetime_data_types,
                datetime_valid_type_percents,
                datetime_min_values,
                datetime_max_values,
                datetime_before_year_counts,
                datetime_after_year_counts,
                datetime_month_counts,
            ],
        ),
        (
            ["column_name", "month", "month_count", "month_percentage"],
            [
                datetime_array_column_names,
                datetime_array_months,
                datetime_array_month_counts,
                datetime_array_month_percentages,
            ],
        ),
        (
            [
                "column_name",
                "data_type",
                "valid_type_percent",
                "min_value",
                "chart_max_value",
                "max_value",
                "negative_count",
                "zero_count",
                "above_chart_max_value_count",
                "range_count",
            ],
            [
                numeric_column_names,
                numeric_data_types,
                numeric_valid_type_percents,
                numeric_min_values,
                numeric_chart_max_values,
                numeric_max_values,
                numeric_negative_counts,
                numeric_zero_counts,
                numeric_above_chart_max_value_counts,
                numeric_range_counts,
            ],
        ),
        (
            ["column_name", "bin_edge", "bin_count", "bin_percentage"],
            [
                numeric_array_column_names,
                numeric_array_bin_edges,
                numeric_array_bin_counts,
                numeric_array_bin_percentages,
            ],
        ),
        ],
    )
    print(f"EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
