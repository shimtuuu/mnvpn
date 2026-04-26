"""Configuration for MNVPN Telegram Bot."""
import os
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM BOT ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

# === XUI PANEL ===
XUI_HOST = os.getenv("XUI_HOST", "http://localhost:2053")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "admin")
XUI_INBOUND_ID = int(os.getenv("XUI_INBOUND_ID", "1"))

# === DATABASE ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///mnvpn.db")

# === PRICING (Ultima Style — Multi-Device Plans + Period Discounts) ===

# Device Plans (Monthly base price)
DEVICE_PLANS = {
    1: {"name": "Solo (1 устройство)", "price_per_month_rub": 100, "price_per_month_stars": 80},
    3: {"name": "Family (3 устройства)", "price_per_month_rub": 200, "price_per_month_stars": 160},
    5: {"name": "Pro (5 устройств)", "price_per_month_rub": 300, "price_per_month_stars": 240},
}

# Subscription Periods (months: {days, discount%})
SUBSCRIPTION_PERIODS = {
    1:  {"name": "1 месяц", "months": 1,  "days": 30,  "discount": 0},
    3:  {"name": "3 месяца", "months": 3,  "days": 90,  "discount": 10},
    6:  {"name": "6 месяцев", "months": 6,  "days": 180, "discount": 15},
    12: {"name": "1 год",     "months": 12, "days": 365, "discount": 20},
}

# Legacy (for backward compatibility)
VPN_SUBSCRIPTION_PRICE = DEVICE_PLANS[1]["price_per_month_rub"]
VPN_DEVICE_PRICE = 50  # Additional slot price
SUBSCRIPTION_DAYS = 30

# === FEATURES ===
TRIAL_ENABLED = True
TRIAL_HOURS = 24

# === REFERRAL PROGRAM ===
REFERRAL_BONUS_DAYS = 7

# === GIFT VPN ===
GIFT_PRICES = {
    1: 100,
    3: 250,
    6: 450,
}

# === PAYMENT PROVIDERS ===
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

CRYPTO_WALLET_USDT = os.getenv("CRYPTO_WALLET_USDT")

# === SUPPORT ===
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "mnvpnsupport")

# === MEDIA ===
BANNER_PATH = os.getenv("BANNER_PATH", "assets/banner.jpg")

# === VPN CONNECTIVITY ===
VPN_SERVER_DOMAIN = os.getenv("VPN_SERVER_DOMAIN", "vpn.example.com")
VPN_SERVER_IP = os.getenv("VPN_SERVER_IP", "1.2.3.4")
VPN_SERVER_PORT = int(os.getenv("VPN_SERVER_PORT", "443"))
VPN_SNI = os.getenv("VPN_SNI", "www.apple.com")
VPN_FINGERPRINT = os.getenv("VPN_FINGERPRINT", "chrome")
