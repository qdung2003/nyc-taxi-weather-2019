from pipeline.services.helpers import write_json_compact
from pipeline.services.queries import (
    compute_upper_bounds,
    ensure_table_exists,
    quote_identifier,
    run_with_conn,
)
from pipeline.constants.modules import ETL03_BUSINESS
from pipeline.constants.upper_bounds_settings import (
    FIRST_PASS_BIN_COUNT,
    SECOND_PASS_BIN_COUNT,
    FIRST_PASS_THRESHOLD_PERCENT,
    SECOND_PASS_THRESHOLD_PERCENT,
)
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tmp_tables import TMP_TAXI03


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_json = TAXI_EDA_RESULTS_DIR / "07_before_upper_bounds.json"


COMPACT_ARRAY_PATHS = [
    ("columns", "*", "bin_edges"),
    ("columns", "*", "bin_counts"),
    ("columns", "*", "bin_percentages"),
]


def main(conn):
    ensure_table_exists(conn, TMP_TAXI03, ETL03_BUSINESS.create_etl03_business_rules)
    tmp_taxi03_quoted = quote_identifier(TMP_TAXI03)
    profiles = compute_upper_bounds(
        conn,
        tmp_taxi03_quoted,
        temp_prefix="tmp_eda07",
    )
    payload = {
        "first_pass_bin_count": FIRST_PASS_BIN_COUNT,
        "second_pass_bin_count": SECOND_PASS_BIN_COUNT,
        "first_pass_threshold_percent": FIRST_PASS_THRESHOLD_PERCENT,
        "second_pass_threshold_percent": SECOND_PASS_THRESHOLD_PERCENT,
        "column_count": len(profiles),
        "columns": profiles,
    }
    write_json_compact(
        output_json,
        payload,
        compact_array_paths=COMPACT_ARRAY_PATHS,
        align_object_values=False,
        align_compact_array_items=True,
        align_compact_array_key_labels=True,
        parallel_array_groups=[
            ("bin_edges", "bin_counts", "bin_percentages"),
        ],
    )
    print(f"EDA 07 saved: {output_json.name}")


if __name__ == "__main__":
    run_with_conn(main)

