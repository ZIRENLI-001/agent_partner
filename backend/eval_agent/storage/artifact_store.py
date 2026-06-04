from __future__ import annotations

from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
            raise ValueError("Invalid artifact path")
        path = self.root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def artifact_path(self, run_id: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise ValueError("Invalid artifact path")
        return self.run_dir(run_id) / filename

    def write_text(self, run_id: str, filename: str, content: str) -> Path:
        path = self.artifact_path(run_id, filename)
        path.write_text(content, encoding="utf-8")
        return path
