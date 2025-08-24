# telegram_listener.py - Handles incoming Telegram messages (VIP + normal channels)

import asyncio
import os
import pytesseract
from PIL import Image
from telethon import TelegramClient, events
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNELS, VIP_CHANNELS, WATCHDOG_INTERVAL
from parser import parse_signal, detect_short_vip
from manager import open_trade_from_signal, apply_command_to_trade, watchdog_tick, save_state
from fxapi_client import FXAPI

# Telethon session
session_name = os.getenv("TELETHON_SESSION", "telegramfxcopier_session")
client = TelegramClient(session_name, TELEGRAM_API_ID, TELEGRAM_API_HASH)

# FX API instance
fx = FXAPI()

# Processed message cache
_processed = set()

async def handle_message(event):
    try:
        msg = event.message
        mid = f"{msg.chat_id}:{msg.id}"
        if mid in _processed:
            return
        _processed.add(mid)

        # Extract text + OCR if media
        text = msg.message or ""
        if msg.media:
            img_path = await msg.download_media()
            try:
                text += " " + pytesseract.image_to_string(Image.open(img_path))
            except Exception as e:
                print("OCR failure:", e)

        # Parse initial trade signal
        signal = parse_signal(text)

        # Identify channel
        try:
            chat = await event.get_chat()
            chat_tag = f"@{getattr(chat, 'username', '')}".lower() if getattr(chat, "username", None) else str(chat.id)
        except Exception:
            chat_tag = None

        # VIP detection
        short_vip = None
        is_from_vip_channel = (chat_tag and chat_tag.lower() in {c.lower() for c in VIP_CHANNELS})
        if is_from_vip_channel:
            short_vip = detect_short_vip(text)
            if short_vip:
                signal = short_vip

        # Handle reply-based updates (follow-ups to old trades)
        if getattr(msg, "reply_to_msg_id", None):
            try:
                parent = await msg.get_reply_message()
                parent_mid = f"{parent.chat_id}:{parent.id}"
                parent_text = parent.message or ""
                parent_signal = parse_signal(parent_text) or detect_short_vip(parent_text)
                for cmd in (signal.get("commands") or []):
                    if apply_command_to_trade(parent_mid, parent_signal, cmd):
                        save_state()
                        return
            except Exception as e:
                print("Reply mapping failed:", e)

        # Handle update-only commands (e.g. "move SL", "close trade")
        if signal.get("commands") and not (signal.get("symbol") and signal.get("side")):
            for cmd in signal["commands"]:
                if apply_command_to_trade(mid, signal, cmd):
                    save_state()
            return

        # Handle full trade entries
        if signal.get("symbol") and signal.get("side"):
            if short_vip:
                signal["vip"] = True
                signal["sl"] = None
                signal["tps"] = []
            ticket = open_trade_from_signal(mid, signal, last_result="win")
            if ticket:
                print("Opened trade:", ticket, "| VIP =", signal.get("vip", False))
            else:
                print("No trade opened for", mid)
            save_state()
            return

    except Exception as e:
        print("Handle message error:", e)

async def watchdog_loop():
    """Runs periodic background checks."""
    while True:
        try:
            watchdog_tick()
        except Exception as e:
            print("Watchdog outer error:", e)
        await asyncio.sleep(WATCHDOG_INTERVAL)

async def main():
    await client.start(phone=TELEGRAM_PHONE)
    print("✅ Connected. Listening to channels:", TELEGRAM_CHANNELS)
    client.add_event_handler(handle_message, events.NewMessage(chats=TELEGRAM_CHANNELS))
    asyncio.create_task(watchdog_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        save_state()
        print("🛑 Stopped.")            chat_tag = None

        short_vip = None
        is_from_vip_channel = (chat_tag and chat_tag.lower() in {c.lower() for c in VIP_CHANNELS})
        if is_from_vip_channel:
            short_vip = detect_short_vip(text)
            if short_vip:
                signal = short_vip

        if getattr(msg, "reply_to_msg_id", None):
            try:
                parent = await msg.get_reply_message()
                parent_mid = f"{parent.chat_id}:{parent.id}"
                parent_text = parent.message or ""
                parent_signal = parse_signal(parent_text) or detect_short_vip(parent_text)
                for cmd in (signal.get("commands") or []):
                    if apply_command_to_trade(parent_mid, parent_signal, cmd):
                        save_state(); return
            except Exception as e:
                print("Reply mapping failed", e)

        if signal.get("commands") and not (signal.get("symbol") and signal.get("side")):
            for cmd in signal["commands"]:
                if apply_command_to_trade(mid, signal, cmd):
                    save_state()
            return

        if signal.get("symbol") and signal.get("side"):
            if short_vip:
                signal["vip"] = True
                signal["sl"] = None
                signal["tps"] = []
            ticket = open_trade_from_signal(mid, signal, last_result="win")
            if ticket:
                print("Opened", ticket, "vip=", signal.get("vip", False))
            else:
                print("No trade opened for", mid)
            save_state(); return

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
    print("Connected. Listening to:", TELEGRAM_CHANNELS)
    client.add_event_handler(handle_message, events.NewMessage(chats=TELEGRAM_CHANNELS))
    asyncio.create_task(watchdog_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        save_state()
        print("Stopped.")                ocr_text = pytesseract.image_to_string(Image.open(img_path))
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
