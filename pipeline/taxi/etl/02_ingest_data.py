from pipeline.services.helpers import extract_month
from pipeline.services.queries import quote_identifier, run_with_conn
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.modules import DOWNLOAD_YELLOW_TRIPDATA


def create_taxi_raw_table(conn) -> None:
    link_parquet_files = sorted(
        DOWNLOAD_YELLOW_TRIPDATA.ensure_taxi_raw_files(),
        key=extract_month,
    )
    print(f"Loading raw Parquet into '{TABLE_TAXI_RAW}'...")
    conn.execute(f'DROP TABLE IF EXISTS "{TABLE_TAXI_RAW}"')
    first_file_path = link_parquet_files[0].as_posix()
    conn.execute(
        f"""
        CREATE TABLE "{TABLE_TAXI_RAW}" AS
        SELECT *
        FROM read_parquet('{first_file_path}')
        LIMIT 0
        """
    )
    rows = conn.execute(f'DESCRIBE "{TABLE_TAXI_RAW}"').fetchall()
    ordered_columns = [
        row[0]
        for row in rows
    ]
    select_cols_sql = ", ".join(quote_identifier(col) for col in ordered_columns)

    batch_insert_clauses = []
    for link_parquet_file in link_parquet_files:
        parquet_path = link_parquet_file.as_posix()
        batch_insert_clauses.append(
            f"SELECT {select_cols_sql} FROM read_parquet('{parquet_path}')"
        )

    batch_insert_sql = f"""
    INSERT INTO "{TABLE_TAXI_RAW}"
    {" UNION ALL ".join(batch_insert_clauses)}
    """
    conn.execute(batch_insert_sql)


def main(conn):
    create_taxi_raw_table(conn)
    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_TAXI_RAW}"').fetchone()[0]
    print("-" * 30)
    print(f"Step {TABLE_TAXI_RAW} complete: {row_count:,} rows.")
    print("-" * 30)


if __name__ == "__main__":
    run_with_conn(main)








