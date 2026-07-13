import sqlite3
import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import Database
from app.models.job import JobStatus, OCRJob, utc_now
from app.models.page import OCRPage, PageStatus
from app.services.jobs import JobRepository


PHASE2_SCHEMA = """CREATE TABLE ocr_jobs (
id VARCHAR(36) PRIMARY KEY, original_filename VARCHAR(255) NOT NULL, stored_filename VARCHAR(255) NOT NULL,
file_type VARCHAR(20) NOT NULL, status VARCHAR(32) NOT NULL, ocr_mode VARCHAR(20) NOT NULL,
source_path TEXT NOT NULL, output_directory TEXT NOT NULL, markdown_result_path TEXT, text_result_path TEXT,
json_result_path TEXT, error_code VARCHAR(64), error_message TEXT, cancel_requested BOOLEAN NOT NULL,
created_at DATETIME NOT NULL, queued_at DATETIME, started_at DATETIME, completed_at DATETIME,
updated_at DATETIME NOT NULL, processing_duration_ms INTEGER)"""


def test_phase2_migration_preserves_records_and_is_idempotent(app_client) -> None:
    _, _, root = app_client; path = root / "legacy.db"
    connection = sqlite3.connect(path); connection.execute(PHASE2_SCHEMA)
    job_id = str(uuid.uuid4())
    connection.execute("INSERT INTO ocr_jobs(id,original_filename,stored_filename,file_type,status,ocr_mode,source_path,output_directory,cancel_requested,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (job_id, "old.png", "source.png", "png", "COMPLETED", "gundam", "old", "out", 0, "2026-01-01", "2026-01-01"))
    connection.commit(); connection.close()
    database = Database(f"sqlite:///{path.as_posix()}"); database.initialize(); database.initialize()
    with database.engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT id,total_pages,processed_pages,progress_percent FROM ocr_jobs").one()
        versions = conn.exec_driver_sql("SELECT count(*) FROM schema_migrations WHERE version=3").scalar_one()
    database.close()
    assert tuple(row) == (job_id, 1, 1, 100) and versions == 1


def test_page_unique_constraint(app_client) -> None:
    client, _, _ = app_client; jobs = client.app.state.jobs
    now = utc_now(); job_id = str(uuid.uuid4())
    job = OCRJob(id=job_id, original_filename="a.pdf", stored_filename="source.pdf", file_type="pdf", status=JobStatus.QUEUED, ocr_mode="gundam", source_path="source", output_directory="output", cancel_requested=False, created_at=now, updated_at=now, total_pages=1, processed_pages=0, successful_pages=0, failed_pages=0, progress_percent=0, pdf_dpi=200)
    jobs.add_pdf(job, 1)
    with pytest.raises(IntegrityError), jobs.database.session() as session:
        session.add(OCRPage(id=str(uuid.uuid4()), job_id=job_id, page_number=1, status=PageStatus.PENDING, created_at=now, updated_at=now)); session.commit()


def test_page_recovery_preserves_completed_and_resets_active(app_client) -> None:
    _, _, root = app_client
    path = root / "recovery.db"; database = Database(f"sqlite:///{path.as_posix()}"); database.initialize(); jobs = JobRepository(database)
    source = root / "resume.pdf"; source.write_bytes(b"source")
    now = utc_now(); job_id = str(uuid.uuid4())
    job = OCRJob(id=job_id, original_filename="a.pdf", stored_filename="source.pdf", file_type="pdf", status=JobStatus.PROCESSING, ocr_mode="gundam", source_path=str(source), output_directory=str(root / "out"), cancel_requested=False, created_at=now, updated_at=now, total_pages=3, processed_pages=0, successful_pages=0, failed_pages=0, progress_percent=0, pdf_dpi=200)
    jobs.add_pdf(job, 3); pages = jobs.pages(job_id)
    jobs.update_page(pages[0].id, PageStatus.COMPLETED, markdown_result_path="one.md", text_result_path="one.txt", completed_at=now)
    jobs.update_page(pages[1].id, PageStatus.PROCESSING)
    result = jobs.recover_interrupted()
    recovered = jobs.pages(job_id)
    assert result["requeued"] == 1 and jobs.get(job_id).status == JobStatus.QUEUED
    assert [page.status for page in recovered] == [PageStatus.COMPLETED, PageStatus.PENDING, PageStatus.PENDING]
    database.close()


def test_missing_pdf_source_recovery_is_stable(app_client) -> None:
    _, _, root = app_client
    database = Database(f"sqlite:///{(root / 'missing.db').as_posix()}"); database.initialize(); jobs = JobRepository(database)
    now = utc_now(); job_id = str(uuid.uuid4())
    job = OCRJob(id=job_id, original_filename="missing.pdf", stored_filename="source.pdf", file_type="pdf", status=JobStatus.PROCESSING, ocr_mode="gundam", source_path=str(root / "absent.pdf"), output_directory=str(root / "out-missing"), cancel_requested=False, created_at=now, updated_at=now, total_pages=1, processed_pages=0, successful_pages=0, failed_pages=0, progress_percent=0, pdf_dpi=200)
    jobs.add_pdf(job, 1); jobs.recover_interrupted()
    recovered = jobs.get(job_id)
    assert recovered.status == JobStatus.FAILED and recovered.error_code == "SOURCE_FILE_MISSING"
    database.close()
