from __future__ import annotations

import json
import time
from typing import Any


class RunStatusStore:
    def __init__(
        self,
        redis_client: Any,
        key_prefix: str = "eval:run",
        ttl_seconds: int = 86400,
    ):
        self.redis_client = redis_client
        self.key_prefix = key_prefix.rstrip(":")
        self.ttl_seconds = ttl_seconds

    def set_status(
        self,
        run_id: str,
        status: str,
        current_stage: str = "",
        stages: list[dict[str, object]] | None = None,
        error: str = "",
        result_url: str = "",
    ) -> dict[str, object]:
        now = time.time()
        existing = self.get_status(run_id) or {}
        payload = {
            "run_id": run_id,
            "status": status,
            "current_stage": current_stage,
            "stages": stages or existing.get("stages", []),
            "error": error,
            "result_url": result_url,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        self.redis_client.setex(
            self._key(run_id),
            self.ttl_seconds,
            json.dumps(payload, ensure_ascii=False),
        )
        return payload

    def get_status(self, run_id: str) -> dict[str, object] | None:
        raw = self.redis_client.get(self._key(run_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _key(self, run_id: str) -> str:
        if not run_id or "/" in run_id or "\\" in run_id:
            raise ValueError("Invalid run_id")
        return "%s:%s" % (self.key_prefix, run_id)


def redis_client_from_url(redis_url: str):
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("redis package is not installed") from exc
    return Redis.from_url(redis_url, decode_responses=True)


class MemoryRunStatusStore:
    def __init__(self):
        self.values: dict[str, dict[str, object]] = {}

    def set_status(
        self,
        run_id: str,
        status: str,
        current_stage: str = "",
        stages: list[dict[str, object]] | None = None,
        error: str = "",
        result_url: str = "",
    ) -> dict[str, object]:
        now = time.time()
        existing = self.values.get(run_id, {})
        payload = {
            "run_id": run_id,
            "status": status,
            "current_stage": current_stage,
            "stages": stages or existing.get("stages", []),
            "error": error,
            "result_url": result_url,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "storage": "memory",
        }
        self.values[run_id] = payload
        return payload

    def get_status(self, run_id: str) -> dict[str, object] | None:
        return self.values.get(run_id)
