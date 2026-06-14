from pyrogram import Client, filters
from pyrogram.types import Message

from database.db import db
from utils.logger import bot_logger as log

START_TEXT = """
👋 **Welcome to Moving Watermark Bot!**

Send me any **video or image** and I'll apply a moving watermark automatically.

**Commands:**
/help — Show all commands
/status — Your current job status
/queue — View queue info
/cancel — Cancel your pending jobs

**Watermark Settings:**
/setwatermark — Set watermark text or image
/setopacity — Set opacity (0.1–1.0)
/setsize — Set size (0.05–0.9)
/setspeed — Set speed in px/s
/setmode — Set moving or static mode
/setfont — Set font size
/setcolor — Set text color
"""

HELP_TEXT = """
📖 **Bot Help**

**How to use:**
1. Send/forward any video or image
2. Bot queues it automatically
3. Processed file is returned with watermark

**Watermark Modes:**
• `moving` — Watermark bounces around (default)
• `static` — Watermark stays in center

**Commands:**
`/setwatermark <text>` — Set text watermark
or send a PNG image with caption `/setwatermark`

`/setopacity <0.1–1.0>` — e.g. `/setopacity 0.7`
`/setsize <0.05–0.9>` — e.g. `/setsize 0.2`
`/setspeed <10–500>` — e.g. `/setspeed 80`
`/setmode moving|static` — e.g. `/setmode moving`
`/setfont <10–200>` — e.g. `/setfont 40`
`/setcolor <color>` — e.g. `/setcolor white` or `#FF0000`

**Queue:**
`/queue` — See queue status
`/status` — Your job status
`/cancel` — Cancel your pending jobs
"""


@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    user = message.from_user
    await db.add_user(user.id, username=user.username or "", full_name=user.full_name or "")
    await message.reply(START_TEXT)


@Client.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, message: Message):
    await message.reply(HELP_TEXT)
