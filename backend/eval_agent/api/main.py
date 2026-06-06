from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.eval_agent.api.routes import calibration, context, health, imports, runs, stages
from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.core.security import ApiTokenMiddleware
from backend.evaluation_engine.app import WEB_INDEX

FRONTEND_DIST = settings_from_env().frontend_dist


def create_app() -> FastAPI:
    settings = settings_from_env()
    if settings.environment.lower() == "production" and not settings.access_token:
        raise RuntimeError("APP_ACCESS_TOKEN is required when APP_ENV=production")

    docs_enabled = settings.environment.lower() != "production"
    app = FastAPI(
        title="Dialogue Eval Platform",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(ApiTokenMiddleware)
    app.include_router(calibration.router)
    app.include_router(context.router)
    app.include_router(health.router)
    app.include_router(imports.router)
    app.include_router(stages.router)
    app.include_router(runs.router)

    if FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIST / "assets"),
            name="frontend-assets",
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _frontend_index_html()

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    def frontend_fallback(full_path: str) -> str:
        if full_path.startswith("api/") or (
            not docs_enabled
            and full_path in {"docs", "redoc", "openapi.json"}
        ):
            raise HTTPException(status_code=404, detail="Not found")
        return _frontend_index_html()

    return app


def _frontend_index_html() -> str:
    frontend_index = FRONTEND_DIST / "index.html"
    if frontend_index.exists():
        return frontend_index.read_text(encoding="utf-8")
    return WEB_INDEX.read_text(encoding="utf-8")


app = create_app()

__all__ = ["app", "create_app"]
