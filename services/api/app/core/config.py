from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    ocr_model_id: str = "baidu/Unlimited-OCR"
    ocr_model_path: Path = Path("./data/models/Unlimited-OCR")
    ocr_device: Literal["cuda"] = "cuda"
    ocr_dtype: Literal["bfloat16"] = "bfloat16"
    ocr_default_mode: Literal["gundam"] = "gundam"
    ocr_max_length: int = Field(default=8192, ge=1, le=32768)
    ocr_concurrency: int = Field(default=1, ge=1, le=1)
    pdf_default_dpi: int = Field(default=200)
    pdf_max_pages: int = Field(default=100, ge=1)
    upload_max_mb: int = Field(default=200, ge=1)
    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/app.db"
    hf_hub_offline: bool = False
    transformers_offline: bool = False
    hf_hub_disable_telemetry: bool = True
    next_public_api_url: str = "http://127.0.0.1:8000"
    worker_poll_seconds: float = Field(default=0.25, gt=0, le=10)
    worker_shutdown_timeout_seconds: float = Field(default=10, gt=0, le=120)
    worker_poll_interval_ms: int = Field(default=500, ge=50, le=10_000)
    worker_heartbeat_interval_seconds: float = Field(default=5, ge=0.1, le=60)
    worker_stale_after_seconds: float = Field(default=120, ge=1, le=3600)
    database_busy_timeout_ms: int = Field(default=5000, ge=100, le=120_000)
    database_journal_mode: Literal["WAL"] = "WAL"
    max_queued_jobs: int = Field(default=50, ge=1, le=1000)
    min_free_disk_gb: float = Field(default=5, ge=0, le=10_000)
    cleanup_enabled: bool = False
    cleanup_retention_days: int = Field(default=30, ge=1, le=3650)
    cleanup_include_rendered_pages: bool = True
    cleanup_include_source_files: bool = False
    shutdown_grace_seconds: float = Field(default=30, ge=1, le=300)
    api_health_target_ms: int = Field(default=250, ge=10, le=5000)

    @field_validator("ocr_model_path", "data_dir", mode="before")
    @classmethod
    def reject_empty_path(cls, value: object) -> object:
        if not str(value).strip():
            raise ValueError("path must not be empty")
        return value

    @field_validator("pdf_default_dpi")
    @classmethod
    def validate_pdf_dpi(cls, value: int) -> int:
        if value not in {150, 200, 300}:
            raise ValueError("PDF DPI must be 150, 200, or 300")
        return value

    @model_validator(mode="after")
    def validate_offline_model(self) -> "Settings":
        if (self.hf_hub_offline or self.transformers_offline) and not self.ocr_model_path.is_dir():
            raise ValueError(
                f"Offline mode requires OCR_MODEL_PATH to exist: {self.ocr_model_path}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
