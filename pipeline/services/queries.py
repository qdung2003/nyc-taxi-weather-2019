"""Helpers for reading DuckDB tables/views in Arrow chunks for EDA scripts."""
import math
import pyarrow as pa
from typing import Iterator
from pipeline.services.connect import connect_warehouse
from pipeline.services.helpers import round_if_needed
from pipeline.services.paths import WAREHOUSE_DB_FILE


def quote_identifier(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def get_schema(conn, source_name: str) -> pa.Schema:
    query = f'SELECT * FROM {quote_identifier(source_name)} LIMIT 0'
    return conn.execute(query).to_arrow_table().schema


def get_total_rows(conn, source_name: str) -> int:
    query = f'SELECT count(*) FROM {quote_identifier(source_name)}'
    return int(conn.execute(query).fetchone()[0] or 0)

def get_chunk_count(total_rows: int, chunk_size: int) -> int:
    return math.ceil(total_rows / chunk_size) if total_rows else 0


def iter_arrow_chunks(
    conn,
    source_name: str,
    *,
    chunk_size: int,
    columns: list[str] | None = None,
) -> Iterator[pa.Table]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    selected = "*"
    if columns:
        selected = ", ".join(quote_identifier(c) for c in columns)

    base = f"SELECT {selected} FROM {quote_identifier(source_name)}"
    total_rows = get_total_rows(conn, source_name)
    for offset in range(0, total_rows, chunk_size):
        query = f"{base} LIMIT {chunk_size} OFFSET {offset}"
        yield conn.execute(query).to_arrow_table()


def connect_and_check(source_name: str, expected_type: str):
    type_map = {
        "table": "BASE TABLE",
        "view": "VIEW"
    }

    if expected_type not in type_map:
        raise ValueError(f"Invalid expected_type. Must be either 'table' or 'view', got '{expected_type}'")

    conn = connect_warehouse()
    
    rows = conn.execute(f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_type = '{type_map[expected_type]}'
        """).fetchall()
        
    known_sources = {row[0] for row in rows}
    if source_name not in known_sources:
        db_path = WAREHOUSE_DB_FILE.as_posix()
        raise SystemExit(f"Missing {expected_type} '{source_name}' in {db_path}.")
        
    # Return connection for caller to manage
    return conn


def ensure_source_exists(conn, source_name: str) -> None:
    """Check if source exists in database."""
    rows = conn.execute(f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = '{source_name}'
        """).fetchall()
    if not rows:
        db_path = WAREHOUSE_DB_FILE.as_posix()
        raise SystemExit(f"""Missing table '{source_name}' in {db_path}.""")


def calculate_correct_type_percent(
    conn, 
    taxi_raw_quoted: str,
    column_quoted: str,
    type_value: str,
    total_rows: int
):
    if total_rows == 0:
        return 100.0

    valid_count = conn.execute(
        f"""
        SELECT COUNT(*) FILTER (
            WHERE {column_quoted} IS NULL OR 
            TRY_CAST({column_quoted} AS {type_value}) IS NOT NULL
        )
        FROM {taxi_raw_quoted}
        """
    ).fetchone()[0]

    return round_if_needed((valid_count / total_rows) * 100)