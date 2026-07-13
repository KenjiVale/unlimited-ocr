from fastapi import APIRouter, Request

from app.schemas.model import ModelStatusResponse
from app.schemas.system import GPUResponse, HealthResponse
from app.services.gpu import get_gpu_status
from app.schemas.reliability import StorageStatusResponse, WorkerStatusResponse
import psutil

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Liveness check; deliberately does not import or load the OCR model."""
    return HealthResponse(status="ok", app_env=request.app.state.settings.app_env)


@router.get("/system/gpu", response_model=GPUResponse)
def gpu() -> GPUResponse:
    return get_gpu_status()


@router.get("/system/model", response_model=ModelStatusResponse)
def model(request: Request) -> ModelStatusResponse:
    return request.app.state.model_service.get_status()


@router.get("/system/worker", response_model=WorkerStatusResponse)
def worker(request: Request) -> WorkerStatusResponse:
    item = request.app.state.worker
    try:
        import torch
        allocated = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        reserved = torch.cuda.memory_reserved() if torch.cuda.is_available() else 0
    except ImportError: allocated = reserved = 0
    return WorkerStatusResponse(state=item.state, started_at=item.started_at, last_heartbeat_at=item.last_heartbeat_at, active_job_id=item.active_job_id, active_page_number=item.active_page_number, last_completed_job_id=item.last_completed_job_id, queued_jobs=request.app.state.jobs.queued_count(), completed_jobs_since_start=item.completed_jobs_since_start, failed_jobs_since_start=item.failed_jobs_since_start, last_error={"code":item.last_error_code,"message":item.last_error_message} if item.last_error_code else None, process_rss_bytes=psutil.Process().memory_info().rss, available_ram_bytes=psutil.virtual_memory().available, allocated_vram_bytes=allocated, reserved_vram_bytes=reserved)


@router.get("/system/storage", response_model=StorageStatusResponse)
def storage(request: Request, refresh: bool = False) -> StorageStatusResponse:
    return StorageStatusResponse(**request.app.state.storage_monitor.status(refresh))
