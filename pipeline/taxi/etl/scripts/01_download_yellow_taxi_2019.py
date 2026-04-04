# -*- coding: utf-8 -*-
import os


import requests

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
TAXI_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(TAXI_ROOT, "raw")

# tao thu muc neu chua co
os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_file(url, dest_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    print(f"Downloaded: {dest_path}")


def main():
    year = 2019

    for month in range(1, 13):
        month_str = f"{month:02d}"
        filename = f"yellow_tripdata_{year}-{month_str}.parquet"
        url = f"{BASE_URL}/{filename}"
        dest_path = os.path.join(OUTPUT_DIR, filename)

        print(f"Downloading {url} ...")
        download_file(url, dest_path)

    print("All files downloaded successfully!")


if __name__ == "__main__":
    main()

