"""
Configuration for Pokemon Auto Register Tool
Based on ANALYSIS-poke-dai-chien.md
"""

import sys
from pathlib import Path

# API Configuration
API_BASE_URL = "https://sdk-sg.pocketgamesol.com/pocketgames"

# Endpoints
ENDPOINTS = {
    "init_sdk": "/client/config/v3.1/initSDK",
    "register": "/client/user/v3/register",
    "bind_zone": "/client/user/v3/bindZone",
    "login": "/client/user/v3/login",
    "verify_user": "/client/user/verify/userInfo",
    "bind_visitor": "/client/user/bindVisitor/v5.0",
}

# Secret Key for MD5 signing
# Verified working signing_value from Dart snapshot
SIGNING_VALUE = "f43968a73df747aab4b9b1e506265050"
SECRET_KEY = "f43968a73df747aab4b9b1e506265050"

# App Configuration (from Dart decompiled code - flutter_register_reverse_engineering.md)
APP_CONFIG = {
    "app_id": "10062",
    "user_channel": 0,
    "adv_channel": "63",
    "source": 2,
    "sdk_version": "flt_250217"
}

# Package Info
PACKAGE_INFO = {
    "package_name": "com.pokedaigpguanwang.vn",
    "version_code": "7300",
    "version_name": "73.0.0"
}

# Validation Rules (from analysis)
VALIDATION = {
    "account_min_length": 4,
    "account_max_length": 50,
    "account_pattern": r'^[a-z0-9_]{4,50}$',
    "password_min_length": 6,
    "password_max_length": 20,
}

# Device Models Pool (30+ Modern popular Android devices 2023 - 2026)
DEVICE_MODELS = [
    # Samsung Flagship & Mid-range
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S928B", "name": "Samsung Galaxy S24 Ultra", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S926B", "name": "Samsung Galaxy S24+", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S921B", "name": "Samsung Galaxy S24", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S918B", "name": "Samsung Galaxy S23 Ultra", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S916B", "name": "Samsung Galaxy S23+", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S911B", "name": "Samsung Galaxy S23", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S908B", "name": "Samsung Galaxy S22 Ultra", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-S901B", "name": "Samsung Galaxy S22", "sdk_version": "32", "os_version": "12"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-A556B", "name": "Samsung Galaxy A55 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-A546B", "name": "Samsung Galaxy A54 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-A356B", "name": "Samsung Galaxy A35 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-F731B", "name": "Samsung Galaxy Z Flip5", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-F946B", "name": "Samsung Galaxy Z Fold5", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "samsung", "brand": "samsung", "model": "SM-F741B", "name": "Samsung Galaxy Z Flip6", "sdk_version": "34", "os_version": "14"},

    # Xiaomi / Redmi / POCO
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23116PN5BC", "name": "Xiaomi 14", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23127PN0CG", "name": "Xiaomi 14 Pro", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "2211133G", "name": "Xiaomi 13", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "2210132G", "name": "Xiaomi 13 Pro", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "2312DRA50G", "name": "Redmi Note 13 Pro 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23090RA98G", "name": "Redmi Note 13", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "22101316G", "name": "Redmi Note 12 Pro", "sdk_version": "32", "os_version": "12"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23021RAAEG", "name": "Redmi Note 12", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23049PCD8G", "name": "POCO F5", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23013PC75G", "name": "POCO F5 Pro", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Xiaomi", "brand": "xiaomi", "model": "23122PCD1G", "name": "POCO X6 Pro", "sdk_version": "34", "os_version": "14"},

    # OPPO
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2525", "name": "OPPO Reno10 Pro 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2599", "name": "OPPO Reno11 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2607", "name": "OPPO Reno12 Pro 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2551", "name": "OPPO Find N3", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2565", "name": "OPPO A78", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "OPPO", "brand": "oppo", "model": "CPH2579", "name": "OPPO A58", "sdk_version": "33", "os_version": "13"},

    # Realme
    {"manufacturer": "realme", "brand": "realme", "model": "RMX3771", "name": "Realme 11 Pro 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "realme", "brand": "realme", "model": "RMX3706", "name": "Realme GT Neo 5", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "realme", "brand": "realme", "model": "RMX3840", "name": "Realme 12 Pro+ 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "realme", "brand": "realme", "model": "RMX3850", "name": "Realme GT 5 Pro", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "realme", "brand": "realme", "model": "RMX3741", "name": "Realme 11 5G", "sdk_version": "33", "os_version": "13"},

    # Vivo
    {"manufacturer": "vivo", "brand": "vivo", "model": "V2250", "name": "Vivo V27 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "vivo", "brand": "vivo", "model": "V2244", "name": "Vivo V29 5G", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "vivo", "brand": "vivo", "model": "V2318", "name": "Vivo V30 5G", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "vivo", "brand": "vivo", "model": "V2247", "name": "Vivo Y36", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "vivo", "brand": "vivo", "model": "V2327", "name": "Vivo V30e", "sdk_version": "34", "os_version": "14"},

    # Google Pixel
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 8 Pro", "name": "Google Pixel 8 Pro", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 8", "name": "Google Pixel 8", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 7 Pro", "name": "Google Pixel 7 Pro", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 7", "name": "Google Pixel 7", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 7a", "name": "Google Pixel 7a", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "Google", "brand": "google", "model": "Pixel 8a", "name": "Google Pixel 8a", "sdk_version": "34", "os_version": "14"},

    # OnePlus
    {"manufacturer": "OnePlus", "brand": "oneplus", "model": "CPH2449", "name": "OnePlus 11", "sdk_version": "33", "os_version": "13"},
    {"manufacturer": "OnePlus", "brand": "oneplus", "model": "CPH2581", "name": "OnePlus 12", "sdk_version": "34", "os_version": "14"},
    {"manufacturer": "OnePlus", "brand": "oneplus", "model": "CPH2493", "name": "OnePlus Nord 3", "sdk_version": "33", "os_version": "13"}
]

# Screen Resolutions
SCREEN_RESOLUTIONS = [
    {"width": "1440", "height": "3200"},  # QHD+
    {"width": "1080", "height": "2400"},  # FHD+
    {"width": "1080", "height": "2340"},  # FHD+
    {"width": "1440", "height": "3088"},  # QHD+
]

# Request Headers
DEFAULT_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "User-Agent": "Dart/3.0 (dart:io)"
}

# Rate Limiting
RATE_LIMIT = {
    "max_per_minute": 30,  # Adjusted limit
    "delay_min": 1.5,     # Min delay between requests (seconds)
    "delay_max": 3.0,     # Max delay between requests (seconds)
}

# Retry Configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 5,  # seconds
}

# Game Zone (Server) Configuration
DEFAULT_GAME_ZONE_ID = "4"  # Server 4 (Poke S4) - confirmed active in pcap

# Database & Storage
def _find_cfg_db():
    import os
    env_db = os.environ.get("POKEMON_DB_PATH")
    if env_db:
        p_env = Path(env_db)
        p_env.parent.mkdir(parents=True, exist_ok=True)
        return str(p_env)
    web_root = Path(__file__).resolve().parent.parent
    default_db = web_root / "data" / "pokemon_web.db"
    default_db.parent.mkdir(parents=True, exist_ok=True)
    return str(default_db)

DATABASE_FILE = _find_cfg_db()
EXPORT_FILE = None

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "auto_register.log"
