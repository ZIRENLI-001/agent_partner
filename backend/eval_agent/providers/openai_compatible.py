from __future__ import annotations

import json
import hashlib
from ipaddress import ip_address
import threading
import time
from typing import Any, Callable, Protocol
from urllib import request
from urllib.parse import urlsplit

from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.providers.base import (
    Message,
    ModelConfig,
    ModelProviderError,
    ModelResponse,
)


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        ...


class UrllibJsonTransport:
    def __init__(
        self,
        opener: Callable[[request.Request, int], Any] | None = None,
        max_response_bytes: int | None = None,
    ):
        self.opener = opener or request.build_opener(_NoRedirectHandler()).open
        self.max_response_bytes = max_response_bytes

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        limit = (
            self.max_response_bytes
            if self.max_response_bytes is not None
            else settings_from_env().model_response_max_bytes
        )
        with self.opener(req, timeout=timeout_seconds) as response:
            response_body = response.read(limit + 1)
        if len(response_body) > limit:
            raise ValueError("Model provider response is too large")
        return json.loads(response_body.decode("utf-8"))


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        return None


class OpenAICompatibleProvider:
    _cache: dict[str, tuple[float, ModelResponse]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, transport: JsonTransport | None = None):
        self.transport = transport or UrllibJsonTransport()

    def generate(self, messages: list[Message], config: ModelConfig) -> ModelResponse:
        api_base = config.api_base.rstrip("/")
        if not api_base:
            raise ValueError("api_base is required")
        if not config.model_name:
            raise ValueError("model_name is required")
        _validate_api_base(api_base, config.provider_type)
        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        if config.response_format:
            payload["response_format"] = config.response_format
        headers = {
            "Content-Type": "application/json",
        }
        if config.api_key:
            headers["Authorization"] = "Bearer %s" % config.api_key

        cache_key = _cache_key(messages, payload, config) if config.cache_enabled else ""
        if cache_key:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        raw = self._post_with_retry(api_base, headers, payload, config)
        content = _extract_content(raw)
        response = ModelResponse(content=content, raw=raw)
        if cache_key:
            self._set_cached(cache_key, response, config)
        return response

    @classmethod
    def clear_cache(cls) -> None:
        with cls._cache_lock:
            cls._cache.clear()

    @classmethod
    def _get_cached(cls, cache_key: str) -> ModelResponse | None:
        now = time.time()
        with cls._cache_lock:
            cached = cls._cache.get(cache_key)
            if cached is None:
                return None
            expires_at, response = cached
            if expires_at <= now:
                cls._cache.pop(cache_key, None)
                return None
            return response

    @classmethod
    def _set_cached(
        cls,
        cache_key: str,
        response: ModelResponse,
        config: ModelConfig,
    ) -> None:
        if config.cache_ttl_seconds <= 0:
            return
        max_entries = max(1, config.cache_max_entries)
        with cls._cache_lock:
            if len(cls._cache) >= max_entries:
                oldest_key = min(cls._cache, key=lambda key: cls._cache[key][0])
                cls._cache.pop(oldest_key, None)
            cls._cache[cache_key] = (time.time() + config.cache_ttl_seconds, response)

    def _post_with_retry(
        self,
        api_base: str,
        headers: dict[str, str],
        payload: dict[str, object],
        config: ModelConfig,
    ) -> dict[str, Any]:
        attempts = max(1, config.retry_count + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self.transport.post_json(
                    "%s/chat/completions" % api_base,
                    headers,
                    payload,
                    config.timeout_seconds,
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                if config.retry_backoff_seconds > 0:
                    time.sleep(config.retry_backoff_seconds * (attempt + 1))
        if last_exc is None:
            last_exc = RuntimeError("Model provider request did not run")
        safe_error = _redact_secret(str(last_exc), config.api_key)
        raise ModelProviderError(
            "Model provider request failed: %s" % safe_error,
            provider_type=config.provider_type,
            model_name=config.model_name,
        ) from last_exc


def _extract_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices", [])
    if not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def _validate_api_base(api_base: str, provider_type: str = "") -> None:
    parsed = urlsplit(api_base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("api_base must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("api_base must not contain credentials, query, or fragment")

    allowed = settings_from_env().allowed_model_api_bases
    if api_base.rstrip("/") not in allowed:
        raise ValueError("api_base is not in ALLOWED_MODEL_API_BASES")
    if (
        settings_from_env().environment.lower() == "production"
        and parsed.scheme != "https"
    ):
        raise ValueError("api_base must use HTTPS in production")
    try:
        address = ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global and provider_type != "internal_gateway":
        raise ValueError(
            "private model addresses require the internal_gateway provider"
        )


def _redact_secret(message: str, secret: str) -> str:
    if not secret:
        return message
    return message.replace(secret, "[REDACTED]")


def _cache_key(
    messages: list[Message],
    payload: dict[str, object],
    config: ModelConfig,
) -> str:
    cache_payload = {
        "provider_type": config.provider_type,
        "api_base": config.api_base.rstrip("/"),
        "model_name": config.model_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "response_format": config.response_format,
        "messages": messages,
        "payload": payload,
    }
    encoded = json.dumps(cache_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
