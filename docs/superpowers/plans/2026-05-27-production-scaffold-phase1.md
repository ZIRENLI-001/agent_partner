# Production Scaffold Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the production-oriented project scaffold without breaking the current FastAPI MVP.

**Architecture:** Keep the existing `eval_agent` runtime as the compatibility source of truth. Add a new `backend/` package with stable API, core config, provider, and artifact boundaries that wrap or prepare for migration from the existing modules. Add tests that prove the new entrypoints work while existing tests remain valid.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, pathlib/json artifacts.

---

## File Structure

- Create `backend/__init__.py`: marks the production backend namespace.
- Create `backend/eval_agent/__init__.py`: marks the future production backend package.
- Create `backend/eval_agent/api/__init__.py`: API package marker.
- Create `backend/eval_agent/api/main.py`: compatibility FastAPI app entrypoint that re-exports the current app.
- Create `backend/eval_agent/core/__init__.py`: core package marker.
- Create `backend/eval_agent/core/config.py`: typed runtime settings for API, database, Redis, artifacts, and model defaults.
- Create `backend/eval_agent/providers/__init__.py`: provider exports.
- Create `backend/eval_agent/providers/base.py`: provider config, response, and protocol types.
- Create `backend/eval_agent/providers/mock.py`: wraps existing mock providers behind the new provider package.
- Create `backend/eval_agent/providers/openai_compatible.py`: OpenAI-compatible/OpenRouter/self-hosted provider implementation with injectable HTTP transport.
- Create `backend/eval_agent/storage/__init__.py`: storage package marker.
- Create `backend/eval_agent/storage/artifact_store.py`: production artifact path boundary with path traversal protection.
- Create `frontend/README.md`: documents the planned React frontend boundary without installing dependencies yet.
- Modify `tests/test_app.py`: add tests for the new backend app entrypoint.
- Create `tests/test_backend_scaffold.py`: tests for settings, artifact store, and OpenAI-compatible provider payload/redaction behavior.

## Task 1: Backend API Compatibility Entrypoint

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/eval_agent/__init__.py`
- Create: `backend/eval_agent/api/__init__.py`
- Create: `backend/eval_agent/api/main.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write the failing compatibility test**

Append this test to `tests/test_app.py`:

```python
def test_backend_api_entrypoint_reuses_current_fastapi_app():
    from backend.eval_agent.api.main import app as backend_app

    client = TestClient(backend_app)
    response = client.get("/")

    assert response.status_code == 200
    assert "美团履约评测" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_app.py::test_backend_api_entrypoint_reuses_current_fastapi_app -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend'`.

- [ ] **Step 3: Create backend package markers**

Create empty files:

```text
backend/__init__.py
backend/eval_agent/__init__.py
backend/eval_agent/api/__init__.py
```

- [ ] **Step 4: Create compatibility app entrypoint**

Create `backend/eval_agent/api/main.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.app import app

__all__ = ["app"]
```

- [ ] **Step 5: Run the compatibility test**

Run: `python3 -m pytest tests/test_app.py::test_backend_api_entrypoint_reuses_current_fastapi_app -q`

Expected: PASS.

## Task 2: Runtime Settings Boundary

**Files:**
- Create: `backend/eval_agent/core/__init__.py`
- Create: `backend/eval_agent/core/config.py`
- Create: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_backend_scaffold.py` with:

```python
from backend.eval_agent.core.config import Settings


def test_settings_default_paths_support_development_deploy():
    settings = Settings()

    assert settings.app_name == "Dialogue Eval Platform"
    assert settings.database_url == "sqlite:///./artifacts/app.db"
    assert settings.artifact_root == "artifacts/runs"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.default_provider_type == "mock"


def test_settings_accepts_openrouter_model_defaults():
    settings = Settings(
        default_provider_type="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        default_model_name="openai/gpt-4o",
    )

    assert settings.default_provider_type == "openrouter"
    assert settings.default_api_base == "https://openrouter.ai/api/v1"
    assert settings.default_model_name == "openai/gpt-4o"
```

- [ ] **Step 2: Run the settings tests to verify they fail**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_settings_default_paths_support_development_deploy -q`

Expected: FAIL with missing module or missing `Settings`.

