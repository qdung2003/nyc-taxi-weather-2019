from pipeline.services.queries import run_with_conn, ensure_table_exists
from pipeline.constants.modules import ETL04_UPPER_BOUNDS
from pipeline.constants.tables import TABLE_TAXI_CLEAN
from pipeline.constants.tmp_tables import TMP_TAXI04


def create_etl05_optimize_dtypes(conn) -> None:
    ensure_table_exists(conn, TMP_TAXI04, ETL04_UPPER_BOUNDS.create_etl04_upper_bounds)

    print(f"Creating table '{TABLE_TAXI_CLEAN}'...")
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_TAXI_CLEAN}"')
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_TAXI_CLEAN}" AS
        SELECT
            CAST(VendorID AS UTINYINT) AS VendorID,
            CAST(tpep_pickup_datetime AS TIMESTAMP) AS tpep_pickup_datetime,
            CAST(tpep_dropoff_datetime AS TIMESTAMP) AS tpep_dropoff_datetime,
            CAST(passenger_count AS UTINYINT) AS passenger_count,
            CAST(trip_distance AS FLOAT) AS trip_distance,
            CAST(RatecodeID AS UTINYINT) AS RatecodeID,
            CASE
                WHEN store_and_fwd_flag = 'Y' THEN true
                WHEN store_and_fwd_flag = 'N' THEN false
            END AS store_and_fwd_flag,
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
        FROM "{TMP_TAXI04}"
        """
    )


def main(conn):
    create_etl05_optimize_dtypes(conn)
    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_TAXI_CLEAN}"').fetchone()[0]

    print("-" * 30)
    print(f"Step {TABLE_TAXI_CLEAN} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)






