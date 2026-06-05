import re
import urllib.request
from pipeline.constants.paths import WEATHER_RAW_FILE, WEATHER_RAW_URL


def build_weather_download_url() -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", WEATHER_RAW_URL)
    if not match:
        return WEATHER_RAW_URL
    file_id = match.group(1)
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def download_weather_file(*, reset_file: bool = False) -> None:
    if reset_file and WEATHER_RAW_FILE.exists():
        WEATHER_RAW_FILE.unlink()

    WEATHER_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    download_url = build_weather_download_url()
    print(f"Downloading from {download_url}\nTo {WEATHER_RAW_FILE}...")
    urllib.request.urlretrieve(download_url, str(WEATHER_RAW_FILE))
    print("Download completed successfully!")


def ensure_weather_raw_file():
    if not WEATHER_RAW_FILE.exists():
        print("INFO: Missing weather CSV file. Downloading...")
        download_weather_file()
    return WEATHER_RAW_FILE


def main() -> None:
    download_weather_file(reset_file=True)


if __name__ == "__main__":
    main()
