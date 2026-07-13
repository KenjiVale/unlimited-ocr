from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def run_job(client: httpx.Client, image: Path) -> dict[str, object]:
    started = time.perf_counter()
    with image.open("rb") as stream:
        response = client.post("/api/ocr/jobs", files={"file": (image.name, stream, "image/png")}, data={"ocr_mode": "gundam"})
    response.raise_for_status()
    submit_ms = round((time.perf_counter() - started) * 1000)
    job = response.json(); job_id = job["id"]
    transitions = [job["status"]]
    health_started = time.perf_counter(); client.get("/api/health").raise_for_status()
    health_ms = round((time.perf_counter() - health_started) * 1000)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        current = client.get(f"/api/ocr/jobs/{job_id}"); current.raise_for_status(); body = current.json()
        if body["status"] != transitions[-1]: transitions.append(body["status"])
        if body["status"] in {"COMPLETED", "FAILED", "CANCELLED"}: break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"Timed out waiting for {job_id}")
    if body["status"] != "COMPLETED": raise RuntimeError(json.dumps(body))
    result = client.get(f"/api/ocr/jobs/{job_id}/result"); result.raise_for_status()
    return {"job_id": job_id, "submit_ms": submit_ms, "health_during_job_ms": health_ms, "transitions": transitions, "job": body, "result": result.json()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        with httpx.Client(base_url=args.url, timeout=30) as client:
            before = client.get("/api/system/model"); before.raise_for_status()
            first = run_job(client, args.image)
            after_first = client.get("/api/system/model").json()
            second = run_job(client, args.image)
            after_second = client.get("/api/system/model").json()
        output = {
            "model_before": before.json(), "first": first, "model_after_first": after_first,
            "second": second, "model_after_second": after_second,
        }
        print(json.dumps(output, indent=2))
        return 0
    except Exception as exc:
        print(f"PHASE2_VERIFICATION_FAILED: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
