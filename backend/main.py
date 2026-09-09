"""dockchat FastAPI application entrypoint.

Run with:
    uvicorn backend.main:app --reload --port 8080
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.database import Database
from backend.dependencies import app_state
from backend.routes import audit, auth, chat, config as config_routes, docker
from backend.services.ai_provider_manager import AIProviderManager
from backend.services.audit_service import AuditService
from backend.services.chat_service import ChatService
from backend.services.docker_service import DockerService
from backend.services.project_service import ProjectService
from backend.services.user_service import UserService

logger = logging.getLogger("dockchat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app_state.settings = settings

    # Datastore
    db = Database(settings)
    await db.connect()
    app_state.db = db
    logger.info("Database mode: %s", "in-memory" if db.is_memory else "postgresql")

    # Services
    app_state.user_service = UserService(db, settings)
    try:
        await app_state.user_service.ensure_seed_admin()
    except Exception as exc:  # never let a bad seed config crash startup
        logger.warning("Seed admin skipped: %s", exc)
    app_state.audit_service = AuditService(db)

    provider_manager = AIProviderManager(settings)
    provider_manager.bootstrap_from_settings()
    app_state.provider_manager = provider_manager

    docker_service = DockerService(settings)
    docker_service.connect()
    app_state.docker_service = docker_service
    logger.info("Docker available: %s", docker_service.available)

    project_service = ProjectService(settings)
    app_state.project_service = project_service

    app_state.chat_service = ChatService(provider_manager, docker_service, project_service)

    yield

    await db.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(config_routes.router)
    app.include_router(docker.router)
    app.include_router(chat.router)
    app.include_router(audit.router)

    @app.get("/api/health", tags=["health"])
    async def health():
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
        }

    return app


app = create_app()
