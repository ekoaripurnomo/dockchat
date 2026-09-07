"""Pydantic models for users, auth tokens and preferences."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Username must be alphanumeric or contain underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_superuser: bool = False
    preferences: Optional[Dict[str, Any]] = None
    workspaces: Optional[List[Dict[str, Any]]] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str
