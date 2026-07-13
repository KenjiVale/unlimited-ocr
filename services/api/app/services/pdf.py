from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.errors import AppError


@dataclass(frozen=True)
class PDFMetadata:
    page_count: int


@dataclass(frozen=True)
class RenderedPage:
    path: Path
    duration_ms: int


class PDFService:
    def inspect_pdf(self, path: Path, maximum_pages: int) -> PDFMetadata:
        try:
            with fitz.open(path) as document:
                if document.needs_pass or document.is_encrypted:
                    raise AppError("PDF_PASSWORD_REQUIRED", "Password-protected PDFs are not supported.", 400)
                page_count = document.page_count
                if page_count < 1:
                    raise AppError("PDF_EMPTY", "The PDF contains no pages.", 400)
                if page_count > maximum_pages:
                    raise AppError("PDF_PAGE_LIMIT_EXCEEDED", "The PDF contains more pages than allowed.", 400, {"page_count": page_count, "maximum": maximum_pages})
                document.load_page(0)
                return PDFMetadata(page_count)
        except AppError:
            raise
        except (fitz.FileDataError, RuntimeError, ValueError, OSError) as exc:
            raise AppError("INVALID_PDF", "The uploaded file is not a valid PDF.", 400) from exc

    def render_page(self, source: Path, page_number: int, dpi: int, target: Path) -> RenderedPage:
        started = time.perf_counter()
        try:
            with fitz.open(source) as document:
                if document.needs_pass:
                    raise AppError("PDF_PASSWORD_REQUIRED", "The PDF requires a password.", 400)
                page = document.load_page(page_number - 1)
                pixmap = page.get_pixmap(dpi=dpi, alpha=False)
                temporary = target.with_name(f".{target.name}.tmp.png")
                pixmap.save(temporary)
                temporary.replace(target)
                del pixmap
            return RenderedPage(target, round((time.perf_counter() - started) * 1000))
        except AppError:
            raise
        except Exception as exc:
            raise AppError("PAGE_RENDER_FAILED", "The PDF page could not be rendered.", 500) from exc


def validate_pdf_type(filename: str, content_type: str | None, content: bytes, max_mb: int) -> None:
    if Path(filename.replace("\\", "/")).suffix.lower() != ".pdf" or content_type != "application/pdf":
        raise AppError("UNSUPPORTED_FILE_TYPE", "The file extension and MIME type must identify a PDF.", 415)
    if not content:
        raise AppError("PDF_EMPTY", "The uploaded PDF is empty.", 400)
    if len(content) > max_mb * 1024 * 1024:
        raise AppError("UPLOAD_TOO_LARGE", f"The uploaded file exceeds {max_mb} MB.", 413)
    if not content.startswith(b"%PDF-"):
        raise AppError("INVALID_PDF", "The uploaded file is not a valid PDF.", 400)

