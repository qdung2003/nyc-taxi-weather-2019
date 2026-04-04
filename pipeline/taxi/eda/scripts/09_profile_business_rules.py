# -*- coding: utf-8 -*-
import json
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from tqdm import tqdm


taxi_root = Path(__file__).resolve().parents[2]
input_file = taxi_root / "etl" / "results" / "04_apply_business_rules.parquet"
output_file = taxi_root / "eda" / "results" / "09_profile_business_rules.json"

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CONTINUOUS_COLUMNS = {"trip_distance", "fare_amount", "tip_amount", "tolls_amount", "total_amount"}
TQDM_DISABLE = not sys.stderr.isatty()


def pct(count: int, total: int, digits: int = 5) -> float:
    if total == 0:
        return 0.0
    return round(count / total * 100, digits)


def sum_true(mask) -> int:
    return int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)


def merge_value_counts(counter: dict, arr) -> None:
    vc = pc.value_counts(arr).to_pylist()
    for row in vc:
        counter[row["values"]] += int(row["counts"])


def build_profiles(parquet: pq.ParquetFile):
    schema = parquet.schema_arrow
    total_rows = parquet.metadata.num_rows
    columns = [f.name for f in schema]

    month_counts = {}
    exact_counters = {}
    null_counts = defaultdict(int)
    nan_counts = defaultdict(int)
    continuous_meta = {}

    for col in columns:
        col_type = schema.field(col).type
        if pa.types.is_timestamp(col_type):
            month_counts[col] = [0] * 12
        elif col in CONTINUOUS_COLUMNS:
            continuous_meta[col] = {"zero": 0, "max_value": 0.0}
        else:
            exact_counters[col] = defaultdict(int)

    for rg in tqdm(
        range(parquet.metadata.num_row_groups),
        desc="EDA 09 - pass 1 (profile columns)",
        disable=TQDM_DISABLE,
    ):
        table = parquet.read_row_group(rg, columns=columns)
        for col in columns:
            arr = table[col]
            col_type = schema.field(col).type

            if pa.types.is_timestamp(col_type):
                m = pc.month(arr)
                for i in range(12):
                    month_counts[col][i] += sum_true(pc.equal(m, i + 1))
                continue

            null_counts[col] += arr.null_count
            if pa.types.is_floating(col_type):
                nan_mask = pc.fill_null(pc.is_nan(arr), False)
                nan_counts[col] += sum_true(nan_mask)
            non_null = pc.drop_null(arr)
            if len(non_null) == 0:
                continue

            if col in CONTINUOUS_COLUMNS:
                continuous_meta[col]["zero"] += sum_true(pc.equal(non_null, 0))
                max_val = pc.max(non_null).as_py()
                if max_val is not None:
                    continuous_meta[col]["max_value"] = max(continuous_meta[col]["max_value"], float(max_val))
            else:
                merge_value_counts(exact_counters[col], non_null)

    continuous_bins = {}
    for col, meta in continuous_meta.items():
        max_value = float(meta["max_value"])
        if max_value <= 0:
            continuous_bins[col] = {"edges": [0.0] * 11, "counts": [0] * 10}
            continue

        edges = [i * (max_value / 10.0) for i in range(11)]
        counts = [0] * 10

        for rg in tqdm(
            range(parquet.metadata.num_row_groups),
            desc=f"EDA 09 - pass 2 (bins: {col})",
            disable=TQDM_DISABLE,
        ):
            arr = parquet.read_row_group(rg, columns=[col])[col]
            pos = pc.drop_null(arr).filter(pc.greater(pc.drop_null(arr), 0))
            if len(pos) == 0:
                continue
            for i in range(10):
                left = edges[i]
                right = edges[i + 1]
                mask = pc.and_(pc.greater(pos, left), pc.less_equal(pos, right))
                counts[i] += sum_true(mask)

        continuous_bins[col] = {"edges": edges, "counts": counts}

    return {
        "schema": schema,
        "total_rows": total_rows,
        "month_counts": month_counts,
        "exact_counters": exact_counters,
        "null_counts": null_counts,
        "nan_counts": nan_counts,
        "continuous_meta": continuous_meta,
        "continuous_bins": continuous_bins,
    }


