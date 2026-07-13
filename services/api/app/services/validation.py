from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.errors import AppError

ALLOWED_IMAGES = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
}


def validate_image_upload(filename: str, content_type: str | None, content: bytes, max_mb: int) -> str:
    extension = Path(filename.replace("\\", "/")).suffix.lower()
    if extension not in ALLOWED_IMAGES or content_type not in ALLOWED_IMAGES.get(extension, set()):
        raise AppError("UNSUPPORTED_FILE_TYPE", "Only PNG, JPG, JPEG, and WEBP images are supported.", 415)
    if not content:
        raise AppError("INVALID_IMAGE", "The uploaded image is empty.", 400)
    if len(content) > max_mb * 1024 * 1024:
        raise AppError("UPLOAD_TOO_LARGE", f"The uploaded file exceeds {max_mb} MB.", 413)
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            detected = image.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise AppError("INVALID_IMAGE", "The uploaded file is not a valid image.", 400) from None
    expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[extension]
    if detected != expected:
        raise AppError("INVALID_IMAGE", "Image content does not match its extension.", 400)
    return extension

