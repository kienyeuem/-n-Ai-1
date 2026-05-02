# FuzzyRide — Tính cước xe công nghệ bằng Logic Mờ

Web app Flask mô phỏng & tính giá cước xe công nghệ (Grab/Be/Gojek style) sử dụng **Hierarchical Fuzzy Logic (Mamdani 3-FIS)** với 10 biến đầu vào, kèm đầy đủ flow đặt xe demo (12 màn theo mockup), đăng nhập, lịch sử và admin dashboard. Dữ liệu địa điểm: **TP. Hồ Chí Minh** (~30 điểm).

## Biến mờ (rút gọn)
| Nhóm | Biến | Miền | Tập mờ |
|---|---|---|---|
| Quãng đường | `distance` (km) | 0 – 50 | short / medium / long / very_long |
| Quãng đường | `estimated_time` (phút) | 0 – 120 | fast / normal / slow / very_slow |
| Quãng đường | `time_of_day` | 0 – 24 | early_morning / morning_rush / noon / afternoon / evening_rush / night / late_night |
| Quãng đường | `day_type` | 0 – 2 | weekday / weekend / holiday |
| Môi trường | `traffic_level` | 0 – 10 | smooth / moderate / heavy / jammed |
| Môi trường | `weather` | 0 – 4 | sunny / cloudy / light_rain / heavy_rain / storm |
| Môi trường | `temperature` (°C) | 15 – 40 | cool / comfortable / hot / very_hot |
| Môi trường | `air_quality` (AQI) | 0 – 500 | good / moderate / unhealthy / hazardous |
| Cung-cầu | `demand_level` | 0 – 10 | low / medium / high / very_high |
| Cung-cầu | `driver_availability` | 0 – 50 | scarce / few / normal / abundant |

**Đầu ra** (3 FIS): `base_multiplier × environment_factor × surge_factor` → `total_multiplier`.
**Cước cuối** = (mở cửa + đơn giá × km) × `total_multiplier`.

## Cài đặt
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
Mở http://localhost:5000 — lần đầu sẽ tự chuyển tới `/setup` để tạo tài khoản admin.

## Tài khoản & route
| Route | Vai trò |
|---|---|
| `/` | Landing page + calculator + 4 tab fuzzy (cho báo cáo học thuật) |
| `/splash` `/login` `/register` | Onboarding & xác thực |
| `/app` | SPA flow đặt xe: Home → Chọn điểm → Ước tính → Tìm tài xế → Đã nhận → Đang đi → Hoàn tất |
| `/history` `/profile` | Lịch sử chuyến & hồ sơ |
| `/admin` | Dashboard 4 tab: Stats, Users, Bookings, Fuzzy params (chỉnh live) |
| `/mockup` | Bảng Figma 12 màn |

## Cấu trúc thư mục
```
deadlineKiennn/
├── app.py                  # Flask + 3 FIS Mamdani + auth + lifecycle trip
├── requirements.txt
├── data/
│   ├── locations.json      # 30 địa điểm TP.HCM
│   ├── bookings.json       # Sinh khi chạy
│   ├── users.json          # Sinh khi chạy (auth)
│   ├── drivers.json        # 15 tài xế mock
│   └── fuzzy_params.json   # Cho admin chỉnh live
├── templates/              # splash, login, register, setup, app, history, profile, admin, index, mockup
└── static/
    ├── css/                # style.css + mobile.css + admin.css
    └── js/                 # app.js + booking-flow.js + admin.js
```

## Tab giao diện chính (`/`)
1. **Chuyến đi** – chọn xe, nhập điểm A→B, autocomplete địa điểm TP.HCM
2. **Môi trường** – sliders cho traffic/weather/temperature/AQI/demand/drivers + nút "Áp dụng tự động"
3. **Biến mờ** – biểu đồ membership functions + vạch crisp value real-time
4. **Luật mờ** – 45 luật IF–THEN của 3 FIS
