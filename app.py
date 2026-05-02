"""
FuzzyRide — Hierarchical Fuzzy System (3 FIS)
=============================================

10 biến đầu vào (9 fuzzy + 1 crisp) như thiết kế:
  Quãng đường & Thời gian:
    - distance        (km, 0-50)        : short, medium, long, very_long
    - estimated_time  (phút, 0-120)     : fast, normal, slow, very_slow
    - time_of_day     (giờ, 0-23)       : early_morning, morning_rush, noon,
                                          afternoon, evening_rush, night, late_night
    - day_type        (0/1/2 - crisp)   : weekday, weekend, holiday
  Giao thông & Môi trường:
    - traffic_level   (0-10)            : smooth, moderate, heavy, jammed
    - weather         (0-4)             : sunny, cloudy, light_rain, heavy_rain, storm
    - temperature     (°C, 15-40)       : cool, comfortable, hot, very_hot
    - air_quality     (AQI, 0-500)      : good, moderate, unhealthy, hazardous
  Cung cầu:
    - demand_level    (0-10)            : low, medium, high, very_high
    - driver_avail.   (0-50 xe)         : scarce, few, normal, abundant
  Loại xe (crisp):
    - vehicle_type                       : bike, 4s, 7s

Kiến trúc Hierarchical 3 FIS:
  FIS-1 (Base Multiplier):
        distance + time_of_day + day_type + estimated_time
        → base_multiplier [0.8 – 2.5]                (~20 rules)
  FIS-2 (Environment Factor):
        traffic_level + weather + temperature + air_quality
        → environment_factor [1.0 – 1.5]             (~15 rules)
  FIS-3 (Surge Factor):
        demand_level + driver_availability
        → surge_factor [1.0 – 2.0]                   (~10 rules)

Total surge = base_multiplier × environment_factor × surge_factor
Cước cuối   = (mở cửa + đơn giá × km) × Total surge
"""

from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for, abort, send_from_directory)
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import json
import math
import os
import uuid
import random
import unicodedata
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from threading import Lock

app = Flask(__name__)
app.secret_key = os.environ.get('FUZZYRIDE_SECRET') or 'fuzzyride-dev-secret-change-in-prod-' + secrets.token_hex(16)
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 7  # 7 ngày

# OAuth credentials — đặt qua biến môi trường để bảo mật
GOOGLE_CLIENT_ID    = os.environ.get('GOOGLE_CLIENT_ID', '')
FACEBOOK_APP_ID     = os.environ.get('FACEBOOK_APP_ID', '')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET', '')

# Payment gateway credentials
VNPAY_TMN_CODE   = os.environ.get('VNPAY_TMN_CODE', '')
VNPAY_HASH_SECRET = os.environ.get('VNPAY_HASH_SECRET', '')
VNPAY_RETURN_URL = os.environ.get('VNPAY_RETURN_URL', 'http://localhost:5000/api/payment/vnpay/return')
VNPAY_SANDBOX    = os.environ.get('VNPAY_SANDBOX', '1') == '1'

MOMO_PARTNER_CODE = os.environ.get('MOMO_PARTNER_CODE', '')
MOMO_ACCESS_KEY   = os.environ.get('MOMO_ACCESS_KEY', '')
MOMO_SECRET_KEY   = os.environ.get('MOMO_SECRET_KEY', '')
MOMO_REDIRECT_URL = os.environ.get('MOMO_REDIRECT_URL', 'http://localhost:5000/api/payment/momo/return')
MOMO_IPN_URL      = os.environ.get('MOMO_IPN_URL',      'http://localhost:5000/api/payment/momo/ipn')
MOMO_SANDBOX      = os.environ.get('MOMO_SANDBOX', '1') == '1'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOCATIONS_FILE      = os.path.join(DATA_DIR, 'locations.json')
BOOKINGS_FILE       = os.path.join(DATA_DIR, 'bookings.json')
USERS_FILE          = os.path.join(DATA_DIR, 'users.json')
DRIVERS_FILE        = os.path.join(DATA_DIR, 'drivers.json')
FUZZY_PARAMS_FILE   = os.path.join(DATA_DIR, 'fuzzy_params.json')
AVATAR_DIR          = os.path.join(BASE_DIR, 'static', 'avatars')
BRANDING_DIR        = os.path.join(BASE_DIR, 'static', 'branding')
BRANDING_FILE       = os.path.join(DATA_DIR, 'branding.json')
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(BRANDING_DIR, exist_ok=True)
ALLOWED_AVATAR_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
MAX_AVATAR_BYTES   = 5 * 1024 * 1024   # 5 MB
MAX_BANNER_BYTES   = 8 * 1024 * 1024   # 8 MB
_bookings_lock = Lock()
_users_lock    = Lock()
_params_lock   = Lock()


# ============================================================================
# 1. BIẾN MỜ — định nghĩa universe + tập mờ
# ============================================================================

# ---------- FIS-1 inputs ----------
distance       = ctrl.Antecedent(np.arange(0, 50.1, 0.1), 'distance')
estimated_time = ctrl.Antecedent(np.arange(0, 120.1, 0.5), 'estimated_time')
time_of_day    = ctrl.Antecedent(np.arange(0, 24.01, 0.1), 'time_of_day')
day_type       = ctrl.Antecedent(np.arange(0, 2.01, 0.01), 'day_type')

distance['short']     = fuzz.trimf(distance.universe, [0, 0, 6])
distance['medium']    = fuzz.trimf(distance.universe, [4, 12, 22])
distance['long']      = fuzz.trimf(distance.universe, [18, 28, 40])
distance['very_long'] = fuzz.trapmf(distance.universe, [35, 45, 50, 50])

estimated_time['fast']      = fuzz.trimf(estimated_time.universe, [0, 0, 15])
estimated_time['normal']    = fuzz.trimf(estimated_time.universe, [10, 30, 50])
estimated_time['slow']      = fuzz.trimf(estimated_time.universe, [40, 65, 90])
estimated_time['very_slow'] = fuzz.trapmf(estimated_time.universe, [80, 100, 120, 120])

time_of_day['early_morning'] = fuzz.trimf(time_of_day.universe, [4, 5.5, 7])
time_of_day['morning_rush']  = fuzz.trimf(time_of_day.universe, [6.5, 8, 10])
time_of_day['noon']          = fuzz.trimf(time_of_day.universe, [10, 12, 14])
time_of_day['afternoon']     = fuzz.trimf(time_of_day.universe, [13, 15.5, 17])
time_of_day['evening_rush']  = fuzz.trimf(time_of_day.universe, [16.5, 18, 20])
time_of_day['night']         = fuzz.trimf(time_of_day.universe, [19, 21, 23])
time_of_day['late_night']    = fuzz.trapmf(time_of_day.universe, [22.5, 23.5, 24, 24])

day_type['weekday'] = fuzz.trimf(day_type.universe, [0, 0, 0.6])
day_type['weekend'] = fuzz.trimf(day_type.universe, [0.4, 1, 1.6])
day_type['holiday'] = fuzz.trimf(day_type.universe, [1.4, 2, 2])

# ---------- FIS-2 inputs ----------
traffic_level = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'traffic_level')
weather       = ctrl.Antecedent(np.arange(0, 4.01, 0.05), 'weather')
temperature   = ctrl.Antecedent(np.arange(15, 40.1, 0.1), 'temperature')
air_quality   = ctrl.Antecedent(np.arange(0, 500.1, 1), 'air_quality')

traffic_level['smooth']   = fuzz.trimf(traffic_level.universe, [0, 0, 3])
traffic_level['moderate'] = fuzz.trimf(traffic_level.universe, [2, 4.5, 7])
traffic_level['heavy']    = fuzz.trimf(traffic_level.universe, [6, 7.5, 9])
traffic_level['jammed']   = fuzz.trapmf(traffic_level.universe, [8, 9, 10, 10])

weather['sunny']      = fuzz.trimf(weather.universe, [0, 0, 1])
weather['cloudy']     = fuzz.trimf(weather.universe, [0.5, 1.2, 2])
weather['light_rain'] = fuzz.trimf(weather.universe, [1.5, 2.2, 3])
weather['heavy_rain'] = fuzz.trimf(weather.universe, [2.5, 3.2, 4])
weather['storm']      = fuzz.trapmf(weather.universe, [3.5, 3.8, 4, 4])

temperature['cool']        = fuzz.trimf(temperature.universe, [15, 15, 21])
temperature['comfortable'] = fuzz.trimf(temperature.universe, [19, 25, 30])
temperature['hot']         = fuzz.trimf(temperature.universe, [28, 33, 37])
temperature['very_hot']    = fuzz.trapmf(temperature.universe, [35, 38, 40, 40])

air_quality['good']      = fuzz.trimf(air_quality.universe, [0, 0, 80])
air_quality['moderate']  = fuzz.trimf(air_quality.universe, [60, 120, 180])
air_quality['unhealthy'] = fuzz.trimf(air_quality.universe, [150, 220, 320])
air_quality['hazardous'] = fuzz.trapmf(air_quality.universe, [280, 380, 500, 500])

# ---------- FIS-3 inputs ----------
demand_level        = ctrl.Antecedent(np.arange(0, 10.1, 0.1), 'demand_level')
driver_availability = ctrl.Antecedent(np.arange(0, 50.1, 0.5), 'driver_availability')

