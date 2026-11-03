"""Avaliação heurística de senhas e invólucro para limpeza de segredos."""

from __future__ import annotations

import math
import re
from collections.abc import ByteString
from dataclasses import dataclass

from cryptovault.domain.errors import PasswordError

MIN_PASSWORD_BYTES = 8
MAX_PASSWORD_BYTES = 1024


@dataclass(frozen=True, slots=True)
class PasswordQuality:
    score: int
    label: str
    hint: str

    @property
    def is_estimate(self) -> bool:
        return True


_COMMON = {
    "123456",
    "12345678",
    "123456789",
    "password",
    "senha",
    "senha123",
    "qwerty",
    "abc123",
    "admin",
    "letmein",
    "welcome",
    "iloveyou",
    "monkey",
    "dragon",
    "football",
    "master",
    "sunshine",
    "princess",
    "trustno1",
    "passw0rd",
    "cryptovault",
}
_SEQUENCES = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm")


def password_bytes(value: str | ByteString) -> bytes:
    if isinstance(value, str):
        result = value.encode("utf-8")
    elif isinstance(value, (bytes, bytearray, memoryview)):
        result = bytes(value)
    else:  # pragma: no cover - proteção de tipo
        raise PasswordError("Tipo de senha inválido.")
    return result


def validate_password(value: str | ByteString) -> bytes:
    encoded = password_bytes(value)
    if len(encoded) < MIN_PASSWORD_BYTES:
        raise PasswordError(
            f"Senha com menos de {MIN_PASSWORD_BYTES} bytes.",
            user_message=f"A senha deve ter pelo menos {MIN_PASSWORD_BYTES} caracteres.",
        )
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordError(
            "Senha acima do limite.",
            user_message="A senha excede o limite de 1024 bytes.",
        )
    if not encoded.strip():
        raise PasswordError("Senha composta apenas por espaços.")
    return encoded


def estimate_quality(value: str) -> PasswordQuality:
    """Estimativa local e heurística; não mede resistência real a ataques."""
    if not value:
        return PasswordQuality(0, "Não informada", "Use uma frase-senha longa e exclusiva.")

    classes = 0
    if re.search(r"[a-z]", value):
        classes += 1
    if re.search(r"[A-Z]", value):
        classes += 1
    if re.search(r"\d", value):
        classes += 1
    if re.search(r"[^\w\s]", value):
        classes += 1
    if re.search(r"\s", value):
        classes += 1

    charset = 26 * max(1, classes)
    entropy = len(value) * math.log2(charset)
    lowered = value.casefold()
    repeated = len(set(value)) / max(1, len(value))
    if lowered in _COMMON:
        entropy = min(entropy, 18.0)
    if repeated < 0.35:
        entropy *= 0.72
    if any(seq in lowered for seq in _SEQUENCES):
        entropy *= 0.75
    if re.fullmatch(r"(.)\1{3,}", value):
        entropy = min(entropy, 16.0)

    if entropy < 28:
        score, label = 0, "Muito fraca"
    elif entropy < 40:
        score, label = 1, "Fraca"
    elif entropy < 60:
        score, label = 2, "Média"
    elif entropy < 80:
        score, label = 3, "Forte"
    else:
        score, label = 4, "Muito forte"

    if len(value) < MIN_PASSWORD_BYTES:
        score = min(score, 1)
        label = "Curta"
    hint = "Estimativa heurística. Use uma senha longa, única e guardada em local seguro."
    return PasswordQuality(score, label, hint)


class Secret:
    """Buffer mutável de senha com limpeza explícita em melhor esforço.

    Python e bibliotecas podem criar cópias internas; a limpeza elimina apenas
    as referências controladas pela aplicação. Nenhum segredo é registrado.
    """

    __slots__ = ("_buffer", "_cleared")

    def __init__(self, value: str | ByteString) -> None:
        encoded = validate_password(value)
        self._buffer = bytearray(encoded)
        self._cleared = False

    @classmethod
    def from_text(cls, value: str) -> Secret:
        return cls(value)

    def bytes_copy(self) -> bytes:
        if self._cleared:
            raise PasswordError("Segredo já foi descartado.")
        return bytes(self._buffer)

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return "Secret(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"

    def wipe(self) -> None:
        if not self._cleared:
            self._buffer[:] = b"\x00" * len(self._buffer)
            self._buffer.clear()
            self._cleared = True

    @property
    def is_cleared(self) -> bool:
        return self._cleared

    def __enter__(self) -> Secret:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.wipe()
