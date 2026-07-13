from __future__ import annotations

import asyncio
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
import fitz

from app.core.config import Settings
from app.main import create_app
from app.schemas.model import ModelStatusResponse
from app.services.model import OCRInferenceResult


class FakeModelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.status = "NOT_LOADED"
        self.loaded_at = None
        self.load_duration_ms = None
        self.calls = 0
        self.failures_remaining = 0
        self.delay = 0.03
        self.active = 0
        self.max_active = 0
        self._lock = asyncio.Lock()

    async def ensure_loaded(self) -> None:
        if self.status != "READY":
            self.status = "LOADING"
            await asyncio.sleep(0.01)
            self.status = "READY"
            self.loaded_at = datetime.now(timezone.utc)
            self.load_duration_ms = 10

    async def infer_image(self, image_path: Path, output_directory: Path) -> OCRInferenceResult:
        await self.ensure_loaded()
        async with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(self.delay)
                self.calls += 1
                if self.failures_remaining:
                    self.failures_remaining -= 1
                    raise RuntimeError("fake inference failure")
                return OCRInferenceResult("# Fake OCR\n\nhello", "Fake OCR\n\nhello", 31, 123, "gundam", "fake")
            finally:
                self.active -= 1

    def get_status(self) -> ModelStatusResponse:
        return ModelStatusResponse(status=self.status, model_id=self.settings.ocr_model_id, model_path="Unlimited-OCR", device="cuda", dtype="bfloat16", offline_mode=False, loaded_at=self.loaded_at, load_duration_ms=self.load_duration_ms, last_error=None)


@pytest.fixture
def app_client():
    root = (Path(__file__).parent.parent / ".test-data" / str(uuid.uuid4())).resolve()
    root.mkdir(parents=True)
    settings = Settings(app_env="test", data_dir=root, database_url=f"sqlite:///{(root / 'test.db').as_posix()}", ocr_model_path=root / "fake-model", hf_hub_offline=False, transformers_offline=False, upload_max_mb=1, worker_poll_seconds=0.01, worker_shutdown_timeout_seconds=2, worker_poll_interval_ms=50, worker_heartbeat_interval_seconds=0.1, worker_stale_after_seconds=1, min_free_disk_gb=0, shutdown_grace_seconds=1, _env_file=None)
    holder: dict[str, FakeModelService] = {}
    def factory(value: Settings) -> FakeModelService:
        holder["model"] = FakeModelService(value); return holder["model"]
    app = create_app(settings, factory)  # type: ignore[arg-type]
    with TestClient(app) as client:
        yield client, holder["model"], root


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (20, 20)) -> bytes:
    stream = io.BytesIO(); Image.new("RGB", size, "white").save(stream, format=fmt); return stream.getvalue()


def upload(client: TestClient, filename: str = "test.png", mime: str = "image/png", content: bytes | None = None):
    return client.post("/api/ocr/jobs", files={"file": (filename, content if content is not None else image_bytes(), mime)}, data={"ocr_mode": "gundam"})


def pdf_bytes(pages: int = 3, encrypted: bool = False) -> bytes:
    document = fitz.open()
    for number in range(1, pages + 1):
        page = document.new_page(width=600, height=800)
        page.insert_text((72, 100), f"PHASE THREE PAGE {number}", fontsize=24)
        page.insert_text((72, 150), f"Sequential OCR verification page {number}.", fontsize=14)
    if encrypted:
        data = document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    else:
        data = document.tobytes()
    document.close(); return data


def upload_pdf(client: TestClient, pages: int = 3, dpi: int = 200, content: bytes | None = None, filename: str = "test.pdf", mime: str = "application/pdf"):
    return client.post("/api/ocr/jobs", files={"file": (filename, content if content is not None else pdf_bytes(pages), mime)}, data={"ocr_mode": "gundam", "pdf_dpi": str(dpi)})


def wait_for_status(client: TestClient, job_id: str, statuses: set[str], timeout: float = 3) -> dict:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/ocr/jobs/{job_id}").json()
        if body["status"] in statuses: return body
        time.sleep(0.01)
    raise AssertionError(f"job did not reach {statuses}")
