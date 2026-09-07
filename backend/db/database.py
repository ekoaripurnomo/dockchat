"""Database access layer.

Provides an asyncpg-backed pool when DATABASE_URL is configured, and an
in-memory store fallback otherwise so the app can run for development/demo
without a running PostgreSQL instance.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from backend.config import Settings
from backend.db.memory_store import MemoryStore

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """Thin wrapper exposing either an asyncpg pool or an in-memory store."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool = None  # asyncpg.Pool when using PostgreSQL
        self.memory: Optional[MemoryStore] = None

    @property
    def is_memory(self) -> bool:
        return self.memory is not None

    async def connect(self) -> None:
        if self.settings.use_database:
            import asyncpg  # imported lazily so the app runs without the driver

            self.pool = await asyncpg.create_pool(dsn=self.settings.database_url)
            await self._init_schema()
        else:
            self.memory = MemoryStore()

    async def _init_schema(self) -> None:
        if not self.pool or not SCHEMA_PATH.exists():
            return
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
