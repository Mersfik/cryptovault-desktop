"""Validação de caminhos, abertura segura e publicação atômica de arquivos."""

from __future__ import annotations

import errno
import os
import shutil
import stat
import tempfile
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from cryptovault.crypto.format import HEADER_SIZE, MAX_FILE_SIZE, TAG_SIZE
from cryptovault.domain.errors import (
    InsufficientSpaceError,
    OutputError,
    OutputExistsError,
    PathSecurityError,
    SizeLimitError,
)

_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_INVALID_FILENAME_CHARS = '<>:"/\\|?*'
_FREE_SPACE_RESERVE = 16 * 1024**2
_MAX_NAME_LENGTH = 180


def _fail(message: str) -> PathSecurityError:
    return PathSecurityError(message, user_message=message)


def sanitize_filename(name: str, *, fallback: str = "arquivo") -> str:
    """Reduz a um único componente seguro, sem separadores ou caracteres de controle."""
    normalized = unicodedata.normalize("NFKC", name)
    normalized = normalized.replace("\x00", "")
    cleaned = "".join(
        "_"
        if (char in _INVALID_FILENAME_CHARS or unicodedata.category(char).startswith("C"))
        else char
        for char in normalized
    )
    cleaned = cleaned.strip().rstrip(". ")
    if cleaned in {"", ".", ".."}:
        cleaned = fallback
    if len(cleaned) > _MAX_NAME_LENGTH:
        stem = Path(cleaned).stem[: _MAX_NAME_LENGTH - 24].rstrip(". ")
        suffix = Path(cleaned).suffix[:15]
        cleaned = f"{stem}{suffix}" if stem else fallback
    if cleaned.split(".", 1)[0].casefold() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned or fallback


