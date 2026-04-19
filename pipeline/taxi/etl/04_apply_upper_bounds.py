import json
from tqdm import tqdm
from pipeline.services.queries import ensure_source_exists
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL
from pipeline.services.views import VIEW_TAXI_BUSINESS_RULES, VIEW_TAXI_UPPER_BOUNDS

TARGET_COLUMNS = ["trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"]


def compute_upper_bounds(conn) -> dict[str, float]:
    print("Computing IQR upper bounds on the fly...")
    selects = ", ".join(
        f"quantile_cont({c}, [0.25, 0.75]), MAX({c})" for c in TARGET_COLUMNS
    )
    query = f'SELECT {selects} FROM "{VIEW_TAXI_BUSINESS_RULES}"'
    row = conn.execute(query).fetchone()
    
    bounds: dict[str, float] = {}
    for i, col in enumerate(TARGET_COLUMNS):
        q1, q3 = row[i*2]
        max_val = row[i*2 + 1]
        iqr = q3 - q1
        upper_limit = q3 + 1.5 * iqr
        bounds[col] = float(min(upper_limit, max_val))
    return bounds


def main(conn):
    with tqdm(
        total=4,
        desc="ETL 04 - upper bounds",
        unit="step",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        upper_bounds = compute_upper_bounds(conn)
        pbar.update(1)

        ensure_source_exists(conn, VIEW_TAXI_BUSINESS_RULES)
        pbar.update(1)

        where_clause = " AND ".join(
            f'{col} <= {upper_bounds[col]:.12f}' for col in TARGET_COLUMNS
        )

        print(f"Creating view '{VIEW_TAXI_UPPER_BOUNDS}'...")
        conn.execute(f'DROP VIEW IF EXISTS "{VIEW_TAXI_UPPER_BOUNDS}"')
        conn.execute(
            f"""
            CREATE VIEW "{VIEW_TAXI_UPPER_BOUNDS}" AS
            SELECT *
            FROM "{VIEW_TAXI_BUSINESS_RULES}"
            WHERE {where_clause}
            """
        )
        pbar.update(1)
        input_rows = conn.execute(f'SELECT count(*) FROM "{VIEW_TAXI_BUSINESS_RULES}"').fetchone()[0]
        output_rows = conn.execute(f'SELECT count(*) FROM "{VIEW_TAXI_UPPER_BOUNDS}"').fetchone()[0]
        pbar.update(1)
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print(f"Step {VIEW_TAXI_UPPER_BOUNDS} complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("Upper bounds used:")
    for col in TARGET_COLUMNS:
        print(f"  - {col}: <= {upper_bounds[col]:.2f}")
    print("-" * 30)


