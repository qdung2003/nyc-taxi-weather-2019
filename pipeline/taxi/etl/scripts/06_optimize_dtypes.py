import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm

# Paths

taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "05_apply_upper_bounds.parquet"
output_file = taxi_root / "etl" / "results" / "06_optimize_dtypes.parquet"
output_clean_file = taxi_root / "clean" / "cleaned_tripdata_2019.parquet"
# Target dtypes after cleaning rules in CLEANING_STRATEGY.md
CAST_MAP = {
    "VendorID": pa.uint8(),
    "passenger_count": pa.uint8(),
    "trip_distance": pa.float32(),
    "RatecodeID": pa.uint8(),
    "PULocationID": pa.uint16(),
    "DOLocationID": pa.uint16(),
    "payment_type": pa.uint8(),
    "fare_amount": pa.float32(),
    "extra": pa.float32(),
    "mta_tax": pa.float32(),
    "tip_amount": pa.float32(),
    "tolls_amount": pa.float32(),
    "improvement_surcharge": pa.float32(),
    "total_amount": pa.float32(),
    "congestion_surcharge": pa.float32(),
}


def optimize_table(table: pa.Table) -> pa.Table:
    columns = {}

    for name in table.schema.names:
        col = table[name]

        if name == "store_and_fwd_flag":
            # After cleaning, only Y/N are valid. Convert to boolean to save space.
            columns[name] = pc.equal(col, "Y")
            continue

        target_type = CAST_MAP.get(name)
        if target_type is None:
            columns[name] = col
            continue

        columns[name] = pc.cast(col, target_type, safe=True)

    return pa.table(columns)


def optimize_parquet() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_clean_file.parent.mkdir(parents=True, exist_ok=True)

    parquet = pq.ParquetFile(input_file)
    row_group_count = parquet.metadata.num_row_groups

    writer = None
    total_rows = 0

    print(f"Input file:       {input_file}")
    print(f"Output (Results): {output_file}")
    print(f"Output (Clean):   {output_clean_file}")
    print("Starting dtype optimization...")

    with tqdm(total=row_group_count, desc="Optimizing dtypes") as pbar:
        for i in range(row_group_count):
            table = parquet.read_row_group(i)
            optimized = optimize_table(table)
            total_rows += len(optimized)

            if writer is None:
                writer = pq.ParquetWriter(
                    output_file,
                    optimized.schema,
                    compression="zstd",
                    use_dictionary=True,
                )

            writer.write_table(optimized)
            pbar.update(1)

    if writer is not None:
        writer.close()

    # Create a duplicate in clean
    shutil.copy2(output_file, output_clean_file)

    input_size = input_file.stat().st_size
    output_size = output_file.stat().st_size
    saved = input_size - output_size
    saved_pct = (saved / input_size * 100) if input_size else 0.0

    print("\nOptimization complete.")
    print(f"Total rows:      {total_rows:,}")
    print(f"Input size:      {input_size / (1024**2):.2f} MB")
    print(f"Output size:     {output_size / (1024**2):.2f} MB")
    print(f"Size reduced by: {saved / (1024**2):.2f} MB ({saved_pct:.2f}%)")
    print(f"\nFinal results saved to: {output_file}")
    print(f"Clean copy saved to:     {output_clean_file}")


if __name__ == "__main__":
    optimize_parquet()
