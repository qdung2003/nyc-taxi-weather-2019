# -*- coding: utf-8 -*-
from pathlib import Path


import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_dir = taxi_root / "raw"
output_file = taxi_root / "etl" / "results" / "02_merge_parquet_2019.parquet"


parquet_files = sorted(input_dir.glob("yellow_tripdata_2019-*.parquet"))

if not parquet_files:
    raise FileNotFoundError("No monthly parquet files found to merge.")

output_file.parent.mkdir(parents=True, exist_ok=True)
first_parquet = pq.ParquetFile(parquet_files[0])
schema = first_parquet.schema_arrow
writer = pq.ParquetWriter(output_file, schema=schema)
total_rows = 0

try:
    for parquet_file in tqdm(parquet_files, desc="Merging parquet files", unit="file"):
        parquet = pq.ParquetFile(parquet_file)
        row_groups = range(parquet.metadata.num_row_groups)

        for row_group_index in tqdm(
            row_groups,
            desc=f"Reading {parquet_file.name}",
            unit="group",
            leave=False,
        ):
            table = parquet.read_row_group(row_group_index)

            pickup = table["tpep_pickup_datetime"]
            dropoff = table["tpep_dropoff_datetime"]

            # điều kiện 1: năm 2019
            cond_pickup_year = pc.equal(pc.year(pickup), 2019)
            cond_dropoff_year = pc.equal(pc.year(dropoff), 2019)
            cond_year = pc.and_(cond_pickup_year, cond_dropoff_year)

            # điều kiện 2: pickup < dropoff
            cond_time = pc.less(pickup, dropoff)

            # combine điều kiện
            mask = pc.and_(cond_year, cond_time)

            # filter table
            table = table.filter(mask)

            # đảm bảo schema giống nhau
            table = pa.Table.from_batches(table.to_batches(), schema=schema)

            writer.write_table(table)
            total_rows += table.num_rows

finally:
    writer.close()

print(f"Created: {output_file}")
print(f"Merged files: {len(parquet_files)}")
print(f"Total rows: {total_rows:,}")
