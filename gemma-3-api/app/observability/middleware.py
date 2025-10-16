"""ASGI middleware for request context management and metrics."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.settings import Settings
from app.observability.logging import bind_request_id, reset_request_id
from app.observability.metrics import record_http_request

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request identifiers, emit structured logs and record metrics."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(self._settings.request_id_header) or str(uuid.uuid4())
        token = bind_request_id(request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        route = getattr(request.scope.get("route"), "path", request.url.path)
        method = request.method

        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            record_http_request(method, route, 500, duration)
            logger.exception(
                "Unhandled exception during request",
                extra={"method": method, "route": route, "status_code": 500, "duration_ms": duration * 1000},
            )
            raise
        else:
            duration = time.perf_counter() - start
            status_code = getattr(response, "status_code", 500)
            record_http_request(method, route, status_code, duration)
            response.headers.setdefault(self._settings.request_id_header, request_id)
            logger.info(
                "Request processed",
                extra={
                    "method": method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return response
        finally:
            reset_request_id(token)
