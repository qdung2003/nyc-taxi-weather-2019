from pipeline.services.helpers import reset_csv_dir, write_upper_bounds_csvs
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
output_json = TAXI_EDA_RESULTS_DIR / "07_before_upper_bounds"




def main(conn):
    ensure_table_exists(conn, TMP_TAXI03, ETL03_BUSINESS.create_etl03_business_rules)
    tmp_taxi03_quoted = quote_identifier(TMP_TAXI03)
    profiles = compute_upper_bounds(
        conn,
        tmp_taxi03_quoted,
        temp_prefix="tmp_eda07",
    )
    reset_csv_dir(output_json)
    write_upper_bounds_csvs(
        output_json,
        {
            "first_pass_bin_count": FIRST_PASS_BIN_COUNT,
            "second_pass_bin_count": SECOND_PASS_BIN_COUNT,
            "first_pass_threshold_percent": FIRST_PASS_THRESHOLD_PERCENT,
            "second_pass_threshold_percent": SECOND_PASS_THRESHOLD_PERCENT,
            "column_count": len(profiles),
        },
        profiles,
    )
    print(f"EDA 07 saved: {output_json.name}")


if __name__ == "__main__":
    run_with_conn(main)





