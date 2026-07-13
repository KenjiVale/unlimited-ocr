from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import fitz
import httpx


def create_pdf(path: Path, pages: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    for number in range(1, pages + 1):
        page = document.new_page(width=900, height=1200)
        page.insert_text((90, 160), f"PHASE THREE PAGE {number}", fontsize=36)
        page.insert_text((90, 240), f"This is sequential offline OCR page {number} of {pages}.", fontsize=22)
        page.insert_text((90, 300), "Unlimited OCR Local - RTX 5070", fontsize=22)
    document.save(path); document.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--pdf", type=Path, default=Path("data/uploads/phase3-verification.pdf"))
    args = parser.parse_args()
    try:
        create_pdf(args.pdf)
        with httpx.Client(base_url=args.url, timeout=30) as client:
            model_before = client.get("/api/system/model").json()
            upload_started = time.perf_counter()
            with args.pdf.open("rb") as stream:
                response = client.post("/api/ocr/jobs", files={"file": (args.pdf.name, stream, "application/pdf")}, data={"ocr_mode": "gundam", "pdf_dpi": "200"})
            upload_ms = round((time.perf_counter() - upload_started) * 1000); response.raise_for_status()
            created = response.json(); job_id = created["id"]
            job_transitions = [created["status"]]; page_transitions = {str(number): [] for number in range(1, 4)}
            maximum_processing_pages = 0; health_latencies: list[int] = []
            processing_started = time.perf_counter(); deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                health_started = time.perf_counter(); client.get("/api/health").raise_for_status()
                health_latencies.append(round((time.perf_counter() - health_started) * 1000))
                job = client.get(f"/api/ocr/jobs/{job_id}").json()
                if job["status"] != job_transitions[-1]: job_transitions.append(job["status"])
                pages = client.get(f"/api/ocr/jobs/{job_id}/pages").json()["pages"]
                maximum_processing_pages = max(maximum_processing_pages, sum(page["status"] == "PROCESSING" for page in pages))
                for page in pages:
                    history = page_transitions[str(page["page_number"])]
                    if not history or history[-1] != page["status"]: history.append(page["status"])
                if job["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "CANCELLED"}: break
                time.sleep(0.05)
            else: raise RuntimeError("PDF job timed out")
            total_ms = round((time.perf_counter() - processing_started) * 1000)
            if job["status"] != "COMPLETED": raise RuntimeError(json.dumps(job))
            combined = client.get(f"/api/ocr/jobs/{job_id}/result"); combined.raise_for_status()
            page_results = []
            for number in range(1, 4):
                page_result = client.get(f"/api/ocr/jobs/{job_id}/pages/{number}/result"); page_result.raise_for_status(); page_results.append(page_result.json())
            model_after = client.get("/api/system/model").json()
        output_dir = Path("data/outputs") / job_id
        evidence = {
            "job_id": job_id, "upload_ms": upload_ms, "total_ms": total_ms,
            "job_transitions": job_transitions, "page_transitions": page_transitions,
            "maximum_processing_pages": maximum_processing_pages,
            "maximum_health_latency_ms": max(health_latencies), "job": job, "pages": pages,
            "model_before": model_before, "model_after": model_after,
            "combined_result_length": len(combined.json()["markdown"]),
            "individual_page_results": len(page_results),
            "files": {name: (output_dir / name).is_file() for name in ("result.md", "result.txt", "result.json")},
        }
        print(json.dumps(evidence, indent=2)); return 0
    except Exception as exc:
        print(f"PHASE3_VERIFICATION_FAILED: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
