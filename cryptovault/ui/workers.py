"""Workers QRunnable: operações criptográficas fora da thread principal."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from cryptovault.application.service import FileOperationService
from cryptovault.domain.errors import (
    BusyError,
    CancelledError,
    CryptoVaultError,
    safe_error_message,
)
from cryptovault.domain.models import (
    BatchItemResult,
    BatchResult,
    OperationKind,
    VerificationStatus,
)
from cryptovault.security.passwords import Secret
from cryptovault.security.redaction import safe_filename

logger = logging.getLogger("cryptovault.worker")

_VERBS = {
    OperationKind.ENCRYPT: "Criptografando",
    OperationKind.DECRYPT: "Descriptografando",
    OperationKind.VERIFY: "Verificando",
}


class WorkerSignals(QObject):
    progress = Signal(int, str)
    itemFinished = Signal(object)
    finished = Signal(object)
    failed = Signal(str)


class BatchOperationWorker(QRunnable):
    """Executa um lote sequencialmente; o segredo é limpo ao final."""

    def __init__(
        self,
        *,
        kind: OperationKind,
        files: list[Path],
        secret: Secret,
        service: FileOperationService,
        output_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.kind = kind
        self.files = files
        self.secret = secret
        self.service = service
        self.output_dir = output_dir
        self.cancel_event = threading.Event()
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        items: list[BatchItemResult] = []
        failure_message: str | None = None
        try:
            with self.service.operation_scope(f"{self.kind.value}-batch"):
                total = len(self.files)
                for index, path in enumerate(self.files):
                    if self.cancel_event.is_set():
                        self._record_cancelled_remaining(items, self.files[index:])
                        break
                    filename = safe_filename(Path(path).name)
                    self.signals.progress.emit(
                        int(index / total * 100),
                        f"{_VERBS[self.kind]} {index + 1} de {total}: {filename}",
                    )

                    def on_progress(
                        done: int,
                        total_bytes: int,
                        *,
                        idx: int = index,
                        current_name: str = filename,
                    ) -> None:
                        fraction = (done / total_bytes) if total_bytes else 1.0
                        percent = int(((idx + min(fraction, 1.0)) / total) * 100)
                        self.signals.progress.emit(
                            max(0, min(percent, 99 if idx + 1 < total else 100)),
                            f"{_VERBS[self.kind]} {idx + 1} de {total}: {current_name}",
                        )

                    try:
                        item = self._execute_one(path, on_progress)
                    except CancelledError as exc:
                        self.cancel_event.set()
                        item = BatchItemResult(
                            filename=filename,
                            kind=self.kind,
                            success=False,
                            message=safe_error_message(exc),
                            cancelled=True,
                        )
                        self.signals.itemFinished.emit(item)
                        items.append(item)
                        self._record_cancelled_remaining(items, self.files[index + 1 :])
                        break
                    except CryptoVaultError as exc:
                        item = BatchItemResult(
                            filename=filename,
                            kind=self.kind,
                            success=False,
                            message=safe_error_message(exc),
                        )
                    except Exception as exc:  # pragma: no cover - proteção final
                        logger.exception(
                            "worker_item_error",
                            extra={
                                "event": "worker_item_error",
                                "operation": self.kind.value,
                                "file_name": filename,
                                "result": "failure",
                            },
                        )
                        item = BatchItemResult(
                            filename=filename,
                            kind=self.kind,
                            success=False,
                            message=("Ocorreu um erro interno. Consulte o log da aplicação."),
                            cancelled=False,
                        )
                        del exc
                    self.signals.itemFinished.emit(item)
                    items.append(item)
                    if self.cancel_event.is_set() and index + 1 < total:
                        self._record_cancelled_remaining(items, self.files[index + 1 :])
                        break
                result = BatchResult(
                    kind=self.kind,
                    items=tuple(items),
                    cancelled=self.cancel_event.is_set(),
                )
        except BusyError as exc:
            failure_message = safe_error_message(exc)
            result = BatchResult(kind=self.kind, cancelled=False)
        except Exception:
            logger.exception(
                "worker_batch_error",
                extra={
                    "event": "worker_batch_error",
                    "operation": self.kind.value,
                    "result": "failure",
                },
            )
            failure_message = "Não foi possível iniciar a operação. Consulte o log."
            result = BatchResult(kind=self.kind, cancelled=False)
        finally:
            self.secret.wipe()

        if failure_message is not None:
            self.signals.failed.emit(failure_message)
        else:
            self.signals.finished.emit(result)

    def _execute_one(self, path: Path, on_progress: object) -> BatchItemResult:
        progress = on_progress  # type: ignore[assignment]
        if self.kind is OperationKind.ENCRYPT:
            if self.output_dir is None:
                raise CryptoVaultError("Diretório de saída não informado.")
            result = self.service.encrypt_file(
                path,
                self.secret,
                self.output_dir,
                progress=progress,  # type: ignore[arg-type]
                cancel=self.cancel_event,
            )
            return BatchItemResult(
                filename=safe_filename(path.name),
                kind=self.kind,
                success=True,
                message="Arquivo criptografado com sucesso.",
                output_path=result.output_path,
                size_bytes=result.output_size,
                duration_ms=result.duration_ms,
            )
        if self.kind is OperationKind.DECRYPT:
            if self.output_dir is None:
                raise CryptoVaultError("Diretório de saída não informado.")
            result = self.service.decrypt_file(
                path,
                self.secret,
                self.output_dir,
                progress=progress,  # type: ignore[arg-type]
                cancel=self.cancel_event,
            )
            return BatchItemResult(
                filename=safe_filename(path.name),
                kind=self.kind,
                success=True,
                message="Arquivo recuperado e autenticado com sucesso.",
                output_path=result.output_path,
                size_bytes=result.output_size,
                duration_ms=result.duration_ms,
            )
        result = self.service.verify_file(
            path,
            self.secret,
            progress=progress,  # type: ignore[arg-type]
            cancel=self.cancel_event,
        )
        authenticated = result.status is VerificationStatus.AUTHENTICATED
        return BatchItemResult(
            filename=safe_filename(path.name),
            kind=self.kind,
            success=authenticated,
            message=(
                "Conteúdo autenticado. Todos os blocos e metadados conferem."
                if authenticated
                else result.detail or "A autenticação do conteúdo falhou."
            ),
            size_bytes=0,
            duration_ms=result.duration_ms,
            verification_status=result.status,
        )

    def _record_cancelled_remaining(
        self,
        items: list[BatchItemResult],
        remaining: list[Path],
    ) -> None:
        for path in remaining:
            filename = safe_filename(path.name)
            self.service.record_cancelled(self.kind, path)
            item = BatchItemResult(
                filename=filename,
                kind=self.kind,
                success=False,
                message="Operação cancelada.",
                cancelled=True,
            )
            items.append(item)
            self.signals.itemFinished.emit(item)
