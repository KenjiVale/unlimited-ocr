import json
from pathlib import Path

from conftest import upload, upload_pdf, wait_for_status


def test_pdf_upload_pages_sequential_outputs_and_apis(app_client) -> None:
    client, model, root = app_client
    response = upload_pdf(client, pages=3, dpi=150); assert response.status_code == 202
    job_id = response.json()["id"]
    initial = client.get(f"/api/ocr/jobs/{job_id}").json()
    assert initial["file_type"] == "pdf" and initial["total_pages"] == 3 and initial["pdf_dpi"] == 150
    done = wait_for_status(client, job_id, {"COMPLETED"})
    assert (done["processed_pages"], done["successful_pages"], done["progress_percent"]) == (3, 3, 100)
    assert model.calls == 3 and model.max_active == 1
    pages = client.get(f"/api/ocr/jobs/{job_id}/pages").json()["pages"]
    assert [page["page_number"] for page in pages] == [1, 2, 3]
    assert all(page["status"] == "COMPLETED" for page in pages)
    assert client.get(f"/api/ocr/jobs/{job_id}/pages/1/result").status_code == 200
    assert client.get(f"/api/ocr/jobs/{job_id}/pages/99").json()["error"]["code"] == "PAGE_NOT_FOUND"
    output = root / "outputs" / job_id
    markdown = (output / "result.md").read_text(encoding="utf-8")
    text = (output / "result.txt").read_text(encoding="utf-8")
    payload = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert markdown.index("## Page 1") < markdown.index("## Page 2") < markdown.index("## Page 3")
    assert markdown.startswith("# OCR Result\n\n## Page 1")
    assert text.index("PAGE 1") < text.index("PAGE 2") < text.index("PAGE 3")
    assert [page["page_number"] for page in payload["pages"]] == [1, 2, 3]
    assert all((output / "pages" / f"page_{number:04d}.md").is_file() for number in (1, 2, 3))


def test_partial_and_total_failure_are_isolated(app_client) -> None:
    client, model, root = app_client
    model.failures_remaining = 1
    partial_id = upload_pdf(client, pages=3).json()["id"]
    partial = wait_for_status(client, partial_id, {"COMPLETED_WITH_ERRORS"})
    assert partial["successful_pages"] == 2 and partial["failed_pages"] == 1
    combined = (root / "outputs" / partial_id / "result.md").read_text(encoding="utf-8")
    assert "OCR failed for this page" in combined and "## Page 3" in combined
    model.failures_remaining = 2
    failed_id = upload_pdf(client, pages=2).json()["id"]
    failed = wait_for_status(client, failed_id, {"FAILED"})
    assert failed["failed_pages"] == 2 and failed["progress_percent"] == 100


def test_active_pdf_cancellation_stops_before_next_page(app_client) -> None:
    client, model, root = app_client
    model.delay = 0.2
    job_id = upload_pdf(client, pages=3).json()["id"]
    wait_for_status(client, job_id, {"PROCESSING"})
    client.post(f"/api/ocr/jobs/{job_id}/cancel")
    cancelled = wait_for_status(client, job_id, {"CANCELLED"})
    assert model.calls == 1 and cancelled["processed_pages"] == 1 and cancelled["progress_percent"] < 100
    assert (root / "outputs" / job_id / "pages" / "page_0001.md").is_file()


def test_page_retry_preserves_successful_pages(app_client) -> None:
    client, model, _ = app_client
    model.failures_remaining = 1
    job_id = upload_pdf(client, pages=3).json()["id"]
    wait_for_status(client, job_id, {"COMPLETED_WITH_ERRORS"})
    calls = model.calls
    response = client.post(f"/api/ocr/jobs/{job_id}/pages/1/retry")
    assert response.status_code == 200 and response.json()["status"] == "PENDING"
    wait_for_status(client, job_id, {"COMPLETED"})
    assert model.calls == calls + 1
    assert client.post(f"/api/ocr/jobs/{job_id}/pages/2/retry").json()["error"]["code"] == "PAGE_NOT_RETRYABLE"
    assert client.post(f"/api/ocr/jobs/{job_id}/retry").json()["error"]["code"] == "JOB_ALREADY_COMPLETED"


def test_pdf_job_retry_only_repeats_failed_pages(app_client) -> None:
    client, model, _ = app_client
    model.failures_remaining = 1
    job_id = upload_pdf(client, pages=3).json()["id"]
    wait_for_status(client, job_id, {"COMPLETED_WITH_ERRORS"}); calls = model.calls
    response = client.post(f"/api/ocr/jobs/{job_id}/retry")
    assert response.status_code == 200 and response.json()["status"] == "QUEUED"
    wait_for_status(client, job_id, {"COMPLETED"})
    assert model.calls == calls + 1


def test_image_regression_remains_one_page(app_client) -> None:
    client, _, _ = app_client
    job_id = upload(client).json()["id"]
    done = wait_for_status(client, job_id, {"COMPLETED"})
    assert done["file_type"] == "png" and done["total_pages"] == 1 and done["progress_percent"] == 100
