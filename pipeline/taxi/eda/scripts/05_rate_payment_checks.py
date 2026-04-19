import json
from tqdm import tqdm
from pipeline.services.helpers import percent
from pipeline.services.queries import quote_identifier
from pipeline.services.queries import connect_and_check
from pipeline.services.tables import TABLE_TAXI_RAW
from pipeline.services.paths import WAREHOUSE_DB_FILE, TAXI_DIR
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "05_rate_payment_checks.json"
CLEAN_FLOW = "pre_etl_03_business_rules_analysis_on_taxi_raw"

ZERO_MONEY_COLUMNS = [
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
]


def main(conn):

    total_rows = int(conn.execute(f"SELECT count(*) FROM {quote_identifier(TABLE_TAXI_RAW)}").fetchone()[0] or 0)

    pay_rows = conn.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE payment_type = 1) AS p1_total,
            COUNT(*) FILTER (WHERE payment_type = 2) AS p2_total,
            COUNT(*) FILTER (WHERE payment_type = 3) AS p3_total,
            COUNT(*) FILTER (WHERE payment_type = 4) AS p4_total,
            COUNT(*) FILTER (WHERE payment_type = 1 AND tip_amount = 0.0) AS p1_tip_zero,
            COUNT(*) FILTER (WHERE payment_type = 2 AND tip_amount = 0.0) AS p2_tip_zero,
            COUNT(*) FILTER (WHERE payment_type = 3 AND tip_amount = 0.0) AS p3_tip_zero,
            COUNT(*) FILTER (WHERE payment_type = 4 AND tip_amount = 0.0) AS p4_tip_zero
        FROM {quote_identifier(TABLE_TAXI_RAW)}
        """
    ).fetchone()

    payment_totals = {1: int(pay_rows[0] or 0), 2: int(pay_rows[1] or 0), 3: int(pay_rows[2] or 0), 4: int(pay_rows[3] or 0)}
    check1_tip_zero_by_payment = {1: int(pay_rows[4] or 0), 2: int(pay_rows[5] or 0), 3: int(pay_rows[6] or 0), 4: int(pay_rows[7] or 0)}

    # Batch query for all money columns to reduce database round trips
    batch_query_clauses = []
    for col in ZERO_MONEY_COLUMNS:
        col_quoted = quote_identifier(col)
        batch_query_clauses.append(
            f"""
            SELECT 
                '{col}' as column_name,
                COUNT(*) FILTER (WHERE payment_type = 3 AND {col_quoted} = 0.0) AS c2,
                COUNT(*) FILTER (WHERE payment_type = 4 AND {col_quoted} = 0.0) AS c3
            FROM {quote_identifier(TABLE_TAXI_RAW)}
            """
        )
    
    batch_query = " UNION ALL ".join(batch_query_clauses)
    
    with tqdm(
        total=1,
        desc="EDA 05 - money columns",
        unit="batch",
        disable=TQDM_DISABLE,
        leave=True,
        mininterval=TQDM_MIN_INTERVAL,
    ):
        batch_results = conn.execute(batch_query).fetchall()
    
    check2_zero_by_col = {}
    check3_zero_by_col = {}
    for col_name, c2, c3 in batch_results:
        check2_zero_by_col[col_name] = int(c2 or 0)
        check3_zero_by_col[col_name] = int(c3 or 0)

    payment3_total = payment_totals[3]
    payment4_total = payment_totals[4]

    report = {
        "warehouse_db": WAREHOUSE_DB_FILE.as_posix(),
        "input_table": TABLE_TAXI_RAW,
        "summary": {
            "total_rows": total_rows,
            "clean_flow": CLEAN_FLOW,
        },
        "check_1_tip_eq_0_by_payment_type": {
            "description": "Tip = 0 theo 4 muc payment_type (1, 2, 3, 4).",
            "col_1_payment_type_1": {
                "payment_type_total_rows": payment_totals[1],
                "rows_tip_eq_0": check1_tip_zero_by_payment[1],
                "percent": percent(check1_tip_zero_by_payment[1], payment_totals[1]),
            },
            "col_2_payment_type_2": {
                "payment_type_total_rows": payment_totals[2],
                "rows_tip_eq_0": check1_tip_zero_by_payment[2],
                "percent": percent(check1_tip_zero_by_payment[2], payment_totals[2]),
            },
            "col_3_payment_type_3": {
                "payment_type_total_rows": payment_totals[3],
                "rows_tip_eq_0": check1_tip_zero_by_payment[3],
                "percent": percent(check1_tip_zero_by_payment[3], payment_totals[3]),
            },
            "col_4_payment_type_4": {
                "payment_type_total_rows": payment_totals[4],
                "rows_tip_eq_0": check1_tip_zero_by_payment[4],
                "percent": percent(check1_tip_zero_by_payment[4], payment_totals[4]),
            },
        },
        "check_2_payment_type_3_zero_money_columns": {
            "description": "Trong nhom payment_type = 3, kiem tra ty le = 0 theo tung cot tien.",
            "denominator_payment_type_3_rows": payment3_total,
            "columns": [
                {
                    "column_name": col,
                    "rows_payment_type_3_and_col_eq_0": check2_zero_by_col[col],
                    "percent": percent(check2_zero_by_col[col], payment3_total),
                }
                for col in ZERO_MONEY_COLUMNS
            ],
        },
        "check_3_payment_type_4_zero_money_columns": {
            "description": "Trong nhom payment_type = 4, kiem tra ty le = 0 theo tung cot tien.",
            "denominator_payment_type_4_rows": payment4_total,
            "columns": [
                {
                    "column_name": col,
                    "rows_payment_type_4_and_col_eq_0": check3_zero_by_col[col],
                    "percent": percent(check3_zero_by_col[col], payment4_total),
                }
                for col in ZERO_MONEY_COLUMNS
            ],
        },
    }
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")
