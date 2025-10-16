"""Client wrapper for the Higgs Audio V2 text-to-speech service."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, Optional

import httpx

from app.config.settings import Settings
from app.observability.metrics import record_external_call

logger = logging.getLogger(__name__)


def _media_type_for_format(response_format: str) -> str:
    mapping = {
        "pcm": "audio/pcm",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }
    return mapping.get(response_format.lower(), "application/octet-stream")


@dataclass(slots=True)
class HiggsSynthesisResult:
    """Blocking synthesis payload."""

    audio: bytes
    response_format: str
    sample_rate: int
    voice: str
    model: str
    media_type: str

    def as_base64(self) -> str:
        return base64.b64encode(self.audio).decode("ascii")


@dataclass(slots=True)
class HiggsSynthesisStream:
    """Streaming synthesis payload."""

    iterator_factory: Callable[[], AsyncIterator[bytes]]
    response_format: str
    sample_rate: int
    voice: str
    model: str
    media_type: str


class HiggsAudioService:
    """Adapter used to interact with a running Higgs Audio deployment."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def startup(self) -> None:
        """Initialise the HTTP client."""

        timeout = httpx.Timeout(self._settings.higgs_timeout_seconds)
        self._client = httpx.AsyncClient(
            base_url=self._settings.higgs_api_base,
            timeout=timeout,
        )
        logger.info("Initialised Higgs Audio client with timeout %.1fs", self._settings.higgs_timeout_seconds)

    async def shutdown(self) -> None:
        """Close the HTTP client."""

        async with self._client_lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    async def synthesize(
        self,
        *,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
        style: Optional[str] = None,
    ) -> HiggsSynthesisResult:
        """Perform blocking TTS synthesis."""

        client = await self._require_client()
        payload = self._build_payload(
            text=text,
            voice=voice,
            model=model,
            response_format=response_format,
            sample_rate=sample_rate,
            speed=speed,
            style=style,
        )

        headers = self._auth_headers()
        logger.debug("Requesting Higgs Audio synthesis: model=%s voice=%s", payload["model"], payload["voice"])
        start = time.perf_counter()
        try:
            response = await client.post(
                self._settings.higgs_speech_path,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            logger.exception("Higgs Audio synthesis failed")
            record_external_call("higgs_synthesize", time.perf_counter() - start, success=False)
            raise RuntimeError("Higgs Audio synthesis failed") from exc

        media_type = response.headers.get("content-type", "application/octet-stream")
        if "application/json" in media_type:
            data = response.json()
            audio_field = data.get("audio") or data.get("audio_base64")
            if not audio_field:
                raise RuntimeError("Higgs Audio response missing audio payload")
            audio_bytes = base64.b64decode(audio_field)
            sample_rate_val = data.get(
                "sample_rate",
                payload.get("sample_rate", self._settings.default_audio_sample_rate),
            )
            response_format_val = data.get("response_format", payload.get("response_format", self._settings.higgs_response_format))
            media_type = _media_type_for_format(response_format_val)
        else:
            audio_bytes = await response.aread()
            sample_rate_header = response.headers.get(
                "x-sample-rate",
                payload.get("sample_rate", self._settings.default_audio_sample_rate),
            )
            try:
                sample_rate_val = int(sample_rate_header)
            except (TypeError, ValueError):  # pragma: no cover - malformed headers
                logger.warning("Falling back to default sample rate due to malformed header: %s", sample_rate_header)
                sample_rate_val = self._settings.default_audio_sample_rate
            response_format_val = payload.get("response_format", self._settings.higgs_response_format)

        try:
            sample_rate_int = int(sample_rate_val)
        except (TypeError, ValueError):  # pragma: no cover - malformed payload
            logger.warning("Invalid sample rate '%s' detected; defaulting to %s", sample_rate_val, self._settings.default_audio_sample_rate)
            sample_rate_int = self._settings.default_audio_sample_rate

        record_external_call("higgs_synthesize", time.perf_counter() - start, success=True)

        return HiggsSynthesisResult(
            audio=audio_bytes,
            response_format=response_format_val,
            sample_rate=sample_rate_int,
            voice=payload["voice"],
            model=payload["model"],
            media_type=media_type,
        )

    async def synthesize_stream(
        self,
        *,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        sample_rate: Optional[int] = None,
        speed: Optional[float] = None,
        style: Optional[str] = None,
    ) -> HiggsSynthesisStream:
        """Return an asynchronous iterator that streams synthesis bytes."""

        client = await self._require_client()
        payload = self._build_payload(
            text=text,
            voice=voice,
            model=model,
            response_format=response_format,
            sample_rate=sample_rate,
            speed=speed,
            style=style,
        )
        # Explicitly request streamed audio chunks from the upstream API. The Higgs
        # Audio OpenAI-compatible server follows the same contract as OpenAI's TTS
        # endpoint which requires ``stream=true`` to deliver incremental bytes.
        payload["stream"] = True
        headers = self._auth_headers()

        async def iterator() -> AsyncIterator[bytes]:
            retries = self._settings.higgs_max_retries
            attempt = 0
            while True:
                attempt += 1
                try:
                    start = time.perf_counter()
                    async with client.stream(
                        "POST",
                        self._settings.higgs_speech_path,
                        json=payload,
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk
                    record_external_call("higgs_stream", time.perf_counter() - start, success=True)
                    break
                except httpx.HTTPError as exc:  # pragma: no cover - network instability
                    record_external_call("higgs_stream", time.perf_counter() - start, success=False)
                    if attempt > retries:
                        logger.exception("Streaming synthesis failed after %s attempts", attempt)
                        raise RuntimeError("Higgs Audio streaming synthesis failed") from exc
                    backoff = min(2 ** attempt, 10)
                    logger.warning("Streaming synthesis error (attempt %s/%s), retrying in %ss", attempt, retries, backoff)
                    await asyncio.sleep(backoff)

        response_format_val = payload.get("response_format", self._settings.higgs_response_format)
        sample_rate_val = payload.get("sample_rate", self._settings.default_audio_sample_rate)
        return HiggsSynthesisStream(
            iterator_factory=iterator,
            response_format=response_format_val,
            sample_rate=int(sample_rate_val),
            voice=payload["voice"],
            model=payload["model"],
            media_type=_media_type_for_format(response_format_val),
        )

    async def _require_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None:
                await self.startup()
            assert self._client is not None
            return self._client

    def _build_payload(
        self,
        *,
        text: str,
        voice: Optional[str],
        model: Optional[str],
        response_format: Optional[str],
        sample_rate: Optional[int],
        speed: Optional[float],
        style: Optional[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "input": text,
            "voice": voice or self._settings.higgs_default_voice,
            "model": model or self._settings.higgs_model_id,
            "response_format": response_format or self._settings.higgs_response_format,
            "sample_rate": sample_rate or self._settings.default_audio_sample_rate,
        }
        if speed is not None:
            payload["speed"] = speed
        if style:
            payload["style"] = style
        return payload

    def _auth_headers(self) -> Dict[str, str]:
        if not self._settings.higgs_api_key:
            return {}
        return {"Authorization": f"Bearer {self._settings.higgs_api_key}"}
