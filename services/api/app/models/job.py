from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    LOADING_MODEL = "LOADING_MODEL"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"


class OCRJob(Base):
    __tablename__ = "ocr_jobs"
    __table_args__ = (
        Index("ix_ocr_jobs_status_created", "status", "created_at"),
        Index("ix_ocr_jobs_updated_at", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(32), index=True)
    ocr_mode: Mapped[str] = mapped_column(String(20))
    source_path: Mapped[str] = mapped_column(Text)
    output_directory: Mapped[str] = mapped_column(Text)
    markdown_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=1)
    processed_pages: Mapped[int] = mapped_column(Integer, default=0)
    successful_pages: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[int] = mapped_column(Integer, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    pdf_dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
