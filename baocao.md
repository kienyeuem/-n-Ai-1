# BÁO CÁO ĐỒ ÁN
# FuzzyRide — Hệ thống tính cước xe công nghệ bằng Logic Mờ (Fuzzy Logic)

---

## MỤC LỤC

- **Chương 1.** Tổng quan đề tài và cơ sở lý thuyết
- **Chương 2.** Phân tích bài toán và thiết kế hệ mờ
- **Chương 3.** Cài đặt hệ thống (Web app Flask)
- **Chương 4.** Kết quả thử nghiệm, đánh giá và hướng phát triển

---

## CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI VÀ CƠ SỞ LÝ THUYẾT

### 1.1. Đặt vấn đề

Trong các nền tảng gọi xe công nghệ (Grab, Be, Gojek, Uber…), giá cước cho mỗi
chuyến đi không còn là một con số cố định mà được điều chỉnh **động** theo nhiều
yếu tố thực tế: quãng đường, thời gian dự kiến di chuyển, khung giờ, ngày trong
tuần, mức độ kẹt xe, thời tiết, nhiệt độ, chất lượng không khí, nhu cầu của khách
và số lượng tài xế đang sẵn sàng. Cách tiếp cận truyền thống — dùng các công thức
toán học cứng kiểu *"if traffic > 7 then ×1.5"* — gặp hai hạn chế lớn:

1. **Ranh giới cứng**: tại các ngưỡng (vd: traffic = 6.99 vs 7.01) giá nhảy bậc,
   gây cảm giác bất công cho người dùng.
2. **Khó mở rộng**: với 9–10 biến đầu vào liên tục, số lượng nhánh `if/else`
   bùng nổ tổ hợp, khó duy trì.

**Logic mờ (Fuzzy Logic)** do L. A. Zadeh đề xuất năm 1965 là công cụ phù hợp để
xử lý tri thức mang tính *ngôn ngữ* — *"đường hơi đông"*, *"trời mưa to"*,
*"giờ cao điểm"* — mà con người dùng để ra quyết định hằng ngày. Đề tài này xây
dựng **FuzzyRide**, một web app sử dụng hệ suy diễn mờ Mamdani phân cấp (3 FIS)
để tính hệ số nhân giá và cước cuối cùng cho 3 loại xe (xe máy, ô tô 4 chỗ, ô tô
7 chỗ) một cách trực quan và minh bạch.

### 1.2. Mục tiêu của đề tài

- Mô hình hóa bài toán định giá xe công nghệ bằng **Mamdani Fuzzy Inference
  System** với 10 biến đầu vào (9 biến mờ + 1 biến crisp `vehicle_type`).
- Thiết kế **kiến trúc phân cấp 3 FIS** thay cho 1 FIS phẳng để giảm bùng nổ luật
  ($4^9 \approx 2.6 \times 10^5$ luật → còn ~45 luật).
- Cài đặt thành **web application Flask** với giao diện trực quan: bản đồ
  Leaflet, biểu đồ membership Chart.js, slider điều khiển real-time.
- Cho phép người dùng **đặt xe**, lưu lịch sử và xem thống kê.

### 1.3. Tập mờ và hàm thuộc

Một **tập mờ** $\tilde{A}$ trên vũ trụ $X$ được đặc trưng bởi hàm thuộc
$\mu_{\tilde{A}}: X \to [0, 1]$, gán cho mỗi $x \in X$ một mức độ thuộc.

Các hàm thuộc sử dụng trong đề tài:

- **Tam giác (`trimf`)** — 3 tham số $(a, b, c)$:
$$\mu(x) = \max\left(\min\left(\frac{x-a}{b-a},\; \frac{c-x}{c-b}\right),\; 0\right)$$

- **Hình thang (`trapmf`)** — 4 tham số $(a, b, c, d)$, dùng cho hai đầu mút
  (vd: `very_long`, `late_night`).

### 1.4. Hệ suy diễn mờ Mamdani

Hệ Mamdani gồm 4 khối chính:

1. **Fuzzification** — chuyển đầu vào số rõ thành mức thuộc trên các tập mờ.
2. **Rule evaluation** — luật dạng `IF x is A AND y is B THEN z is C`; toán tử
   AND dùng phép `min` (T-norm).
