"""Persistent per-user chat history (PostgreSQL or in-memory).

Mirrors the AuditService pattern: branch on db.is_memory, use the memory lock
for the in-memory path, and plain parameters for the postgres path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from backend.db.database import Database


class ChatHistoryService:
    def __init__(self, db: Database):
        self.db = db

    async def add_message(self, user_id: UUID, role: str, content: str) -> None:
        if self.db.is_memory:
            with self.db.memory.lock:
                self.db.memory.chat_messages.append({
                    "id": uuid4(), "user_id": user_id, "role": role,
                    "content": content, "created_at": datetime.now(timezone.utc),
                })
            return
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages (user_id, role, content) VALUES ($1, $2, $3)",
                user_id, role, content,
            )

    async def get_history(
        self, user_id: UUID, limit: Optional[int] = 50
    ) -> List[Dict[str, Any]]:
        """Return chat messages in chronological order.

        limit=None returns the entire history; otherwise the most recent
        `limit` messages.
        """
        if self.db.is_memory:
            with self.db.memory.lock:
                rows = [
                    {"role": m["role"], "content": m["content"],
                     "created_at": m["created_at"].isoformat()}
                    for m in self.db.memory.chat_messages
                    if str(m["user_id"]) == str(user_id)
                ]
            return rows if limit is None else rows[-limit:]
        async with self.db.pool.acquire() as conn:
            if limit is None:
                rows = await conn.fetch(
                    """SELECT role, content, created_at FROM chat_messages
                       WHERE user_id = $1 ORDER BY created_at ASC""",
                    user_id,
                )
                return [
                    {"role": r["role"], "content": r["content"],
                     "created_at": r["created_at"].isoformat()}
                    for r in rows
                ]
            rows = await conn.fetch(
                """SELECT role, content, created_at FROM chat_messages
                   WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2""",
                user_id, limit,
            )
            # Fetched newest-first; return chronological (oldest-first).
            return [
                {"role": r["role"], "content": r["content"],
                 "created_at": r["created_at"].isoformat()}
                for r in reversed(rows)
            ]

    async def clear_history(self, user_id: UUID) -> None:
        if self.db.is_memory:
            with self.db.memory.lock:
                self.db.memory.chat_messages = [
                    m for m in self.db.memory.chat_messages
                    if str(m["user_id"]) != str(user_id)
                ]
            return
        async with self.db.pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_messages WHERE user_id = $1", user_id)
