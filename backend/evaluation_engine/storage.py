from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from backend.eval_agent.storage.artifact_store import safe_run_dir


class RunStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return safe_run_dir(self.root, run_id, create=True)

    def write_model(self, run_id: str, filename: str, model: BaseModel) -> None:
        self.write_json(run_id, filename, model.model_dump(mode="json"))

    def write_json(self, run_id: str, filename: str, payload: object) -> None:
        path = self.run_dir(run_id) / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def write_jsonl(
        self,
        run_id: str,
        filename: str,
        models: Iterable[BaseModel],
    ) -> None:
        path = self.run_dir(run_id) / filename
        lines = [
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
            for model in models
        ]
        content = "\n".join(lines)
        if content:
            content += "\n"
        path.write_text(content, encoding="utf-8")

    def write_text(self, run_id: str, filename: str, content: str) -> None:
        path = self.run_dir(run_id) / filename
        path.write_text(content, encoding="utf-8")
