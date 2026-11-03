"""Formato binário versionado CryptoVault v1.

Layout do cabeçalho (80 bytes, big-endian)::

    offset  size  campo
    0       8     magic = b"CVLTFILE"
    8       1     format_version = 1
    9       1     algorithm_id = 1 (AES-256-GCM)
    10      1     kdf_id = 1 (Scrypt)
    11      1     kdf_log2_n
    12      4     kdf_r
    16      4     kdf_p
    20      1     salt_length = 32
    21      32    salt
    53      1     nonce_prefix_length = 8
    54      8     nonce_prefix
    62      4     chunk_size (1 MiB)
    66      8     plaintext_size
    74      1     flags = 0
    75      5     reserved = 0

Cada registro de conteúdo é ``uint32 plaintext_len || ciphertext || tag(16)``.
O nonce de 96 bits é ``nonce_prefix(8) || contador(4)`` e nunca se repete para
a mesma chave. O AAD de cada registro autentica o cabeçalho completo, o índice
do registro, o tamanho em claro e o marcador de registro final.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from cryptovault.domain.errors import (
    FormatError,
    SizeLimitError,
    UnsupportedVersionError,
    ValidationError,
)

MAGIC = b"CVLTFILE"
FORMAT_VERSION = 1
ALGORITHM_AES_256_GCM = 1
KDF_SCRYPT = 1

SALT_SIZE = 32
NONCE_PREFIX_SIZE = 8
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
CHUNK_SIZE = 1024 * 1024
MAX_FILE_SIZE = 100 * 1024**3  # 100 GiB
MAX_CHUNKS = (MAX_FILE_SIZE + CHUNK_SIZE - 1) // CHUNK_SIZE

KDF_MIN_LOG_N = 15
KDF_MAX_LOG_N = 18
KDF_MIN_R = 8
KDF_MAX_R = 16
KDF_MIN_P = 1
KDF_MAX_P = 4
KDF_MEMORY_CAP = 256 * 1024**2
KDF_DEFAULT_LOG_N = 15
KDF_DEFAULT_R = 8
KDF_DEFAULT_P = 1

# >8sBBBBIIB32sB8sIQB5s
HEADER_STRUCT = struct.Struct(">8sBBBBIIB32sB8sIQB5s")
HEADER_SIZE = HEADER_STRUCT.size
RECORD_AAD_STRUCT = struct.Struct(">QIB")
RECORD_LENGTH_STRUCT = struct.Struct(">I")
if HEADER_SIZE != 80:  # pragma: no cover - invariante de formato
    raise RuntimeError("Layout de cabeçalho inesperado.")
if RECORD_AAD_STRUCT.size != 13:  # pragma: no cover - invariante de formato
    raise RuntimeError("Layout de AAD inesperado.")


@dataclass(frozen=True, slots=True)
class KdfParams:
    log_n: int = KDF_DEFAULT_LOG_N
    r: int = KDF_DEFAULT_R
    p: int = KDF_DEFAULT_P

    @property
    def n(self) -> int:
        return 1 << self.log_n

    @property
    def memory_bytes(self) -> int:
        # Scrypt usa aproximadamente 128 * N * r bytes.
        return 128 * self.n * self.r

    def validate(self) -> None:
        if not KDF_MIN_LOG_N <= self.log_n <= KDF_MAX_LOG_N:
            raise ValidationError(
                f"log2(N) fora dos limites: {self.log_n}",
                user_message="Parâmetros de derivação de chave fora dos limites permitidos.",
            )
        if not KDF_MIN_R <= self.r <= KDF_MAX_R:
            raise ValidationError(
                f"r fora dos limites: {self.r}",
                user_message="Parâmetros de derivação de chave fora dos limites permitidos.",
            )
        if not KDF_MIN_P <= self.p <= KDF_MAX_P:
            raise ValidationError(
                f"p fora dos limites: {self.p}",
                user_message="Parâmetros de derivação de chave fora dos limites permitidos.",
            )
        if self.memory_bytes > KDF_MEMORY_CAP:
            raise ValidationError(
                f"memória estimada do KDF excede o limite: {self.memory_bytes}",
                user_message="Parâmetros de derivação de chave exigem memória excessiva.",
            )


DEFAULT_KDF_PARAMS = KdfParams()
DEFAULT_KDF_PARAMS.validate()


@dataclass(frozen=True, slots=True)
class CryptoHeader:
    version: int
    algorithm_id: int
    kdf: KdfParams
    salt: bytes
    nonce_prefix: bytes
    chunk_size: int
    plaintext_size: int
    flags: int = 0

    def to_bytes(self) -> bytes:
        if len(self.salt) != SALT_SIZE:
            raise FormatError("Tamanho de salt inválido.")
        if len(self.nonce_prefix) != NONCE_PREFIX_SIZE:
            raise FormatError("Tamanho do prefixo de nonce inválido.")
        self.kdf.validate()
        if self.flag_bytes:
            raise FormatError("Flags desconhecidas no cabeçalho.")
        if not 0 <= self.plaintext_size <= MAX_FILE_SIZE:
            raise SizeLimitError("Tamanho em claro fora do limite.")
        if self.chunk_size != CHUNK_SIZE:
            raise FormatError("Tamanho de bloco não suportado.")
        return HEADER_STRUCT.pack(
            MAGIC,
            self.version,
            self.algorithm_id,
            KDF_SCRYPT,
            self.kdf.log_n,
            self.kdf.r,
            self.kdf.p,
            SALT_SIZE,
            self.salt,
            NONCE_PREFIX_SIZE,
            self.nonce_prefix,
            self.chunk_size,
            self.plaintext_size,
            self.flags,
            b"\x00" * 5,
        )

    @property
    def flag_bytes(self) -> int:
        return self.flags


def parse_header(data: bytes) -> CryptoHeader:
    """Valida todo o cabeçalho antes de qualquer derivação custosa."""
    if len(data) != HEADER_SIZE:
        raise FormatError("Cabeçalho incompleto.")
    (
        magic,
        version,
        algorithm_id,
        kdf_id,
        log_n,
        r,
        p,
        salt_len,
        salt,
        nonce_len,
        nonce_prefix,
        chunk_size,
        plaintext_size,
        flags,
        reserved,
    ) = HEADER_STRUCT.unpack(data)

    if magic != MAGIC:
        raise FormatError("Magic bytes inválidos.")
    if version != FORMAT_VERSION:
        raise UnsupportedVersionError(f"Versão {version} não suportada.")
    if algorithm_id != ALGORITHM_AES_256_GCM:
        raise FormatError(f"Algoritmo {algorithm_id} não suportado.")
    if kdf_id != KDF_SCRYPT:
        raise FormatError(f"KDF {kdf_id} não suportado.")
    if salt_len != SALT_SIZE or nonce_len != NONCE_PREFIX_SIZE:
        raise FormatError("Tamanhos de salt ou nonce inválidos.")
    if chunk_size != CHUNK_SIZE:
        raise FormatError("Tamanho de bloco não suportado.")
    if flags != 0:
        raise FormatError("Flags desconhecidas no cabeçalho.")
    if reserved != b"\x00" * 5:
        raise FormatError("Bytes reservados inválidos.")
    if salt == b"\x00" * SALT_SIZE or nonce_prefix == b"\x00" * NONCE_PREFIX_SIZE:
        raise FormatError("Salt ou nonce inválido.")
    if plaintext_size > MAX_FILE_SIZE:
        raise SizeLimitError("O cabeçalho declara um arquivo grande demais.")
    if plaintext_size > 0 and (plaintext_size + CHUNK_SIZE - 1) // CHUNK_SIZE > MAX_CHUNKS:
        raise FormatError("Quantidade de blocos inválida.")

    kdf = KdfParams(log_n=log_n, r=r, p=p)
    kdf.validate()

    return CryptoHeader(
        version=version,
        algorithm_id=algorithm_id,
        kdf=kdf,
        salt=salt,
        nonce_prefix=nonce_prefix,
        chunk_size=chunk_size,
        plaintext_size=plaintext_size,
        flags=flags,
    )


def build_header(
    *,
    salt: bytes,
    nonce_prefix: bytes,
    plaintext_size: int,
    params: KdfParams = DEFAULT_KDF_PARAMS,
) -> tuple[CryptoHeader, bytes]:
    header = CryptoHeader(
        version=FORMAT_VERSION,
        algorithm_id=ALGORITHM_AES_256_GCM,
        kdf=params,
        salt=salt,
        nonce_prefix=nonce_prefix,
        chunk_size=CHUNK_SIZE,
        plaintext_size=plaintext_size,
    )
    return header, header.to_bytes()


def nonce_for(prefix: bytes, counter: int) -> bytes:
    if len(prefix) != NONCE_PREFIX_SIZE:
        raise ValueError("Prefixo de nonce inválido.")
    if not 0 <= counter <= 0xFFFFFFFF:
        raise ValueError("Contador de nonce esgotado.")
    return prefix + struct.pack(">I", counter)


def record_aad(header_bytes: bytes, index: int, plaintext_len: int, final: bool) -> bytes:
    if not 0 <= index <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("Índice de registro inválido.")
    return header_bytes + RECORD_AAD_STRUCT.pack(index, plaintext_len, int(final))


def header_fingerprint(header_bytes: bytes) -> str:
    """Identificador público curto; não é uma assinatura nem prova de origem."""
    return hashlib.sha256(header_bytes).hexdigest()[:16]


def expected_chunk_lengths(plaintext_size: int) -> list[int]:
    """Somente para testes e diagnóstico; não alocar para arquivos grandes."""
    if plaintext_size == 0:
        return [0]
    full, remainder = divmod(plaintext_size, CHUNK_SIZE)
    lengths = [CHUNK_SIZE] * full
    if remainder:
        lengths.append(remainder)
    return lengths
