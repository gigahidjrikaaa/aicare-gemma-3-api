from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from app.config.settings import Settings
from app.security.rate_limiter import (
    RateLimiter,
    enforce_rate_limit,
    enforce_websocket_rate_limit,
)


def _build_request(
    headers: dict[str, str] | None,
    *,
    host: str = "127.0.0.1",
    limiter: RateLimiter,
) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/test",
        "headers": encoded_headers,
        "client": (host, 1234),
        "app": SimpleNamespace(state=SimpleNamespace(rate_limiter=limiter)),
    }
    return Request(scope)


class DummyWebSocket:
    def __init__(self, headers: dict[str, str], limiter: RateLimiter, host: str = "127.0.0.1") -> None:
        self.headers = Headers(headers)
        self.client = SimpleNamespace(host=host, port=1234)
        self.app = SimpleNamespace(state=SimpleNamespace(rate_limiter=limiter))
        self.closed = False
        self.close_args: list[tuple[int, str]] = []

    async def close(self, code: int, reason: str) -> None:
        self.closed = True
        self.close_args.append((code, reason))


@pytest.mark.asyncio
async def test_rate_limiter_rejects_when_budget_exhausted() -> None:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    limiter = RateLimiter(settings=settings)
    request = _build_request({}, limiter=limiter)

    await enforce_rate_limit(request, limiter=limiter)

    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit(request, limiter=limiter)

    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_rate_limiter_isolated_per_api_key() -> None:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    limiter = RateLimiter(settings=settings)

    await enforce_rate_limit(_build_request({"X-API-Key": "alpha"}, limiter=limiter), limiter=limiter)
    # Different API key should have its own bucket and succeed.
    await enforce_rate_limit(_build_request({"X-API-Key": "beta"}, limiter=limiter), limiter=limiter)


@pytest.mark.asyncio
async def test_websocket_rate_limiter_closes_on_rejection() -> None:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )
    limiter = RateLimiter(settings=settings)
    websocket = DummyWebSocket({}, limiter)

    allowed_initial = await enforce_websocket_rate_limit(websocket, limiter=limiter)
    assert allowed_initial is True

    allowed_second = await enforce_websocket_rate_limit(websocket, limiter=limiter)
    assert allowed_second is False
    assert websocket.closed is True
    assert websocket.close_args[-1][0] == 4429
