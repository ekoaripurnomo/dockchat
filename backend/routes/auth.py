"""Authentication and account routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_current_user, get_user_service
from backend.models.user import (
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from backend.services.user_service import UserService

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service),
):
    user = await user_service.create_user(user_data)
    return await user_service.create_token(user.id)


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    user_service: UserService = Depends(get_user_service),
):
    user = await user_service.authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await user_service.create_token(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.refresh_token(body.refresh_token)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    user_service: UserService = Depends(get_user_service),
):
    await user_service.revoke_token(body.refresh_token)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    user = await user_service.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    updates: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.update_user(current_user["user_id"], updates)
