"""In-process rate limiting utilities for REST and WebSocket handlers."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Tuple

from fastapi import Depends, HTTPException, Request, status
from starlette.websockets import WebSocket

from app.config.settings import Settings
from app.observability import record_rate_limit_rejection


@dataclass
class _TokenBucket:
    tokens: float
    last_refill: float


class RateLimiter:
    """A simple token-bucket rate limiter with async safety."""

    def __init__(self, *, settings: Settings) -> None:
        self.enabled = settings.rate_limit_enabled
        self._api_key_header = settings.api_key_header_name
        raw_capacity = float(settings.rate_limit_requests) * float(
            settings.rate_limit_burst_multiplier
        )
        self._capacity = max(1.0, raw_capacity)
        window = float(settings.rate_limit_window_seconds)
        self._refill_rate = self._capacity / window if window > 0 else float("inf")
        self._bucket_ttl = window * 5
        self._lock = asyncio.Lock()
        self._buckets: dict[str, _TokenBucket] = {}

    async def acquire(self, identifier: str, scope: str) -> Tuple[bool, float]:
        """Attempt to consume a single token for ``identifier``."""

        if not self.enabled or self._capacity <= 0:
            return True, 0.0

        now = time.monotonic()
        bucket_key = f"{scope}:{identifier}"

        async with self._lock:
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = _TokenBucket(tokens=self._capacity, last_refill=now)
            else:
                elapsed = max(0.0, now - bucket.last_refill)
                bucket.tokens = min(
                    self._capacity, bucket.tokens + (elapsed * self._refill_rate)
                )
                bucket.last_refill = now

            allowed = bucket.tokens >= 1.0
            if allowed:
                bucket.tokens -= 1.0
            self._buckets[bucket_key] = bucket

            self._cleanup_locked(now)

            if allowed:
                return True, 0.0

            retry_after = 0.0
            if self._refill_rate > 0:
                retry_after = max(0.0, (1.0 - bucket.tokens) / self._refill_rate)

        record_rate_limit_rejection(scope)
        return False, retry_after

    def identifier_from_request(self, request: Request) -> Tuple[str, str]:
        """Derive the rate limit bucket identifier for an HTTP request."""

        header_value = self._extract_header(request.headers.get)
        if header_value:
            return header_value, "api_key"

        client_host = getattr(request.client, "host", "anonymous")
        return client_host or "anonymous", "ip"

    def identifier_from_websocket(self, websocket: WebSocket) -> Tuple[str, str]:
        """Derive the identifier for WebSocket clients."""

        header_value = self._extract_header(websocket.headers.get)
        if header_value:
            return header_value, "api_key"

        client = getattr(websocket, "client", None)
        client_host = getattr(client, "host", "anonymous") if client else "anonymous"
        return client_host or "anonymous", "ip"

    def _extract_header(self, getter: Callable[[str], str | None]) -> str | None:
        if not self._api_key_header:
            return None
        return getter(self._api_key_header)

    def _cleanup_locked(self, now: float) -> None:
        if self._bucket_ttl <= 0:
            return
        expired_keys = [
            key
            for key, bucket in self._buckets.items()
            if (now - bucket.last_refill) > self._bucket_ttl
        ]
        for key in expired_keys:
            self._buckets.pop(key, None)


def get_rate_limiter_from_request(request: Request) -> RateLimiter | None:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if isinstance(limiter, RateLimiter):
        return limiter
    return None


async def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter | None = Depends(get_rate_limiter_from_request),
) -> None:
    """FastAPI dependency that rejects requests once the quota is exhausted."""

    if limiter is None or not limiter.enabled:
        return

    identifier, scope = limiter.identifier_from_request(request)
    allowed, retry_after = await limiter.acquire(identifier, scope)
    if allowed:
        return

    retry_after_header = str(int(math.ceil(retry_after))) if retry_after > 0 else "1"
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please retry later.",
        headers={"Retry-After": retry_after_header},
    )


async def enforce_websocket_rate_limit(
    websocket: WebSocket,
    limiter: RateLimiter | None = None,
) -> bool:
    """Guard WebSocket connections behind the shared rate limiter."""

    if limiter is None:
        app = getattr(websocket, "app", None)
        state = getattr(app, "state", SimpleNamespace()) if app else SimpleNamespace()
        limiter = getattr(state, "rate_limiter", None)

    if limiter is None or not limiter.enabled:
        return True

    identifier, scope = limiter.identifier_from_websocket(websocket)
    allowed, _ = await limiter.acquire(identifier, scope)
    if allowed:
        return True

    await websocket.close(code=4429, reason="Rate limit exceeded")
    return False

