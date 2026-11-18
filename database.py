"""
Асинхронная работа с базой данных SQLite (через aiosqlite).

Таблицы:
    users         — пользователи бота
    appeals       — обращения: предложения (type='suggestion') и жалобы (type='problem')
    responses     — ответы администрации на обращения
    polls         — голосования
    poll_options  — варианты ответов
    votes         — голоса (PRIMARY KEY (poll_id, user_id) защищает от повторного голосования)
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,               -- Telegram ID
    username    TEXT,
    full_name   TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appeals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('suggestion', 'problem')),
    category    TEXT,
    text        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'progress', 'resolved')),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_appeals_user   ON appeals(user_id);
CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status);
CREATE INDEX IF NOT EXISTS idx_appeals_type   ON appeals(type);

CREATE TABLE IF NOT EXISTS responses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    appeal_id   INTEGER NOT NULL REFERENCES appeals(id) ON DELETE CASCADE,
    admin_id    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_responses_appeal ON responses(appeal_id);

CREATE TABLE IF NOT EXISTS polls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_by  INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at   TEXT
);

CREATE TABLE IF NOT EXISTS poll_options (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    position    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_options_poll ON poll_options(poll_id);

CREATE TABLE IF NOT EXISTS votes (
    poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (poll_id, user_id)                  -- один голос на пользователя в опросе
);
"""


class VoteResult(Enum):
    """Результат попытки проголосовать."""

    OK = "ok"
    ALREADY_VOTED = "already_voted"
    POLL_CLOSED = "poll_closed"
    NOT_FOUND = "not_found"


