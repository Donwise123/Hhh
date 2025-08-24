# TelegramFXCopier — Quick Deploy & Run

## Important security
- NEVER commit real tokens/passwords to GitHub.
- Use Railway environment variables or a local `.env`. Keep session files private.

## Files
- config_example.py (placeholders)
- fxapi_client.py
- parser.py
- manager.py
- telegram_listener.py
- requirements.txt
- Procfile

## Env vars to set (Railway)
TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
TELEGRAM_CHANNELS (comma-separated)
VIP_CHANNELS (comma-separated e.g. @forexgdp0)
FXAPI_TOKEN
MT5_ACCOUNT (optional), MT5_SERVER, MT5_PASSWORD
NEAR_MISS_PIPS, VIP_PROFIT_TRAIL_PIPS, TP1_THRESHOLD_PERCENT, WATCHDOG_INTERVAL, MAX_RETRIES

## First-run Telethon session
Run locally once to create session file:
1. pip install -r requirements.txt
2. python telegram_listener.py
3. Telethon will prompt for login code — enter from your phone. This creates `telegramfxcopier_session.session`.
4. Upload that `.session` file to Railway as a project file/secret OR run the bot locally forever.

## Deploy (Railway)
1. Push repo to GitHub.
2. Create Railway project -> Deploy from GitHub.
3. Add env vars in Railway project settings (as above).
4. Add the Telethon session file to Railway or perform first login locally and upload session file.
5. Deploy. Check logs.

## Testing
- Use a demo MT5 account or FXAPI sandbox first.
- Post test signals into your channels.
- Monitor logs and `telegramfxcopier_trades.csv`.
## Notes
- This bot is designed for zero-delay via FXAPI retries and watchdog loops.
- It is robust but cannot control broker-side delays; always test on demo first.
