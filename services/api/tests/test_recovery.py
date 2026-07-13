from pathlib import Path
import uuid
from app.models.job import JobStatus, OCRJob, utc_now


def make_job(root: Path, status: JobStatus, source_exists: bool = True, cancel: bool = False) -> OCRJob:
    job_id = str(uuid.uuid4()); source = root / f"{job_id}.png"
    if source_exists: source.write_bytes(b"source")
    now = utc_now()
    return OCRJob(id=job_id, original_filename="a.png", stored_filename="source.png", file_type="png", status=status, ocr_mode="gundam", source_path=str(source), output_directory=str(root / job_id), cancel_requested=cancel, created_at=now, updated_at=now)


def test_restart_recovery_requeues_or_fails_and_preserves_terminal(app_client) -> None:
    client, _, root = app_client; jobs = client.app.state.jobs
    processing = jobs.add(make_job(root, JobStatus.PROCESSING))
    missing = jobs.add(make_job(root, JobStatus.LOADING_MODEL, source_exists=False))
    completed = jobs.add(make_job(root, JobStatus.COMPLETED))
    cancelled = jobs.add(make_job(root, JobStatus.CANCELLED, cancel=True))
    result = jobs.recover_interrupted()
    assert result == {"interrupted": 2, "requeued": 1, "failed": 1}
    assert jobs.get(processing.id).status == JobStatus.QUEUED
    assert jobs.get(missing.id).error_code == "SOURCE_FILE_MISSING"
    assert jobs.get(completed.id).status == JobStatus.COMPLETED
    assert jobs.get(cancelled.id).status == JobStatus.CANCELLED


def test_atomic_claim_prevents_duplicate_processing(app_client) -> None:
    client, _, root = app_client; jobs = client.app.state.jobs
    job = jobs.add(make_job(root, JobStatus.QUEUED))
    claimed = jobs.claim_next(); duplicate = jobs.claim_next()
    assert claimed and claimed.id == job.id
    assert duplicate is None

