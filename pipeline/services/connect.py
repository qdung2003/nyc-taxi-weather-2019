import os, duckdb, psutil
from contextlib import contextmanager
from pipeline.services.paths import DUCKDB_TEMP_DIR, WAREHOUSE_DB_FILE


class DuckDBConnectionManager:
    def __init__(self):
        self._connection = None
        self._config = None

    @contextmanager
    def get_connection(self, ensure_dirs: bool = True, load_parquet: bool = True):
        current_config = (ensure_dirs, load_parquet)

        # Reuse connection nếu config giống
        if self._connection is not None and self._config == current_config:
            try:
                self._connection.execute("SELECT 1")
                yield self._connection
                return
            except Exception:
                self._connection.close()
                self._connection = None
                self._config = None

        # Tạo connection mới
        conn = connect_warehouse(
            ensure_dirs=ensure_dirs,
            load_parquet=load_parquet
        )
        self._connection = conn
        self._config = current_config

        try:
            yield conn
        except Exception:
            conn.close()
            self._connection = None
            self._config = None
            raise

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._config = None


def get_warehouse_config() -> tuple[int, int, str]:
    cpu_total = os.cpu_count() or 1
    threads = max(1, cpu_total // 2)

    try:
        ram_bytes = int(psutil.virtual_memory().total)
        memory_limit = max(1, int(ram_bytes * 0.5))
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_idx = 0

        while memory_limit >= 1024 and unit_idx < len(units) - 1:
            memory_limit /= 1024
            unit_idx += 1

        memory_limit = int(memory_limit)
        memory_unit = units[unit_idx]
    except Exception:
        memory_limit = 4
        memory_unit = "GB"

    return threads, memory_limit, memory_unit


def connect_warehouse(
    ensure_dirs: bool = True,
    load_parquet: bool = True,
) -> duckdb.DuckDBPyConnection:
    if ensure_dirs:
        WAREHOUSE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        DUCKDB_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(WAREHOUSE_DB_FILE.as_posix())
    threads, memory_limit, memory_unit = get_warehouse_config()
    checkpoint_value = max(1, memory_limit // 2)

    conn.execute(f"SET threads = {threads}")
    conn.execute(f"SET memory_limit = '{memory_limit}{memory_unit}'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(f"SET temp_directory = '{DUCKDB_TEMP_DIR.as_posix()}'")
    conn.execute(f"SET checkpoint_threshold = '{checkpoint_value}{memory_unit}'")

    if load_parquet:
        conn.execute("LOAD 'parquet';")

    return conn


