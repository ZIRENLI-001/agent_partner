from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


Message = dict[str, str]


@dataclass(frozen=True)
class ModelConfig:
    provider_type: str = "mock"
    api_base: str = ""
    api_key: str = ""
    model_name: str = ""
    temperature: float = 0.2
    max_tokens: int = 512
    timeout_seconds: int = 60
    response_format: dict[str, Any] | None = None
    retry_count: int = 1
    retry_backoff_seconds: float = 0.2
    cache_enabled: bool = False
    cache_ttl_seconds: int = 0
    cache_max_entries: int = 256

    def safe_summary(self) -> dict[str, object]:
        return {
            "provider_type": self.provider_type,
            "api_base": self.api_base,
            "model_name": self.model_name,
            "api_key_configured": bool(self.api_key),
            "api_key_last4": self.api_key[-4:] if self.api_key else "",
        }


@dataclass(frozen=True)
class ModelResponse:
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class ModelProviderError(RuntimeError):
    def __init__(self, message: str, provider_type: str, model_name: str):
        super().__init__(message)
        self.provider_type = provider_type
        self.model_name = model_name


class ModelProvider(Protocol):
    def generate(self, messages: list[Message], config: ModelConfig) -> ModelResponse:
        ...
