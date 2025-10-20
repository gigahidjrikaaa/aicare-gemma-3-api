"""Orchestration utilities that combine STT, LLM and TTS services."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.schemas.generation import GenerationRequest
from app.services.openaudio import (
    OpenAudioService,
    OpenAudioSynthesisResult,
    OpenAudioSynthesisStream,
)
from app.services.llm import LLMService
from app.services.whisper import WhisperService, WhisperTranscription
from app.observability.metrics import record_external_call, record_pipeline


@dataclass(slots=True)
class DialogueResult:
    """Container returned by :class:`ConversationService` for blocking calls."""

    transcription: WhisperTranscription
    response_text: str
    synthesis: OpenAudioSynthesisResult


@dataclass(slots=True)
class DialogueStreamResult:
    """Container returned by :class:`ConversationService` for streaming calls."""

    transcription: WhisperTranscription
    response_text: str
    synthesis_stream: OpenAudioSynthesisStream


class ConversationService:
    """High level helper that links Whisper, Gemma and OpenAudio."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        whisper_service: WhisperService,
        openaudio_service: OpenAudioService,
    ) -> None:
        self._llm_service = llm_service
        self._whisper_service = whisper_service
        self._openaudio_service = openaudio_service

    async def run_dialogue(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: Optional[str],
        instructions: Optional[str],
        generation_overrides: Optional[Dict[str, Any]] = None,
        synthesis_overrides: Optional[Dict[str, Any]] = None,
        stream_audio: bool = False,
    ) -> DialogueResult | DialogueStreamResult:
        """Execute STT → LLM → TTS for the supplied audio payload."""

        pipeline_start = time.perf_counter()
        pipeline_success = False
        try:
            transcription = await self._whisper_service.transcribe(
                audio_bytes,
                filename=filename,
                content_type=content_type,
            )

            prompt = self._build_prompt(transcription_text=transcription.text, instructions=instructions)
            generation_request = self._build_generation_request(
                prompt=prompt, overrides=generation_overrides or {}
            )

            generation_params = generation_request.model_dump(exclude_unset=True)
            llm_model = self._llm_service.model
            llm_start = time.perf_counter()
            try:
                response_payload = await asyncio.to_thread(llm_model, **generation_params)
            except Exception:
                record_external_call("llm_generation", time.perf_counter() - llm_start, success=False)
                raise
            record_external_call("llm_generation", time.perf_counter() - llm_start, success=True)
            response_text = response_payload["choices"][0]["text"]

            synthesis_kwargs = self._prepare_synthesis_kwargs(synthesis_overrides or {})

            if stream_audio:
                synthesis_stream = await self._openaudio_service.synthesize_stream(
                    text=response_text,
                    **synthesis_kwargs,
                )
                pipeline_success = True
                return DialogueStreamResult(
                    transcription=transcription,
                    response_text=response_text,
                    synthesis_stream=synthesis_stream,
                )

            synthesis_result = await self._openaudio_service.synthesize(
                text=response_text,
                **synthesis_kwargs,
            )
            pipeline_success = True
            return DialogueResult(
                transcription=transcription,
                response_text=response_text,
                synthesis=synthesis_result,
            )
        except Exception:
            record_pipeline("speech_dialogue", time.perf_counter() - pipeline_start, success=False)
            raise
        finally:
            if pipeline_success:
                record_pipeline("speech_dialogue", time.perf_counter() - pipeline_start, success=True)

    @staticmethod
    def _build_prompt(*, transcription_text: str, instructions: Optional[str]) -> str:
        """Craft a simple conversational prompt for the Gemma model."""

        user_text = transcription_text.strip() or "(no transcript available)"
        if instructions:
            instructions_clean = instructions.strip()
            return f"{instructions_clean}\n\nUser: {user_text}\nAssistant:"
        return f"User: {user_text}\nAssistant:"

    @staticmethod
    def _build_generation_request(
        *, prompt: str, overrides: Dict[str, Any]
    ) -> GenerationRequest:
        """Merge overrides with the default :class:`GenerationRequest` schema."""

        sanitized = {k: v for k, v in overrides.items() if v is not None and k != "prompt"}
        try:
            return GenerationRequest(prompt=prompt, **sanitized)
        except Exception as exc:  # pragma: no cover - validation error surfaces upstream
            raise ValueError("Invalid generation overrides supplied") from exc

    @staticmethod
    def _prepare_synthesis_kwargs(overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Remove disallowed keys and ``None`` values from synthesis overrides."""

        filtered = {
            key: value
            for key, value in overrides.items()
            if key not in {"text", "stream"} and value is not None
        }
        return filtered

