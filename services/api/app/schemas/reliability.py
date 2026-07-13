from datetime import datetime
from pydantic import BaseModel, Field


class WorkerStatusResponse(BaseModel):
    state: str
    started_at: datetime | None
    last_heartbeat_at: datetime | None
    active_job_id: str | None
    active_page_number: int | None
    last_completed_job_id: str | None
    queued_jobs: int
    completed_jobs_since_start: int
    failed_jobs_since_start: int
    last_error: dict[str, str | None] | None
    process_rss_bytes: int
    available_ram_bytes: int
    allocated_vram_bytes: int
    reserved_vram_bytes: int


class StorageStatusResponse(BaseModel):
    data_directory: str
    free_disk_bytes: int
    used_disk_bytes: int
    uploads_bytes: int
    rendered_pages_bytes: int
    outputs_bytes: int
    model_bytes: int
    orphaned_directories: int
    minimum_free_disk_bytes: int
    accepting_new_jobs: bool


class IntegrityResponse(BaseModel):
    job_id: str
    valid: bool
    issues: list[str]
    checked_at: datetime


class CleanupRequest(BaseModel):
    older_than_days: int = Field(default=30, ge=0, le=3650)
    include_rendered_pages: bool = True
    include_source_files: bool = False
    include_outputs: bool = False
    include_orphans: bool = False
    terminal_statuses: list[str] = ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "CANCELLED"]


class CleanupResponse(BaseModel):
    jobs_considered: int
    rendered_page_files: int
    rendered_page_bytes: int
    source_files: int
    source_bytes: int
    output_files: int
    output_bytes: int
    orphaned_directories: int
    deleted_items: int = 0
    deleted_bytes: int = 0
    failed_items: int = 0
    will_delete_database_records: bool = False
