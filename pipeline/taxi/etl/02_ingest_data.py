import shutil
from tqdm import tqdm
from pipeline.services.helpers import extract_month
from pipeline.services.queries import quote_identifier
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.paths import TAXI_RAW_TEMP_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


def main(conn):
    link_parquet_files = sorted(
        TAXI_RAW_TEMP_DIR.glob("yellow_tripdata_2019-*.parquet"),
        key=extract_month
    )

    if not link_parquet_files:
        raise SystemExit(
            f"No parquet files matching yellow_tripdata_2019-*.parquet in {TAXI_RAW_TEMP_DIR}. "
            "Run 01_download_yellow_tripdata.py first."
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
    rows = conn.execute(f'PRAGMA table_info("{TABLE_TAXI_RAW}")').fetchall()
    ordered_columns = [
        row[1]
        for row in rows
    ]
    select_cols_sql = ", ".join(quote_identifier(col) for col in ordered_columns)

    # Use batch INSERT for better performance
    with tqdm(
        total=len(link_parquet_files),
        desc="Ingest All Files",
        unit="file",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as overall_bar:
        # Build batch INSERT statement for all files
        batch_insert_clauses = []
        for link_parquet_file in link_parquet_files:
            parquet_path = link_parquet_file.as_posix()
            batch_insert_clauses.append(
                f"SELECT {select_cols_sql} FROM read_parquet('{parquet_path}')"
            )
            overall_bar.update(1)
        
        # Execute single batch INSERT
        batch_insert_sql = f"""
        INSERT INTO "{TABLE_TAXI_RAW}"
        {" UNION ALL ".join(batch_insert_clauses)}
        """
        conn.execute(batch_insert_sql)

    row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_TAXI_RAW}"').fetchone()[0]
    print("-" * 30)
    print(f"Step {TABLE_TAXI_RAW} complete: {row_count:,} rows.")
    print("-" * 30)

    if TAXI_RAW_TEMP_DIR.exists():
        shutil.rmtree(TAXI_RAW_TEMP_DIR)
        print(f"Removed temp directory: {TAXI_RAW_TEMP_DIR}")


