import os

def _int(key, default):
    try:
        return int(os.environ.get(key, default))
    except:
        return default

def _float(key, default):
    try:
        return float(os.environ.get(key, default))
    except:
        return default

# ── Telegram ──────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
API_ID      = _int("API_ID", 0)
API_HASH    = os.environ.get("API_HASH", "")

# ── Admin ─────────────────────────────────────────────────────────────────
_admins_raw = os.environ.get("ADMINS", "")
ADMINS: list[int] = [int(x.strip()) for x in _admins_raw.split(",") if x.strip().isdigit()]
OWNER_ID    = ADMINS[0] if ADMINS else 0

# ── Storage ───────────────────────────────────────────────────────────────
DATABASE_PATH = os.environ.get("DATABASE_PATH", "watermark_bot.db")
TEMP_DIR      = os.environ.get("TEMP_DIR", "temp")
LOGS_DIR      = os.environ.get("LOGS_DIR", "logs")

# ── Limits ────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_GB  = _float("MAX_FILE_SIZE_GB", 1.0)
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_GB * 1024 * 1024 * 1024)

# ── Watermark defaults ────────────────────────────────────────────────────
DEFAULT_WATERMARK_TEXT    = os.environ.get("DEFAULT_WATERMARK_TEXT", "@YourChannel")
DEFAULT_OPACITY           = _float("DEFAULT_OPACITY", 0.7)
DEFAULT_SIZE              = _float("DEFAULT_SIZE", 0.2)       # fraction of video width
DEFAULT_SPEED             = _float("DEFAULT_SPEED", 80.0)     # pixels per second
DEFAULT_FONT_SIZE         = _int("DEFAULT_FONT_SIZE", 40)
DEFAULT_COLOR             = os.environ.get("DEFAULT_COLOR", "white")
DEFAULT_MODE              = os.environ.get("DEFAULT_MODE", "moving")  # moving | static

# ── Flask health server ───────────────────────────────────────────────────
PORT = _int("PORT", 10000)
