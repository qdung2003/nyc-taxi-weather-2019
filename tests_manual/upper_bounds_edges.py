import csv
from pathlib import Path


BASE = Path("data/eda_results/taxi")
OUT = BASE / "compare_upper_bounds_head_tail"


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def group_rows(rows, key):
    grouped = {}
    for row in rows:
        group_key = row.get(key)
        if group_key is None:
            continue
        grouped.setdefault(str(group_key), []).append(row)
    return grouped


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    before_meta_rows = read_csv_rows(BASE / "08_before_upper_bounds" / "column_bins.csv")
    before_bin_rows = read_csv_rows(BASE / "08_before_upper_bounds" / "column_bins_array.csv")
    after_meta_rows = read_csv_rows(BASE / "09_after_upper_bounds" / "high_unique_columns_numeric.csv")
    after_bin_rows = read_csv_rows(BASE / "09_after_upper_bounds" / "high_unique_columns_numeric_array.csv")

    before_meta = {row["column_name"]: row for row in before_meta_rows if row.get("column_name")}
    after_meta = {row["column_name"]: row for row in after_meta_rows if row.get("column_name")}
    before_bins = group_rows(before_bin_rows, "column_name")
    after_bins = group_rows(after_bin_rows, "column_name")

    column_names = sorted(set(before_meta) | set(after_meta) | set(before_bins) | set(after_bins))
    rows = []
    for column_name in column_names:
        before_bin_list = before_bins.get(column_name, [])
        after_bin_list = after_bins.get(column_name, [])
        before_meta_row = before_meta.get(column_name, {})
        after_meta_row = after_meta.get(column_name, {})

        before_first = before_bin_list[0] if before_bin_list else {}
        before_last = before_bin_list[-1] if before_bin_list else {}
        after_first = after_bin_list[0] if after_bin_list else {}
        after_last = after_bin_list[-1] if after_bin_list else {}

        rows.append(
            {
                "column_name": column_name,
                "before_lower_bound": before_meta_row.get("second_pass_min_value", ""),
                "before_upper_bound": before_meta_row.get("second_pass_max_value", before_meta_row.get("second_pass_value", "")),
                "before_first_bin_edge": before_first.get("bin_edge", ""),
                "before_first_bin_count": before_first.get("bin_count", ""),
                "before_first_bin_percentage": before_first.get("bin_percentage", ""),
                "before_last_bin_edge": before_last.get("bin_edge", ""),
                "before_last_bin_count": before_last.get("bin_count", ""),
                "before_last_bin_percentage": before_last.get("bin_percentage", ""),
                "after_min_value": after_meta_row.get("min_value", ""),
                "after_chart_max_value": after_meta_row.get("chart_max_value", ""),
                "after_first_bin_edge": after_first.get("bin_edge", ""),
                "after_first_bin_count": after_first.get("bin_count", ""),
                "after_first_bin_percentage": after_first.get("bin_percentage", ""),
                "after_last_bin_edge": after_last.get("bin_edge", ""),
                "after_last_bin_count": after_last.get("bin_count", ""),
                "after_last_bin_percentage": after_last.get("bin_percentage", ""),
            }
        )

    write_csv(OUT / "upper_bounds_head_tail_compare.csv", rows)


if __name__ == "__main__":
    main()
