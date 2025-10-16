"""llama.cpp based LLM service utilities."""

from __future__ import annotations

import logging
from typing import Optional

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class LLMService:
    """Lifecycle manager for the Gemma llama.cpp model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm: Optional[Llama] = None
        self._model_path: Optional[str] = None

    def startup(self) -> None:
        """Download and load the configured model if required."""

        if self._llm is not None:
            logger.debug("LLMService.startup invoked but model already loaded")
            return

        logger.info(
            "Downloading model '%s' from repo '%s'...",
            self._settings.llm_model_filename,
            self._settings.llm_repo_id,
        )

        self._model_path = hf_hub_download(
            repo_id=self._settings.llm_repo_id,
            filename=self._settings.llm_model_filename,
            token=self._settings.hugging_face_hub_token,
        )

        logger.info("Model downloaded to: %s", self._model_path)
        logger.info("Loading model into memory via llama.cpp...")

        self._llm = Llama(
            model_path=self._model_path,
            n_gpu_layers=self._settings.llm_gpu_layers,
            n_batch=self._settings.llm_batch_size,
            n_threads=self._settings.llm_n_threads,
            n_ctx=self._settings.llm_context_size,
            verbose=True,
        )

        logger.info("Model loaded successfully.")

    def shutdown(self) -> None:
        """Release model resources."""

        if self._llm is not None:
            logger.info("Releasing llama.cpp model instance")
        self._llm = None
        self._model_path = None

    @property
    def model(self) -> Llama:
        if self._llm is None:
            raise RuntimeError("LLM model is not loaded")
        return self._llm

