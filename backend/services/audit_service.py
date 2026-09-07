"""Audit logging service (PostgreSQL or in-memory)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.db.database import Database


class AuditService:
    def __init__(self, db: Database):
        self.db = db

    async def log_action(
        self,
        user_id: UUID,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.db.is_memory:
            with self.db.memory.lock:
                self.db.memory.audit_logs.append({
                    "user_id": user_id, "action": action,
                    "resource_type": resource_type, "resource_id": resource_id,
                    "details": details, "created_at": datetime.now(timezone.utc),
                })
            return
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details)
                   VALUES ($1, $2, $3, $4, $5)""",
                user_id, action, resource_type, resource_id, details,
            )

    async def get_user_logs(self, user_id: UUID, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        if self.db.is_memory:
            with self.db.memory.lock:
                logs = [dict(x) for x in self.db.memory.audit_logs if str(x["user_id"]) == str(user_id)]
            logs.sort(key=lambda x: x["created_at"], reverse=True)
            return logs[offset:offset + limit]
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM audit_logs WHERE user_id = $1
                   ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                user_id, limit, offset,
            )
            return [dict(r) for r in rows]
