from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from cryptovault.crypto.engine import CryptoEngine
from cryptovault.crypto.format import CHUNK_SIZE, HEADER_SIZE
from cryptovault.domain.errors import (
    AuthenticationError,
    CancelledError,
    FormatError,
    OutputExistsError,
    PathSecurityError,
)
from cryptovault.domain.models import VerificationStatus

pytestmark = pytest.mark.security
PASSWORD = "frase-senha-de-teste-segura-2026"


def _encrypt(engine: CryptoEngine, source: Path, destination: Path) -> None:
    engine.encrypt_file(source, destination, PASSWORD)


@pytest.mark.parametrize(
    "size",
    [0, 1, 1024, CHUNK_SIZE, CHUNK_SIZE + 1, CHUNK_SIZE * 2 + 37],
)
def test_roundtrip_sizes(tmp_path: Path, size: int) -> None:
    engine = CryptoEngine()
    source = tmp_path / f"source-{size}.bin"
    payload = os.urandom(size)
    source.write_bytes(payload)
    encrypted = tmp_path / f"encrypted-{size}.cvlt"
    _encrypt(engine, source, encrypted)
    assert encrypted.stat().st_size > len(payload)
    decrypted = tmp_path / f"decrypted-{size}.bin"
    result = engine.decrypt_file(encrypted, decrypted, PASSWORD)
    assert decrypted.read_bytes() == payload
    assert result.output_size == len(payload)
    assert result.source_size == encrypted.stat().st_size


