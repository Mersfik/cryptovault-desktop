from __future__ import annotations

import pytest

from cryptovault.crypto.format import KdfParams
from cryptovault.crypto.kdf import constant_time_equal, derive_key, password_to_bytes
from cryptovault.domain.errors import ValidationError

pytestmark = pytest.mark.security


def test_scrypt_is_deterministic_for_same_salt() -> None:
    salt = b"0123456789abcdef0123456789abcdef"
    first = derive_key("senha longa e exclusiva", salt)
    second = derive_key("senha longa e exclusiva", salt)
    assert first == second
    assert len(first) == 32


def test_scrypt_changes_with_password_and_salt() -> None:
    salt = b"0123456789abcdef0123456789abcdef"
    base = derive_key("senha longa e exclusiva", salt)
    assert base != derive_key("outra senha longa e exclusiva", salt)
    assert base != derive_key("senha longa e exclusiva", b"fedcba9876543210fedcba9876543210")


def test_password_limits() -> None:
    with pytest.raises(ValidationError):
        password_to_bytes("")
    with pytest.raises(ValidationError):
        password_to_bytes("x" * 1025)
    assert password_to_bytes("senha") == b"senha"
    assert password_to_bytes(bytearray(b"bytes")) == b"bytes"
    assert password_to_bytes(memoryview(b"view")) == b"view"


@pytest.mark.parametrize(
    "params",
    [
        KdfParams(log_n=14, r=8, p=1),
        KdfParams(log_n=19, r=8, p=1),
        KdfParams(log_n=15, r=7, p=1),
        KdfParams(log_n=15, r=8, p=0),
        KdfParams(log_n=18, r=16, p=4),
    ],
)
def test_invalid_kdf_parameters_rejected(params: KdfParams) -> None:
    with pytest.raises(ValidationError):
        params.validate()


def test_salt_length_enforced() -> None:
    with pytest.raises(ValidationError):
        derive_key("senha longa e exclusiva", b"short")


def test_constant_time_compare() -> None:
    assert constant_time_equal(b"abc", b"abc")
    assert not constant_time_equal(b"abc", b"abd")
