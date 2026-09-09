"""AI provider configuration models."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    VLLM = "vllm"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelCapability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"


class AIProviderConfig(BaseModel):
    provider_type: ProviderType
    name: str = Field(description="Display name / unique key")
    enabled: bool = True
    is_default: bool = False
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3

    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=32000)
    top_p: float = Field(0.95, ge=0.0, le=1.0)

    # Whether this provider/endpoint supports OpenAI-style tool calling.
    # vLLM requires --enable-auto-tool-choice + --tool-call-parser at launch,
    # so it defaults to off and can be enabled via VLLM_ENABLE_TOOLS.
    supports_tools: bool = True

    capabilities: List[ModelCapability] = Field(default_factory=list)
    provider_settings: Dict[str, Any] = Field(default_factory=dict)


class ProviderSwitchRequest(BaseModel):
    provider_name: str


class ProviderParameters(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
