from pipeline.constants.modules import ETL04_BUSINESS
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tmp_tables import TMP_TAXI04
from pipeline.constants.columns import AGGREGATE_COLUMNS
from pipeline.constants.upper_bounds_settings import (
    FIRST_PASS_BIN_COUNT,
    FIRST_PASS_THRESHOLD_PERCENT,
    SECOND_PASS_BIN_COUNT,
    SECOND_PASS_THRESHOLD_PERCENT,
)
from pipeline.services.helpers import reset_csv_dir, write_csv, write_metadata_csv
from pipeline.services.queries import (
    compute_upper_bounds,
    ensure_table_exists,
    run_with_conn,
)


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_json = TAXI_EDA_RESULTS_DIR / "08_before_upper_bounds"


def split_bin_rows(profiles: list[dict]) -> tuple[list[dict], list[dict]]:
    columns = []
    array_rows = []
    for row in profiles:
        column_name = row.get("column_name")
        bin_edges = row.get("bin_edges", [])
        bin_counts = row.get("bin_counts", [])
        bin_percentages = row.get("bin_percentages", [])
        columns.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"bin_edges", "bin_counts", "bin_percentages"}
            }
        )
        for index, bin_edge in enumerate(bin_edges):
            array_rows.append(
                {
                    "column_name": column_name,
                    "bin_edge": bin_edge,
                    "bin_count": bin_counts[index] if index < len(bin_counts) else None,
                    "bin_percentage": bin_percentages[index] if index < len(bin_percentages) else None,
                }
            )
    return columns, array_rows


def main(conn):
    ensure_table_exists(conn, TMP_TAXI04, ETL04_BUSINESS.create_etl04_business_rules)
    profiles_money_columns, profiles_aggregate_columns = compute_upper_bounds(conn, TMP_TAXI04, "eda08")
    money_columns, money_array_rows = split_bin_rows(profiles_money_columns)
    aggregate_columns, aggregate_array_rows = split_bin_rows(profiles_aggregate_columns)

    reset_csv_dir(output_json)
    write_metadata_csv(
        output_json,
        keys=[
            "first_pass_bin_count",
            "second_pass_bin_count",
            "first_pass_threshold_percent",
            "second_pass_threshold_percent",
            "column_count",
            "lower_trimmed_column_count",
        ],
        values=[
            FIRST_PASS_BIN_COUNT,
            SECOND_PASS_BIN_COUNT,
            FIRST_PASS_THRESHOLD_PERCENT,
            SECOND_PASS_THRESHOLD_PERCENT,
            len(profiles_money_columns) + len(profiles_aggregate_columns),
            len(AGGREGATE_COLUMNS),
        ],
    )
    write_csv(output_json / "money_column_bins.csv", money_columns)
    write_csv(output_json / "money_column_bins_array.csv", money_array_rows)
    write_csv(output_json / "aggregate_column_bins.csv", aggregate_columns)
    write_csv(output_json / "aggregate_column_bins_array.csv", aggregate_array_rows)
    print(f"EDA 08 saved: {output_json.name}")


if __name__ == "__main__":
    run_with_conn(main)
