import json
from pipeline.services.queries import quote_identifier
from pipeline.services.tables import TABLE_WEATHER_RAW
from pipeline.services.paths import WEATHER_DIR, WAREHOUSE_DB_FILE


output_dir = WEATHER_DIR / "eda" / "results"
output_file = output_dir / "02_check_date.json"


def main(conn) -> None:

    weather_raw_quoted = quote_identifier(TABLE_WEATHER_RAW)
    column_name = "DATE"
    column_quoted = quote_identifier(column_name)

    print(f"Analyzing {column_name} in {TABLE_WEATHER_RAW}...")
    
    stats = conn.execute(
        f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT {column_quoted}) as unique_count,
            MIN({column_quoted}) as min_date,
            MAX({column_quoted}) as max_date
        FROM {weather_raw_quoted}
        """
    ).fetchone()

    total_rows, unique_count, min_date, max_date = stats
    
    # Check for uniqueness (no duplicates)
    is_unique = (unique_count == total_rows)
    
    # Check for full year 2019 (365 days) - Note: This script checks raw data which has more years
    # So we check if 2019-01-01 and 2019-12-31 exist and have 365 unique dates in between
    year_2019_stats = conn.execute(
        f"""
        SELECT COUNT(DISTINCT {column_quoted})
        FROM {weather_raw_quoted}
        WHERE {column_quoted} >= '2019-01-01' AND {column_quoted} <= '2019-12-31'
        """
    ).fetchone()
    
    count_2019 = year_2019_stats[0]
    is_full_year_2019 = (count_2019 == 365)

    report = {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_WEATHER_RAW,
        "date_dimension_check": {
            "column_name": column_name,
            "total_rows": total_rows,
            "unique_count": unique_count,
            "min_date": min_date.strftime("%Y-%m-%d") if min_date else None,
            "max_date": max_date.strftime("%Y-%m-%d") if max_date else None,
            "is_unique": "yes" if is_unique else "no",
            "full_year_2019": "yes" if is_full_year_2019 else "no",
            "unique_count_2019": count_2019
        }
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved report: {output_file}")
