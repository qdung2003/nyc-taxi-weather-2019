from pipeline.constants.modules import ETL02_INGEST
from pipeline.constants.paths import TAXI_EDA_RESULTS_DIR
from pipeline.constants.tables import TABLE_TAXI_RAW
from pipeline.services.helpers import percentage, reset_csv_dir, write_csv
from pipeline.services.queries import ensure_table_exists, quote_identifier, run_with_conn


TAXI_EDA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
output_file = TAXI_EDA_RESULTS_DIR / "04_payments"


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
    ensure_table_exists(conn, TABLE_TAXI_RAW, ETL02_INGEST.create_taxi_raw_table)

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

    taxi_raw_quoted = quote_identifier(TABLE_TAXI_RAW)
    zero_count_exprs = []
    for col in ZERO_MONEY_COLUMNS:
        col_quoted = quote_identifier(col)
        zero_count_exprs.append(
            f"COUNT(*) FILTER (WHERE payment_type = 3 AND {col_quoted} = 0.0) AS p3_{col}"
        )
        zero_count_exprs.append(
            f"COUNT(*) FILTER (WHERE payment_type = 4 AND {col_quoted} = 0.0) AS p4_{col}"
        )

    zero_row = conn.execute(
        f"""
        SELECT
            {", ".join(zero_count_exprs)}
        FROM {taxi_raw_quoted}
        """
    ).fetchone()

    zero_map = {}
    idx = 0
    for col in ZERO_MONEY_COLUMNS:
        zero_map[(3, col)] = int(zero_row[idx] or 0)
        idx += 1
        zero_map[(4, col)] = int(zero_row[idx] or 0)
        idx += 1

    payment3_total = payment_totals[3]
    payment4_total = payment_totals[4]
    payment_types = [1, 2, 3, 4]

    check_1_rows = [
        {
            "check": 1,
            "description": "Tip rate = 0 in 4 payment_type items (1, 2, 3, 4).",
            "column_count": len(payment_types),
        }
    ]
    check_1_array_rows = [
        {
            "check": 1,
            "payment_type": payment_type,
            "tip_0_count": check1_tip_zero_by_payment[payment_type],
            "total_count": payment_totals[payment_type],
            "percent": percentage(check1_tip_zero_by_payment[payment_type], payment_totals[payment_type]),
        }
        for payment_type in payment_types
    ]
    check_2_3_rows = [
        {
            "check": 2,
            "description": "In the payment_type = 3 group, check that the rate = 0 for each money column.",
            "payment_type": 3,
            "row_count": payment3_total,
            "column_count": len(ZERO_MONEY_COLUMNS),
        },
        {
            "check": 3,
            "description": "In the payment_type = 4 group, check that the rate = 0 for each money column.",
            "payment_type": 4,
            "row_count": payment4_total,
            "column_count": len(ZERO_MONEY_COLUMNS),
        },
    ]
    check_2_3_array_rows = [
        {
            "check": check,
            "column_name": column_name,
            "count": zero_map[(payment_type, column_name)],
            "percent": percentage(zero_map[(payment_type, column_name)], total_count),
        }
        for check, payment_type, total_count in [(2, 3, payment3_total), (3, 4, payment4_total)]
        for column_name in ZERO_MONEY_COLUMNS
    ]

    reset_csv_dir(output_file)
    write_csv(
        output_file,
        [
            "check_1",
            "check_1_array",
            "check_2_3",
            "check_2_3_array",
        ],
        [
            (
                ["check", "description", "column_count"],
                [
                    [row["check"] for row in check_1_rows],
                    [row["description"] for row in check_1_rows],
                    [row["column_count"] for row in check_1_rows],
                ],
            ),
            (
                ["check", "payment_type", "tip_0_count", "total_count", "percent"],
                [
                    [row["check"] for row in check_1_array_rows],
                    [row["payment_type"] for row in check_1_array_rows],
                    [row["tip_0_count"] for row in check_1_array_rows],
                    [row["total_count"] for row in check_1_array_rows],
                    [row["percent"] for row in check_1_array_rows],
                ],
            ),
            (
                ["check", "description", "payment_type", "row_count", "column_count"],
                [
                    [row["check"] for row in check_2_3_rows],
                    [row["description"] for row in check_2_3_rows],
                    [row["payment_type"] for row in check_2_3_rows],
                    [row["row_count"] for row in check_2_3_rows],
                    [row["column_count"] for row in check_2_3_rows],
                ],
            ),
            (
                ["check", "column_name", "count", "percent"],
                [
                    [row["check"] for row in check_2_3_array_rows],
                    [row["column_name"] for row in check_2_3_array_rows],
                    [row["count"] for row in check_2_3_array_rows],
                    [row["percent"] for row in check_2_3_array_rows],
                ],
            ),
        ],
    )
    print(f"EDA 04 saved: {output_file.name}")


if __name__ == "__main__":
    run_with_conn(main)
