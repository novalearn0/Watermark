"""
database/db.py
SQLite-based persistent storage for queue jobs and user settings.
Uses aiosqlite for async access.
"""
import asyncio
import datetime
import json
import os
from typing import Optional

import aiosqlite

from config import DATABASE_PATH, DEFAULT_WATERMARK_TEXT, DEFAULT_OPACITY, DEFAULT_SIZE
from config import DEFAULT_SPEED, DEFAULT_FONT_SIZE, DEFAULT_COLOR, DEFAULT_MODE

# ── Status constants ───────────────────────────────────────────────────────
STATUS_PENDING    = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED  = "completed"
STATUS_FAILED     = "failed"
STATUS_CANCELLED  = "cancelled"


class Database:
    def __init__(self, path: str = DATABASE_PATH):
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        if self._db:
            await self._db.close()

    async def _create_tables(self):
        await self._db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            file_id         TEXT NOT NULL,
            file_path       TEXT,
            output_path     TEXT,
            file_type       TEXT NOT NULL DEFAULT 'video',
            status          TEXT NOT NULL DEFAULT 'pending',
            queue_position  INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            started_at      TEXT,
            finished_at     TEXT,
            error_msg       TEXT
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id         INTEGER PRIMARY KEY,
            watermark_text  TEXT,
            watermark_file_id TEXT,
            opacity         REAL    NOT NULL DEFAULT 0.7,
            size            REAL    NOT NULL DEFAULT 0.2,
            speed           REAL    NOT NULL DEFAULT 80.0,
            font_size       INTEGER NOT NULL DEFAULT 40,
            color           TEXT    NOT NULL DEFAULT 'white',
            mode            TEXT    NOT NULL DEFAULT 'moving',
            updated_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            full_name       TEXT,
            created_at      TEXT NOT NULL
        );
        """)
        await self._db.commit()

    # ═══════════════════════════════════ USERS ═══════════════════════════════
    async def add_user(self, user_id: int, username: str = "", full_name: str = ""):
        now = _now()
        await self._db.execute(
            """INSERT INTO users (user_id, username, full_name, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
            (user_id, username, full_name, now),
        )
        await self._db.commit()

    async def total_users(self) -> int:
        async with self._db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    async def all_user_ids(self) -> list[int]:
        async with self._db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    # ═══════════════════════════════════ SETTINGS ═════════════════════════════
    async def get_settings(self, user_id: int) -> dict:
        async with self._db.execute(
            "SELECT * FROM user_settings WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            return dict(row)
        # Return defaults
        return {
            "user_id": user_id,
            "watermark_text": DEFAULT_WATERMARK_TEXT,
            "watermark_file_id": None,
            "opacity": DEFAULT_OPACITY,
            "size": DEFAULT_SIZE,
            "speed": DEFAULT_SPEED,
            "font_size": DEFAULT_FONT_SIZE,
            "color": DEFAULT_COLOR,
            "mode": DEFAULT_MODE,
        }

    async def set_setting(self, user_id: int, key: str, value):
        now = _now()
        # Ensure row exists
        await self._db.execute(
            """INSERT INTO user_settings (user_id, watermark_text, opacity, size, speed, font_size, color, mode, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id) DO NOTHING""",
            (
                user_id,
                DEFAULT_WATERMARK_TEXT, DEFAULT_OPACITY, DEFAULT_SIZE,
                DEFAULT_SPEED, DEFAULT_FONT_SIZE, DEFAULT_COLOR, DEFAULT_MODE,
                now,
            ),
        )
        await self._db.execute(
            f"UPDATE user_settings SET {key}=?, updated_at=? WHERE user_id=?",
            (value, now, user_id),
        )
        await self._db.commit()

    # ═══════════════════════════════════ JOBS ════════════════════════════════
    async def add_job(self, user_id: int, file_id: str, file_type: str = "video") -> int:
        now = _now()
        # Get next position
        async with self._db.execute(
            "SELECT COALESCE(MAX(queue_position),0)+1 FROM jobs WHERE status=?",
            (STATUS_PENDING,),
        ) as cur:
            row = await cur.fetchone()
            pos = row[0] if row else 1

        async with self._db.execute(
            """INSERT INTO jobs (user_id, file_id, file_type, status, queue_position, created_at)
               VALUES (?,?,?,?,?,?)""",
            (user_id, file_id, file_type, STATUS_PENDING, pos, now),
        ) as cur:
            job_id = cur.lastrowid
        await self._db.commit()
        return job_id

    async def get_job(self, job_id: int) -> Optional[dict]:
        async with self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def next_pending_job(self) -> Optional[dict]:
        async with self._db.execute(
            "SELECT * FROM jobs WHERE status=? ORDER BY queue_position ASC, id ASC LIMIT 1",
            (STATUS_PENDING,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def update_job_status(self, job_id: int, status: str, **kwargs):
        now = _now()
        sets = ["status=?"]
        vals = [status]
        if status == STATUS_PROCESSING:
            sets.append("started_at=?"); vals.append(now)
        if status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
            sets.append("finished_at=?"); vals.append(now)
        for k, v in kwargs.items():
            sets.append(f"{k}=?"); vals.append(v)
        vals.append(job_id)
        await self._db.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", vals
        )
        await self._db.commit()

    async def cancel_user_jobs(self, user_id: int) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status=?",
            (user_id, STATUS_PENDING),
        ) as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
        await self._db.execute(
            "UPDATE jobs SET status=?, finished_at=? WHERE user_id=? AND status=?",
            (STATUS_CANCELLED, _now(), user_id, STATUS_PENDING),
        )
        await self._db.commit()
        return count

    async def user_pending_jobs(self, user_id: int) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM jobs WHERE user_id=? AND status IN (?,?) ORDER BY queue_position ASC",
            (user_id, STATUS_PENDING, STATUS_PROCESSING),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def queue_stats(self) -> dict:
        async with self._db.execute(
            "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
        ) as cur:
            rows = await cur.fetchall()
        stats = {r["status"]: r["cnt"] for r in rows}

        async with self._db.execute(
            "SELECT * FROM jobs WHERE status=? LIMIT 1", (STATUS_PROCESSING,)
        ) as cur:
            current = await cur.fetchone()

        return {
            "pending": stats.get(STATUS_PENDING, 0),
            "processing": stats.get(STATUS_PROCESSING, 0),
            "completed": stats.get(STATUS_COMPLETED, 0),
            "failed": stats.get(STATUS_FAILED, 0),
            "cancelled": stats.get(STATUS_CANCELLED, 0),
            "current_job": dict(current) if current else None,
        }

    async def restore_stuck_jobs(self):
        """On startup, reset any 'processing' jobs back to 'pending'."""
        await self._db.execute(
            "UPDATE jobs SET status=? WHERE status=?",
            (STATUS_PENDING, STATUS_PROCESSING),
        )
        await self._db.commit()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


# Singleton
db = Database()
