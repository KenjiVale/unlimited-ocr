import json
import time
from pathlib import Path

from conftest import upload, upload_pdf, wait_for_status


def test_worker_state_heartbeat_and_resources(app_client) -> None:
    client, _, _ = app_client
    first=client.get("/api/system/worker").json(); time.sleep(0.22); second=client.get("/api/system/worker").json()
    assert first["state"] in {"IDLE","CLAIMING"}
    assert second["last_heartbeat_at"] != first["last_heartbeat_at"]
    assert second["process_rss_bytes"] > 0 and second["available_ram_bytes"] > 0


def test_worker_exposes_active_job_page_and_remains_responsive(app_client) -> None:
    client, model, _ = app_client; model.delay=.3
    job_id=upload_pdf(client,pages=2).json()["id"]
    wait_for_status(client,job_id,{"PROCESSING"})
    status=client.get("/api/system/worker").json()
    started=time.perf_counter(); health=client.get("/api/health"); latency=(time.perf_counter()-started)*1000
    assert status["active_job_id"]==job_id and status["active_page_number"] in {1,2}
    assert health.status_code==200 and latency<250


def test_worker_failure_is_reported_and_worker_survives(app_client) -> None:
    client, model, _=app_client; model.failures_remaining=1
    job_id=upload(client).json()["id"]; wait_for_status(client,job_id,{"FAILED"})
    time.sleep(.05); status=client.get("/api/system/worker").json()
    assert status["failed_jobs_since_start"]==1 and status["last_error"] is not None
    next_id=upload(client).json()["id"]; wait_for_status(client,next_id,{"COMPLETED"})


def test_queue_capacity_excludes_active_and_terminal(app_client) -> None:
    client, model, _=app_client; model.delay=.3; client.app.state.settings.max_queued_jobs=1
    active=upload(client).json()["id"]; wait_for_status(client,active,{"PROCESSING"})
    queued=upload(client); assert queued.status_code==202
    rejected=upload(client); assert rejected.status_code==429 and rejected.json()["error"]["code"]=="QUEUE_CAPACITY_REACHED"
    wait_for_status(client,active,{"COMPLETED"}); wait_for_status(client,queued.json()["id"],{"COMPLETED"})
    assert upload(client).status_code==202


def test_disk_preflight_rejects_low_space(monkeypatch, app_client) -> None:
    client, _, _=app_client; client.app.state.settings.min_free_disk_gb=5
    usage=type("Usage",(),{"total":10_000,"used":9_000,"free":1_000})()
    monkeypatch.setattr("app.services.reliability.shutil.disk_usage",lambda _:usage)
    response=upload(client)
    assert response.status_code==507 and response.json()["error"]["code"]=="INSUFFICIENT_DISK_SPACE"


def test_sqlite_pragmas_are_applied(app_client) -> None:
    client, _, _=app_client
    with client.app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar().lower()=="wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar()==1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar()==5000


def test_valid_integrity_and_detects_corruption(app_client) -> None:
    client, _, _=app_client; job_id=upload_pdf(client,pages=2).json()["id"]; wait_for_status(client,job_id,{"COMPLETED"})
    assert client.get(f"/api/ocr/jobs/{job_id}/integrity").json()["valid"]
    job=client.app.state.jobs.get(job_id); Path(job.markdown_result_path).unlink()
    issues=client.get(f"/api/ocr/jobs/{job_id}/integrity").json()["issues"]
    assert "RESULT_MARKDOWN_MISSING" in issues
    Path(job.json_result_path).write_text("broken",encoding="utf-8")
    assert "RESULT_JSON_INVALID" in client.get(f"/api/ocr/jobs/{job_id}/integrity").json()["issues"]


def test_cleanup_preview_run_idempotent_and_preserves_source_outputs_model(app_client) -> None:
    client, _, root=app_client; job_id=upload_pdf(client,pages=2).json()["id"]; wait_for_status(client,job_id,{"COMPLETED"})
    body={"older_than_days":0,"include_rendered_pages":True,"include_source_files":False,"include_outputs":False,"include_orphans":False}
    preview=client.post("/api/maintenance/cleanup/preview",json=body).json()
    assert preview["rendered_page_files"]==2 and (root/"pages"/job_id).exists()
    result=client.post("/api/maintenance/cleanup/run",json=body).json()
    assert result["deleted_items"]>=1 and not (root/"pages"/job_id).exists()
    assert (root/"uploads"/job_id).exists() and (root/"outputs"/job_id).exists()
    assert client.post("/api/maintenance/cleanup/run",json=body).json()["failed_items"]==0


def test_orphan_detection_and_explicit_cleanup(app_client) -> None:
    client, _, root=app_client; orphan=root/"pages"/"orphan-test"; orphan.mkdir(parents=True); (orphan/"x.png").write_bytes(b"x")
    assert client.get("/api/system/storage?refresh=true").json()["orphaned_directories"]>=1
    safe={"older_than_days":0,"include_rendered_pages":False,"include_source_files":False,"include_outputs":False,"include_orphans":False}
    client.post("/api/maintenance/cleanup/run",json=safe); assert orphan.exists()
    safe["include_orphans"]=True; result=client.post("/api/maintenance/cleanup/run",json=safe).json()
    assert result["orphaned_directories"]>=1 and not orphan.exists()


def test_repeated_cancel_and_recovery_are_idempotent(app_client) -> None:
    client, model, _=app_client; model.delay=.3
    active=upload(client).json()["id"]; wait_for_status(client,active,{"PROCESSING"})
    queued=upload(client).json()["id"]
    first=client.post(f"/api/ocr/jobs/{queued}/cancel").json(); second=client.post(f"/api/ocr/jobs/{queued}/cancel").json()
    assert first["status"]==second["status"]=="CANCELLED"
    wait_for_status(client,active,{"COMPLETED"})
    assert client.app.state.jobs.recover_interrupted()=={"interrupted":0,"requeued":0,"failed":0}
