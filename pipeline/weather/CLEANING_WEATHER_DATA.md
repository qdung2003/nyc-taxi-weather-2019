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

Quy trình ETL cho dữ liệu thời tiết bao gồm 2 bước chính:

1. **`01_get_weather_2019.py`**:
    - Đọc file CSV thô từ `raw/NYC_Central_Park_weather_1869-2022.csv`.
    - Lọc và trích xuất chỉ duy nhất các bản ghi của năm **2019**.
    - Kết quả lưu tại: `etl/results/01_get_weather_2019.csv`.

2. **`02_convert_type.py`**:
    - Áp dụng các **Business Rules** (lọc giá trị âm, lọc giá trị phi thực tế).
    - Thực hiện chuyển đổi đơn vị và làm tròn số liệu.
    - Ép kiểu dữ liệu về `float32` để tối ưu dung lượng.
    - Kết quả lưu song song tại:
        - `etl/results/02_convert_type.parquet`
        - `clean/cleaned_weather_2019.parquet`

---

## 5. Chiến lược tối ưu hóa kiểu dữ liệu (Dtypes)

Dữ liệu thời tiết được lưu trữ dưới định dạng **Parquet** với kiểu dữ liệu `float32`. Việc này giúp giảm kích thước file và tăng tốc độ xử lý khi thực hiện các phép tính tương quan (correlation) giữa thời tiết và lưu lượng Taxi ở các bước phân tích sâu hơn.
