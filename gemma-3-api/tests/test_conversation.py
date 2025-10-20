import asyncio
from typing import AsyncIterator

import pytest

from app.services.conversation import ConversationService, DialogueResult, DialogueStreamResult
from app.services.openaudio import OpenAudioSynthesisResult, OpenAudioSynthesisStream
from app.services.whisper import WhisperTranscription, WhisperTranscriptionSegment


class FakeLLMService:
    def __init__(self, response_text: str = "Hello from Gemma") -> None:
        self._response_text = response_text
        self.model = self

    def __call__(self, **_: object) -> dict[str, object]:
        return {"choices": [{"text": self._response_text}]}


class FakeWhisperService:
    async def transcribe(self, *_: object, **__: object) -> WhisperTranscription:
        return WhisperTranscription(
            text="transcribed text",
            language="en",
            segments=[
                WhisperTranscriptionSegment(id=1, start=0.0, end=1.0, text="transcribed text"),
            ],
        )


class FakeOpenAudioService:
    def __init__(self) -> None:
        self._synthesis_calls: list[dict[str, object]] = []

    async def synthesize(self, *, text: str, **kwargs: object) -> OpenAudioSynthesisResult:
        self._synthesis_calls.append({"text": text, **kwargs})
        return OpenAudioSynthesisResult(
            audio=b"fake-bytes",
            response_format="pcm",
            sample_rate=16000,
            reference_id="demo-ref",
            media_type="audio/pcm",
        )

    async def synthesize_stream(self, *, text: str, **kwargs: object) -> OpenAudioSynthesisStream:
        self._synthesis_calls.append({"text": text, **kwargs})

        async def iterator() -> AsyncIterator[bytes]:
            yield b"chunk-1"
            yield b"chunk-2"

        return OpenAudioSynthesisStream(
            iterator_factory=iterator,
            response_format="pcm",
            sample_rate=16000,
            reference_id="demo-ref",
            media_type="audio/pcm",
        )


@pytest.mark.asyncio
async def test_run_dialogue_returns_compound_result() -> None:
    service = ConversationService(
        llm_service=FakeLLMService(),
        whisper_service=FakeWhisperService(),
        openaudio_service=FakeOpenAudioService(),
    )

    result = await service.run_dialogue(
        audio_bytes=b"bytes",
        filename="sample.wav",
        content_type="audio/wav",
        instructions="Be helpful",
        stream_audio=False,
    )

    assert isinstance(result, DialogueResult)
    assert result.transcription.text == "transcribed text"
    assert result.response_text == "Hello from Gemma"
    assert result.synthesis.media_type == "audio/pcm"
    assert result.synthesis.reference_id == "demo-ref"


@pytest.mark.asyncio
async def test_run_dialogue_streaming_returns_stream_container() -> None:
    service = ConversationService(
        llm_service=FakeLLMService(),
        whisper_service=FakeWhisperService(),
        openaudio_service=FakeOpenAudioService(),
    )

    result = await service.run_dialogue(
        audio_bytes=b"bytes",
        filename="sample.wav",
        content_type="audio/wav",
        instructions=None,
        stream_audio=True,
    )

    assert isinstance(result, DialogueStreamResult)
    chunks = [chunk async for chunk in result.synthesis_stream.iterator_factory()]
    assert chunks == [b"chunk-1", b"chunk-2"]


def test_generation_request_validation_handles_invalid_overrides() -> None:
    with pytest.raises(ValueError):
        ConversationService._build_generation_request(
            prompt="Hello",
            overrides={"max_tokens": "invalid"},
        )


def test_prepare_synthesis_kwargs_filters_reserved_fields() -> None:
    overrides = {
        "text": "ignored",
        "stream": True,
        "reference_id": "demo",
        "normalize": False,
        "top_p": 0.7,
        "format": "wav",
        "speed": None,
    }
    filtered = ConversationService._prepare_synthesis_kwargs(overrides)
    assert filtered == {
        "reference_id": "demo",
        "normalize": False,
        "top_p": 0.7,
        "format": "wav",
    }
