import pytest
from app.core.errors import AppError
from app.services.storage import StorageService
from app.services.validation import validate_image_upload
from conftest import image_bytes


@pytest.mark.parametrize(("name", "mime", "fmt"), [("a.png", "image/png", "PNG"), ("a.jpg", "image/jpeg", "JPEG"), ("a.webp", "image/webp", "WEBP")])
def test_valid_images(name: str, mime: str, fmt: str) -> None:
    assert validate_image_upload(name, mime, image_bytes(fmt), 1) == "." + name.split(".")[-1]


@pytest.mark.parametrize(("name", "mime", "content", "code"), [
    ("a.pdf", "application/pdf", b"x", "UNSUPPORTED_FILE_TYPE"),
    ("a.png", "image/jpeg", image_bytes(), "UNSUPPORTED_FILE_TYPE"),
    ("a.png", "image/png", b"broken", "INVALID_IMAGE"),
    ("a.png", "image/png", b"", "INVALID_IMAGE"),
    ("a.png", "image/png", b"x" * (1024 * 1024 + 1), "UPLOAD_TOO_LARGE"),
], ids=["extension", "mime", "corrupt", "empty", "oversized"])
def test_invalid_uploads(name: str, mime: str, content: bytes, code: str) -> None:
    with pytest.raises(AppError) as caught: validate_image_upload(name, mime, content, 1)
    assert caught.value.code == code


def test_filename_path_traversal_is_neutralized() -> None:
    assert StorageService.sanitize_filename("../../secret.png") == "secret.png"
    assert StorageService.sanitize_filename("..\\..\\secret.png") == "secret.png"