3. **Aggregation** — tổng hợp đầu ra của mọi luật bằng phép `max` (S-norm).
4. **Defuzzification** — đưa kết quả mờ về số rõ, mặc định dùng phương pháp
   **trọng tâm (Centroid of Area)**:
$$z^* = \frac{\int z \cdot \mu_{C}(z)\,dz}{\int \mu_{C}(z)\,dz}$$

### 1.5. Hệ mờ phân cấp (Hierarchical FIS)

Khi số biến đầu vào lớn, một FIS phẳng cần $\prod_i n_i$ luật (với $n_i$ là số
tập mờ của biến $i$). Cách hiệu quả là **chia hệ thành nhiều FIS nhỏ** rồi nối
đầu ra: hệ FIS-A xử lý nhóm biến A, FIS-B xử lý nhóm biến B, … rồi nhân/cộng kết
quả. Đề tài chọn **3 FIS** tương ứng 3 nhóm yếu tố tự nhiên: *cơ bản – môi
trường – cung cầu*, đầu ra cuối là **tích** của 3 hệ số nhân.

### 1.6. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend | Python 3, Flask |
| Tính toán mờ | `scikit-fuzzy` (`skfuzzy.control`), NumPy, SciPy |
| Frontend | HTML5, CSS3 (gradient, glassmorphism, dark theme) |
| Visualization | Chart.js (membership functions), Leaflet (bản đồ) |
| Lưu trữ | JSON file (`bookings.json`, `locations.json`) |

---

## CHƯƠNG 2. PHÂN TÍCH BÀI TOÁN VÀ THIẾT KẾ HỆ MỜ

### 2.1. Phân tích biến đầu vào / đầu ra

Đề tài sử dụng **10 biến đầu vào** (9 biến mờ + 1 biến rõ) chia thành 3 nhóm:

#### 2.1.1. Nhóm Quãng đường & Thời gian (FIS-1)

| Biến | Miền giá trị | Đơn vị | Tập mờ |
|---|---|---|---|
| `distance` | 0 – 50 | km | `short`, `medium`, `long`, `very_long` |
| `estimated_time` | 0 – 120 | phút | `fast`, `normal`, `slow`, `very_slow` |
| `time_of_day` | 0 – 24 | giờ | `early_morning`, `morning_rush`, `noon`, `afternoon`, `evening_rush`, `night`, `late_night` |
| `day_type` | 0 – 2 | crisp | `weekday`, `weekend`, `holiday` |

#### 2.1.2. Nhóm Giao thông & Môi trường (FIS-2)

| Biến | Miền giá trị | Tập mờ |
|---|---|---|
| `traffic_level` | 0 – 10 | `smooth`, `moderate`, `heavy`, `jammed` |
| `weather` | 0 – 4 | `sunny`, `cloudy`, `light_rain`, `heavy_rain`, `storm` |
| `temperature` | 15 – 40 °C | `cool`, `comfortable`, `hot`, `very_hot` |
| `air_quality` | 0 – 500 AQI | `good`, `moderate`, `unhealthy`, `hazardous` |

#### 2.1.3. Nhóm Cung – Cầu (FIS-3)

| Biến | Miền giá trị | Tập mờ |
|---|---|---|
| `demand_level` | 0 – 10 | `low`, `medium`, `high`, `very_high` |
| `driver_availability` | 0 – 50 (xe) | `scarce`, `few`, `normal`, `abundant` |

#### 2.1.4. Biến rõ — loại xe

`vehicle_type ∈ {bike, 4s, 7s}`, không tham gia quá trình suy diễn mờ mà chỉ
dùng để tra **bảng giá mở cửa & đơn giá / km** ở bước cuối.

#### 2.1.5. Đầu ra của các FIS

| Đầu ra | Miền | Ý nghĩa | Tập mờ |
|---|---|---|---|
| `base_multiplier` | 0.8 – 2.5 | Hệ số cơ bản theo quãng đường & giờ | `low`, `normal`, `high`, `very_high` |
| `environment_factor` | 1.0 – 1.5 | Phụ thu môi trường | `none`, `mild`, `strong`, `severe` |
| `surge_factor` | 1.0 – 2.0 | Phụ thu cung-cầu | `none`, `mild`, `high`, `very_high` |

### 2.2. Kiến trúc Hierarchical 3-FIS

