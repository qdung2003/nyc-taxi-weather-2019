# Data Cleaning Strategy - NYC Central Park Weather 2019

## 1. Nguồn tài liệu (Data Source)

Dữ liệu được tham chiếu từ bộ dữ liệu lịch sử của Trạm quan trắc Central Park (NYC):

- **Kaggle**: [New York City Weather (1869-2022)](https://www.kaggle.com/datasets/danbraswell/new-york-city-weather-18692022)

---

## 2. Bảng kế hoạch dọn dẹp tóm tắt

| # | Cột | Quy tắc lọc | Chuyển đổi đơn vị | Lý do / Ràng buộc |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `DATE` | Giữ năm 2019 | YYYY-MM-DD | Chỉ phân tích cho năm 2019. |
| 2 | `PRCP` | `v >= 0` | Inch -> Cm (x 2.54) | Lượng mưa không thể âm. |
| 3 | `SNOW` | `v >= 0` | Inch -> Cm (x 2.54) | Lượng tuyết rơi không thể âm. |
| 4 | `SNWD` | `v >= 0` | Inch -> Cm (x 2.54) | Độ dày tuyết phủ không thể âm. |
| 5 | `TMIN` | `v > -459.67°F` | °F -> °C | Giới hạn vật lý (Độ không tuyệt đối). |
| 6 | `TMAX` | `v > -459.67°F` | °F -> °C | Giới hạn vật lý (Độ không tuyệt đối). |

---

## 3. Quy tắc chi tiết (Detailed Rules)

### Rule 1: Chuyển đổi đơn vị (Unit Conversion)
Để đồng bộ với các tiêu chuẩn quốc tế và dễ phân tích, dữ liệu được chuyển từ hệ đo lường Anh (Imperial) sang hệ mét (Metric):
- **Lượng mưa/Tuyết**: Nhân với `2.54` để chuyển từ Inch sang Centimeter (cm).
- **Nhiệt độ**: Sử dụng công thức `Celsius = (Fahrenheit - 32) * 5/9`.
- **Làm tròn**: Tất cả các giá trị số đo được làm tròn đến `2` chữ số thập phân.

### Rule 2: Xử lý dữ liệu thiếu (Missing Data)
- Các bản ghi bị thiếu thông tin tại các cột chỉ số quan trọng (`PRCP`, `SNOW`, `SNWD`, `TMIN`, `TMAX`) sẽ bị loại bỏ để đảm bảo tính nhất quán (Row-wise deletion).

---

## 4. Luồng thực thi Scripts

Quy trình ETL cho dữ liệu thời tiết (đã đồng bộ với mảng Taxi dùng DuckDB) bao gồm 4 bước chính:

1. **`01_download_weather.py`**:
    - Tải nguyên bản CSV thô từ online vào thư mục data runtime (`DATA_DIR/NYC_Central_Park_weather_1869-2022.csv`).

2. **`02_ingest_data.py`**:
    - Sử dụng `read_csv_auto` của DuckDB để ingest trực tiếp CSV vào bảng thô `TABLE_WEATHER_RAW` trong cơ sở dữ liệu `taxi_and_weather.db`.

3. **`03_apply_business_rules.py`**:
    - Nhận vào từ bảng `TABLE_WEATHER_RAW` và thiết lập VIEW `v_weather_03_business_rules`.
    - Áp dụng các **Business Rules** (lọc dòng ngày tháng thuộc 2019, bỏ các ô null, lọc giá trị âm, và chặn giá trị phi thực tế).
    - Thực hiện quy đổi hệ đơn vị đo lường (Inch sang Cm, độ Fahrenheit sang Celsius) và làm tròn 2 chữ số thập phân hoàn toàn bằng các tính năng SQL bên trong CTEs.

4. **`04_optimize_dtypes.py`**:
    - Ép định dạng khắt khe (`CAST`) từ view sang bảng vật lý đích `TABLE_WEATHER_CLEAN`.
    - Các metric đo đạc tự động mang chuẩn `FLOAT`, tối ưu cực đỉnh trong RAM.

---

## 5. Chiến lược tối ưu hóa kiểu dữ liệu (Dtypes)

Thay vì xuất file **Parquet** thuần túy chứa float32 rời rạc, mọi cột dữ liệu sạch giờ đây được lưu đồng thời ngay trong File Database gốc **DuckDB** (`TABLE_WEATHER_CLEAN`) cùng tầng với dữ liệu mảng Taxi. Các biến metric gán chuẩn `FLOAT` giúp hệ thống truy vấn được cô đọng, triệt tiêu I/O đọc rời các mảnh parquet trung gian nhằm đẩy nhanh siêu tốc độ xử lý khi thực hiện các phép join và tập trung tính tương quan (correlation factor) giữa lưu lượng Taxi và thời tiết ở các bước phân tích sau đó!
