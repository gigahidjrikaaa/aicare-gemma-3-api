"""Schema exports."""

from .generation import GenerationRequest, GenerationResponse, ModelInfo, ModelListResponse
from .speech import (
    SpeechDialogueResponse,
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SpeechTranscriptionOptions,
    SpeechTranscriptionResponse,
    SpeechTranscriptionSegment,
)

__all__ = [
    "GenerationRequest",
    "GenerationResponse",
    "ModelInfo",
    "ModelListResponse",
    "SpeechDialogueResponse",
    "SpeechSynthesisRequest",
    "SpeechSynthesisResponse",
    "SpeechTranscriptionOptions",
    "SpeechTranscriptionResponse",
    "SpeechTranscriptionSegment",
]
