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
    model_repo_id = "google/gemma-3-12b-it-qat-q4_0-gguf"
    model_filename = "gemma-3-12b-it-q4_0.gguf" # A ~7.5GB 4-bit quantization

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
        n_gpu_layers=-1,  # Use all available GPU layers
        n_batch=2048,      # Batch size for processing
        n_threads=10,       # Number of threads for processing
        n_ctx=32768,      # Context size
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

@app.post("/v1/generate_stream", response_model=GenerationResponse)
async def generate_text_stream(request: GenerationRequest):
    llm = ml_models.get("llm")
    if not llm:
        raise HTTPException(status_code=503, detail="Model is not available")

    try:
        logger.info(f"Generating text stream for prompt: '{request.prompt[:50]}...'")

        output = llm(
            request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=["<|endoftext|>", "<|im_end|>"],
            stream=True
        )

        result_text = ""
        for chunk in output:
            result_text += chunk['choices'][0]['text']
            yield GenerationResponse(generated_text=result_text)

    except Exception as e:
        logger.error(f"Error during text generation stream: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate text stream.")

# List models endpoint
@app.get("/v1/models", response_model=dict)
async def list_models():
    return {
        "models": [
            {
                "id": "google/gemma-3-12b-it-qat-q4_0-gguf",
                "name": "Gemma 3 12B Q4_0 GGUF",
                "description": "Google's Gemma 3 model, 12B parameters, quantized to 4-bit."
            }
        ]
    }
@app.get("/v1/models/{model_id}", response_model=dict)
async def get_model_info(model_id: str):
    if model_id == "google/gemma-3-12b-it-qat-q4_0-gguf":
        return {
            "id": model_id,
            "name": "Gemma 3 12B Q4_0 GGUF",
            "description": "Google's Gemma 3 model, 12B parameters, quantized to 4-bit."
        }
    else:
        raise HTTPException(status_code=404, detail="Model not found.")

    