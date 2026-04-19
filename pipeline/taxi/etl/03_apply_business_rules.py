from tqdm import tqdm
from pipeline.services.queries import ensure_source_exists
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.views import VIEW_TAXI_BUSINESS_RULES
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


FILTER_YEAR_SQL = """
tpep_pickup_datetime >= TIMESTAMP '2019-01-01'
AND tpep_pickup_datetime < TIMESTAMP '2020-01-01'
AND tpep_dropoff_datetime >= TIMESTAMP '2019-01-01'
AND tpep_dropoff_datetime < TIMESTAMP '2020-01-01'
AND tpep_pickup_datetime < tpep_dropoff_datetime
"""

BUSINESS_RULES_SQL = """
VendorID IN (1, 2)
AND passenger_count BETWEEN 1 AND 5
AND RatecodeID BETWEEN 1 AND 6
AND store_and_fwd_flag IN ('Y', 'N')
AND PULocationID BETWEEN 1 AND 263
AND DOLocationID BETWEEN 1 AND 263
AND payment_type BETWEEN 1 AND 4
AND congestion_surcharge IN (0.0, 0.75, 2.5)
AND trip_distance > 0
AND fare_amount > 0
AND extra IN (0.0, 0.5, 1.0)
AND mta_tax = 0.5
AND tip_amount >= 0
AND tolls_amount >= 0
AND improvement_surcharge = 0.3
AND total_amount > 0
AND NOT (payment_type IN (2, 3, 4) AND tip_amount <> 0)
"""


def main(conn):
    with tqdm(
        total=3,
        desc="ETL 03 - business rules",
        unit="step",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        ensure_source_exists(conn, TABLE_TAXI_RAW)
        pbar.update(1)

        print(f"Creating view '{VIEW_TAXI_BUSINESS_RULES}'...")
        # Single query with shared CTEs for both view creation and row counting
        combined_query = f"""
        WITH filtered_2019 AS (
            SELECT *
            FROM "{TABLE_TAXI_RAW}"
            WHERE {FILTER_YEAR_SQL}
        ),
        normalized_fares AS (
            SELECT
                VendorID,
                tpep_pickup_datetime,
                tpep_dropoff_datetime,
                passenger_count,
                trip_distance,
                RatecodeID,
                store_and_fwd_flag,
                PULocationID,
                DOLocationID,
                payment_type,
                CASE WHEN extra >= 2.5 THEN fare_amount + 2.5 ELSE fare_amount END AS fare_amount,
                CASE WHEN extra >= 2.5 THEN extra - 2.5 ELSE extra END AS extra,
                mta_tax,
                tip_amount,
                tolls_amount,
                improvement_surcharge,
                total_amount,
                COALESCE(congestion_surcharge, 0.0) AS congestion_surcharge
            FROM filtered_2019
        ),
        business_filtered AS (
            SELECT *
            FROM normalized_fares
            WHERE {BUSINESS_RULES_SQL}
        ),
        stats AS (
            SELECT
                COUNT(*) AS input_rows,
                (SELECT COUNT(*) FROM business_filtered) AS output_rows
            FROM normalized_fares
        )
        SELECT * FROM stats
        """
        
        # Get row counts first
        input_rows, output_rows = conn.execute(combined_query).fetchone()
        pbar.update(1)
        
        # Create the view using the same CTE structure
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW "{VIEW_TAXI_BUSINESS_RULES}" AS
            WITH filtered_2019 AS (
                SELECT *
                FROM "{TABLE_TAXI_RAW}"
                WHERE {FILTER_YEAR_SQL}
            ),
            normalized_fares AS (
                SELECT
                    VendorID,
                    tpep_pickup_datetime,
                    tpep_dropoff_datetime,
                    passenger_count,
                    trip_distance,
                    RatecodeID,
                    store_and_fwd_flag,
                    PULocationID,
                    DOLocationID,
                    payment_type,
                    CASE WHEN extra >= 2.5 THEN fare_amount + 2.5 ELSE fare_amount END AS fare_amount,
                    CASE WHEN extra >= 2.5 THEN extra - 2.5 ELSE extra END AS extra,
                    mta_tax,
                    tip_amount,
                    tolls_amount,
                    improvement_surcharge,
                    total_amount,
                    COALESCE(congestion_surcharge, 0.0) AS congestion_surcharge
                FROM filtered_2019
            )
            SELECT *
            FROM normalized_fares
            WHERE {BUSINESS_RULES_SQL}
            """
        )
        pbar.update(1)
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print(f"Step {VIEW_TAXI_BUSINESS_RULES} complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("-" * 30)


