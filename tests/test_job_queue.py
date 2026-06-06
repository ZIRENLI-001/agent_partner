from __future__ import annotations

import json

import pytest

from backend.eval_agent.services.job_queue import (
    JobQueueFull,
    JobQueueUnavailable,
    JobQuotaExceeded,
    RedisJobQueue,
)


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.expirations: dict[str, int] = {}
        self.fail_submit = False

    def eval(self, script, numkeys, *values):
        if self.fail_submit:
            raise ConnectionError("redis unavailable")
        keys = values[:numkeys]
        args = values[numkeys:]
        queue_key, quota_key, payload_key, status_key = keys
        (
            run_id,
            quota_limit,
            max_queued,
            payload,
            status,
            payload_ttl,
            status_ttl,
        ) = args
        quota = int(self.values.get(quota_key, "0"))
        if quota >= int(quota_limit):
            return -1
        if len(self.lists.get(queue_key, [])) >= int(max_queued):
            return -2
        self.values[quota_key] = str(quota + 1)
        self.expirations[quota_key] = 3600
        self.values[payload_key] = payload
        self.expirations[payload_key] = int(payload_ttl)
        self.values[status_key] = status
        self.expirations[status_key] = int(status_ttl)
        self.lists.setdefault(queue_key, []).insert(0, run_id)
        return 1

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.expirations[key] = int(ttl)

    def exists(self, key):
        return key in self.values

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.expirations.pop(key, None)

    def brpoplpush(self, source, destination, timeout):
        source_values = self.lists.get(source, [])
        if not source_values:
            return None
        value = source_values.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value

    def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        return list(values if end == -1 else values[start : end + 1])

    def lrem(self, key, count, value):
        values = self.lists.get(key, [])
        original = len(values)
        self.lists[key] = [item for item in values if item != value]
        return original - len(self.lists[key])

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)


def build_queue(
    *,
    runs_per_hour: int = 10,
    max_queued: int = 10,
) -> tuple[RedisJobQueue, FakeRedis]:
    redis = FakeRedis()
    queue = RedisJobQueue(
        redis,
        runs_per_ip_per_hour=runs_per_hour,
        max_queued_runs=max_queued,
        job_timeout_seconds=900,
        status_ttl_seconds=86_400,
    )
    return queue, redis


def test_submit_enforces_jobs_per_ip_per_hour():
    queue, _ = build_queue(runs_per_hour=10, max_queued=20)
    for index in range(10):
        queue.submit(
            "203.0.113.10",
            f"run_{index:08x}",
            {"instruction": "ok"},
        )

    with pytest.raises(JobQuotaExceeded):
        queue.submit(
            "203.0.113.10",
            "run_deadbeef",
            {"instruction": "blocked"},
        )


def test_submit_rejects_eleventh_queued_job():
    queue, _ = build_queue(runs_per_hour=20, max_queued=10)
    for index in range(10):
        queue.submit(
            f"203.0.113.{index}",
            f"run_{index:08x}",
            {"instruction": "ok"},
        )

    with pytest.raises(JobQueueFull):
        queue.submit(
            "198.51.100.1",
            "run_deadbeef",
            {"instruction": "blocked"},
        )


def test_job_payload_expires_and_is_not_returned_in_status():
    queue, redis = build_queue()

    queue.submit(
        "203.0.113.10",
        "run_deadbeef",
        {"instruction": "ok", "api_key": "sk-secret"},
    )

    assert redis.expirations["eval:job:payload:run_deadbeef"] == 900
    assert "sk-secret" not in json.dumps(queue.status("run_deadbeef"))


def test_submit_connection_failure_leaves_no_partial_job():
    queue, redis = build_queue()
    redis.fail_submit = True

    with pytest.raises(JobQueueUnavailable):
        queue.submit(
            "203.0.113.10",
            "run_deadbeef",
            {"instruction": "ok"},
        )

    assert redis.values == {}
    assert redis.lists == {}


def test_claim_is_fifo_and_creates_a_lease():
    queue, redis = build_queue()
    queue.submit("203.0.113.1", "run_00000001", {"instruction": "first"})
    queue.submit("203.0.113.2", "run_00000002", {"instruction": "second"})

    claimed = queue.claim(timeout_seconds=0)

    assert claimed == ("run_00000001", {"instruction": "first"})
    assert redis.exists("eval:job:lease:run_00000001")
    assert queue.status("run_00000001")["status"] == "running"


def test_reconcile_requeues_processing_job_without_lease():
    queue, redis = build_queue()
    queue.submit("203.0.113.1", "run_deadbeef", {"instruction": "test"})
    assert queue.claim(timeout_seconds=0) is not None
    redis.delete("eval:job:lease:run_deadbeef")

    reconciled = queue.reconcile_stale_jobs()

    assert reconciled == 1
    assert redis.lists["eval:job:queue"] == ["run_deadbeef"]
    assert redis.lists["eval:job:processing"] == []
    assert queue.status("run_deadbeef")["status"] == "queued"
