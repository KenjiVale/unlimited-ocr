from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobCreated(BaseModel):
    id: str
    status: str
    original_filename: str
    ocr_mode: str
    created_at: datetime
    file_type: str
    pdf_dpi: int | None = None
    total_pages: int = 1


class JobResponse(JobCreated):
    error: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    processing_duration_ms: int | None
    result_available: bool
    cancel_requested: bool
    processed_pages: int
    successful_pages: int
    failed_pages: int
    progress_percent: int
    current_page_number: int | None


class JobList(BaseModel):
    items: list[JobResponse]
    limit: int
    offset: int


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    markdown: str
    text: str
    duration_ms: int
    peak_allocated_vram_mb: int
