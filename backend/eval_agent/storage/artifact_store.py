from __future__ import annotations

from pathlib import Path
import re


GENERATED_RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{8}$")


def safe_run_dir(
    root: str | Path,
    run_id: str,
    *,
    create: bool = False,
    require_generated_id: bool = False,
) -> Path:
    if (
        not run_id
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
        or (require_generated_id and not GENERATED_RUN_ID_PATTERN.fullmatch(run_id))
    ):
        raise ValueError("Invalid artifact path")

    resolved_root = Path(root).resolve()
    path = (resolved_root / run_id).resolve()
    if path.parent != resolved_root:
        raise ValueError("Invalid artifact path")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return safe_run_dir(self.root, run_id, create=True)

    def artifact_path(self, run_id: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise ValueError("Invalid artifact path")
        return self.run_dir(run_id) / filename

    def write_text(self, run_id: str, filename: str, content: str) -> Path:
        path = self.artifact_path(run_id, filename)
        path.write_text(content, encoding="utf-8")
        return path
