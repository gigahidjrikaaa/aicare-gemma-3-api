"""Application configuration and environment management."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings.

    Phase 1 introduces placeholders for upcoming speech integrations while
    preserving backwards compatibility with the existing text endpoints.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Core service metadata
    api_title: str = Field(default="Gemma 3 API Service", description="Human readable API title")
    api_version: str = Field(default="1.0.0", description="Semantic version exposed by FastAPI")
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level used for application loggers.",
    )
    request_id_header: str = Field(
        default="X-Request-ID",
        alias="REQUEST_ID_HEADER",
        description="HTTP header used to propagate the request identifier.",
    )

    # API security configuration
    api_key_enabled: bool = Field(
        default=False,
        alias="API_KEY_ENABLED",
        description="Enable API key enforcement on incoming requests.",
    )
    api_key_header_name: str = Field(
        default="X-API-Key",
        alias="API_KEY_HEADER_NAME",
        description="HTTP header name checked for API key authentication.",
    )
    api_keys: list[str] = Field(
        default_factory=list,
        alias="API_KEYS",
        description="Comma separated list of valid API keys.",
    )
    rate_limit_enabled: bool = Field(
        default=False,
        alias="RATE_LIMIT_ENABLED",
        description="Enable global rate limiting for REST and WebSocket clients.",
    )
    rate_limit_requests: PositiveInt = Field(
        default=120,
        alias="RATE_LIMIT_REQUESTS",
        description="Number of allowed requests per sliding window before throttling.",
    )
    rate_limit_window_seconds: PositiveFloat = Field(
        default=60.0,
        alias="RATE_LIMIT_WINDOW_SECONDS",
        description="Duration in seconds of the rolling window applied to rate limits.",
    )
    rate_limit_burst_multiplier: PositiveFloat = Field(
        default=1.0,
        alias="RATE_LIMIT_BURST_MULTIPLIER",
        description="Multiplier applied to the base allowance to accommodate short bursts.",
    )

    # Hugging Face / LLM configuration
    llm_repo_id: str = Field(
        default="google/gemma-3-12b-it-qat-q4_0-gguf",
        description="Repository identifier for the default Gemma GGUF checkpoint.",
    )
    llm_model_filename: str = Field(
        default="gemma-3-12b-it-q4_0.gguf",
        description="Filename of the quantised GGUF model to download from Hugging Face.",
    )
    hugging_face_hub_token: Optional[str] = Field(
        default=None,
        alias="HUGGING_FACE_HUB_TOKEN",
        description="Optional access token for private Hugging Face repositories.",
    )
    llm_gpu_layers: int = Field(
        default=-1,
        description="Number of model layers to place on the GPU (-1 uses all available layers).",
    )
    llm_batch_size: PositiveInt = Field(
        default=2048,
        alias="LLM_BATCH_SIZE",
        description="Batch size forwarded to llama.cpp during inference.",
    )
    llm_n_threads: PositiveInt = Field(
        default=10,
        alias="LLM_N_THREADS",
        description="Number of CPU threads used by llama.cpp for residual work.",
    )
    llm_context_size: PositiveInt = Field(
        default=32768,
        alias="LLM_CONTEXT_SIZE",
        description="Maximum context window forwarded to llama.cpp.",
    )

    # Speech configuration (Phase 2 integrations)
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY",
        description="API key for upcoming OpenAI Whisper integrations.",
    )
    openai_api_base: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_BASE",
        description="Optional override for the OpenAI API base URL (useful for proxies).",
    )
    openai_timeout_seconds: PositiveFloat = Field(
        default=60.0,
        alias="OPENAI_TIMEOUT_SECONDS",
        description="Network timeout applied to Whisper API requests.",
    )
    openai_whisper_model: str = Field(
        default="gpt-4o-mini-transcribe",
        alias="OPENAI_WHISPER_MODEL",
        description="Default Whisper-compatible model deployed via the OpenAI API.",
    )
    openai_whisper_response_format: str = Field(
        default="verbose_json",
        alias="OPENAI_WHISPER_RESPONSE_FORMAT",
        description="Preferred transcription response format returned by Whisper.",
    )
    higgs_api_key: Optional[str] = Field(
        default=None,
        alias="HIGGS_API_KEY",
        description="Authentication token for the planned Higgs Audio V2 service.",
    )
    higgs_api_base: str = Field(
        default="http://localhost:8000/v1",
        alias="HIGGS_API_BASE",
        description="Base URL for the Higgs Audio V2 OpenAI-compatible deployment.",
    )
    higgs_speech_path: str = Field(
        default="/audio/speech",
        alias="HIGGS_SPEECH_PATH",
        description="Path component for the Higgs Audio speech synthesis endpoint.",
    )
    higgs_model_id: str = Field(
        default="higgs-audio-v2-generation-3B-base",
        alias="HIGGS_MODEL_ID",
        description="Identifier of the default Higgs Audio model to request when none is provided.",
    )
    higgs_default_voice: str = Field(
        default="en_woman",
        alias="HIGGS_DEFAULT_VOICE",
        description="Fallback voice preset forwarded to the Higgs Audio API.",
    )
    higgs_response_format: str = Field(
        default="pcm",
        alias="HIGGS_RESPONSE_FORMAT",
        description="Audio container/codec requested from Higgs Audio by default.",
    )
    higgs_timeout_seconds: PositiveFloat = Field(
        default=120.0,
        alias="HIGGS_TIMEOUT_SECONDS",
        description="Network timeout applied to Higgs Audio synthesis requests.",
    )
    higgs_max_retries: PositiveInt = Field(
        default=3,
        alias="HIGGS_MAX_RETRIES",
        description="Number of retry attempts for recoverable Higgs Audio errors.",
    )
    default_audio_sample_rate: PositiveInt = Field(
        default=16000,
        alias="DEFAULT_AUDIO_SAMPLE_RATE",
        description="Default PCM sample rate expected by the speech pipeline.",
    )
    enable_local_whisper: bool = Field(
        default=False,
        alias="ENABLE_LOCAL_WHISPER",
        description="Feature flag toggling local Whisper inference vs hosted APIs.",
    )
    local_whisper_model: str = Field(
        default="base",
        alias="LOCAL_WHISPER_MODEL",
        description="Model identifier used when running Whisper locally (e.g. tiny, base, large-v3).",
    )

    @field_validator("api_keys", mode="before")
    @classmethod
    def _split_api_keys(cls, value: Optional[str | list[str]]) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [item for item in value if item]
        raise TypeError("Invalid value for API_KEYS")


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()

