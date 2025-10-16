"""Logging helpers that provide structured request identifiers."""

from __future__ import annotations

import logging
from logging.config import dictConfig
from contextvars import ContextVar, Token

from app.config.settings import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject the current request id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - exercised indirectly
        record.request_id = _REQUEST_ID.get()
        return True


def bind_request_id(request_id: str) -> Token[str]:
    """Bind the provided request identifier in the current context."""

    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request identifier from a token."""

    _REQUEST_ID.reset(token)


def configure_logging(settings: Settings) -> None:
    """Configure application logging using the provided settings."""

    log_level = settings.log_level.upper()
    request_filter = RequestIdFilter()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["request_id"],
                }
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": log_level,
                },
                "uvicorn": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )

    logging.getLogger(__name__).debug("Logging configured at level %s", log_level)

    # Ensure the filter is registered on the root logger so custom handlers inherit it.
    logging.getLogger().addFilter(request_filter)