```
┌──────────────── FIS-1: Base Multiplier (20 luật) ────────────────┐
│  distance + estimated_time + time_of_day + day_type              │
│                  →  base_multiplier ∈ [0.8, 2.5]                 │
└──────────────────────────────────────────────────────────────────┘
┌──────────────── FIS-2: Environment Factor (15 luật) ─────────────┐
│  traffic_level + weather + temperature + air_quality             │
│                  →  environment_factor ∈ [1.0, 1.5]              │
└──────────────────────────────────────────────────────────────────┘
┌──────────────── FIS-3: Surge Factor (10 luật) ───────────────────┐
│  demand_level + driver_availability                              │
│                  →  surge_factor ∈ [1.0, 2.0]                    │
└──────────────────────────────────────────────────────────────────┘

total_multiplier = base_multiplier × environment_factor × surge_factor
final_fare       = (open_fee + per_km × distance) × total_multiplier
```

**Lý do chọn 3 FIS**: 9 biến mờ × 4 tập trung bình → một FIS phẳng cần
$\sim 4^9 = 262{,}144$ luật. Phân chia 4 + 4 + 2 biến cho 3 FIS → tổng còn
**45 luật**, dễ kiểm soát, dễ giải thích, dễ mở rộng.

### 2.3. Định nghĩa tập mờ chi tiết

