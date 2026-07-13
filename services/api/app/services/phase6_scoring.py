from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import unicodedata


class OCRPageParseError(ValueError):
    pass


class DuplicateOCRPageNumber(OCRPageParseError):
    pass


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    markdown: str


@dataclass(frozen=True)
class GroundTruthPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class Counts:
    substitutions: int
    insertions: int
    deletions: int
    reference_length: int

    @property
    def error_rate(self) -> float | None:
        if self.reference_length == 0:
            return None
        return (self.substitutions + self.insertions + self.deletions) / self.reference_length


@dataclass(frozen=True)
class MetricResult:
    cer: float | None
    wer: float | None
    character_edits: Counts
    word_edits: Counts


@dataclass(frozen=True)
class PageMetricResult:
    page_number: int
    ocr_present: bool
    ground_truth_present: bool
    raw_markdown: MetricResult
    strict_content: MetricResult
    relaxed_content: MetricResult


@dataclass(frozen=True)
class MultiPageMetricResult:
    pages: list[PageMetricResult]
    raw_markdown: MetricResult
    strict_content: MetricResult
    relaxed_content: MetricResult


def extract_ocr_pages_from_markdown(markdown: str) -> list[OCRPage]:
    markers = list(re.finditer(r"^## Page ([1-9][0-9]*)\s*$", markdown, re.MULTILINE))
    if not markers:
        raise OCRPageParseError("no valid page markers")

    pages: list[OCRPage] = []
    seen: set[int] = set()
    for index, marker in enumerate(markers):
        page_number = int(marker.group(1))
        end = markers[index + 1].start() if index + 1 < len(markers) else len(markdown)
        content = markdown[marker.end() : end].strip()
        if page_number in seen:
            raise DuplicateOCRPageNumber(str(page_number))
        if pages and page_number < pages[-1].page_number:
            raise OCRPageParseError("OCR page markers must be strictly ascending")
        if not content:
            raise OCRPageParseError(f"empty page {page_number}")
        seen.add(page_number)
        pages.append(OCRPage(page_number, content))
    return pages


def load_multi_page_ocr(path: Path) -> list[OCRPage]:
    if not path.is_file():
        raise OCRPageParseError(f"missing OCR source: {path}")
    markdown = path.read_text(encoding="utf-8")
    if not markdown.strip():
        raise OCRPageParseError(f"empty OCR source: {path}")
    try:
        return extract_ocr_pages_from_markdown(markdown)
    except OCRPageParseError as error:
        raise type(error)(f"{path}: {error}") from error


