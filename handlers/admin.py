"""
handlers/admin.py
Owner-only admin commands: /stats /users /jobs /clearqueue
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from database.db import db
from config import ADMINS
from utils.logger import bot_logger as log

admin_filter = filters.user(ADMINS) & filters.private


@Client.on_message(filters.command("stats") & admin_filter)
async def cmd_stats(client: Client, message: Message):
    stats = await db.queue_stats()
    total_users = await db.total_users()
    text = (
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total Users: **{total_users}**\n\n"
        f"📋 Jobs:\n"
        f"  ⏳ Pending:    **{stats['pending']}**\n"
        f"  ⚙️ Processing: **{stats['processing']}**\n"
        f"  ✅ Completed:  **{stats['completed']}**\n"
        f"  ❌ Failed:     **{stats['failed']}**\n"
        f"  🚫 Cancelled:  **{stats['cancelled']}**\n"
    )
    await message.reply(text)


@Client.on_message(filters.command("users") & admin_filter)
async def cmd_users(client: Client, message: Message):
    total = await db.total_users()
    ids   = await db.all_user_ids()
    ids_preview = ", ".join(str(i) for i in ids[:30])
    if len(ids) > 30:
        ids_preview += f"… (+{len(ids)-30} more)"
    await message.reply(
        f"👥 **Total Users: {total}**\n\nIDs: `{ids_preview}`"
    )


@Client.on_message(filters.command("jobs") & admin_filter)
async def cmd_jobs(client: Client, message: Message):
    stats = await db.queue_stats()
    cur   = stats.get("current_job")
    lines = [
        f"⏳ Pending:    {stats['pending']}",
        f"⚙️ Processing: {stats['processing']}",
        f"✅ Completed:  {stats['completed']}",
        f"❌ Failed:     {stats['failed']}",
        f"🚫 Cancelled:  {stats['cancelled']}",
    ]
    if cur:
        lines.append(f"\nCurrent: Job `{cur['id']}` → User `{cur['user_id']}`")
    await message.reply("📋 **Job Summary**\n\n" + "\n".join(lines))


@Client.on_message(filters.command("clearqueue") & admin_filter)
async def cmd_clearqueue(client: Client, message: Message):
    # Cancel ALL pending jobs (admin action)
    async with db._db.execute(
        "UPDATE jobs SET status='cancelled', finished_at=datetime('now') WHERE status='pending'"
    ) as cur:
        pass
    await db._db.commit()
    await message.reply("✅ All pending jobs cleared from queue.")
