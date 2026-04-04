# -*- coding: utf-8 -*-
import gc
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "04_apply_business_rules.parquet"
output_file = taxi_root / "etl" / "results" / "05_apply_upper_bounds.parquet"
simulation_file = taxi_root / "eda" / "results" / "11_simulate_upper_bounds.json"

TQDM_DISABLE = not sys.stderr.isatty()
TARGET_COLUMNS = ["trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"]


def load_upper_bounds_from_simulation() -> dict[str, float]:
    if not simulation_file.exists():
        sim_script = taxi_root / "eda" / "scripts" / "11_simulate_upper_bounds.py"
        print(f"Simulation JSON not found. Running {sim_script.name} first...")
        subprocess.run([sys.executable, str(sim_script)], check=True)
        
        if not simulation_file.exists():
            raise FileNotFoundError(f"Failed to generate {simulation_file} after running script.")
    
    payload = json.loads(simulation_file.read_text(encoding="utf-8"))
    by_name = {c.get("column_name"): c for c in payload.get("columns", [])}
    missing = [c for c in TARGET_COLUMNS if c not in by_name]
    if missing:
        raise ValueError(f"Missing upper bound in simulation JSON for: {', '.join(missing)}")

    bounds: dict[str, float] = {}
    for col in TARGET_COLUMNS:
        raw = by_name[col].get("final_upper_bound")
        if raw is None:
            raw = by_name[col].get("max_value")
        if raw is None:
            raise ValueError(f"Column {col} has no final_upper_bound/max_value in {simulation_file}")
        bounds[col] = float(raw)
    return bounds


def build_outlier_mask(table: pa.Table, upper_bounds: dict[str, float]):
    mask = pc.fill_null(pc.less_equal(table["trip_distance"], upper_bounds["trip_distance"]), False)
    mask = pc.and_(mask, pc.fill_null(pc.less_equal(table["fare_amount"], upper_bounds["fare_amount"]), False))
    mask = pc.and_(mask, pc.fill_null(pc.less_equal(table["tip_amount"], upper_bounds["tip_amount"]), False))
    mask = pc.and_(mask, pc.fill_null(pc.less_equal(table["tolls_amount"], upper_bounds["tolls_amount"]), False))
    mask = pc.and_(mask, pc.fill_null(pc.less_equal(table["total_amount"], upper_bounds["total_amount"]), False))
    return mask


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    upper_bounds = load_upper_bounds_from_simulation()
    parquet = pq.ParquetFile(input_file)
    schema = parquet.schema_arrow

    writer = None
    input_rows = 0
    output_rows = 0

    with tqdm(
        total=parquet.metadata.num_row_groups,
        desc="ETL 05 - outlier cut",
        disable=TQDM_DISABLE,
        leave=False,
        dynamic_ncols=True,
        mininterval=0.5,
    ) as pbar:
        for i in range(parquet.metadata.num_row_groups):
            table = parquet.read_row_group(i)
            input_rows += len(table)

            if len(table) > 0:
                table = table.filter(build_outlier_mask(table, upper_bounds))

            output_rows += len(table)
            if writer is None:
                writer = pq.ParquetWriter(output_file, schema)
            writer.write_table(table)
            pbar.update(1)

    if writer:
        writer.close()

    removed = input_rows - output_rows
    removed_pct = (removed / input_rows * 100) if input_rows else 0.0
    print("ETL 05 complete.")
    print(f"Outlier-cut input rows:   {input_rows:,}")
    print(f"Output rows:              {output_rows:,}")
    print(f"Rows removed (outlier):   {removed:,} ({removed_pct:.2f}%)")
    print("Outlier upper bounds used:")
    for col in TARGET_COLUMNS:
        print(f"  - {col}: <= {upper_bounds[col]:.2f}")
    print(f"Upper-bound source JSON:  {simulation_file}")
    print(f"Output file:              {output_file}")


if __name__ == "__main__":
    main()
