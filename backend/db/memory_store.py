"""In-memory data store used when no PostgreSQL DATABASE_URL is configured.

This keeps dockchat runnable for local development and demos without external
infrastructure. Data is not persisted across restarts.
"""
from __future__ import annotations

import threading
from typing import Dict, List


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.users: Dict[str, dict] = {}          # user_id -> user row
        self.preferences: Dict[str, dict] = {}     # user_id -> prefs row
        self.workspaces: Dict[str, dict] = {}      # workspace_id -> row
        self.sessions: Dict[str, dict] = {}        # token -> session row
        self.containers: Dict[str, dict] = {}      # id -> row
        self.projects: Dict[str, dict] = {}        # id -> row
        self.audit_logs: List[dict] = []

    @property
    def lock(self) -> threading.RLock:
        return self._lock
