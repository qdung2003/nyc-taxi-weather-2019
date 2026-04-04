# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "03_drop_airport_fee.parquet"
output_file = taxi_root / "eda" / "results" / "05_rate_payment_checks.json"
CLEAN_FLOW = "pre_etl_04_business_rules_analysis_on_03_drop_airport_fee"
TQDM_DISABLE = not sys.stderr.isatty()

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


def pct(part: int, total: int, digits: int = 5) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, digits)


def sum_true(mask) -> int:
    return int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)


def fill_bool(mask):
    return pc.fill_null(mask, False)


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    parquet = pq.ParquetFile(input_file)
    columns = ["payment_type"] + ZERO_MONEY_COLUMNS
    row_group_count = parquet.metadata.num_row_groups

    total_rows = 0

    # Check 1: tip = 0 by payment_type 1..4
    payment_totals = {1: 0, 2: 0, 3: 0, 4: 0}
    check1_tip_zero_by_payment = {1: 0, 2: 0, 3: 0, 4: 0}

    # Check 2: payment_type = 3 and zero money columns
    payment3_total = 0
    check2_zero_by_col = {col: 0 for col in ZERO_MONEY_COLUMNS}

    # Check 3: payment_type = 4 and zero money columns
    payment4_total = 0
    check3_zero_by_col = {col: 0 for col in ZERO_MONEY_COLUMNS}

    with tqdm(
        total=row_group_count,
        desc="EDA 05 - payment_type checks (pre ETL 04)",
        leave=False,
        dynamic_ncols=True,
        mininterval=0.5,
        disable=TQDM_DISABLE,
    ) as pbar:
        for rg in range(row_group_count):
            table = parquet.read_row_group(rg, columns=columns)
            total_rows += len(table)

            payment_type = table["payment_type"]
            tip_amount = table["tip_amount"]

            mask_payment_1 = fill_bool(pc.equal(payment_type, 1))
            mask_payment_2 = fill_bool(pc.equal(payment_type, 2))
            mask_payment_3 = fill_bool(pc.equal(payment_type, 3))
            mask_payment_4 = fill_bool(pc.equal(payment_type, 4))

            payment_totals[1] += sum_true(mask_payment_1)
            payment_totals[2] += sum_true(mask_payment_2)
            payment_totals[3] += sum_true(mask_payment_3)
            payment_totals[4] += sum_true(mask_payment_4)

            payment3_total += sum_true(mask_payment_3)
            payment4_total += sum_true(mask_payment_4)

            tip_zero_mask = fill_bool(pc.equal(tip_amount, 0.0))
            check1_tip_zero_by_payment[1] += sum_true(pc.and_(mask_payment_1, tip_zero_mask))
            check1_tip_zero_by_payment[2] += sum_true(pc.and_(mask_payment_2, tip_zero_mask))
            check1_tip_zero_by_payment[3] += sum_true(pc.and_(mask_payment_3, tip_zero_mask))
            check1_tip_zero_by_payment[4] += sum_true(pc.and_(mask_payment_4, tip_zero_mask))

            for col in ZERO_MONEY_COLUMNS:
                zero_mask = fill_bool(pc.equal(table[col], 0.0))
                check2_zero_by_col[col] += sum_true(pc.and_(mask_payment_3, zero_mask))
                check3_zero_by_col[col] += sum_true(pc.and_(mask_payment_4, zero_mask))

            pbar.update(1)

    report = {
        "input_file": input_file.as_posix(),
        "summary": {
            "total_rows": total_rows,
            "clean_flow": CLEAN_FLOW,
        },
        "check_1_tip_eq_0_by_payment_type": {
            "description": "Tip = 0 theo 4 muc payment_type (1, 2, 3, 4).",
            "col_1_payment_type_1": {
                "payment_type_total_rows": payment_totals[1],
                "rows_tip_eq_0": check1_tip_zero_by_payment[1],
                "percent": pct(check1_tip_zero_by_payment[1], payment_totals[1]),
            },
            "col_2_payment_type_2": {
                "payment_type_total_rows": payment_totals[2],
                "rows_tip_eq_0": check1_tip_zero_by_payment[2],
                "percent": pct(check1_tip_zero_by_payment[2], payment_totals[2]),
            },
            "col_3_payment_type_3": {
                "payment_type_total_rows": payment_totals[3],
                "rows_tip_eq_0": check1_tip_zero_by_payment[3],
                "percent": pct(check1_tip_zero_by_payment[3], payment_totals[3]),
            },
            "col_4_payment_type_4": {
                "payment_type_total_rows": payment_totals[4],
                "rows_tip_eq_0": check1_tip_zero_by_payment[4],
                "percent": pct(check1_tip_zero_by_payment[4], payment_totals[4]),
            },
        },
        "check_2_payment_type_3_zero_money_columns": {
            "description": "Trong nhom payment_type = 3, kiem tra ty le = 0 theo tung cot tien.",
            "denominator_payment_type_3_rows": payment3_total,
            "columns": [
                {
                    "column_name": col,
                    "rows_payment_type_3_and_col_eq_0": check2_zero_by_col[col],
                    "percent": pct(check2_zero_by_col[col], payment3_total),
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
                    "percent": pct(check3_zero_by_col[col], payment4_total),
                }
                for col in ZERO_MONEY_COLUMNS
            ],
        },
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")


if __name__ == "__main__":
    main()
