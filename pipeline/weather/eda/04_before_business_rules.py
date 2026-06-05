from pipeline.constants.modules import WEATHER02_INGEST
from pipeline.constants.paths import WEATHER_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_WEATHER_RAW
from pipeline.constants.times import YEAR
from pipeline.services.helpers import percentage, reset_csv_dir, write_rules_csvs
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


WEATHER_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = WEATHER_EDA_RESULTS_DIR / "04_before_business_rules"

RULES = [
    ("DATE", f"DATE >= {YEAR}-01-01", f'"DATE" >= DATE \'{YEAR}-01-01\''),
    ("DATE", f"DATE < {YEAR + 1}-01-01", f'"DATE" < DATE \'{YEAR + 1}-01-01\''),
    ("PRCP", "PRCP >= 0", '"PRCP" >= 0'),
    ("SNOW", "SNOW >= 0", '"SNOW" >= 0'),
    ("SNWD", "SNWD >= 0", '"SNWD" >= 0'),
    ("TMIN", "TMIN > -459.67", '"TMIN" > -459.67'),
    ("TMAX", "TMAX > -459.67", '"TMAX" > -459.67'),
]


def main(conn):
    ensure_table_exists(conn, TABLE_WEATHER_RAW, WEATHER02_INGEST.create_weather_raw_table)

    rule_aliases = [f"r{i}" for i in range(len(RULES))]
    fail_exprs = [
        f"CASE WHEN ({cond_sql}) THEN 0 ELSE 1 END"
        for _, _, cond_sql in RULES
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
        FROM {quote_identifier(TABLE_WEATHER_RAW)}
    """

    print(f"Analyzing business rules impact on {TABLE_WEATHER_RAW}...")
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
    for alias, (column_name, rule_name, _cond_sql) in zip(rule_aliases, RULES):
        invalid_row_count = invalid_by_rule[alias]
        exclusive_removed_row_count = exclusive_by_rule[alias]
        shared_removed_row_count = invalid_row_count - exclusive_removed_row_count
        rules.append(
            {
                "rule_name": rule_name,
                "column_name": column_name,
                "invalid_row_count": invalid_row_count,
                "exclusive_removed_row_count": exclusive_removed_row_count,
                "shared_removed_row_count": shared_removed_row_count,
                "invalid_row_percentage": percentage(invalid_row_count, raw_row_count),
                "exclusive_removed_percentage": percentage(exclusive_removed_row_count, raw_row_count),
                "shared_removed_percentage": percentage(shared_removed_row_count, raw_row_count),
            }
        )

    rules.sort(key=lambda item: -item["exclusive_removed_row_count"])

    reset_csv_dir(output_file)
    write_rules_csvs(
        output_file,
        {
            "raw_row_count": raw_row_count,
            "clean_row_count": clean_row_count,
            "removed_row_count": removed_row_count,
            "removed_percentage": percentage(removed_row_count, raw_row_count),
            "rule_count": len(rules),
        },
        rules,
    )
    print(f"EDA 04 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)



