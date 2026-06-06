from __future__ import annotations

from contextlib import contextmanager
import logging
import signal
import time
from typing import Callable, Iterator

from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.services.job_queue import (
    JobQueueUnavailable,
    RedisJobQueue,
)
from backend.eval_agent.services.run_service import (
    execute_queued_run,
    job_queue,
)

logger = logging.getLogger(__name__)


def process_next_job(
    queue: RedisJobQueue,
    execute: Callable[[dict[str, object], str], None],
    *,
    claim_timeout_seconds: int = 5,
    deadline_seconds: int | None = None,
) -> bool:
    claimed = queue.claim(timeout_seconds=claim_timeout_seconds)
    if claimed is None:
        return False
    run_id, payload = claimed
    try:
        with _job_deadline(deadline_seconds):
            execute(payload, run_id)
    except Exception as exc:
        logger.error(
            "Evaluation job %s failed with %s",
            run_id,
            type(exc).__name__,
        )
        queue.fail(run_id, "Evaluation failed")
        return True
    queue.complete(run_id)
    return True


def run_worker() -> None:
    settings = settings_from_env()
    queue = job_queue(require_redis=True)
    while True:
        try:
            queue.reconcile_stale_jobs()
            process_next_job(
                queue,
                execute_queued_run,
                claim_timeout_seconds=5,
                deadline_seconds=settings.run_job_timeout_seconds,
            )
        except JobQueueUnavailable:
            logger.error("Evaluation queue is unavailable")
            time.sleep(2)


@contextmanager
def _job_deadline(seconds: int | None) -> Iterator[None]:
    if not seconds or not hasattr(signal, "SIGALRM"):
        yield
        return

    def timeout_handler(signum, frame):
        raise TimeoutError("Evaluation job timed out")

    previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
