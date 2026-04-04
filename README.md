# 🚖 NYC Taxi & Weather Data Pipeline (2019)

## 🚧 Status

Dự án đang ở giai đoạn **Kết hợp dữ liệu (Data Joining)** sau khi đã hoàn tất quy trình ETL cho cả hai nguồn dữ liệu Taxi và Weather.

---

## 📌 Goal

Xây dựng hệ thống thu thập và xử lý dữ liệu để phân tích mối tương quan giữa:

* Các chuyến đi của Taxi NYC (Yellow Taxi 2019)
* Điều kiện thời tiết tại NYC (Trạm Central Park 2019)

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
Optimized Clean Storage (Parquet)
        ↓
JOINING (Next Phase) → Analysis & Loading
```

---

## 🔄 Current Progress

* [x] **Project Structure**: Đã thiết lập cấu trúc pipeline cho Taxi và Weather.
* [x] **Taxi Ingestion**: Tải và gộp 12 tháng dữ liệu năm 2019.
* [x] **Weather Ingestion**: Trích xuất dữ liệu Central Park năm 2019.
* [x] **Data Cleaning & Transformation**:
    * **Taxi**: Lọc Business Rules, xử lý tiền Tip/Phụ phí, cắt Outlier động, nén dtypes.
    * **Weather**: Chuyển đổi sang hệ mét (Celsius/Cm), lọc giá trị âm vô lý.
* [x] **EDA Dashboards**: Tạo các báo cáo dashboard trực quan cao cấp (Premium Visuals).
* [/] **Join datasets**: Đang triển khai logic kết hợp theo khung thời gian.
* [ ] **Load to database**: (Planned)
* [ ] **Final Analysis**: (Planned)

---

## 📖 Documentation

* [Chiến lược dọn dẹp dữ liệu Taxi](pipeline/taxi/CLEANING_TAXI_DATA.md)
* [Chiến lược dọn dẹp dữ liệu Thời tiết](pipeline/weather/CLEANING_WEATHER_DATA.md)

---

## ⚙️ Tech Stack

* **Language**: Python
* **Processing**: Pandas, PyArrow (Dùng để xử lý file lớn)
* **Storage**: Parquet (Tối ưu hóa nén zstd)
* **Visualization**: SVG Dashboards (Embedded in HTML)

---

## 🚀 Next Steps

* Kết hợp (Join) bộ dữ liệu Taxi và Weather theo ngày/giờ.
* Thiết lập Database Schema (PostgreSQL) để lưu trữ dữ liệu sạch.
* Thực hiện phân tích chuyên sâu về tác động của thời tiết đến lưu lượng Taxi.
