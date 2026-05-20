import pyarrow.csv as pv

from pipeline.constants.modules import WEATHER01_DOWNLOAD, WEATHER02_INGEST
from pipeline.constants.paths import WEATHER_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.services.helpers import write_json_compact
from pipeline.services.queries import ensure_table_exists, run_with_conn


WEATHER_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = WEATHER_EDA_RESULTS_DIR / "01_schemas.json"


def read_csv_schema(csv_path) -> dict[str, str]:
    table = pv.read_csv(csv_path)
    return {
        field.name: str(field.type)
        for field in table.schema
    }


def main(conn):
    weather_csv = WEATHER01_DOWNLOAD.ensure_weather_raw_file()
    ensure_table_exists(conn, TABLE_WEATHER_RAW, WEATHER02_INGEST.create_weather_raw_table)

    reference_schema = read_csv_schema(weather_csv)
    database_rows = conn.execute(f'DESCRIBE "{TABLE_WEATHER_RAW}"').fetchall()
    database_schema = {str(row[0]): str(row[1]) for row in database_rows}

    report = {
        "file_directory": weather_csv.parent.as_posix(),
        "file_name": weather_csv.name,
        "column_count": len(reference_schema),
        "reference_schema": reference_schema,
        "database_schema": database_schema,
    }
    write_json_compact(output_file, report)
    print(f"EDA 01 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
