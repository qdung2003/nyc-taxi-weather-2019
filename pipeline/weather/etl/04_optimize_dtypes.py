from tqdm import tqdm
from pipeline.services.queries import ensure_source_exists
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL
from pipeline.services.tables import TABLE_WEATHER_CLEAN
from pipeline.services.views import VIEW_WEATHER_BUSINESS_RULES

def main(conn):
    with tqdm(
        total=3,
        desc="ETL 04 - finalize clean weather",
        unit="step",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        ensure_source_exists(conn, VIEW_WEATHER_BUSINESS_RULES)
        pbar.update(1)

        print(f"Creating table '{TABLE_WEATHER_CLEAN}'...")
        conn.execute(f'DROP TABLE IF EXISTS "{TABLE_WEATHER_CLEAN}"')
        
        # Optimize types to standard numeric representation
        conn.execute(
            f"""
            CREATE TABLE "{TABLE_WEATHER_CLEAN}" AS
            SELECT
                "DATE",
                CAST(PRCP AS FLOAT) AS PRCP,
                CAST(SNOW AS FLOAT) AS SNOW,
                CAST(SNWD AS FLOAT) AS SNWD,
                CAST(TMIN AS FLOAT) AS TMIN,
                CAST(TMAX AS FLOAT) AS TMAX
            FROM "{VIEW_WEATHER_BUSINESS_RULES}"
            """
        )
        pbar.update(1)

        row_count = conn.execute(f'SELECT count(*) FROM "{TABLE_WEATHER_CLEAN}"').fetchone()[0]
        pbar.update(1)

    print("-" * 30)
    print(f"Step {TABLE_WEATHER_CLEAN} complete: {row_count:,} rows.")
    print("-" * 30)


