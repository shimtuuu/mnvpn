import os
from dotenv import load_dotenv

load_dotenv()

# ==================== Bot ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")

DB_PATH = os.getenv("DB_PATH", "db.sqlite3")

# Admin Telegram IDs (comma-separated in .env)
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "mnvpn_support")

# ==================== Brand (HitVPN parity) ====================
BRAND_NAME = os.getenv("BRAND_NAME", "MNVPN")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Быстрый и безопасный VPN без логов")
PRICE_PER_DEVICE_DISPLAY = os.getenv("PRICE_PER_DEVICE_DISPLAY", "100₽ / устройство / мес")
EXPIRY_NOTICE_DAYS = int(os.getenv("EXPIRY_NOTICE_DAYS", "3"))

# ==================== VPN Panel (3X-UI) ====================
VPN_PANEL_URL = os.getenv("VPN_PANEL_URL")
VPN_PANEL_USERNAME = os.getenv("VPN_PANEL_USERNAME")
VPN_PANEL_PASSWORD = os.getenv("VPN_PANEL_PASSWORD")

# Server details for generating client links
SERVER_IP = os.getenv("SERVER_IP", "50.114.115.138")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "50.114.115.138.nip.io")
SUB_PORT = os.getenv("SUB_PORT", "2096")
SUB_SECRET = os.getenv("SUB_SECRET", "DR8BISV6VBK13aNbnOTCs66mZbw0YZPl")
INBOUND_ID = int(os.getenv("INBOUND_ID", "1"))

# ==================== Pricing ====================
VPN_SUBSCRIPTION_PRICE = float(os.getenv("VPN_SUBSCRIPTION_PRICE", "100"))
VPN_DEVICE_PRICE = float(os.getenv("VPN_DEVICE_PRICE", "100"))
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

# Gift pricing: {months: price_rub}
GIFT_PRICES = {
    1: int(os.getenv("GIFT_PRICE_1M", "100")),
    3: int(os.getenv("GIFT_PRICE_3M", "250")),
    6: int(os.getenv("GIFT_PRICE_6M", "450")),
}

# ==================== Trial ====================
TRIAL_ENABLED = os.getenv("TRIAL_ENABLED", "true").lower() == "true"
TRIAL_HOURS = int(os.getenv("TRIAL_HOURS", "24"))
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "30"))

# ==================== Referral ====================
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "15"))

# ==================== Payments ====================
# Yandex.Kassa / YooKassa
YANDEX_KASSA_SHOP_ID = os.getenv("YANDEX_KASSA_SHOP_ID")
YANDEX_KASSA_API_KEY = os.getenv("YANDEX_KASSA_API_KEY")
YANDEX_KASSA_WEBHOOK_SECRET = os.getenv("YANDEX_KASSA_WEBHOOK_SECRET")

# Legacy Telegram Payments
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", None)

# Crypto (USDT TRC20)
CRYPTO_WALLET_USDT = os.getenv("CRYPTO_WALLET_USDT", "")

# ==================== Misc ====================
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://example.com")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BANNER_PATH = os.path.join(os.path.dirname(__file__), "assets", "banner.png")
