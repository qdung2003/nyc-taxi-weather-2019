from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.upper_bounds_settings import (
    FIRST_PASS_BIN_COUNT,
    FIRST_PASS_THRESHOLD_PERCENT,
    SECOND_PASS_BIN_COUNT,
    SECOND_PASS_THRESHOLD_PERCENT,
)
from pipeline.services.helpers import reset_csv_dir, write_csv, write_metadata_csv
from pipeline.services.queries import compute_upper_bounds, quote_identifier, run_with_conn


TEST_TABLE = "taxi_upper_bounds_compare"
output_dir = TAXI_EDA_RESULTS_DIR / "test_bounds_eda"


def main(conn):
    profiles = compute_upper_bounds(
        conn,
        quote_identifier(TEST_TABLE),
        column_names=[
            "before_lower_bound",
            "before_upper_bound",
            "after_min_value",
            "after_max_value",
        ],
        temp_prefix="tmp_test_bounds_eda",
    )

    columns = []
    array_rows = []
    for row in profiles:
        column_name = row.get("column_name")
        columns.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"bin_edges", "bin_counts", "bin_percentages"}
            }
        )
        for bin_edge, bin_count, bin_percentage in zip(
            row.get("bin_edges", []),
            row.get("bin_counts", []),
            row.get("bin_percentages", []),
        ):
            array_rows.append(
                {
                    "column_name": column_name,
                    "bin_edge": bin_edge,
                    "bin_count": bin_count,
                    "bin_percentage": bin_percentage,
                }
            )

    reset_csv_dir(output_dir)
    write_metadata_csv(
        output_dir,
        keys=[
            "first_pass_bin_count",
            "second_pass_bin_count",
            "first_pass_threshold_percent",
            "second_pass_threshold_percent",
            "column_count",
        ],
        values=[
            FIRST_PASS_BIN_COUNT,
            SECOND_PASS_BIN_COUNT,
            FIRST_PASS_THRESHOLD_PERCENT,
            SECOND_PASS_THRESHOLD_PERCENT,
            len(profiles),
        ],
    )
    write_csv(output_dir / "column_bins.csv", columns)
    write_csv(output_dir / "column_bins_array.csv", array_rows)
    print(f"Test EDA saved: {output_dir.name}")


if __name__ == "__main__":
    run_with_conn(main)
