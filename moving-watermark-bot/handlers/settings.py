"""
handlers/settings.py
All /setwatermark /setopacity /setsize /setspeed /setmode /setfont /setcolor commands.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

from database.db import db
from utils.validators import (
    sanitize_text, validate_opacity, validate_size,
    validate_speed, validate_font_size,
)
from utils.logger import bot_logger as log

VALID_COLORS = {
    "white", "black", "red", "green", "blue", "yellow",
    "orange", "pink", "purple", "cyan", "gray",
}


@Client.on_message(filters.command("setwatermark") & filters.private)
async def cmd_setwatermark(client: Client, message: Message):
    """
    /setwatermark <text>           → set text watermark
    Send PNG photo with this command → set image watermark
    """
    user_id = message.from_user.id

    # Image watermark: message has a photo or document PNG
    if message.photo or (message.document and
                         message.document.mime_type in ("image/png", "image/webp")):
        fid = (message.photo or message.document).file_id
        await db.set_setting(user_id, "watermark_file_id", fid)
        await db.set_setting(user_id, "watermark_text", "")
        await message.reply("✅ **Image watermark set!** I'll use this PNG for your videos.")
        return

    # Text watermark
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        settings = await db.get_settings(user_id)
        current = settings.get("watermark_text") or settings.get("watermark_file_id") or "Not set"
        await message.reply(
            f"Current watermark: `{current}`\n\n"
            "**Usage:**\n"
            "`/setwatermark YourText`\n"
            "or send a PNG/WEBP image with this caption."
        )
        return

    text = sanitize_text(parts[1])
    if not text:
        await message.reply("❌ Invalid watermark text.")
        return

    await db.set_setting(user_id, "watermark_text", text)
    await db.set_setting(user_id, "watermark_file_id", None)
    await message.reply(f"✅ Watermark text set to: `{text}`")


@Client.on_message(filters.command("setopacity") & filters.private)
async def cmd_setopacity(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        await message.reply(f"Current opacity: `{s['opacity']}`\n\nUsage: `/setopacity 0.7`")
        return
    try:
        val = validate_opacity(float(parts[1]))
    except ValueError:
        await message.reply("❌ Invalid value. Use a number between 0.1 and 1.0")
        return
    await db.set_setting(message.from_user.id, "opacity", val)
    await message.reply(f"✅ Opacity set to `{val}`")


@Client.on_message(filters.command("setsize") & filters.private)
async def cmd_setsize(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        await message.reply(f"Current size: `{s['size']}`\n\nUsage: `/setsize 0.2`\n(fraction of video width, 0.05–0.9)")
        return
    try:
        val = validate_size(float(parts[1]))
    except ValueError:
        await message.reply("❌ Invalid value. Use a number between 0.05 and 0.9")
        return
    await db.set_setting(message.from_user.id, "size", val)
    await message.reply(f"✅ Size set to `{val}`")


@Client.on_message(filters.command("setspeed") & filters.private)
async def cmd_setspeed(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        await message.reply(f"Current speed: `{s['speed']}` px/s\n\nUsage: `/setspeed 80`\n(10–500)")
        return
    try:
        val = validate_speed(float(parts[1]))
    except ValueError:
        await message.reply("❌ Invalid value. Use a number between 10 and 500")
        return
    await db.set_setting(message.from_user.id, "speed", val)
    await message.reply(f"✅ Speed set to `{val}` px/s")


@Client.on_message(filters.command("setmode") & filters.private)
async def cmd_setmode(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        await message.reply(f"Current mode: `{s['mode']}`\n\nUsage: `/setmode moving` or `/setmode static`")
        return
    mode = parts[1].lower().strip()
    if mode not in ("moving", "static"):
        await message.reply("❌ Valid modes: `moving` or `static`")
        return
    await db.set_setting(message.from_user.id, "mode", mode)
    await message.reply(f"✅ Mode set to `{mode}`")


@Client.on_message(filters.command("setfont") & filters.private)
async def cmd_setfont(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        await message.reply(f"Current font size: `{s['font_size']}`\n\nUsage: `/setfont 40`\n(10–200)")
        return
    try:
        val = validate_font_size(int(parts[1]))
    except ValueError:
        await message.reply("❌ Invalid value. Use an integer between 10 and 200")
        return
    await db.set_setting(message.from_user.id, "font_size", val)
    await message.reply(f"✅ Font size set to `{val}`")


@Client.on_message(filters.command("setcolor") & filters.private)
async def cmd_setcolor(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        s = await db.get_settings(message.from_user.id)
        colors = ", ".join(sorted(VALID_COLORS))
        await message.reply(
            f"Current color: `{s['color']}`\n\n"
            f"Available colors: {colors}\n"
            "or use hex: `#FF0000`\n\n"
            "Usage: `/setcolor white`"
        )
        return
    color = parts[1].strip()
    if color not in VALID_COLORS and not color.startswith("#"):
        await message.reply(f"❌ Use a color name or hex code like `#FF0000`")
        return
    await db.set_setting(message.from_user.id, "color", color)
    await message.reply(f"✅ Color set to `{color}`")
