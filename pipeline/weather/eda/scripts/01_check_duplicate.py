import json
from tqdm import tqdm
from pipeline.services.helpers import round_if_needed
from pipeline.services.queries import quote_identifier
from pipeline.services.tables import TABLE_WEATHER_RAW
from pipeline.services.paths import WEATHER_DIR, WAREHOUSE_DB_FILE


MAX_UNIQUE_VALUES = 300
output_dir = WEATHER_DIR / "eda" / "results"
output_file = output_dir / "01_check_duplicate.json"
output_dir.mkdir(parents=True, exist_ok=True)


def main(conn):

    weather_raw_quoted = quote_identifier(TABLE_WEATHER_RAW)
    column_type_rows = conn.execute(
        f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{TABLE_WEATHER_RAW}'
        ORDER BY ordinal_position
        """
    ).fetchall()
    columns = [row[0] for row in column_type_rows]
    columns_types = {row[0]: str(row[1]) for row in column_type_rows}
    total_rows = conn.execute(
        f"SELECT count(*) FROM {weather_raw_quoted}"
    ).fetchone()[0]

    print(f"Input table: {TABLE_WEATHER_RAW}")
    print(f"Total rows: {total_rows:,}")
    print("Phase 1/3: Computing unique_count per column...")

    columns_uniques = {}
    for column in tqdm(columns, desc="Phase 1 unique_count", unit="col", leave=True):
        column_quoted = quote_identifier(column)
        unique_count_row = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT {column_quoted}
                FROM {weather_raw_quoted}
                LIMIT {MAX_UNIQUE_VALUES + 1}
            )
            """
        ).fetchone()
        columns_uniques[column] = int(unique_count_row[0] or 0)

    low_cardinality_columns = []
    high_cardinality_columns = []
    for column in columns:
        if columns_uniques[column] <= MAX_UNIQUE_VALUES:
            low_cardinality_columns.append(column)
        else:
            high_cardinality_columns.append(column)

    print(f"Phase 2/3: Analyzing columns...")
    
    # Calculate correct_type_percent for all columns
    type_percent_map = {}
    for column in columns:
        column_quoted = quote_identifier(column)
        type_value = columns_types.get(column, "")
        correct_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {weather_raw_quoted}
            WHERE {column_quoted} IS NULL OR TRY_CAST({column_quoted} AS {type_value}) IS NOT NULL
            """
        ).fetchone()[0]
        type_percent_map[column] = round_if_needed(correct_count * 100.0 / total_rows if total_rows else 0)

    low_duplicate_columns = []
    for column in tqdm(low_cardinality_columns, desc="Phase 2 low-cardinality", unit="col", leave=True):
        column_quoted = quote_identifier(column)
        rows = conn.execute(
            f"""
            SELECT {column_quoted}, COUNT(*)
            FROM {weather_raw_quoted}
            GROUP BY {column_quoted}
            """
        ).fetchall()
        # Sort values: Null first, then by string representation
        sorted_rows = sorted(rows, key=lambda x: (x[0] is None, str(x[0])))
        
        values = []
        counts = []
        percentages = []
        for val, count in sorted_rows:
            values.append(round_if_needed(val))
            counts.append(count)
            percentages.append(round_if_needed(count * 100.0 / total_rows if total_rows else 0))
        
        low_duplicate_columns.append({
            "column_name": column,
            "type_value": columns_types[column],
            "unique_count": columns_uniques[column],
            "correct_type_percent": type_percent_map[column],
            "values": values,
            "quantity": counts, # Keep key same as original for 03 consistency
            "quantity_percent": percentages,
        })

    high_duplicate_columns = [
        {
            "column_name": col,
            "type_value": columns_types[col],
            "correct_type_percent": type_percent_map[col],
        }
        for col in high_cardinality_columns
    ]

    print("Phase 3/3: Writing JSON report...")
    report = {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_WEATHER_RAW,
        "row_count": total_rows,
        "column_count": len(columns),
        "max_unique_values": MAX_UNIQUE_VALUES,
        "low_duplicate_columns": low_duplicate_columns,
        "high_duplicate_columns": high_duplicate_columns,
    }

    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")
