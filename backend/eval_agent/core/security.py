from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.eval_agent.core.config import settings_from_env


class ApiTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not request.url.path.startswith("/api/") or request.url.path == "/api/health":
            return await call_next(request)

        expected = settings_from_env().access_token
        if not expected:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        if not supplied:
            supplied = request.headers.get("x-api-key", "").strip()

        if not supplied or not secrets.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "A valid access token is required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
