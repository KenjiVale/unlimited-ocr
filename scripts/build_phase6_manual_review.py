from __future__ import annotations

import html
import json
from pathlib import Path
import sys

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.services.phase6_scoring import (  # noqa: E402
    extract_ocr_pages_from_markdown,
    load_page_ground_truth,
    normalize_content_strict,
)


DOCUMENT_IDS = [
    "multi-column-01", "multi-column-02", "tables-01", "tables-02",
    "invoice-receipt-01", "invoice-receipt-02", "multi-page-01", "multi-page-02",
]


def pre(value: str) -> str:
    return f"<pre>{html.escape(value)}</pre>"


def render_pdf(input_path: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    with fitz.open(input_path) as document:
        for index, page in enumerate(document, start=1):
            target = destination / f"page_{index:04d}.png"
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pixmap.save(target)
            rendered.append(target)
    return rendered


def main() -> None:
    review_root = ROOT / "evaluation" / "reports" / "manual-review"
    assets = review_root / "assets"
    manifest = {entry["id"]: entry for entry in json.loads((ROOT / "evaluation" / "manifest.json").read_text(encoding="utf-8"))}
    sections: list[str] = []
    for document_id in DOCUMENT_IDS:
        entry = manifest[document_id]
        input_path = ROOT / entry["input_path"]
        ocr_path = ROOT / "evaluation" / "outputs" / f"{document_id}-200.md"
        raw_ocr = ocr_path.read_text(encoding="utf-8")
        ground_truth = (ROOT / entry["ground_truth_path"]).read_text(encoding="utf-8")
        rendered = render_pdf(input_path, assets / document_id)
        page_blocks: list[str] = []
        if entry["page_count"] > 1:
            ocr_pages = {page.page_number: page.markdown for page in extract_ocr_pages_from_markdown(raw_ocr)}
            truth_pages = {page.page_number: page.text for page in load_page_ground_truth(ROOT / entry["page_ground_truth_path"])}
            for number, image in enumerate(rendered, start=1):
                page_blocks.append(
                    f"<h3>Page {number}</h3><div class='grid'><section><h4>Rendered input</h4><img src='assets/{document_id}/{image.name}' alt='{document_id} page {number}'></section>"
                    f"<section><h4>Ground truth</h4>{pre(truth_pages[number])}</section><section><h4>Raw OCR Markdown</h4>{pre(ocr_pages[number])}</section>"
                    f"<section><h4>Strict normalized OCR</h4>{pre(normalize_content_strict(ocr_pages[number]))}</section></div>"
                )
        else:
            image = rendered[0]
            page_blocks.append(
                f"<div class='grid'><section><h4>Rendered input</h4><img src='assets/{document_id}/{image.name}' alt='{document_id} input'></section>"
                f"<section><h4>Ground truth</h4>{pre(ground_truth)}</section><section><h4>Raw OCR Markdown</h4>{pre(raw_ocr)}</section>"
                f"<section><h4>Strict normalized OCR</h4>{pre(normalize_content_strict(raw_ocr))}</section></div>"
            )
        sections.append(
            f"<article id='document-{document_id}'><h2>{document_id}</h2><p>Category: {entry['category']} | DPI: 200 | Pages: {entry['page_count']}</p>{''.join(page_blocks)}</article>"
        )
    document = """<!doctype html><html><head><meta charset='utf-8'><title>Phase 6 Manual Layout Review</title>
<style>body{font:14px system-ui,sans-serif;margin:24px;background:#f5f5f5;color:#111}article{background:#fff;margin:24px 0;padding:20px;border:1px solid #bbb}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}section{min-width:0}img{max-width:100%;border:1px solid #777}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f0f0;padding:10px;border:1px solid #ddd}h3{border-top:1px solid #bbb;padding-top:16px}</style></head><body>
<h1>Phase 6 manual layout review</h1><p>Local artifacts only. Raw OCR is not corrected.</p>""" + "".join(sections) + "</body></html>"
    (review_root / "index.html").write_text(document, encoding="utf-8")
    print(review_root / "index.html")


if __name__ == "__main__":
    main()
