import pyarrow.csv as pv

from pipeline.constants.modules import WEATHER01_DOWNLOAD, WEATHER02_INGEST
from pipeline.constants.paths import WEATHER_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.services.helpers import is_schema_type_match, reset_csv_dir, write_csv, write_metadata_csv
from pipeline.services.queries import ensure_table_exists, run_with_conn


WEATHER_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = WEATHER_EDA_RESULTS_DIR / "01_schemas"


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
    column_names = list(reference_schema)
    all_match = (
        set(reference_schema) == set(database_schema)
        and all(
            is_schema_type_match(reference_schema[column_name], database_schema.get(column_name))
            for column_name in column_names
        )
    )

    reset_csv_dir(output_file)
    write_metadata_csv(
        output_file,
        {
            "file_directory": weather_csv.parent.as_posix(),
            "file_name": weather_csv.name,
            "column_count": len(reference_schema),
            "all_match": all_match,
        },
    )
    write_csv(
        output_file / "schema.csv",
        [
            {
                "column_name": column_name,
                "csv_type": reference_schema[column_name],
                "database_type": database_schema.get(column_name),
                "match": (
                    "yes"
                    if is_schema_type_match(reference_schema[column_name], database_schema.get(column_name))
                    else "no"
                ),
            }
            for column_name in column_names
        ],
    )
    print(f"EDA 01 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)


