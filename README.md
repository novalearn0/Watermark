# 🎬 Moving Watermark Bot

A Telegram bot that applies a **moving/bouncing watermark** to videos and images using FFmpeg.

## ✨ Features

- ✅ Moving watermark that bounces across the video (FFmpeg expressions — no frame-by-frame Python)
- ✅ Text watermark or PNG image watermark
- ✅ Supports videos up to **1GB**
- ✅ Files downloaded directly to disk — never loaded into RAM
- ✅ **FIFO queue** — multiple videos processed one at a time
- ✅ Queue **persists in SQLite** — survives bot restarts
- ✅ Per-user settings: opacity, size, speed, color, font size, mode
- ✅ Progress updates: 10%, 20%, … 100%
- ✅ Admin commands: /stats /users /jobs /clearqueue
- ✅ Deploy-ready: Render.com + Docker

---

## 🚀 Quick Deploy to Render

1. Fork this repo on GitHub
2. Go to [render.com](https://render.com) → New → Web Service → Connect repo
3. Render auto-detects `render.yaml`
4. Set these Environment Variables in Render dashboard:
   - `BOT_TOKEN` — from @BotFather
   - `API_ID` — from https://my.telegram.org
   - `API_HASH` — from https://my.telegram.org
   - `ADMINS` — your Telegram user ID
5. Deploy!

---

## 🐳 Local Docker Run

```bash
cp .env.example .env
# Edit .env with your values

docker build -t watermark-bot .
docker run --env-file .env watermark-bot
```

---

## 💻 Local Development

```bash
pip install -r requirements.txt
# Install FFmpeg: https://ffmpeg.org/download.html

cp .env.example .env
# Edit .env

python3 bot.py
```

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Full help |
| `/status` | Your job status |
| `/queue` | Queue overview |
| `/cancel` | Cancel your pending jobs |
| `/setwatermark <text>` | Set text watermark (or send PNG) |
| `/setopacity <0.1–1.0>` | Set watermark opacity |
| `/setsize <0.05–0.9>` | Set watermark size |
| `/setspeed <10–500>` | Set movement speed (px/s) |
| `/setmode moving\|static` | Set watermark mode |
| `/setfont <10–200>` | Set font size |
| `/setcolor <color>` | Set watermark color |

**Admin only:**

| Command | Description |
|---------|-------------|
| `/stats` | Bot statistics |
| `/users` | Total users |
| `/jobs` | Job summary |
| `/clearqueue` | Clear all pending jobs |

---

## 🗂 Project Structure

```
moving-watermark-bot/
├── bot.py               # Main entry point
├── config.py            # All configuration
├── queue_manager.py     # FIFO queue processor
├── database/
│   └── db.py            # SQLite (aiosqlite)
├── handlers/
│   ├── start.py         # /start /help
│   ├── media.py         # Incoming video/image
│   ├── settings.py      # /set* commands
│   ├── queue.py         # /queue /status /cancel
│   └── admin.py         # Admin commands
├── services/
│   ├── ffmpeg_service.py  # FFmpeg watermark engine
│   ├── image_service.py   # Watermark PNG download/cache
│   └── telegram_service.py # Safe send/edit helpers
├── utils/
│   ├── logger.py        # Rotating logs
│   ├── validators.py    # Input validation
│   └── helpers.py       # Temp files, subprocess
├── Dockerfile
├── render.yaml
├── requirements.txt
└── .env.example
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | required | Telegram bot token |
| `API_ID` | required | Telegram API ID |
| `API_HASH` | required | Telegram API hash |
| `ADMINS` | required | Comma-separated admin IDs |
| `DATABASE_PATH` | `watermark_bot.db` | SQLite file path |
| `TEMP_DIR` | `temp` | Temp file directory |
| `MAX_FILE_SIZE_GB` | `1` | Max upload size in GB |
| `DEFAULT_WATERMARK_TEXT` | `@YourChannel` | Default watermark text |
| `DEFAULT_OPACITY` | `0.7` | Default opacity |
| `DEFAULT_SIZE` | `0.2` | Default size (fraction of width) |
| `DEFAULT_SPEED` | `80` | Default speed (px/s) |
| `DEFAULT_MODE` | `moving` | Default mode |

---

## 📝 Notes

- FFmpeg must be installed (included in Docker image automatically)
- Render **Standard plan** recommended (2GB RAM)
- SQLite DB is at `/tmp/` on Render (resets on redeploy — acceptable for queue)
- For permanent DB, mount a Render Disk or use Turso/LibSQL
