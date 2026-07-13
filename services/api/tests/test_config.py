import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_configuration() -> None:
    settings = Settings(_env_file=None)
    assert settings.api_host == "127.0.0.1"
    assert settings.ocr_concurrency == 1
    assert settings.pdf_default_dpi == 200


def test_rejects_unsupported_dtype() -> None:
    with pytest.raises(ValidationError):
        Settings(ocr_dtype="float64", _env_file=None)


def test_rejects_invalid_dpi() -> None:
    with pytest.raises(ValidationError):
        Settings(pdf_default_dpi=72, _env_file=None)


def test_rejects_invalid_concurrency() -> None:
    with pytest.raises(ValidationError):
        Settings(ocr_concurrency=2, _env_file=None)


def test_offline_mode_requires_model_directory() -> None:
    with pytest.raises(ValidationError, match="Offline mode requires OCR_MODEL_PATH"):
        Settings(hf_hub_offline=True, ocr_model_path="./definitely-missing-model", _env_file=None)


def test_offline_mode_accepts_existing_model_directory() -> None:
    settings = Settings(hf_hub_offline=True, ocr_model_path="../../data/models", _env_file=None)
    assert settings.hf_hub_offline
