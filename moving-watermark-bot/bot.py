"""
bot.py — Moving Watermark Bot
Main entry point. Starts Flask health server + Pyrogram bot.
"""
import asyncio
import os
import sys
import threading
import time
import traceback

# ── asyncio setup (Python 3.11+) ─────────────────────────────────────────
if not sys.platform.startswith("win"):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from flask import Flask
from pyrogram import Client, idle

from config import BOT_TOKEN, API_ID, API_HASH, PORT, TEMP_DIR, LOGS_DIR
from database.db import db
from queue_manager import start_queue
from utils.logger import bot_logger as log

# ── Auto-create directories ───────────────────────────────────────────────
for d in (TEMP_DIR, LOGS_DIR, "handlers", "services", "utils", "database"):
    os.makedirs(d, exist_ok=True)

# ── Flask health server ───────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Moving Watermark Bot is running!"

@flask_app.route("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}

def _run_flask():
    log.info(f"Flask health server starting on port {PORT}…")
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)


# ── Pyrogram Bot ──────────────────────────────────────────────────────────
class WatermarkBot(Client):
    def __init__(self):
        super().__init__(
            "watermark_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="handlers"),
            workers=50,
            sleep_threshold=5,
            workdir="/tmp",
        )

    async def start(self):
        # Init DB
        await db.connect()
        log.info("Database connected.")

        # Restore stuck jobs from previous run
        await db.restore_stuck_jobs()
        log.info("Stuck jobs restored to pending.")

        await super().start()
        me = await self.get_me()
        log.info(f"✅ Bot started: @{me.username} (ID: {me.id})")

        # Start queue processor
        start_queue(self)
        log.info("Queue processor started.")

    async def stop(self, *args):
        log.info("Bot stopping…")
        try:
            await db.close()
        except Exception:
            pass
        await super().stop()
        log.info("Bot stopped.")


# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Validate config
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if missing:
        log.critical(f"Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    # Start Flask in background
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()
    time.sleep(1)

    try:
        bot = WatermarkBot()

        import signal

        def _shutdown(sig, frame):
            log.info(f"Signal {sig} received. Shutting down…")
            try:
                ev = asyncio.get_event_loop()
                ev.create_task(bot.stop())
            except Exception:
                pass
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        log.info("Starting bot…")
        bot.run()

    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — exiting.")
    except Exception as e:
        log.critical(f"Fatal error: {e}\n{traceback.format_exc()}")
    finally:
        log.info("Process exit.")
