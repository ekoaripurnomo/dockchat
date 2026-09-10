"""Shared application state and FastAPI dependency providers.

Services are constructed once at startup (see main.lifespan) and stored on
this module-level container so route dependencies can retrieve them.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings
from backend.db.database import Database
from backend.services.ai_provider_manager import AIProviderManager
from backend.services.audit_service import AuditService
from backend.services.chat_history_service import ChatHistoryService
from backend.services.chat_service import ChatService
from backend.services.docker_service import DockerService
from backend.services.project_service import ProjectService
from backend.services.user_service import UserService


class AppState:
    """Container for singletons initialised during app startup."""

    settings: Settings
    db: Database
    user_service: UserService
    audit_service: AuditService
    provider_manager: AIProviderManager
    docker_service: DockerService
    project_service: ProjectService
    chat_service: ChatService
    chat_history_service: ChatHistoryService


app_state = AppState()

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Database:
    return app_state.db


def get_user_service() -> UserService:
    return app_state.user_service


def get_audit_service() -> AuditService:
    return app_state.audit_service


def get_provider_manager() -> AIProviderManager:
    return app_state.provider_manager


def get_docker_service() -> DockerService:
    return app_state.docker_service


def get_project_service() -> ProjectService:
    return app_state.project_service


def get_chat_service() -> ChatService:
    return app_state.chat_service


def get_chat_history_service() -> ChatHistoryService:
    return app_state.chat_history_service


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Validate the bearer access token and return the authenticated user claims."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh token cannot be used for access")
    return {
        "user_id": UUID(payload["sub"]),
        "username": payload.get("username"),
        "role": payload.get("role", "user"),
    }


async def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
