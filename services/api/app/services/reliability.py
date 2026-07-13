from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path

import psutil

from app.core.config import Settings
from app.core.errors import AppError
from app.models.job import JobStatus, OCRJob
from app.services.jobs import JobRepository
from app.services.storage import StorageService


class WorkerState(StrEnum):
    STARTING="STARTING"; IDLE="IDLE"; CLAIMING="CLAIMING"; LOADING_MODEL="LOADING_MODEL"; PROCESSING="PROCESSING"; STOPPING="STOPPING"; STOPPED="STOPPED"; FAILED="FAILED"


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists(): return 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink(): total += item.stat().st_size
        except OSError: pass
    return total


class StorageMonitor:
    def __init__(self, settings: Settings, storage: StorageService, jobs: JobRepository) -> None:
        self.settings, self.storage, self.jobs = settings, storage, jobs
        self._cached: dict | None = None; self._cached_at = 0.0

    def preflight(self) -> None:
        try: free = shutil.disk_usage(self.storage.data_dir).free
        except OSError as exc: raise AppError("INSUFFICIENT_DISK_SPACE", "Disk space could not be verified.", 503) from exc
        required = int(self.settings.min_free_disk_gb * 1024**3)
        if free < required: raise AppError("INSUFFICIENT_DISK_SPACE", "There is not enough free disk space to accept a new OCR job.", 507, {"free_bytes": free, "required_free_bytes": required})

    def orphans(self) -> list[Path]:
        known = {job.id for job in self.jobs.list(100000, 0, None)}
        found: list[Path] = []
        for root in (self.storage.uploads_dir, self.storage.pages_dir, self.storage.outputs_dir):
            for child in root.iterdir() if root.exists() else []:
                if child.is_dir() and not child.is_symlink() and child.name not in known: found.append(child)
        return found

    def status(self, refresh: bool = False) -> dict:
        if self._cached and not refresh and time.monotonic() - self._cached_at < 10: return self._cached
        usage = shutil.disk_usage(self.storage.data_dir); required = int(self.settings.min_free_disk_gb * 1024**3)
        result = {"data_directory": self.settings.data_dir.name, "free_disk_bytes": usage.free, "used_disk_bytes": usage.used, "uploads_bytes": directory_size(self.storage.uploads_dir), "rendered_pages_bytes": directory_size(self.storage.pages_dir), "outputs_bytes": directory_size(self.storage.outputs_dir), "model_bytes": directory_size(self.storage.data_dir / "models"), "orphaned_directories": len(self.orphans()), "minimum_free_disk_bytes": required, "accepting_new_jobs": usage.free >= required and self.jobs.queued_count() < self.settings.max_queued_jobs}
        self._cached, self._cached_at = result, time.monotonic(); return result


class IntegrityService:
    def __init__(self, storage: StorageService, jobs: JobRepository) -> None: self.storage, self.jobs = storage, jobs
    def check(self, job: OCRJob) -> list[str]:
        issues: list[str] = []; root = self.storage.data_dir.resolve()
        paths = [(job.markdown_result_path,"RESULT_MARKDOWN_MISSING"),(job.text_result_path,"RESULT_TEXT_MISSING"),(job.json_result_path,"RESULT_JSON_MISSING")]
        for raw, code in paths:
            if not raw or not Path(raw).is_file(): issues.append(code)
            elif root not in Path(raw).resolve().parents: issues.append("PATH_OUTSIDE_DATA_DIRECTORY")
        if job.json_result_path and Path(job.json_result_path).is_file():
            try:
                payload=json.loads(Path(job.json_result_path).read_text(encoding="utf-8"))
                if payload.get("job_id") != job.id: issues.append("RESULT_JOB_ID_MISMATCH")
                if payload.get("status") != job.status: issues.append("RESULT_STATUS_MISMATCH")
            except Exception: issues.append("RESULT_JSON_INVALID")
        for page in self.jobs.pages(job.id):
            if page.status == "COMPLETED" and (not page.markdown_result_path or not Path(page.markdown_result_path).is_file() or not page.text_result_path or not Path(page.text_result_path).is_file()): issues.append("PAGE_RESULT_MISSING")
        return sorted(set(issues))


class CleanupService:
    TERMINAL={"COMPLETED","COMPLETED_WITH_ERRORS","FAILED","CANCELLED"}
    def __init__(self, storage: StorageService, jobs: JobRepository, monitor: StorageMonitor) -> None: self.storage,self.jobs,self.monitor=storage,jobs,monitor
    def plan(self, request) -> tuple[dict,list[Path]]:
        if not set(request.terminal_statuses).issubset(self.TERMINAL): raise AppError("CLEANUP_INVALID_REQUEST","Cleanup statuses must be terminal.",422)
        cutoff=datetime.now(timezone.utc)-timedelta(days=request.older_than_days); targets=[]; result={"jobs_considered":0,"rendered_page_files":0,"rendered_page_bytes":0,"source_files":0,"source_bytes":0,"output_files":0,"output_bytes":0,"orphaned_directories":0,"deleted_items":0,"deleted_bytes":0,"failed_items":0,"will_delete_database_records":False}
        for job in self.jobs.list(100000,0,None):
            completed=job.completed_at
            if job.status not in request.terminal_statuses or not completed or (completed.replace(tzinfo=timezone.utc) if completed.tzinfo is None else completed) > cutoff: continue
            result["jobs_considered"]+=1
            groups=[]
            if request.include_rendered_pages: groups.append((self.storage.pages_dir/job.id,"rendered_page"))
            if request.include_source_files: groups.append((self.storage.uploads_dir/job.id,"source"))
            if request.include_outputs: groups.append((self.storage.outputs_dir/job.id,"output"))
            for path,kind in groups:
                if path.exists():
                    files=[p for p in path.rglob("*") if p.is_file() and not p.is_symlink()]; size=sum(p.stat().st_size for p in files); targets.append(path)
                    result[kind+"_files" if kind!="rendered_page" else "rendered_page_files"]+=len(files); result[kind+"_bytes" if kind!="rendered_page" else "rendered_page_bytes"]+=size
        if request.include_orphans:
            orphaned=self.monitor.orphans(); result["orphaned_directories"]=len(orphaned); targets.extend(orphaned)
        return result,targets

    def run(self, request) -> dict:
        result,targets=self.plan(request); root=self.storage.data_dir.resolve()
        for target in targets:
            try:
                resolved=target.resolve()
                if root not in resolved.parents or resolved==root or resolved.name=="models": raise AppError("CLEANUP_PATH_REJECTED","Cleanup path was rejected.",400)
                size=directory_size(resolved); shutil.rmtree(resolved); result["deleted_items"]+=1; result["deleted_bytes"]+=size
            except Exception: result["failed_items"]+=1
        return result
