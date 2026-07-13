from __future__ import annotations

from sqlalchemy import Engine, text


JOB_COLUMNS = {
    "total_pages": "INTEGER NOT NULL DEFAULT 1",
    "processed_pages": "INTEGER NOT NULL DEFAULT 0",
    "successful_pages": "INTEGER NOT NULL DEFAULT 0",
    "failed_pages": "INTEGER NOT NULL DEFAULT 0",
    "progress_percent": "INTEGER NOT NULL DEFAULT 0",
    "pdf_dpi": "INTEGER",
    "current_page_number": "INTEGER",
}


def migrate(engine: Engine) -> None:
    """Apply small idempotent SQLite schema migrations without replacing user data."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
        existing = {row[1] for row in connection.execute(text("PRAGMA table_info(ocr_jobs)"))}
        for name, definition in JOB_COLUMNS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE ocr_jobs ADD COLUMN {name} {definition}"))
        connection.execute(text("""
            UPDATE ocr_jobs SET total_pages=1, processed_pages=1, successful_pages=1,
            failed_pages=0, progress_percent=100, current_page_number=1
            WHERE file_type IN ('png','jpg','jpeg','webp') AND status='COMPLETED'
        """))
        connection.execute(text("INSERT OR IGNORE INTO schema_migrations(version) VALUES (3)"))