class Database:
    """Обёртка над SQLite. Каждая операция открывает короткое соединение."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # ── Служебные методы ─────────────────────────────────────────────
    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self.path)
        try:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            await conn.close()

    async def init(self) -> None:
        """Создаёт папку и таблицы, если их ещё нет."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as conn:
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.executescript(SCHEMA)
            await conn.commit()
        logger.info("База данных готова: %s", self.path)

    async def _fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        async with self.connect() as conn:
            cur = await conn.execute(sql, tuple(params))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        async with self.connect() as conn:
            cur = await conn.execute(sql, tuple(params))
            return [dict(r) for r in await cur.fetchall()]

    async def _scalar(self, sql: str, params: Iterable[Any] = ()) -> int:
        row = await self._fetchone(sql, params)
        if not row:
            return 0
        return int(next(iter(row.values())) or 0)

    async def _execute(self, sql: str, params: Iterable[Any] = ()) -> tuple[int, int]:
        """Выполняет запрос на изменение. Возвращает (lastrowid, rowcount)."""
        async with self.connect() as conn:
            cur = await conn.execute(sql, tuple(params))
            await conn.commit()
            return cur.lastrowid or 0, cur.rowcount

    # ── Пользователи ─────────────────────────────────────────────────
    async def upsert_user(self, user_id: int, username: str | None, full_name: str | None) -> None:
        await self._execute(
            """
            INSERT INTO users (id, username, full_name) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name,
                last_seen = CURRENT_TIMESTAMP
            """,
            (user_id, username, full_name),
        )

    async def get_all_user_ids(self) -> list[int]:
        rows = await self._fetchall("SELECT id FROM users ORDER BY id")
        return [r["id"] for r in rows]

    # ── Обращения ────────────────────────────────────────────────────
    async def create_appeal(
        self, user_id: int, appeal_type: str, text: str, category: str | None = None
    ) -> int:
        appeal_id, _ = await self._execute(
            "INSERT INTO appeals (user_id, type, category, text) VALUES (?, ?, ?, ?)",
            (user_id, appeal_type, category, text),
        )
        return appeal_id

    async def count_recent_appeals(self, user_id: int, hours: int = 24) -> int:
        """Сколько обращений пользователь отправил за последние N часов (антиспам)."""
        return await self._scalar(
            "SELECT COUNT(*) FROM appeals WHERE user_id = ? AND created_at >= datetime('now', ?)",
            (user_id, f"-{hours} hours"),
        )

    async def get_appeal(self, appeal_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            SELECT a.*, u.username, u.full_name
            FROM appeals a LEFT JOIN users u ON u.id = a.user_id
            WHERE a.id = ?
            """,
            (appeal_id,),
        )

    async def list_user_appeals(self, user_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM appeals WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )

    async def count_user_appeals(self, user_id: int) -> int:
        return await self._scalar("SELECT COUNT(*) FROM appeals WHERE user_id = ?", (user_id,))

    @staticmethod
    def _appeal_filters(appeal_type: str | None, status: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if appeal_type:
            clauses.append("type = ?")
            params.append(appeal_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    async def list_appeals(
        self, appeal_type: str | None, status: str | None, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        where, params = self._appeal_filters(appeal_type, status)
        return await self._fetchall(
            f"SELECT * FROM appeals {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )

    async def count_appeals(self, appeal_type: str | None, status: str | None) -> int:
        where, params = self._appeal_filters(appeal_type, status)
        return await self._scalar(f"SELECT COUNT(*) FROM appeals {where}", params)

    async def update_appeal_status(self, appeal_id: int, status: str) -> bool:
        _, count = await self._execute(
            "UPDATE appeals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, appeal_id),
        )
        return count > 0

    async def delete_appeal(self, appeal_id: int) -> bool:
        _, count = await self._execute("DELETE FROM appeals WHERE id = ?", (appeal_id,))
        return count > 0

    # ── Ответы администрации ─────────────────────────────────────────
    async def add_response(self, appeal_id: int, admin_id: int, text: str) -> int:
        async with self.connect() as conn:
            cur = await conn.execute(
                "INSERT INTO responses (appeal_id, admin_id, text) VALUES (?, ?, ?)",
                (appeal_id, admin_id, text),
            )
            await conn.execute(
                "UPDATE appeals SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (appeal_id,)
            )
            await conn.commit()
            return cur.lastrowid or 0

    async def get_responses(self, appeal_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM responses WHERE appeal_id = ? ORDER BY id", (appeal_id,)
        )

    # ── Голосования ──────────────────────────────────────────────────
    async def create_poll(self, question: str, options: list[str], created_by: int) -> int:
        """Создаёт опрос с вариантами в одной транзакции."""
        async with self.connect() as conn:
            cur = await conn.execute(
                "INSERT INTO polls (question, created_by) VALUES (?, ?)", (question, created_by)
            )
            poll_id = cur.lastrowid
            await conn.executemany(
                "INSERT INTO poll_options (poll_id, text, position) VALUES (?, ?, ?)",
                [(poll_id, text, pos) for pos, text in enumerate(options)],
            )
            await conn.commit()
            return int(poll_id)

    async def get_poll(self, poll_id: int) -> dict[str, Any] | None:
        return await self._fetchone("SELECT * FROM polls WHERE id = ?", (poll_id,))

    async def get_poll_options(self, poll_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM poll_options WHERE poll_id = ? ORDER BY position", (poll_id,)
        )

    async def list_polls(self, active: bool | None = None, limit: int = 50) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if active is not None:
            where = "WHERE p.is_active = ?"
            params.append(1 if active else 0)
        return await self._fetchall(
            f"""
            SELECT p.*, (SELECT COUNT(*) FROM votes v WHERE v.poll_id = p.id) AS votes
            FROM polls p {where}
            ORDER BY p.is_active DESC, p.id DESC
            LIMIT ?
            """,
            (*params, limit),
        )

    async def set_poll_active(self, poll_id: int, active: bool) -> bool:
        _, count = await self._execute(
            """
            UPDATE polls
            SET is_active = ?, closed_at = CASE WHEN ? THEN NULL ELSE CURRENT_TIMESTAMP END
            WHERE id = ?
            """,
            (1 if active else 0, 1 if active else 0, poll_id),
        )
        return count > 0

    async def delete_poll(self, poll_id: int) -> bool:
        _, count = await self._execute("DELETE FROM polls WHERE id = ?", (poll_id,))
        return count > 0

    async def add_vote(self, poll_id: int, user_id: int, option_id: int) -> VoteResult:
        """Сохраняет голос. Повторный голос в том же опросе отклоняется."""
        async with self.connect() as conn:
            cur = await conn.execute("SELECT is_active FROM polls WHERE id = ?", (poll_id,))
            poll = await cur.fetchone()
            if poll is None:
                return VoteResult.NOT_FOUND
            if not poll["is_active"]:
                return VoteResult.POLL_CLOSED

            cur = await conn.execute(
                "SELECT 1 FROM poll_options WHERE id = ? AND poll_id = ?", (option_id, poll_id)
            )
            if await cur.fetchone() is None:
                return VoteResult.NOT_FOUND

            try:
                await conn.execute(
                    "INSERT INTO votes (poll_id, user_id, option_id) VALUES (?, ?, ?)",
                    (poll_id, user_id, option_id),
                )
                await conn.commit()
            except sqlite3.IntegrityError:
                # Нарушен PRIMARY KEY (poll_id, user_id) — пользователь уже голосовал
                return VoteResult.ALREADY_VOTED
            return VoteResult.OK

    async def get_user_vote(self, poll_id: int, user_id: int) -> int | None:
        row = await self._fetchone(
            "SELECT option_id FROM votes WHERE poll_id = ? AND user_id = ?", (poll_id, user_id)
        )
        return row["option_id"] if row else None

    async def get_poll_results(self, poll_id: int) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            SELECT o.id, o.text, COUNT(v.user_id) AS votes
            FROM poll_options o
            LEFT JOIN votes v ON v.option_id = o.id
            WHERE o.poll_id = ?
            GROUP BY o.id
            ORDER BY o.position
            """,
            (poll_id,),
        )

    # ── Статистика ───────────────────────────────────────────────────
    async def get_stats(self) -> dict[str, Any]:
        """Агрегированная статистика (без каких-либо личных данных)."""
        by_type = await self._fetchall("SELECT type, COUNT(*) AS c FROM appeals GROUP BY type")
        by_status = await self._fetchall("SELECT status, COUNT(*) AS c FROM appeals GROUP BY status")
        by_category = await self._fetchall(
            "SELECT category, COUNT(*) AS c FROM appeals WHERE type = 'problem' GROUP BY category"
        )
        return {
            "users": await self._scalar("SELECT COUNT(*) FROM users"),
            "appeals_total": await self._scalar("SELECT COUNT(*) FROM appeals"),
            "appeals_today": await self._scalar(
                "SELECT COUNT(*) FROM appeals WHERE date(created_at) = date('now')"
            ),
            "appeals_week": await self._scalar(
                "SELECT COUNT(*) FROM appeals WHERE created_at >= datetime('now', '-7 days')"
            ),
            "by_type": {r["type"]: r["c"] for r in by_type},
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_category": {r["category"]: r["c"] for r in by_category},
            "responses": await self._scalar("SELECT COUNT(*) FROM responses"),
            "polls_total": await self._scalar("SELECT COUNT(*) FROM polls"),
            "polls_active": await self._scalar("SELECT COUNT(*) FROM polls WHERE is_active = 1"),
            "votes_total": await self._scalar("SELECT COUNT(*) FROM votes"),
        }
