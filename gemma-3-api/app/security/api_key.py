"""API key authentication helpers."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, WebSocket

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def require_api_key(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency that enforces API key authentication when enabled."""

    if not settings.api_key_enabled:
        return

    provided_key = _extract_header(request.headers.get, settings.api_key_header_name)
    if provided_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    if provided_key not in settings.api_keys:
        logger.warning("Rejected request with invalid API key")
        raise HTTPException(status_code=403, detail="Invalid API key")


def _extract_header(getter, header_name: str) -> str | None:
    if not header_name:
        return None
    return getter(header_name)


async def enforce_websocket_api_key(
    websocket: WebSocket,
    *,
    settings: Settings | None = None,
) -> bool:
    """Verify API key authentication for WebSocket connections."""

    settings = settings or get_settings()
    if not settings.api_key_enabled:
        return True

    provided_key = _extract_header(websocket.headers.get, settings.api_key_header_name)
    if provided_key is None:
        await websocket.close(code=4401, reason="Missing API key")
        return False

    if provided_key not in settings.api_keys:
        logger.warning("Rejected WebSocket connection with invalid API key")
        await websocket.close(code=4403, reason="Invalid API key")
        return False

    return True
