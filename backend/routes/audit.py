"""Audit log routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.dependencies import get_audit_service, get_current_user
from backend.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
async def get_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
):
    return await audit.get_user_logs(current_user["user_id"], limit, offset)
