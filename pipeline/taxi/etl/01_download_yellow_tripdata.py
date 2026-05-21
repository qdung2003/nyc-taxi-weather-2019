import requests
from tqdm import tqdm
from pipeline.constants.paths import TAXI_RAW_TEMP_DIR, TAXI_RAW_URL
from pipeline.constants.times import MONTHS, YEAR
from pipeline.constants.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


def get_expected_taxi_raw_filenames() -> list[str]:
    return [
        f"yellow_tripdata_{YEAR}-{month:02d}.parquet"
        for month in MONTHS
    ]


def download_file(filenames: list[str] | None = None) -> None:
    TAXI_RAW_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    filenames = filenames or get_expected_taxi_raw_filenames()
    overall_bar_setup = {
        "total": len(filenames),
        "desc": "Download files",
        "unit": "file",
        "disable": TQDM_DISABLE,
        "leave": True,
        "mininterval": TQDM_MIN_INTERVAL,
    }

    with tqdm(**overall_bar_setup) as overall_bar:
        for filename in filenames:
            url = f"{TAXI_RAW_URL}/{filename}"
            dest_path = TAXI_RAW_TEMP_DIR / filename

            try:
                response = requests.get(url, stream=True, timeout=60)
                response.raise_for_status()  # check HTTP errors
            except requests.exceptions.HTTPError as err:
                print(f"HTTP error: {err}")
            except requests.exceptions.RequestException as err:
                print(f"Request error: {err}")
            else:
                total_capacity = response.headers.get("content-length")
                bar_setup = {
                    "unit": "B",
                    "unit_scale": True,
                    "unit_divisor": 1024,
                    "desc": filename,
                    "disable": TQDM_DISABLE,
                    "leave": False,
                    "mininterval": TQDM_MIN_INTERVAL,
                }

                if total_capacity is not None:
                    bar_setup["total"] = int(total_capacity)

                with open(dest_path, "wb") as f, tqdm(**bar_setup) as bar:
                    for chunk in response.iter_content(chunk_size=1024**2):  # 1 MB
                        if not chunk:
                            continue
                        f.write(chunk)
                        bar.update(len(chunk))

            overall_bar.update(1)

    print("All files downloaded successfully!")


def ensure_taxi_raw_files() -> list:
    expected_filenames = get_expected_taxi_raw_filenames()
    existing_filenames = {
        path.name
        for path in TAXI_RAW_TEMP_DIR.glob(f"yellow_tripdata_{YEAR}-*.parquet")
    }
    missing_filenames = [
        filename for filename in expected_filenames
        if filename not in existing_filenames
    ]
    if missing_filenames:
        print(
            f"INFO: Missing {len(missing_filenames)} of {len(expected_filenames)} taxi parquet files. "
            "Downloading missing files..."
        )
        download_file(missing_filenames)

    still_missing_filenames = [
        filename for filename in expected_filenames
        if not (TAXI_RAW_TEMP_DIR / filename).exists()
    ]
    if still_missing_filenames:
        raise SystemExit(
            "Missing taxi parquet files after download attempt: "
            + ", ".join(still_missing_filenames)
        )

    return [TAXI_RAW_TEMP_DIR / filename for filename in expected_filenames]


def main() -> None:
    ensure_taxi_raw_files()


if __name__ == "__main__":
    main()




