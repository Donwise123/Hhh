# config_example.py
# Upload this file to GitHub as an example. DO NOT put real secrets here.

import os

# TELEGRAM (Telethon user session recommended for VIP/private channels)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "24361556"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "your_api_hash_here")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "+2340000000000")   # for first-run Telethon login

# Channels to listen (comma-separated or array in Railway env var)
# Example: "@GaryGoldLegacy,@forexgdp0"
TELEGRAM_CHANNELS = [c.strip() for c in os.getenv("TELEGRAM_CHANNELS", "@GaryGoldLegacy,@forexgdp0").split(",") if c.strip()]

# Channels that are considered VIP short-source(s) (where short "Gold sell now" posts occur)
VIP_CHANNELS = {c.strip().lower() for c in os.getenv("VIP_CHANNELS", "@forexgdp0").split(",") if c.strip()}

# FXAPI (store token in Railway env var FXAPI_TOKEN)
FXAPI_TOKEN = os.getenv("FXAPI_TOKEN", "your_fxapi_token_here")

# (Optional) MT5 account details if your FXAPI requires them
MT5_ACCOUNT = os.getenv("MT5_ACCOUNT", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")

# Bot behavior tuning (change via env vars in Railway if needed)
NEAR_MISS_PIPS = float(os.getenv("NEAR_MISS_PIPS", "2"))             # execute if within 2 pips of other end
VIP_PROFIT_TRAIL_PIPS = float(os.getenv("VIP_PROFIT_TRAIL_PIPS", "3")) # 3 pips trailing for VIP
TP1_THRESHOLD_PERCENT = float(os.getenv("TP1_THRESHOLD_PERCENT", "75"))
WATCHDOG_INTERVAL = float(os.getenv("WATCHDOG_INTERVAL", "0.25"))     # seconds between watchdog ticks
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "6"))
MAX_CONCURRENT_PER_SYMBOL = int(os.getenv("MAX_CONCURRENT_PER_SYMBOL", "3"))

# Persistence & logs
LOG_CSV = os.getenv("LOG_CSV", "telegramfxcopier_trades.csv")
STATE_JSON = os.getenv("STATE_JSON", "telegramfxcopier_state.json")
