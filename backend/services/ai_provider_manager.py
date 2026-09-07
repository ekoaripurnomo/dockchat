"""Manages AI provider configurations and clients.

Supports vLLM (OpenAI-compatible), OpenAI and Anthropic. Providers can be
registered globally or per-user, and switched at runtime. Clients are created
lazily and cached.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from backend.config import Settings
from backend.models.providers import AIProviderConfig, ProviderType


class AIProviderManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.global_providers: Dict[str, AIProviderConfig] = {}
        self.user_providers: Dict[str, Dict[str, AIProviderConfig]] = {}
        self.clients: Dict[str, Any] = {}
        self.active_providers: Dict[Optional[str], str] = {}
        self._lock = asyncio.Lock()

    def bootstrap_from_settings(self) -> None:
        """Register the default providers based on environment configuration."""
        vllm = AIProviderConfig(
            provider_type=ProviderType.VLLM, name="vllm", model=self.settings.vllm_model,
            base_url=self.settings.vllm_url, api_key=self.settings.vllm_api_key, is_default=True,
        )
        self.register_provider(vllm)

        if self.settings.openai_api_key:
            self.register_provider(AIProviderConfig(
                provider_type=ProviderType.OPENAI, name="openai",
                model=self.settings.openai_model, api_key=self.settings.openai_api_key,
            ))
        if self.settings.anthropic_api_key:
            self.register_provider(AIProviderConfig(
                provider_type=ProviderType.ANTHROPIC, name="anthropic",
                model=self.settings.anthropic_model, api_key=self.settings.anthropic_api_key,
            ))

    def register_provider(self, config: AIProviderConfig, user_id: Optional[str] = None) -> None:
        if user_id:
            self.user_providers.setdefault(user_id, {})[config.name] = config
            if config.is_default:
                self.active_providers[user_id] = config.name
        else:
            self.global_providers[config.name] = config
            if config.is_default and None not in self.active_providers:
                self.active_providers[None] = config.name

    def get_provider(self, name: str, user_id: Optional[str] = None) -> Optional[AIProviderConfig]:
        if user_id and user_id in self.user_providers and name in self.user_providers[user_id]:
            return self.user_providers[user_id][name]
        return self.global_providers.get(name)

    def list_providers(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        providers = [self._format(p) for p in self.global_providers.values()]
        if user_id and user_id in self.user_providers:
            providers += [self._format(p) for p in self.user_providers[user_id].values()]
        return providers

    def get_active_provider(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        name = self.active_providers.get(user_id) or self.active_providers.get(None)
        if not name:
            return None
        config = self.get_provider(name, user_id)
        return self._format(config) if config else None

    def _format(self, config: AIProviderConfig) -> Dict[str, Any]:
        return {
            "name": config.name,
            "provider_type": config.provider_type.value,
            "model": config.model,
            "enabled": config.enabled,
            "is_default": config.is_default,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "capabilities": [c.value for c in config.capabilities],
        }

    async def switch_provider(self, name: str, user_id: Optional[str] = None) -> bool:
        async with self._lock:
            config = self.get_provider(name, user_id)
            if not config or not config.enabled:
                return False
            self.active_providers[user_id] = name
            return True

    def update_parameters(
        self, name: str, params: Dict[str, Any], user_id: Optional[str] = None
    ) -> bool:
        config = self.get_provider(name, user_id)
        if not config:
            return False
        for key in ("temperature", "max_tokens", "top_p"):
            if params.get(key) is not None:
                setattr(config, key, params[key])
        # Invalidate cached client so new params are picked up
        self.clients.pop(self._cache_key(name, user_id), None)
        return True

    def _cache_key(self, name: str, user_id: Optional[str]) -> str:
        return f"{user_id}:{name}" if user_id else name

    async def get_client(self, provider_name: Optional[str] = None, user_id: Optional[str] = None):
        name = provider_name or self.active_providers.get(user_id) or self.active_providers.get(None)
        if not name:
            raise ValueError("No active provider set")
        config = self.get_provider(name, user_id)
        if not config:
            raise ValueError(f"Provider '{name}' not found")
        if not config.enabled:
            raise ValueError(f"Provider '{name}' is disabled")

        cache_key = self._cache_key(name, user_id)
        if cache_key in self.clients:
            return self.clients[cache_key], config
        client = self._create_client(config)
        self.clients[cache_key] = client
        return client, config

    def _create_client(self, config: AIProviderConfig):
        if config.provider_type in (ProviderType.VLLM, ProviderType.OPENAI):
            from openai import AsyncOpenAI

            return AsyncOpenAI(
                base_url=config.base_url,
                api_key=config.api_key or ("EMPTY" if config.provider_type == ProviderType.VLLM else None),
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        if config.provider_type == ProviderType.ANTHROPIC:
            from anthropic import AsyncAnthropic

            return AsyncAnthropic(
                api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries
            )
        raise ValueError(f"Unsupported provider type: {config.provider_type}")

    async def test_connection(self, name: str, user_id: Optional[str] = None) -> bool:
        try:
            client, config = await self.get_client(name, user_id)
        except Exception:
            return False
        try:
            if config.provider_type in (ProviderType.VLLM, ProviderType.OPENAI):
                await client.models.list()
                return True
            if config.provider_type == ProviderType.ANTHROPIC:
                # Anthropic has no lightweight list endpoint; a minimal call verifies auth.
                await client.messages.create(
                    model=config.model, max_tokens=1, messages=[{"role": "user", "content": "ping"}]
                )
                return True
        except Exception:
            return False
        return False
