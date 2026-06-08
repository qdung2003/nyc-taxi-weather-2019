import csv
import os
import subprocess
import webbrowser
from shutil import which

from pipeline.constants.paths import (
    FEATURE_EDA_RESULTS_DIR,
    PROJECT_ROOT,
    TAXI_EDA_RESULTS_DIR,
    WEATHER_EDA_RESULTS_DIR,
)
from pipeline.services.helpers import dumps_json_compact


DATA_JS_FILE = PROJECT_ROOT / "data" / "dashboard_data.js"
HTML_FILE = PROJECT_ROOT / "pipeline" / "dashboard" / "index.html"

TAXI_STEP_DIRS = {
    "01": "01_schemas",
    "02": "02_low_duplicates",
    "03": "03_high_duplicates",
    "04": "04_payments",
    "05": "05_before_business_rules",
    "06": "06_after_business_rules",
    "07": "07_before_upper_bounds",
    "08": "08_after_upper_bounds",
}

WEATHER_STEP_DIRS = {
    "01": "01_schemas",
    "02": "02_low_duplicates",
    "03": "03_high_duplicates",
    "04": "04_before_business_rules",
    "05": "05_after_business_rules",
}

FEATURE_STEP_DIRS = {
    "01": "01_profile_features",
    "02": "02_daily_weather_metrics",
    "03": "03_weather_impact_metrics",
}

RAW_TEXT_KEYS = {
    "all_match",
    "avg_temp_level",
    "column_name",
    "csv_type",
    "data_type",
    "database_type",
    "date",
    "day_type",
    "description",
    "file",
    "file_directory",
    "file_name",
    "files_directory",
    "group_by",
    "match",
    "metric",
    "parquet_type",
    "rain_level",
    "rain_status",
    "reference_file",
    "rule_name",
    "table",
    "temp_range_level",
    "value",
    "value_range",
    "warehouse_database_path",
    "weather_level",
}


def normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def parse_scalar(value: str):
    stripped = value.strip()
    if stripped == "":
        return value

    lowered = stripped.lower()
    if lowered == "null":
        return None
    if lowered == "yes":
        return True
    if lowered == "no":
        return False

    integer_candidate = stripped.lstrip("+-")
    if integer_candidate.isdigit():
        try:
            return int(stripped)
        except ValueError:
            pass

    try:
        return float(stripped)
    except ValueError:
        return value


def parse_csv_value(key: str, value: str):
    return value if key in RAW_TEXT_KEYS else parse_scalar(value)


def read_csv_columnar(path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = [normalize_key(name) for name in (reader.fieldnames or []) if name is not None]
        columns = {fieldname: [] for fieldname in fieldnames}
        for row in reader:
            for raw_key, raw_value in row.items():
                if raw_key is None:
                    continue
                key = normalize_key(raw_key)
                value = raw_value or ""
                parser = parse_scalar if key == "value" else parse_csv_value
                columns[key].append(parser(key, value) if parser is parse_csv_value else parser(value))
    return columns


def sort_csv_files(paths):
    return sorted(paths, key=lambda path: (0 if path.stem == "metadata" else 1, path.stem))


def build_step_payload(step_dir) -> dict:
    return {
        csv_path.stem: read_csv_columnar(csv_path)
        for csv_path in sort_csv_files(step_dir.glob("*.csv"))
    }


def build_domain_payload(results_dir, step_dirs: dict[str, str]) -> list[dict]:
    steps = []
    for dirname in step_dirs.values():
        step_dir = results_dir / dirname
        if step_dir.exists():
            steps.append(build_step_payload(step_dir))
    return steps


def build_payload() -> dict:
    return {
        "taxi": build_domain_payload(TAXI_EDA_RESULTS_DIR, TAXI_STEP_DIRS),
        "weather": build_domain_payload(WEATHER_EDA_RESULTS_DIR, WEATHER_STEP_DIRS),
        "feature": build_domain_payload(FEATURE_EDA_RESULTS_DIR, FEATURE_STEP_DIRS),
    }


def open_dashboard_html() -> None:
    resolved_html = HTML_FILE.resolve()
    browser_url = resolved_html.as_uri()
    methods: list[tuple[str, callable]] = []

    methods.append(("webbrowser.open", lambda: webbrowser.open(browser_url, new=2)))

    browser_candidates = [
        ("msedge", ["msedge", browser_url]),
        ("chrome", ["chrome", browser_url]),
        ("firefox", ["firefox", browser_url]),
        ("edge-path", [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", browser_url]),
        ("chrome-path", [r"C:\Program Files\Google\Chrome\Application\chrome.exe", browser_url]),
        ("chrome-path-x86", [r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", browser_url]),
        ("firefox-path", [r"C:\Program Files\Mozilla Firefox\firefox.exe", browser_url]),
    ]

    for name, command in browser_candidates:
        executable = command[0]
        if os.path.isabs(executable):
            if os.path.exists(executable):
                methods.append((
                    name,
                    lambda cmd=command: subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                    ),
                ))
        elif which(executable):
            methods.append((
                name,
                lambda cmd=command: subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                ),
            ))

    methods.extend([
        (
            "rundll32 FileProtocolHandler",
            lambda: subprocess.run(
                ["rundll32.exe", "url.dll,FileProtocolHandler", browser_url],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            ),
        ),
        (
            "cmd start",
            lambda: subprocess.run(
                ["cmd.exe", "/c", "start", "", browser_url],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            ),
        ),
        (
            "powershell Start-Process",
            lambda: subprocess.run(
                [
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"Start-Process '{browser_url}'",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            ),
        ),
    ])

    failures = []
    for method_name, method in methods:
        try:
            method()
            print(f"Opened dashboard with {method_name}: {resolved_html}")
            return
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"{method_name}: {exc}")

    print(f"Warning: cannot open HTML automatically: {resolved_html}")
    for failure in failures:
        print(f"  - {failure}")


def main(open_html: bool = True) -> None:
    payload_text = dumps_json_compact(
        build_payload(),
        indent=2,
        compact_list_min_items=1,
        compact_all_scalar_arrays=True,
    )
    DATA_JS_FILE.write_text(
        "window.DASHBOARD_DATA = " + payload_text + ";\n",
        encoding="utf-8",
    )
    print(f"Saved: {DATA_JS_FILE}")

    if open_html and os.name == "nt" and HTML_FILE.exists():
        open_dashboard_html()


if __name__ == "__main__":
    main()
