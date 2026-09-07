"""Chat routes wiring the LLM to Docker tools."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.dependencies import get_audit_service, get_chat_service, get_current_user
from backend.services.audit_service import AuditService
from backend.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.post("")
async def chat(
    body: ChatMessage,
    current_user: Dict[str, Any] = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    audit: AuditService = Depends(get_audit_service),
):
    result = await chat_service.chat(current_user["user_id"], body.message, body.history)
    await audit.log_action(current_user["user_id"], "chat", "message")
    return result
