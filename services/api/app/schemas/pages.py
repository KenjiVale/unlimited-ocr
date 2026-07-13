from __future__ import annotations

from pydantic import BaseModel


class PageSummary(BaseModel):
    page_number: int
    status: str
    render_duration_ms: int | None
    inference_duration_ms: int | None
    peak_allocated_vram_mb: int | None
    error: dict[str, str | None] | None


class PageListResponse(BaseModel):
    job_id: str
    total_pages: int
    pages: list[PageSummary]


class PageResultResponse(BaseModel):
    job_id: str
    page_number: int
    status: str
    markdown: str
    text: str

