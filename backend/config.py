"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "dockchat"
    app_version: str = "2.2.0"
    debug: bool = True

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 3600
    refresh_token_expire_seconds: int = 604800

    # Datastores (optional: empty DATABASE_URL enables in-memory mode)
    database_url: Optional[str] = None
    redis_url: Optional[str] = None

    # AI providers
    vllm_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-14B-Instruct"
    vllm_api_key: Optional[str] = None  # bearer token for secured vLLM endpoints
    vllm_enable_tools: bool = False  # set True only if vLLM launched with tool-calling flags
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # Docker
    docker_host: Optional[str] = None
    allowed_paths: str = "/home:/workspace:/tmp"

    # CORS
    allowed_origins: str = "http://localhost:8501,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_paths_list(self) -> List[str]:
        return [p.strip() for p in self.allowed_paths.split(":") if p.strip()]

    @property
    def use_database(self) -> bool:
        return bool(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
