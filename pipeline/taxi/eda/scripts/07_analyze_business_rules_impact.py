import json
from tqdm import tqdm
from pipeline.services.helpers import percent
from pipeline.services.queries import quote_identifier
from pipeline.services.queries import connect_and_check
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.paths import WAREHOUSE_DB_FILE, TAXI_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


output_dir = TAXI_DIR / "eda" / "results"
output_file = output_dir / "07_business_rules_impact.json"
output_dir.mkdir(parents=True, exist_ok=True)


RULES = [
    ("VendorID_in_1_2", "VendorID IN (1, 2)"),
    ("passenger_count_in_1_5", "passenger_count BETWEEN 1 AND 5"),
    ("RatecodeID_in_1_6", "RatecodeID BETWEEN 1 AND 6"),
    ("store_and_fwd_flag_in_Y_N", "store_and_fwd_flag IN ('Y', 'N')"),
    ("PULocationID_in_1_263", "PULocationID BETWEEN 1 AND 263"),
    ("DOLocationID_in_1_263", "DOLocationID BETWEEN 1 AND 263"),
    ("payment_type_in_1_4", "payment_type BETWEEN 1 AND 4"),
    ("congestion_surcharge_in_0_0_75_2_5", "congestion_norm IN (0.0, 0.75, 2.5)"),
    ("trip_distance_gt_0", "trip_distance > 0.0"),
    ("fare_amount_gt_0", "fare_norm > 0.0"),
    ("extra_in_set_0_0_5_1_after_normalize", "extra_norm IN (0.0, 0.5, 1.0)"),
    ("mta_tax_eq_0_5", "mta_tax = 0.5"),
    ("tip_amount_ge_0", "tip_amount >= 0.0"),
    ("tolls_amount_ge_0", "tolls_amount >= 0.0"),
        mininterval=TQDM_MIN_INTERVAL,
    ) as pbar:
        pbar.update(1)

    fail_defs = ",\n            ".join(
        f"CASE WHEN ({cond}) THEN 0 ELSE 1 END AS fail_{name}" for name, cond in RULES
    )
    fail_sum = " + ".join(f"fail_{name}" for name, _ in RULES)
    invalid_select = ",\n            ".join(
        f"SUM(fail_{name}) AS invalid_{name}" for name, _ in RULES
    )
    exclusive_select = ",\n            ".join(
        f"SUM(CASE WHEN fail_{name} = 1 AND fail_count = 1 THEN 1 ELSE 0 END) AS exclusive_{name}"
        for name, _ in RULES
    )

    sql = f"""
        WITH normalized AS (
            SELECT
                *,
                CASE WHEN extra >= 2.5 THEN fare_amount + 2.5 ELSE fare_amount END AS fare_norm,
                CASE WHEN extra >= 2.5 THEN extra - 2.5 ELSE extra END AS extra_norm,
                COALESCE(congestion_surcharge, 0.0) AS congestion_norm
            FROM {quote_identifier(TABLE_TAXI_RAW)}
        ),
        flags AS (
            SELECT
                *,
                {fail_defs}
            FROM normalized
        ),
        scored AS (
            SELECT
                *,
                ({fail_sum}) AS fail_count
            FROM flags
        )
        SELECT
            COUNT(*) AS total_input_rows,
            SUM(CASE WHEN fail_count = 0 THEN 1 ELSE 0 END) AS total_clean_rows,
            SUM(CASE WHEN fail_count > 0 THEN 1 ELSE 0 END) AS total_removed_rows,
            {invalid_select},
            {exclusive_select}
        FROM scored
    """

    row = conn.execute(sql).fetchone()
    total_input_rows = int(row[0] or 0)
    total_clean_rows = int(row[1] or 0)
    total_removed_rows = int(row[2] or 0)

    idx = 3
    invalid_by_rule = {}
    for name, _ in RULES:
        invalid_by_rule[name] = int(row[idx] or 0)
        idx += 1

    exclusive_by_rule = {}
    for name, _ in RULES:
        exclusive_by_rule[name] = int(row[idx] or 0)
        idx += 1

    rules_report = []
    for name, _ in RULES:
        invalid_rows = invalid_by_rule[name]
        exclusive_rows = exclusive_by_rule[name]
        shared_rows = invalid_rows - exclusive_rows
        rules_report.append(
            {
                "rule_name": name,
                "invalid_rows": invalid_rows,
                "invalid_percent_on_input": percent(invalid_rows, total_input_rows),
                "removed_exclusive_rows": exclusive_rows,
                "removed_exclusive_percent_on_input": percent(exclusive_rows, total_input_rows),
                "removed_shared_rows": shared_rows,
                "removed_shared_percent_on_input": percent(shared_rows, total_input_rows),
            }
        )

    rules_report.sort(key=lambda item: -item["removed_exclusive_rows"])

    report = {
        "warehouse_db_file": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_TAXI_RAW,
        "scenario_assumptions": {
            "cleaning_flow": "single_stage_clean_with_in-row_transforms",
            "rules": "congestion null->0; normalize extra>=2.5 => extra-2.5 and fare+2.5; apply discrete+money rules in one pass",
        },
        "summary": {
            "total_input_rows": total_input_rows,
            "total_clean_rows": total_clean_rows,
            "total_removed_rows": total_removed_rows,
            "total_removed_percent": percent(total_removed_rows, total_input_rows),
        },
        "rules": rules_report,
    }
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")
