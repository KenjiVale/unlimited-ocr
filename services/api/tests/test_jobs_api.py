from conftest import upload, wait_for_status


def test_unsupported_ocr_mode_is_rejected(app_client) -> None:
    client, _, _ = app_client
    response = client.post("/api/ocr/jobs", files={"file": ("a.png", b"x", "image/png")}, data={"ocr_mode": "base"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_OCR_MODE"


def test_upload_persists_lists_fetches_and_returns_results(app_client) -> None:
    client, _, root = app_client
    response = upload(client); assert response.status_code == 202
    job_id = response.json()["id"]
    assert client.get("/api/ocr/jobs").json()["items"]
    assert client.get(f"/api/ocr/jobs/{job_id}").status_code == 200
    assert wait_for_status(client, job_id, {"COMPLETED"})["result_available"]
    result = client.get(f"/api/ocr/jobs/{job_id}/result")
    assert result.status_code == 200 and result.json()["markdown"].startswith("# Fake")
    output = root / "outputs" / job_id
    assert all((output / name).is_file() for name in ("result.md", "result.txt", "result.json"))
    for kind, content_type in (("markdown", "text/markdown"), ("text", "text/plain"), ("json", "application/json")):
        download = client.get(f"/api/ocr/jobs/{job_id}/download/{kind}")
        assert download.status_code == 200 and content_type in download.headers["content-type"]


def test_missing_job_and_unfinished_result_errors(app_client) -> None:
    client, model, _ = app_client
    assert client.get("/api/ocr/jobs/missing").json()["error"]["code"] == "JOB_NOT_FOUND"
    model.delay = 0.3; job_id = upload(client).json()["id"]
    result = client.get(f"/api/ocr/jobs/{job_id}/result")
    assert result.status_code == 409 and result.json()["error"]["code"] == "RESULT_NOT_AVAILABLE"


def test_cancel_queued_job_prevents_inference(app_client) -> None:
    client, model, _ = app_client
    model.delay = 0.3
    first = upload(client).json()["id"]; wait_for_status(client, first, {"PROCESSING"})
    second = upload(client).json()["id"]
    assert client.post(f"/api/ocr/jobs/{second}/cancel").json()["status"] == "CANCELLED"
    assert wait_for_status(client, second, {"CANCELLED"})["status"] == "CANCELLED"


def test_cooperative_cancel_during_inference(app_client) -> None:
    client, model, root = app_client
    model.delay = 0.2; job_id = upload(client).json()["id"]
    wait_for_status(client, job_id, {"PROCESSING"})
    assert client.post(f"/api/ocr/jobs/{job_id}/cancel").json()["status"] == "CANCEL_REQUESTED"
    wait_for_status(client, job_id, {"CANCELLED"})
    assert (root / "outputs" / job_id / "result.md").is_file()


def test_retry_failed_and_completed_not_retryable(app_client) -> None:
    client, model, _ = app_client
    model.failures_remaining = 1; job_id = upload(client).json()["id"]
    wait_for_status(client, job_id, {"FAILED"})
    assert client.post(f"/api/ocr/jobs/{job_id}/retry").json()["status"] == "QUEUED"
    wait_for_status(client, job_id, {"COMPLETED"})
    response = client.post(f"/api/ocr/jobs/{job_id}/retry")
    assert response.status_code == 409 and response.json()["error"]["code"] == "JOB_ALREADY_COMPLETED"


def test_active_cannot_delete_terminal_can_delete(app_client) -> None:
    client, model, _ = app_client
    model.delay = 0.2; job_id = upload(client).json()["id"]
    wait_for_status(client, job_id, {"PROCESSING"})
    assert client.delete(f"/api/ocr/jobs/{job_id}").status_code == 409
    wait_for_status(client, job_id, {"COMPLETED"})
    assert client.delete(f"/api/ocr/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/ocr/jobs/{job_id}").status_code == 404


def test_worker_survives_failure_and_gpu_concurrency_is_one(app_client) -> None:
    client, model, _ = app_client
    model.failures_remaining = 1
    ids = [upload(client, filename=f"{i}.png").json()["id"] for i in range(3)]
    statuses = [wait_for_status(client, value, {"FAILED", "COMPLETED"})["status"] for value in ids]
    assert statuses.count("FAILED") == 1 and statuses.count("COMPLETED") == 2
    assert model.max_active == 1


def test_model_is_lazy_then_reused(app_client) -> None:
    client, model, _ = app_client
    assert client.get("/api/system/model").json()["status"] == "NOT_LOADED"
    ids = [upload(client).json()["id"] for _ in range(2)]
    for job_id in ids: wait_for_status(client, job_id, {"COMPLETED"})
    assert client.get("/api/system/model").json()["status"] == "READY"
    assert model.calls == 2 and model.load_duration_ms == 10
