# main.py
"""
Main entrypoint for TelegramFXCopier.
Starts Telethon client, registers handler from telegram_listener,
starts watchdog loop and ensures graceful shutdown.
"""

import asyncio
import logging
import signal
import os
from telethon import TelegramClient
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNELS
from telegram_listener import handle_message, watchdog_loop  # handler and watchdog coroutine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("telegramfxcopier")

# Telethon session name (can be uploaded to Railway if created locally)
SESSION_NAME = os.getenv("TELETHON_SESSION", "telegramfxcopier_session")

def run():
    loop = asyncio.get_event_loop()

    # Create Telethon client instance (the same used in telegram_listener)
    client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    async def _startup():
        try:
            logger.info("Starting TelegramFXCopier...")
            # start Telethon (will reuse session file if present; otherwise prompt first-run locally)
            await client.start(phone=TELEGRAM_PHONE)
            logger.info("Telethon client started.")
            # Register event handler (handler defined in telegram_listener)
            # Note: telegram_listener.handle_message expects 'event' parameter.
            client.add_event_handler(handle_message, events=TelegramClient._event_class("NewMessage"))

            # Add handler using chats list - Telethon allows specifying chats when adding handler,
            # but telegram_listener.handle_message already checks incoming events; we keep registration general.
            # Start watchdog loop (runs in background)
            loop.create_task(watchdog_loop())

            logger.info(f"Listening on channels: {TELEGRAM_CHANNELS}")
            # Block until disconnected
            await client.run_until_disconnected()
        except Exception as exc:
            logger.exception("Startup error: %s", exc)
            raise

    # Graceful shutdown handler
    def _stop(*args):
        logger.info("Shutdown signal received. Stopping...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    # Hook signals
    try:
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        # Windows may not support add_signal_handler in same way
        pass

    try:
        loop.run_until_complete(_startup())
    except asyncio.CancelledError:
        logger.info("Tasks cancelled, shutting down.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
    finally:
        try:
            loop.run_until_complete(client.disconnect())
        except Exception:
            pass
        loop.close()
        logger.info("TelegramFXCopier stopped.")

if __name__ == "__main__":
    run()
