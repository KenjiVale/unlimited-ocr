from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.migrations import migrate
import app.models  # noqa: F401 - registers all metadata


class Database:
    def __init__(self, url: str, busy_timeout_ms: int = 5000, journal_mode: str = "WAL") -> None:
        self.busy_timeout_ms, self.journal_mode = busy_timeout_ms, journal_mode
        connect_args = {"check_same_thread": False, "timeout": busy_timeout_ms / 1000} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def _configure_sqlite(self, dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute(f"PRAGMA journal_mode={self.journal_mode}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        cursor.close()

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        migrate(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def sessions(self) -> Iterator[Session]:
        with self.session() as session:
            yield session

    def close(self) -> None:
        self.engine.dispose()
