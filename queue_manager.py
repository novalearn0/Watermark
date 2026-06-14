"""
queue_manager.py

FIFO queue processor.
- Only ONE FFmpeg process runs at a time.
- Queue persists in SQLite; survives bot restarts.
- Progress updates are sent to the user via Telegram.
"""
import asyncio
import os
from typing import Optional

from pyrogram import Client

from database.db import db, STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED
from services.ffmpeg_service import apply_watermark_video, apply_watermark_image
from services.image_service import download_watermark_image
from services.telegram_service import (
    safe_send_message, safe_edit_message,
    send_video_file, send_photo_file, send_document_file,
)
from utils.helpers import make_temp_path, safe_delete
from utils.logger import queue_logger as log
from config import TEMP_DIR

os.makedirs(TEMP_DIR, exist_ok=True)

_processing = False
_queue_task: Optional[asyncio.Task] = None
_client_ref: Optional[Client] = None


def start_queue(client: Client):
    global _queue_task, _client_ref
    _client_ref = client
    if _queue_task is None or _queue_task.done():
        _queue_task = asyncio.create_task(_queue_loop())
        log.info("Queue loop started.")


async def _queue_loop():
    """Continuously pick next pending job and process it."""
    global _processing
    while True:
        try:
            job = await db.next_pending_job()
            if job:
                _processing = True
                await _process_job(job)
                _processing = False
            else:
                await asyncio.sleep(2)
        except Exception as ex:
            log.error(f"Queue loop error: {ex}", exc_info=True)
            _processing = False
            await asyncio.sleep(5)


async def _process_job(job: dict):
    job_id  = job["id"]
    user_id = job["user_id"]
    file_id = job["file_id"]
    ftype   = job.get("file_type", "video")

    log.info(f"Processing job {job_id} for user {user_id}, type={ftype}")

    # Mark processing
    await db.update_job_status(job_id, STATUS_PROCESSING)

    # Status message to user
    status_msg = await safe_send_message(
        _client_ref, user_id,
        f"⚙️ **Processing started!**\nJob ID: `{job_id}`",
    )

    input_path  = None
    output_path = None

    try:
        # ── Download media ─────────────────────────────────────────────────
        suffix = ".mp4" if ftype == "video" else ".jpg"
        input_path = make_temp_path(suffix)

        if status_msg:
            await safe_edit_message(status_msg, "📥 Downloading your file…")

        dl_path = await _client_ref.download_media(file_id, file_name=input_path)
        if not dl_path or not os.path.exists(dl_path):
            raise RuntimeError("Download failed or file missing.")

        input_path = dl_path

        # ── Load user settings ─────────────────────────────────────────────
        settings = await db.get_settings(user_id)

        # If user has a watermark image, download it
        wm_file_id = settings.get("watermark_file_id")
        if wm_file_id:
            wm_path = await download_watermark_image(_client_ref, wm_file_id)
            settings["watermark_file_id"] = wm_path  # replace id with local path

        # ── Apply watermark ────────────────────────────────────────────────
        if ftype == "video":
            output_path = make_temp_path(".mp4")

            async def progress_cb(pct: float):
                if status_msg:
                    bar = _make_bar(pct)
                    await safe_edit_message(
                        status_msg,
                        f"⚙️ **Processing…**\n{bar} {pct:.0f}%",
                    )

            await apply_watermark_video(input_path, output_path, settings, progress_cb)

        else:
            output_path = make_temp_path(".jpg")
            await apply_watermark_image(input_path, output_path, settings)

        # ── Upload result ──────────────────────────────────────────────────
        if status_msg:
            await safe_edit_message(status_msg, "📤 Uploading result…")

        if ftype == "video":
            ok = await send_video_file(
                _client_ref, user_id, output_path,
                caption="✅ Watermark applied!",
            )
        else:
            ok = await send_photo_file(
                _client_ref, user_id, output_path,
                caption="✅ Watermark applied!",
            )

        if ok:
            await db.update_job_status(job_id, STATUS_COMPLETED, output_path=output_path)
            if status_msg:
                await safe_edit_message(status_msg, f"✅ **Done!** Job `{job_id}` completed.")
        else:
            raise RuntimeError("Upload failed.")

    except Exception as ex:
        log.error(f"Job {job_id} failed: {ex}", exc_info=True)
        await db.update_job_status(job_id, STATUS_FAILED, error_msg=str(ex)[:500])
        err_text = f"❌ **Job `{job_id}` failed!**\n\n`{str(ex)[:300]}`"
        if status_msg:
            await safe_edit_message(status_msg, err_text)
        else:
            await safe_send_message(_client_ref, user_id, err_text)

    finally:
        safe_delete(input_path, output_path)


def _make_bar(pct: float, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def is_processing() -> bool:
    return _processing
