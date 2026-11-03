from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cryptovault.domain.errors import HistoryError
from cryptovault.domain.models import (
    OperationKind,
    OperationOutcome,
    OperationRecord,
)
from cryptovault.infrastructure.history import HistoryRepository

pytestmark = pytest.mark.integration


def _record(
    kind: OperationKind = OperationKind.ENCRYPT,
    outcome: OperationOutcome = OperationOutcome.SUCCESS,
    *,
    filename: str = "documento.txt",
    message: str = "Concluído.",
    timestamp: datetime | None = None,
) -> OperationRecord:
    return OperationRecord(
        kind=kind,
        filename=filename,
        outcome=outcome,
        message=message,
        size_bytes=123,
        duration_ms=45,
        timestamp=timestamp or datetime.now(UTC),
    )


def test_record_list_order_and_filters(history: HistoryRepository) -> None:
    first = history.record(_record())
    second = history.record(
        _record(OperationKind.DECRYPT, filename="foto.jpg", message="Recuperado.")
    )
    third = history.record(
        _record(
            OperationKind.VERIFY,
            OperationOutcome.FAILURE,
            filename="relatorio.pdf",
            message="Autenticação inválida.",
        )
    )
    assert (first, second, third) == (1, 2, 3)

    records = history.list_records()
    assert [record.id for record in records] == [3, 2, 1]
    assert records[0].kind is OperationKind.VERIFY
    assert records[0].outcome is OperationOutcome.FAILURE
    assert records[1].filename == "foto.jpg"
    assert records[1].size_bytes == 123
    assert records[1].duration_ms == 45

    only_decrypt = history.list_records(kind=OperationKind.DECRYPT)
    assert [record.kind for record in only_decrypt] == [OperationKind.DECRYPT]
    only_failures = history.list_records(outcome=OperationOutcome.FAILURE)
    assert [record.filename for record in only_failures] == ["relatorio.pdf"]
    combined = history.list_records(
        kind=OperationKind.DECRYPT,
        outcome=OperationOutcome.SUCCESS,
    )
    assert len(combined) == 1
    assert len(history.list_records(limit=2)) == 2
    assert history.list_records(limit=0)[0].id == 3
    assert len(history.list_records(limit=10_000)) == 3


def test_clear_and_retention(history: HistoryRepository) -> None:
    old = datetime.now(UTC) - timedelta(days=120)
    history.record(_record(timestamp=old))
    history.record(_record(OperationKind.DECRYPT))
    assert history.purge_older_than(30) == 1
    remaining = history.list_records()
    assert len(remaining) == 1
    assert remaining[0].kind is OperationKind.DECRYPT

    assert history.clear() == 1
    assert history.list_records() == []


def test_history_sanitizes_control_characters_and_secret_labels(
    history: HistoryRepository,
) -> None:
    history.record(
        _record(
            filename="arquivo\x00malicioso.txt",
            message="senha=super-secreta token=abc123",
        )
    )
    record = history.list_records()[0]
    assert "\x00" not in record.filename
    assert "super-secreta" not in record.message
    assert "abc123" not in record.message
    assert "<redacted>" in record.message


def test_history_database_is_local_and_private(data_dir: Path) -> None:
    repository = HistoryRepository(data_dir)
    assert repository.db_path == data_dir / "history.db"
    assert repository.db_path.exists()
    repository.record(_record())
    assert repository.list_records()[0].filename == "documento.txt"


def test_invalid_database_reports_history_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = HistoryRepository(tmp_path)
    import sqlite3

    def broken_connect() -> sqlite3.Connection:
        raise sqlite3.OperationalError("falha simulada")

    monkeypatch.setattr(repository, "_connect", broken_connect)
    with pytest.raises(HistoryError):
        repository.record(_record())
    with pytest.raises(HistoryError):
        repository.list_records()
    with pytest.raises(HistoryError):
        repository.clear()
    with pytest.raises(HistoryError):
        repository.purge_older_than(30)
