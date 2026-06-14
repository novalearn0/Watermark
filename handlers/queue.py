"""
handlers/queue.py
/queue, /status, /cancel commands
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from database.db import db, STATUS_PENDING, STATUS_PROCESSING
from utils.logger import bot_logger as log


@Client.on_message(filters.command("queue") & filters.private)
async def cmd_queue(client: Client, message: Message):
    stats = await db.queue_stats()
    user_jobs = await db.user_pending_jobs(message.from_user.id)

    cur = stats.get("current_job")
    cur_txt = "None"
    if cur:
        uid  = cur["user_id"]
        jid  = cur["id"]
        cur_txt = f"Job `{jid}` (User `{uid}`)"

    user_jobs_txt = ""
    if user_jobs:
        lines = [f"  • Job `{j['id']}` — {j['status']}" for j in user_jobs]
        user_jobs_txt = "\n".join(lines)
    else:
        user_jobs_txt = "  (none)"

    text = (
        f"📋 **Queue Status**\n\n"
        f"⚙️ Currently processing: {cur_txt}\n"
        f"⏳ Pending jobs: **{stats['pending']}**\n"
        f"✅ Completed: **{stats['completed']}**\n"
        f"❌ Failed: **{stats['failed']}**\n\n"
        f"**Your jobs:**\n{user_jobs_txt}"
    )
    await message.reply(text)


@Client.on_message(filters.command("status") & filters.private)
async def cmd_status(client: Client, message: Message):
    user_jobs = await db.user_pending_jobs(message.from_user.id)
    stats = await db.queue_stats()

    if not user_jobs:
        await message.reply("ℹ️ You have no active jobs in the queue.")
        return

    lines = []
    for j in user_jobs:
        pos_note = ""
        if j["status"] == STATUS_PROCESSING:
            pos_note = "▶️ Processing now"
        else:
            pos_note = f"Queue position approx. #{j.get('queue_position', '?')}"

        lines.append(
            f"🆔 Job `{j['id']}`\n"
            f"   Status: **{j['status'].upper()}**\n"
            f"   {pos_note}\n"
            f"   Added: `{j['created_at'][:19]}`"
        )

    await message.reply("📊 **Your Jobs:**\n\n" + "\n\n".join(lines))


@Client.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message):
    count = await db.cancel_user_jobs(message.from_user.id)
    if count == 0:
        await message.reply("ℹ️ You have no pending jobs to cancel.")
    else:
        await message.reply(f"✅ Cancelled **{count}** pending job(s).")
