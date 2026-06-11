import csv
from pathlib import Path


BASE = Path("data/eda_results/taxi")
OUT = BASE / "compare_upper_bounds_outputs"


def read_csv_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def index_rows(rows, key):
    return {str(row[key]): row for row in rows if row.get(key) is not None}


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

    before_meta = index_rows(before_meta_rows, "column_name")
    after_meta = index_rows(after_meta_rows, "column_name")
    before_bins = group_rows(before_bin_rows, "column_name")
    after_bins = group_rows(after_bin_rows, "column_name")

    column_names = sorted(set(before_meta) | set(after_meta) | set(before_bins) | set(after_bins))
    compare_rows = []
    all_bin_rows = []
    for column_name in column_names:
        before_meta_row = before_meta.get(column_name, {})
        after_meta_row = after_meta.get(column_name, {})
        before_bin_list = before_bins.get(column_name, [])
        after_bin_list = after_bins.get(column_name, [])

        compare_rows.append(
            {
                "column_name": column_name,
                "before_min_value": before_meta_row.get("min_value", ""),
                "before_first_pass_min_value": before_meta_row.get("first_pass_min_value", ""),
                "before_second_pass_min_value": before_meta_row.get("second_pass_min_value", ""),
                "before_first_pass_max_value": before_meta_row.get("first_pass_max_value", before_meta_row.get("first_pass_value", "")),
                "before_second_pass_max_value": before_meta_row.get("second_pass_max_value", before_meta_row.get("second_pass_value", "")),
                "before_below_chart_min_value_count": before_meta_row.get("below_chart_min_value_count", ""),
                "before_above_chart_max_value_count": before_meta_row.get("above_chart_max_value_count", ""),
                "before_bin_count": len(before_bin_list),
                "before_first_bin_edge": before_bin_list[0]["bin_edge"] if before_bin_list else "",
                "before_first_bin_count": before_bin_list[0]["bin_count"] if before_bin_list else "",
                "before_first_bin_percentage": before_bin_list[0]["bin_percentage"] if before_bin_list else "",
                "after_min_value": after_meta_row.get("min_value", ""),
                "after_chart_max_value": after_meta_row.get("chart_max_value", ""),
                "after_max_value": after_meta_row.get("max_value", ""),
                "after_above_chart_max_value_count": after_meta_row.get("above_chart_max_value_count", ""),
                "after_bin_count": len(after_bin_list),
                "after_first_bin_edge": after_bin_list[0]["bin_edge"] if after_bin_list else "",
                "after_first_bin_count": after_bin_list[0]["bin_count"] if after_bin_list else "",
                "after_first_bin_percentage": after_bin_list[0]["bin_percentage"] if after_bin_list else "",
            }
        )

        all_bin_rows.extend(
            {
                "stage": "08_before_upper_bounds",
                "column_name": row.get("column_name", ""),
                "bin_edge": row.get("bin_edge", ""),
                "bin_count": row.get("bin_count", ""),
                "bin_percentage": row.get("bin_percentage", ""),
            }
            for row in before_bin_list
        )
        all_bin_rows.extend(
            {
                "stage": "09_after_upper_bounds",
                "column_name": row.get("column_name", ""),
                "bin_edge": row.get("bin_edge", ""),
                "bin_count": row.get("bin_count", ""),
                "bin_percentage": row.get("bin_percentage", ""),
            }
            for row in after_bin_list
        )

    write_csv(OUT / "upper_bounds_compare.csv", compare_rows)
    write_csv(OUT / "upper_bounds_bins_compare.csv", all_bin_rows)


if __name__ == "__main__":
    main()
