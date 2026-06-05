import csv

from pipeline.constants.modules import WEATHER02_INGEST
from pipeline.constants.paths import WEATHER_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.constants.times import YEAR
from pipeline.constants.unique_settings import POSITIVE_BIN_COUNT
from pipeline.services.helpers import reset_csv_dir, write_high_unique_csvs, write_metadata_csv
from pipeline.services.queries import (
    build_high_unique_columns,
    calculate_valid_type_percentages,
    ensure_table_exists,
    get_column_data_types,
    quote_identifier,
    run_with_conn,
)


WEATHER_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = WEATHER_EDA_RESULTS_DIR / "03_high_duplicates"
profile_file = WEATHER_EDA_RESULTS_DIR / "02_low_duplicates"



def get_high_unique_column_names(column_names: list[str]) -> list[str]:
    profile_dir = profile_file.with_suffix("")
    high_unique_csv = profile_dir / "high_unique_columns.csv"
    if high_unique_csv.exists():
        with high_unique_csv.open("r", encoding="utf-8", newline="") as file:
            high_unique_columns = [
                str(row["column_name"])
                for row in csv.DictReader(file)
                if row.get("column_name")
            ]
        if high_unique_columns:
            return [column_name for column_name in column_names if column_name in set(high_unique_columns)]
    return [column_name for column_name in column_names if column_name in {"DATE", "PRCP"}]


def build_filter(conn, source_table_quoted: str) -> dict:
    column_quoted = quote_identifier("DATE")
    row_count, unique_count, min_date, max_date, unique_count_in_year = conn.execute(
        f"""
        WITH typed AS (
            SELECT TRY_CAST({column_quoted} AS DATE) AS v
            FROM {source_table_quoted}
        )
        SELECT
            COUNT(*) AS row_count,
            COUNT(DISTINCT v) AS unique_count,
            MIN(v) AS min_date,
            MAX(v) AS max_date,
            COUNT(DISTINCT v) AS unique_count_in_year
        FROM typed
        WHERE v >= DATE '{YEAR}-01-01'
          AND v < DATE '{YEAR + 1}-01-01'
        """
    ).fetchone()
    return {
        "filter_year": YEAR,
        "row_count": int(row_count or 0),
        "unique_count": int(unique_count or 0),
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "is_unique": "yes" if row_count == unique_count else "no",
        "full_year": "yes" if int(unique_count_in_year or 0) == 365 else "no",
    }


def main(conn):
    ensure_table_exists(conn, TABLE_WEATHER_RAW, WEATHER02_INGEST.create_weather_raw_table)

    weather_raw_quoted = quote_identifier(TABLE_WEATHER_RAW)
    row_count = int(conn.execute(f"SELECT count(*) FROM {weather_raw_quoted}").fetchone()[0] or 0)

    column_type_rows = conn.execute(f"DESCRIBE {weather_raw_quoted}").fetchall()
    column_names = [str(row[0]) for row in column_type_rows]

    high_unique_column_names = get_high_unique_column_names(column_names)
    high_unique_data_types = get_column_data_types(column_type_rows, high_unique_column_names)
    high_unique_valid_type_percentages = calculate_valid_type_percentages(
        conn,
        weather_raw_quoted,
        high_unique_column_names,
        high_unique_data_types,
        row_count,
    )
    high_unique_columns = build_high_unique_columns(
        conn,
        TABLE_WEATHER_RAW,
        high_unique_column_names,
        high_unique_data_types,
        high_unique_valid_type_percentages,
        row_count,
        desc="Weather EDA 03 - profiling high-duplicate columns",
        temp_prefix="tmp_weather_eda03",
    )
    for high_unique_column in high_unique_columns:
        if high_unique_column.get("column_name") == "DATE":
            high_unique_column["filter"] = build_filter(conn, weather_raw_quoted)
            break

    reset_csv_dir(output_file)
    write_metadata_csv(
        output_file,
        {
            "tail_ratio": "1/101",
            "positive_bin_count": POSITIVE_BIN_COUNT,
            "high_unique_column_count": len(high_unique_columns),
        },
    )
    write_high_unique_csvs(output_file, high_unique_columns)
    print(f"EDA 03 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)





