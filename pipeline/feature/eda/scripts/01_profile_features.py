import importlib

from pipeline.constants.paths import FEATURE_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_WEATHER_FEATURES
from pipeline.services.helpers import write_json_compact
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


FEATURE_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = FEATURE_EDA_RESULTS_DIR / "01_profile_features.json"


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
    low_unique_columns = build_low_unique_columns(
        conn,
        feature_table_quoted,
        low_unique_column_names,
        low_unique_data_types,
        low_unique_valid_type_percentages,
        row_count,
        desc="Feature EDA 01 - value counts",
        leave=False,
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
    high_unique_columns = build_high_unique_columns(
        conn,
        TABLE_TAXI_WEATHER_FEATURES,
        high_unique_column_names,
        high_unique_data_types,
        high_unique_valid_type_percentages,
        row_count,
        desc="Feature EDA 01 - profiling high-duplicate columns",
        temp_prefix="tmp_feature_eda01",
    )

    payload = {
        "row_count": row_count,
        "low_unique_column_count": len(low_unique_columns),
        "high_unique_column_count": len(high_unique_columns),
        "low_unique_columns": low_unique_columns,
        "high_unique_columns": high_unique_columns,
    }
    write_json_compact(
        output_file,
        payload,
        compact_all_scalar_arrays=True,
        align_compact_array_items=True,
        align_compact_array_key_labels=True,
        parallel_array_groups=[
            ("values", "counts", "percentages"),
            ("month_counts", "month_percentages"),
            ("bin_edges", "bin_counts", "bin_percentages"),
        ],
    )
    print(f"Feature EDA 01 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
