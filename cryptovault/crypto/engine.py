"""Motor criptográfico AES-256-GCM com processamento em blocos autenticados."""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections.abc import ByteString, Callable, Iterator
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cryptovault.crypto.format import (
    CHUNK_SIZE,
    DEFAULT_KDF_PARAMS,
    HEADER_SIZE,
    RECORD_LENGTH_STRUCT,
    TAG_SIZE,
    CryptoHeader,
    KdfParams,
    build_header,
    header_fingerprint,
    nonce_for,
    parse_header,
    record_aad,
)
from cryptovault.crypto.kdf import derive_key
from cryptovault.domain.errors import (
    AuthenticationError,
    CancelledError,
    FormatError,
    OutputError,
    OutputExistsError,
    PathSecurityError,
    ValidationError,
)
from cryptovault.domain.models import (
    DecryptResult,
    EncryptResult,
    HeaderInfo,
    VerificationStatus,
    VerifyResult,
)
from cryptovault.security.paths import (
    AtomicOutput,
    check_free_space,
    expected_output_capacity,
    secure_open_input,
    validate_output_directory,
)

ProgressCallback = Callable[[int, int], None]


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise CancelledError("Operação cancelada pelo usuário.")


def _read_exact(stream: object, size: int, *, what: str) -> bytes:
    data = stream.read(size)  # type: ignore[attr-defined]
    if data is None or len(data) != size:
        raise FormatError(f"Leitura incompleta: {what}.")
    return data


def _header_info(header: CryptoHeader, header_bytes: bytes) -> HeaderInfo:
    return HeaderInfo(
        version=header.version,
        algorithm_id=header.algorithm_id,
        kdf_id=1,
        kdf_log_n=header.kdf.log_n,
        kdf_r=header.kdf.r,
        kdf_p=header.kdf.p,
        salt_size=len(header.salt),
        nonce_size=len(header.nonce_prefix) + 4,
        chunk_size=header.chunk_size,
        plaintext_size=header.plaintext_size,
        header_size=len(header_bytes),
        fingerprint=header_fingerprint(header_bytes),
    )


