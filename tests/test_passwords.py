from __future__ import annotations

import pytest

from cryptovault.domain.errors import PasswordError
from cryptovault.security.passwords import (
    MAX_PASSWORD_BYTES,
    Secret,
    estimate_quality,
    validate_password,
)


def test_password_minimum_and_maximum() -> None:
    assert validate_password("12345678") == b"12345678"
    with pytest.raises(PasswordError):
        validate_password("1234567")
    with pytest.raises(PasswordError):
        validate_password("x" * (MAX_PASSWORD_BYTES + 1))
    with pytest.raises(PasswordError):
        validate_password("        ")
    assert validate_password("çãõ-áéí") == "çãõ-áéí".encode()


def test_quality_is_estimative_and_ranks_examples() -> None:
    assert estimate_quality("").score == 0
    assert estimate_quality("123456").score <= 1
    assert estimate_quality("password").score <= 1
    assert estimate_quality("correct horse battery staple 2026").score >= 3
    assert "heurística" in estimate_quality("uma senha longa e exclusiva").hint.lower()


def test_secret_wipes_and_does_not_repr_value() -> None:
    secret = Secret("segredo-muito-sensivel")
    assert secret.bytes_copy() == b"segredo-muito-sensivel"
    assert "segredo" not in repr(secret)
    assert "segredo" not in str(secret)
    secret.wipe()
    assert secret.is_cleared
    with pytest.raises(PasswordError):
        secret.bytes_copy()


def test_secret_context_manager() -> None:
    with Secret("outro-segredo-longo") as secret:
        assert len(secret) == len("outro-segredo-longo")
    assert secret.is_cleared
