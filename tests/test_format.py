from __future__ import annotations

import struct
from contextlib import suppress

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptovault.crypto.format import (
    ALGORITHM_AES_256_GCM,
    CHUNK_SIZE,
    DEFAULT_KDF_PARAMS,
    HEADER_SIZE,
    HEADER_STRUCT,
    KDF_SCRYPT,
    MAGIC,
    SALT_SIZE,
    CryptoHeader,
    KdfParams,
    build_header,
    header_fingerprint,
    nonce_for,
    parse_header,
    record_aad,
)
from cryptovault.domain.errors import (
    CryptoVaultError,
    FormatError,
    SizeLimitError,
    UnsupportedVersionError,
    ValidationError,
)

pytestmark = pytest.mark.security


def _header_bytes(**overrides: object) -> bytes:
    values = {
        "magic": MAGIC,
        "version": 1,
        "algorithm": ALGORITHM_AES_256_GCM,
        "kdf": KDF_SCRYPT,
        "log_n": 15,
        "r": 8,
        "p": 1,
        "salt_len": 32,
        "salt": b"S" * 32,
        "nonce_len": 8,
        "nonce": b"N" * 8,
        "chunk_size": CHUNK_SIZE,
        "plaintext_size": 42,
        "flags": 0,
        "reserved": b"\x00" * 5,
    }
    values.update(overrides)
    return HEADER_STRUCT.pack(*values.values())


def test_header_roundtrip_and_size() -> None:
    header, raw = build_header(
        salt=b"A" * SALT_SIZE,
        nonce_prefix=b"B" * 8,
        plaintext_size=2 * CHUNK_SIZE + 9,
    )
    assert len(raw) == HEADER_SIZE == 80
    parsed = parse_header(raw)
    assert parsed == header
    assert header_fingerprint(raw) == header_fingerprint(raw)
    assert len(header_fingerprint(raw)) == 16


def test_default_kdf_is_within_limits() -> None:
    DEFAULT_KDF_PARAMS.validate()
    assert DEFAULT_KDF_PARAMS.n == 32768
    assert DEFAULT_KDF_PARAMS.memory_bytes == 32 * 1024 * 1024


@pytest.mark.parametrize(
    ("overrides", "exception"),
    [
        ({"magic": b"BADMAGIC"}, FormatError),
        ({"version": 2}, UnsupportedVersionError),
        ({"algorithm": 2}, FormatError),
        ({"kdf": 2}, FormatError),
        ({"salt_len": 16}, FormatError),
        ({"nonce_len": 12}, FormatError),
        ({"chunk_size": 1024}, FormatError),
        ({"flags": 1}, FormatError),
        ({"reserved": b"\x00\x00\x00\x00\x01"}, FormatError),
        ({"salt": b"\x00" * 32}, FormatError),
        ({"nonce": b"\x00" * 8}, FormatError),
        ({"plaintext_size": 101 * 1024**3}, SizeLimitError),
        ({"log_n": 14}, ValidationError),
        ({"log_n": 19}, ValidationError),
        ({"r": 7}, ValidationError),
        ({"p": 0}, ValidationError),
        ({"log_n": 18, "r": 16}, ValidationError),
    ],
)
def test_invalid_header_fields_rejected(
    overrides: dict[str, object], exception: type[Exception]
) -> None:
    with pytest.raises(exception):
        parse_header(_header_bytes(**overrides))


def test_truncated_or_oversized_header_rejected() -> None:
    with pytest.raises(FormatError):
        parse_header(b"short")
    with pytest.raises(FormatError):
        parse_header(b"x" * (HEADER_SIZE + 1))


def test_header_rejects_empty_salt_when_building() -> None:
    with pytest.raises(FormatError):
        CryptoHeader(
            version=1,
            algorithm_id=1,
            kdf=KdfParams(),
            salt=b"",
            nonce_prefix=b"n" * 8,
            chunk_size=CHUNK_SIZE,
            plaintext_size=1,
        ).to_bytes()


def test_nonce_is_96_bits_and_unique_by_counter() -> None:
    prefix = b"12345678"
    first = nonce_for(prefix, 0)
    second = nonce_for(prefix, 1)
    assert len(first) == 12
    assert first != second
    assert first[:8] == prefix
    with pytest.raises(ValueError):
        nonce_for(prefix, -1)
    with pytest.raises(ValueError):
        nonce_for(b"short", 1)


def test_record_aad_authenticates_index_length_and_final_flag() -> None:
    header = b"h" * HEADER_SIZE
    base = record_aad(header, 0, 100, False)
    assert base != record_aad(header, 1, 100, False)
    assert base != record_aad(header, 0, 101, False)
    assert base != record_aad(header, 0, 100, True)
    assert len(base) == HEADER_SIZE + 13


@given(st.binary(max_size=220))
def test_parser_never_raises_unexpected_exception(data: bytes) -> None:
    if len(data) != HEADER_SIZE:
        with pytest.raises(FormatError):
            parse_header(data)
        return
    with suppress(CryptoVaultError):
        parse_header(data)


def test_struct_integer_bounds_are_not_negative() -> None:
    raw = bytearray(_header_bytes())
    # plaintext_size é u64; valores altos são rejeitados pelo limite explícito.
    raw[66:74] = struct.pack(">Q", 2**63)
    with pytest.raises(SizeLimitError):
        parse_header(bytes(raw))
