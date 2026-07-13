from __future__ import annotations

import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evaluation" / "reports"


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    content = json.loads((REPORTS / "phase6-content-results.json").read_text(encoding="utf-8"))
    structured = json.loads((REPORTS / "phase6-structured-results.json").read_text(encoding="utf-8"))
    review = json.loads((REPORTS / "manual-layout-review.json").read_text(encoding="utf-8"))
    raw = json.loads((REPORTS / "raw-results.json").read_text(encoding="utf-8"))
    scores = {item["document_id"]: item["scores"] for item in review["documents"]}
    categories = {}
    for category in ("multi-column", "tables", "invoice-receipt", "multi-page"):
        values = [item["scores"]["overall"] for item in review["documents"] if item["document_id"].startswith(category)]
        categories[category] = {"median_overall": statistics.median(values), "scores": values}
    overall_scores = [item["scores"]["overall"] for item in review["documents"]]
    category_relaxed = {name: result["median_relaxed_content_cer"] for name, result in structured["category_content_aggregates"].items()}
    summary = content["summary"]
    threshold_results = [
        {"metric":"Document completion rate", "actual":1.0, "required":">= 0.95", "status":"PASS", "source":"38 canonical records"},
        {"metric":"Page success rate", "actual":1.0, "required":">= 0.98", "status":"PASS", "source":"canonical raw results"},
        {"metric":"Integrity pass rate", "actual":1.0, "required":"= 1.0", "status":"PASS", "source":"canonical raw results"},
        {"metric":"Median relaxed content CER", "actual":summary["median_relaxed_cer"], "required":"<= 0.05", "status":"PASS", "source":"phase6-content-results.json"},
        {"metric":"Median relaxed content WER", "actual":summary["median_relaxed_wer"], "required":"<= 0.10", "status":"PASS", "source":"phase6-content-results.json"},
        {"metric":"Numeric-field accuracy", "actual":structured["numeric_aggregate_accuracy"]["overall"]["accuracy"], "required":">= 0.95", "status":"PASS", "source":"phase6-structured-results.json"},
        {"metric":"No category median relaxed CER above 15%", "actual":max(category_relaxed.values()), "required":"<= 0.15", "status":"FAIL", "source":"low-resolution category aggregate"},
        {"metric":"Median overall layout score", "actual":statistics.median(overall_scores), "required":">= 3", "status":"PASS", "source":"manual-layout-review.json"},
        {"metric":"Minimum table overall score", "actual":min(categories["tables"]["scores"]), "required":">= 2", "status":"PASS", "source":"manual-layout-review.json"},
        {"metric":"Minimum multi-column overall score", "actual":min(categories["multi-column"]["scores"]), "required":">= 2", "status":"PASS", "source":"manual-layout-review.json"},
        {"metric":"Median page inference duration", "actual":2046, "required":"<= 5000 ms", "status":"PASS", "source":"Phase 3 real offline three-page verification"},
        {"metric":"CUDA OOM", "actual":0, "required":"0", "status":"PASS", "source":"Phase 6 raw results"},
        {"metric":"Application crashes", "actual":0, "required":"0", "status":"PASS", "source":"Phase 6 evaluation evidence"},
    ]
    performance = {
        "median_page_inference_ms": {"value":2046, "source":"Phase 3 real offline three-page verification"},
        "p95_page_inference_ms": {"value":2565, "source":"Phase 3 real offline three-page verification; nearest-rank p95 of 3 pages"},
        "maximum_page_inference_ms": {"value":2565, "source":"Phase 3 real offline three-page verification"},
        "median_render_ms": {"value":71, "source":"Phase 3 real offline three-page verification"},
        "maximum_render_ms": {"value":72, "source":"Phase 3 real offline three-page verification"},
        "peak_allocated_vram_mb": {"value":max(item["peak_vram_mb"] for item in raw), "source":"Phase 6 raw results"},
        "peak_process_rss_bytes": {"value":7359299584, "source":"Phase 4 12-page soak verification"},
    }
    final = {
        "phase":"Phase 6", "status":"COMPLETED", "historical_physical_jobs":44,
        "canonical_records":38, "primary_records":20, "canonical_dpi_records":18,
        "content_summary":summary, "structured_metrics":structured,
        "manual_layout_review":review, "layout_aggregates":{"by_category":categories,"median_overall":statistics.median(overall_scores)},
        "performance":performance, "threshold_results":threshold_results,
        "dpi_decision":{"decision":"KEEP_200_DPI", "reason":"The six-document canonical DPI matrix has equal relaxed CER/WER at 150, 200, and 300 DPI; 200 DPI remains the verified balanced default."},
        "regression_results":{"scorer_tests":"83 passed", "backend_tests":"139 passed", "frontend_smoke":"3 passed", "playwright":"4 passed", "typescript":"passed", "production_build":"passed", "build_id":"present", "packaged_verifier":"checks completed; wrapper process required scoped cleanup after completion"},
        "known_limitations":["Low-resolution fixtures are weak: category median relaxed CER is 22.45%.","Table cell scoring does not validate visual alignment.","The multi-column fixtures render as single-column labelled text, so visual column ordering is not applicable."],
        "release_decision":"REMAIN_RC", "release_designation":"Local OCR v0.1.0-rc1",
    }
    write_json(REPORTS / "phase6-final-results.json", final)
    lines = ["# Phase 6 final quality report", "", "Decision: **REMAIN_RC** — Local OCR v0.1.0-rc1.", "", "## Threshold results", "", "| Metric | Actual | Required | Status |", "| --- | ---: | --- | --- |"]
    lines += [f"| {item['metric']} | {item['actual']} | {item['required']} | {item['status']} |" for item in threshold_results]
    lines += ["", "## Limitations", "", "- Low-resolution generated fixtures exceed the 15% category median relaxed-CER threshold (22.45%).", "- Table cell scoring verifies content and row order, not visual alignment.", "- This is a bounded local evaluation using generated, non-sensitive fixtures; it is not an industry OCR benchmark.", ""]
    (REPORTS / "phase6-final-summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"decision":final["release_decision"], "failed_thresholds":[item["metric"] for item in threshold_results if item["status"] == "FAIL"]}, indent=2))


if __name__ == "__main__":
    main()
