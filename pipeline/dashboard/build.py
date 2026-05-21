import json
import os

from pipeline.constants.paths import (
    FEATURE_EDA_RESULTS_DIR,
    PROJECT_ROOT,
    TAXI_EDA_RESULTS_DIR,
    WEATHER_EDA_RESULTS_DIR,
)
from pipeline.services.helpers import dumps_json_compact


DATA_JS_FILE = PROJECT_ROOT / "data" / "dashboard_data.js"
HTML_FILE = PROJECT_ROOT / "pipeline" / "dashboard" / "index.html"

TAXI_STEP_FILES = {
    "01": "01_schemas.json",
    "02": "02_low_duplicates.json",
    "03": "03_high_duplicates.json",
    "04": "04_payments.json",
    "05": "05_before_business_rules.json",
    "06": "06_after_business_rules.json",
    "07": "07_before_upper_bounds.json",
    "08": "08_after_upper_bounds.json",
}

WEATHER_STEP_FILES = {
    "01": "01_schemas.json",
    "02": "02_low_duplicates.json",
    "03": "03_high_duplicates.json",
    "04": "04_before_business_rules.json",
    "05": "05_after_business_rules.json",
}

FEATURE_STEP_FILES = {
    "01": "01_profile_features.json",
    "02": "02_daily_weather_metrics.json",
    "03": "03_weather_impact_metrics.json",
}


def build_domain_payload(results_dir, step_files: dict[str, str]) -> dict:
    steps_data = {}
    for step, filename in step_files.items():
        json_path = results_dir / filename
        if json_path.exists():
            steps_data[step] = {"data": json.loads(json_path.read_text(encoding="utf-8"))}
    return steps_data


def build_payload() -> dict:
    return {
        "taxi": build_domain_payload(TAXI_EDA_RESULTS_DIR, TAXI_STEP_FILES),
        "weather": build_domain_payload(WEATHER_EDA_RESULTS_DIR, WEATHER_STEP_FILES),
        "feature": build_domain_payload(FEATURE_EDA_RESULTS_DIR, FEATURE_STEP_FILES),
    }


def main(open_html: bool = True) -> None:
    payload_text = dumps_json_compact(
        build_payload(),
        indent=2,
        compact_list_min_items=1,
        align_compact_array_items=True,
        compact_all_scalar_arrays=True,
    )
    DATA_JS_FILE.write_text(
        "window.DASHBOARD_DATA = " + payload_text + ";\n",
        encoding="utf-8",
    )
    print(f"Saved: {DATA_JS_FILE}")

    if open_html and os.name == "nt" and HTML_FILE.exists():
        try:
            os.startfile(str(HTML_FILE))
        except OSError as exc:
            print(f"Warning: cannot open HTML automatically: {exc}")


if __name__ == "__main__":
    main()
