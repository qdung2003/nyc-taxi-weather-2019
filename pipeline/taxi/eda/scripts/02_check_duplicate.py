import json
from tqdm import tqdm
from pipeline.services.helpers import round_if_needed
from pipeline.services.queries import quote_identifier, connect_and_check, calculate_correct_type_percent
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.paths import TAXI_DIR, WAREHOUSE_DB_FILE


MAX_UNIQUE_VALUES = 300
output_dir = TAXI_DIR / "eda" / "results"
output_file = output_dir / "02_check_duplicate.json"
output_dir.mkdir(parents=True, exist_ok=True)


def main(conn):
    taxi_raw_quoted = quote_identifier(TABLE_TAXI_RAW)
    column_type_rows = conn.execute(
        f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{TABLE_TAXI_RAW}'
        ORDER BY ordinal_position
        """
    ).fetchall()
    columns = [row[0] for row in column_type_rows]
    columns_types = {row[0]: str(row[1]) for row in column_type_rows}
    total_rows = conn.execute(
        f"SELECT count(*) FROM {taxi_raw_quoted}"
    ).fetchone()[0]

    print(f"Input table: {TABLE_TAXI_RAW}")
    print(f"Total rows: {total_rows:,}")
    print("Phase 1/3: Computing unique_count per column...")

    columns_uniques = {}
    for column in tqdm(columns, desc="Phase 1 unique_count", unit="col", leave=True):
        column_quoted = quote_identifier(column)
        unique_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT {column_quoted}
                FROM {taxi_raw_quoted}
                LIMIT {MAX_UNIQUE_VALUES + 1}
            )
            """
        ).fetchone()[0]
        columns_uniques[column] = int(unique_count or 0)


    low_cardinality_columns = []
    high_cardinality_columns = []
    for column in columns:
        unique_count = columns_uniques[column]
        if unique_count <= MAX_UNIQUE_VALUES:
            low_cardinality_columns.append(column)
        else:
            high_cardinality_columns.append(column)


    print(
        "Phase 2/3: Counting values for low-cardinality columns "
        f"({len(low_cardinality_columns)}/{len(columns)})..."
    )
    
    # Batch process low cardinality columns
    low_duplicate_columns = []
    
    # First, batch calculate correct_type_percent for all low cardinality columns
    type_percent_query = """
    SELECT 
        column_name,
        correct_type_percent
    FROM (
    """
    
    type_percent_clauses = []
    for column in low_cardinality_columns:
        column_quoted = quote_identifier(column)
        type_value = columns_types.get(column, "")
        type_percent_clauses.append(
            f"""
            SELECT 
                '{column}' as column_name,
                ROUND(COUNT(*) FILTER (
                    WHERE {column_quoted} IS NULL OR 
                    TRY_CAST({column_quoted} AS {type_value}) IS NOT NULL
                ) * 100.0 / {total_rows}, 2) as correct_type_percent
            FROM {taxi_raw_quoted}
            """
        )
    
    type_percent_query += " UNION ALL ".join(type_percent_clauses) + """
    )
    """
    
    type_percent_rows = conn.execute(type_percent_query).fetchall()
    type_percent_map = {row[0]: row[1] for row in type_percent_rows}
    
    # Now process each column for value counts
    for column in tqdm(
        low_cardinality_columns,
        desc="Phase 2 value_counts",
        unit="col",
        leave=True,
    ):
        column_quoted = quote_identifier(column)
        rows = conn.execute(
            f"""
            SELECT {column_quoted}, COUNT(*)
            FROM {taxi_raw_quoted}
            GROUP BY {column_quoted}
            """
        ).fetchall()
        sorted_rows = sorted(rows, key=lambda x: (x[0] is None, str(x[0])))
        
        values = []
        counts = []
        percentages = []
        for value, count in sorted_rows:
            values.append(round_if_needed(value))
            counts.append(count)
            percentages.append(
                round_if_needed((count / total_rows * 100))
            )
        
        type_value = columns_types.get(column, "")
        unique_count = columns_uniques[column]
        correct_type_percent = type_percent_map.get(column, 0.0)

        low_duplicate_columns.append(
            {
                "column_name": column,
                "type_value": type_value,
                "unique_count": unique_count,
                "correct_type_percent": correct_type_percent,
                "values": values,
                "counts": counts,
                "percentages": percentages,
            }
        )


    # Batch calculate correct_type_percent for high cardinality columns
    high_duplicate_columns = []
    
    if high_cardinality_columns:
        high_type_percent_query = """
        SELECT 
            column_name,
            correct_type_percent
        FROM (
        """
        
        high_type_percent_clauses = []
        for column in high_cardinality_columns:
            column_quoted = quote_identifier(column)
            type_value = columns_types.get(column, "")
            high_type_percent_clauses.append(
                f"""
                SELECT 
                    '{column}' as column_name,
                    ROUND((COUNT(*) FILTER (
                        WHERE {column_quoted} IS NULL OR 
                        TRY_CAST({column_quoted} AS {type_value}) IS NOT NULL
                    ) * 100.0 / {total_rows}), 2) as correct_type_percent
                FROM {taxi_raw_quoted}
                """
            )
        
        high_type_percent_query += " UNION ALL ".join(high_type_percent_clauses) + """
        )
        """
        
        high_type_percent_rows = conn.execute(high_type_percent_query).fetchall()
        high_type_percent_map = {row[0]: row[1] for row in high_type_percent_rows}
        
        for column in high_cardinality_columns:
            type_value = columns_types.get(column, "")
            correct_type_percent = high_type_percent_map.get(column, 0.0)
            
            high_duplicate_columns.append(
                {
                    "column_name": column,
                    "type_value": type_value,
                    "correct_type_percent": correct_type_percent,
                }
            )


    print("Phase 3/3: Writing JSON report...")
    report = {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_TAXI_RAW,
        "max_unique_values": MAX_UNIQUE_VALUES,
        "total_rows": total_rows,
        "low_duplicate_columns": low_duplicate_columns,
        "high_duplicate_columns": high_duplicate_columns,
    }

    output_file.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ), encoding="utf-8"
    )
    print(f"Saved report: {output_file}")
