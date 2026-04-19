import urllib.request
import re
from pipeline.services.paths import WEATHER_RAW_URL, DATA_DIR

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / "NYC_Central_Park_weather_1869-2022.csv"
    download_url = WEATHER_RAW_URL
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', WEATHER_RAW_URL)
    if match:
        file_id = match.group(1)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    print(f"Downloading from {download_url} \nTo {output_file}...")
    urllib.request.urlretrieve(download_url, str(output_file))
    print("Download completed successfully!")


