from pipeline.services.queries import (
    run_with_conn,
    compute_upper_bounds,
    ensure_table_exists,
    quote_identifier,
)
from pipeline.constants.columns import UPPER_BOUND_COLUMNS
from pipeline.constants.modules import ETL04_BUSINESS
from pipeline.constants.tmp_tables import TMP_TAXI04, TMP_TAXI05


def create_etl05_upper_bounds(conn):
    ensure_table_exists(conn, TMP_TAXI04, ETL04_BUSINESS.create_etl04_business_rules)
    profiles = compute_upper_bounds(conn, TMP_TAXI04, "etl05")
    bounds = {
        str(profile["column_name"]): {
            "trim_lower": bool(profile.get("trim_lower")),
            "lower": float(profile["second_pass_min_value"]),
            "upper": float(profile["second_pass_max_value"]),
        }
        for profile in profiles
    }

    where_clause = " AND ".join(
        (
            (
                f"({quote_identifier(col)} >= {bounds[col]['lower']:.12f} "
                f"AND {quote_identifier(col)} <= {bounds[col]['upper']:.12f})"
            )
            if bounds[col]["trim_lower"]
            else f"({quote_identifier(col)} <= {bounds[col]['upper']:.12f})"
        )
        for col in UPPER_BOUND_COLUMNS
    )
    conn.execute(f'DROP TABLE IF EXISTS "{TMP_TAXI05}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{TMP_TAXI05}" AS
        SELECT *
        FROM "{TMP_TAXI04}"
        WHERE {where_clause}
        """
    )
    return bounds


def main(conn):
    print("Preparing histogram-threshold bounds...")
    bounds = create_etl05_upper_bounds(conn)

    input_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI04}"').fetchone()[0] or 0)
    output_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI05}"').fetchone()[0] or 0)
        
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print("Step taxi_etl_05_apply_upper_bounds complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("Bounds used:")
    for col in UPPER_BOUND_COLUMNS:
        trim_lower = bounds[col]["trim_lower"]
        lower = bounds[col]["lower"]
        upper = bounds[col]["upper"]
        if trim_lower:
            print(f"  - {col}: {lower:.2f} <= value <= {upper:.2f}")
        else:
            print(f"  - {col}: value <= {upper:.2f}")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