- [ ] **Step 3: Implement settings**

Create `backend/eval_agent/core/__init__.py` as an empty file.

Create `backend/eval_agent/core/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Dialogue Eval Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./artifacts/app.db"
    redis_url: str = "redis://localhost:6379/0"
    artifact_root: str = "artifacts/runs"
    default_provider_type: str = "mock"
    default_api_base: str = ""
    default_model_name: str = ""
    request_timeout_seconds: int = 60
```

- [ ] **Step 4: Run settings tests**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_settings_default_paths_support_development_deploy tests/test_backend_scaffold.py::test_settings_accepts_openrouter_model_defaults -q`

Expected: PASS.

## Task 3: Artifact Store Boundary

**Files:**
- Create: `backend/eval_agent/storage/__init__.py`
- Create: `backend/eval_agent/storage/artifact_store.py`
- Modify: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing artifact store tests**

Append to `tests/test_backend_scaffold.py`:

```python
import pytest

from backend.eval_agent.storage.artifact_store import ArtifactStore


def test_artifact_store_writes_run_artifact(tmp_path):
    store = ArtifactStore(tmp_path)

    path = store.write_text("run_abc123", "report.md", "# Report")

    assert path == tmp_path / "run_abc123" / "report.md"
    assert path.read_text(encoding="utf-8") == "# Report"


def test_artifact_store_rejects_path_traversal(tmp_path):
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="Invalid artifact path"):
        store.write_text("run_abc123", "../report.md", "bad")
```

- [ ] **Step 2: Run artifact tests to verify they fail**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_artifact_store_writes_run_artifact -q`

Expected: FAIL with missing module or missing `ArtifactStore`.

- [ ] **Step 3: Implement artifact store**

Create `backend/eval_agent/storage/__init__.py` as an empty file.

Create `backend/eval_agent/storage/artifact_store.py`:

```python
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
```

- [ ] **Step 4: Run artifact tests**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_artifact_store_writes_run_artifact tests/test_backend_scaffold.py::test_artifact_store_rejects_path_traversal -q`

Expected: PASS.

## Task 4: Provider Abstraction And OpenAI-Compatible Payload

**Files:**
- Create: `backend/eval_agent/providers/__init__.py`
- Create: `backend/eval_agent/providers/base.py`
- Create: `backend/eval_agent/providers/mock.py`
- Create: `backend/eval_agent/providers/openai_compatible.py`
- Modify: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing provider tests**

Append to `tests/test_backend_scaffold.py`:

```python
from backend.eval_agent.providers.base import ModelConfig
from backend.eval_agent.providers.openai_compatible import OpenAICompatibleProvider


class RecordingTransport:
    def __init__(self):
        self.url = ""
        self.headers = {}
        self.payload = {}

    def post_json(self, url, headers, payload, timeout_seconds):
        self.url = url
        self.headers = headers
        self.payload = payload
        return {
            "choices": [
                {"message": {"content": "模型回复"}}
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }


def test_openai_compatible_provider_builds_chat_completion_request():
    transport = RecordingTransport()
    provider = OpenAICompatibleProvider(transport=transport)
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model_name="openai/gpt-4o",
        temperature=0.2,
        max_tokens=128,
    )

    response = provider.generate(
        messages=[{"role": "user", "content": "你好"}],
        config=config,
    )

    assert transport.url == "https://openrouter.ai/api/v1/chat/completions"
    assert transport.headers["Authorization"] == "Bearer sk-or-secret"
    assert transport.payload["model"] == "openai/gpt-4o"
    assert transport.payload["messages"] == [{"role": "user", "content": "你好"}]
    assert transport.payload["temperature"] == 0.2
    assert transport.payload["max_tokens"] == 128
    assert response.content == "模型回复"
    assert response.raw["usage"]["completion_tokens"] == 2


def test_model_config_summary_does_not_expose_api_key():
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model_name="openai/gpt-4o",
    )

    assert config.safe_summary() == {
        "provider_type": "openrouter",
        "api_base": "https://openrouter.ai/api/v1",
        "model_name": "openai/gpt-4o",
        "api_key_configured": True,
        "api_key_last4": "cret",
    }
