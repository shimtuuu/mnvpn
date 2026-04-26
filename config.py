# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== Telegram Bot ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# ==================== 3X-UI Panel ====================
PANEL_URL = os.getenv("PANEL_URL", os.getenv("VPN_PANEL_URL"))
PANEL_USERNAME = os.getenv("PANEL_USERNAME", os.getenv("VPN_PANEL_USERNAME"))
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", os.getenv("VPN_PANEL_PASSWORD"))

# Server details for generating client links
SERVER_IP = os.getenv("SERVER_IP", "50.114.115.138")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "50.114.115.138.nip.io")
SUB_PORT = os.getenv("SUB_PORT", "2096")
SUB_SECRET = os.getenv("SUB_SECRET", "DR8BISV6VBK13aNbnOTCs66mZbw0YZPl")
INBOUND_ID = int(os.getenv("INBOUND_ID", "1"))

# ==================== Pricing Model (Ultima VPN style) ====================
# Base price: 100₽/month for 1 device, with volume discounts
DEVICE_PLANS = {
    1: {"price_per_month_rub": 100, "price_per_month_stars": 75, "name": "1 устройство"},
    2: {"price_per_month_rub": 180, "price_per_month_stars": 135, "name": "2 устройства"},
    3: {"price_per_month_rub": 250, "price_per_month_stars": 190, "name": "3 устройства"},
    5: {"price_per_month_rub": 400, "price_per_month_stars": 300, "name": "5 устройств"},
}

# Subscription periods with volume discounts
SUBSCRIPTION_PERIODS = {
    1: {"months": 1, "days": 30, "discount": 0, "name": "1 месяц"},
    3: {"months": 3, "days": 90, "discount": 10, "name": "3 месяца (-10%)"},
    6: {"months": 6, "days": 180, "discount": 15, "name": "6 месяцев (-15%)"},
    12: {"months": 12, "days": 365, "discount": 20, "name": "1 год (-20%)"},
}

# Referral
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "3"))

# Legacy pricing (to prevent imports breaking)
VPN_SUBSCRIPTION_PRICE = 100
VPN_DEVICE_PRICE = 100
SUBSCRIPTION_DAYS = 30
GIFT_PRICES = {1: 100, 3: 250, 6: 450}

# ==================== Trial ====================
TRIAL_DURATION_DAYS = 1  # 24 hours
TRIAL_MAX_DEVICES = 1
TRIAL_ENABLED = os.getenv("TRIAL_ENABLED", "true").lower() == "true"

# ==================== Limits ====================
MAX_CLIENTS_PER_USER = 5

# ==================== Payments ====================
# Yandex.Kassa / YooKassa (optional)
YANDEX_KASSA_SHOP_ID = os.getenv("YANDEX_KASSA_SHOP_ID")
YANDEX_KASSA_API_KEY = os.getenv("YANDEX_KASSA_API_KEY")
YANDEX_KASSA_WEBHOOK_SECRET = os.getenv("YANDEX_KASSA_WEBHOOK_SECRET")

# Crypto (USDT TRC20) - optional
CRYPTO_WALLET_USDT = os.getenv("CRYPTO_WALLET_USDT", "")

# ==================== Misc ====================
DB_PATH = os.getenv("DB_PATH", "mnvpn.db")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "mnvpn_support")
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://example.com")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BANNER_PATH = os.path.join(os.path.dirname(__file__), "assets", "banner.png")
