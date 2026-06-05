import csv
from pipeline.services.queries import (
    run_with_conn,
    compute_upper_bounds,
    ensure_table_exists,
    quote_identifier,
)
from pipeline.constants.columns import MONEY_COLUMNS
from pipeline.constants.modules import ETL03_BUSINESS
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tmp_tables import TMP_TAXI03, TMP_TAXI04


upper_bounds_file = TAXI_EDA_RESULTS_DIR / "07_before_upper_bounds" / "column_bins.csv"


def load_upper_bounds_from_eda07():
    if not upper_bounds_file.exists():
        return None

    try:
        with upper_bounds_file.open("r", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
    except OSError:
        return None

    upper_bounds = {
        str(row.get("column_name")): row.get("second_pass_value")
        for row in rows
        if row.get("column_name") is not None
    }

    if any(column_name not in upper_bounds for column_name in MONEY_COLUMNS):
        return None

    try:
        return {
            column_name: float(upper_bounds[column_name])
            for column_name in MONEY_COLUMNS
        }
    except (TypeError, ValueError):
        return None


def create_etl04_upper_bounds(conn):
    ensure_table_exists(conn, TMP_TAXI03, ETL03_BUSINESS.create_etl03_business_rules)
    upper_bounds = load_upper_bounds_from_eda07()
    if upper_bounds is None:
        profiles = compute_upper_bounds(conn, quote_identifier(TMP_TAXI03))
        upper_bounds = {
            str(profile["column_name"]): float(profile["second_pass_value"])
            for profile in profiles
        }

    where_clause = " AND ".join(
        f"{quote_identifier(col)} <= {upper_bounds[col]:.12f}" for col in MONEY_COLUMNS
    )
    conn.execute(f'DROP TABLE IF EXISTS "{TMP_TAXI04}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{TMP_TAXI04}" AS
        SELECT *
        FROM "{TMP_TAXI03}"
        WHERE {where_clause}
        """
    )
    return upper_bounds


def main(conn):
    print("Preparing histogram-threshold upper bounds...")
    upper_bounds = create_etl04_upper_bounds(conn)

    input_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI03}"').fetchone()[0] or 0)
    output_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI04}"').fetchone()[0] or 0)
        
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print("Step taxi_etl_04_upper_bounds_cte complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("Upper bounds used:")
    for col in MONEY_COLUMNS:
        print(f"  - {col}: <= {upper_bounds[col]:.2f}")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
