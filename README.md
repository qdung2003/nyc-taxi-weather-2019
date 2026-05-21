# 🚖 NYC Taxi & Weather Data Pipeline (2019)

## 🚧 Status

The project has completed the **ETL → EDA → Feature Joining → Dashboard** flow for 2019 Taxi and Weather data.

---

## 📌 Goal

Build a data collection and processing pipeline to analyze the relationship between:

* NYC Yellow Taxi trips in 2019
* NYC weather conditions from the Central Park station in 2019

---

## 📊 Data Sources

* **NYC Taxi Data**: [Official TLC Trip Record Data](https://home4.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
* **Weather Data**: [NYC Weather (1869-2022) - Kaggle](https://www.kaggle.com/datasets/danbraswell/new-york-city-weather-18692022)

---

## 🏗️ Architecture

```
Raw Data (CSV/Parquet)
        ↓
Ingestion Pipeline (PyArrow / Pandas)
        ↓
Cleaning & Business Rules (Metric Units / Outlier Cutting)
        ↓
Optimized Clean Storage (DuckDB)
        ↓
Feature Joining → EDA Analysis → HTML Dashboard
```

---

## 🔄 Current Progress

* [x] **Project Structure**: Set up the pipeline structure for Taxi and Weather.
* [x] **Taxi Ingestion**: Downloaded and ingested 12 monthly files for 2019.
* [x] **Weather Ingestion**: Extracted Central Park weather data for 2019.
* [x] **Data Cleaning & Transformation**:
    * **Taxi**: Applied business rules, handled tips/surcharges, applied dynamic outlier cuts, and optimized dtypes.
    * **Weather**: Converted to metric units (Celsius/Cm) and filtered invalid negative values.
* [x] **Feature Joining**: Created the `taxi_weather_features` table by joining Taxi and Weather by date.
* [x] **EDA Dashboards**: Built HTML/SVG dashboards for Taxi, Weather, and Feature EDA.
* [x] **Final Analysis**: Summarized findings in `pipeline/feature/FEATURE_ANALYSIS.md`.

---

## 📖 Documentation

* [Taxi data cleaning strategy](pipeline/taxi/CLEANING_TAXI_DATA.md)
* [Weather data cleaning strategy](pipeline/weather/CLEANING_WEATHER_DATA.md)

---

## ⚙️ Tech Stack

* **Language**: Python
* **Processing**: DuckDB SQL, with PyArrow/Pandas where needed for data reading
* **Storage**: DuckDB file database (`data/taxi_and_weather.db`)
* **Visualization**: SVG Dashboard (HTML/CSS/JS)

---

## 🚀 Next Steps

* Re-run the full pipeline with `python main.py --all` when data or rules change.
* Rebuild the dashboard with `python main.py dashboard`.
* Extend the analysis if hourly weather data, seasonality, or holiday features are added.
