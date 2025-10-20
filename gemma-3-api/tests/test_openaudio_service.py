from typing import Any, AsyncIterator, Dict, List

import pytest

from typing import Any, AsyncIterator, Dict, List

import pytest

from app.config.settings import Settings
from app.services.openaudio import OpenAudioService


class _DummyStreamResponse:
    def __init__(self, chunks: List[bytes]) -> None:
        self._chunks = chunks

    async def __aenter__(self) -> "_DummyStreamResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup required
        return None

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk

    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def stream(self, method: str, path: str, *, json: Dict[str, Any], headers: Dict[str, str]):
        self.calls.append({"method": method, "path": path, "json": json, "headers": headers})
        return _DummyStreamResponse(chunks=[b"chunk-1", b"chunk-2"])


@pytest.mark.asyncio
async def test_synthesize_stream_sets_stream_flag() -> None:
    settings = Settings(
        openaudio_api_base="http://localhost:8080",
        openaudio_tts_path="/v1/tts",
        openaudio_max_retries=1,
    )
    service = OpenAudioService(settings=settings)

    # Inject a fake client to avoid real network calls.
    fake_client = _FakeAsyncClient()
    service._client = fake_client  # type: ignore[attr-defined]

    stream = await service.synthesize_stream(text="hello world")

    collected = []
    async for chunk in stream.iterator_factory():
        collected.append(chunk)

    assert collected == [b"chunk-1", b"chunk-2"]
    assert fake_client.calls  # ensure at least one request was made
    request_payload = fake_client.calls[0]["json"]
    assert request_payload.get("streaming") is True

