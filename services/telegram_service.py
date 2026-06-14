"""
services/telegram_service.py
Helper functions for sending messages / files via the Pyrogram client.
"""
import asyncio
import os
from typing import Optional

from pyrogram import Client
from pyrogram.errors import FloodWait, MessageNotModified

from utils.logger import bot_logger as log


async def safe_send_message(client: Client, chat_id: int, text: str, **kwargs) -> Optional[object]:
    for attempt in range(3):
        try:
            return await client.send_message(chat_id, text, **kwargs)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as ex:
            log.error(f"send_message failed attempt {attempt}: {ex}")
            await asyncio.sleep(2)
    return None


async def safe_edit_message(msg, text: str, **kwargs):
    try:
        await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        try:
            await msg.edit_text(text, **kwargs)
        except Exception:
            pass
    except Exception as ex:
        log.debug(f"edit_message: {ex}")


async def send_video_file(
    client: Client,
    chat_id: int,
    file_path: str,
    caption: str = "",
    progress_msg=None,
) -> bool:
    try:
        size = os.path.getsize(file_path)
        if size > 2 * 1024 * 1024 * 1024:  # >2GB: Telegram limit
            await safe_send_message(client, chat_id, "⚠️ Output file too large for Telegram (>2GB).")
            return False

        if progress_msg:
            await safe_edit_message(progress_msg, "📤 Uploading processed video…")

        await client.send_video(
            chat_id,
            video=file_path,
            caption=caption,
            supports_streaming=True,
        )
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return False
    except Exception as ex:
        log.error(f"send_video_file: {ex}")
        return False


async def send_photo_file(
    client: Client,
    chat_id: int,
    file_path: str,
    caption: str = "",
) -> bool:
    try:
        await client.send_photo(chat_id, photo=file_path, caption=caption)
        return True
    except Exception as ex:
        log.error(f"send_photo_file: {ex}")
        return False


async def send_document_file(
    client: Client,
    chat_id: int,
    file_path: str,
    caption: str = "",
) -> bool:
    try:
        await client.send_document(chat_id, document=file_path, caption=caption)
        return True
    except Exception as ex:
        log.error(f"send_document_file: {ex}")
        return False
