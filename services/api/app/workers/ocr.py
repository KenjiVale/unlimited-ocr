from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.models.job import JobStatus, OCRJob, utc_now
from app.services.jobs import JobRepository
from app.services.model import ModelService
from app.services.storage import StorageService
from app.services.pdf import PDFService
from app.models.page import PageStatus
from app.services.reliability import WorkerState

logger = logging.getLogger("unlimited_ocr.worker")


class OCRWorker:
    def __init__(self, settings: Settings, jobs: JobRepository, storage: StorageService, model: ModelService) -> None:
        self.settings, self.jobs, self.storage, self.model = settings, jobs, storage, model
        self.pdf = PDFService()
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self.state = WorkerState.STARTING
        self.started_at: datetime | None = None; self.last_heartbeat_at: datetime | None = None
        self.active_job_id: str | None = None; self.active_page_number: int | None = None
        self.last_completed_job_id: str | None = None; self.last_error_code: str | None = None; self.last_error_message: str | None = None
        self.completed_jobs_since_start = 0; self.failed_jobs_since_start = 0

    def start(self) -> None:
        self.started_at = utc_now(); self.last_heartbeat_at = self.started_at; self.state = WorkerState.IDLE
        self._task = asyncio.create_task(self.run(), name="single-ocr-gpu-worker")
        self._heartbeat_task = asyncio.create_task(self._heartbeat(), name="ocr-worker-heartbeat")

    async def _heartbeat(self) -> None:
        while not self._stop.is_set():
            self.last_heartbeat_at = utc_now()
            await asyncio.sleep(self.settings.worker_heartbeat_interval_seconds)

    def wake(self) -> None:
        self._wake.set()

    async def stop(self) -> None:
        self.state = WorkerState.STOPPING
        self._stop.set(); self._wake.set()
        if self._task:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), self.settings.shutdown_grace_seconds)
            except TimeoutError:
                logger.warning("worker shutdown timed out; active job remains recoverable")
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self.state = WorkerState.STOPPED

    async def run(self) -> None:
        while not self._stop.is_set():
            self.state = WorkerState.CLAIMING
            job = await asyncio.to_thread(self.jobs.claim_next)
            if job is None:
                self.state = WorkerState.IDLE
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), self.settings.worker_poll_interval_ms / 1000)
                except TimeoutError:
                    pass
                continue
            self.active_job_id = job.id; self.active_page_number = None; self.state = WorkerState.LOADING_MODEL
            await self._process(job)
            final = await asyncio.to_thread(self.jobs.get, job.id)
            if final and final.status in {JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS, JobStatus.CANCELLED}:
                self.completed_jobs_since_start += 1; self.last_completed_job_id = job.id
            elif final and final.status == JobStatus.FAILED:
                self.failed_jobs_since_start += 1; self.last_error_code = final.error_code; self.last_error_message = final.error_message
            self.active_job_id = None; self.active_page_number = None; self.state = WorkerState.IDLE

    async def _process(self, claimed: OCRJob) -> None:
        job_id = claimed.id
        try:
            current = await asyncio.to_thread(self.jobs.get, job_id)
            if not current or current.cancel_requested:
                await asyncio.to_thread(self.jobs.update_status, job_id, JobStatus.CANCELLED, completed_at=utc_now())
                return
            await self.model.ensure_loaded()
            current = await asyncio.to_thread(self.jobs.get, job_id)
            if not current or current.cancel_requested:
                await asyncio.to_thread(self.jobs.update_status, job_id, JobStatus.CANCELLED, completed_at=utc_now())
                return
            await asyncio.to_thread(self.jobs.update_status, job_id, JobStatus.PROCESSING)
            self.state = WorkerState.PROCESSING
            if current.file_type == "pdf":
                await self._process_pdf(current)
                return
            await self._process_image(current)
        except AppError as exc:
            await asyncio.to_thread(self.jobs.update_status, job_id, JobStatus.FAILED, error_code=exc.code, error_message=exc.message, completed_at=utc_now())
            logger.error("job failed", extra={"job_id": job_id, "status": "FAILED", "operation": "ocr", "error_code": exc.code})
        except Exception:
            await asyncio.to_thread(self.jobs.update_status, job_id, JobStatus.FAILED, error_code="INTERNAL_ERROR", error_message="Unexpected worker failure.", completed_at=utc_now())
            logger.exception("job failed", extra={"job_id": job_id, "status": "FAILED", "operation": "ocr", "error_code": "INTERNAL_ERROR"})

    async def _process_image(self, current: OCRJob) -> None:
            job_id = current.id
            result = await self.model.infer_image(Path(current.source_path), Path(current.output_directory))
            finished = utc_now()
            latest = await asyncio.to_thread(self.jobs.get, job_id)
            cancelled = bool(latest and latest.cancel_requested)
            final_status = JobStatus.CANCELLED if cancelled else JobStatus.COMPLETED
            payload = {
                "job_id": job_id, "original_filename": current.original_filename, "status": final_status,
                "ocr_mode": current.ocr_mode, "model": self.settings.ocr_model_id,
                "duration_ms": result.duration_ms, "peak_allocated_vram_mb": result.peak_allocated_vram_mb,
                "markdown": result.markdown, "text": result.plain_text,
                "created_at": current.created_at, "completed_at": finished,
            }
            paths = await asyncio.to_thread(self.storage.write_results, Path(current.output_directory), result.markdown, result.plain_text, payload)
            await asyncio.to_thread(
                self.jobs.update_status, job_id, final_status, completed_at=finished,
                processing_duration_ms=result.duration_ms, markdown_result_path=str(paths[0]),
                text_result_path=str(paths[1]), json_result_path=str(paths[2]),
                processed_pages=1, successful_pages=1, failed_pages=0, progress_percent=100,
                current_page_number=1,
            )
            logger.info("job finalized", extra={"job_id": job_id, "status": final_status, "operation": "ocr", "duration_ms": result.duration_ms})

    async def _process_pdf(self, job: OCRJob) -> None:
        source, output = Path(job.source_path), Path(job.output_directory)
        for page in await asyncio.to_thread(self.jobs.pages, job.id):
            if self._stop.is_set():
                return
            if page.status not in {PageStatus.PENDING, PageStatus.RENDERED}:
                continue
            latest = await asyncio.to_thread(self.jobs.get, job.id)
            if not latest or latest.cancel_requested:
                await self._finalize_pdf(job.id, JobStatus.CANCELLED)
                return
            await asyncio.to_thread(self.jobs.update_status, job.id, JobStatus.PROCESSING, current_page_number=page.page_number)
            self.active_page_number = page.page_number
            image_path = Path(page.image_path) if page.image_path else self.storage.page_image_path(job.id, page.page_number)
            if page.status == PageStatus.PENDING:
                await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.RENDERING, started_at=utc_now())
                try:
                    rendered = await asyncio.to_thread(self.pdf.render_page, source, page.page_number, job.pdf_dpi or 200, image_path)
                    page = await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.RENDERED, image_path=str(image_path), render_duration_ms=rendered.duration_ms)
                    logger.info("pdf page rendered", extra={"job_id": job.id, "page_number": page.page_number, "operation": "render", "render_duration_ms": rendered.duration_ms})
                except AppError as exc:
                    await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.FAILED, error_code=exc.code, error_message=exc.message, completed_at=utc_now())
                    await asyncio.to_thread(self.jobs.recalculate_progress, job.id)
                    continue
            await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.PROCESSING)
            try:
                work = output / ".work" / f"page_{page.page_number:04d}"
                result = await self.model.infer_image(image_path, work)
                try:
                    result_paths = await asyncio.to_thread(self.storage.write_page_results, output, page.page_number, result.markdown, result.plain_text)
                except Exception as exc:
                    raise AppError("PAGE_RESULT_WRITE_FAILED", "The page result could not be saved.", 500) from exc
                await asyncio.to_thread(
                    self.jobs.update_page, page.id, PageStatus.COMPLETED,
                    markdown_result_path=str(result_paths[0]), text_result_path=str(result_paths[1]),
                    inference_duration_ms=result.duration_ms, peak_allocated_vram_mb=result.peak_allocated_vram_mb,
                    completed_at=utc_now(), error_code=None, error_message=None,
                )
                logger.info("page inference completed", extra={"job_id": job.id, "page_number": page.page_number, "operation": "inference", "inference_duration_ms": result.duration_ms})
            except AppError as exc:
                code = exc.code if exc.code in {"OCR_CUDA_OUT_OF_MEMORY", "PAGE_RESULT_WRITE_FAILED"} else "PAGE_OCR_FAILED"
                await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.FAILED, error_code=code, error_message=exc.message, completed_at=utc_now())
                logger.error("page failed", extra={"job_id": job.id, "page_number": page.page_number, "operation": "inference", "error_code": code})
            except Exception:
                await asyncio.to_thread(self.jobs.update_page, page.id, PageStatus.FAILED, error_code="PAGE_OCR_FAILED", error_message="OCR failed for this page.", completed_at=utc_now())
            await asyncio.to_thread(self.jobs.recalculate_progress, job.id)
            latest = await asyncio.to_thread(self.jobs.get, job.id)
            if latest and latest.cancel_requested:
                await self._finalize_pdf(job.id, JobStatus.CANCELLED)
                return
            if self._stop.is_set():
                return
        await self._finalize_pdf(job.id)

    async def _finalize_pdf(self, job_id: str, forced_status: JobStatus | None = None) -> None:
        job = await asyncio.to_thread(self.jobs.recalculate_progress, job_id)
        if not job:
            return
        pages = await asyncio.to_thread(self.jobs.pages, job_id)
        markdown_parts: list[str] = []
        text_parts: list[str] = []
        json_pages: list[dict[str, object]] = []
        total_duration = 0
        for page in pages:
            markdown, plain = None, None
            if page.status == PageStatus.COMPLETED and page.markdown_result_path and page.text_result_path:
                markdown = self.storage.read_text(Path(page.markdown_result_path)); plain = self.storage.read_text(Path(page.text_result_path))
                markdown_parts.append(f"## Page {page.page_number}\n\n{markdown}")
                text_parts.append(f"===== PAGE {page.page_number} =====\n\n{plain}")
            elif page.status == PageStatus.FAILED:
                markdown_parts.append(f"## Page {page.page_number}\n\n> OCR failed for this page.\n> Error: {page.error_code}")
                text_parts.append(f"===== PAGE {page.page_number} =====\n\n[OCR FAILED: {page.error_code}]")
            else:
                markdown_parts.append(f"## Page {page.page_number}\n\n> OCR not processed for this page.")
                text_parts.append(f"===== PAGE {page.page_number} =====\n\n[NOT PROCESSED]")
            total_duration += (page.render_duration_ms or 0) + (page.inference_duration_ms or 0)
            json_pages.append({"page_number": page.page_number, "status": page.status, "markdown": markdown, "text": plain, "render_duration_ms": page.render_duration_ms, "inference_duration_ms": page.inference_duration_ms, "peak_allocated_vram_mb": page.peak_allocated_vram_mb, "error": {"code": page.error_code, "message": page.error_message} if page.error_code else None})
        if forced_status:
            status = forced_status
        elif job.successful_pages and job.failed_pages:
            status = JobStatus.COMPLETED_WITH_ERRORS
        elif job.successful_pages == job.total_pages:
            status = JobStatus.COMPLETED
        else:
            status = JobStatus.FAILED
        finished = utc_now()
        payload = {"job_id": job.id, "original_filename": job.original_filename, "file_type": "pdf", "status": status, "ocr_mode": job.ocr_mode, "pdf_dpi": job.pdf_dpi, "total_pages": job.total_pages, "processed_pages": job.processed_pages, "successful_pages": job.successful_pages, "failed_pages": job.failed_pages, "duration_ms": total_duration, "pages": json_pages}
        combined_markdown = "# OCR Result\n\n" + "\n\n---\n\n".join(markdown_parts)
        paths = await asyncio.to_thread(self.storage.write_results, Path(job.output_directory), combined_markdown, "\n\n".join(text_parts), payload)
        await asyncio.to_thread(self.jobs.update_status, job.id, status, completed_at=finished, processing_duration_ms=total_duration, markdown_result_path=str(paths[0]), text_result_path=str(paths[1]), json_result_path=str(paths[2]), current_page_number=None)