def test_inspect_does_not_require_password(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "inspect.cvlt"
    _encrypt(engine, sample_file, encrypted)
    info = engine.inspect_file(encrypted)
    assert info.version == 1
    assert info.algorithm_label == "AES-256-GCM"
    assert info.kdf_label == "Scrypt"
    assert info.salt_size == 32
    assert info.nonce_size == 12
    assert info.plaintext_size == sample_file.stat().st_size
    assert len(info.fingerprint) == 16


def test_wrong_password_is_rejected_without_output(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "wrong.cvlt"
    _encrypt(engine, sample_file, encrypted)
    output = tmp_path / "never.bin"
    with pytest.raises(AuthenticationError):
        engine.decrypt_file(encrypted, output, "senha-completamente-errada")
    assert not output.exists()
    assert not list(tmp_path.glob(".cryptovault-*"))


def test_tampered_ciphertext_tag_and_header_are_rejected(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "tamper.cvlt"
    _encrypt(engine, sample_file, encrypted)
    original = encrypted.read_bytes()
    mutations = {
        "tag": len(original) - 1,
        "ciphertext": HEADER_SIZE + 8,
        "salt": 25,
        "nonce": 58,
    }
    for name, index in mutations.items():
        data = bytearray(original)
        data[index] ^= 0x01
        tampered = tmp_path / f"{name}.cvlt"
        tampered.write_bytes(bytes(data))
        output = tmp_path / f"{name}.out"
        with pytest.raises(AuthenticationError):
            engine.decrypt_file(tampered, output, PASSWORD)
        assert not output.exists(), name


@pytest.mark.parametrize("mutation", ["truncate", "append", "length"])
def test_malformed_structure_is_rejected(tmp_path: Path, sample_file: Path, mutation: str) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "malformed.cvlt"
    _encrypt(engine, sample_file, encrypted)
    data = encrypted.read_bytes()
    if mutation == "truncate":
        changed = data[:-1]
    elif mutation == "append":
        changed = data + b"extra"
    else:
        raw = bytearray(data)
        raw[HEADER_SIZE : HEADER_SIZE + 4] = (0xFFFFFFFF).to_bytes(4, "big")
        changed = bytes(raw)
    malformed = tmp_path / f"{mutation}.cvlt"
    malformed.write_bytes(changed)
    output = tmp_path / f"{mutation}.out"
    with pytest.raises((AuthenticationError, FormatError)):
        engine.decrypt_file(malformed, output, PASSWORD)
    assert not output.exists()
    assert not list(tmp_path.glob(".cryptovault-*"))


def test_no_partial_output_when_later_chunk_is_tampered(tmp_path: Path) -> None:
    engine = CryptoEngine()
    source = tmp_path / "multi.bin"
    source.write_bytes(os.urandom(CHUNK_SIZE + 2048))
    encrypted = tmp_path / "multi.cvlt"
    _encrypt(engine, source, encrypted)
    data = bytearray(encrypted.read_bytes())
    second_tag = HEADER_SIZE + 4 + CHUNK_SIZE + 16 + 4 + 2048 + 15
    data[second_tag] ^= 0xFF
    tampered = tmp_path / "multi-tampered.cvlt"
    tampered.write_bytes(bytes(data))
    output = tmp_path / "partial.bin"
    with pytest.raises(AuthenticationError):
        engine.decrypt_file(tampered, output, PASSWORD)
    assert not output.exists()
    assert not list(tmp_path.glob(".cryptovault-*"))


def test_verify_authenticated_wrong_password_and_tamper(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "verify.cvlt"
    _encrypt(engine, sample_file, encrypted)
    assert engine.verify_file(encrypted, PASSWORD).status is VerificationStatus.AUTHENTICATED
    assert (
        engine.verify_file(encrypted, "senha-totalmente-incorreta").status
        is VerificationStatus.INVALID_AUTHENTICATION
    )
    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 0x01
    tampered = tmp_path / "verify-tamper.cvlt"
    tampered.write_bytes(bytes(data))
    assert (
        engine.verify_file(tampered, PASSWORD).status is VerificationStatus.INVALID_AUTHENTICATION
    )


def test_verify_truncated_file_reports_invalid_format(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "trunc.cvlt"
    _encrypt(engine, sample_file, encrypted)
    truncated = tmp_path / "truncated.cvlt"
    truncated.write_bytes(encrypted.read_bytes()[:-1])
    result = engine.verify_file(truncated, PASSWORD)
    assert result.status is VerificationStatus.INVALID_FORMAT


def test_no_overwrite_preserves_existing_file(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    destination = tmp_path / "existing.cvlt"
    destination.write_bytes(b"do-not-overwrite")
    with pytest.raises(OutputExistsError):
        engine.encrypt_file(sample_file, destination, PASSWORD)
    assert destination.read_bytes() == b"do-not-overwrite"


def test_cancel_before_start_creates_no_output(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    cancel = threading.Event()
    cancel.set()
    output = tmp_path / "cancelled.cvlt"
    with pytest.raises(CancelledError):
        engine.encrypt_file(sample_file, output, PASSWORD, cancel=cancel)
    assert not output.exists()


def test_cancel_during_encryption_removes_temporary(tmp_path: Path) -> None:
    engine = CryptoEngine()
    source = tmp_path / "large.bin"
    source.write_bytes(os.urandom(CHUNK_SIZE * 2 + 10))
    output = tmp_path / "cancel-mid.cvlt"
    cancel = threading.Event()

    def progress(done: int, _total: int) -> None:
        if done >= CHUNK_SIZE:
            cancel.set()

    with pytest.raises(CancelledError):
        engine.encrypt_file(source, output, PASSWORD, progress=progress, cancel=cancel)
    assert not output.exists()
    assert not list(tmp_path.glob(".cryptovault-*"))


def test_progress_is_monotonic(tmp_path: Path) -> None:
    engine = CryptoEngine()
    source = tmp_path / "progress.bin"
    source.write_bytes(os.urandom(CHUNK_SIZE + 50))
    values: list[int] = []
    engine.encrypt_file(
        source,
        tmp_path / "progress.cvlt",
        PASSWORD,
        progress=lambda done, _total: values.append(done),
    )
    assert values == sorted(values)
    assert values[-1] == source.stat().st_size


def test_inspect_invalid_header_raises(tmp_path: Path) -> None:
    engine = CryptoEngine()
    invalid = tmp_path / "invalid.cvlt"
    invalid.write_bytes(b"not a vault")
    with pytest.raises(FormatError):
        engine.inspect_file(invalid)


def test_output_directory_is_validated(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    with pytest.raises(PathSecurityError):
        engine.encrypt_file(sample_file, tmp_path / "missing" / "out.cvlt", PASSWORD)


@pytest.mark.skipif(os.name == "nt", reason="semântica de permissões POSIX")
def test_output_permissions_are_restrictive(tmp_path: Path, sample_file: Path) -> None:
    engine = CryptoEngine()
    encrypted = tmp_path / "perms.cvlt"
    _encrypt(engine, sample_file, encrypted)
    assert encrypted.stat().st_mode & 0o777 == 0o600
    decrypted = tmp_path / "perms.txt"
    engine.decrypt_file(encrypted, decrypted, PASSWORD)
    assert decrypted.stat().st_mode & 0o777 == 0o600
