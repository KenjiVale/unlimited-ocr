from pathlib import Path

import pytest

from app.core.errors import AppError
from app.services.pdf import PDFService, validate_pdf_type
from conftest import pdf_bytes, upload_pdf


def test_valid_one_and_multi_page_pdf(app_client) -> None:
    _, _, tmp_path = app_client
    service = PDFService()
    for count in (1, 3):
        path = tmp_path / f"{count}.pdf"; path.write_bytes(pdf_bytes(count))
        assert service.inspect_pdf(path, 10).page_count == count


@pytest.mark.parametrize(("name", "mime", "content", "code"), [
    ("a.txt", "application/pdf", b"%PDF-x", "UNSUPPORTED_FILE_TYPE"),
    ("a.pdf", "text/plain", b"%PDF-x", "UNSUPPORTED_FILE_TYPE"),
    ("a.pdf", "application/pdf", b"", "PDF_EMPTY"),
    ("a.pdf", "application/pdf", b"broken", "INVALID_PDF"),
])
def test_pdf_type_rejections(name: str, mime: str, content: bytes, code: str) -> None:
    with pytest.raises(AppError) as caught: validate_pdf_type(name, mime, content, 1)
    assert caught.value.code == code


def test_corrupt_and_encrypted_pdf_rejected(app_client) -> None:
    _, _, tmp_path = app_client
    service = PDFService()
    corrupt = tmp_path / "bad.pdf"; corrupt.write_bytes(b"%PDF-broken")
    with pytest.raises(AppError) as caught: service.inspect_pdf(corrupt, 10)
    assert caught.value.code == "INVALID_PDF"
    encrypted = tmp_path / "secret.pdf"; encrypted.write_bytes(pdf_bytes(1, encrypted=True))
    with pytest.raises(AppError) as caught: service.inspect_pdf(encrypted, 10)
    assert caught.value.code == "PDF_PASSWORD_REQUIRED"


def test_page_limit_and_dpi_rejected(app_client) -> None:
    client, _, tmp_path = app_client
    path = tmp_path / "many.pdf"; path.write_bytes(pdf_bytes(3))
    with pytest.raises(AppError) as caught: PDFService().inspect_pdf(path, 2)
    assert caught.value.code == "PDF_PAGE_LIMIT_EXCEEDED"
    response = upload_pdf(client, dpi=72)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_PDF_DPI"


def test_pdf_oversized_and_path_name(app_client) -> None:
    client, model, _ = app_client
    response = upload_pdf(client, content=b"%PDF-" + b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413
    response = upload_pdf(client, pages=1, filename="../../safe.pdf")
    assert response.status_code == 202 and response.json()["original_filename"] == "safe.pdf"
