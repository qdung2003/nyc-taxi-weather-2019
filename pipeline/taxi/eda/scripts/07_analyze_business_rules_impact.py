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
output_dir = taxi_root / "eda" / "results"
output_file = output_dir / "07_business_rules_impact.json"
TQDM_DISABLE = not sys.stderr.isatty()


def to_posix(path: Path) -> str:
    return path.as_posix()


def pct(count: int, total: int, digits: int = 5) -> float:
    if total == 0:
        return 0.0
    return round(count / total * 100, digits)


def sum_true(mask) -> int:
    return int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)


def valid_inclusive_range(table, col_name: str, min_value, max_value):
    col_mask = pc.and_(pc.greater_equal(table[col_name], min_value), pc.less_equal(table[col_name], max_value))
    return pc.fill_null(col_mask, False)


def valid_is_in(table, col_name: str, values):
    value_set = pa.array(values, type=table[col_name].type)
    col_mask = pc.is_in(table[col_name], value_set=value_set)
    return pc.fill_null(col_mask, False)


def normalize_congestion(col):
    return pc.if_else(
        pc.fill_null(pc.is_null(col), False),
        pa.scalar(0.0, type=col.type),
        col,
    )


def normalize_extra_and_fare(table: pa.Table) -> pa.Table:
    extra_col = table["extra"]
    fare_col = table["fare_amount"]

    shift_mask = pc.fill_null(pc.greater_equal(extra_col, 2.5), False)
    extra_shift = pa.scalar(2.5, type=extra_col.type)
    fare_shift = pa.scalar(2.5, type=fare_col.type)

    normalized_extra = pc.if_else(shift_mask, pc.subtract(extra_col, extra_shift), extra_col)
    normalized_fare = pc.if_else(shift_mask, pc.add(fare_col, fare_shift), fare_col)

    table = table.set_column(table.schema.get_field_index("extra"), "extra", normalized_extra)
    table = table.set_column(table.schema.get_field_index("fare_amount"), "fare_amount", normalized_fare)
    return table


def build_rule_valid_masks(table):
    p234 = pc.fill_null(
        pc.is_in(table["payment_type"], value_set=pa.array([2, 3, 4], type=table["payment_type"].type)),
        False,
    )
    tip_eq_0 = pc.fill_null(pc.equal(table["tip_amount"], 0.0), False)

    return {
        "VendorID_in_1_2": valid_is_in(table, "VendorID", [1, 2]),
        "passenger_count_in_1_5": valid_inclusive_range(table, "passenger_count", 1, 5),
        "RatecodeID_in_1_6": valid_inclusive_range(table, "RatecodeID", 1, 6),
        "store_and_fwd_flag_in_Y_N": valid_is_in(table, "store_and_fwd_flag", ["Y", "N"]),
        "PULocationID_in_1_263": valid_inclusive_range(table, "PULocationID", 1, 263),
        "DOLocationID_in_1_263": valid_inclusive_range(table, "DOLocationID", 1, 263),
        "payment_type_in_1_4": valid_inclusive_range(table, "payment_type", 1, 4),
        "congestion_surcharge_in_0_0_75_2_5": valid_is_in(table, "congestion_surcharge", [0.0, 0.75, 2.5]),
        "trip_distance_gt_0": pc.fill_null(pc.greater(table["trip_distance"], 0.0), False),
        "fare_amount_gt_0": pc.fill_null(pc.greater(table["fare_amount"], 0.0), False),
        "extra_in_set_0_0_5_1_after_normalize": valid_is_in(table, "extra", [0.0, 0.5, 1.0]),
        "mta_tax_eq_0_5": pc.fill_null(pc.equal(table["mta_tax"], 0.5), False),
        "tip_amount_ge_0": pc.fill_null(pc.greater_equal(table["tip_amount"], 0.0), False),
        "tolls_amount_ge_0": pc.fill_null(pc.greater_equal(table["tolls_amount"], 0.0), False),
        "improvement_surcharge_eq_0_3": pc.fill_null(pc.equal(table["improvement_surcharge"], 0.3), False),
        "total_amount_gt_0": pc.fill_null(pc.greater(table["total_amount"], 0.0), False),
        "payment_type_2_3_4_then_tip_eq_0": pc.or_(pc.invert(p234), tip_eq_0),
    }


