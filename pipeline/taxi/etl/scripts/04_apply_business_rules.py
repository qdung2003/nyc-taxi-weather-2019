# -*- coding: utf-8 -*-
import gc
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "03_drop_airport_fee.parquet"
output_file = taxi_root / "etl" / "results" / "04_apply_business_rules.parquet"

TQDM_DISABLE = not sys.stderr.isatty()


def and_inclusive_range(mask, table, col, min_value, max_value):
    col_mask = pc.and_(pc.greater_equal(table[col], min_value), pc.less_equal(table[col], max_value))
    return pc.and_(mask, pc.fill_null(col_mask, False))


def and_is_in(mask, table, col, values):
    value_set = pa.array(values, type=table[col].type)
    col_mask = pc.is_in(table[col], value_set=value_set)
    return pc.and_(mask, pc.fill_null(col_mask, False))


def normalize_congestion(col):
    return pc.if_else(pc.fill_null(pc.is_null(col), False), pa.scalar(0.0, type=col.type), col)


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


def build_base_mask(table: pa.Table):
    mask = pc.fill_null(pc.is_in(table["VendorID"], value_set=pa.array([1, 2], type=pa.int64())), False)
    mask = and_inclusive_range(mask, table, "passenger_count", 1, 5)
    mask = and_inclusive_range(mask, table, "RatecodeID", 1, 6)
    mask = and_is_in(mask, table, "store_and_fwd_flag", ["Y", "N"])
    mask = and_inclusive_range(mask, table, "PULocationID", 1, 263)
    mask = and_inclusive_range(mask, table, "DOLocationID", 1, 263)
    mask = and_inclusive_range(mask, table, "payment_type", 1, 4)

    congestion_mask = pc.is_in(table["congestion_surcharge"], value_set=pa.array([0.0, 0.75, 2.5], type=table["congestion_surcharge"].type))
    mask = pc.and_(mask, pc.fill_null(congestion_mask, False))

    mask = pc.and_(mask, pc.fill_null(pc.greater(table["trip_distance"], 0.0), False))
    mask = pc.and_(mask, pc.fill_null(pc.greater(table["fare_amount"], 0.0), False))
    mask = and_is_in(mask, table, "extra", [0.0, 0.5, 1.0])
    mask = pc.and_(mask, pc.fill_null(pc.equal(table["mta_tax"], 0.5), False))
    mask = pc.and_(mask, pc.fill_null(pc.greater_equal(table["tip_amount"], 0.0), False))
    mask = pc.and_(mask, pc.fill_null(pc.greater_equal(table["tolls_amount"], 0.0), False))
    mask = pc.and_(mask, pc.fill_null(pc.equal(table["improvement_surcharge"], 0.3), False))
    mask = pc.and_(mask, pc.fill_null(pc.greater(table["total_amount"], 0.0), False))

    p234_mask = pc.fill_null(
        pc.is_in(table["payment_type"], value_set=pa.array([2, 3, 4], type=table["payment_type"].type)),
        False,
    )
    tip_ne_0 = pc.fill_null(pc.not_equal(table["tip_amount"], 0.0), False)
    invalid_tip_rule = pc.and_(p234_mask, tip_ne_0)
    return pc.and_(mask, pc.invert(invalid_tip_rule))


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    parquet = pq.ParquetFile(input_file)
    schema = parquet.schema_arrow
    writer = None

    input_rows = 0
    output_rows = 0

    with tqdm(
        total=parquet.metadata.num_row_groups,
        desc="ETL 04 - apply business rules",
        disable=TQDM_DISABLE,
        leave=False,
        dynamic_ncols=True,
        mininterval=0.5,
    ) as pbar:
        for i in range(parquet.metadata.num_row_groups):
            table = parquet.read_row_group(i)
            input_rows += len(table)

            if len(table) > 0:
                table = table.set_column(
                    table.schema.get_field_index("congestion_surcharge"),
                    "congestion_surcharge",
                    normalize_congestion(table["congestion_surcharge"]),
                )
                table = normalize_extra_and_fare(table)
                table = table.filter(build_base_mask(table))

            output_rows += len(table)
            if writer is None:
                writer = pq.ParquetWriter(output_file, schema)
            writer.write_table(table)
            pbar.update(1)

    if writer:
        writer.close()

    parquet = None
    gc.collect()

    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0
    print("ETL 04 complete.")
    print(f"Input rows:               {input_rows:,}")
    print(f"Output rows:              {output_rows:,}")
    print(f"Rows removed:             {removed:,} ({removed_pct:.2f}%)")
    print(f"Output file:              {output_file}")


if __name__ == "__main__":
    main()
