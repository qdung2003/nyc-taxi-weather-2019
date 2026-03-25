# 🚖 NYC Taxi & Weather Data Pipeline (2019)

## 🚧 Status

This project is currently **work in progress**.

---

## 📌 Goal

Build a data pipeline to analyze the relationship between:

* NYC taxi trips
* Weather conditions (2019)

---

## 📊 Data Sources

* NYC Taxi Data: [https://home4.nyc.gov/site/tlc/about/tlc-trip-record-data.page](https://home4.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
* Weather Data: [https://www.kaggle.com/datasets/danbraswell/new-york-city-weather-18692022](https://www.kaggle.com/datasets/danbraswell/new-york-city-weather-18692022)

---

## 🏗️ Planned Architecture

```
Taxi Data + Weather Data
        ↓
Ingestion (Python / PyArrow)
        ↓
Transformation (Pandas / SQL)
        ↓
Storage (PostgreSQL)
        ↓
Analysis
```

---

## 🔄 Current Progress

* [x] Setup project structure
* [ ] Ingest taxi data
* [ ] Ingest weather data
* [ ] Data cleaning & transformation
* [ ] Join datasets
* [ ] Load to database
* [ ] Analysis

---

## ⚙️ Tech Stack

* Python
* Pandas / PyArrow
* PostgreSQL
* Docker (planned)

---

## 🚀 Next Steps

* Implement ingestion pipeline
* Handle large parquet files
* Design database schema
