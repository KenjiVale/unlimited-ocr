from __future__ import annotations

import uuid
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.models.job import JobStatus, OCRJob, utc_now
from app.schemas.jobs import JobCreated, JobList, JobResponse, JobResultResponse
from app.schemas.pages import PageListResponse, PageResultResponse, PageSummary
from app.models.page import PageStatus
from app.services.jobs import ACTIVE_STATUSES, JobRepository
from app.services.storage import StorageService
from app.services.validation import validate_image_upload
from app.services.pdf import validate_pdf_type

router = APIRouter(prefix="/api/ocr/jobs", tags=["ocr-jobs"])


def _services(request: Request) -> tuple[JobRepository, StorageService]:
    return request.app.state.jobs, request.app.state.storage


def _job_response(job: OCRJob) -> JobResponse:
    error = {"code": job.error_code, "message": job.error_message} if job.error_code else None
    return JobResponse(
        id=job.id, status=job.status, original_filename=job.original_filename, ocr_mode=job.ocr_mode,
        created_at=job.created_at, file_type=job.file_type, pdf_dpi=job.pdf_dpi, total_pages=job.total_pages,
        error=error, started_at=job.started_at,
        completed_at=job.completed_at, processing_duration_ms=job.processing_duration_ms,
        result_available=job.status in {JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS} and bool(job.markdown_result_path),
        cancel_requested=job.cancel_requested,
        processed_pages=job.processed_pages, successful_pages=job.successful_pages,
        failed_pages=job.failed_pages, progress_percent=job.progress_percent,
        current_page_number=job.current_page_number,
    )


def _get_or_404(jobs: JobRepository, job_id: str) -> OCRJob:
    job = jobs.get(job_id)
    if job is None:
        raise AppError("JOB_NOT_FOUND", "OCR job was not found.", 404)
    return job


@router.post("", response_model=JobCreated, status_code=202)
async def create_job(request: Request, file: UploadFile = File(...), ocr_mode: str = Form("gundam"), pdf_dpi: int = Form(200)) -> JobCreated:
    if ocr_mode != "gundam":
        raise AppError("UNSUPPORTED_OCR_MODE", "Phase 2 supports only gundam OCR mode.", 422)
    settings = request.app.state.settings
    request.app.state.storage_monitor.preflight()
    content = await file.read(settings.upload_max_mb * 1024 * 1024 + 1)
    filename = file.filename or ""
    is_pdf = Path(filename.replace("\\", "/")).suffix.lower() == ".pdf" or file.content_type == "application/pdf"
    if is_pdf:
        if pdf_dpi not in {150, 200, 300}:
            raise AppError("INVALID_PDF_DPI", "PDF DPI must be 150, 200, or 300.", 422)
        validate_pdf_type(filename, file.content_type, content, settings.upload_max_mb)
        extension = ".pdf"
    else:
        extension = validate_image_upload(filename, file.content_type, content, settings.upload_max_mb)
    jobs, storage = _services(request)
    job_id, now = str(uuid.uuid4()), utc_now()
    source, output = storage.create_job_paths(job_id, extension)
    try:
        storage.save_bytes(source, content)
        page_count = 1
        if is_pdf:
            metadata = request.app.state.pdf_service.inspect_pdf(source, settings.pdf_max_pages)
            page_count = metadata.page_count
        record = OCRJob(
            id=job_id, original_filename=storage.sanitize_filename(file.filename or "upload"),
            stored_filename=source.name, file_type=extension.lstrip("."), status=JobStatus.QUEUED,
            ocr_mode=ocr_mode, source_path=str(source), output_directory=str(output),
            cancel_requested=False, created_at=now, queued_at=now, updated_at=now,
            total_pages=page_count, processed_pages=0, successful_pages=0, failed_pages=0,
            progress_percent=0, pdf_dpi=pdf_dpi if is_pdf else None,
        )
        job = jobs.add_with_capacity(record, page_count if is_pdf else None, settings.max_queued_jobs)
    except Exception:
        storage.delete_job(job_id)
        raise
    request.app.state.worker.wake()
    return JobCreated(id=job.id, status=job.status, original_filename=job.original_filename, ocr_mode=job.ocr_mode, created_at=job.created_at, file_type=job.file_type, pdf_dpi=job.pdf_dpi, total_pages=job.total_pages)