```

- [ ] **Step 2: Run provider tests to verify they fail**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_openai_compatible_provider_builds_chat_completion_request -q`

Expected: FAIL with missing module or missing provider.

- [ ] **Step 3: Implement provider base types**

Create `backend/eval_agent/providers/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


Message = dict[str, str]


@dataclass(frozen=True)
class ModelConfig:
    provider_type: str = "mock"
    api_base: str = ""
    api_key: str = ""
    model_name: str = ""
    temperature: float = 0.2
    max_tokens: int = 512
    timeout_seconds: int = 60

    def safe_summary(self) -> dict[str, object]:
        return {
            "provider_type": self.provider_type,
            "api_base": self.api_base,
            "model_name": self.model_name,
            "api_key_configured": bool(self.api_key),
            "api_key_last4": self.api_key[-4:] if self.api_key else "",
        }


@dataclass(frozen=True)
class ModelResponse:
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    def generate(self, messages: list[Message], config: ModelConfig) -> ModelResponse:
        ...
```

- [ ] **Step 4: Implement OpenAI-compatible provider**

Create `backend/eval_agent/providers/openai_compatible.py`:

```python
from __future__ import annotations

import json
from typing import Any, Protocol
from urllib import request

from backend.eval_agent.providers.base import Message, ModelConfig, ModelResponse


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
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


class OpenAICompatibleProvider:
    def __init__(self, transport: JsonTransport | None = None):
        self.transport = transport or UrllibJsonTransport()

    def generate(self, messages: list[Message], config: ModelConfig) -> ModelResponse:
        api_base = config.api_base.rstrip("/")
        if not api_base:
            raise ValueError("api_base is required")
        if not config.model_name:
            raise ValueError("model_name is required")
        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
        }
        if config.api_key:
            headers["Authorization"] = "Bearer %s" % config.api_key

        raw = self.transport.post_json(
            "%s/chat/completions" % api_base,
            headers,
            payload,
            config.timeout_seconds,
        )
        content = _extract_content(raw)
        return ModelResponse(content=content, raw=raw)


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
```

- [ ] **Step 5: Implement provider package exports and mock wrappers**

Create `backend/eval_agent/providers/mock.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider

__all__ = ["FakeAssistantProvider", "FakeUserProvider"]
```

Create `backend/eval_agent/providers/__init__.py`:

```python
from backend.eval_agent.providers.base import ModelConfig, ModelProvider, ModelResponse
from backend.eval_agent.providers.openai_compatible import OpenAICompatibleProvider

__all__ = ["ModelConfig", "ModelProvider", "ModelResponse", "OpenAICompatibleProvider"]
```

- [ ] **Step 6: Run provider tests**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_openai_compatible_provider_builds_chat_completion_request tests/test_backend_scaffold.py::test_model_config_summary_does_not_expose_api_key -q`

Expected: PASS.

## Task 5: Frontend Boundary Documentation

**Files:**
- Create: `frontend/README.md`

- [ ] **Step 1: Create frontend boundary documentation**

Create `frontend/README.md`:

```markdown
# Frontend

This directory is reserved for the React + TypeScript + Vite frontend described in `docs/architecture/production-platform-tech-selection.md`.

The current runnable MVP is still served from `eval_agent/web/index.html`. The migration should keep that page available until the React implementation reaches feature parity for:

- Home
- End-to-end evaluation
- Evaluation visualization
- Run history
- Run detail report

Do not remove `eval_agent/web/index.html` until the React app has equivalent tests and deployment wiring.
```

- [ ] **Step 2: Verify documentation exists**

Run: `test -f frontend/README.md`

Expected: PASS with exit code 0.

## Task 6: Full Verification

**Files:**
- No code changes.

- [ ] **Step 1: Run backend scaffold tests**

Run: `python3 -m pytest tests/test_backend_scaffold.py -q`

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Run frontend script syntax check for current MVP**

Run:

```bash
node -e "const fs=require('fs');const html=fs.readFileSync('eval_agent/web/index.html','utf8');const m=html.match(/<script>([\s\S]*)<\/script>/);new Function(m[1]);console.log('script syntax ok')"
```

Expected: `script syntax ok`.
