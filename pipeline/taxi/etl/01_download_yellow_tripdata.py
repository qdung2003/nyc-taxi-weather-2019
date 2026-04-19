import shutil
import requests
from tqdm import tqdm
from pipeline.services.paths import TAXI_RAW_TEMP_DIR, TAXI_RAW_URL
from pipeline.services.tqdm_settings import TQDM_DISABLE, TQDM_MIN_INTERVAL


# Temporary directory; ingest (02) will delete after loading.
if TAXI_RAW_TEMP_DIR.exists():
    shutil.rmtree(TAXI_RAW_TEMP_DIR)

TAXI_RAW_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url, dest_path, filename) -> None:
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


def main() -> None:
    year = 2019
    months = list(range(1, 13))

    overall_bar_setup = {
        "total": len(months),
        "desc": "Download All Files",
        "unit": "file",
        "disable": TQDM_DISABLE,
        "leave": True,
        "mininterval": TQDM_MIN_INTERVAL,
    }

    with tqdm(**overall_bar_setup) as overall_bar:
        for month in months:
            month_str = f"{month:02d}"
            filename = f"yellow_tripdata_{year}-{month_str}.parquet"
            url = f"{TAXI_RAW_URL}/{filename}"
            dest_path = TAXI_RAW_TEMP_DIR / filename

            download_file(url, dest_path.as_posix(), filename)
            overall_bar.update(1)

    print("All files downloaded successfully!")


