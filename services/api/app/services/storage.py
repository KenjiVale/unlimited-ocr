from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.core.errors import AppError


class StorageService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        self.uploads_dir = self.data_dir / "uploads"
        self.outputs_dir = self.data_dir / "outputs"
        self.pages_dir = self.data_dir / "pages"

    def initialize(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        name = Path(filename.replace("\\", "/")).name
        name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
        return name[:255] or "upload"

    def create_job_paths(self, job_id: str, extension: str) -> tuple[Path, Path]:
        if not re.fullmatch(r"[0-9a-f-]{36}", job_id):
            raise AppError("INTERNAL_ERROR", "Invalid generated job identifier.", 500)
        upload_dir, output_dir = self.uploads_dir / job_id, self.outputs_dir / job_id
        if upload_dir.exists() or output_dir.exists():
            raise AppError("INTERNAL_ERROR", "Job storage already exists.", 500)
        upload_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)
        return upload_dir / f"source{extension.lower()}", output_dir

    def page_image_path(self, job_id: str, page_number: int) -> Path:
        directory = self.pages_dir / job_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"page_{page_number:04d}.png"

    def write_page_results(self, output_dir: Path, page_number: int, markdown: str, plain_text: str) -> tuple[Path, Path]:
        directory = output_dir / "pages"
        directory.mkdir(parents=True, exist_ok=True)
        markdown_path = directory / f"page_{page_number:04d}.md"
        text_path = directory / f"page_{page_number:04d}.txt"
        self._atomic_text(markdown_path, markdown)
        self._atomic_text(text_path, plain_text)
        return markdown_path, text_path

    @staticmethod
    def save_bytes(path: Path, content: bytes) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)

    def write_results(self, output_dir: Path, markdown: str, plain_text: str, payload: dict[str, Any]) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path, text_path, json_path = output_dir / "result.md", output_dir / "result.txt", output_dir / "result.json"
        self._atomic_text(markdown_path, markdown)
        self._atomic_text(text_path, plain_text)
        self._atomic_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return markdown_path, text_path, json_path

    @staticmethod
    def read_text(path: Path) -> str:
        if not path.is_file():
            raise AppError("RESULT_NOT_AVAILABLE", "The OCR result is not available.", 409)
        return path.read_text(encoding="utf-8")

    @staticmethod
    def read_json(path: Path) -> dict[str, Any]:
        return json.loads(StorageService.read_text(path))

    def delete_job(self, job_id: str) -> None:
        for root in (self.uploads_dir, self.pages_dir, self.outputs_dir):
            target = (root / job_id).resolve()
            if target.parent != root.resolve():
                raise AppError("INTERNAL_ERROR", "Unsafe storage path.", 500)
            if target.exists():
                shutil.rmtree(target)
