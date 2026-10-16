"""Small durable user registry; no payment or VPN credentials are stored here."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite


@dataclass(frozen=True)
class UserRecord:
    telegram_id: int
    username: str | None
    full_name: str
    created_at: str
    updated_at: str


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        if self._connection is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        try:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.execute("PRAGMA busy_timeout=5000")
            await connection.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            await connection.commit()
        except BaseException:
            await connection.close()
            raise
        self._connection = connection

    def _require_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not initialized")
        return self._connection

    async def upsert_user(self, telegram_id: int, username: str | None, full_name: str) -> None:
        connection = self._require_connection()
        now = datetime.now(UTC).isoformat()
        await connection.execute(
            """INSERT INTO users (telegram_id, username, full_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (telegram_id) DO UPDATE SET
                   username = excluded.username,
                   full_name = excluded.full_name,
                   updated_at = excluded.updated_at""",
            (telegram_id, username, full_name, now, now),
        )
        await connection.commit()

    async def get_user(self, telegram_id: int) -> UserRecord | None:
        async with self._require_connection().execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return UserRecord(**dict(row)) if row else None

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
