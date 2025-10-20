"""Client wrapper for the OpenAudio-S1-mini text-to-speech service."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, Optional, Sequence

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
class OpenAudioSynthesisResult:
    """Blocking synthesis payload."""

    audio: bytes
    response_format: str
    sample_rate: int
    reference_id: Optional[str]
    media_type: str

    def as_base64(self) -> str:
        return base64.b64encode(self.audio).decode("ascii")


@dataclass(slots=True)
class OpenAudioSynthesisStream:
    """Streaming synthesis payload."""

    iterator_factory: Callable[[], AsyncIterator[bytes]]
    response_format: str
    sample_rate: int
    reference_id: Optional[str]
    media_type: str


class OpenAudioService:
    """Adapter used to interact with a running OpenAudio deployment."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def startup(self) -> None:
        """Initialise the HTTP client."""

        timeout = httpx.Timeout(self._settings.openaudio_timeout_seconds)
        self._client = httpx.AsyncClient(
            base_url=self._settings.openaudio_api_base,
            timeout=timeout,
        )
        logger.info(
            "Initialised OpenAudio client with timeout %.1fs",
            self._settings.openaudio_timeout_seconds,
        )

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
        response_format: Optional[str] = None,
        sample_rate: Optional[int] = None,
        reference_id: Optional[str] = None,
        normalize: Optional[bool] = None,
        references: Optional[Sequence[str]] = None,
        top_p: Optional[float] = None,
    ) -> OpenAudioSynthesisResult:
        """Perform blocking TTS synthesis."""

        client = await self._require_client()
        payload = self._build_payload(
            text=text,
            response_format=response_format,
            sample_rate=sample_rate,
            reference_id=reference_id,
            normalize=normalize,
            references=references,
            top_p=top_p,
        )

        headers = self._auth_headers()
        logger.debug(
            "Requesting OpenAudio synthesis: format=%s reference_id=%s",
            payload.get("format"),
            payload.get("reference_id"),
        )
        start = time.perf_counter()
        try:
            response = await client.post(
                self._settings.openaudio_tts_path,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            logger.exception("OpenAudio synthesis failed")
            record_external_call("openaudio_synthesize", time.perf_counter() - start, success=False)
            raise RuntimeError("OpenAudio synthesis failed") from exc

        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            audio_b64 = data.get("audio") or data.get("audio_base64")
            if not audio_b64:
                raise RuntimeError("OpenAudio response missing audio payload")
            audio_bytes = base64.b64decode(audio_b64)
            response_format_val = data.get("format", payload.get("format"))
            sample_rate_val = data.get("sample_rate") or payload.get(
                "sample_rate", self._settings.default_audio_sample_rate
            )
        else:
            audio_bytes = await response.aread()
            response_format_val = payload.get("format", self._settings.openaudio_default_format)
            sample_rate_header = response.headers.get(
                "x-sample-rate",
                payload.get("sample_rate", self._settings.default_audio_sample_rate),
            )
            try:
                sample_rate_val = int(sample_rate_header)
            except (TypeError, ValueError):  # pragma: no cover - malformed headers
                logger.warning(
                    "Falling back to default sample rate due to malformed header: %s",
                    sample_rate_header,
                )
                sample_rate_val = self._settings.default_audio_sample_rate

        try:
            sample_rate_int = int(sample_rate_val)
        except (TypeError, ValueError):  # pragma: no cover - malformed payload
            logger.warning(
                "Invalid sample rate '%s' detected; defaulting to %s",
                sample_rate_val,
                self._settings.default_audio_sample_rate,
            )
            sample_rate_int = self._settings.default_audio_sample_rate

        record_external_call("openaudio_synthesize", time.perf_counter() - start, success=True)

        return OpenAudioSynthesisResult(
            audio=audio_bytes,
            response_format=response_format_val,
            sample_rate=sample_rate_int,
            reference_id=payload.get("reference_id"),
            media_type=_media_type_for_format(response_format_val),
        )

    async def synthesize_stream(
        self,
        *,
        text: str,
        response_format: Optional[str] = None,
        sample_rate: Optional[int] = None,
        reference_id: Optional[str] = None,
        normalize: Optional[bool] = None,
        references: Optional[Sequence[str]] = None,
        top_p: Optional[float] = None,
    ) -> OpenAudioSynthesisStream:
        """Return an asynchronous iterator that streams synthesis bytes."""

        client = await self._require_client()
        payload = self._build_payload(
            text=text,
            response_format=response_format,
            sample_rate=sample_rate,
            reference_id=reference_id,
            normalize=normalize,
            references=references,
            top_p=top_p,
        )
        payload["streaming"] = True
        headers = self._auth_headers()

        async def iterator() -> AsyncIterator[bytes]:
            retries = self._settings.openaudio_max_retries
            attempt = 0
            while True:
                attempt += 1
                try:
                    start = time.perf_counter()
                    async with client.stream(
                        "POST",
                        self._settings.openaudio_tts_path,
                        json=payload,
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk
                    record_external_call("openaudio_stream", time.perf_counter() - start, success=True)
                    break
                except httpx.HTTPError as exc:  # pragma: no cover - network instability
                    record_external_call("openaudio_stream", time.perf_counter() - start, success=False)
                    if attempt > retries:
                        logger.exception("Streaming synthesis failed after %s attempts", attempt)
                        raise RuntimeError("OpenAudio streaming synthesis failed") from exc
                    backoff = min(2 ** attempt, 10)
                    logger.warning(
                        "Streaming synthesis error (attempt %s/%s), retrying in %ss",
                        attempt,
                        retries,
                        backoff,
                    )
                    await asyncio.sleep(backoff)

        response_format_val = payload.get("format", self._settings.openaudio_default_format)
        sample_rate_val = payload.get("sample_rate", self._settings.default_audio_sample_rate)
        return OpenAudioSynthesisStream(
            iterator_factory=iterator,
            response_format=response_format_val,
            sample_rate=int(sample_rate_val),
            reference_id=payload.get("reference_id"),
            media_type=_media_type_for_format(response_format_val),
        )

    async def _require_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None:
                await self.startup()
            assert self._client is not None
            return self._client

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._settings.openaudio_api_key:
            headers["Authorization"] = f"Bearer {self._settings.openaudio_api_key}"
        return headers

    def _build_payload(
        self,
        *,
        text: str,
        response_format: Optional[str],
        sample_rate: Optional[int],
        reference_id: Optional[str],
        normalize: Optional[bool],
        references: Optional[Sequence[str]],
        top_p: Optional[float],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "text": text,
            "format": response_format or self._settings.openaudio_default_format,
            "streaming": False,
        }

        chosen_reference = reference_id or self._settings.openaudio_default_reference_id
        if chosen_reference:
            payload["reference_id"] = chosen_reference
        if sample_rate is not None:
            payload["sample_rate"] = sample_rate
        if normalize is not None:
            payload["normalize"] = normalize
        else:
            payload["normalize"] = self._settings.openaudio_default_normalize
        if references:
            payload["references"] = list(references)
        if top_p is not None:
            payload["top_p"] = top_p

        return payload

