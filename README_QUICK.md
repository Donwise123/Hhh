# TelegramFXCopier (FXAPI edition) — Quick Run

## 1. Add files to GitHub (already done)
Files: telegram_listener.py, fxapi_client.py, parser.py, manager.py, config.py, requirements.txt, Procfile

## 2. Set environment variables (Railway / .env)
TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNEL
FXAPI_TOKEN
MT5_ACCOUNT, MT5_SERVER, MT5_PASSWORD
(optional) NEAR_MISS_PIPS, VIP_PROFIT_TRAIL_PIPS, TP1_THRESHOLD_PERCENT

## 3. Deploy on Railway
- Connect repo to Railway
- Set env vars in Railway project settings
- Deploy; Railway runs `Procfile` -> `python telegram_listener.py`

## 4. First run telethon will ask for code once (enter on the first run)
- This establishes the user session.

## 5. Test
- Post a test VIP signal in the channel and watch Railway logs + trades_log.csv

## Notes
- This bot is designed for zero-delay via FXAPI retries and watchdog loops.
- It is robust but cannot control broker-side delays; always test on demo first.
