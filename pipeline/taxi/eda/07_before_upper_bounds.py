from pipeline.constants.modules import ETL03_BUSINESS
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tmp_tables import TMP_TAXI03
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
    quote_identifier,
    run_with_conn,
)


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_json = TAXI_EDA_RESULTS_DIR / "07_before_upper_bounds"


def main(conn):
    ensure_table_exists(conn, TMP_TAXI03, ETL03_BUSINESS.create_etl03_business_rules)
    tmp_taxi03_quoted = quote_identifier(TMP_TAXI03)
    profiles = compute_upper_bounds(
        conn,
        tmp_taxi03_quoted,
        temp_prefix="tmp_eda07",
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

    reset_csv_dir(output_json)
    write_metadata_csv(
        output_json,
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
    write_csv(output_json / "column_bins.csv", columns)
    write_csv(output_json / "column_bins_array.csv", array_rows)
    print(f"EDA 07 saved: {output_json.name}")


if __name__ == "__main__":
    run_with_conn(main)
