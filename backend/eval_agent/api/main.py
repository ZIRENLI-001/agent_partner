from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.eval_agent.api.routes import calibration, context, health, imports, runs, stages
from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.core.security import (
    ApiTokenMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from backend.evaluation_engine.app import WEB_INDEX

FRONTEND_DIST: Path | None = None


def create_app() -> FastAPI:
    settings = settings_from_env()
    production = settings.environment.lower() == "production"
    frontend_dist = (
        Path(FRONTEND_DIST) if FRONTEND_DIST is not None else Path(settings.frontend_dist)
    )
    if production:
        if settings.auth_required and not settings.access_token:
            raise RuntimeError("APP_ACCESS_TOKEN is required when APP_ENV=production")
        if not (frontend_dist / "index.html").is_file():
            raise RuntimeError("frontend production build is required")

    docs_enabled = not production
    app = FastAPI(
        title="Dialogue Eval Platform",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    if production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(settings.trusted_hosts),
        )
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(ApiTokenMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(calibration.router)
    app.include_router(context.router)
    app.include_router(health.router)
    app.include_router(imports.router)
    app.include_router(stages.router)
    app.include_router(runs.router)

    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="frontend-assets",
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _frontend_index_html(frontend_dist)

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    def frontend_fallback(full_path: str) -> str:
        if full_path.startswith("api/") or (
            not docs_enabled
            and full_path in {"docs", "redoc", "openapi.json"}
        ):
            raise HTTPException(status_code=404, detail="Not found")
        return _frontend_index_html(frontend_dist)

    return app


def _frontend_index_html(frontend_dist: Path | None = None) -> str:
    dist = frontend_dist or Path(settings_from_env().frontend_dist)
    frontend_index = dist / "index.html"
    if frontend_index.exists():
        return frontend_index.read_text(encoding="utf-8")
    return WEB_INDEX.read_text(encoding="utf-8")


app = create_app()

__all__ = ["app", "create_app"]
