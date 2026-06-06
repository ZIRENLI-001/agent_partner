from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.cleanup_artifacts import cleanup_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_run(root: Path, run_id: str, *, age_days: int, now: float) -> Path:
    path = root / run_id
    path.mkdir()
    timestamp = now - age_days * 86_400
    os.utime(path, (timestamp, timestamp))
    return path


def test_cleanup_removes_only_expired_valid_run_directories(tmp_path):
    now = 2_000_000_000.0
    old = _make_run(tmp_path, "run_deadbeef", age_days=8, now=now)
    recent = _make_run(tmp_path, "run_1234abcd", age_days=1, now=now)
    malformed = _make_run(tmp_path, "other", age_days=8, now=now)

    removed = cleanup_artifacts(tmp_path, retention_days=7, now=now)

    assert removed == [old]
    assert not old.exists()
    assert recent.exists()
    assert malformed.exists()


def test_cleanup_never_follows_symlinks(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "run_deadbeef"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable in this environment")

    cleanup_artifacts(tmp_path, retention_days=0, now=2_000_000_000.0)

    assert outside.exists()
    assert link.is_symlink()
