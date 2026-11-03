"""Tipos de domínio compartilhados, sem dependência de Qt ou de criptografia."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class OperationKind(StrEnum):
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    VERIFY = "verify"

    @property
    def label_pt(self) -> str:
        return {
            OperationKind.ENCRYPT: "Criptografia",
            OperationKind.DECRYPT: "Descriptografia",
            OperationKind.VERIFY: "Verificação",
        }[self]


class OperationOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"

    @property
    def label_pt(self) -> str:
        return {
            OperationOutcome.SUCCESS: "Sucesso",
            OperationOutcome.FAILURE: "Falha",
            OperationOutcome.CANCELLED: "Cancelado",
        }[self]


class VerificationStatus(StrEnum):
    AUTHENTICATED = "authenticated"
    INVALID_AUTHENTICATION = "invalid_authentication"
    INVALID_FORMAT = "invalid_format"
    UNSUPPORTED_VERSION = "unsupported_version"

    @property
    def label_pt(self) -> str:
        return {
            VerificationStatus.AUTHENTICATED: "Conteúdo autenticado",
            VerificationStatus.INVALID_AUTHENTICATION: "Autenticação inválida",
            VerificationStatus.INVALID_FORMAT: "Formato inválido",
            VerificationStatus.UNSUPPORTED_VERSION: "Versão não suportada",
        }[self]


@dataclass(frozen=True, slots=True)
class OperationRecord:
    """Registro de histórico. Nunca contém senhas, chaves ou conteúdo."""

    kind: OperationKind
    filename: str
    outcome: OperationOutcome
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = 0
    duration_ms: int = 0
    id: int | None = None


@dataclass(frozen=True, slots=True)
class HeaderInfo:
    """Metadados públicos e não secretos do envelope criptográfico."""

    version: int
    algorithm_id: int
    kdf_id: int
    kdf_log_n: int
    kdf_r: int
    kdf_p: int
    salt_size: int
    nonce_size: int
    chunk_size: int
    plaintext_size: int
    header_size: int
    fingerprint: str

    @property
    def algorithm_label(self) -> str:
        return "AES-256-GCM" if self.algorithm_id == 1 else f"Algoritmo {self.algorithm_id}"

    @property
    def kdf_label(self) -> str:
        return "Scrypt" if self.kdf_id == 1 else f"KDF {self.kdf_id}"

    @property
    def chunk_count(self) -> int:
        if self.plaintext_size == 0:
            return 1
        return (self.plaintext_size + self.chunk_size - 1) // self.chunk_size


@dataclass(frozen=True, slots=True)
class EncryptResult:
    kind: OperationKind = OperationKind.ENCRYPT
    output_path: Path = Path()
    source_size: int = 0
    output_size: int = 0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class DecryptResult:
    kind: OperationKind = OperationKind.DECRYPT
    output_path: Path = Path()
    source_size: int = 0
    output_size: int = 0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class VerifyResult:
    kind: OperationKind = OperationKind.VERIFY
    status: VerificationStatus = VerificationStatus.INVALID_FORMAT
    header: HeaderInfo | None = None
    duration_ms: int = 0
    detail: str = ""

    @property
    def is_authenticated(self) -> bool:
        return self.status is VerificationStatus.AUTHENTICATED


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    filename: str
    kind: OperationKind
    success: bool
    message: str
    output_path: Path | None = None
    size_bytes: int = 0
    duration_ms: int = 0
    cancelled: bool = False
    verification_status: VerificationStatus | None = None


@dataclass(frozen=True, slots=True)
class BatchResult:
    kind: OperationKind
    items: tuple[BatchItemResult, ...] = ()
    cancelled: bool = False

    @property
    def succeeded(self) -> int:
        return sum(1 for item in self.items if item.success)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if not item.success and not item.cancelled)

    @property
    def cancelled_count(self) -> int:
        return sum(1 for item in self.items if item.cancelled)


@dataclass(slots=True)
class SessionStats:
    encrypted: int = 0
    decrypted: int = 0
    verified: int = 0
    failures: int = 0

    def reset(self) -> None:
        self.encrypted = self.decrypted = self.verified = self.failures = 0
