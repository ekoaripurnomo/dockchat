"""Chat routes wiring the LLM to Docker tools, with persistent history."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.dependencies import (
    get_audit_service,
    get_chat_history_service,
    get_chat_service,
    get_current_user,
)
from backend.services.audit_service import AuditService
from backend.services.chat_history_service import ChatHistoryService
from backend.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Cap the conversation context sent to the model to bound token usage.
MAX_HISTORY = 50


class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.post("")
async def chat(
    body: ChatMessage,
    current_user: Dict[str, Any] = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    history_service: ChatHistoryService = Depends(get_chat_history_service),
    audit: AuditService = Depends(get_audit_service),
):
    user_id = current_user["user_id"]

    # Persist the user's message before answering.
    await history_service.add_message(user_id, "user", body.message)

    # Prefer stored history as the source of truth; fall back to client-provided.
    stored = await history_service.get_history(user_id, MAX_HISTORY)
    # Exclude the message we just stored (it is passed separately as body.message).
    history = [{"role": m["role"], "content": m["content"]} for m in stored[:-1]][-MAX_HISTORY:]

    result = await chat_service.chat(user_id, body.message, history)

    reply = (result or {}).get("reply") or ""
    if reply:
        await history_service.add_message(user_id, "assistant", reply)

    await audit.log_action(user_id, "chat", "message")
    return result


@router.get("/history")
async def get_history(
    limit: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    history_service: ChatHistoryService = Depends(get_chat_history_service),
):
    """Return the user's chat history (chronological).

    By default returns the full history so the UI can display everything.
    Pass ?limit=N to cap the number of most-recent messages.
    """
    return await history_service.get_history(current_user["user_id"], limit)


@router.delete("/history")
async def clear_history(
    current_user: Dict[str, Any] = Depends(get_current_user),
    history_service: ChatHistoryService = Depends(get_chat_history_service),
):
    await history_service.clear_history(current_user["user_id"])
    return {"message": "Chat history cleared"}
