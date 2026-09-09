"""User authentication and account management service.

Works against either a PostgreSQL pool (asyncpg) or the in-memory store,
selected via the Database wrapper.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import bcrypt
import jwt
from fastapi import HTTPException, status

from backend.config import Settings
from backend.db.database import Database
from backend.models.user import (
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


class UserService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ #
    # Account creation / lookup
    # ------------------------------------------------------------------ #
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        if self.db.is_memory:
            return await self._create_user_memory(user_data)
        return await self._create_user_pg(user_data)

    async def _create_user_memory(self, user_data: UserCreate) -> UserResponse:
        store = self.db.memory
        with store.lock:
            for u in store.users.values():
                if u["username"] == user_data.username or u["email"] == user_data.email:
                    raise HTTPException(status_code=400, detail="Username or email already registered")
            user_id = uuid4()
            now = datetime.now(timezone.utc)
            store.users[str(user_id)] = {
                "id": user_id,
                "username": user_data.username,
                "email": user_data.email,
                "password_hash": _hash_password(user_data.password),
                "full_name": user_data.full_name,
                "created_at": now,
                "last_login": None,
                "is_active": True,
                "is_superuser": False,
            }
            store.preferences[str(user_id)] = {
                "default_provider": "vllm",
                "default_model_params": {"temperature": 0.7, "max_tokens": 4096, "top_p": 0.95},
                "theme": "dark",
                "notifications_enabled": True,
            }
            store.workspaces[str(uuid4())] = {
                "user_id": user_id,
                "name": "default",
                "path": f"/workspace/{user_data.username}",
                "is_default": True,
            }
        return await self.get_user_by_id(user_id)

    async def _create_user_pg(self, user_data: UserCreate) -> UserResponse:
        async with self.db.pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1 OR email = $2",
                user_data.username, user_data.email,
            )
            if existing:
                raise HTTPException(status_code=400, detail="Username or email already registered")
            user_id = uuid4()
            await conn.execute(
                """INSERT INTO users (id, username, email, password_hash, full_name)
                   VALUES ($1, $2, $3, $4, $5)""",
                user_id, user_data.username, user_data.email,
                _hash_password(user_data.password), user_data.full_name,
            )
            await conn.execute("INSERT INTO user_preferences (user_id) VALUES ($1)", user_id)
            await conn.execute(
                """INSERT INTO user_workspaces (user_id, name, path, is_default)
                   VALUES ($1, 'default', $2, TRUE)""",
                user_id, f"/workspace/{user_data.username}",
            )
        return await self.get_user_by_id(user_id)

    async def authenticate_user(self, username: str, password: str) -> Optional[UserResponse]:
        if self.db.is_memory:
            store = self.db.memory
            with store.lock:
                row = next((u for u in store.users.values()
                            if u["username"] == username and u["is_active"]), None)
                if not row or not _verify_password(password, row["password_hash"]):
                    return None
                row["last_login"] = datetime.now(timezone.utc)
                user_id = row["id"]
            return await self.get_user_by_id(user_id)

        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, password_hash FROM users WHERE username = $1 AND is_active = TRUE",
                username,
            )
            if not row or not _verify_password(password, row["password_hash"]):
                return None
            await conn.execute("UPDATE users SET last_login = NOW() WHERE id = $1", row["id"])
            return await self.get_user_by_id(row["id"])

    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        if self.db.is_memory:
            store = self.db.memory
            with store.lock:
                row = store.users.get(str(user_id))
                if not row:
                    return None
                prefs = store.preferences.get(str(user_id))
                workspaces = [
                    {"id": wid, **{k: v for k, v in w.items() if k != "user_id"}}
                    for wid, w in store.workspaces.items()
                    if str(w["user_id"]) == str(user_id)
                ]
                return UserResponse(
                    id=row["id"], username=row["username"], email=row["email"],
                    full_name=row["full_name"], created_at=row["created_at"],
                    last_login=row["last_login"], is_active=row["is_active"],
                    is_superuser=row["is_superuser"], preferences=prefs, workspaces=workspaces,
                )

        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, username, email, full_name, created_at, last_login,
                          is_active, is_superuser FROM users WHERE id = $1""",
                user_id,
            )
            if not row:
                return None
            prefs = await conn.fetchrow("SELECT * FROM user_preferences WHERE user_id = $1", user_id)
            workspaces = await conn.fetch(
                "SELECT id, name, path, is_default FROM user_workspaces WHERE user_id = $1", user_id
            )
            return UserResponse(
                id=row["id"], username=row["username"], email=row["email"],
                full_name=row["full_name"], created_at=row["created_at"],
                last_login=row["last_login"], is_active=row["is_active"],
                is_superuser=row["is_superuser"],
                preferences=dict(prefs) if prefs else None,
                workspaces=[dict(w) for w in workspaces],
            )

    # ------------------------------------------------------------------ #
    # Tokens
    # ------------------------------------------------------------------ #
    def _encode(self, payload: Dict[str, Any]) -> str:
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    async def create_token(self, user_id: UUID) -> TokenResponse:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        now = datetime.now(timezone.utc)
        # A unique jti guarantees distinct tokens even when issued within the
        # same second, avoiding UNIQUE(token) collisions and improving security.
        access_token = self._encode({
            "sub": str(user_id), "username": user.username, "role": "user",
            "jti": str(uuid4()), "iat": now,
            "exp": now + timedelta(seconds=self.settings.access_token_expire_seconds),
        })
        refresh_token = self._encode({
            "sub": str(user_id), "type": "refresh",
            "jti": str(uuid4()), "iat": now,
            "exp": now + timedelta(seconds=self.settings.refresh_token_expire_seconds),
        })
        await self._store_session(user_id, refresh_token, now)
        return TokenResponse(
            access_token=access_token, refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_seconds, user=user,
        )

    async def _store_session(self, user_id: UUID, token: str, now: datetime) -> None:
        expires = now + timedelta(seconds=self.settings.refresh_token_expire_seconds)
        if self.db.is_memory:
            with self.db.memory.lock:
                self.db.memory.sessions[token] = {
                    "user_id": user_id, "token": token,
                    "expires_at": expires, "revoked_at": None,
                }
            return
        async with self.db.pool.acquire() as conn:
            # Compute expiry in the database to avoid tz-aware/naive mismatches
            # with the column type.
            await conn.execute(
                """INSERT INTO user_sessions (user_id, token, expires_at)
                   VALUES ($1, $2, NOW() + make_interval(secs => $3))""",
                user_id, token, float(self.settings.refresh_token_expire_seconds),
            )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        try:
            payload = jwt.decode(
                refresh_token, self.settings.jwt_secret, algorithms=[self.settings.jwt_algorithm]
            )
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        if not await self._session_valid(refresh_token):
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        return await self.create_token(UUID(payload["sub"]))

    async def _session_valid(self, token: str) -> bool:
        now = datetime.now(timezone.utc)
        if self.db.is_memory:
            with self.db.memory.lock:
                s = self.db.memory.sessions.get(token)
                return bool(s and s["revoked_at"] is None and s["expires_at"] > now)
        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id FROM user_sessions
                   WHERE token = $1 AND revoked_at IS NULL AND expires_at > NOW()""",
                token,
            )
            return bool(row)

    async def revoke_token(self, refresh_token: str) -> None:
        if self.db.is_memory:
            with self.db.memory.lock:
                s = self.db.memory.sessions.get(refresh_token)
                if s:
                    s["revoked_at"] = datetime.now(timezone.utc)
            return
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_sessions SET revoked_at = NOW() WHERE token = $1", refresh_token
            )

    # ------------------------------------------------------------------ #
    # Updates
    # ------------------------------------------------------------------ #
    async def update_user(self, user_id: UUID, updates: UserUpdate) -> UserResponse:
        data = updates.model_dump(exclude_unset=True)
        if self.db.is_memory:
            with self.db.memory.lock:
                row = self.db.memory.users.get(str(user_id))
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                if "password" in data:
                    row["password_hash"] = _hash_password(data.pop("password"))
                if "preferences" in data and data["preferences"] is not None:
                    self.db.memory.preferences[str(user_id)] = {
                        **self.db.memory.preferences.get(str(user_id), {}),
                        **data.pop("preferences"),
                    }
                for k in ("full_name", "email"):
                    if k in data and data[k] is not None:
                        row[k] = data[k]
            return await self.get_user_by_id(user_id)

        async with self.db.pool.acquire() as conn:
            if "password" in data and data["password"]:
                await conn.execute(
                    "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
                    _hash_password(data.pop("password")), user_id,
                )
            if "preferences" in data and data["preferences"] is not None:
                prefs = data.pop("preferences")
                await conn.execute(
                    """UPDATE user_preferences
                       SET default_provider = COALESCE($1, default_provider),
                           default_model_params = COALESCE($2, default_model_params),
                           theme = COALESCE($3, theme), updated_at = NOW()
                       WHERE user_id = $4""",
                    prefs.get("default_provider"), prefs.get("default_model_params"),
                    prefs.get("theme"), user_id,
                )
            for field in ("full_name", "email"):
                if field in data and data[field] is not None:
                    await conn.execute(
                        f"UPDATE users SET {field} = $1, updated_at = NOW() WHERE id = $2",
                        data[field], user_id,
                    )
        return await self.get_user_by_id(user_id)
