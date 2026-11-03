"""Derivação de chaves com Scrypt e limites rígidos de custo."""

from __future__ import annotations

import hmac
from collections.abc import ByteString

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from cryptovault.crypto.format import (
    DEFAULT_KDF_PARAMS,
    KDF_MEMORY_CAP,
    KEY_SIZE,
    SALT_SIZE,
    KdfParams,
)
from cryptovault.domain.errors import ValidationError


def password_to_bytes(password: str | ByteString) -> bytes:
    if isinstance(password, str):
        encoded = password.encode("utf-8")
    elif isinstance(password, (bytes, bytearray, memoryview)):
        encoded = bytes(password)
    else:  # pragma: no cover - proteção de tipo
        raise TypeError("Senha deve ser texto ou bytes.")
    if not encoded:
        raise ValidationError("A senha não pode ser vazia.")
    if len(encoded) > 1024:
        raise ValidationError("A senha excede o limite de 1024 bytes.")
    return encoded


def derive_key(
    password: str | ByteString,
    salt: bytes,
    params: KdfParams = DEFAULT_KDF_PARAMS,
) -> bytes:
    """Deriva 256 bits. O chamador deve descartar a referência o quanto antes."""
    if len(salt) != SALT_SIZE:
        raise ValidationError("Salt inválido para derivação de chave.")
    params.validate()
    if params.memory_bytes > KDF_MEMORY_CAP:
        raise ValidationError("Custo de KDF acima do limite permitido.")
    password_bytes = password_to_bytes(password)
    try:
        kdf = Scrypt(
            salt=salt,
            length=KEY_SIZE,
            n=params.n,
            r=params.r,
            p=params.p,
        )
        return kdf.derive(password_bytes)
    finally:
        # bytes imutáveis não podem ser apagados de forma confiável; apenas
        # removemos a referência local. A limitação está documentada.
        password_bytes = b""


def constant_time_equal(left: bytes, right: bytes) -> bool:
    return hmac.compare_digest(left, right)