Trích một số tập mờ tiêu biểu (xem [app.py](app.py#L62-L130) cho bản đầy đủ):

```python
distance['short']     = trimf([0, 0, 6])          # ≤ 6 km hoàn toàn ngắn
distance['medium']    = trimf([4, 12, 22])
distance['long']      = trimf([18, 28, 40])
distance['very_long'] = trapmf([35, 45, 50, 50])  # bão hòa từ 45 km

weather['sunny']      = trimf([0, 0, 1])
weather['cloudy']     = trimf([0.5, 1.2, 2])
weather['light_rain'] = trimf([1.5, 2.2, 3])
weather['heavy_rain'] = trimf([2.5, 3.2, 4])
weather['storm']      = trapmf([3.5, 3.8, 4, 4])
```

### 2.4. Hệ luật

#### 2.4.1. FIS-1 — 20 luật (trích)

```
R1:  IF distance is short  AND estimated_time is fast      THEN base is low
R6:  IF distance is medium AND estimated_time is slow      THEN base is high
R10: IF distance is long   AND estimated_time is very_slow THEN base is very_high
R11: IF distance is very_long                              THEN base is very_high
R12: IF time_of_day is morning_rush AND day_type is weekday THEN base is high
R18: IF day_type is holiday                                THEN base is very_high
```

#### 2.4.2. FIS-2 — 15 luật (trích)

```
R1: IF traffic is smooth AND weather is sunny AND temperature is comfortable
       THEN environment is none
R7: IF traffic is jammed AND weather is heavy_rain  THEN environment is severe
R10: IF weather is storm                            THEN environment is severe
R14: IF air_quality is hazardous                    THEN environment is severe
```

#### 2.4.3. FIS-3 — 10 luật (trích)

```
R1:  IF demand is low      AND drivers is abundant THEN surge is none
R8:  IF demand is high     AND drivers is scarce   THEN surge is very_high
R10: IF demand is very_high AND drivers is scarce  THEN surge is very_high
```

### 2.5. Bảng giá theo loại xe

| Mã | Tên | Mở cửa | Đơn giá | Icon |
|---|---|---:|---:|:-:|
| `bike` | Xe máy | 12.000 đ | 4.500 đ/km | 🛵 |
| `4s` | Ô tô 4 chỗ | 25.000 đ | 11.000 đ/km | 🚗 |
| `7s` | Ô tô 7 chỗ | 32.000 đ | 14.000 đ/km | 🚙 |

### 2.6. Quy trình suy diễn cho một chuyến đi

1. Người dùng nhập / chọn 10 biến đầu vào.
2. Backend gọi `compute_all(inputs)` → chạy lần lượt 3 FIS Mamdani.
3. Tính `total_multiplier = bm × ef × sf`.
4. Tính `base_fare = open_fee + per_km × distance`.
5. Tính `final_fare = base_fare × total_multiplier` rồi làm tròn.
6. Trả thêm **mức thuộc** của từng biến cho frontend vẽ vạch trên đồ thị.

---

## CHƯƠNG 3. CÀI ĐẶT HỆ THỐNG

### 3.1. Cấu trúc thư mục

```
deadlineKiennn/
├── app.py                  # Flask app + 3 FIS + REST API
├── requirements.txt        # Flask, numpy, scikit-fuzzy, scipy, networkx
├── README.md
├── data/
│   ├── locations.json      # ~30 địa điểm Hà Nội (lat/lng)
│   └── bookings.json       # Lịch sử đặt xe (sinh khi chạy)
├── templates/
│   └── index.html          # SPA 1 trang, 4 tab
└── static/
    ├── css/style.css       # Dark theme, glassmorphism, gradient
    └── js/app.js           # Slider, Chart.js, Leaflet, fetch API
```

### 3.2. Cài đặt và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
# Mở http://localhost:5000
```

### 3.3. Cài đặt hệ mờ trong [app.py](app.py)

#### 3.3.1. Khai báo biến và tập mờ

Sử dụng `skfuzzy.control.Antecedent` / `Consequent` để khai báo biến vào / ra
cùng vũ trụ, sau đó gán hàm thuộc bằng `fuzz.trimf` / `fuzz.trapmf`. Toàn bộ 10
biến đầu vào và 3 đầu ra được khai báo tại [app.py](app.py#L57-L150).

#### 3.3.2. Xây dựng `ControlSystem` cho 3 FIS

```python
fis1_ctrl = ctrl.ControlSystem(fis1_rules)   # 20 rules
fis2_ctrl = ctrl.ControlSystem(fis2_rules)   # 15 rules
fis3_ctrl = ctrl.ControlSystem(fis3_rules)   # 10 rules
```

#### 3.3.3. Hàm tính toán an toàn `_safe_compute`

Bao bọc lời gọi `ControlSystemSimulation.compute()` trong `try / except` để khi
một số tổ hợp đầu vào hiếm gặp không kích hoạt luật nào, hệ vẫn trả về giá trị
mặc định `1.0` (không phụ thu) thay vì làm crash request.

#### 3.3.4. Hàm `compute_all(inputs)`

Nhận dict 10 biến → clip vào miền hợp lệ → gọi 3 FIS song song → trả về
`base_multiplier`, `environment_factor`, `surge_factor`, `total_multiplier`.

### 3.4. REST API

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/` | Render trang chính `index.html` |
| POST | `/api/calculate` | Tính cước theo 10 biến + loại xe, trả về membership |
| GET | `/api/membership-curves` | Trả tất cả đường cong tập mờ cho Chart.js |
| GET | `/api/places?q=` | Tìm kiếm địa điểm theo tên (bỏ dấu) |
| POST | `/api/route` | Tính khoảng cách & thời gian giữa 2 địa điểm (Haversine × 1.32) |
| GET | `/api/auto-conditions` | Sinh điều kiện môi trường tự động theo giờ hiện tại |
| GET | `/api/bookings` | Liệt kê 20 booking gần nhất |
| POST | `/api/bookings` | Tạo booking mới (lưu vào `bookings.json`) |
| DELETE | `/api/bookings/<id>` | Xóa booking |
| GET | `/api/stats` | Thống kê: số chuyến, tổng tiền, surge trung bình |
| GET | `/api/rules` | Mô tả meta của 3 FIS (đầu vào, đầu ra, số luật) |

### 3.5. Các thuật toán phụ trợ

#### 3.5.1. `haversine_km` — khoảng cách đường chim bay

$$
d = 2R \cdot \arcsin\left(\sqrt{\sin^2\!\frac{\Delta\varphi}{2} + \cos\varphi_1\cos\varphi_2 \sin^2\!\frac{\Delta\lambda}{2}}\right)
$$

với $R = 6371$ km. Khoảng cách đường thật được ước lượng `straight × 1.32`
(hệ số đường vòng trung bình trong nội đô TP. HCM), thời gian dự kiến tính theo
tốc độ trung bình 25 km/h.

#### 3.5.2. `_strip_accents` — chuẩn hóa Unicode để tìm kiếm địa điểm

Sử dụng `unicodedata.normalize('NFD', ...)` rồi lọc combining characters để cho
phép gõ "ho guom" tìm ra "Hồ Gươm".

#### 3.5.3. `api_auto_conditions` — sinh tự động điều kiện thực tế

Trộn hàm Gauss quanh 8h và 18h cho `traffic_level`, hàm sin theo giờ cho
`temperature`, ngẫu nhiên có trọng số cho thời tiết, AQI… nhằm minh họa kịch bản
thực tế khi người dùng nhấn "Áp dụng tự động".

### 3.6. Giao diện (Frontend)

[templates/index.html](templates/index.html) tổ chức **4 tab** trong cùng SPA:

1. **Chuyến đi** — chọn loại xe, nhập điểm đi/đến (autocomplete), tự tính
   `distance` & `estimated_time` từ tọa độ; hiển thị bản đồ Leaflet và kết quả
   cước.
2. **Môi trường** — 6 slider (`traffic`, `weather`, `temperature`, `air_quality`,
   `demand`, `driver_avail`) + nút **Áp dụng tự động** gọi
   `/api/auto-conditions`.
3. **Biến mờ** — 10 biểu đồ Chart.js vẽ membership functions; mỗi đồ thị có
   đường thẳng đứng đánh dấu **giá trị crisp** hiện tại + bảng mức thuộc.
4. **Luật mờ** — liệt kê 45 luật theo nhóm 3 FIS, kèm giải thích.

[static/js/app.js](static/js/app.js) đảm nhiệm gọi API, debounce cập nhật
slider, vẽ Chart.js và quản lý lịch sử booking; [static/css/style.css](static/css/style.css)
cung cấp giao diện dark + gradient + glassmorphism hiện đại.

### 3.7. Lưu trữ

Lịch sử booking lưu vào file JSON [data/bookings.json](data/bookings.json) (có
khóa `Lock` để tránh ghi đè khi đa luồng); dữ liệu ~30 địa điểm TP. HCM đọc một
lần từ [data/locations.json](data/locations.json) khi khởi động.

---

## CHƯƠNG 4. THỬ NGHIỆM, ĐÁNH GIÁ VÀ HƯỚNG PHÁT TRIỂN

### 4.1. Môi trường thử nghiệm

- Windows 10/11, Python 3.11
- Trình duyệt: Edge / Chrome (hỗ trợ Leaflet, Chart.js)
- Server chạy tại `http://127.0.0.1:5000`

### 4.2. Các kịch bản thử nghiệm

#### Kịch bản 1 — Chuyến ngắn, giờ thấp điểm, thời tiết đẹp

```json
{ "distance": 3, "estimated_time": 10, "time_of_day": 14, "day_type": 0,
  "traffic_level": 2, "weather": 0, "temperature": 26, "air_quality": 50,
  "demand_level": 3, "driver_availability": 30, "vehicle": "bike" }
```
**Kỳ vọng**: `total_multiplier ≈ 1.0`, cước gần với giá niêm yết.

#### Kịch bản 2 — Cao điểm chiều, mưa, kẹt xe (test bằng PowerShell ở terminal)

```powershell
$body='{"distance":8,"estimated_time":20,"time_of_day":18,"day_type":0,
"traffic_level":8,"weather":2.5,"temperature":30,"air_quality":120,
"demand_level":7,"driver_availability":10,"vehicle":"bike"}'
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/calculate `
                  -Method POST -Body $body -ContentType 'application/json'
```
**Quan sát**: API trả về `base_multiplier`, `environment_factor`,
`surge_factor`, `total_multiplier`, `final_fare`, `vehicle` — tất cả thay đổi
mượt khi điều chỉnh slider, không có hiện tượng nhảy bậc.

#### Kịch bản 3 — Quãng đường rất xa, ngày lễ

```json
{ "distance": 42, "estimated_time": 95, "time_of_day": 9, "day_type": 2, ... }
```
**Kỳ vọng**: `base_multiplier` rơi vào tập `very_high` (≈ 2.2 – 2.4).

#### Kịch bản 4 — Bão + AQI nguy hại + ít tài xế

```json
{ "weather": 3.8, "air_quality": 380, "demand_level": 9, "driver_availability": 3 }
```
**Kỳ vọng**: `environment_factor ≈ 1.45` (severe), `surge_factor ≈ 1.9` (very_high).

### 4.3. Đánh giá kết quả

#### 4.3.1. Tính đúng đắn

- Đầu ra **liên tục, đơn điệu** theo từng biến: ví dụ giữ nguyên các biến khác,
  tăng `traffic_level` từ 0 → 10 thì `environment_factor` tăng đều từ ≈1.0 lên
  ≈1.45.
- Khi đầu vào ở vùng "không có luật nào kích hoạt mạnh", `_safe_compute` rơi về
  giá trị mặc định an toàn (1.0), tránh exception phá vỡ trải nghiệm.

#### 4.3.2. Hiệu năng

- Mỗi lần `compute_all` thực thi 3 FIS độc lập, thời gian phản hồi trên máy
  thử ~ vài chục ms — đủ nhanh cho cập nhật real-time khi kéo slider.
- Frontend dùng **debounce** ~150 ms để giảm số request khi kéo liên tục.

#### 4.3.3. Tính giải thích (Explainability)

- Mỗi response bao gồm trường `memberships` cho biết **mức thuộc** của crisp
  value vào từng tập mờ → người dùng/giáo viên có thể kiểm chứng *vì sao* hệ
  cho ra giá trị đó.
- Tab **Biến mờ** vẽ đường cong tập mờ + vạch giá trị hiện tại; tab **Luật
  mờ** liệt kê 45 luật → toàn bộ quá trình suy diễn minh bạch.

#### 4.3.4. So sánh với tiếp cận luật cứng

| Tiêu chí | Luật cứng (`if/else`) | Hệ mờ Mamdani |
|---|---|---|
| Số luật cần viết tay | Bùng nổ tổ hợp | 45 luật ngôn ngữ |
| Hành vi tại biên | Nhảy bậc, không công bằng | Trơn, liên tục |
| Mức độ giải thích | Tốt | Tốt + có membership |
| Tinh chỉnh ngữ nghĩa | Khó (sửa số) | Dễ (chỉnh tập mờ) |

### 4.4. Hạn chế của hệ thống hiện tại

1. **Không kết nối API thực**: dữ liệu thời tiết, AQI, traffic được sinh giả
   lập trong `api_auto_conditions`.
2. **Đường đi**: dùng Haversine × 1.32 thay vì gọi dịch vụ định tuyến (OSRM,
   Google Directions) → khoảng cách đường thật không chính xác trong khu vực
   nhiều ngõ nhỏ.
3. **Tập mờ định nghĩa thủ công**: chưa được học từ dữ liệu thực, có thể chưa
   tối ưu.
4. **Lưu trữ JSON file**: phù hợp prototype, không scale được cho nhiều người
   dùng đồng thời.
5. **Chưa có xác thực người dùng** — bất kỳ ai cũng có thể tạo / xóa booking.

### 4.5. Hướng phát triển

- **Tích hợp API thực**: OpenWeather (thời tiết, nhiệt độ), AirVisual (AQI),
  TomTom / Google Maps (traffic + định tuyến).
- **Tự động học tập mờ** từ dữ liệu lịch sử bằng **ANFIS** (Adaptive
  Neuro-Fuzzy Inference System) hoặc thuật toán di truyền (GA) để tinh chỉnh
  hàm thuộc.
- **So sánh với mô hình ML** (XGBoost, LightGBM) để đối chiếu sai số dự đoán
  giá thực tế.
- **Mở rộng số loại xe** (taxi, xe điện, xe ghép) và thêm yếu tố *điểm tài xế*,
  *thanh toán*.
- **Chuyển sang database** (SQLite/PostgreSQL), thêm xác thực JWT, tách thành
  microservice.
- **Triển khai cloud** (Render, Fly.io, Railway) + CI/CD GitHub Actions.

### 4.6. Kết luận

Đề tài đã hiện thực hóa thành công một **hệ tính cước xe công nghệ dựa trên
Logic Mờ Mamdani phân cấp 3 tầng**, đầy đủ từ mô hình toán → backend Flask →
giao diện web trực quan. Hệ thống cho phép suy diễn 10 biến đầu vào với chỉ 45
luật ngôn ngữ, đầu ra trơn — minh bạch — dễ giải thích, đồng thời cung cấp các
chức năng phụ trợ (đặt xe, lịch sử, thống kê, bản đồ, biểu đồ membership) đủ để
demo thực tế. Đây là minh chứng rõ ràng cho sức mạnh của Fuzzy Logic trong các
bài toán ra quyết định mang tính ngôn ngữ và nhiều biến nhiễu của đời sống.

---

*Hết báo cáo.*
