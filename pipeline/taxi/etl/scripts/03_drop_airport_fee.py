# -*- coding: utf-8 -*-
from pathlib import Path


import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "02_merge_parquet_2019.parquet"
output_file = taxi_root / "etl" / "results" / "03_drop_airport_fee.parquet"
column_to_drop = "airport_fee"


parquet = pq.ParquetFile(input_file)
writer = None
total_rows = 0

try:
    for row_group_index in tqdm(
        range(parquet.metadata.num_row_groups),
        desc="Dropping airport_fee column",
        unit="group",
    ):
        table = parquet.read_row_group(row_group_index)

        if column_to_drop in table.column_names:
            table = table.drop([column_to_drop])

        if writer is None:
            writer = pq.ParquetWriter(output_file, table.schema)

        writer.write_table(table)
        total_rows += table.num_rows
finally:
    if writer is not None:
        writer.close()

print(f"Created: {output_file}")
print(f"Dropped column: {column_to_drop}")
print(f"Total rows written: {total_rows:,}")

