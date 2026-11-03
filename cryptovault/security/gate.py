"""Portão de concorrência para impedir operações simultâneas conflitantes."""

from __future__ import annotations

import threading

from cryptovault.domain.errors import BusyError


class OperationGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owner: str | None = None

    @property
    def owner(self) -> str | None:
        with self._lock:
            return self._owner

    def enter(self, owner: str) -> None:
        with self._lock:
            if self._owner is not None:
                raise BusyError("Já existe uma operação em andamento.")
            self._owner = owner

    def leave(self, owner: str) -> None:
        with self._lock:
            if self._owner == owner:
                self._owner = None

    def __enter__(self) -> OperationGate:
        self.enter("operation")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.leave("operation")
