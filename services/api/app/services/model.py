from __future__ import annotations

import asyncio
import gc
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.model import ModelStatusResponse

logger = logging.getLogger("unlimited_ocr.model")


class ModelState(StrEnum):
    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OCRInferenceResult:
    markdown: str
    plain_text: str
    duration_ms: int
    peak_allocated_vram_mb: int
    mode: str
    model_path: str


class ModelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = ModelState.NOT_LOADED
        self.loaded_at: datetime | None = None
        self.load_duration_ms: int | None = None
        self.last_error: str | None = None
        self._model: object | None = None
        self._tokenizer: object | None = None
        self._load_lock = asyncio.Lock()
        self._gpu_lock = asyncio.Lock()

    async def ensure_loaded(self) -> None:
        if self.state == ModelState.READY:
            return
        async with self._load_lock:
            if self.state == ModelState.READY:
                return
            self.state, self.last_error = ModelState.LOADING, None
            logger.info("model load started", extra={"operation": "model_load", "status": self.state})
            started = time.perf_counter()
            try:
                await asyncio.to_thread(self._load_sync)
                self.load_duration_ms = round((time.perf_counter() - started) * 1000)
                self.loaded_at, self.state = datetime.now(timezone.utc), ModelState.READY
                logger.info("model load completed", extra={"operation": "model_load", "status": self.state, "duration_ms": self.load_duration_ms})
            except Exception as exc:
                self.state, self.last_error = ModelState.FAILED, str(exc)
                logger.exception("model load failed", extra={"operation": "model_load", "status": self.state})
                if isinstance(exc, AppError):
                    raise
                raise AppError("MODEL_LOAD_FAILED", "Unable to load the local OCR model.", 500) from exc

    def _load_sync(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        if not torch.cuda.is_available():
            raise AppError("CUDA_UNAVAILABLE", "CUDA is not available.", 503)
        model_path = self.settings.ocr_model_path
        if not model_path.is_dir():
            raise AppError("MODEL_FILES_MISSING", "The local OCR model directory is missing.", 503)
        cache_root = (self.settings.data_dir / ".cache").resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
        os.environ.setdefault("HF_MODULES_CACHE", str(cache_root / "huggingface" / "modules"))
        os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        local_only = self.settings.hf_hub_offline or self.settings.transformers_offline
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True, local_files_only=local_only)
        self._model = AutoModel.from_pretrained(str(model_path), trust_remote_code=True, use_safetensors=True, torch_dtype=torch.bfloat16, local_files_only=local_only).eval().cuda()

    async def infer_image(self, image_path: Path, output_directory: Path) -> OCRInferenceResult:
        await self.ensure_loaded()
        async with self._gpu_lock:
            return await asyncio.to_thread(self._infer_sync, image_path, output_directory)

    def _infer_sync(self, image_path: Path, output_directory: Path) -> OCRInferenceResult:
        import torch

        if self._model is None or self._tokenizer is None:
            raise AppError("MODEL_LOAD_FAILED", "OCR model is not loaded.", 500)
        upstream_dir = output_directory / ".upstream"
        upstream_dir.mkdir(parents=True, exist_ok=True)
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        logger.info("inference started", extra={"operation": "inference", "status": "PROCESSING"})
        try:
            with torch.inference_mode():
                returned = self._model.infer(  # type: ignore[attr-defined]
                    self._tokenizer, prompt="<image>document parsing.", image_file=str(image_path.resolve()),
                    output_path=str(upstream_dir.resolve()), base_size=1024, image_size=640,
                    crop_mode=True, max_length=self.settings.ocr_max_length,
                    no_repeat_ngram_size=35, ngram_window=128, save_results=True,
                )
            torch.cuda.synchronize()
            duration_ms = round((time.perf_counter() - started) * 1000)
            result_file = upstream_dir / "result.md"
            markdown = result_file.read_text(encoding="utf-8") if result_file.is_file() else str(returned or "")
            plain_text = re.sub(r"[`#*_>]", "", markdown).strip()
            peak = torch.cuda.max_memory_allocated() // (1024 * 1024)
            logger.info("inference completed", extra={"operation": "inference", "status": "COMPLETED", "duration_ms": duration_ms})
            return OCRInferenceResult(markdown.strip(), plain_text, duration_ms, peak, "gundam", str(self.settings.ocr_model_path))
        except torch.cuda.OutOfMemoryError as exc:
            gc.collect(); torch.cuda.empty_cache()
            raise AppError("OCR_CUDA_OUT_OF_MEMORY", "CUDA ran out of memory during OCR inference.", 500) from exc
        except AppError:
            raise
        except Exception as exc:
            logger.exception("inference failed", extra={"operation": "inference", "status": "FAILED"})
            raise AppError("MODEL_INFERENCE_FAILED", "OCR model inference failed.", 500) from exc

    def get_status(self) -> ModelStatusResponse:
        return ModelStatusResponse(
            status=self.state, model_id=self.settings.ocr_model_id,
            model_path=self.settings.ocr_model_path.name, device=self.settings.ocr_device,
            dtype=self.settings.ocr_dtype,
            offline_mode=self.settings.hf_hub_offline or self.settings.transformers_offline,
            loaded_at=self.loaded_at, load_duration_ms=self.load_duration_ms, last_error=self.last_error,
        )