def load_page_ground_truth(path: Path) -> list[GroundTruthPage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("document_id") or not isinstance(data.get("pages"), list):
        raise ValueError(f"invalid page ground truth: {path}")

    pages: list[GroundTruthPage] = []
    seen: set[int] = set()
    for item in data["pages"]:
        page_number = item.get("page_number")
        text = item.get("text", "")
        if not isinstance(page_number, int) or page_number < 1:
            raise ValueError(f"invalid ground-truth page number: {path}")
        if page_number in seen:
            raise ValueError(f"duplicate ground-truth page number {page_number}: {path}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"empty ground-truth page {page_number}: {path}")
        seen.add(page_number)
        pages.append(GroundTruthPage(page_number, text))
    return pages


def _counts(reference: list[str], hypothesis: list[str]) -> Counts:
    matrix = [[(0, column, 0) for column in range(len(hypothesis) + 1)]]
    for row_index in range(1, len(reference) + 1):
        row = [(0, 0, row_index)]
        for column_index in range(1, len(hypothesis) + 1):
            if reference[row_index - 1] == hypothesis[column_index - 1]:
                row.append(matrix[row_index - 1][column_index - 1])
                continue
            substitution = matrix[row_index - 1][column_index - 1]
            insertion = row[column_index - 1]
            deletion = matrix[row_index - 1][column_index]
            candidates = [
                (substitution[0] + 1, substitution[1], substitution[2]),
                (insertion[0], insertion[1] + 1, insertion[2]),
                (deletion[0], deletion[1], deletion[2] + 1),
            ]
            row.append(min(candidates, key=sum))
        matrix.append(row)
    substitutions, insertions, deletions = matrix[-1][-1]
    return Counts(substitutions, insertions, deletions, len(reference))


def character_edit_counts(reference: str, hypothesis: str) -> Counts:
    return _counts(list(reference), list(hypothesis))


def word_edit_counts(reference: str, hypothesis: str) -> Counts:
    return _counts(reference.split(), hypothesis.split())


def calculate_cer(reference: str, hypothesis: str) -> Counts:
    return character_edit_counts(reference, hypothesis)


def calculate_wer(reference: str, hypothesis: str) -> Counts:
    return word_edit_counts(reference, hypothesis)


def normalize_raw_markdown(text: str) -> str:
    return "\n".join(unicodedata.normalize("NFC", text).replace("\r\n", "\n").splitlines()).strip()


def normalize_content_strict(text: str) -> str:
    normalized = normalize_raw_markdown(text)
    normalized = re.sub(r"(?m)^# OCR Result\s*$|^## Page \d+\s*$|^---\s*$|^```.*$", "", normalized)
    normalized = re.sub(r"(?m)^#{1,6}\s*", "", normalized)
    normalized = re.sub(r"(?m)^\s*\|?-{3,}\|?\s*$", "", normalized)
    return re.sub(r"[*`_]", "", normalized).strip()


def normalize_content_relaxed(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_content_strict(text)).strip()


def validate_paths(ocr: Path, truth: Path, completed: bool = True) -> None:
    if ocr.resolve() == truth.resolve():
        raise ValueError("OCR/ground-truth path collision")
    if not truth.is_file() or not truth.read_text(encoding="utf-8").strip():
        raise ValueError("missing ground truth")
    if completed and (not ocr.is_file() or not ocr.read_text(encoding="utf-8").strip()):
        raise ValueError("missing OCR result")


def _add_counts(left: Counts, right: Counts) -> Counts:
    return Counts(
        left.substitutions + right.substitutions,
        left.insertions + right.insertions,
        left.deletions + right.deletions,
        left.reference_length + right.reference_length,
    )


def _empty_counts() -> Counts:
    return Counts(0, 0, 0, 0)


def metric_result(reference: str, hypothesis: str, normalizer) -> MetricResult:
    normalized_reference = normalizer(reference)
    normalized_hypothesis = normalizer(hypothesis)
    characters = calculate_cer(normalized_reference, normalized_hypothesis)
    words = calculate_wer(normalized_reference, normalized_hypothesis)
    return MetricResult(characters.error_rate, words.error_rate, characters, words)


def _aggregate_metric_results(results: list[MetricResult]) -> MetricResult:
    characters = _empty_counts()
    words = _empty_counts()
    for result in results:
        characters = _add_counts(characters, result.character_edits)
        words = _add_counts(words, result.word_edits)
    return MetricResult(characters.error_rate, words.error_rate, characters, words)


def _page_map(pages, label: str) -> dict[int, object]:
    mapping: dict[int, object] = {}
    for page in pages:
        if page.page_number in mapping:
            raise ValueError(f"duplicate {label} page number {page.page_number}")
        mapping[page.page_number] = page
    return mapping


def score_page_aligned_document(
    ocr_pages: list[OCRPage], ground_truth_pages: list[GroundTruthPage]
) -> MultiPageMetricResult:
    """Score page N against page N; never reorder by OCR content or position."""
    ocr_by_number = _page_map(ocr_pages, "OCR")
    truth_by_number = _page_map(ground_truth_pages, "ground-truth")
    page_results: list[PageMetricResult] = []

    for page_number in sorted(set(ocr_by_number) | set(truth_by_number)):
        ocr_page = ocr_by_number.get(page_number)
        truth_page = truth_by_number.get(page_number)
        ocr_markdown = ocr_page.markdown if ocr_page else ""
        ground_truth = truth_page.text if truth_page else ""
        page_results.append(
            PageMetricResult(
                page_number=page_number,
                ocr_present=ocr_page is not None,
                ground_truth_present=truth_page is not None,
                raw_markdown=metric_result(ground_truth, ocr_markdown, normalize_raw_markdown),
                strict_content=metric_result(ground_truth, ocr_markdown, normalize_content_strict),
                relaxed_content=metric_result(ground_truth, ocr_markdown, normalize_content_relaxed),
            )
        )

    return MultiPageMetricResult(
        pages=page_results,
        raw_markdown=_aggregate_metric_results([page.raw_markdown for page in page_results]),
        strict_content=_aggregate_metric_results([page.strict_content for page in page_results]),
        relaxed_content=_aggregate_metric_results([page.relaxed_content for page in page_results]),
    )


def page_counts(reference_pages: list[str], ocr_pages: list[str]) -> tuple[Counts, Counts]:
    """Compatibility helper retained for existing scorer tests."""
    result = score_page_aligned_document(
        [OCRPage(index + 1, text) for index, text in enumerate(ocr_pages)],
        [GroundTruthPage(index + 1, text) for index, text in enumerate(reference_pages)],
    )
    return result.raw_markdown.character_edits, result.raw_markdown.word_edits


def metric_result_dict(result: MetricResult) -> dict:
    return {
        "cer": result.cer,
        "wer": result.wer,
        "character_edits": asdict(result.character_edits),
        "word_edits": asdict(result.word_edits),
    }


def multi_page_metric_result_dict(result: MultiPageMetricResult) -> dict:
    return {
        "pages": [
            {
                "page_number": page.page_number,
                "ocr_present": page.ocr_present,
                "ground_truth_present": page.ground_truth_present,
                "raw_markdown": metric_result_dict(page.raw_markdown),
                "strict_content": metric_result_dict(page.strict_content),
                "relaxed_content": metric_result_dict(page.relaxed_content),
            }
            for page in result.pages
        ],
        "document_metrics": {
            "raw_markdown": metric_result_dict(result.raw_markdown),
            "strict_content": metric_result_dict(result.strict_content),
            "relaxed_content": metric_result_dict(result.relaxed_content),
        },
    }


def percentile(values: list[float], percentile_value: float) -> float:
    """Nearest-rank percentile used by the Phase 6 reports."""
    if not values:
        raise ValueError("cannot calculate a percentile of an empty list")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * percentile_value + 99) // 100) - 1))
    return ordered[index]


def metric_distribution(records: list[dict], mode: str, metric_name: str) -> dict:
    values = [record["metrics"][mode][metric_name] for record in records]
    if any(value is None for value in values):
        raise ValueError(f"null {mode} {metric_name} in aggregate input")
    return {
        "zero_records": sum(value == 0 for value in values),
        "nonzero_records": sum(value != 0 for value in values),
        "minimum": min(values),
        "median": percentile(values, 50),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
        "maximum": max(values),
    }


def aggregate_content_metrics(records: list[dict]) -> dict:
    if not records:
        raise ValueError("cannot aggregate no records")
    output = {"record_count": len(records)}
    for mode in ("raw_markdown", "strict_content", "relaxed_content"):
        for metric_name in ("cer", "wer"):
            values = [record["metrics"][mode][metric_name] for record in records]
            if any(value is None for value in values):
                raise ValueError(f"null {mode} {metric_name} in aggregate input")
            output[f"median_{mode}_{metric_name}"] = percentile(values, 50)
            if mode == "relaxed_content":
                output[f"minimum_{mode}_{metric_name}"] = min(values)
                output[f"maximum_{mode}_{metric_name}"] = max(values)
    return output


def category_content_aggregates(records: list[dict], categories: list[str]) -> dict[str, dict]:
    output: dict[str, dict] = {}
    primary = [record for record in records if record["evaluation_type"] == "primary" and not record.get("excluded")]
    for category in categories:
        selected = [record for record in primary if record.get("category") == category]
        if len(selected) != 2:
            raise ValueError(f"category {category} requires exactly two primary records, found {len(selected)}")
        output[category] = aggregate_content_metrics(selected)
    return output


def dpi_content_aggregates(records: list[dict]) -> dict[str, dict]:
    dpi_records = [record for record in records if record["evaluation_type"] == "dpi" and not record.get("excluded")]
    output: dict[str, dict] = {}
    for dpi in sorted({record["dpi"] for record in dpi_records}):
        selected = [record for record in dpi_records if record["dpi"] == dpi]
        if len(selected) != 6:
            raise ValueError(f"DPI {dpi} requires exactly six canonical records, found {len(selected)}")
        output[str(dpi)] = aggregate_content_metrics(selected)
    return output


def highest_error_records(records: list[dict], mode: str, metric_name: str, count: int = 5) -> list[dict]:
    ranked = sorted(records, key=lambda record: record["metrics"][mode][metric_name], reverse=True)[:count]
    return [
        {
            "record_id": record["record_id"],
            "document_id": record["document_id"],
            "category": record.get("category"),
            "evaluation_type": record["evaluation_type"],
            "dpi": record["dpi"],
            "metric": record["metrics"][mode][metric_name],
            "ocr_source_path": record.get("ocr_source_path"),
            "ground_truth_source_path": record.get("ground_truth_source_path"),
        }
        for record in ranked
    ]


NUMERIC_FAILURE_BY_TYPE = {
    "identifier": "IDENTIFIER_MISMATCH",
    "date": "DATE_MISMATCH",
    "currency": "CURRENCY_MISMATCH",
    "percentage": "PERCENTAGE_MISMATCH",
    "quantity": "QUANTITY_MISMATCH",
    "phone": "PHONE_MISMATCH",
}


def _digits(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def _normalise_currency_number(value: str) -> str:
    return _digits(value)


def _normalise_identifier(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", value.upper())


def _normalise_date(value: str) -> str | None:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y"):
        try:
            from datetime import datetime
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _field_candidates(text: str, field: dict) -> list[tuple[str, str, tuple[int, int]]]:
    field_type = field["type"]
    if field_type == "currency":
        return [
            (match.group(0), f"{'IDR' if match.group(1).upper() == 'RP' else match.group(1).upper()}:{_normalise_currency_number(match.group(2))}", match.span())
            for match in re.finditer(r"(?i)\b(RP|IDR)\s*([0-9][0-9.,]*)", text)
        ]
    if field_type == "date":
        pattern = r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b"
        accepted = set(field.get("accepted_formats", [field["expected"]]))
        return [
            (match.group(0), _normalise_date(match.group(0)) or "", match.span())
            for match in re.finditer(pattern, text)
            if match.group(0) in accepted
        ]
    if field_type == "identifier":
        expected = _normalise_identifier(field["expected"])
        return [
            (match.group(0), _normalise_identifier(match.group(0)), match.span())
            for match in re.finditer(r"\b[A-Za-z]+[\s-]*[0-9][A-Za-z0-9-]*\b", text)
            if _normalise_identifier(match.group(0)) == expected
        ]
    if field_type == "phone":
        return [(match.group(0), _digits(match.group(0)), match.span()) for match in re.finditer(r"\+?[0-9][0-9\s().-]{5,}[0-9]", text)]
    if field_type == "percentage":
        return [(match.group(0), _digits(match.group(1)), match.span()) for match in re.finditer(r"\b([0-9][0-9.,]*)\s*%", text)]
    return [(match.group(0), _digits(match.group(0)), match.span()) for match in re.finditer(r"\b[0-9][0-9.,]*\b", text)]


def score_numeric_fields(ocr_text: str, fields: list[dict]) -> list[dict]:
    """Exact, non-reusing schema matching against OCR content."""
    used_spans: set[tuple[int, int]] = set()
    results: list[dict] = []
    for field in fields:
        field_type = field["type"]
        if field_type == "currency":
            expected = f"{field['expected_currency'].upper()}:{_normalise_currency_number(field['expected_numeric'])}"
        elif field_type == "date":
            expected = _normalise_date(field["expected"])
        elif field_type == "identifier":
            expected = _normalise_identifier(field["expected"])
        else:
            expected = _digits(str(field["expected"]))
        candidates = _field_candidates(ocr_text, field)
        match = next((item for item in candidates if item[1] == expected and item[2] not in used_spans), None)
        currency_missing = field_type == "currency" and _normalise_currency_number(field["expected_numeric"]) in _digits(ocr_text) and match is None
        if match:
            used_spans.add(match[2])
        failure = None if match else ("CURRENCY_MISSING" if currency_missing else NUMERIC_FAILURE_BY_TYPE.get(field_type, "NUMBER_MISMATCH"))
        results.append(
            {
                "name": field["name"],
                "type": field_type,
                "expected": expected,
                "observed": match[1] if match else None,
                "matched_ocr_span": match[0] if match else None,
                "normalization_applied": "deterministic_schema_normalization",
                "correct": match is not None,
                "failure_category": failure,
            }
        )
    return results


def aggregate_numeric_results(results: list[dict]) -> dict:
    output: dict[str, dict] = {}
    types = ["identifier", "date", "currency", "integer", "decimal", "percentage", "quantity", "phone"]
    for field_type in ["overall", *types]:
        selected = results if field_type == "overall" else [result for result in results if result["type"] == field_type]
        correct = sum(result["correct"] for result in selected)
        output[field_type] = {"correct": correct, "total": len(selected), "accuracy": correct / len(selected) if selected else None}
    return output


def _table_cells_from_line(line: str) -> list[str]:
    stripped = line.strip()
    if "|" in stripped:
        return [cell.strip() for cell in stripped.strip("|").split("|")]
    return re.split(r"\s+", stripped)


def extract_table_cells(markdown: str, headers: list[str], row_count: int) -> tuple[list[str], list[list[str]]]:
    lines = [line for line in normalize_content_strict(markdown).splitlines() if line.strip()]
    expected_header = [_normalise_identifier(header) for header in headers]
    for index, line in enumerate(lines):
        cells = _table_cells_from_line(line)
        if [_normalise_identifier(cell) for cell in cells] != expected_header:
            continue
        rows: list[list[str]] = []
        for candidate in lines[index + 1 :]:
            if re.fullmatch(r"\s*\|?\s*-{3,}.*", candidate):
                continue
            row = _table_cells_from_line(candidate)
            if len(row) == len(headers):
                rows.append(row)
            if len(rows) == row_count:
                return cells, rows
        return cells, rows
    return [], []


def _cell_equal(expected: str, observed: str) -> bool:
    return normalize_content_relaxed(expected) == normalize_content_relaxed(observed)


def score_table(markdown: str, schema: dict) -> dict:
    headers = schema["headers"]
    expected_rows = schema["rows"]
    observed_headers, observed_rows = extract_table_cells(markdown, headers, len(expected_rows))
    header_results = [
        {"expected": value, "observed": observed_headers[index] if index < len(observed_headers) else None,
         "correct": index < len(observed_headers) and _cell_equal(value, observed_headers[index])}
        for index, value in enumerate(headers)
    ]
    body_results: list[dict] = []
    row_preserved: list[bool] = []
    for row_index, expected_row in enumerate(expected_rows):
        actual_row = observed_rows[row_index] if row_index < len(observed_rows) else []
        row_cells = []
        for column_index, expected in enumerate(expected_row):
            observed = actual_row[column_index] if column_index < len(actual_row) else None
            row_cells.append({"row": row_index, "column": column_index, "expected": expected, "observed": observed,
                              "correct": observed is not None and _cell_equal(expected, observed)})
        body_results.extend(row_cells)
        row_preserved.append(all(cell["correct"] for cell in row_cells))
    numeric = [cell for cell in body_results if re.fullmatch(r"[0-9][0-9.,]*", cell["expected"])]
    all_cells = header_results + body_results
    def accuracy(items: list[dict]) -> dict:
        correct = sum(item["correct"] for item in items)
        return {"correct": correct, "total": len(items), "accuracy": correct / len(items) if items else None}
    return {
        "headers": header_results,
        "body_cells": body_results,
        "row_content_preservation": {"correct": sum(row_preserved), "total": len(row_preserved), "accuracy": sum(row_preserved) / len(row_preserved) if row_preserved else None},
        "header_cell_accuracy": accuracy(header_results),
        "body_cell_accuracy": accuracy(body_results),
        "numeric_cell_accuracy": accuracy(numeric),
        "overall_cell_accuracy": accuracy(all_cells),
    }


def aggregate_table_results(results: list[dict]) -> dict:
    keys = ["header_cell_accuracy", "body_cell_accuracy", "numeric_cell_accuracy", "row_content_preservation", "overall_cell_accuracy"]
    output = {}
    for key in keys:
        correct = sum(result[key]["correct"] for result in results)
        total = sum(result[key]["total"] for result in results)
        output[key] = {"correct": correct, "total": total, "accuracy": correct / total if total else None}
    return output
