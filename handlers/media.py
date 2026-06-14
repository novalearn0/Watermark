"""
handlers/media.py
Receives video/image from user → validates → adds to queue → notifies user.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from database.db import db
from utils.validators import is_valid_file_size, is_valid_video, is_valid_image
from utils.helpers import human_size
from utils.logger import bot_logger as log
from config import MAX_FILE_SIZE_BYTES


def _get_media_info(message: Message):
    """Return (file_id, mime_type, size, ftype) or None."""
    if message.video:
        m = message.video
        return m.file_id, m.mime_type, m.file_size, "video"
    if message.document:
        m = message.document
        mime = m.mime_type or ""
        fname = m.file_name or ""
        if is_valid_video(mime):
            return m.file_id, mime, m.file_size, "video"
        if is_valid_image(mime, fname):
            return m.file_id, mime, m.file_size, "image"
        return None
    if message.photo:
        m = message.photo
        return m.file_id, "image/jpeg", m.file_size, "image"
    return None


@Client.on_message(
    filters.private & (filters.video | filters.document | filters.photo),
    group=10,
)
async def handle_media(client: Client, message: Message):
    user = message.from_user
    info = _get_media_info(message)
    if not info:
        await message.reply("❌ Unsupported file type. Send a video (MP4/MKV/AVI…) or image (JPG/PNG/WEBP).")
        return

    file_id, mime_type, file_size, ftype = info

    # Size validation
    if file_size and not is_valid_file_size(file_size):
        await message.reply(
            f"❌ File too large! Max allowed: **{human_size(MAX_FILE_SIZE_BYTES)}**\n"
            f"Your file: **{human_size(file_size)}**"
        )
        return

    # Register user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    await db.add_user(user.id, username=user.username or "", full_name=full_name)

    # Add to queue
    job_id = await db.add_job(user_id=user.id, file_id=file_id, file_type=ftype)

    # Count pending ahead
    all_pending = await db.queue_stats()
    pos = all_pending["pending"] + all_pending["processing"]

    emoji = "🎬" if ftype == "video" else "🖼️"
    await message.reply(
        f"{emoji} **Added to queue!**\n\n"
        f"📋 Job ID: `{job_id}`\n"
        f"📍 Queue Position: **#{pos}**\n\n"
        f"Use /status to track progress."
    )
    log.info(f"User {user.id} added job {job_id} (type={ftype}, size={file_size})")