@router.get("", response_model=JobList)
def list_jobs(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), status: JobStatus | None = None) -> JobList:
    jobs, _ = _services(request)
    return JobList(items=[_job_response(job) for job in jobs.list(limit, offset, status)], limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(request: Request, job_id: str) -> JobResponse:
    jobs, _ = _services(request)
    return _job_response(_get_or_404(jobs, job_id))


@router.get("/{job_id}/result", response_model=JobResultResponse)
def get_result(request: Request, job_id: str) -> JobResultResponse:
    jobs, storage = _services(request)
    job = _get_or_404(jobs, job_id)
    if job.status not in {JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS} or not all((job.markdown_result_path, job.text_result_path, job.json_result_path)):
        raise AppError("RESULT_NOT_AVAILABLE", "The OCR result is not available for this job.", 409)
    metadata = storage.read_json(Path(job.json_result_path))
    return JobResultResponse(
        job_id=job.id, status=job.status, markdown=storage.read_text(Path(job.markdown_result_path)),
        text=storage.read_text(Path(job.text_result_path)), duration_ms=job.processing_duration_ms or 0,
        peak_allocated_vram_mb=int(metadata.get("peak_allocated_vram_mb", 0)),
    )


@router.get("/{job_id}/download/{kind}")
def download_result(request: Request, job_id: str, kind: str):
    jobs, storage = _services(request); job = _get_or_404(jobs, job_id)
    options = {"markdown": (job.markdown_result_path, ".md", "text/markdown"), "text": (job.text_result_path, ".txt", "text/plain"), "json": (job.json_result_path, ".json", "application/json")}
    if kind not in options: raise AppError("RESULT_NOT_AVAILABLE", "The requested result format is unavailable.", 404)
    raw, suffix, media = options[kind]
    if not raw: raise AppError("RESULT_NOT_AVAILABLE", "The OCR result is not available.", 409)
    path = Path(raw).resolve(); output = Path(job.output_directory).resolve()
    if output not in path.parents or not path.is_file(): raise AppError("RESULT_NOT_AVAILABLE", "The OCR result is not available.", 409)
    name = f"{storage.sanitize_filename(Path(job.original_filename).stem)}-ocr{suffix}"
    return FileResponse(path, media_type=media, filename=name)


@router.get("/{job_id}/integrity")
def integrity(request: Request, job_id: str):
    jobs, _ = _services(request); job = _get_or_404(jobs, job_id)
    issues = request.app.state.integrity_service.check(job)
    return {"job_id": job.id, "valid": not issues, "issues": issues, "checked_at": utc_now()}


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(request: Request, job_id: str) -> JobResponse:
    jobs, _ = _services(request)
    _get_or_404(jobs, job_id)
    return _job_response(jobs.request_cancel(job_id))  # type: ignore[arg-type]


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(request: Request, job_id: str) -> JobResponse:
    jobs, _ = _services(request)
    job = _get_or_404(jobs, job_id)
    retried = jobs.retry(job_id)
    if retried is None:
        code = "JOB_ALREADY_COMPLETED" if job.status == JobStatus.COMPLETED else "JOB_NOT_RETRYABLE"
        raise AppError(code, "This OCR job cannot be retried.", 409)
    request.app.state.worker.wake()
    return _job_response(retried)


@router.delete("/{job_id}", status_code=204, response_class=Response)
def delete_job(request: Request, job_id: str) -> Response:
    jobs, storage = _services(request)
    job = _get_or_404(jobs, job_id)
    if job.status in ACTIVE_STATUSES:
        raise AppError("JOB_ACTIVE", "An active OCR job cannot be deleted.", 409)
    jobs.delete(job_id)
    storage.delete_job(job_id)
    return Response(status_code=204)


def _page_summary(page) -> PageSummary:
    error = {"code": page.error_code, "message": page.error_message} if page.error_code else None
    return PageSummary(page_number=page.page_number, status=page.status, render_duration_ms=page.render_duration_ms, inference_duration_ms=page.inference_duration_ms, peak_allocated_vram_mb=page.peak_allocated_vram_mb, error=error)


@router.get("/{job_id}/pages", response_model=PageListResponse)
def list_pages(request: Request, job_id: str) -> PageListResponse:
    jobs, _ = _services(request); job = _get_or_404(jobs, job_id)
    return PageListResponse(job_id=job.id, total_pages=job.total_pages, pages=[_page_summary(page) for page in jobs.pages(job_id)])


@router.get("/{job_id}/pages/{page_number}", response_model=PageSummary)
def get_page(request: Request, job_id: str, page_number: int) -> PageSummary:
    jobs, _ = _services(request); _get_or_404(jobs, job_id)
    page = jobs.page(job_id, page_number)
    if not page: raise AppError("PAGE_NOT_FOUND", "OCR page was not found.", 404)
    return _page_summary(page)


@router.get("/{job_id}/pages/{page_number}/result", response_model=PageResultResponse)
def get_page_result(request: Request, job_id: str, page_number: int) -> PageResultResponse:
    jobs, storage = _services(request); _get_or_404(jobs, job_id)
    page = jobs.page(job_id, page_number)
    if not page: raise AppError("PAGE_NOT_FOUND", "OCR page was not found.", 404)
    if page.status != PageStatus.COMPLETED or not page.markdown_result_path or not page.text_result_path:
        raise AppError("PAGE_RESULT_NOT_AVAILABLE", "The page result is not available.", 409)
    return PageResultResponse(job_id=job_id, page_number=page_number, status=page.status, markdown=storage.read_text(Path(page.markdown_result_path)), text=storage.read_text(Path(page.text_result_path)))


@router.post("/{job_id}/pages/{page_number}/retry", response_model=PageSummary)
def retry_page(request: Request, job_id: str, page_number: int) -> PageSummary:
    jobs, _ = _services(request); job = _get_or_404(jobs, job_id)
    if job.status in ACTIVE_STATUSES: raise AppError("JOB_ACTIVE", "An active OCR job cannot retry a page.", 409)
    if not jobs.page(job_id, page_number): raise AppError("PAGE_NOT_FOUND", "OCR page was not found.", 404)
    retried = jobs.retry_page(job_id, page_number)
    if not retried: raise AppError("PAGE_NOT_RETRYABLE", "This OCR page cannot be retried.", 409)
    request.app.state.worker.wake()
    return _page_summary(retried)
