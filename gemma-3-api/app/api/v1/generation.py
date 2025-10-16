"""Text generation API endpoints."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.schemas.generation import (
    GenerationRequest,
    GenerationResponse,
    ModelInfo,
    ModelListResponse,
)
from app.services.llm import LLMService
from app.security import (
    enforce_rate_limit,
    enforce_websocket_api_key,
    enforce_websocket_rate_limit,
    require_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["generation"],
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)


def _get_llm_service(request: Request) -> LLMService:
    service: LLMService | None = getattr(request.app.state, "llm_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Model is not available")
    return service


@router.post("/generate", response_model=GenerationResponse)
async def generate_text(
    payload: GenerationRequest,
    llm_service: LLMService = Depends(_get_llm_service),
) -> GenerationResponse:
    """Synchronous text generation endpoint."""

    logger.info("Generating text for prompt: '%s...'", payload.prompt[:50])

    generation_params = payload.model_dump(exclude_unset=True)
    try:
        output = llm_service.model(**generation_params)
    except Exception as exc:  # pragma: no cover - llama.cpp errors
        logger.exception("Error during text generation")
        raise HTTPException(status_code=500, detail="Failed to generate text.") from exc

    result_text = output["choices"][0]["text"]
    return GenerationResponse(generated_text=result_text)


@router.post("/generate_stream")
async def generate_text_stream(
    payload: GenerationRequest,
    llm_service: LLMService = Depends(_get_llm_service),
) -> StreamingResponse:
    """Stream partial generations as newline-delimited JSON."""

    logger.info("Generating text stream for prompt: '%s...'", payload.prompt[:50])

    generation_params = payload.model_dump(exclude_unset=True)

    def event_stream() -> Iterable[str]:
        aggregated_text = ""
        try:
            for chunk in llm_service.model(**generation_params, stream=True):
                token = chunk["choices"][0]["text"]
                aggregated_text += token
                yield json.dumps({"generated_text": aggregated_text}) + "\n"
        except Exception as exc:  # pragma: no cover - llama.cpp errors
            logger.exception("Error during streaming generation")
            error_payload: Dict[str, str] = {"detail": "Failed to generate text stream."}
            yield json.dumps(error_payload) + "\n"
            return

    return StreamingResponse(event_stream(), media_type="application/json")


@router.websocket("/generate_ws")
async def generate_ws(websocket: WebSocket) -> None:
    if not await enforce_websocket_api_key(websocket):
        return
    if not await enforce_websocket_rate_limit(websocket):
        return
    await websocket.accept()

    try:
        llm_service: LLMService | None = getattr(websocket.app.state, "llm_service", None)
        if llm_service is None:
            await websocket.close(code=1011, reason="Model is not available")
            return
        while True:
            data = await websocket.receive_json()
            payload = GenerationRequest(**data)

            logger.info("Generating text stream for prompt: '%s...'", payload.prompt[:50])

            generation_params = payload.model_dump(exclude_unset=True)
            for chunk in llm_service.model(**generation_params, stream=True):
                token = chunk["choices"][0]["text"]
                await websocket.send_json({"token": token})

            await websocket.send_json({"status": "done"})

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket.")
    except Exception as exc:  # pragma: no cover - llama.cpp errors
        logger.exception("Error in WebSocket handler")
        await websocket.close(code=1011, reason="An internal error occurred.")


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List available LLM checkpoints."""

    return ModelListResponse(
        models=[
            ModelInfo(
                id="google/gemma-3-12b-it-qat-q4_0-gguf",
                name="Gemma 3 12B Q4_0 GGUF",
                description="Google's Gemma 3 model, 12B parameters, quantized to 4-bit.",
            )
        ]
    )


@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model_info(model_id: str) -> ModelInfo:
    if model_id != "google/gemma-3-12b-it-qat-q4_0-gguf":
        raise HTTPException(status_code=404, detail="Model not found.")

    return ModelInfo(
        id=model_id,
        name="Gemma 3 12B Q4_0 GGUF",
        description="Google's Gemma 3 model, 12B parameters, quantized to 4-bit.",
    )

