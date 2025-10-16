"""Pydantic models for text generation endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=0)
    repeat_penalty: float = Field(default=1.1, ge=0.0)
    stop: Optional[List[str]] = Field(
        default_factory=lambda: ["<|endoftext|>", "<|im_end|>"],
        description="Stop sequences forwarded to llama.cpp",
    )
    seed: Optional[int] = Field(default=None, ge=0)
    min_p: float = Field(default=0.05, ge=0.0)
    tfs_z: float = Field(default=1.0, ge=0.0)
    typical_p: float = Field(default=1.0, ge=0.0)


class GenerationResponse(BaseModel):
    generated_text: str


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str


class ModelListResponse(BaseModel):
    models: List[ModelInfo]

