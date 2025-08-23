# telegram_listener.py - main entry point. Uses Telethon user session to read VIP channels reliably.

import asyncio
import aiohttp
import os
import time
import pytesseract
from PIL import Image
from telethon import TelegramClient, events
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNEL, WATCHDOG_INTERVAL
from parser import parse_signal
from manager import open_trade_from_signal, apply_command_to_trade, watchdog_tick, save_state
from fxapi_client import FXAPI

# Telethon client (user session recommended for private VIP channels)
session_name = os.getenv("TELETHON_SESSION", "telegramfxcopier_session")
client = TelegramClient(session_name, TELEGRAM_API_ID, TELEGRAM_API_HASH)
fx = FXAPI()

# processed message ids to prevent duplicate work
_processed = set()

async def handle_message(event):
    try:
        msg = event.message
        mid = f"{msg.chat_id}:{msg.id}"
        if mid in _processed:
            return
        _processed.add(mid)

        text = msg.message or ""
        # if there's a photo or media, download and OCR
        if msg.media:
            # download into memory
            img_path = await msg.download_media()
            try:
                ocr_text = pytesseract.image_to_string(Image.open(img_path))
                text += " " + ocr_text
            except Exception as e:
                print("OCR fail", e)

        # parse
        signal = parse_signal(text)

        # If message is a follow-up (reply), try to map to parent via event.message.reply_to_msg_id
        if getattr(msg, "reply_to_msg_id", None):
            # fetch parent
            try:
                parent = await msg.get_reply_message()
                parent_mid = f"{parent.chat_id}:{parent.id}"
                parent_text = parent.message or ""
                parent_signal = parse_signal(parent_text)
                # If this message contains update commands, apply to parent's trade
                for cmd in signal.get("commands", []):
                    applied = apply_command_to_trade(parent_mid, parent_signal, cmd)
                    if applied:
                        print("Applied command to parent trade:", cmd)
                        # persist state
                        save_state()
                        return
            except Exception as e:
                print("Reply mapping failed", e)

        # If message contains only an update command but not a reply, attempt to map by symbol/most recent
        if signal.get("commands") and not signal.get("side"):
            # apply each command
            for cmd in signal["commands"]:
                applied = apply_command_to_trade(mid, signal, cmd)
                if applied:
                    save_state()
            return

        # Entry signals
        if signal.get("side") and signal.get("symbol"):
            # open trade
            ticket = open_trade_from_signal(mid, signal, last_result="win")  # last_result could be computed from history
            if ticket:
                print("Opened trade ticket:", ticket)
            else:
                print("No trade opened for message:", mid)
            save_state()
            return

    except Exception as e:
        print("Handle message error:", e)

async def watchdog_loop():
    while True:
        try:
            watchdog_tick()
        except Exception as e:
            print("Watchdog outer error:", e)
        await asyncio.sleep(WATCHDOG_INTERVAL)

async def main():
    await client.start(phone=TELEGRAM_PHONE)
    print("Connected to Telegram — listening on", TELEGRAM_CHANNEL)
    # register handler for that channel
    client.add_event_handler(handle_message, events.NewMessage(chats=TELEGRAM_CHANNEL))
    # spawn watchdog
    asyncio.create_task(watchdog_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
        save_state()
