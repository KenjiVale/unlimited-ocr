from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.system import router as system_router
from app.api.jobs import router as jobs_router
from app.api.maintenance import router as maintenance_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError, app_error_handler
from app.db import Database
from app.services.jobs import JobRepository
from app.services.model import ModelService
from app.services.storage import StorageService
from app.services.pdf import PDFService
from app.services.reliability import CleanupService, IntegrityService, StorageMonitor
from app.workers.ocr import OCRWorker


def create_app(settings: Settings | None = None, model_factory: Callable[[Settings], ModelService] = ModelService) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        storage = StorageService(configured.data_dir); storage.initialize()
        database = Database(configured.database_url, configured.database_busy_timeout_ms, configured.database_journal_mode); database.initialize()
        jobs = JobRepository(database)
        recovery = jobs.recover_interrupted()
        model_service = model_factory(configured)
        worker = OCRWorker(configured, jobs, storage, model_service)
        app.state.settings, app.state.storage, app.state.database = configured, storage, database
        app.state.jobs, app.state.model_service, app.state.worker = jobs, model_service, worker
        app.state.pdf_service = PDFService()
        monitor=StorageMonitor(configured,storage,jobs)
        app.state.storage_monitor=monitor; app.state.integrity_service=IntegrityService(storage,jobs); app.state.cleanup_service=CleanupService(storage,jobs,monitor)
        logging.getLogger("unlimited_ocr").info("startup recovery", extra={"operation": "recovery", **recovery})
        worker.start()
        try:
            yield
        finally:
            await worker.stop()
            database.close()

    app = FastAPI(title="Unlimited OCR Local API", version="0.2.0", lifespan=lifespan)
    app.state.settings = configured
    app.include_router(system_router)
    app.include_router(jobs_router)
    app.include_router(maintenance_router)
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_middleware(CORSMiddleware, allow_origins=[configured.next_public_api_url.replace(":8000", ":3000")], allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
    return app


app = create_app()
