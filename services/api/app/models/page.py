from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.job import utc_now


class PageStatus(StrEnum):
    PENDING = "PENDING"
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class OCRPage(Base):
    __tablename__ = "ocr_pages"
    __table_args__ = (
        UniqueConstraint("job_id", "page_number", name="uq_ocr_pages_job_page"),
        Index("ix_ocr_pages_job_status", "job_id", "status"),
        Index("ix_ocr_pages_job_page", "job_id", "page_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("ocr_jobs.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    markdown_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inference_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peak_allocated_vram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

