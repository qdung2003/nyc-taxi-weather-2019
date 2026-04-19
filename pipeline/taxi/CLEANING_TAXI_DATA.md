# Data Cleaning Strategy - NYC Yellow Taxi 2019

## 1. Nguồn tài liệu (Wayback)

Dữ liệu năm 2019 được tham chiếu qua các tài liệu chính thống của TLC:

1. [Data Dictionary - Yellow Trip Records (2019)](https://web.archive.org/web/20190808095554/https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
2. [Taxi Fare Rates (2019)](https://web.archive.org/web/20190801021305/https://www.nyc.gov/site/tlc/passengers/taxi-fare.page)
3. [TLC Passenger FAQ](https://web.archive.org/web/20260122112926/https://www.nyc.gov/site/tlc/passengers/passenger-frequently-asked-questions.page)
4. [Trip Record User Guide](https://web.archive.org/web/20190810080518/https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf)

---

## 2. Bảng kế hoạch dọn dẹp tóm tắt

| # | Cột | Khoảng lọc | Dẫn chứng (text) | Link |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `VendorID` | `[1, 2]` | Theo mã hãng TPEP/LPEP hợp lệ. | 1 |
| 2 | `passenger_count` | `[1, 5]` | Taxi chở tối đa 5 hành khách (quy định TLC; không tính lap child). | 3 |
| 3 | `RatecodeID` | `[1, 6]` | Theo mã RatecodeID hợp lệ từ 1-6. | 1 |
| 4 | `store_and_fwd_flag` | `['Y', 'N']` | Cờ chỉ nhận giá trị `Y` hoặc `N`. | 1 |
| 5 | `PULocationID`, `DOLocationID` | `[1, 263]` | “...pickup or drop-off... populated by numbers ranging from 1-263.” | 4 |
| 6 | `payment_type` | `[1, 4]` | Giữ các nhóm chính; loại bỏ 5 (Unknown) và 6 (Void). | 1 + Decision |
| 7 | `trip_distance` | `(0, Max*]` | Lọc > 0 và cắt ngưỡng Max từ Simulation. | Decision |
| 8 | `fare_amount` | `(0, Max*]` | Áp dụng sau chuẩn hóa 2.5 USD; cắt ngưỡng Max. | Decision |
| 9 | `extra` | `{0.0, 0.5, 1.0}` | Áp dụng sau bước chuẩn hóa (tách phí 2.5 USD). | 2 + Decision |
| 10 | `mta_tax` | `{0.5}` | “Plus 50 cents MTA State Surcharge...” | 2 + Decision |
| 11 | `improvement_surcharge` | `{0.3}` | “Plus $0.3 Improvement Surcharge.” | 2 + Decision |
| 12 | `congestion_surcharge` | `{0, 0.75, 2.5}` | “Plus $2.50 (Yellow Taxi) ...”; chuẩn hóa `null -> 0`. | 2 + EDA |
| 13 | `tip_amount` | `[0, Max*]` | Ràng buộc theo `payment_type`; cắt ngưỡng Max. | Decision |
| 14 | `total_amount` | `(0, Max*]` | Lọc > 0 và cắt ngưỡng Max từ Simulation. | Decision |

*\*Max: Cận trên được tính toán động bởi script mô phỏng EDA 11.*

---

## 3. Quy tắc chi tiết (Detailed Rules)

### Rule 1: Chuẩn hóa phí hạ tầng (The 2.5 USD Shift)
Trong dữ liệu 2019, nhiều trường hợp ghi nhận phí **$2.50 Congestion Surcharge** nhầm vào cột `extra`. 
- **Dấu hiệu**: `extra >= 2.5`.
- **Xử lý**: Lấy 2.5 USD từ `extra` cộng bù vào `fare_amount`. Việc này đảm bảo biểu đồ phân bổ của `extra` chỉ còn các giá trị phụ phí giờ cao điểm/ban đêm hợp lệ {0.5, 1.0}.

### Rule 2: Logic Tiền tip (Tip vs Payment Type)
TLC chỉ ghi nhận tiền Tip tự động thông qua thẻ tín dụng.
- **Quy tắc**: Nếu `payment_type` không thuộc `{1}` (Thẻ tín dụng), hệ thống sẽ buộc `tip_amount = 0` để tránh các sai số ghi nhận thủ công cho các lượt Cash/Dispute/Free.

### Rule 3: Lọc ngoại lai động (Dynamic Outlier Cutting)
Sử dụng script **EDA 11** để quét dữ liệu và tìm điểm rơi phân bổ tự nhiên. Script `04_apply_upper_bounds.py` sẽ tự động kích hoạt `11_simulate_upper_bounds.py` nếu thiếu file kết quả mô phỏng.

---

## 4. Luồng thực thi Scripts

Quy trình ETL bao gồm 6 giai đoạn chính:

1. **`01_download_yellow_tripdata.py`**: Tải 12 file dữ liệu thô hàng tháng từ Cloudfront TLC.
2. **`02_ingest_data.py`**: Nạp toàn bộ 12 file vào bảng DuckDB `taxi_raw`.
3. **`03_apply_business_rules.py`**:
    - Lọc bản ghi đúng năm 2019 và điều kiện `pickup < dropoff`.
    - Loại bỏ cột `airport_fee`.
    - Áp dụng toàn bộ business rules nền tảng vào view trung gian.
4. **`04_apply_upper_bounds.py`**: Cắt bỏ các kỷ lục giao dịch ảo hoặc phi lý (Outlier Cut).
5. **`05_optimize_dtypes.py`**:
    - Ép lại kiểu dữ liệu để đạt hiệu quả nén cao nhất (~20%).
    - Kết quả được lưu song song tại:
        - bảng DuckDB `taxi_clean`
        - `clean/cleaned_tripdata_2019.parquet`

---

## 5. Chiến lược tối ưu hóa kiểu dữ liệu (Dtypes)

Dữ liệu sạch được nén bằng cách chuyển các kiểu dữ liệu từ `double/int64` sang các kiểu nhỏ hơn như `float32/int32/int8`. Hiệu quả giúp giảm dung lượng từ 1.3GB xuống còn ~1.03GB, tăng tốc độ đọc/ghi dữ liệu ở các giai đoạn phân tích sau.