demand_level['low']       = fuzz.trimf(demand_level.universe, [0, 0, 3])
demand_level['medium']    = fuzz.trimf(demand_level.universe, [2, 5, 7])
demand_level['high']      = fuzz.trimf(demand_level.universe, [6, 7.5, 9])
demand_level['very_high'] = fuzz.trapmf(demand_level.universe, [8, 9, 10, 10])

driver_availability['scarce']   = fuzz.trimf(driver_availability.universe, [0, 0, 5])
driver_availability['few']      = fuzz.trimf(driver_availability.universe, [3, 10, 18])
driver_availability['normal']   = fuzz.trimf(driver_availability.universe, [15, 25, 35])
driver_availability['abundant'] = fuzz.trapmf(driver_availability.universe, [30, 42, 50, 50])

# ---------- Outputs ----------
base_multiplier    = ctrl.Consequent(np.arange(0.8, 2.51, 0.01), 'base_multiplier')
environment_factor = ctrl.Consequent(np.arange(1.0, 1.51, 0.005), 'environment_factor')
surge_factor       = ctrl.Consequent(np.arange(1.0, 2.01, 0.01), 'surge_factor')

base_multiplier['low']       = fuzz.trimf(base_multiplier.universe, [0.8, 0.8, 1.2])
base_multiplier['normal']    = fuzz.trimf(base_multiplier.universe, [1.0, 1.3, 1.6])
base_multiplier['high']      = fuzz.trimf(base_multiplier.universe, [1.4, 1.8, 2.2])
base_multiplier['very_high'] = fuzz.trapmf(base_multiplier.universe, [2.0, 2.3, 2.5, 2.5])

environment_factor['none']   = fuzz.trimf(environment_factor.universe, [1.0, 1.0, 1.15])
environment_factor['mild']   = fuzz.trimf(environment_factor.universe, [1.05, 1.20, 1.30])
environment_factor['strong'] = fuzz.trimf(environment_factor.universe, [1.2, 1.35, 1.45])
environment_factor['severe'] = fuzz.trapmf(environment_factor.universe, [1.35, 1.45, 1.5, 1.5])

surge_factor['none']      = fuzz.trimf(surge_factor.universe, [1.0, 1.0, 1.2])
surge_factor['mild']      = fuzz.trimf(surge_factor.universe, [1.1, 1.3, 1.5])
surge_factor['high']      = fuzz.trimf(surge_factor.universe, [1.4, 1.6, 1.8])
surge_factor['very_high'] = fuzz.trapmf(surge_factor.universe, [1.7, 1.9, 2.0, 2.0])


# ============================================================================
# 2. HỆ LUẬT — 45 luật chia 3 FIS (20 + 15 + 10)
# ============================================================================

# ---------------- FIS-1: Base Multiplier (20 rules) ----------------
fis1_rules = [
    ctrl.Rule(distance['short']  & estimated_time['fast'],   base_multiplier['low']),
    ctrl.Rule(distance['short']  & estimated_time['normal'], base_multiplier['low']),
    ctrl.Rule(distance['short']  & estimated_time['slow'],   base_multiplier['normal']),
    ctrl.Rule(distance['medium'] & estimated_time['fast'],      base_multiplier['normal']),
    ctrl.Rule(distance['medium'] & estimated_time['normal'],    base_multiplier['normal']),
    ctrl.Rule(distance['medium'] & estimated_time['slow'],      base_multiplier['high']),
    ctrl.Rule(distance['medium'] & estimated_time['very_slow'], base_multiplier['high']),
    ctrl.Rule(distance['long']   & estimated_time['fast'],      base_multiplier['normal']),
    ctrl.Rule(distance['long']   & estimated_time['slow'],      base_multiplier['high']),
    ctrl.Rule(distance['long']   & estimated_time['very_slow'], base_multiplier['very_high']),
    ctrl.Rule(distance['very_long'],                              base_multiplier['very_high']),
    ctrl.Rule(time_of_day['morning_rush'] & day_type['weekday'], base_multiplier['high']),
    ctrl.Rule(time_of_day['evening_rush'] & day_type['weekday'], base_multiplier['high']),
    ctrl.Rule(time_of_day['morning_rush'] & day_type['weekend'], base_multiplier['normal']),
    ctrl.Rule(time_of_day['evening_rush'] & day_type['weekend'], base_multiplier['normal']),
    ctrl.Rule(time_of_day['late_night'],    base_multiplier['high']),
    ctrl.Rule(time_of_day['early_morning'], base_multiplier['normal']),
    ctrl.Rule(day_type['holiday'], base_multiplier['very_high']),
    ctrl.Rule(time_of_day['noon']      & day_type['weekday'], base_multiplier['normal']),
    ctrl.Rule(time_of_day['night']     & day_type['weekend'], base_multiplier['normal']),
]

# ---------------- FIS-2: Environment Factor (15 rules) ----------------
fis2_rules = [
    ctrl.Rule(traffic_level['smooth']   & weather['sunny']      & temperature['comfortable'], environment_factor['none']),
    ctrl.Rule(traffic_level['smooth']   & weather['cloudy']     & air_quality['good'],         environment_factor['none']),
    ctrl.Rule(traffic_level['moderate'] & weather['sunny'],      environment_factor['mild']),
    ctrl.Rule(traffic_level['heavy']    & weather['sunny'],      environment_factor['mild']),
    ctrl.Rule(traffic_level['heavy']    & weather['light_rain'], environment_factor['strong']),
    ctrl.Rule(traffic_level['jammed']   & weather['sunny'],      environment_factor['strong']),
    ctrl.Rule(traffic_level['jammed']   & weather['heavy_rain'], environment_factor['severe']),
    ctrl.Rule(traffic_level['jammed']   & weather['storm'],      environment_factor['severe']),
    ctrl.Rule(weather['heavy_rain'], environment_factor['strong']),
    ctrl.Rule(weather['storm'],      environment_factor['severe']),
    ctrl.Rule(weather['light_rain']  & traffic_level['moderate'], environment_factor['mild']),
    ctrl.Rule(temperature['very_hot'] & air_quality['unhealthy'], environment_factor['strong']),
    ctrl.Rule(temperature['hot']      & air_quality['moderate'],   environment_factor['mild']),
    ctrl.Rule(air_quality['hazardous'],                            environment_factor['severe']),
    ctrl.Rule(temperature['cool']     & weather['sunny'],          environment_factor['none']),
]

# ---------------- FIS-3: Surge Factor (10 rules) ----------------
fis3_rules = [
    ctrl.Rule(demand_level['low']       & driver_availability['abundant'], surge_factor['none']),
    ctrl.Rule(demand_level['low']       & driver_availability['normal'],   surge_factor['none']),
    ctrl.Rule(demand_level['medium']    & driver_availability['normal'],   surge_factor['mild']),
    ctrl.Rule(demand_level['medium']    & driver_availability['few'],      surge_factor['mild']),
    ctrl.Rule(demand_level['medium']    & driver_availability['scarce'],   surge_factor['high']),
    ctrl.Rule(demand_level['high']      & driver_availability['normal'],   surge_factor['mild']),
    ctrl.Rule(demand_level['high']      & driver_availability['few'],      surge_factor['high']),
    ctrl.Rule(demand_level['high']      & driver_availability['scarce'],   surge_factor['very_high']),
    ctrl.Rule(demand_level['very_high'] & driver_availability['few'],      surge_factor['very_high']),
    ctrl.Rule(demand_level['very_high'] & driver_availability['scarce'],   surge_factor['very_high']),
]

fis1_ctrl = ctrl.ControlSystem(fis1_rules)
fis2_ctrl = ctrl.ControlSystem(fis2_rules)
fis3_ctrl = ctrl.ControlSystem(fis3_rules)


def _safe_compute(ctrl_sys, inputs, output_name, fallback):
    sim = ctrl.ControlSystemSimulation(ctrl_sys)
    for k, v in inputs.items():
        sim.input[k] = float(v)
    try:
        sim.compute()
        return float(sim.output[output_name])
    except Exception:
        return fallback


def compute_all(inputs):
    bm = _safe_compute(fis1_ctrl, {
        'distance':       np.clip(inputs['distance'], 0, 50),
        'estimated_time': np.clip(inputs['estimated_time'], 0, 120),
        'time_of_day':    np.clip(inputs['time_of_day'], 0, 24),
        'day_type':       np.clip(inputs['day_type'], 0, 2),
    }, 'base_multiplier', 1.0)

    ef = _safe_compute(fis2_ctrl, {
        'traffic_level': np.clip(inputs['traffic_level'], 0, 10),
        'weather':       np.clip(inputs['weather'], 0, 4),
        'temperature':   np.clip(inputs['temperature'], 15, 40),
        'air_quality':   np.clip(inputs['air_quality'], 0, 500),
    }, 'environment_factor', 1.0)

    sf = _safe_compute(fis3_ctrl, {
        'demand_level':        np.clip(inputs['demand_level'], 0, 10),
        'driver_availability': np.clip(inputs['driver_availability'], 0, 50),
    }, 'surge_factor', 1.0)

    return {
        'base_multiplier':    round(bm, 3),
        'environment_factor': round(ef, 3),
        'surge_factor':       round(sf, 3),
        'total_multiplier':   round(bm * ef * sf, 3),
    }


