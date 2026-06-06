from __future__ import annotations

from hashlib import sha256
import json
import time
from typing import Any

from backend.eval_agent.storage.artifact_store import GENERATED_RUN_ID_PATTERN


class JobQuotaExceeded(RuntimeError):
    pass


class JobQueueFull(RuntimeError):
    pass


class JobQueueUnavailable(RuntimeError):
    pass


SUBMIT_SCRIPT = """
local quota = tonumber(redis.call('GET', KEYS[2]) or '0')
if quota >= tonumber(ARGV[2]) then
    return -1
end
if redis.call('LLEN', KEYS[1]) >= tonumber(ARGV[3]) then
    return -2
end
redis.call('SETEX', KEYS[3], ARGV[6], ARGV[4])
redis.call('SETEX', KEYS[4], ARGV[7], ARGV[5])
redis.call('LPUSH', KEYS[1], ARGV[1])
local updated_quota = redis.call('INCR', KEYS[2])
if updated_quota == 1 then
    redis.call('EXPIRE', KEYS[2], 3600)
end
return 1
"""


class RedisJobQueue:
    queue_key = "eval:job:queue"
    processing_key = "eval:job:processing"

    def __init__(
        self,
        redis_client: Any,
        *,
        runs_per_ip_per_hour: int,
        max_queued_runs: int,
        job_timeout_seconds: int,
        status_ttl_seconds: int,
    ):
        self.redis = redis_client
        self.runs_per_ip_per_hour = runs_per_ip_per_hour
        self.max_queued_runs = max_queued_runs
        self.job_timeout_seconds = job_timeout_seconds
        self.status_ttl_seconds = status_ttl_seconds

    def submit(
        self,
        source_ip: str,
        run_id: str,
        payload: dict[str, object],
    ) -> None:
        self._validate_run_id(run_id)
        now = time.time()
        public_status = {
            "run_id": run_id,
            "status": "queued",
            "current_stage": "queued",
            "stages": [],
            "error": "",
            "result_url": "",
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = self.redis.eval(
                SUBMIT_SCRIPT,
                4,
                self.queue_key,
                self._quota_key(source_ip),
                self._payload_key(run_id),
                self._status_key(run_id),
                run_id,
                self.runs_per_ip_per_hour,
                self.max_queued_runs,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(public_status, ensure_ascii=False),
                self.job_timeout_seconds,
                self.status_ttl_seconds,
            )
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc
        if int(result) == -1:
            raise JobQuotaExceeded("Hourly run quota exceeded")
        if int(result) == -2:
            raise JobQueueFull("Job queue is full")
        if int(result) != 1:
            raise JobQueueUnavailable("Job queue rejected the request")

    def status(self, run_id: str) -> dict[str, object] | None:
        self._validate_run_id(run_id)
        try:
            raw = self.redis.get(self._status_key(run_id))
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc
        if raw is None:
            return None
        return json.loads(_text(raw))

    def claim(
        self,
        timeout_seconds: int = 5,
    ) -> tuple[str, dict[str, object]] | None:
        try:
            raw_run_id = self.redis.brpoplpush(
                self.queue_key,
                self.processing_key,
                timeout_seconds,
            )
            if raw_run_id is None:
                return None
            run_id = _text(raw_run_id)
            self._validate_run_id(run_id)
            raw_payload = self.redis.get(self._payload_key(run_id))
            if raw_payload is None:
                self.redis.lrem(self.processing_key, 0, run_id)
                self._set_status(run_id, "failed", error="Evaluation job expired")
                return None
            self.redis.setex(
                self._lease_key(run_id),
                self.job_timeout_seconds,
                "active",
            )
            self._set_status(run_id, "running", current_stage="starting")
            return run_id, json.loads(_text(raw_payload))
        except JobQueueUnavailable:
            raise
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc

    def heartbeat(self, run_id: str) -> None:
        self._validate_run_id(run_id)
        try:
            self.redis.setex(
                self._lease_key(run_id),
                self.job_timeout_seconds,
                "active",
            )
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc

    def complete(self, run_id: str) -> None:
        self._validate_run_id(run_id)
        try:
            self._set_status(
                run_id,
                "completed",
                result_url=f"/api/runs/{run_id}",
            )
            self._remove_claimed_job(run_id)
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc

    def fail(self, run_id: str, public_error: str) -> None:
        self._validate_run_id(run_id)
        try:
            self._set_status(run_id, "failed", error=public_error)
            self._remove_claimed_job(run_id)
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc

    def reconcile_stale_jobs(self) -> int:
        reconciled = 0
        try:
            for raw_run_id in self.redis.lrange(self.processing_key, 0, -1):
                run_id = _text(raw_run_id)
                if self.redis.exists(self._lease_key(run_id)):
                    continue
                self.redis.lrem(self.processing_key, 0, run_id)
                if self.redis.get(self._payload_key(run_id)) is None:
                    self._set_status(
                        run_id,
                        "failed",
                        error="Evaluation job expired",
                    )
                    continue
                self.redis.lpush(self.queue_key, run_id)
                self._set_status(run_id, "queued", current_stage="queued")
                reconciled += 1
        except Exception as exc:
            raise JobQueueUnavailable("Job queue is unavailable") from exc
        return reconciled

    def _remove_claimed_job(self, run_id: str) -> None:
        self.redis.lrem(self.processing_key, 0, run_id)
        self.redis.delete(
            self._payload_key(run_id),
            self._lease_key(run_id),
        )

    def _set_status(
        self,
        run_id: str,
        status: str,
        *,
        current_stage: str = "",
        error: str = "",
        result_url: str = "",
    ) -> None:
        existing = self.status(run_id) or {}
        now = time.time()
        payload = {
            "run_id": run_id,
            "status": status,
            "current_stage": current_stage,
            "stages": existing.get("stages", []),
            "error": error,
            "result_url": result_url,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        self.redis.setex(
            self._status_key(run_id),
            self.status_ttl_seconds,
            json.dumps(payload, ensure_ascii=False),
        )

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not GENERATED_RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid run_id")

    @staticmethod
    def _quota_key(source_ip: str) -> str:
        digest = sha256(source_ip.encode("utf-8")).hexdigest()
        return f"eval:job:quota:{digest}"

    @staticmethod
    def _payload_key(run_id: str) -> str:
        return f"eval:job:payload:{run_id}"

    @staticmethod
    def _lease_key(run_id: str) -> str:
        return f"eval:job:lease:{run_id}"

    @staticmethod
    def _status_key(run_id: str) -> str:
        return f"eval:run:{run_id}"


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
