"""Histórico local em SQLite, com consultas parametrizadas e sem segredos."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptovault.domain.errors import HistoryError
from cryptovault.domain.models import OperationKind, OperationOutcome, OperationRecord
from cryptovault.security.paths import ensure_private_directory
from cryptovault.security.redaction import sanitize_log_value

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('encrypt', 'decrypt', 'verify')),
    filename TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('success', 'failure', 'cancelled')),
    message TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0)
);
CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_operations_kind ON operations(operation);
CREATE INDEX IF NOT EXISTS idx_operations_result ON operations(result);
PRAGMA user_version = 1;
"""

_SELECT_COLUMNS = (
    "SELECT id, timestamp, operation, filename, result, message, size_bytes, duration_ms "
    "FROM operations"
)


class HistoryRepository:
    """Repositório de histórico local; não é um registro de auditoria inviolável."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = ensure_private_directory(data_dir)
        self.db_path = self.data_dir / "history.db"
        try:
            self._initialize()
        except sqlite3.Error as exc:
            raise HistoryError("Falha ao inicializar o banco de histórico.") from exc
        self._restrict_permissions()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.executescript(_SCHEMA)

    def _restrict_permissions(self) -> None:
        import os
        from contextlib import suppress

        for suffix in ("", "-wal", "-shm"):
            with suppress(OSError):
                os.chmod(Path(f"{self.db_path}{suffix}"), 0o600)

    def record(self, record: OperationRecord) -> int:
        filename = sanitize_log_value(record.filename, max_length=200)
        message = sanitize_log_value(record.message, max_length=300)
        try:
            with self._session() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO operations
                        (timestamp, operation, filename, result, message, size_bytes, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.timestamp.astimezone(UTC).isoformat(),
                        record.kind.value,
                        filename,
                        record.outcome.value,
                        message,
                        max(0, int(record.size_bytes)),
                        max(0, int(record.duration_ms)),
                    ),
                )
                return int(cursor.lastrowid or 0)
        except sqlite3.Error as exc:
            raise HistoryError("Falha ao gravar no histórico.") from exc

    def list_records(
        self,
        *,
        limit: int = 200,
        kind: OperationKind | None = None,
        outcome: OperationOutcome | None = None,
    ) -> list[OperationRecord]:
        limit = max(1, min(int(limit), 1000))
        clauses: list[str] = []
        parameters: list[object] = []
        if kind is not None:
            clauses.append("operation = ?")
            parameters.append(kind.value)
        if outcome is not None:
            clauses.append("result = ?")
            parameters.append(outcome.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        # ``where`` só recebe cláusulas constantes; valores são sempre parametrizados.
        query = f"{_SELECT_COLUMNS} {where} ORDER BY id DESC LIMIT ?"
        parameters.append(limit)
        try:
            with self._session() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as exc:
            raise HistoryError("Falha ao consultar o histórico.") from exc
        return [self._row_to_record(row) for row in rows]

    def clear(self) -> int:
        try:
            with self._session() as connection:
                cursor = connection.execute("DELETE FROM operations")
                return int(cursor.rowcount)
        except sqlite3.Error as exc:
            raise HistoryError("Falha ao limpar o histórico.") from exc

    def purge_older_than(self, days: int) -> int:
        days = max(1, min(int(days), 3650))
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        try:
            with self._session() as connection:
                cursor = connection.execute(
                    "DELETE FROM operations WHERE timestamp < ?",
                    (cutoff,),
                )
                return int(cursor.rowcount)
        except sqlite3.Error as exc:
            raise HistoryError("Falha ao aplicar retenção do histórico.") from exc

    @staticmethod
    def _row_to_record(row: tuple[object, ...]) -> OperationRecord:
        record_id, timestamp, operation, filename, result, message, size, duration = row
        return OperationRecord(
            id=int(record_id),  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat(str(timestamp)).astimezone(UTC),
            kind=OperationKind(str(operation)),
            filename=str(filename),
            outcome=OperationOutcome(str(result)),
            message=str(message),
            size_bytes=int(size),  # type: ignore[arg-type]
            duration_ms=int(duration),  # type: ignore[arg-type]
        )
