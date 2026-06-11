from pipeline.services.queries import ensure_table_exists, run_with_conn
from pipeline.constants.times import YEAR
from pipeline.constants.tmp_tables import TMP_TAXI03, TMP_TAXI04
from pipeline.constants.modules import ETL03_AGGREGATE


def create_etl04_business_rules(conn) -> None:
    ensure_table_exists(conn, TMP_TAXI03, ETL03_AGGREGATE.create_etl03_add_aggregate_columns)
    print("Applying business rules...")
    conn.execute(f'DROP TABLE IF EXISTS "{TMP_TAXI04}"')
    conn.execute(
        f"""
        CREATE TEMP TABLE "{TMP_TAXI04}" AS
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
            COALESCE(congestion_surcharge, 0.0) AS congestion_surcharge,
            trip_duration,
            average_speed,
            fare_per_mile,
            fare_per_minute
        FROM "{TMP_TAXI03}"
        WHERE
            tpep_pickup_datetime >= TIMESTAMP '{YEAR}-01-01'
            AND tpep_pickup_datetime < TIMESTAMP '{YEAR + 1}-01-01'
            AND tpep_dropoff_datetime >= TIMESTAMP '{YEAR}-01-01'
            AND tpep_dropoff_datetime < TIMESTAMP '{YEAR + 1}-01-01'
            AND tpep_pickup_datetime < tpep_dropoff_datetime
            AND VendorID IN (1, 2)
            AND passenger_count BETWEEN 1 AND 5
            AND RatecodeID BETWEEN 1 AND 6
            AND store_and_fwd_flag IN ('Y', 'N')
            AND PULocationID BETWEEN 1 AND 263
            AND DOLocationID BETWEEN 1 AND 263
            AND payment_type BETWEEN 1 AND 4
            AND (
                congestion_surcharge IS NULL
                OR congestion_surcharge IN (0.0, 0.75, 2.5)
            )
            AND trip_distance > 0
            AND (CASE WHEN extra >= 2.5 THEN fare_amount + 2.5 ELSE fare_amount END) > 0
            AND (CASE WHEN extra >= 2.5 THEN extra - 2.5 ELSE extra END) IN (0.0, 0.5, 1.0)
            AND mta_tax = 0.5
            AND tip_amount >= 0
            AND tolls_amount >= 0
            AND improvement_surcharge = 0.3
            AND total_amount >= 0
            AND NOT (payment_type IN (2, 3, 4) AND tip_amount > 0)
        """
    )


def main(conn):
    create_etl04_business_rules(conn)

    input_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI03}"').fetchone()[0] or 0)
    output_rows = int(conn.execute(f'SELECT COUNT(*) FROM "{TMP_TAXI04}"').fetchone()[0] or 0)
    
    
    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print("Step taxi_etl_04_apply_business_rules complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)
