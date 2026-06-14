"""
services/image_service.py
Download watermark PNG from Telegram and cache it locally.
"""
import os
from typing import Optional

from pyrogram import Client

from utils.helpers import make_temp_path
from utils.logger import bot_logger as log
from config import TEMP_DIR

os.makedirs(TEMP_DIR, exist_ok=True)

_wm_cache: dict[str, str] = {}   # file_id -> local path


async def download_watermark_image(client: Client, file_id: str) -> Optional[str]:
    """Download watermark PNG to disk and return local path."""
    if file_id in _wm_cache and os.path.exists(_wm_cache[file_id]):
        return _wm_cache[file_id]
    try:
        dest = os.path.join(TEMP_DIR, f"wm_{file_id[:20]}.png")
        path = await client.download_media(file_id, file_name=dest)
        _wm_cache[file_id] = path
        return path
    except Exception as ex:
        log.error(f"download_watermark_image: {ex}")
        return None
