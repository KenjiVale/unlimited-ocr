from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import OperationalError
import uuid

from app.db.session import Database
from app.models.job import JobStatus, OCRJob, utc_now
from app.models.page import OCRPage, PageStatus

ACTIVE_STATUSES = {JobStatus.LOADING_MODEL, JobStatus.PROCESSING, JobStatus.CANCEL_REQUESTED}
TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS, JobStatus.FAILED, JobStatus.CANCELLED}


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, job: OCRJob) -> OCRJob:
        with self.database.session() as session:
            session.add(job); session.commit(); session.refresh(job); return job

    def add_pdf(self, job: OCRJob, page_count: int) -> OCRJob:
        with self.database.session() as session:
            session.add(job)
            session.add_all([OCRPage(id=str(uuid.uuid4()), job_id=job.id, page_number=number, status=PageStatus.PENDING, created_at=job.created_at, updated_at=job.updated_at) for number in range(1, page_count + 1)])
            session.commit(); session.refresh(job); return job

    def add_with_capacity(self, job: OCRJob, page_count: int | None, maximum: int) -> OCRJob:
        waiting = [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.INTERRUPTED]
        try:
            with self.database.session() as session:
                session.execute(text("BEGIN IMMEDIATE"))
                queued = session.scalar(select(func.count()).select_from(OCRJob).where(OCRJob.status.in_(waiting))) or 0
                if queued >= maximum:
                    session.rollback()
                    from app.core.errors import AppError
                    raise AppError("QUEUE_CAPACITY_REACHED", "The OCR queue has reached its configured capacity.", 429)
                session.add(job)
                if page_count:
                    session.add_all([OCRPage(id=str(uuid.uuid4()), job_id=job.id, page_number=number, status=PageStatus.PENDING, created_at=job.created_at, updated_at=job.updated_at) for number in range(1, page_count + 1)])
                session.commit(); session.refresh(job); return job
        except OperationalError as exc:
            from app.core.errors import AppError
            if "locked" in str(exc).lower(): raise AppError("DATABASE_BUSY", "The job database is busy.", 503) from exc
            raise AppError("DATABASE_WRITE_FAILED", "The OCR job could not be persisted.", 500) from exc

    def queued_count(self) -> int:
        with self.database.session() as session:
            return session.scalar(select(func.count()).select_from(OCRJob).where(OCRJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.INTERRUPTED]))) or 0

    def get(self, job_id: str) -> OCRJob | None:
        with self.database.session() as session:
            return session.get(OCRJob, job_id)

    def pages(self, job_id: str) -> list[OCRPage]:
        with self.database.session() as session:
            return list(session.scalars(select(OCRPage).where(OCRPage.job_id == job_id).order_by(OCRPage.page_number)))

    def page(self, job_id: str, page_number: int) -> OCRPage | None:
        with self.database.session() as session:
            return session.scalar(select(OCRPage).where(OCRPage.job_id == job_id, OCRPage.page_number == page_number))

    def update_page(self, page_id: str, status: PageStatus, **values: object) -> OCRPage | None:
        with self.database.session() as session:
            values.update(status=status, updated_at=utc_now())
            session.execute(update(OCRPage).where(OCRPage.id == page_id).values(**values)); session.commit()
            return session.get(OCRPage, page_id)

    def recalculate_progress(self, job_id: str) -> OCRJob | None:
        with self.database.session() as session:
            rows = session.execute(select(OCRPage.status, func.count()).where(OCRPage.job_id == job_id).group_by(OCRPage.status)).all()
            counts = {str(status): count for status, count in rows}
            total = session.scalar(select(func.count()).select_from(OCRPage).where(OCRPage.job_id == job_id)) or 0
            successful = counts.get(PageStatus.COMPLETED, 0)
            failed = counts.get(PageStatus.FAILED, 0)
            skipped = counts.get(PageStatus.SKIPPED, 0)
            processed = successful + failed + skipped
            progress = min(100, round(processed / total * 100)) if total else 0
            session.execute(update(OCRJob).where(OCRJob.id == job_id).values(total_pages=total or 1, processed_pages=processed, successful_pages=successful, failed_pages=failed, progress_percent=progress, updated_at=utc_now()))
            session.commit()
        return self.get(job_id)

    def list(self, limit: int, offset: int, status: str | None) -> list[OCRJob]:
        with self.database.session() as session:
            statement = select(OCRJob)
            if status:
                statement = statement.where(OCRJob.status == status)
            return list(session.scalars(statement.order_by(OCRJob.created_at.desc()).limit(limit).offset(offset)))

    def claim_next(self) -> OCRJob | None:
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            job_id = session.scalar(select(OCRJob.id).where(OCRJob.status == JobStatus.QUEUED, OCRJob.cancel_requested.is_(False)).order_by(OCRJob.queued_at, OCRJob.created_at).limit(1))
            if job_id is None:
                session.commit(); return None
            now = utc_now()
            claimed = session.execute(
                update(OCRJob).where(OCRJob.id == job_id, OCRJob.status == JobStatus.QUEUED, OCRJob.cancel_requested.is_(False))
                .values(status=JobStatus.LOADING_MODEL, started_at=now, updated_at=now).returning(OCRJob.id)
            ).scalar_one_or_none()
            session.commit()
            return self.get(job_id) if claimed else None

    def update_status(self, job_id: str, status: JobStatus, **values: object) -> OCRJob | None:
        with self.database.session() as session:
            values.update(status=status, updated_at=utc_now())
            session.execute(update(OCRJob).where(OCRJob.id == job_id).values(**values)); session.commit()
        return self.get(job_id)

    def request_cancel(self, job_id: str) -> OCRJob | None:
        job = self.get(job_id)
        if not job or job.status in TERMINAL_STATUSES:
            return job
        next_status = JobStatus.CANCELLED if job.status in {JobStatus.PENDING, JobStatus.QUEUED, JobStatus.INTERRUPTED} else JobStatus.CANCEL_REQUESTED
        completed = utc_now() if next_status == JobStatus.CANCELLED else None
        return self.update_status(job_id, next_status, cancel_requested=True, completed_at=completed)

    def retry(self, job_id: str) -> OCRJob | None:
        job = self.get(job_id)
        if not job or job.status not in {JobStatus.FAILED, JobStatus.INTERRUPTED, JobStatus.CANCELLED, JobStatus.COMPLETED_WITH_ERRORS}:
            return None
        if job.file_type == "pdf":
            with self.database.session() as session:
                session.execute(update(OCRPage).where(OCRPage.job_id == job_id, OCRPage.status.in_([PageStatus.FAILED, PageStatus.SKIPPED, PageStatus.RENDERING, PageStatus.PROCESSING])).values(status=PageStatus.PENDING, error_code=None, error_message=None, started_at=None, completed_at=None, updated_at=utc_now()))
                session.commit()
            self.recalculate_progress(job_id)
        now = utc_now()
        return self.update_status(job_id, JobStatus.QUEUED, cancel_requested=False, error_code=None, error_message=None, queued_at=now, started_at=None, completed_at=None, processing_duration_ms=None)

    def delete(self, job_id: str) -> None:
        with self.database.session() as session:
            session.execute(delete(OCRJob).where(OCRJob.id == job_id)); session.commit()

    def retry_page(self, job_id: str, page_number: int) -> OCRPage | None:
        page = self.page(job_id, page_number)
        if not page or page.status not in {PageStatus.FAILED, PageStatus.SKIPPED}:
            return None
        self.update_page(page.id, PageStatus.PENDING, error_code=None, error_message=None, started_at=None, completed_at=None)
        self.recalculate_progress(job_id)
        self.update_status(job_id, JobStatus.QUEUED, cancel_requested=False, error_code=None, error_message=None, queued_at=utc_now(), completed_at=None)
        return self.page(job_id, page_number)

    def recover_interrupted(self) -> dict[str, int]:
        counts = {"interrupted": 0, "requeued": 0, "failed": 0}
        with self.database.session() as session:
            jobs = list(session.scalars(select(OCRJob).where(OCRJob.status.in_([JobStatus.LOADING_MODEL, JobStatus.PROCESSING, JobStatus.CANCEL_REQUESTED]))))
            for job in jobs:
                counts["interrupted"] += 1
                job.status = JobStatus.INTERRUPTED
                job.updated_at = utc_now()
                if job.cancel_requested:
                    job.status, job.completed_at = JobStatus.CANCELLED, utc_now()
                elif Path(job.source_path).is_file():
                    if job.file_type == "pdf":
                        active_pages = list(session.scalars(select(OCRPage).where(OCRPage.job_id == job.id, OCRPage.status.in_([PageStatus.RENDERING, PageStatus.PROCESSING]))))
                        for page in active_pages:
                            page.status = PageStatus.RENDERED if page.image_path and Path(page.image_path).is_file() else PageStatus.PENDING
                            page.started_at = None; page.updated_at = utc_now()
                    job.status, job.queued_at, job.started_at = JobStatus.QUEUED, utc_now(), None
                    job.error_code = job.error_message = None
                    counts["requeued"] += 1
                else:
                    job.status, job.error_code = JobStatus.FAILED, "SOURCE_FILE_MISSING"
                    job.error_message, job.completed_at = "The source image is missing.", utc_now()
                    counts["failed"] += 1
            session.commit()
        for job in jobs:
            if job.file_type == "pdf":
                self.recalculate_progress(job.id)
        return counts
