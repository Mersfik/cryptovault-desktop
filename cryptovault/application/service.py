"""Casos de uso: validação, orquestração, histórico e auditoria."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import ByteString, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from cryptovault.crypto.engine import CryptoEngine
from cryptovault.domain.errors import (
    CancelledError,
    CryptoVaultError,
    HistoryError,
    safe_error_message,
)
from cryptovault.domain.models import (
    DecryptResult,
    EncryptResult,
    HeaderInfo,
    OperationKind,
    OperationOutcome,
    OperationRecord,
    VerificationStatus,
    VerifyResult,
)
from cryptovault.infrastructure.history import HistoryRepository
from cryptovault.security.gate import OperationGate
from cryptovault.security.passwords import Secret
from cryptovault.security.paths import (
    decrypted_output_name,
    encrypted_output_name,
    unique_destination,
    validate_input_file,
    validate_output_directory,
)
from cryptovault.security.redaction import safe_filename

logger = logging.getLogger("cryptovault.application")


class FileOperationService:
    def __init__(
        self,
        engine: CryptoEngine,
        history: HistoryRepository,
        *,
        gate: OperationGate | None = None,
    ) -> None:
        self.engine = engine
        self.history = history
        self.gate = gate or OperationGate()

    @property
    def busy(self) -> bool:
        return self.gate.owner is not None

    @contextmanager
    def operation_scope(self, owner: str) -> Iterator[None]:
        self.gate.enter(owner)
        try:
            yield
        finally:
            self.gate.leave(owner)

    def encrypt_file(
        self,
        source: str | Path,
        password: Secret | str | ByteString,
        output_dir: str | Path,
        *,
        progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> EncryptResult:
        source_path = Path(source)
        filename = safe_filename(source_path.name)
        secret, owned = self._as_secret(password)
        started = time.monotonic()
        try:
            validated = validate_input_file(source_path)
            destination_dir = validate_output_directory(output_dir)
            destination = unique_destination(
                destination_dir,
                encrypted_output_name(validated.name),
            )
            logger.info(
                "encrypt_started",
                extra={"event": "encrypt_started", "operation": "encrypt", "file_name": filename},
            )
            result = self.engine.encrypt_file(
                validated,
                destination,
                secret.bytes_copy(),
                progress=progress,
                cancel=cancel,
            )
        except CancelledError as exc:
            self._record_failure(OperationKind.ENCRYPT, filename, exc)
            raise
        except CryptoVaultError as exc:
            self._record_failure(OperationKind.ENCRYPT, filename, exc)
            logger.warning(
                "encrypt_failed",
                extra={
                    "event": "encrypt_failed",
                    "operation": "encrypt",
                    "file_name": filename,
                    "result": "failure",
                    "code": exc.code,
                },
            )
            raise
        except Exception as exc:
            self._record_failure(
                OperationKind.ENCRYPT,
                filename,
                CryptoVaultError("Erro inesperado na criptografia."),
            )
            logger.exception(
                "encrypt_error",
                extra={
                    "event": "encrypt_error",
                    "operation": "encrypt",
                    "file_name": filename,
                    "result": "failure",
                },
            )
            raise CryptoVaultError("Erro inesperado na criptografia.") from exc
        else:
            duration = int((time.monotonic() - started) * 1000)
            self._record_success(
                OperationKind.ENCRYPT,
                filename,
                result.source_size,
                duration,
            )
            logger.info(
                "encrypt_completed",
                extra={
                    "event": "encrypt_completed",
                    "operation": "encrypt",
                    "file_name": filename,
                    "result": "success",
                    "duration_ms": duration,
                    "size_bytes": result.source_size,
                },
            )
            return result
        finally:
            if owned:
                secret.wipe()

    def decrypt_file(
        self,
        source: str | Path,
        password: Secret | str | ByteString,
        output_dir: str | Path,
        *,
        progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> DecryptResult:
        source_path = Path(source)
        filename = safe_filename(source_path.name)
        secret, owned = self._as_secret(password)
        started = time.monotonic()
        try:
            validated = validate_input_file(source_path)
            destination_dir = validate_output_directory(output_dir)
            destination = unique_destination(
                destination_dir,
                decrypted_output_name(validated.name),
            )
            logger.info(
                "decrypt_started",
                extra={"event": "decrypt_started", "operation": "decrypt", "file_name": filename},
            )
            result = self.engine.decrypt_file(
                validated,
                destination,
                secret.bytes_copy(),
                progress=progress,
                cancel=cancel,
            )
        except CancelledError as exc:
            self._record_failure(OperationKind.DECRYPT, filename, exc)
            raise
        except CryptoVaultError as exc:
            self._record_failure(OperationKind.DECRYPT, filename, exc)
            logger.warning(
                "decrypt_failed",
                extra={
                    "event": "decrypt_failed",
                    "operation": "decrypt",
                    "file_name": filename,
                    "result": "failure",
                    "code": exc.code,
                },
            )
            raise
        except Exception as exc:
            self._record_failure(
                OperationKind.DECRYPT,
                filename,
                CryptoVaultError("Erro inesperado na descriptografia."),
            )
            logger.exception(
                "decrypt_error",
                extra={
                    "event": "decrypt_error",
                    "operation": "decrypt",
                    "file_name": filename,
                    "result": "failure",
                },
            )
            raise CryptoVaultError("Erro inesperado na descriptografia.") from exc
        else:
            duration = int((time.monotonic() - started) * 1000)
            self._record_success(
                OperationKind.DECRYPT,
                filename,
                result.output_size,
                duration,
            )
            logger.info(
                "decrypt_completed",
                extra={
                    "event": "decrypt_completed",
                    "operation": "decrypt",
                    "file_name": filename,
                    "result": "success",
                    "duration_ms": duration,
                    "size_bytes": result.output_size,
                },
            )
            return result
        finally:
            if owned:
                secret.wipe()

    def verify_file(
        self,
        source: str | Path,
        password: Secret | str | ByteString,
        *,
        progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> VerifyResult:
        source_path = Path(source)
        filename = safe_filename(source_path.name)
        secret, owned = self._as_secret(password)
        started = time.monotonic()
        try:
            validated = validate_input_file(source_path)
            result = self.engine.verify_file(
                validated,
                secret.bytes_copy(),
                progress=progress,
                cancel=cancel,
            )
        except CancelledError as exc:
            self._record_failure(OperationKind.VERIFY, filename, exc)
            raise
        except CryptoVaultError as exc:
            self._record_failure(OperationKind.VERIFY, filename, exc)
            logger.warning(
                "verify_failed",
                extra={
                    "event": "verify_failed",
                    "operation": "verify",
                    "file_name": filename,
                    "result": "failure",
                    "code": exc.code,
                },
            )
            raise
        except Exception as exc:
            self._record_failure(
                OperationKind.VERIFY,
                filename,
                CryptoVaultError("Erro inesperado na verificação."),
            )
            logger.exception(
                "verify_error",
                extra={
                    "event": "verify_error",
                    "operation": "verify",
                    "file_name": filename,
                    "result": "failure",
                },
            )
            raise CryptoVaultError("Erro inesperado na verificação.") from exc
        else:
            duration = int((time.monotonic() - started) * 1000)
            outcome = (
                OperationOutcome.SUCCESS
                if result.status is VerificationStatus.AUTHENTICATED
                else OperationOutcome.FAILURE
            )
            message = (
                "Conteúdo autenticado."
                if outcome is OperationOutcome.SUCCESS
                else result.status.label_pt
            )
            self._record(
                OperationRecord(
                    kind=OperationKind.VERIFY,
                    filename=filename,
                    outcome=outcome,
                    message=message,
                    size_bytes=0,
                    duration_ms=duration,
                )
            )
            logger.info(
                "verify_completed",
                extra={
                    "event": "verify_completed",
                    "operation": "verify",
                    "file_name": filename,
                    "result": outcome.value,
                    "duration_ms": duration,
                },
            )
            return result
        finally:
            if owned:
                secret.wipe()

    def inspect_file(self, source: str | Path) -> HeaderInfo:
        return self.engine.inspect_file(source)

    def list_history(
        self,
        *,
        limit: int = 200,
        kind: OperationKind | None = None,
        outcome: OperationOutcome | None = None,
    ) -> list[OperationRecord]:
        return self.history.list_records(limit=limit, kind=kind, outcome=outcome)

    def clear_history(self) -> int:
        return self.history.clear()

    def apply_retention(self, days: int) -> int:
        return self.history.purge_older_than(days)

    def record_cancelled(self, kind: OperationKind, source: str | Path) -> None:
        self._record(
            OperationRecord(
                kind=kind,
                filename=safe_filename(Path(source).name),
                outcome=OperationOutcome.CANCELLED,
                message="Operação cancelada.",
            )
        )

    def _record_success(
        self,
        kind: OperationKind,
        filename: str,
        size_bytes: int,
        duration_ms: int,
    ) -> None:
        self._record(
            OperationRecord(
                kind=kind,
                filename=filename,
                outcome=OperationOutcome.SUCCESS,
                message="Concluído com sucesso.",
                size_bytes=size_bytes,
                duration_ms=duration_ms,
            )
        )

    def _record_failure(
        self,
        kind: OperationKind,
        filename: str,
        exc: CryptoVaultError,
    ) -> None:
        outcome = (
            OperationOutcome.CANCELLED
            if isinstance(exc, CancelledError)
            else OperationOutcome.FAILURE
        )
        self._record(
            OperationRecord(
                kind=kind,
                filename=filename,
                outcome=outcome,
                message=safe_error_message(exc),
            )
        )

    def _record(self, record: OperationRecord) -> None:
        try:
            self.history.record(record)
        except HistoryError:
            logger.exception(
                "history_write_failed",
                extra={"event": "history_write_failed", "component": "infrastructure"},
            )

    @staticmethod
    def _as_secret(password: Secret | str | ByteString) -> tuple[Secret, bool]:
        if isinstance(password, Secret):
            return password, False
        return Secret(password), True
