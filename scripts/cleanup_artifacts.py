from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time

from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.storage.artifact_store import GENERATED_RUN_ID_PATTERN


def cleanup_artifacts(
    root: str | Path,
    *,
    retention_days: int,
    now: float | None = None,
) -> list[Path]:
    artifact_root = Path(root).resolve()
    if not artifact_root.is_dir():
        return []
    cutoff = (time.time() if now is None else now) - retention_days * 86_400
    removed: list[Path] = []
    for child in artifact_root.iterdir():
        if (
            not GENERATED_RUN_ID_PATTERN.fullmatch(child.name)
            or child.is_symlink()
            or not child.is_dir()
        ):
            continue
        if child.stat().st_mtime > cutoff:
            continue
        resolved = child.resolve()
        if resolved.parent != artifact_root:
            continue
        shutil.rmtree(resolved)
        removed.append(child)
    return removed


def main() -> int:
    settings = settings_from_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(settings.artifact_root))
    parser.add_argument(
        "--retention-days",
        type=int,
        default=settings.artifact_retention_days,
    )
    args = parser.parse_args()
    cleanup_artifacts(
        args.root,
        retention_days=max(0, args.retention_days),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
