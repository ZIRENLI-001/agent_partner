from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Dialogue Eval Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./artifacts/app.db"
    redis_url: str = "redis://localhost:6379/0"
    artifact_root: str | Path = "artifacts/runs"
    frontend_dist: str | Path = "frontend/dist"
    default_provider_type: str = "mock"
    default_api_base: str = ""
    default_model_name: str = ""
    request_timeout_seconds: int = 60
    request_retry_count: int = 1
    request_retry_backoff_seconds: float = 0.2
    scenario_concurrency: int = 3
    scenario_batch_size: int = 6
    model_cache_ttl_seconds: int = 900
    model_cache_max_entries: int = 512
    report_max_evidence_items: int = 80
    run_status_ttl_seconds: int = 86400
    eval_chain_provider: str = "mock"
    eval_chain_api_base: str = "https://openrouter.ai/api/v1"
    eval_chain_api_key: str = ""
    eval_user_simulator_model: str = "openai/gpt-4.1-mini"
    eval_semantic_judge_model: str = "anthropic/claude-sonnet-4.6"
    eval_rubric_generator_model: str = "openai/gpt-4.1-mini"
    eval_scenario_generator_model: str = "openai/gpt-4.1-mini"
    eval_report_generator_model: str = "openai/gpt-4.1-mini"
    eval_instruction_parser_model: str = "openai/gpt-4.1-mini"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_root() / path


def _dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        values[key] = value
    return values


def _env(name: str, default: str, dotenv: dict[str, str]) -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    return dotenv.get(name, default)


def settings_from_env() -> Settings:
    dotenv = _dotenv_values(project_root() / ".env")
    return Settings(
        environment=_env("APP_ENV", "development", dotenv),
        database_url=_env("DATABASE_URL", "sqlite:///./artifacts/app.db", dotenv),
        redis_url=_env("REDIS_URL", "redis://localhost:6379/0", dotenv),
        artifact_root=resolve_project_path(_env("EVAL_ARTIFACT_ROOT", "runs", dotenv)),
        frontend_dist=resolve_project_path(
            _env("EVAL_FRONTEND_DIST", "frontend/dist", dotenv)
        ),
        default_provider_type=_env("DEFAULT_PROVIDER_TYPE", "mock", dotenv),
        default_api_base=_env("DEFAULT_API_BASE", "", dotenv),
        default_model_name=_env("DEFAULT_MODEL_NAME", "", dotenv),
        request_timeout_seconds=int(_env("REQUEST_TIMEOUT_SECONDS", "60", dotenv)),
        request_retry_count=int(_env("REQUEST_RETRY_COUNT", "1", dotenv)),
        request_retry_backoff_seconds=float(
            _env("REQUEST_RETRY_BACKOFF_SECONDS", "0.2", dotenv)
        ),
        scenario_concurrency=int(_env("EVAL_SCENARIO_CONCURRENCY", "3", dotenv)),
        scenario_batch_size=int(_env("EVAL_SCENARIO_BATCH_SIZE", "6", dotenv)),
        model_cache_ttl_seconds=int(_env("EVAL_MODEL_CACHE_TTL_SECONDS", "900", dotenv)),
        model_cache_max_entries=int(_env("EVAL_MODEL_CACHE_MAX_ENTRIES", "512", dotenv)),
        report_max_evidence_items=int(
            _env("EVAL_REPORT_MAX_EVIDENCE_ITEMS", "80", dotenv)
        ),
        run_status_ttl_seconds=int(_env("EVAL_RUN_STATUS_TTL_SECONDS", "86400", dotenv)),
        eval_chain_provider=_env("EVAL_CHAIN_PROVIDER", "mock", dotenv),
        eval_chain_api_base=_env(
            "EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1", dotenv
        ),
        eval_chain_api_key=_env("EVAL_CHAIN_API_KEY", "", dotenv),
        eval_user_simulator_model=_env(
            "EVAL_USER_SIMULATOR_MODEL", "openai/gpt-4.1-mini", dotenv
        ),
        eval_semantic_judge_model=_env(
            "EVAL_SEMANTIC_JUDGE_MODEL", "anthropic/claude-sonnet-4.6", dotenv
        ),
        eval_rubric_generator_model=_env(
            "EVAL_RUBRIC_GENERATOR_MODEL", "openai/gpt-4.1-mini", dotenv
        ),
        eval_scenario_generator_model=_env(
            "EVAL_SCENARIO_GENERATOR_MODEL", "openai/gpt-4.1-mini", dotenv
        ),
        eval_report_generator_model=_env(
            "EVAL_REPORT_GENERATOR_MODEL", "openai/gpt-4.1-mini", dotenv
        ),
        eval_instruction_parser_model=_env(
            "EVAL_INSTRUCTION_PARSER_MODEL", "openai/gpt-4.1-mini", dotenv
        ),
    )
