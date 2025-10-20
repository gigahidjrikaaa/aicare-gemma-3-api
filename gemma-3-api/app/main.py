"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config.settings import Settings, get_settings
from app.observability import (
    RequestContextMiddleware,
    configure_logging,
    register_metrics_endpoint,
)
from app.security import RateLimiter
from app.services.conversation import ConversationService
from app.services.openaudio import OpenAudioService
from app.services.llm import LLMService
from app.services.whisper import WhisperService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")

    settings = get_settings()
    llm_service = LLMService(settings=settings)
    llm_service.startup()
    app.state.llm_service = llm_service

    whisper_service = WhisperService(settings=settings)
    await whisper_service.startup()
    app.state.whisper_service = whisper_service

    openaudio_service = OpenAudioService(settings=settings)
    await openaudio_service.startup()
    app.state.openaudio_service = openaudio_service

    rate_limiter = RateLimiter(settings=settings)
    app.state.rate_limiter = rate_limiter

    conversation_service = ConversationService(
        llm_service=llm_service,
        whisper_service=whisper_service,
        openaudio_service=openaudio_service,
    )
    app.state.conversation_service = conversation_service

    try:
        yield
    finally:
        logger.info("Application shutdown...")
        if hasattr(app.state, "conversation_service") and app.state.conversation_service is not None:
            app.state.conversation_service = None
        if hasattr(app.state, "openaudio_service") and app.state.openaudio_service is not None:
            await app.state.openaudio_service.shutdown()
            app.state.openaudio_service = None
        if hasattr(app.state, "whisper_service") and app.state.whisper_service is not None:
            await app.state.whisper_service.shutdown()
            app.state.whisper_service = None
        if hasattr(app.state, "rate_limiter") and app.state.rate_limiter is not None:
            app.state.rate_limiter = None
        llm_service.shutdown()
        app.state.llm_service = None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    configure_logging(settings)

    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware, settings=settings)
    application.include_router(api_router)
    register_metrics_endpoint(application)

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