def build_exact_rows(col_name: str, counter: dict, null_count: int, total_rows: int):
    rows = []
    for value, count in counter.items():
        if int(count) <= 0:
            continue
        label = "null" if value is None else str(value)
        rows.append({"label": label, "value": value, "count": int(count), "percent": pct(int(count), total_rows)})

    if null_count > 0:
        rows.append({"label": "null", "value": None, "count": int(null_count), "percent": pct(int(null_count), total_rows)})

    def sort_key(row):
        v = row.get("value")
        if v is None:
            return (2, 0.0, row["label"])
        if isinstance(v, (int, float)):
            return (0, float(v), row["label"])
        return (1, 0.0, row["label"])

    rows = sorted(rows, key=sort_key)

    if col_name in {"PULocationID", "DOLocationID"}:
        visible = [r for r in rows if r["percent"] > 1.0]
        hidden = [r for r in rows if r not in visible]
        if hidden:
            visible.append(
                {
                    "label": f"Other ({len(hidden)} values)",
                    "count": sum(r["count"] for r in hidden),
                    "percent": round(sum(r["percent"] for r in hidden), 5),
                }
            )
        return visible

    return rows


def build_payload(profiles):
    schema = profiles["schema"]
    total_rows = profiles["total_rows"]
    month_counts = profiles["month_counts"]
    exact_counters = profiles["exact_counters"]
    null_counts = profiles["null_counts"]
    nan_counts = profiles["nan_counts"]
    continuous_meta = profiles["continuous_meta"]
    continuous_bins = profiles["continuous_bins"]

    columns_payload = []

    for field in schema:
        col = field.name
        type_text = str(field.type)
        chart_rows = []
        note = ""
        unique_count = None
        range_bucket_count = None
        month_bucket_count = None
        invalid_type_count = int(null_counts.get(col, 0)) + int(nan_counts.get(col, 0))
        valid_type_count = max(0, int(total_rows) - invalid_type_count)
        correct_type_percent = pct(valid_type_count, int(total_rows))

        if col in month_counts:
            chart_rows = [
                {"label": MONTH_LABELS[i], "count": int(c), "percent": pct(int(c), total_rows)}
                for i, c in enumerate(month_counts[col])
            ]
            month_bucket_count = 12
            note = "12-month distribution from 04_apply_business_rules.parquet"
        elif col in continuous_meta:
            meta = continuous_meta[col]
            bins = continuous_bins[col]
            # Skip negative bucket by requirement; include zero only if count > 0.
            if int(meta["zero"]) > 0:
                chart_rows.append(
                    {"label": "= 0", "x_label": "0", "count": int(meta["zero"]), "percent": pct(int(meta["zero"]), total_rows)}
                )
            for i in range(10):
                count = int(bins["counts"][i])
                left = float(bins["edges"][i])
                right = float(bins["edges"][i + 1])
                chart_rows.append(
                    {
                        "label": f"({left:.2f}, {right:.2f}]",
                        "x_label": f"{right:.2f}",
                        "count": count,
                        "percent": pct(count, total_rows),
                    }
                )
            range_bucket_count = len(chart_rows)
            note = "Zero and positive bins from 04_apply_business_rules.parquet (negative bins hidden; 10 raw bins)"
        else:
            chart_rows = build_exact_rows(col, exact_counters.get(col, {}), int(null_counts.get(col, 0)), total_rows)
            unique_count = len(exact_counters.get(col, {})) + (1 if int(null_counts.get(col, 0)) > 0 else 0)
            note = "Value distribution from 04_apply_business_rules.parquet (count=0 values hidden)"

        columns_payload.append(
            {
                "column_name": col,
                "type_value": type_text,
                "unique_count": unique_count,
                "range_bucket_count": range_bucket_count,
                "month_bucket_count": month_bucket_count,
                "correct_type_percent": correct_type_percent,
                "chart_rows": chart_rows,
                "chart_note": note,
            }
        )

    return {
        "summary": {
            "column_count": len(columns_payload),
            "total_rows": total_rows,
            "input_file": input_file.as_posix(),
            "clean_flow": "04_apply_business_rules",
        },
        "columns": columns_payload,
        "range_columns": sorted(list(CONTINUOUS_COLUMNS)),
    }


def main():
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    parquet = pq.ParquetFile(input_file)
    payload = build_payload(build_profiles(parquet))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved profile JSON: {output_file}")


if __name__ == "__main__":
    main()
