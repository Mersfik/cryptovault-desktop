"""Controlador de aplicação: liga casos de uso, workers e sinais da interface."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal

from cryptovault.application.service import FileOperationService
from cryptovault.domain.errors import BusyError, safe_error_message
from cryptovault.domain.models import (
    BatchItemResult,
    BatchResult,
    OperationKind,
    SessionStats,
)
from cryptovault.security.passwords import Secret
from cryptovault.ui.workers import BatchOperationWorker


class AppController(QObject):
    progress = Signal(int, str)
    itemFinished = Signal(object)
    operationFinished = Signal(object)
    busyChanged = Signal(bool)
    statsChanged = Signal(object)
    historyChanged = Signal()
    errorRaised = Signal(str)
    notification = Signal(str, str)

    def __init__(self, service: FileOperationService, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.stats = SessionStats()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._worker: BatchOperationWorker | None = None
        self._busy = False
        self._current_kind: OperationKind | None = None
        self._notifications_enabled = True
        self._notify_success = True
        self._notify_failure = True

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def current_kind(self) -> OperationKind | None:
        return self._current_kind

    def configure_notifications(
        self,
        *,
        enabled: bool,
        on_success: bool,
        on_failure: bool,
    ) -> None:
        self._notifications_enabled = enabled
        self._notify_success = on_success
        self._notify_failure = on_failure

    def start_encrypt(
        self,
        files: Sequence[str | Path],
        secret: Secret,
        output_dir: str | Path,
    ) -> bool:
        return self._start(
            OperationKind.ENCRYPT,
            files,
            secret,
            output_dir=Path(output_dir),
        )

    def start_decrypt(
        self,
        files: Sequence[str | Path],
        secret: Secret,
        output_dir: str | Path,
    ) -> bool:
        return self._start(
            OperationKind.DECRYPT,
            files,
            secret,
            output_dir=Path(output_dir),
        )

    def start_verify(self, files: Sequence[str | Path], secret: Secret) -> bool:
        return self._start(OperationKind.VERIFY, files, secret)

    def cancel(self) -> None:
        if self._worker is not None and self._busy:
            self._worker.cancel()
            self.progress.emit(0, "Cancelamento solicitado…")

    def _start(
        self,
        kind: OperationKind,
        files: Sequence[str | Path],
        secret: Secret,
        *,
        output_dir: Path | None = None,
    ) -> bool:
        if self._busy:
            secret.wipe()
            self.errorRaised.emit("Já existe uma operação em andamento.")
            return False
        paths = [Path(item) for item in files]
        if not paths:
            secret.wipe()
            self.errorRaised.emit("Selecione ao menos um arquivo.")
            return False
        try:
            worker = BatchOperationWorker(
                kind=kind,
                files=paths,
                secret=secret,
                service=self.service,
                output_dir=output_dir,
            )
        except Exception:
            secret.wipe()
            raise
        self._busy = True
        self._current_kind = kind
        self._worker = worker
        worker.signals.progress.connect(self.progress)
        worker.signals.itemFinished.connect(self._on_item_finished)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self.busyChanged.emit(True)
        self._pool.start(worker)
        return True

    def _on_item_finished(self, item: BatchItemResult) -> None:
        self.itemFinished.emit(item)

    def _on_finished(self, result: BatchResult) -> None:
        self._finish_busy()
        self._update_stats(result)
        self.historyChanged.emit()
        self.statsChanged.emit(self.stats)
        self.operationFinished.emit(result)
        self._notify_result(result)

    def _on_failed(self, message: str) -> None:
        self._finish_busy()
        self.errorRaised.emit(message)
        self.historyChanged.emit()

    def _finish_busy(self) -> None:
        self._busy = False
        self._current_kind = None
        self._worker = None
        self.busyChanged.emit(False)

    def _update_stats(self, result: BatchResult) -> None:
        for item in result.items:
            if item.success:
                if item.kind is OperationKind.ENCRYPT:
                    self.stats.encrypted += 1
                elif item.kind is OperationKind.DECRYPT:
                    self.stats.decrypted += 1
                elif item.kind is OperationKind.VERIFY:
                    self.stats.verified += 1
            elif not item.cancelled:
                self.stats.failures += 1

    def _notify_result(self, result: BatchResult) -> None:
        if not self._notifications_enabled:
            return
        if result.succeeded and self._notify_success:
            label = {
                OperationKind.ENCRYPT: "Criptografia concluída",
                OperationKind.DECRYPT: "Descriptografia concluída",
                OperationKind.VERIFY: "Verificação concluída",
            }[result.kind]
            if result.failed:
                text = f"{result.succeeded} concluído(s), {result.failed} com falha."
                variant = "warning"
            else:
                text = f"{result.succeeded} arquivo(s) processado(s) com sucesso."
                variant = "success"
            self.notification.emit(f"{label}: {text}", variant)
            return
        if (result.failed or result.cancelled_count) and self._notify_failure:
            if result.cancelled:
                self.notification.emit("Operação cancelada.", "warning")
            else:
                self.notification.emit(
                    f"Operação concluída com {result.failed} falha(s).",
                    "error",
                )

    def wait_for_idle(self, timeout_ms: int = 15_000) -> bool:
        finished = self._pool.waitForDone(timeout_ms)
        if finished:
            self._finish_busy()
        return finished

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._pool.waitForDone(15_000)

    def clear_history(self) -> int:
        count = self.service.clear_history()
        self.historyChanged.emit()
        return count

    def record_retention(self, days: int) -> int:
        return self.service.apply_retention(days)

    def list_history(self, **kwargs: object) -> list[object]:
        return self.service.list_history(**kwargs)  # type: ignore[arg-type]

    def runtime_status(self) -> str:
        return "Operação em andamento" if self._busy else "Pronto"

    def safe_error(self, exc: BaseException) -> str:
        return safe_error_message(exc)

    def ensure_not_busy(self) -> None:
        if self._busy:
            raise BusyError("Já existe uma operação em andamento.")
