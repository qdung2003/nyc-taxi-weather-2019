import importlib
from tqdm import tqdm

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import (
    column_profile_file_name,
    reset_csv_dir,
    write_csv,
    write_csv_rows,
    write_high_unique_column_csv,
    write_low_unique_column_csv,
)
from pipeline.services.queries import (
    calculate_valid_type_percentages,
    count_limited_unique_values,
    ensure_table_exists,
    get_column_data_types,
    get_column_groups,
    profile_high_unique_column,
    profile_low_unique_column,
    quote_identifier,
    run_with_conn,
)


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "01_profile_features"


def main(conn):
    feature_etl = importlib.import_module("pipeline.feature.etl.01_join_taxi_weather")
    ensure_table_exists(
        conn,
        TABLE_TAXI_WEATHER_FEATURES,
        feature_etl.create_taxi_weather_features,
    )
    feature_table_quoted = quote_identifier(TABLE_TAXI_WEATHER_FEATURES)

    row_count = conn.execute(
        f"SELECT count(*) FROM {feature_table_quoted}"
    ).fetchone()[0]

    column_type_rows = conn.execute(f"DESCRIBE {feature_table_quoted}").fetchall()
    column_names = [str(row[0]) for row in column_type_rows]
    low_unique_column_names, high_unique_column_names = get_column_groups(
        conn,
        feature_table_quoted,
        column_names,
        desc="Feature EDA 01 - detecting column groups",
    )

    low_unique_data_types = get_column_data_types(
        column_type_rows,
        low_unique_column_names,
    )
    low_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        feature_table_quoted,
        low_unique_column_names,
        low_unique_data_types,
        row_count,
    )
    high_unique_data_types = get_column_data_types(
        column_type_rows,
        high_unique_column_names,
    )
    high_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        feature_table_quoted,
        high_unique_column_names,
        high_unique_data_types,
        row_count,
    )
    reset_csv_dir(output_file)
    low_unique_columns = []
    for index, (column_name, data_type, valid_type_percent) in enumerate(
        tqdm(
            zip(
                low_unique_column_names,
                low_unique_data_types,
                low_unique_valid_type_percentages,
            ),
            desc="Feature EDA 01 - value counts",
            unit="col",
            total=len(low_unique_column_names),
            leave=False,
        ),
        start=1,
    ):
        unique_count = count_limited_unique_values(
            conn,
            feature_table_quoted,
            quote_identifier(column_name),
        )
        low_unique_column = profile_low_unique_column(
            conn,
            feature_table_quoted,
            column_name,
            data_type,
            unique_count,
            valid_type_percent,
            row_count,
        )
        low_unique_column["profile_csv"] = write_low_unique_column_csv(
            output_file,
            low_unique_column,
            file_name=column_profile_file_name(column_name, index),
        )
        low_unique_columns.append(low_unique_column)

    high_unique_columns = []
    for index, (column_name, data_type, valid_type_percent) in enumerate(
        tqdm(
            zip(
                high_unique_column_names,
                high_unique_data_types,
                high_unique_valid_type_percentages,
            ),
            desc="Feature EDA 01 - profiling high-duplicate columns",
            unit="col",
            total=len(high_unique_column_names),
            leave=False,
        ),
        start=1,
    ):
        high_unique_column = profile_high_unique_column(
            conn,
            TABLE_TAXI_WEATHER_FEATURES,
            column_name,
            data_type,
            valid_type_percent,
            row_count,
            temp_prefix="tmp_feature_eda01",
        )
        profile_kind, profile_csv = write_high_unique_column_csv(
            output_file,
            high_unique_column,
            file_name=column_profile_file_name(column_name, index),
        )
        high_unique_column["profile_kind"] = profile_kind
        high_unique_column["profile_csv"] = profile_csv
        high_unique_columns.append(high_unique_column)

    write_csv(
        output_file,
        ["metadata"],
        [(
            ["key", "value"],
            [
                ["row_count", "low_unique_column_count", "high_unique_column_count"],
                [row_count, len(low_unique_columns), len(high_unique_columns)],
            ],
        )],
    )
    write_csv_rows(
        output_file / "low_unique_columns.csv",
        [
            {
                key: value
                for key, value in row.items()
                if key not in {"values", "counts", "percentages"}
            }
            for row in low_unique_columns
        ],
        columns=["column_name", "data_type", "unique_count", "valid_type_percent", "profile_csv"],
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
    print(f"Feature EDA 01 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
