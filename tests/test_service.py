from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from cryptovault.application.service import FileOperationService
from cryptovault.domain.errors import (
    AuthenticationError,
    BusyError,
    CancelledError,
    HistoryError,
    PathSecurityError,
)
from cryptovault.domain.models import (
    OperationKind,
    OperationOutcome,
    VerificationStatus,
)
from cryptovault.security.passwords import Secret

pytestmark = [pytest.mark.integration, pytest.mark.security]

PASSWORD = "frase-senha-de-teste-segura-2026"


def test_encrypt_decrypt_roundtrip_and_history(
    service: FileOperationService,
    history,
    sample_file: Path,
    output_dir: Path,
) -> None:
    encrypted = service.encrypt_file(sample_file, PASSWORD, output_dir)
    assert encrypted.output_path == output_dir / "documento.txt.cvlt"
    assert encrypted.output_path.exists()
    assert encrypted.source_size == sample_file.stat().st_size
    assert encrypted.output_size == encrypted.output_path.stat().st_size
    assert encrypted.duration_ms >= 0

    info = service.inspect_file(encrypted.output_path)
    assert info.plaintext_size == sample_file.stat().st_size
    assert info.version == 1
    assert len(info.fingerprint) == 16

    decrypted = service.decrypt_file(encrypted.output_path, PASSWORD, output_dir)
    assert decrypted.output_path.name == "documento.txt"
    assert decrypted.output_path.read_bytes() == sample_file.read_bytes()

    records = service.list_history()
    assert [record.kind for record in records] == [
        OperationKind.DECRYPT,
        OperationKind.ENCRYPT,
    ]
    assert all(record.outcome is OperationOutcome.SUCCESS for record in records)
    assert records[0].size_bytes == sample_file.stat().st_size
    assert history.db_path.exists()


def test_password_is_never_written_to_history_database(
    service: FileOperationService,
    history,
    sample_file: Path,
    output_dir: Path,
) -> None:
    encrypted = service.encrypt_file(sample_file, PASSWORD, output_dir)
    service.decrypt_file(encrypted.output_path, PASSWORD, output_dir)
    service.verify_file(encrypted.output_path, PASSWORD)

    connection = sqlite3.connect(history.db_path)
    try:
        rows = connection.execute("SELECT * FROM operations").fetchall()
    finally:
        connection.close()
    assert rows
    serialized = "\n".join(str(value) for row in rows for value in row)
    assert PASSWORD not in serialized

    for path in history.data_dir.glob("history.db*"):
        raw = path.read_bytes().decode("utf-8", errors="ignore")
        assert PASSWORD not in raw


def test_wrong_password_records_failure_without_output(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    encrypted = service.encrypt_file(sample_file, PASSWORD, output_dir)
    with pytest.raises(AuthenticationError):
        service.decrypt_file(encrypted.output_path, "senha-incorreta-total", output_dir)
    assert not (output_dir / "documento.txt").exists()
    assert not list(output_dir.glob(".cryptovault-*"))

    latest = service.list_history(limit=1)[0]
    assert latest.kind is OperationKind.DECRYPT
    assert latest.outcome is OperationOutcome.FAILURE
    assert "senha-incorreta-total" not in latest.message.casefold()


def test_tampered_file_verification_is_recorded(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    encrypted = service.encrypt_file(sample_file, PASSWORD, output_dir)
    data = bytearray(encrypted.output_path.read_bytes())
    data[-1] ^= 0x01
    tampered = output_dir / "adulterado.cvlt"
    tampered.write_bytes(bytes(data))

    result = service.verify_file(tampered, PASSWORD)
    assert result.status is VerificationStatus.INVALID_AUTHENTICATION
    assert result.is_authenticated is False

    latest = service.list_history(limit=1)[0]
    assert latest.kind is OperationKind.VERIFY
    assert latest.outcome is OperationOutcome.FAILURE


def test_authenticated_verify_is_recorded(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    encrypted = service.encrypt_file(sample_file, PASSWORD, output_dir)
    result = service.verify_file(encrypted.output_path, PASSWORD)
    assert result.status is VerificationStatus.AUTHENTICATED
    latest = service.list_history(limit=1)[0]
    assert latest.outcome is OperationOutcome.SUCCESS
    assert latest.size_bytes == 0


def test_repeated_encryption_never_overwrites(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    first = service.encrypt_file(sample_file, PASSWORD, output_dir)
    original = first.output_path.read_bytes()
    second = service.encrypt_file(sample_file, PASSWORD, output_dir)
    assert second.output_path.name == "documento.txt (1).cvlt"
    assert first.output_path.read_bytes() == original
    assert second.output_path.read_bytes() != original


def test_cancel_before_start_records_cancelled(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(CancelledError):
        service.encrypt_file(sample_file, PASSWORD, output_dir, cancel=cancel)
    assert not list(output_dir.iterdir())
    latest = service.list_history(limit=1)[0]
    assert latest.outcome is OperationOutcome.CANCELLED


def test_cancel_during_encryption_records_cancelled(
    service: FileOperationService,
    tmp_path: Path,
    output_dir: Path,
) -> None:
    source = tmp_path / "grande.bin"
    source.write_bytes(b"x" * (2 * 1024 * 1024 + 17))
    cancel = threading.Event()

    def progress(done: int, _total: int) -> None:
        if done >= 1024 * 1024:
            cancel.set()

    with pytest.raises(CancelledError):
        service.encrypt_file(source, PASSWORD, output_dir, progress=progress, cancel=cancel)
    assert not list(output_dir.iterdir())
    assert not list(output_dir.glob(".cryptovault-*"))
    latest = service.list_history(limit=1)[0]
    assert latest.outcome is OperationOutcome.CANCELLED


def test_history_failures_do_not_break_operations(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_record: object) -> int:
        raise HistoryError("falha simulada")

    monkeypatch.setattr(service.history, "record", broken)
    result = service.encrypt_file(sample_file, PASSWORD, output_dir)
    assert result.output_path.exists()


def test_operation_gate_rejects_simultaneous_scopes(
    service: FileOperationService,
) -> None:
    with service.operation_scope("primeira"):
        assert service.busy is True
        with pytest.raises(BusyError):
            with service.operation_scope("segunda"):
                pass
    assert service.busy is False


def test_secret_instance_is_not_owned_or_wiped_by_service(
    service: FileOperationService,
    sample_file: Path,
    output_dir: Path,
) -> None:
    secret = Secret(PASSWORD)
    service.encrypt_file(sample_file, secret, output_dir)
    assert secret.is_cleared is False
    secret.wipe()
    assert secret.is_cleared is True


def test_invalid_source_and_output_are_rejected(
    service: FileOperationService,
    sample_file: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(PathSecurityError):
        service.inspect_file(tmp_path / "missing.cvlt")
    with pytest.raises(PathSecurityError):
        service.encrypt_file(sample_file, PASSWORD, tmp_path / "diretorio-inexistente")
