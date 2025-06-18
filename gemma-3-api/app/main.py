# app/main.py (Final GGUF Version for 12B Model)
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ml_models = {}

class GenerationRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class GenerationResponse(BaseModel):
    generated_text: str

def load_model():
    """Downloads the 12B GGUF model and loads it into llama.cpp."""
    # Pointing to the 12B version of the GGUF model
    model_repo_id = "MaziyarPanahi/gemma-3-12b-it-GGUF"
    model_filename = "gemma-3-12b-it.Q4_K_M.gguf" # A ~7.5GB 4-bit quantization

    logger.info(f"Downloading model '{model_filename}' from repo '{model_repo_id}'...")

    model_path = hf_hub_download(
        repo_id=model_repo_id,
        filename=model_filename,
        token=os.getenv("HUGGING_FACE_HUB_TOKEN")
    )

    logger.info(f"Model downloaded to: {model_path}")
    logger.info("Loading model into GPU...")

    llm = Llama(
        model_path=model_path,
        n_gpu_layers=-1,  # Offload all possible layers to GPU
        n_ctx=4096,       # 4K context is fine for a 12B model on 24GB VRAM
        verbose=True
    )

    logger.info("Model loaded successfully.")
    return llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    ml_models["llm"] = load_model()
    yield
    logger.info("Application shutdown...")
    ml_models.clear()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/v1/generate", response_model=GenerationResponse)
async def generate_text(request: GenerationRequest):
    llm = ml_models.get("llm")
    if not llm:
        raise HTTPException(status_code=503, detail="Model is not available")

    try:
        logger.info(f"Generating text for prompt: '{request.prompt[:50]}...'")

        output = llm(
            request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=["<|endoftext|>", "<|im_end|>"]
        )

        result_text = output['choices'][0]['text']
        return GenerationResponse(generated_text=result_text)
    except Exception as e:
        logger.error(f"Error during text generation: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate text.")
