from pipeline.constants.modules import ETL02_INGEST
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.constants.times import YEAR
from pipeline.services.helpers import percentage, reset_csv_dir, write_csv, write_metadata_csv
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


output_file = TAXI_EDA_RESULTS_DIR / "06_before_business_rules"
TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


RULES = [
    ("tpep_pickup_datetime", f"tpep_pickup_datetime >= TIMESTAMP '{YEAR}-01-01'"),
    ("tpep_pickup_datetime", f"tpep_pickup_datetime < TIMESTAMP '{YEAR + 1}-01-01'"),
    ("tpep_dropoff_datetime", f"tpep_dropoff_datetime >= TIMESTAMP '{YEAR}-01-01'"),
    ("tpep_dropoff_datetime", f"tpep_dropoff_datetime < TIMESTAMP '{YEAR + 1}-01-01'"),
    ("trip_datetime", "tpep_pickup_datetime < tpep_dropoff_datetime"),
    ("VendorID", "VendorID IN (1, 2)"),
    ("passenger_count", "passenger_count BETWEEN 1 AND 5"),
    ("RatecodeID", "RatecodeID BETWEEN 1 AND 6"),
    ("store_and_fwd_flag", "store_and_fwd_flag IN ('Y', 'N')"),
    ("PULocationID", "PULocationID BETWEEN 1 AND 263"),
    ("DOLocationID", "DOLocationID BETWEEN 1 AND 263"),
    ("payment_type", "payment_type BETWEEN 1 AND 4"),
    ("congestion_surcharge", "COALESCE(congestion_surcharge, 0.0) IN (0.0, 0.75, 2.5)"),
    ("trip_distance", "trip_distance > 0.0"),
    ("fare_amount", "(CASE WHEN extra >= 2.5 THEN fare_amount + 2.5 ELSE fare_amount END) > 0.0"),
    ("extra", "(CASE WHEN extra >= 2.5 THEN extra - 2.5 ELSE extra END) IN (0.0, 0.5, 1.0)"),
    ("mta_tax", "mta_tax = 0.5"),
    ("tip_amount", "tip_amount >= 0.0"),
    ("tolls_amount", "tolls_amount >= 0.0"),
    ("improvement_surcharge", "improvement_surcharge = 0.3"),
    ("total_amount", "total_amount >= 0.0"),
    ("tip_payment_type", "NOT (payment_type IN (2, 3, 4) AND tip_amount > 0.0)"),
]


def main(conn):
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)

    rule_aliases = [f"r{i}" for i in range(len(RULES))]
    fail_exprs = [
        f"CASE WHEN ({cond_sql}) THEN 0 ELSE 1 END"
        for _, cond_sql in RULES
    ]
    fail_sum = " + ".join(f"({fail_expr})" for fail_expr in fail_exprs)
    invalid_select = ",\n            ".join(
        f"SUM({fail_expr}) AS invalid_{alias}"
        for alias, fail_expr in zip(rule_aliases, fail_exprs)
    )
    exclusive_select = ",\n            ".join(
        f"SUM(CASE WHEN ({fail_expr}) = 1 AND ({fail_sum}) = 1 THEN 1 ELSE 0 END) AS exclusive_{alias}"
        for alias, fail_expr in zip(rule_aliases, fail_exprs)
    )

    sql = f"""
        SELECT
            COUNT(*) AS raw_row_count,
            SUM(CASE WHEN ({fail_sum}) = 0 THEN 1 ELSE 0 END) AS clean_row_count,
            SUM(CASE WHEN ({fail_sum}) > 0 THEN 1 ELSE 0 END) AS removed_row_count,
            {invalid_select},
            {exclusive_select}
        FROM {quote_identifier(TABLE_TAXI_RAW)}
    """

    print(f"Analyzing business rules impact on {TABLE_TAXI_RAW}...")
    row = conn.execute(sql).fetchone()
    raw_row_count = int(row[0] or 0)
    clean_row_count = int(row[1] or 0)
    removed_row_count = int(row[2] or 0)

    idx = 3
    invalid_by_rule = {}
    for alias in rule_aliases:
        invalid_by_rule[alias] = int(row[idx] or 0)
        idx += 1

    exclusive_by_rule = {}
    for alias in rule_aliases:
        exclusive_by_rule[alias] = int(row[idx] or 0)
        idx += 1

    rules = []
    for alias, (column_name, rule_name) in zip(rule_aliases, RULES):
        invalid_row_count = invalid_by_rule[alias]
        exclusive_removed_row_count = exclusive_by_rule[alias]
        shared_removed_row_count = invalid_row_count - exclusive_removed_row_count
        rules.append(
            {
                "rule_name": rule_name,
                "column_name": column_name,
                "invalid_count": invalid_row_count,
                "exclusive_removed_count": exclusive_removed_row_count,
                "shared_removed_count": shared_removed_row_count,
                "invalid_percentage": percentage(invalid_row_count, raw_row_count),
                "exclusive_removed_percentage": percentage(exclusive_removed_row_count, raw_row_count),
                "shared_removed_percentage": percentage(shared_removed_row_count, raw_row_count),
            }
        )

    rules.sort(key=lambda item: -item["exclusive_removed_count"])

    reset_csv_dir(output_file)
    write_metadata_csv(
        output_file,
        keys=[
            "raw_count",
            "clean_count",
            "removed_count",
            "removed_percentage",
            "rule_count",
        ],
        values=[
            raw_row_count,
            clean_row_count,
            removed_row_count,
            percentage(removed_row_count, raw_row_count),
            len(rules),
        ],
    )
    write_csv(output_file / "rules.csv", rules)
    print(f"EDA 06 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