# ============================================================================
# 3. BẢNG GIÁ + ĐỊA ĐIỂM + HÀM TRỢ GIÚP
# ============================================================================
DEFAULT_VEHICLE_PRICING = {
    'bike': {'name': 'Xe máy',     'open': 12000, 'per_km': 4500,  'icon': '🛵'},
    '4s':   {'name': 'Ô tô 4 chỗ', 'open': 25000, 'per_km': 11000, 'icon': '🚗'},
    '7s':   {'name': 'Ô tô 7 chỗ', 'open': 32000, 'per_km': 14000, 'icon': '🚙'},
}


def load_fuzzy_params():
    """Đọc fuzzy_params.json. Tự khởi tạo nếu chưa có."""
    try:
        with open(FUZZY_PARAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        defaults = {
            'version': 1,
            'updated_at': None,
            'vehicle_pricing': DEFAULT_VEHICLE_PRICING,
            'output_caps': {
                'base_multiplier':    {'min': 0.8, 'max': 2.5},
                'environment_factor': {'min': 1.0, 'max': 1.5},
                'surge_factor':       {'min': 1.0, 'max': 2.0},
            },
            'manual_factor': 1.0,
        }
        save_fuzzy_params(defaults)
        return defaults


def save_fuzzy_params(params):
    os.makedirs(DATA_DIR, exist_ok=True)
    params['updated_at'] = datetime.now().isoformat(timespec='seconds')
    with open(FUZZY_PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


def get_vehicle_pricing():
    """VEHICLE_PRICING động — đọc từ fuzzy_params mỗi lần (không cache, để admin chỉnh thấy ngay)."""
    return load_fuzzy_params().get('vehicle_pricing', DEFAULT_VEHICLE_PRICING)


def get_manual_factor():
    return float(load_fuzzy_params().get('manual_factor', 1.0))


# Backward compat: nhiều code cũ dùng VEHICLE_PRICING như dict thông thường
VEHICLE_PRICING = get_vehicle_pricing()


def load_locations():
    try:
        with open(LOCATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

LOCATIONS = load_locations()


def _strip_accents(s):
    if not s:
        return ''
    nfkd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


for _loc in LOCATIONS:
    _loc['_norm'] = _strip_accents(_loc['name'])


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def find_location(name):
    if not name:
        return None
    n_raw = name.strip().lower()
    n = _strip_accents(name)
    for loc in LOCATIONS:
        if loc['name'].lower() == n_raw or loc['_norm'] == n:
            return loc
    for loc in LOCATIONS:
        if n in loc['_norm'] or loc['_norm'] in n:
            return loc
    return None


def memberships(value, antecedent):
    out = {}
    for label in antecedent.terms:
        mf = antecedent[label].mf
        out[label] = float(fuzz.interp_membership(antecedent.universe, mf, value))
    return out


ALL_VARS = {
    'distance': distance, 'estimated_time': estimated_time,
    'time_of_day': time_of_day, 'day_type': day_type,
    'traffic_level': traffic_level, 'weather': weather,
    'temperature': temperature, 'air_quality': air_quality,
    'demand_level': demand_level, 'driver_availability': driver_availability,
}
ALL_OUTPUTS = {
    'base_multiplier': base_multiplier,
    'environment_factor': environment_factor,
    'surge_factor': surge_factor,
}


# ============================================================================
# 3b. AUTH + USERS + DRIVERS + TRIP LIFECYCLE
# ============================================================================

def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                            salt.encode('utf-8'), 120_000)
    return f"pbkdf2_sha256${salt}${h.hex()}"


def _verify_password(password, hashed):
    try:
        algo, salt, h = hashed.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                    salt.encode('utf-8'), 120_000).hex()
        return secrets.compare_digest(check, h)
    except Exception:
        return False


def _read_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _write_users(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def find_user(by, value):
    """by ∈ {'id','username','email','phone'}"""
    for u in _read_users():
        if str(u.get(by, '')).lower() == str(value).lower():
            return u
    return None


def admin_exists():
    return any(u.get('role') == 'admin' for u in _read_users())


def get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return find_user('id', uid)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        u = get_current_user()
        if not u:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Cần đăng nhập'}), 401
            return redirect(url_for('view_login', next=request.path))
        if u.get('locked'):
            session.clear()
            return jsonify({'error': 'Tài khoản đã bị khoá'}), 403
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        u = get_current_user()
        if not u or u.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Cần quyền admin'}), 403
            return redirect(url_for('view_login'))
        return view(*args, **kwargs)
    return wrapper


def avatar_url_for(uid):
    """Trả URL avatar nếu file tồn tại, kèm cache-buster mtime."""
    if not uid:
        return None
    path = os.path.join(AVATAR_DIR, f'{uid}.png')
    if os.path.exists(path):
        return url_for('static', filename=f'avatars/{uid}.png') + f'?v={int(os.path.getmtime(path))}'
    return None


def public_user(u):
    if not u:
        return None
    return {
        'id':       u.get('id'),
        'username': u.get('username'),
        'email':    u.get('email'),
        'phone':    u.get('phone'),
        'fullname': u.get('fullname', u.get('username')),
        'role':     u.get('role', 'user'),
        'locked':   bool(u.get('locked')),
        'created_at': u.get('created_at'),
        'avatar':   (u.get('fullname') or u.get('username') or 'U')[:1].upper(),
        'avatar_url': avatar_url_for(u.get('id')),
    }


# -------- Drivers --------
def load_drivers():
    try:
        with open(DRIVERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


DRIVERS = load_drivers()


def pick_driver_for(vehicle_type):
    pool = [d for d in DRIVERS if d.get('vehicle_type') == vehicle_type]
    if not pool:
        pool = DRIVERS
    if not pool:
        return None
    d = random.choice(pool).copy()
    d['eta_min']    = round(random.uniform(2, 7), 1)
    d['distance_m'] = random.randint(200, 1500)
    return d


# -------- Trip lifecycle --------
TRIP_STATUSES = ['searching', 'driver_assigned', 'in_trip', 'completed', 'cancelled']


def _update_booking(bid, mutator):
    """Helper: load → mutate(item) → save. Return updated booking or None."""
    with _bookings_lock:
        items = _read_bookings()
        for i, it in enumerate(items):
            if it.get('id') == bid:
                mutator(it)
                items[i] = it
                _write_bookings(items)
                return it
    return None


# ============================================================================
# 4. ROUTES
# ============================================================================
@app.before_request
def _bootstrap_redirect():
    """Trang đầu tiên chạy → ép vào /setup nếu chưa có admin (trừ static & setup endpoint)."""
    if request.path.startswith('/static/'):
        return None
    if request.endpoint in {'view_setup', 'api_setup', 'static'}:
        return None
    if request.path.startswith('/api/setup'):
        return None
    if not admin_exists() and request.path not in {'/setup'}:
        # Cho phép /api/auth/me trả 401 thường; chặn các page khác
        if request.path.startswith('/api/'):
            return None
        return redirect(url_for('view_setup'))
    return None


@app.route('/')
def index():
    return render_template('index.html',
                           vehicles=get_vehicle_pricing(),
                           current_user=public_user(get_current_user()))


@app.route('/mockup')
def mockup():
    return render_template('mockup.html')


# ----- Pages: auth & onboarding -----
@app.route('/splash')
def view_splash():
    return render_template('splash.html')


@app.route('/login')
def view_login():
    if get_current_user():
        return redirect(url_for('view_app'))
    return render_template('login.html', next_url=request.args.get('next', '/app'))


@app.route('/register')
def view_register():
    if get_current_user():
        return redirect(url_for('view_app'))
    return render_template('register.html')


@app.route('/setup')
def view_setup():
    if admin_exists():
        return redirect(url_for('view_login'))
    return render_template('setup.html')


@app.route('/logout')
def view_logout():
    session.clear()
    return redirect(url_for('view_login'))


# ----- Pages: app, history, profile, admin -----
@app.route('/app')
@login_required
def view_app():
    return render_template('app.html',
                           vehicles=get_vehicle_pricing(),
                           current_user=public_user(get_current_user()))


@app.route('/history')
@login_required
def view_history():
    return render_template('history.html',
                           current_user=public_user(get_current_user()))


@app.route('/profile')
@login_required
def view_profile():
    return render_template('profile.html',
                           current_user=public_user(get_current_user()))


@app.route('/admin')
@admin_required
def view_admin():
    return render_template('admin.html',
                           current_user=public_user(get_current_user()))


# ============================================================================
# 5. API: AUTH
# ============================================================================
@app.route('/api/auth/me')
def api_me():
    u = get_current_user()
    if not u:
        return jsonify({'authenticated': False}), 200
    return jsonify({'authenticated': True, 'user': public_user(u)})


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True) or {}
    username = (data.get('username') or '').strip().lower()
    email    = (data.get('email')    or '').strip().lower()
    phone    = (data.get('phone')    or '').strip()
    fullname = (data.get('fullname') or '').strip()
    password = data.get('password') or ''
    if not username or not password or not email:
        return jsonify({'error': 'Username, email và mật khẩu là bắt buộc'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Mật khẩu tối thiểu 6 ký tự'}), 400
    with _users_lock:
        items = _read_users()
        if any(u['username'].lower() == username for u in items):
            return jsonify({'error': 'Username đã tồn tại'}), 409
        if any(u.get('email','').lower() == email for u in items):
            return jsonify({'error': 'Email đã được dùng'}), 409
        new_user = {
            'id': uuid.uuid4().hex[:12],
            'username': username,
            'email': email,
            'phone': phone,
            'fullname': fullname or username,
            'password': _hash_password(password),
            'role': 'user',
            'locked': False,
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
        items.append(new_user)
        _write_users(items)
    session.permanent = True
    session['user_id'] = new_user['id']
    return jsonify({'ok': True, 'user': public_user(new_user)}), 201


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True) or {}
    ident    = (data.get('username') or data.get('identifier') or data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not ident or not password:
        return jsonify({'error': 'Thiếu thông tin'}), 400
    user = None
    for u in _read_users():
        if (u['username'].lower() == ident or
            u.get('email','').lower() == ident or
            u.get('phone','') == ident):
            user = u
            break
    if not user or not _verify_password(password, user['password']):
        return jsonify({'error': 'Sai tài khoản hoặc mật khẩu'}), 401
    if user.get('locked'):
        return jsonify({'error': 'Tài khoản đã bị khoá. Liên hệ admin.'}), 403
    session.permanent = True
    session['user_id'] = user['id']
    return jsonify({'ok': True, 'user': public_user(user)})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/avatar', methods=['POST'])
@login_required
def api_avatar_upload():
    """Upload ảnh đại diện. Resize 256x256 PNG nếu có Pillow, không thì lưu raw rồi đổi đuôi."""
    u = get_current_user()
    if 'avatar' not in request.files:
        return jsonify({'error': 'Không có file'}), 400
    f = request.files['avatar']
    if not f or not f.filename:
        return jsonify({'error': 'File rỗng'}), 400
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in ALLOWED_AVATAR_EXT:
        return jsonify({'error': 'Định dạng không hỗ trợ. Dùng PNG/JPG/WEBP/GIF'}), 400

    raw = f.read()
    if len(raw) > MAX_AVATAR_BYTES:
        return jsonify({'error': f'File quá lớn (>{MAX_AVATAR_BYTES // 1024 // 1024}MB)'}), 400

    out_path = os.path.join(AVATAR_DIR, f"{u['id']}.png")
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(raw))
        # Crop vuông trung tâm rồi resize 256x256
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img = img.crop((left, top, left + side, top + side)).resize((256, 256), Image.LANCZOS)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')
        img.save(out_path, 'PNG', optimize=True)
    except ImportError:
        # Pillow chưa cài → ghi nguyên file dưới dạng .png (không tối ưu nhưng OK cho demo)
        with open(out_path, 'wb') as wf:
            wf.write(raw)
    except Exception as e:
        return jsonify({'error': f'Không xử lý được ảnh: {e}'}), 500

    return jsonify({'ok': True, 'avatar_url': avatar_url_for(u['id'])})


@app.route('/api/auth/avatar', methods=['DELETE'])
@login_required
def api_avatar_delete():
    u = get_current_user()
    path = os.path.join(AVATAR_DIR, f"{u['id']}.png")
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})


# -------- OAuth (Google + Facebook) --------
def _find_or_create_oauth_user(provider, sub, email, name):
    """Tìm user theo provider+sub, theo email; tạo mới nếu chưa có."""
    sub_field = f'{provider}_sub'
    with _users_lock:
        items = _read_users()
        for u in items:
            if u.get(sub_field) == sub:
                return u
        if email:
            for u in items:
                if u.get('email', '').lower() == email.lower():
                    u[sub_field] = sub
                    _write_users(items)
                    return u
        base = (email.split('@')[0] if email else f'{provider}{sub[:6]}').lower()
        base = ''.join(c for c in base if c.isalnum() or c == '_')[:18] or f'{provider}user'
        username = base
        i = 1
        while any(x.get('username') == username for x in items):
            username = f'{base}{i}'; i += 1
        new_user = {
            'id': uuid.uuid4().hex[:12],
            'username': username,
            'email': email or '',
            'phone': '',
            'fullname': name or username,
            'password': _hash_password(secrets.token_urlsafe(24)),  # random — chỉ login qua OAuth
            'role': 'user',
            'locked': False,
            sub_field: sub,
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
        items.append(new_user)
        _write_users(items)
        return new_user


@app.route('/api/auth/oauth/config')
def api_oauth_config():
    """Frontend đọc Client ID để khởi tạo SDK."""
    return jsonify({
        'google_client_id':  GOOGLE_CLIENT_ID,
        'facebook_app_id':   FACEBOOK_APP_ID,
        'google_configured':   bool(GOOGLE_CLIENT_ID),
        'facebook_configured': bool(FACEBOOK_APP_ID),
    })


@app.route('/api/auth/oauth/google', methods=['POST'])
def api_oauth_google():
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'GOOGLE_CLIENT_ID chưa cấu hình. Đặt biến môi trường rồi restart server.'}), 503
    data = request.get_json(force=True) or {}
    credential = data.get('credential') or data.get('id_token')
    if not credential:
        return jsonify({'error': 'Thiếu credential'}), 400
    try:
        from google.oauth2 import id_token as gid
        from google.auth.transport import requests as gr
        info = gid.verify_oauth2_token(credential, gr.Request(), GOOGLE_CLIENT_ID)
        sub   = info['sub']
        email = info.get('email', '')
        name  = info.get('name', email.split('@')[0] if email else 'Google User')
    except ImportError:
        return jsonify({'error': 'Thiếu thư viện google-auth. Chạy: pip install google-auth'}), 500
    except Exception as e:
        return jsonify({'error': f'Token Google không hợp lệ: {e}'}), 401
    user = _find_or_create_oauth_user('google', sub, email, name)
    if user.get('locked'):
        return jsonify({'error': 'Tài khoản đã bị khoá'}), 403
    session.permanent = True
    session['user_id'] = user['id']
    return jsonify({'ok': True, 'user': public_user(user)})


@app.route('/api/auth/oauth/facebook', methods=['POST'])
def api_oauth_facebook():
    if not FACEBOOK_APP_ID:
        return jsonify({'error': 'FACEBOOK_APP_ID chưa cấu hình.'}), 503
    data = request.get_json(force=True) or {}
    access_token = data.get('access_token')
    if not access_token:
        return jsonify({'error': 'Thiếu access_token'}), 400
    try:
        import urllib.request, urllib.parse
        # Tuỳ chọn: verify token qua debug_token (cần app_secret)
        if FACEBOOK_APP_SECRET:
            app_token = f'{FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}'
            dq = urllib.parse.urlencode({'input_token': access_token, 'access_token': app_token})
            with urllib.request.urlopen(f'https://graph.facebook.com/debug_token?{dq}', timeout=10) as r:
                dbg = json.loads(r.read()).get('data', {})
            if not dbg.get('is_valid') or str(dbg.get('app_id')) != str(FACEBOOK_APP_ID):
                return jsonify({'error': 'Access token Facebook không hợp lệ hoặc không khớp App ID'}), 401
        # Lấy thông tin user
        params = urllib.parse.urlencode({'fields': 'id,name,email', 'access_token': access_token})
        with urllib.request.urlopen(f'https://graph.facebook.com/v18.0/me?{params}', timeout=10) as r:
            info = json.loads(r.read())
        sub   = info['id']
        email = info.get('email', '')
        name  = info.get('name', 'Facebook User')
    except Exception as e:
        return jsonify({'error': f'Token Facebook không hợp lệ: {e}'}), 401
    user = _find_or_create_oauth_user('facebook', sub, email, name)
    if user.get('locked'):
        return jsonify({'error': 'Tài khoản đã bị khoá'}), 403
    session.permanent = True
    session['user_id'] = user['id']
    return jsonify({'ok': True, 'user': public_user(user)})


# ============================================================================
# BRANDING (logo, banner, footer config)
# ============================================================================
DEFAULT_BRANDING = {
    'site_name':   'FuzzyRide',
    'tagline':     'Đặt xe thông minh, cước minh bạch.',
    'logo_url':    None,                # null → fallback chữ "F"
    
    'banners':     [],                  # [{id, url, link, alt}]
    'footer': {
        'copyright': '© 2026 FuzzyRide. Đồ án Hierarchical Fuzzy Logic.',
        'sections': [
            {'title': 'Dịch vụ khách hàng', 'links': [
                {'text': 'Trung tâm trợ giúp',  'url': '#'},
                {'text': 'Hướng dẫn đặt chuyến','url': '#'},
                {'text': 'Liên hệ',             'url': '#'},
                {'text': 'Chính sách bảo hành', 'url': '#'},
            ]},
            {'title': 'Về FuzzyRide', 'links': [
                {'text': 'Giới thiệu',         'url': '#'},
                {'text': 'Báo cáo Fuzzy Logic','url': '/'},
                {'text': 'Bảng mockup',        'url': '/mockup'},
                {'text': 'Điều khoản',         'url': '#'},
                {'text': 'Chính sách bảo mật', 'url': '#'},
            ]},
            {'title': 'Theo dõi', 'links': [
                {'text': 'Facebook',  'url': '#'},
                {'text': 'Instagram', 'url': '#'},
                {'text': 'LinkedIn',  'url': '#'},
            ]},
        ]
    }
}


def load_branding():
    try:
        with open(BRANDING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # merge defaults để khoá thiếu vẫn có giá trị
        for k, v in DEFAULT_BRANDING.items():
            data.setdefault(k, v)
        return data
    except Exception:
        save_branding(DEFAULT_BRANDING)
        return DEFAULT_BRANDING.copy()


def save_branding(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    data['updated_at'] = datetime.now().isoformat(timespec='seconds')
    with open(BRANDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _resolve_branding_for_template():
    """Trả về object để Jinja inject vào tất cả template."""
    b = load_branding()
    # Refresh logo_url với cache-buster theo mtime
    if b.get('logo_url'):
        path = os.path.join(BASE_DIR, b['logo_url'].lstrip('/').replace('/', os.sep))
        if os.path.exists(path):
            b['logo_url'] = b['logo_url'].split('?')[0] + f'?v={int(os.path.getmtime(path))}'
        else:
            b['logo_url'] = None
    return b


@app.context_processor
def inject_branding():
    return {'branding': _resolve_branding_for_template()}


@app.route('/api/branding')
def api_branding_get():
    return jsonify(_resolve_branding_for_template())


@app.route('/api/admin/branding/logo', methods=['POST'])
@admin_required
def api_admin_logo_upload():
    if 'logo' not in request.files:
        return jsonify({'error': 'Không có file'}), 400
    f = request.files['logo']
    if not f or not f.filename:
        return jsonify({'error': 'File rỗng'}), 400
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in ALLOWED_AVATAR_EXT:
        return jsonify({'error': 'Định dạng không hỗ trợ'}), 400
    raw = f.read()
    if len(raw) > MAX_AVATAR_BYTES:
        return jsonify({'error': 'File quá lớn'}), 400
    out_path = os.path.join(BRANDING_DIR, 'logo.png')
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(raw))
        # Logo: giữ tỉ lệ, max 256px chiều cao
        w, h = img.size
        if h > 256:
            w = int(w * 256 / h); h = 256
        img = img.resize((w, h), Image.LANCZOS)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')
        img.save(out_path, 'PNG', optimize=True)
    except ImportError:
        with open(out_path, 'wb') as wf:
            wf.write(raw)
    except Exception as e:
        return jsonify({'error': f'Không xử lý được ảnh: {e}'}), 500
    with _params_lock:
        b = load_branding()
        b['logo_url'] = '/static/branding/logo.png'
        save_branding(b)
    return jsonify({'ok': True, 'branding': _resolve_branding_for_template()})


@app.route('/api/admin/branding/logo', methods=['DELETE'])
@admin_required
def api_admin_logo_delete():
    p = os.path.join(BRANDING_DIR, 'logo.png')
    if os.path.exists(p):
        os.remove(p)
    with _params_lock:
        b = load_branding()
        b['logo_url'] = None
        save_branding(b)
    return jsonify({'ok': True, 'branding': _resolve_branding_for_template()})


@app.route('/api/admin/branding/banners', methods=['POST'])
@admin_required
def api_admin_banner_upload():
    if 'banner' not in request.files:
        return jsonify({'error': 'Không có file'}), 400
    f = request.files['banner']
    if not f or not f.filename:
        return jsonify({'error': 'File rỗng'}), 400
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in ALLOWED_AVATAR_EXT:
        return jsonify({'error': 'Định dạng không hỗ trợ'}), 400
    raw = f.read()
    if len(raw) > MAX_BANNER_BYTES:
        return jsonify({'error': 'File quá lớn (>8MB)'}), 400
    bid = uuid.uuid4().hex[:8]
    out_path = os.path.join(BRANDING_DIR, f'banner_{bid}.jpg')
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(raw))
        w, h = img.size
        # Crop về tỉ lệ 16:9
        target_ratio = 16 / 9
        cur_ratio = w / h
        if cur_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((1600, 900), Image.LANCZOS)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(out_path, 'JPEG', quality=88, optimize=True)
    except ImportError:
        with open(out_path, 'wb') as wf:
            wf.write(raw)
    except Exception as e:
        return jsonify({'error': f'Không xử lý được ảnh: {e}'}), 500
    with _params_lock:
        b = load_branding()
        b.setdefault('banners', []).append({
            'id':   bid,
            'url':  f'/static/branding/banner_{bid}.jpg',
            'link': request.form.get('link', ''),
            'alt':  request.form.get('alt',  '')[:120],
        })
        save_branding(b)
    return jsonify({'ok': True, 'branding': _resolve_branding_for_template()})


@app.route('/api/admin/branding/banners/<bid>', methods=['DELETE'])
@admin_required
def api_admin_banner_delete(bid):
    with _params_lock:
        b = load_branding()
        b['banners'] = [x for x in b.get('banners', []) if x.get('id') != bid]
        save_branding(b)
    p = os.path.join(BRANDING_DIR, f'banner_{bid}.jpg')
    if os.path.exists(p):
        os.remove(p)
    return jsonify({'ok': True})



# ============================================================================
# PAYMENT — VNPay + MoMo + Cash
# ============================================================================

def _verify_booking_owner(bid):
    """Helper: trả booking nếu user hiện tại là chủ, else None."""
    u = get_current_user()
    if not u:
        return None
    for b in _read_bookings():
        if b.get('id') == bid and b.get('user_id') == u['id']:
            return b
    return None


@app.route('/api/payment/methods')
def api_payment_methods():
    """Danh sách phương thức + trạng thái cấu hình (cho frontend hiển thị)."""
    return jsonify({
        'methods': [
            {'code': 'cash',   'name': 'Tiền mặt',   'configured': True,
             'icon': 'cash',   'desc': 'Trả trực tiếp cho tài xế khi đến nơi'},
            {'code': 'vnpay',  'name': 'VNPay',      'configured': bool(VNPAY_TMN_CODE and VNPAY_HASH_SECRET),
             'icon': 'vnpay',  'desc': 'ATM nội địa / Visa / Mastercard / QR'},
            {'code': 'momo',   'name': 'MoMo',       'configured': bool(MOMO_PARTNER_CODE and MOMO_ACCESS_KEY and MOMO_SECRET_KEY),
             'icon': 'momo',   'desc': 'Ví điện tử MoMo'},
            {'code': 'zalopay','name': 'ZaloPay',    'configured': False,
             'icon': 'zalopay','desc': 'Đang phát triển'},
        ]
    })


@app.route('/api/payment/cash', methods=['POST'])
@login_required
def api_payment_cash():
    """Cash: chỉ đánh dấu booking là 'pending_cash', tài xế thu khi đến nơi."""
    data = request.get_json(force=True) or {}
    bid = data.get('booking_id')
    booking = _verify_booking_owner(bid)
    if not booking:
        return jsonify({'error': 'Không tìm thấy chuyến'}), 404

    def _mut(it):
        it['payment'] = {
            'method': 'cash',
            'status': 'pending_cash',
            'amount': it.get('final_fare', 0),
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
    out = _update_booking(bid, _mut)
    return jsonify({'ok': True, 'booking': out, 'instruction': 'Trả tiền mặt khi đến nơi'})


@app.route('/api/payment/vnpay/create', methods=['POST'])
@login_required
def api_payment_vnpay_create():
    """Tạo URL thanh toán VNPay. Frontend redirect user tới URL này."""
    if not VNPAY_TMN_CODE or not VNPAY_HASH_SECRET:
        return jsonify({'error': 'VNPay chưa được cấu hình. Đặt VNPAY_TMN_CODE & VNPAY_HASH_SECRET.'}), 503
    data = request.get_json(force=True) or {}
    bid = data.get('booking_id')
    booking = _verify_booking_owner(bid)
    if not booking:
        return jsonify({'error': 'Không tìm thấy chuyến'}), 404
    amount_vnd = int(round(booking.get('final_fare', 0)))
    if amount_vnd <= 0:
        return jsonify({'error': 'Số tiền không hợp lệ'}), 400

    import hmac, hashlib, urllib.parse
    txn_ref = f"{bid}_{int(datetime.now().timestamp())}"
    base_url = ('https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
                if VNPAY_SANDBOX else 'https://pay.vnpay.vn/vpcpay.html')

    params = {
        'vnp_Version':  '2.1.0',
        'vnp_Command':  'pay',
        'vnp_TmnCode':  VNPAY_TMN_CODE,
        'vnp_Amount':   str(amount_vnd * 100),         # VNPay yêu cầu nhân 100
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef':   txn_ref,
        'vnp_OrderInfo': f'FuzzyRide booking {bid}',
        'vnp_OrderType': 'other',
        'vnp_Locale':    'vn',
        'vnp_ReturnUrl': VNPAY_RETURN_URL,
        'vnp_IpAddr':    request.remote_addr or '127.0.0.1',
        'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
    }
    sorted_params = sorted(params.items())
    query = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote_plus)
    secure_hash = hmac.new(VNPAY_HASH_SECRET.encode(), query.encode(), hashlib.sha512).hexdigest()
    pay_url = f"{base_url}?{query}&vnp_SecureHash={secure_hash}"

    def _mut(it):
        it['payment'] = {
            'method': 'vnpay', 'status': 'pending',
            'txn_ref': txn_ref, 'amount': amount_vnd,
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
    _update_booking(bid, _mut)
    return jsonify({'ok': True, 'pay_url': pay_url, 'txn_ref': txn_ref})


@app.route('/api/payment/vnpay/return')
def api_payment_vnpay_return():
    """VNPay redirect user về đây sau khi thanh toán."""
    if not VNPAY_HASH_SECRET:
        return 'VNPay chưa được cấu hình', 503
    import hmac, hashlib, urllib.parse
    args = dict(request.args)
    received_hash = args.pop('vnp_SecureHash', None)
    args.pop('vnp_SecureHashType', None)
    sorted_p = sorted(args.items())
    query = urllib.parse.urlencode(sorted_p, quote_via=urllib.parse.quote_plus)
    expected = hmac.new(VNPAY_HASH_SECRET.encode(), query.encode(), hashlib.sha512).hexdigest()
    if not received_hash or expected != received_hash:
        return 'Chữ ký VNPay không hợp lệ', 400
    txn_ref     = args.get('vnp_TxnRef', '')
    rsp_code    = args.get('vnp_ResponseCode', '')
    success     = (rsp_code == '00')
    bid = txn_ref.split('_')[0] if txn_ref else ''
    if bid:
        def _mut(it):
            it['payment'] = it.get('payment', {})
            it['payment']['status']      = 'paid' if success else 'failed'
            it['payment']['paid_at']     = datetime.now().isoformat(timespec='seconds')
            it['payment']['vnpay_code']  = rsp_code
            it['payment']['vnpay_amount']= args.get('vnp_Amount')
        _update_booking(bid, _mut)
    return redirect(f'/history?payment={"success" if success else "failed"}')


@app.route('/api/payment/momo/create', methods=['POST'])
@login_required
def api_payment_momo_create():
    """Tạo request thanh toán MoMo (one-time payment)."""
    if not (MOMO_PARTNER_CODE and MOMO_ACCESS_KEY and MOMO_SECRET_KEY):
        return jsonify({'error': 'MoMo chưa được cấu hình.'}), 503
    data = request.get_json(force=True) or {}
    bid = data.get('booking_id')
    booking = _verify_booking_owner(bid)
    if not booking:
        return jsonify({'error': 'Không tìm thấy chuyến'}), 404
    amount = int(round(booking.get('final_fare', 0)))
    if amount <= 0:
        return jsonify({'error': 'Số tiền không hợp lệ'}), 400

    import hmac, hashlib, urllib.request
    request_id = f"FZR{int(datetime.now().timestamp()*1000)}"
    order_id   = f"{bid}_{int(datetime.now().timestamp())}"
    order_info = f'FuzzyRide booking {bid}'
    extra_data = ''
    request_type = 'captureWallet'
    api_endpoint = ('https://test-payment.momo.vn/v2/gateway/api/create'
                    if MOMO_SANDBOX else 'https://payment.momo.vn/v2/gateway/api/create')

    raw_signature = (
        f'accessKey={MOMO_ACCESS_KEY}&amount={amount}&extraData={extra_data}'
        f'&ipnUrl={MOMO_IPN_URL}&orderId={order_id}&orderInfo={order_info}'
        f'&partnerCode={MOMO_PARTNER_CODE}&redirectUrl={MOMO_REDIRECT_URL}'
        f'&requestId={request_id}&requestType={request_type}'
    )
    signature = hmac.new(MOMO_SECRET_KEY.encode(), raw_signature.encode(), hashlib.sha256).hexdigest()
    payload = {
        'partnerCode': MOMO_PARTNER_CODE, 'partnerName': 'FuzzyRide',
        'storeId':     'FuzzyRideStore',  'requestId':  request_id,
        'amount':      amount,            'orderId':    order_id,
        'orderInfo':   order_info,        'redirectUrl': MOMO_REDIRECT_URL,
        'ipnUrl':      MOMO_IPN_URL,      'lang':       'vi',
        'requestType': request_type,      'autoCapture': True,
        'extraData':   extra_data,        'signature':  signature,
    }
    try:
        req = urllib.request.Request(
            api_endpoint, data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        return jsonify({'error': f'Gọi MoMo lỗi: {e}'}), 502
    if result.get('resultCode') != 0:
        return jsonify({'error': result.get('message', 'MoMo từ chối'), 'detail': result}), 400

    def _mut(it):
        it['payment'] = {
            'method': 'momo', 'status': 'pending',
            'order_id': order_id, 'amount': amount,
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
    _update_booking(bid, _mut)
    return jsonify({'ok': True, 'pay_url': result.get('payUrl'), 'qr_url': result.get('qrCodeUrl')})


@app.route('/api/payment/momo/ipn', methods=['POST'])
def api_payment_momo_ipn():
    """MoMo IPN webhook — verify signature & update booking."""
    if not MOMO_SECRET_KEY:
        return jsonify({'error': 'MoMo not configured'}), 503
    import hmac, hashlib
    data = request.get_json(force=True) or {}
    raw = (
        f"accessKey={MOMO_ACCESS_KEY}&amount={data.get('amount')}&extraData={data.get('extraData','')}"
        f"&message={data.get('message','')}&orderId={data.get('orderId','')}&orderInfo={data.get('orderInfo','')}"
        f"&orderType={data.get('orderType','')}&partnerCode={data.get('partnerCode','')}"
        f"&payType={data.get('payType','')}&requestId={data.get('requestId','')}&responseTime={data.get('responseTime','')}"
        f"&resultCode={data.get('resultCode')}&transId={data.get('transId','')}"
    )
    expected = hmac.new(MOMO_SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if data.get('signature') != expected:
        return jsonify({'error': 'invalid signature'}), 400
    order_id = data.get('orderId', '')
    bid = order_id.split('_')[0] if order_id else ''
    success = data.get('resultCode') == 0
    if bid:
        def _mut(it):
            it['payment'] = it.get('payment', {})
            it['payment']['status']    = 'paid' if success else 'failed'
            it['payment']['paid_at']   = datetime.now().isoformat(timespec='seconds')
            it['payment']['trans_id']  = data.get('transId')
            it['payment']['momo_msg']  = data.get('message')
        _update_booking(bid, _mut)
    return jsonify({'message': 'received'}), 204


@app.route('/api/payment/momo/return')
def api_payment_momo_return():
    """User redirected here after MoMo. IPN sẽ là nguồn xác nhận chính."""
    success = request.args.get('resultCode') == '0'
    return redirect(f'/history?payment={"success" if success else "failed"}')


@app.route('/api/admin/branding/info', methods=['PATCH'])
@admin_required
def api_admin_branding_info():
    """Cập nhật site_name, tagline, footer."""
    data = request.get_json(force=True) or {}
    with _params_lock:
        b = load_branding()
        if 'site_name' in data: b['site_name'] = (data['site_name'] or '').strip()[:80] or 'FuzzyRide'
        if 'tagline'   in data: b['tagline']   = (data['tagline']   or '').strip()[:200]
        if 'footer'    in data and isinstance(data['footer'], dict):
            b['footer'] = data['footer']
        save_branding(b)
    return jsonify({'ok': True, 'branding': _resolve_branding_for_template()})


# ============================================================================
# GEOCODING — proxy Nominatim cho free-text location
# ============================================================================
@app.route('/api/geocode')
def api_geocode():
    """Tìm địa điểm bất kỳ qua Nominatim. Trả structured kết quả."""
    q = (request.args.get('q') or '').strip()
    limit = min(10, int(request.args.get('limit', 8)))
    if len(q) < 2:
        return jsonify([])
    try:
        import urllib.request, urllib.parse
        params = urllib.parse.urlencode({
            'q': q, 'format': 'jsonv2', 'limit': limit,
            'addressdetails': 1, 'countrycodes': 'vn',
            'accept-language': 'vi',
        })
        req = urllib.request.Request(
            f'https://nominatim.openstreetmap.org/search?{params}',
            headers={'User-Agent': 'FuzzyRide/1.0 (academic project)'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            results = json.loads(r.read())
    except Exception as e:
        return jsonify({'error': f'Geocoding lỗi: {e}'}), 502
    out = []
    for it in results:
        out.append({
            'name': it.get('display_name', ''),
            'short': it.get('name', '') or it.get('display_name','').split(',')[0],
            'lat':  float(it['lat']),
            'lng':  float(it['lon']),
            'type': it.get('type', it.get('class','')),
        })
    return jsonify(out)


@app.route('/api/reverse-geocode')
def api_reverse_geocode():
    """Lat/lng → tên địa điểm gần nhất."""
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Tham số lat/lng không hợp lệ'}), 400
    try:
        import urllib.request, urllib.parse
        params = urllib.parse.urlencode({
            'lat': lat, 'lon': lng, 'format': 'jsonv2',
            'accept-language': 'vi', 'zoom': 17,
        })
        req = urllib.request.Request(
            f'https://nominatim.openstreetmap.org/reverse?{params}',
            headers={'User-Agent': 'FuzzyRide/1.0 (academic project)'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
    except Exception as e:
        return jsonify({'error': f'Reverse lỗi: {e}'}), 502
    return jsonify({
        'name': data.get('display_name', f'{lat}, {lng}'),
        'short': data.get('name', '') or data.get('display_name','').split(',')[0],
        'lat': lat, 'lng': lng,
    })


@app.route('/api/auth/profile', methods=['PATCH'])
@login_required
def api_profile_update():
    """Cập nhật fullname, phone, email."""
    data = request.get_json(force=True) or {}
    u = get_current_user()
    with _users_lock:
        items = _read_users()
        for it in items:
            if it.get('id') == u['id']:
                if 'fullname' in data: it['fullname'] = (data['fullname'] or '').strip()[:80] or it.get('username')
                if 'phone'    in data: it['phone']    = (data['phone']    or '').strip()[:30]
                if 'email'    in data:
                    new_email = (data['email'] or '').strip().lower()
                    if new_email and any(x.get('email','').lower() == new_email and x.get('id') != u['id'] for x in items):
                        return jsonify({'error': 'Email đã được dùng'}), 409
                    it['email'] = new_email
                _write_users(items)
                return jsonify({'ok': True, 'user': public_user(it)})
    return jsonify({'error': 'Không tìm thấy user'}), 404


@app.route('/api/setup', methods=['POST'])
def api_setup():
    """Tạo admin đầu tiên — chỉ dùng được khi chưa có admin nào."""
    if admin_exists():
        return jsonify({'error': 'Hệ thống đã được cấu hình'}), 400
    data = request.get_json(force=True) or {}
    username = (data.get('username') or '').strip().lower()
    email    = (data.get('email')    or '').strip().lower()
    fullname = (data.get('fullname') or '').strip() or 'Quản trị viên'
    password = data.get('password') or ''
    if not username or not password or not email:
        return jsonify({'error': 'Vui lòng nhập đủ thông tin'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Mật khẩu tối thiểu 6 ký tự'}), 400
    with _users_lock:
        items = _read_users()
        admin = {
            'id': uuid.uuid4().hex[:12],
            'username': username,
            'email': email,
            'phone': data.get('phone',''),
            'fullname': fullname,
            'password': _hash_password(password),
            'role': 'admin',
            'locked': False,
            'created_at': datetime.now().isoformat(timespec='seconds'),
        }
        # Seed thêm 1 user demo nếu danh sách trống
        if not items:
            demo = {
                'id': uuid.uuid4().hex[:12],
                'username': 'demo',
                'email': 'demo@fuzzyride.local',
                'phone': '0900-000-000',
                'fullname': 'Người dùng Demo',
                'password': _hash_password('demo123'),
                'role': 'user',
                'locked': False,
                'created_at': datetime.now().isoformat(timespec='seconds'),
            }
            items.append(demo)
        items.append(admin)
        _write_users(items)
    session.permanent = True
    session['user_id'] = admin['id']
    return jsonify({'ok': True, 'user': public_user(admin)}), 201


# ============================================================================
# 6. API: TRIP LIFECYCLE
# ============================================================================
@app.route('/api/drivers/find', methods=['POST'])
@login_required
def api_drivers_find():
    data = request.get_json(force=True) or {}
    vt = data.get('vehicle_type', 'bike')
    d = pick_driver_for(vt)
    if not d:
        return jsonify({'error': 'Không có tài xế phù hợp'}), 404
    return jsonify(d)


@app.route('/api/bookings/<bid>/assign', methods=['POST'])
@login_required
def api_bookings_assign(bid):
    """FE gọi sau 3-5s 'tìm kiếm' → backend gắn 1 driver random."""
    booking = next((b for b in _read_bookings() if b.get('id') == bid), None)
    if not booking:
        return jsonify({'error': 'Không tìm thấy chuyến'}), 404
    u = get_current_user()
    if booking.get('user_id') != u['id'] and u.get('role') != 'admin':
        return jsonify({'error': 'Không có quyền'}), 403
    driver = pick_driver_for(booking.get('vehicle', 'bike'))

    def _mut(it):
        it['status'] = 'driver_assigned'
        it['driver'] = driver
        it['assigned_at'] = datetime.now().isoformat(timespec='seconds')
    return jsonify(_update_booking(bid, _mut))


@app.route('/api/bookings/<bid>/start', methods=['POST'])
@login_required
def api_bookings_start(bid):
    def _mut(it):
        it['status'] = 'in_trip'
        it['started_at'] = datetime.now().isoformat(timespec='seconds')
    out = _update_booking(bid, _mut)
    return (jsonify(out), 200) if out else (jsonify({'error': 'Not found'}), 404)


@app.route('/api/bookings/<bid>/complete', methods=['POST'])
@login_required
def api_bookings_complete(bid):
    def _mut(it):
        it['status'] = 'completed'
        it['ended_at'] = datetime.now().isoformat(timespec='seconds')
    out = _update_booking(bid, _mut)
    return (jsonify(out), 200) if out else (jsonify({'error': 'Not found'}), 404)


@app.route('/api/bookings/<bid>/cancel', methods=['POST'])
@login_required
def api_bookings_cancel(bid):
    def _mut(it):
        it['status'] = 'cancelled'
        it['cancelled_at'] = datetime.now().isoformat(timespec='seconds')
    out = _update_booking(bid, _mut)
    return (jsonify(out), 200) if out else (jsonify({'error': 'Not found'}), 404)


@app.route('/api/bookings/<bid>/rate', methods=['POST'])
@login_required
def api_bookings_rate(bid):
    data = request.get_json(force=True) or {}
    stars = int(data.get('stars', 5))
    comment = (data.get('comment') or '').strip()[:500]

    def _mut(it):
        it['rating'] = max(1, min(5, stars))
        it['comment'] = comment
    out = _update_booking(bid, _mut)
    return (jsonify(out), 200) if out else (jsonify({'error': 'Not found'}), 404)


# ============================================================================
# 7. API: ADMIN
# ============================================================================
@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    bookings = _read_bookings()
    users = _read_users()
    by_v, by_status = {}, {}
    last_7 = {}
    revenue = 0
    for b in bookings:
        by_v[b.get('vehicle_name', '?')] = by_v.get(b.get('vehicle_name', '?'), 0) + 1
        by_status[b.get('status','confirmed')] = by_status.get(b.get('status','confirmed'), 0) + 1
        revenue += b.get('final_fare', 0) if b.get('status') != 'cancelled' else 0
        try:
            d = b.get('created_at', '')[:10]
            if d:
                last_7[d] = last_7.get(d, 0) + 1
        except Exception:
            pass
    days = sorted(last_7.keys())[-7:]
    return jsonify({
        'total_bookings': len(bookings),
        'total_users': len([u for u in users if u.get('role') != 'admin']),
        'total_revenue': revenue,
        'avg_surge': round(
            sum(b.get('total_multiplier', 1.0) for b in bookings) / max(1, len(bookings)),
            2),
        'by_vehicle': by_v,
        'by_status': by_status,
        'daily_chart': [{'date': d, 'count': last_7[d]} for d in days],
    })


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_admin_users():
    items = _read_users()
    q = (request.args.get('q') or '').lower().strip()
    if q:
        items = [u for u in items
                 if q in u.get('username','').lower()
                 or q in u.get('email','').lower()
                 or q in u.get('fullname','').lower()]
    return jsonify([public_user(u) for u in items])


@app.route('/api/admin/users/<uid>', methods=['DELETE'])
@admin_required
def api_admin_user_delete(uid):
    me = get_current_user()
    if me['id'] == uid:
        return jsonify({'error': 'Không thể tự xoá chính mình'}), 400
    with _users_lock:
        items = _read_users()
        items = [u for u in items if u.get('id') != uid]
        _write_users(items)
    return jsonify({'ok': True})


@app.route('/api/admin/users/<uid>/lock', methods=['POST'])
@admin_required
def api_admin_user_lock(uid):
    data = request.get_json(force=True) or {}
    locked = bool(data.get('locked', True))
    me = get_current_user()
    if me['id'] == uid:
        return jsonify({'error': 'Không thể tự khoá chính mình'}), 400
    with _users_lock:
        items = _read_users()
        for u in items:
            if u.get('id') == uid:
                u['locked'] = locked
        _write_users(items)
    return jsonify({'ok': True, 'locked': locked})


@app.route('/api/admin/bookings')
@admin_required
def api_admin_bookings():
    items = _read_bookings()
    status = request.args.get('status')
    vehicle = request.args.get('vehicle')
    if status:
        items = [b for b in items if b.get('status') == status]
    if vehicle:
        items = [b for b in items if b.get('vehicle') == vehicle]
    return jsonify(items[::-1])


@app.route('/api/admin/fuzzy-params', methods=['GET'])
@admin_required
def api_admin_params_get():
    return jsonify(load_fuzzy_params())


@app.route('/api/admin/fuzzy-params', methods=['PUT'])
@admin_required
def api_admin_params_put():
    data = request.get_json(force=True) or {}
    with _params_lock:
        params = load_fuzzy_params()
        # Cập nhật chọn lọc, không cho ghi đè structure tuỳ ý
        if 'vehicle_pricing' in data:
            for k, v in data['vehicle_pricing'].items():
                if k in params['vehicle_pricing'] and isinstance(v, dict):
                    if 'open' in v:
                        params['vehicle_pricing'][k]['open'] = float(v['open'])
                    if 'per_km' in v:
                        params['vehicle_pricing'][k]['per_km'] = float(v['per_km'])
        if 'manual_factor' in data:
            params['manual_factor'] = max(0.5, min(3.0, float(data['manual_factor'])))
        save_fuzzy_params(params)
    return jsonify(load_fuzzy_params())


@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    data = request.get_json(force=True) or {}
    try:
        inp = {k: float(data.get(k, 0)) for k in ALL_VARS.keys()}
    except (TypeError, ValueError):
        return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400
    pricing_table = get_vehicle_pricing()
    vehicle = data.get('vehicle', 'bike')
    if vehicle not in pricing_table:
        vehicle = 'bike'

    out = compute_all(inp)
    manual = get_manual_factor()
    out['manual_factor']    = round(manual, 3)
    out['total_multiplier'] = round(out['total_multiplier'] * manual, 3)

    pricing = pricing_table[vehicle]
    base_fare = pricing['open'] + pricing['per_km'] * inp['distance']
    final_fare = base_fare * out['total_multiplier']

    mems = {}
    for k, ant in ALL_VARS.items():
        mems[k] = memberships(np.clip(inp[k], ant.universe[0], ant.universe[-1]), ant)

    return jsonify({
        **out,
        'base_fare': round(base_fare),
        'final_fare': round(final_fare),
        'vehicle': pricing['name'],
        'vehicle_code': vehicle,
        'icon': pricing['icon'],
        'open_fee': pricing['open'],
        'per_km': pricing['per_km'],
        'memberships': mems,
    })


@app.route('/api/membership-curves')
def api_curves():
    def pack(ant):
        return {
            'universe': ant.universe.tolist(),
            'terms': {label: ant[label].mf.tolist() for label in ant.terms},
            'min': float(ant.universe[0]),
            'max': float(ant.universe[-1]),
        }
    return jsonify({
        **{k: pack(v) for k, v in ALL_VARS.items()},
        **{k: pack(v) for k, v in ALL_OUTPUTS.items()},
    })


# ---------- Địa điểm & tuyến ----------
@app.route('/api/places')
def api_places():
    q = (request.args.get('q') or '').strip()
    limit = int(request.args.get('limit', 8))
    if not q:
        results = LOCATIONS[:limit]
    else:
        qn = _strip_accents(q)
        results = [loc for loc in LOCATIONS if qn in loc['_norm']][:limit]
    return jsonify([{k: v for k, v in loc.items() if not k.startswith('_')} for loc in results])


@app.route('/api/route', methods=['POST'])
def api_route():
    data = request.get_json(force=True) or {}
    # Ưu tiên lat/lng truyền trực tiếp; nếu không có, tra locations.json
    def _resolve(prefix):
        lat = data.get(f'{prefix}_lat')
        lng = data.get(f'{prefix}_lng')
        name = data.get(prefix)
        if lat is not None and lng is not None:
            return {'name': name or f'{lat},{lng}', 'lat': float(lat), 'lng': float(lng)}
        return find_location(name)
    a = _resolve('from')
    b = _resolve('to')
    if not a or not b:
        return jsonify({'error': 'Không tìm thấy địa điểm'}), 404
    straight = haversine_km(a['lat'], a['lng'], b['lat'], b['lng'])
    road_distance = round(max(0.3, straight * 1.32), 2)
    estimated = round(max(2, road_distance / 25.0 * 60.0), 1)
    clean = lambda x: {k: v for k, v in x.items() if not k.startswith('_')}
    return jsonify({
        'from': clean(a), 'to': clean(b),
        'straight_km': round(straight, 2),
        'distance_km': road_distance,
        'estimated_min': estimated,
    })


@app.route('/api/auto-conditions')
def api_auto_conditions():
    now = datetime.now()
    h = now.hour + now.minute / 60.0

    morning = max(0, 1 - abs(h - 8) / 1.5)
    evening = max(0, 1 - abs(h - 18) / 2.0)
    traffic = max(morning, evening) * 9.0 + 1.5
    if now.weekday() >= 5:
        traffic *= 0.7
    if 23 <= h or h <= 5:
        traffic = 1.0
    traffic = float(min(10, max(0, traffic + random.uniform(-0.6, 0.6))))

    r = random.random()
    if r < 0.55:   w = random.uniform(0, 1.2)
    elif r < 0.85: w = random.uniform(1.2, 2.5)
    else:          w = random.uniform(2.5, 4)

    base_temp = 28 + 5 * math.sin((h - 8) * math.pi / 12)
    temp = float(max(15, min(40, base_temp + random.uniform(-2, 2))))

    aqi = float(max(0, min(500, 90 + random.uniform(-40, 180))))

    demand = traffic * 0.7 + random.uniform(0, 3)
    drivers = float(max(0, min(50, 30 - traffic * 1.8 + random.uniform(-5, 5))))

    return jsonify({
        'traffic_level': round(traffic, 1),
        'weather':       round(w, 2),
        'temperature':   round(temp, 1),
        'air_quality':   round(aqi),
        'demand_level':  round(min(10, demand), 1),
        'driver_availability': round(drivers, 1),
        'time_of_day':   round(h, 2),
        'day_type':      1 if now.weekday() >= 5 else 0,
        'time':          now.strftime('%H:%M, %A'),
    })


# ---------- Bookings ----------
def _read_bookings():
    try:
        with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _write_bookings(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


@app.route('/api/bookings', methods=['GET'])
def api_bookings_list():
    """Trả booking của user hiện tại (admin → tất cả)."""
    items = _read_bookings()
    u = get_current_user()
    if u and u.get('role') != 'admin':
        items = [b for b in items if b.get('user_id') == u['id']]
    elif not u:
        # Khách: trả 20 booking mới nhất (không kèm PII), đa phần FE dùng bản /api/bookings của user
        items = items[-20:]
    return jsonify(items[::-1])


@app.route('/api/bookings', methods=['POST'])
@login_required
def api_bookings_create():
    data = request.get_json(force=True) or {}
    try:
        inp = {k: float(data.get(k, 0)) for k in ALL_VARS.keys()}
    except (TypeError, ValueError):
        return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400
    pricing_table = get_vehicle_pricing()
    vehicle = data.get('vehicle', 'bike')
    if vehicle not in pricing_table:
        vehicle = 'bike'
    pricing = pricing_table[vehicle]
    out = compute_all(inp)
    manual = get_manual_factor()
    total = out['total_multiplier'] * manual
    base_fare = pricing['open'] + pricing['per_km'] * inp['distance']
    final_fare = round(base_fare * total)

    user = get_current_user()
    booking = {
        'id': uuid.uuid4().hex[:8],
        'user_id': user['id'],
        'username': user['username'],
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'from_text': data.get('from_text', ''),
        'to_text':   data.get('to_text', ''),
        'vehicle':   vehicle,
        'vehicle_name': pricing['name'],
        'icon':      pricing['icon'],
        'inputs':    {k: round(v, 2) for k, v in inp.items()},
        **{k: out[k] for k in ('base_multiplier', 'environment_factor', 'surge_factor', 'total_multiplier')},
        'manual_factor': round(manual, 3),
        'base_fare': round(base_fare),
        'final_fare': final_fare,
        'status':    'searching',
        'driver':    None,
    }
    with _bookings_lock:
        items = _read_bookings()
        items.append(booking)
        _write_bookings(items)
    return jsonify(booking), 201


@app.route('/api/bookings/<bid>', methods=['GET'])
@login_required
def api_bookings_get(bid):
    booking = next((b for b in _read_bookings() if b.get('id') == bid), None)
    if not booking:
        return jsonify({'error': 'Không tìm thấy chuyến'}), 404
    u = get_current_user()
    if booking.get('user_id') != u['id'] and u.get('role') != 'admin':
        return jsonify({'error': 'Không có quyền'}), 403
    return jsonify(booking)


@app.route('/api/bookings/<bid>', methods=['DELETE'])
@login_required
def api_bookings_delete(bid):
    u = get_current_user()
    with _bookings_lock:
        items = _read_bookings()
        target = next((b for b in items if b.get('id') == bid), None)
        if target and target.get('user_id') != u['id'] and u.get('role') != 'admin':
            return jsonify({'error': 'Không có quyền'}), 403
        items = [b for b in items if b.get('id') != bid]
        _write_bookings(items)
    return jsonify({'ok': True})


@app.route('/api/stats')
def api_stats():
    items = _read_bookings()
    u = get_current_user()
    if u and u.get('role') != 'admin':
        items = [b for b in items if b.get('user_id') == u['id']]
    if not items:
        return jsonify({'count': 0, 'total': 0, 'avg_surge': 1.0,
                        'avg_distance': 0, 'by_vehicle': {}})
    by_v = {}
    for it in items:
        by_v[it['vehicle_name']] = by_v.get(it['vehicle_name'], 0) + 1
    completed = [it for it in items if it.get('status') in ('completed', 'confirmed', None)]
    return jsonify({
        'count': len(items),
        'completed': len(completed),
        'total': sum(it['final_fare'] for it in items if it.get('status') != 'cancelled'),
        'avg_surge': round(sum(it.get('total_multiplier', 1.0) for it in items) / len(items), 2),
        'avg_distance': round(sum(it.get('inputs', {}).get('distance', 0) for it in items) / len(items), 2),
        'by_vehicle': by_v,
    })


@app.route('/api/rules')
def api_rules():
    return jsonify({
        'fis1': {
            'name': 'FIS-1: Base Multiplier',
            'inputs': ['distance', 'estimated_time', 'time_of_day', 'day_type'],
            'output': 'base_multiplier [0.8 – 2.5]',
            'count': len(fis1_rules),
        },
        'fis2': {
            'name': 'FIS-2: Environment Factor',
            'inputs': ['traffic_level', 'weather', 'temperature', 'air_quality'],
            'output': 'environment_factor [1.0 – 1.5]',
            'count': len(fis2_rules),
        },
        'fis3': {
            'name': 'FIS-3: Surge Factor',
            'inputs': ['demand_level', 'driver_availability'],
            'output': 'surge_factor [1.0 – 2.0]',
            'count': len(fis3_rules),
        },
        'total': len(fis1_rules) + len(fis2_rules) + len(fis3_rules),
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