def validate_input_file(path: str | Path, *, max_size: int = MAX_FILE_SIZE) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = candidate.absolute()
    try:
        lst = os.lstat(candidate)
    except OSError as exc:
        raise _fail("O arquivo selecionado não existe ou não pode ser acessado.") from exc
    if stat.S_ISLNK(lst.st_mode):
        raise _fail("Links simbólicos não são aceitos como arquivos de entrada.")
    if not stat.S_ISREG(lst.st_mode):
        raise _fail("O caminho selecionado não é um arquivo regular.")
    if lst.st_size > max_size:
        raise SizeLimitError(
            f"Tamanho {lst.st_size} acima do limite {max_size}.",
            user_message="O arquivo excede o limite de tamanho suportado.",
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise _fail("Não foi possível resolver o caminho do arquivo.") from exc
    if resolved != candidate.resolve(strict=False):  # pragma: no cover - proteção extra
        raise _fail("O caminho do arquivo não pôde ser validado.")
    return resolved


def validate_output_directory(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = candidate.absolute()
    try:
        lst = os.lstat(candidate)
    except OSError as exc:
        raise _fail("O diretório de destino não existe.") from exc
    if stat.S_ISLNK(lst.st_mode):
        raise _fail("Links simbólicos não são aceitos como diretório de destino.")
    if not stat.S_ISDIR(lst.st_mode):
        raise _fail("O destino selecionado não é um diretório.")
    if not os.access(candidate, os.W_OK | os.X_OK):
        raise _fail("O diretório de destino não permite gravação.")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise _fail("Não foi possível resolver o diretório de destino.") from exc
    return resolved


def ensure_private_directory(path: str | Path) -> Path:
    """Cria diretórios da aplicação com permissão restritiva (melhor esforço no Windows)."""
    candidate = Path(path).expanduser()
    candidate.mkdir(parents=True, exist_ok=True, mode=0o700)
    with suppress(OSError):
        os.chmod(candidate, 0o700)
    return candidate.resolve()


def check_free_space(directory: Path, needed_bytes: int) -> None:
    try:
        free = shutil.disk_usage(directory).free
    except OSError as exc:
        raise OutputError("Não foi possível consultar o espaço livre.") from exc
    if needed_bytes + _FREE_SPACE_RESERVE > free:
        raise InsufficientSpaceError(
            f"Espaço insuficiente: necessário={needed_bytes}, livre={free}.",
        )


def encrypted_output_name(source_name: str) -> str:
    return sanitize_filename(f"{sanitize_filename(source_name)}.cvlt")


def decrypted_output_name(source_name: str) -> str:
    base = sanitize_filename(source_name)
    if base.casefold().endswith(".cvlt"):
        base = base[:-5]
    # Evita criar arquivos ocultos no POSIX a partir de nomes hostis.
    base = base.lstrip(". ")
    return sanitize_filename(base, fallback="arquivo_restaurado")


def unique_destination(directory: Path, filename: str, *, limit: int = 10_000) -> Path:
    safe_name = sanitize_filename(filename)
    candidate = directory / safe_name
    if not candidate.exists() and not candidate.is_symlink():
        return candidate
    suffix = candidate.suffix
    stem = candidate.name[: -len(suffix)] if suffix else candidate.name
    for index in range(1, limit + 1):
        name = f"{stem} ({index}){suffix}"
        alternative = directory / sanitize_filename(name)
        if not alternative.exists() and not alternative.is_symlink():
            return alternative
    raise OutputExistsError("Não foi possível encontrar um nome de destino livre.")


def expected_output_capacity(plaintext_size: int, *, encrypting: bool) -> int:
    if encrypting:
        chunks = max(1, (plaintext_size + 1024 * 1024 - 1) // (1024 * 1024))
        return HEADER_SIZE + plaintext_size + chunks * (4 + TAG_SIZE) + 4096
    return plaintext_size + 4096


@dataclass(slots=True)
class SecureInput:
    stream: object
    path: Path
    initial_stat: os.stat_result

    def assert_unchanged(self) -> None:
        try:
            descriptor = self.stream.fileno()  # type: ignore[attr-defined]
            current = os.fstat(descriptor)
        except (AttributeError, OSError) as exc:
            raise _fail("Não foi possível confirmar a integridade da origem.") from exc
        if current.st_size != self.initial_stat.st_size or (
            current.st_mtime_ns != self.initial_stat.st_mtime_ns
        ):
            raise PathSecurityError(
                "O arquivo de origem mudou durante a leitura.",
                user_message=(
                    "O arquivo de origem foi alterado durante a operação. A operação foi abortada."
                ),
            )


@contextmanager
def secure_open_input(path: str | Path) -> Iterator[SecureInput]:
    resolved = validate_input_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags | no_follow)
    except OSError as exc:
        raise _fail("Não foi possível abrir o arquivo de entrada com segurança.") from exc
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise _fail("O descritor aberto não aponta para um arquivo regular.")
        stream = os.fdopen(descriptor, "rb", closefd=True)
    except Exception:
        os.close(descriptor)
        raise
    secure = SecureInput(stream=stream, path=resolved, initial_stat=current)
    try:
        yield secure
    finally:
        with suppress(Exception):
            stream.close()


class AtomicOutput:
    """Arquivo temporário no destino, publicado sem sobrescrever.

    Conteúdo só se torna visível no nome final após commit bem-sucedido. Falhas
    e cancelamentos removem o temporário; conteúdo em claro é sobrescrito em
    melhor esforço antes da remoção.
    """

    def __init__(self, directory: Path, *, sensitive: bool) -> None:
        self.directory = validate_output_directory(directory)
        self.sensitive = sensitive
        self.path: Path | None = None
        self._stream: object | None = None
        self._committed = False
        self._closed = False

    def __enter__(self) -> AtomicOutput:
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=".cryptovault-",
                suffix=".part",
                dir=self.directory,
            )
            with suppress(OSError):
                os.chmod(raw_path, 0o600)
            self.path = Path(raw_path)
            self._stream = os.fdopen(descriptor, "wb")
        except OSError as exc:
            raise OutputError("Não foi possível criar o arquivo temporário.") from exc
        return self

    def write(self, data: bytes) -> None:
        if self._stream is None or self._closed:
            raise OutputError("Arquivo temporário não está disponível para escrita.")
        self._stream.write(data)  # type: ignore[attr-defined]

    def flush(self) -> None:
        if self._stream is None or self._closed:
            raise OutputError("Arquivo temporário não está disponível para escrita.")
        self._stream.flush()  # type: ignore[attr-defined]
        os.fsync(self._stream.fileno())  # type: ignore[attr-defined]

    def commit(self, destination: Path) -> Path:
        if self._stream is None or self.path is None or self._closed:
            raise OutputError("Arquivo temporário não está disponível.")
        dest = destination.absolute()
        if dest.parent.resolve(strict=False) != self.directory:
            raise OutputError("Destino fora do diretório de saída autorizado.")
        if dest.exists() or dest.is_symlink():
            raise OutputExistsError("O arquivo de destino já existe.")
        try:
            self.flush()
            self._stream.close()  # type: ignore[attr-defined]
            self._closed = True
            _publish_no_overwrite(self.path, dest)
            self._committed = True
            self.path = None
            return dest
        except FileExistsError as exc:
            raise OutputExistsError("O arquivo de destino passou a existir.") from exc
        except OSError as exc:
            raise OutputError("Falha ao publicar o arquivo de saída.") from exc
        finally:
            self._cleanup()

    def abort(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self._stream is not None and not self._closed:
            with suppress(Exception):
                self._stream.close()  # type: ignore[attr-defined]
            self._closed = True
        if self.path is not None and not self._committed:
            if self.sensitive:
                _best_effort_wipe(self.path)
            with suppress(OSError):
                self.path.unlink()
            self.path = None

    def __exit__(self, *_exc: object) -> None:
        self._cleanup()


def _publish_no_overwrite(temp: Path, destination: Path) -> None:
    if os.name == "nt":
        # No Windows, os.rename falha quando o destino já existe.
        os.rename(temp, destination)
        return
    # No POSIX, link é atômico e falha com EEXIST, evitando substituição.
    try:
        os.link(temp, destination)
    except FileExistsError:
        raise
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise FileExistsError(str(destination)) from exc
        raise
    else:
        temp.unlink()
        with suppress(OSError):
            dir_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)


def _best_effort_wipe(path: Path) -> None:
    try:
        size = path.stat().st_size
        with path.open("r+b", buffering=0) as handle:
            remaining = size
            block = b"\x00" * (1024 * 1024)
            while remaining > 0:
                written = handle.write(block[: min(len(block), remaining)])
                if not written:
                    break
                remaining -= written
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return
