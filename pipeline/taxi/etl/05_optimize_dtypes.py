"""Create final clean table taxi_clean from stage view v_taxi_04_upper_bounds."""
from tqdm import tqdm
from pipeline.services.queries import ensure_source_exists
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL
from pipeline.services.tables import TABLE_TAXI_CLEAN
from pipeline.services.views import VIEW_TAXI_UPPER_BOUNDS

def main(conn):
    with tqdm(
        total=3,
        desc="ETL 05 - finalize clean",
        unit="step",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        ensure_source_exists(conn, VIEW_TAXI_UPPER_BOUNDS)
        pbar.update(1)

        print(f"Creating table '{TABLE_TAXI_CLEAN}'...")
        conn.execute(f'DROP TABLE IF EXISTS "{TABLE_TAXI_CLEAN}"')
        conn.execute(
            f"""
            CREATE TABLE "{TABLE_TAXI_CLEAN}" AS
            SELECT
                CAST(VendorID AS UTINYINT) AS VendorID,
                tpep_pickup_datetime,
                tpep_dropoff_datetime,
                CAST(passenger_count AS UTINYINT) AS passenger_count,
                CAST(trip_distance AS FLOAT) AS trip_distance,
                CAST(RatecodeID AS UTINYINT) AS RatecodeID,
                (store_and_fwd_flag = 'Y') AS store_and_fwd_flag,
                CAST(PULocationID AS USMALLINT) AS PULocationID,
                CAST(DOLocationID AS USMALLINT) AS DOLocationID,
                CAST(payment_type AS UTINYINT) AS payment_type,
                CAST(fare_amount AS FLOAT) AS fare_amount,
                CAST(extra AS FLOAT) AS extra,
                CAST(mta_tax AS FLOAT) AS mta_tax,
                CAST(tip_amount AS FLOAT) AS tip_amount,
                CAST(tolls_amount AS FLOAT) AS tolls_amount,
                CAST(improvement_surcharge AS FLOAT) AS improvement_surcharge,
                CAST(total_amount AS FLOAT) AS total_amount,
                CAST(congestion_surcharge AS FLOAT) AS congestion_surcharge
            FROM "{VIEW_TAXI_UPPER_BOUNDS}"
            """
        )
        pbar.update(1)

        row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_TAXI_CLEAN}"').fetchone()[0]
        pbar.update(1)
    print("-" * 30)
    print(f"Step {TABLE_TAXI_CLEAN} complete: {row_count:,} rows.")
    print("-" * 30)


