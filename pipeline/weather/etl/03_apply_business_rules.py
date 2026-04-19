from tqdm import tqdm
from pipeline.services.queries import ensure_source_exists
from pipeline.services.tables import TABLE_WEATHER_RAW
from pipeline.services.views import VIEW_WEATHER_BUSINESS_RULES
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


def main(conn):
    with tqdm(
        total=3,
        desc="ETL 03 - business rules",
        unit="step",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        ensure_source_exists(conn, TABLE_WEATHER_RAW)
        pbar.update(1)

        print(f"Creating view '{VIEW_WEATHER_BUSINESS_RULES}'...")
        
        # We process the CSV-based strings/doubles directly with CTEs
        view_sql = f"""
        WITH cast_data AS (
            SELECT
                TRY_CAST("DATE" AS DATE) AS "DATE",
                TRY_CAST("PRCP" AS DOUBLE) AS PRCP,
                TRY_CAST("SNOW" AS DOUBLE) AS SNOW,
                TRY_CAST("SNWD" AS DOUBLE) AS SNWD,
                TRY_CAST("TMIN" AS DOUBLE) AS TMIN,
                TRY_CAST("TMAX" AS DOUBLE) AS TMAX
            FROM "{TABLE_WEATHER_RAW}"
        ),
        filtered_2019 AS (
            SELECT *
            FROM cast_data
            WHERE "DATE" >= DATE '2019-01-01' 
              AND "DATE" <= DATE '2019-12-31'
        ),
        non_null_metrics AS (
            SELECT *
            FROM filtered_2019
            WHERE PRCP IS NOT NULL
              AND SNOW IS NOT NULL
              AND SNWD IS NOT NULL
              AND TMIN IS NOT NULL
              AND TMAX IS NOT NULL
        ),
        applied_rules AS (
            SELECT *
            FROM non_null_metrics
            WHERE PRCP >= 0
              AND SNOW >= 0
              AND SNWD >= 0
              AND TMIN > -459.67
              AND TMAX > -459.67
        ),
        unit_conversions AS (
            SELECT
                "DATE",
                ROUND(PRCP * 2.54, 2) AS PRCP,
                ROUND(SNOW * 2.54, 2) AS SNOW,
                ROUND(SNWD * 2.54, 2) AS SNWD,
                ROUND((TMIN - 32.0) * 5.0 / 9.0, 2) AS TMIN,
                ROUND((TMAX - 32.0) * 5.0 / 9.0, 2) AS TMAX
            FROM applied_rules
        )
        SELECT * FROM unit_conversions
        """

        combined_query = f"""
        WITH query_stats AS (
            SELECT
                (SELECT COUNT(*) FROM "{TABLE_WEATHER_RAW}") AS input_rows,
                (SELECT COUNT(*) FROM ({view_sql})) AS output_rows
        )
        SELECT input_rows, output_rows FROM query_stats
        """
        
        input_rows, output_rows = conn.execute(combined_query).fetchone()
        pbar.update(1)

        conn.execute(
            f"""
            CREATE OR REPLACE VIEW "{VIEW_WEATHER_BUSINESS_RULES}" AS
            {view_sql}
            """
        )
        pbar.update(1)

    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0

    print("-" * 30)
    print(f"Step {VIEW_WEATHER_BUSINESS_RULES} complete.")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed:,} ({removed_pct:.2f}%)")
    print("-" * 30)


