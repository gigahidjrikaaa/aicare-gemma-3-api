"""Prometheus metrics utilities."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

logger = logging.getLogger(__name__)

_http_request_latency = Histogram(
    "app_http_request_duration_seconds",
    "Latency of processed HTTP requests",
    labelnames=("method", "route"),
)
_http_request_total = Counter(
    "app_http_requests_total",
    "Total number of processed HTTP requests",
    labelnames=("method", "route", "status"),
)
_http_request_errors = Counter(
    "app_http_request_errors_total",
    "Total number of HTTP requests that raised server errors",
    labelnames=("method", "route", "status"),
)
_external_call_latency = Histogram(
    "app_external_call_duration_seconds",
    "Duration of external service interactions",
    labelnames=("service",),
)
_external_call_errors = Counter(
    "app_external_call_errors_total",
    "Number of failed external service interactions",
    labelnames=("service",),
)
_pipeline_latency = Histogram(
    "app_pipeline_duration_seconds",
    "Duration of high-level pipeline orchestrations",
    labelnames=("pipeline",),
)
_pipeline_errors = Counter(
    "app_pipeline_errors_total",
    "Number of failed high-level pipeline orchestrations",
    labelnames=("pipeline",),
)
_rate_limit_rejections = Counter(
    "app_rate_limit_rejections_total",
    "Number of requests rejected by rate limiting",
    labelnames=("scope",),
)


def _normalise_route(route: Optional[str]) -> str:
    if not route:
        return "unknown"
    return route


def record_http_request(method: str, route: Optional[str], status_code: int, duration_seconds: float) -> None:
    """Record metrics for a handled HTTP request."""

    normalized_route = _normalise_route(route)
    _http_request_latency.labels(method=method, route=normalized_route).observe(duration_seconds)
    status_str = str(status_code)
    _http_request_total.labels(method=method, route=normalized_route, status=status_str).inc()
    if status_code >= 500:
        _http_request_errors.labels(method=method, route=normalized_route, status=status_str).inc()


def record_external_call(service: str, duration_seconds: float, *, success: bool) -> None:
    """Record metrics for a call to an external dependency."""

    _external_call_latency.labels(service=service).observe(duration_seconds)
    if not success:
        _external_call_errors.labels(service=service).inc()


def record_pipeline(pipeline: str, duration_seconds: float, *, success: bool) -> None:
    """Record metrics for a full orchestration pipeline."""

    _pipeline_latency.labels(pipeline=pipeline).observe(duration_seconds)
    if not success:
        _pipeline_errors.labels(pipeline=pipeline).inc()


def record_rate_limit_rejection(scope: str) -> None:
    """Increment the counter for throttled requests."""

    _rate_limit_rejections.labels(scope=scope).inc()


def register_metrics_endpoint(app: FastAPI) -> None:
    """Expose a Prometheus scrape endpoint on ``/metrics``."""

    @app.get("/metrics")
    async def metrics_endpoint() -> Response:  # pragma: no cover - exercised in integration tests
        payload = generate_latest()
        return Response(payload, media_type=CONTENT_TYPE_LATEST)

    logger.info("Registered /metrics endpoint for Prometheus scraping")