def evaluate_rules(valid_masks, invalid_by_rule, exclusive_by_rule):
    fail_masks = {rule_name: pc.invert(valid_mask) for rule_name, valid_mask in valid_masks.items()}

    fail_counts = None
    for idx, (rule_name, fail_mask) in enumerate(fail_masks.items()):
        fail_i64 = pc.cast(fail_mask, pa.int64())
        if idx == 0:
            fail_counts = fail_i64
        else:
            fail_counts = pc.add(fail_counts, fail_i64)

        invalid_by_rule[rule_name] = invalid_by_rule.get(rule_name, 0) + sum_true(fail_mask)

    if fail_counts is None:
        return None, 0

    removed_mask = pc.greater(fail_counts, 0)
    removed_rows = sum_true(removed_mask)
    exactly_one_fail = pc.equal(fail_counts, 1)

    for rule_name, fail_mask in fail_masks.items():
        exclusive_mask = pc.and_(fail_mask, exactly_one_fail)
        exclusive_by_rule[rule_name] = exclusive_by_rule.get(rule_name, 0) + sum_true(exclusive_mask)

    keep_mask = pc.invert(removed_mask)
    return keep_mask, removed_rows


def main():
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    parquet = pq.ParquetFile(input_file)

    columns_needed = [
        "VendorID",
        "passenger_count",
        "trip_distance",
        "RatecodeID",
        "store_and_fwd_flag",
        "PULocationID",
        "DOLocationID",
        "payment_type",
        "fare_amount",
        "extra",
        "mta_tax",
        "tip_amount",
        "tolls_amount",
        "improvement_surcharge",
        "total_amount",
        "congestion_surcharge",
    ]

    row_group_count = parquet.metadata.num_row_groups
    total_input_rows = 0
    total_clean_rows = 0
    total_removed_rows = 0

    invalid_by_rule = {}
    exclusive_by_rule = {}

    with tqdm(
        total=row_group_count,
        desc="Analyzing business-rules impact (EDA 07)",
        leave=False,
        dynamic_ncols=True,
        mininterval=0.5,
        disable=TQDM_DISABLE,
    ) as pbar:
        for rg in range(row_group_count):
            table = parquet.read_row_group(rg, columns=columns_needed)
            total_input_rows += len(table)

            if len(table) > 0:
                table = table.set_column(
                    table.schema.get_field_index("congestion_surcharge"),
                    "congestion_surcharge",
                    normalize_congestion(table["congestion_surcharge"]),
                )
                table = normalize_extra_and_fare(table)

                valid_masks = build_rule_valid_masks(table)
                keep_mask, removed_rows = evaluate_rules(valid_masks, invalid_by_rule, exclusive_by_rule)
                total_removed_rows += removed_rows

                clean_table = table.filter(keep_mask) if keep_mask is not None else table
                total_clean_rows += len(clean_table)

            pbar.update(1)

    rules_report = []
    for rule_name, invalid_rows in invalid_by_rule.items():
        exclusive_rows = exclusive_by_rule.get(rule_name, 0)
        shared_rows = invalid_rows - exclusive_rows
        rules_report.append(
            {
                "rule_name": rule_name,
                "invalid_rows": invalid_rows,
                "invalid_percent_on_input": pct(invalid_rows, total_input_rows),
                "removed_exclusive_rows": exclusive_rows,
                "removed_exclusive_percent_on_input": pct(exclusive_rows, total_input_rows),
                "removed_shared_rows": shared_rows,
                "removed_shared_percent_on_input": pct(shared_rows, total_input_rows),
            }
        )

    rules_report.sort(key=lambda item: -item["removed_exclusive_rows"])

    report = {
        "input_file": to_posix(input_file),
        "scenario_assumptions": {
            "cleaning_flow": "single_stage_clean_with_in-row_transforms",
            "rules": "congestion null->0; normalize extra>=2.5 => extra-2.5 and fare+2.5; apply discrete+money rules in one pass",
        },
        "summary": {
            "total_input_rows": total_input_rows,
            "total_clean_rows": total_clean_rows,
            "total_removed_rows": total_removed_rows,
            "total_removed_percent": pct(total_removed_rows, total_input_rows),
        },
        "rules": rules_report,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved report: {output_file}")


if __name__ == "__main__":
    main()
