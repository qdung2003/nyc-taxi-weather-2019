from pathlib import Path

import pyarrow.csv as pacsv
import pyarrow.parquet as pq


taxi_root = Path(__file__).resolve().parents[1]
input_file = taxi_root / "raw" / "yellow_tripdata_2019-01.parquet"
output_file = taxi_root / "preview" / "yellow_tripdata_2019-01_sample_50.csv"
max_rows = 50


table = pq.read_table(input_file).slice(0, max_rows)
with output_file.open("wb") as dst:
    pacsv.write_csv(table, dst)

print(f"Created: {output_file}")
print(f"Rows written: {max_rows}")
