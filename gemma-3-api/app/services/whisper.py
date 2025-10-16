"""Service wrapper around OpenAI Whisper and optional local inference."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.settings import Settings
from app.observability.metrics import record_external_call

try:  # pragma: no cover - optional dependency
    from openai import AsyncOpenAI
    from openai import APIError as OpenAIAPIError
except ImportError:  # pragma: no cover - handled gracefully at runtime
    AsyncOpenAI = None  # type: ignore[assignment]
    OpenAIAPIError = Exception  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WhisperTranscriptionSegment:
    """Normalized representation of a transcription segment."""

    id: Optional[int]
    start: Optional[float]
    end: Optional[float]
    text: str


@dataclass(slots=True)
class WhisperTranscription:
    """Container returned by the Whisper service."""

    text: str
    language: Optional[str]
    segments: List[WhisperTranscriptionSegment]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WhisperTranscription":
        segments_data = payload.get("segments") or []
        segments = [
            WhisperTranscriptionSegment(
                id=segment.get("id"),
                start=segment.get("start"),
                end=segment.get("end"),
                text=segment.get("text", ""),
            )
            for segment in segments_data
        ]
        return cls(text=payload.get("text", ""), language=payload.get("language"), segments=segments)


class WhisperService:
    """High-level speech-to-text adapter supporting remote and local inference."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional[AsyncOpenAI] = None
        self._local_model: Any | None = None
        self._local_model_lock = asyncio.Lock()

    async def startup(self) -> None:
        """Initialise the configured Whisper backend."""

        if self._settings.enable_local_whisper:
            await self._load_local_model()
            return

        if self._settings.openai_api_key is None:
            logger.warning("WhisperService configured without API key; remote transcription disabled")
            return

        if AsyncOpenAI is None:  # pragma: no cover - dependency is optional
            raise RuntimeError("The 'openai' package is required for remote Whisper usage.")

        timeout = self._settings.openai_timeout_seconds
        self._client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_api_base,
            timeout=timeout,
        )
        logger.info("Initialised AsyncOpenAI Whisper client with timeout %.1fs", timeout)

    async def shutdown(self) -> None:
        """Release any allocated resources."""

        self._client = None
        self._local_model = None

    @property
    def is_ready(self) -> bool:
        """Return True when a backend is available."""

        return bool(self._client or self._local_model)

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> WhisperTranscription:
        """Transcribe the provided audio payload."""

        if self._settings.enable_local_whisper:
            start = time.perf_counter()
            try:
                result = await self._transcribe_locally(
                    audio_bytes,
                    language=language,
                    prompt=prompt,
                    temperature=temperature,
                )
            except Exception:
                record_external_call("whisper_local", time.perf_counter() - start, success=False)
                raise
            record_external_call("whisper_local", time.perf_counter() - start, success=True)
            return result

        if self._client is None:
            raise RuntimeError("Whisper remote backend is not configured.")

        file_tuple = (filename, audio_bytes, content_type or "application/octet-stream")
        request_kwargs: Dict[str, Any] = {
            "model": self._settings.openai_whisper_model,
            "file": file_tuple,
            "response_format": response_format or self._settings.openai_whisper_response_format,
        }
        if language:
            request_kwargs["language"] = language
        if prompt:
            request_kwargs["prompt"] = prompt
        if temperature is not None:
            request_kwargs["temperature"] = temperature

        logger.debug("Dispatching Whisper transcription via OpenAI: model=%s", request_kwargs["model"])

        start = time.perf_counter()
        try:
            response = await self._client.audio.transcriptions.create(**request_kwargs)
        except OpenAIAPIError as exc:  # pragma: no cover - network failure
            logger.exception("Remote Whisper transcription failed")
            record_external_call("whisper_remote", time.perf_counter() - start, success=False)
            raise RuntimeError("Remote Whisper transcription failed") from exc

        payload = response if isinstance(response, dict) else response.model_dump()
        record_external_call("whisper_remote", time.perf_counter() - start, success=True)
        return WhisperTranscription.from_dict(payload)

    async def _load_local_model(self) -> None:
        """Load Whisper locally in a background thread."""

        try:
            import whisper  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Local Whisper inference requested but the 'whisper' package is not installed."
            ) from exc

        model_name = self._settings.local_whisper_model
        async with self._local_model_lock:
            if self._local_model is not None:
                return
            logger.info("Loading local Whisper model '%s'", model_name)
            self._local_model = await asyncio.to_thread(whisper.load_model, model_name)

    async def _transcribe_locally(
        self,
        audio_bytes: bytes,
        *,
        language: Optional[str],
        prompt: Optional[str],
        temperature: Optional[float],
    ) -> WhisperTranscription:
        """Run the locally loaded Whisper model against the audio payload."""

        if self._local_model is None:
            await self._load_local_model()

        assert self._local_model is not None  # for type-checkers

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = Path(tmp_file.name)

        try:
            kwargs: Dict[str, Any] = {}
            if language:
                kwargs["language"] = language
            if prompt:
                kwargs["prompt"] = prompt
            if temperature is not None:
                kwargs["temperature"] = temperature

            model_name = getattr(self._local_model, "model_name", "local-whisper")
            logger.debug("Dispatching Whisper transcription locally: model=%s", model_name)
            result: Dict[str, Any] = await asyncio.to_thread(self._local_model.transcribe, str(tmp_path), **kwargs)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - best effort cleanup
                logger.warning("Failed to remove temporary audio file at %s", tmp_path)

        return WhisperTranscription.from_dict(result)
