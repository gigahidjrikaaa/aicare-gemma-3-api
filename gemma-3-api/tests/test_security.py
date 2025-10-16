import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import Request

from app.config.settings import Settings
from app.security.api_key import enforce_websocket_api_key, require_api_key


class DummyWebSocket:
    def __init__(self, headers: Headers) -> None:
        self.headers = headers
        self.closed = False
        self.close_args: list[tuple[int, str]] = []

    async def close(self, code: int, reason: str) -> None:
        self.closed = True
        self.close_args.append((code, reason))


def _build_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()
        ],
    }
    return Request(scope)


def test_require_api_key_noop_when_disabled() -> None:
    request = _build_request({})
    settings = Settings(api_key_enabled=False)
    require_api_key(request, settings=settings)  # Should not raise


def test_require_api_key_rejects_missing_header() -> None:
    request = _build_request({})
    settings = Settings(api_key_enabled=True, api_keys=["secret"])
    with pytest.raises(HTTPException) as exc:
        require_api_key(request, settings=settings)
    assert exc.value.status_code == 401


def test_require_api_key_accepts_valid_header() -> None:
    request = _build_request({"X-API-Key": "secret"})
    settings = Settings(api_key_enabled=True, api_keys=["secret"])
    require_api_key(request, settings=settings)


@pytest.mark.asyncio
async def test_websocket_enforcement_closes_on_missing_key() -> None:
    websocket = DummyWebSocket(Headers({}))
    settings = Settings(api_key_enabled=True, api_keys=["secret"])

    authorised = await enforce_websocket_api_key(websocket, settings=settings)

    assert authorised is False
    assert websocket.closed is True
    assert websocket.close_args[0][0] == 4401


@pytest.mark.asyncio
async def test_websocket_enforcement_allows_valid_key() -> None:
    websocket = DummyWebSocket(Headers({"X-API-Key": "secret"}))
    settings = Settings(api_key_enabled=True, api_keys=["secret"])

    authorised = await enforce_websocket_api_key(websocket, settings=settings)

    assert authorised is True
    assert websocket.closed is False
