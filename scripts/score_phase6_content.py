from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, "services/api")

from app.services.phase6_scoring import (
    aggregate_content_metrics,
    aggregate_numeric_results,
    aggregate_table_results,
    category_content_aggregates,
    dpi_content_aggregates,
    highest_error_records,
    load_multi_page_ocr,
    load_page_ground_truth,
    metric_distribution,
    metric_result,
    metric_result_dict,
    multi_page_metric_result_dict,
    normalize_content_relaxed,
    normalize_content_strict,
    normalize_raw_markdown,
    score_page_aligned_document,
    score_numeric_fields,
    score_table,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evaluation" / "reports"


def source_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def single_page_metrics(ground_truth: str, ocr_markdown: str) -> dict:
    return {
        "raw_markdown": metric_result_dict(metric_result(ground_truth, ocr_markdown, normalize_raw_markdown)),
        "strict_content": metric_result_dict(metric_result(ground_truth, ocr_markdown, normalize_content_strict)),
        "relaxed_content": metric_result_dict(metric_result(ground_truth, ocr_markdown, normalize_content_relaxed)),
    }


def manifest_by_id() -> dict[str, dict]:
    return {item["id"]: item for item in json.loads((ROOT / "evaluation" / "manifest.json").read_text(encoding="utf-8"))}


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def per_document_dpi_comparison(records: list[dict]) -> list[dict]:
    output = []
    for document_id in sorted({record["document_id"] for record in records if record["evaluation_type"] == "dpi"}):
        selected = sorted((record for record in records if record["evaluation_type"] == "dpi" and record["document_id"] == document_id), key=lambda record: record["dpi"])
        values = {str(record["dpi"]): record["metrics"] for record in selected}
        output.append(
            {
                "document_id": document_id,
                "dpi_metrics": values,
                "best_relaxed_cer_dpi": min(selected, key=lambda record: record["metrics"]["relaxed_content"]["cer"])["dpi"],
                "best_relaxed_wer_dpi": min(selected, key=lambda record: record["metrics"]["relaxed_content"]["wer"])["dpi"],
            }
        )
    return output


def main() -> None:
    canonical = json.loads((REPORTS / "canonical-records.json").read_text(encoding="utf-8"))
    validation = json.loads((REPORTS / "canonical-record-validation.json").read_text(encoding="utf-8"))
    if not validation.get("valid"):
        raise SystemExit("canonical validation failed")

    manifest = manifest_by_id()
    records: list[dict] = []
    for record in canonical["records"]:
        ocr_path = source_path(record["ocr_source_path"])
        truth_path = source_path(record["ground_truth_source_path"])
        ocr_markdown = ocr_path.read_text(encoding="utf-8")
        ground_truth = truth_path.read_text(encoding="utf-8")
        if not ocr_markdown.strip() or not ground_truth.strip():
            raise SystemExit(f"{record['record_id']} has an empty source")

        result = {
            **record,
            "ocr_bytes": len(ocr_markdown.encode("utf-8")),
            "ground_truth_bytes": len(ground_truth.encode("utf-8")),
        }
        if record["category"] == "multi-page":
            page_truth = manifest[record["document_id"]].get("page_ground_truth_path")
            if not page_truth:
                raise SystemExit(f"{record['record_id']} is missing page_ground_truth_path")
            page_result = score_page_aligned_document(
                load_multi_page_ocr(ocr_path), load_page_ground_truth(source_path(page_truth))
            )
            page_data = multi_page_metric_result_dict(page_result)
            result.update(
                {
                    "page_aligned": True,
                    "expected_page_numbers": [page.page_number for page in load_page_ground_truth(source_path(page_truth))],
                    "ocr_page_numbers": [page.page_number for page in load_multi_page_ocr(ocr_path)],
                    "pages": page_data["pages"],
                    "metrics": page_data["document_metrics"],
                }
            )
        else:
            result["page_aligned"] = False
            result["metrics"] = single_page_metrics(ground_truth, ocr_markdown)
        document = manifest[record["document_id"]]
        strict_ocr = normalize_content_strict(ocr_markdown)
        if document.get("numeric_fields"):
            result["numeric_fields"] = score_numeric_fields(strict_ocr, document["numeric_fields"])
        if document.get("table"):
            result["table"] = score_table(ocr_markdown, document["table"])
        records.append(result)

    if len(records) != 38:
        raise SystemExit(f"expected 38 records, found {len(records)}")
    multi_page_records = [record for record in records if record["category"] == "multi-page"]
    if not multi_page_records or not all(record.get("page_aligned") and record.get("pages") for record in multi_page_records):
        raise SystemExit("multi-page records were not page aligned")

    def median(mode: str, key: str) -> float:
        return statistics.median(record["metrics"][mode][key] for record in records)

    primary_records = [record for record in records if record["evaluation_type"] == "primary"]
    category_names = [
        "clean-digital", "scanned-print", "low-resolution", "rotated", "multi-column",
        "tables", "invoice-receipt", "bilingual", "numeric", "multi-page",
    ]
    category_aggregates = category_content_aggregates(records, category_names)
    dpi_aggregates = dpi_content_aggregates(records)
    distributions = {
        "method": "nearest-rank percentiles: ceil(n * percentile / 100), one-based rank",
        "primary": {f"{mode}_{metric}": metric_distribution(primary_records, mode, metric) for mode in ("strict_content", "relaxed_content") for metric in ("cer", "wer")},
        "canonical": {f"{mode}_{metric}": metric_distribution(records, mode, metric) for mode in ("strict_content", "relaxed_content") for metric in ("cer", "wer")},
    }
    high_error_records = {
        "raw_markdown_cer": highest_error_records(records, "raw_markdown", "cer"),
        "relaxed_content_cer": highest_error_records(records, "relaxed_content", "cer"),
        "raw_markdown_wer": highest_error_records(records, "raw_markdown", "wer"),
        "relaxed_content_wer": highest_error_records(records, "relaxed_content", "wer"),
    }
    numeric_field_results = [field for record in records for field in record.get("numeric_fields", [])]
    table_results = [record["table"] for record in records if "table" in record]
    summary = {
        "records": 38,
        "primary": sum(record["evaluation_type"] == "primary" for record in records),
        "dpi": sum(record["evaluation_type"] == "dpi" for record in records),
        "median_raw_cer": median("raw_markdown", "cer"),
        "median_strict_cer": median("strict_content", "cer"),
        "median_relaxed_cer": median("relaxed_content", "cer"),
        "median_raw_wer": median("raw_markdown", "wer"),
        "median_strict_wer": median("strict_content", "wer"),
        "median_relaxed_wer": median("relaxed_content", "wer"),
        "multi_page_records": [record["record_id"] for record in multi_page_records],
    }
    structured = {
        "category_content_aggregates": category_aggregates,
        "dpi_content_aggregates": dpi_aggregates,
        "per_document_dpi_comparison": per_document_dpi_comparison(records),
        "metric_distributions": distributions,
        "highest_error_records": high_error_records,
        "numeric_schemas_used": {document_id: document.get("numeric_fields", []) for document_id, document in manifest.items() if document.get("numeric_fields")},
        "numeric_per_field_results": numeric_field_results,
        "numeric_aggregate_accuracy": aggregate_numeric_results(numeric_field_results),
        "table_schemas_used": {document_id: document["table"] for document_id, document in manifest.items() if document.get("table")},
        "table_per_document_results": [{"record_id": record["record_id"], "document_id": record["document_id"], "result": record["table"]} for record in records if "table" in record],
        "table_aggregate_accuracy": aggregate_table_results(table_results),
        "known_limitations": ["Layout structure is not evaluated by table cell scoring.", "No manual layout review has been performed in this stage."],
    }
    payload = {"canonical_validation": validation, "summary": summary, "structured": structured, "records": records}
    write_json_atomic(REPORTS / "phase6-content-results.json", payload)
    (REPORTS / "phase6-content-summary.md").write_text(
        "# Phase 6 content metrics\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n\n"
        "## Structured metrics\n\n```json\n" + json.dumps({"category_content_aggregates": category_aggregates, "dpi_content_aggregates": dpi_aggregates}, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    write_json_atomic(REPORTS / "phase6-structured-results.json", structured)
    (REPORTS / "phase6-structured-summary.md").write_text(
        "# Phase 6 structured scoring\n\n```json\n" + json.dumps({"numeric_aggregate_accuracy": structured["numeric_aggregate_accuracy"], "table_aggregate_accuracy": structured["table_aggregate_accuracy"]}, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