class CryptoEngine:
    """Operações de arquivo. Não conhece Qt, histórico, configurações ou UI."""

    def __init__(self, kdf_params: KdfParams = DEFAULT_KDF_PARAMS) -> None:
        kdf_params.validate()
        self.kdf_params = kdf_params

    def inspect_file(self, source: str | Path) -> HeaderInfo:
        with secure_open_input(source) as secure:
            header_bytes = _read_exact(secure.stream, HEADER_SIZE, what="cabeçalho")
            header = parse_header(header_bytes)
            secure.assert_unchanged()
        return _header_info(header, header_bytes)

    def encrypt_file(
        self,
        source: str | Path,
        destination: str | Path,
        password: str | ByteString,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> EncryptResult:
        started = time.monotonic()
        _check_cancel(cancel)
        destination_path = Path(destination).absolute()
        output_dir = validate_output_directory(destination_path.parent)
        if destination_path.exists() or destination_path.is_symlink():
            raise OutputExistsError("O arquivo de destino já existe.")
        if destination_path.resolve(strict=False) == Path(source).resolve(strict=False):
            raise PathSecurityError("Origem e destino não podem ser o mesmo arquivo.")

        with secure_open_input(source) as secure:
            source_size = secure.initial_stat.st_size
            if source_size < 0:
                raise ValidationError("Tamanho de arquivo inválido.")
            check_free_space(
                output_dir,
                expected_output_capacity(source_size, encrypting=True),
            )
            salt = secrets.token_bytes(32)
            nonce_prefix = secrets.token_bytes(8)
            header, header_bytes = build_header(
                salt=salt,
                nonce_prefix=nonce_prefix,
                plaintext_size=source_size,
                params=self.kdf_params,
            )
            key = derive_key(password, salt, header.kdf)
            _check_cancel(cancel)

            output_path: Path | None = None
            try:
                cipher = AESGCM(key)
                with AtomicOutput(output_dir, sensitive=False) as output:
                    output.write(header_bytes)
                    index = 0
                    processed = 0
                    current = secure.stream.read(CHUNK_SIZE)
                    if progress is not None:
                        progress(0, source_size)
                    while True:
                        _check_cancel(cancel)
                        pending = secure.stream.read(CHUNK_SIZE)
                        final = not pending
                        nonce = nonce_for(nonce_prefix, index)
                        aad = record_aad(header_bytes, index, len(current), final)
                        record = cipher.encrypt(nonce, current, aad)
                        output.write(RECORD_LENGTH_STRUCT.pack(len(current)))
                        output.write(record)
                        processed += len(current)
                        if progress is not None:
                            progress(processed, source_size)
                        if final:
                            break
                        current = pending
                        index += 1
                    secure.assert_unchanged()
                    output_path = output.commit(destination_path)
            except InvalidTag as exc:  # pragma: no cover - encrypt não autentica
                raise OutputError("Falha criptográfica inesperada.") from exc
            finally:
                key = b""

            size = os.stat(output_path).st_size
            return EncryptResult(
                output_path=output_path,
                source_size=source_size,
                output_size=size,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    def decrypt_file(
        self,
        source: str | Path,
        destination: str | Path,
        password: str | ByteString,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> DecryptResult:
        started = time.monotonic()
        _check_cancel(cancel)
        destination_path = Path(destination).absolute()
        output_dir = validate_output_directory(destination_path.parent)
        if destination_path.exists() or destination_path.is_symlink():
            raise OutputExistsError("O arquivo de destino já existe.")

        with secure_open_input(source) as secure:
            source_size = secure.initial_stat.st_size
            header_bytes = _read_exact(secure.stream, HEADER_SIZE, what="cabeçalho")
            header = parse_header(header_bytes)
            check_free_space(
                output_dir,
                expected_output_capacity(header.plaintext_size, encrypting=False),
            )
            key = derive_key(password, header.salt, header.kdf)
            _check_cancel(cancel)
            output_path: Path | None = None
            try:
                with AtomicOutput(output_dir, sensitive=True) as output:
                    processed = 0
                    for chunk in self._authenticated_chunks(
                        secure,
                        header,
                        header_bytes,
                        key,
                        progress=progress,
                        cancel=cancel,
                    ):
                        output.write(chunk)
                        processed += len(chunk)
                    if processed != header.plaintext_size:  # pragma: no cover - invariante
                        raise FormatError("Tamanho recuperado não confere.")
                    secure.assert_unchanged()
                    output_path = output.commit(destination_path)
            finally:
                key = b""

            return DecryptResult(
                output_path=output_path,
                source_size=source_size,
                output_size=header.plaintext_size,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    def verify_file(
        self,
        source: str | Path,
        password: str | ByteString,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> VerifyResult:
        started = time.monotonic()
        _check_cancel(cancel)
        with secure_open_input(source) as secure:
            header_bytes = _read_exact(secure.stream, HEADER_SIZE, what="cabeçalho")
            header = parse_header(header_bytes)
            info = _header_info(header, header_bytes)
            key = derive_key(password, header.salt, header.kdf)
            _check_cancel(cancel)
            try:
                try:
                    for _chunk in self._authenticated_chunks(
                        secure,
                        header,
                        header_bytes,
                        key,
                        progress=progress,
                        cancel=cancel,
                    ):
                        pass
                except AuthenticationError:
                    return VerifyResult(
                        status=VerificationStatus.INVALID_AUTHENTICATION,
                        header=info,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        detail=(
                            "A tag de autenticação não confere. A senha pode estar "
                            "incorreta ou o arquivo pode ter sido alterado."
                        ),
                    )
                except FormatError:
                    return VerifyResult(
                        status=VerificationStatus.INVALID_FORMAT,
                        header=info,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        detail="A estrutura interna do arquivo é inválida ou foi truncada.",
                    )
                secure.assert_unchanged()
            finally:
                key = b""
        return VerifyResult(
            status=VerificationStatus.AUTHENTICATED,
            header=info,
            duration_ms=int((time.monotonic() - started) * 1000),
            detail="Todos os blocos e metadados autenticados foram validados.",
        )

    def _authenticated_chunks(
        self,
        secure: object,
        header: CryptoHeader,
        header_bytes: bytes,
        key: bytes,
        *,
        progress: ProgressCallback | None,
        cancel: threading.Event | None,
    ) -> Iterator[bytes]:
        """Gera blocos somente depois da validação da tag correspondente."""
        aesgcm = AESGCM(key)
        remaining = header.plaintext_size
        index = 0
        processed = 0
        chunk_size = header.chunk_size
        while True:
            _check_cancel(cancel)
            expected_len = min(chunk_size, remaining)
            final = remaining == expected_len
            length_raw = _read_exact(
                secure.stream,  # type: ignore[attr-defined]
                RECORD_LENGTH_STRUCT.size,
                what="tamanho do registro",
            )
            (declared_len,) = RECORD_LENGTH_STRUCT.unpack(length_raw)
            if declared_len != expected_len:
                raise FormatError("Tamanho de registro inconsistente com o cabeçalho.")
            record = _read_exact(
                secure.stream,  # type: ignore[attr-defined]
                declared_len + TAG_SIZE,
                what="registro autenticado",
            )
            nonce = nonce_for(header.nonce_prefix, index)
            aad = record_aad(header_bytes, index, declared_len, final)
            try:
                plaintext = aesgcm.decrypt(nonce, record, aad)
            except InvalidTag as exc:
                raise AuthenticationError(
                    "Tag de autenticação inválida.",
                    user_message="Senha incorreta ou arquivo adulterado/corrompido.",
                ) from exc
            remaining -= len(plaintext)
            processed += len(plaintext)
            if final:
                trailing = secure.stream.read(1)  # type: ignore[attr-defined]
                if trailing:
                    raise FormatError("Dados após o registro final não são permitidos.")
            if progress is not None:
                progress(processed, header.plaintext_size)
            yield plaintext
            if final:
                break
            index += 1
