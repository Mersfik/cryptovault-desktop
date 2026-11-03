from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptovault.domain.errors import OutputExistsError, PathSecurityError
from cryptovault.security.paths import (
    AtomicOutput,
    decrypted_output_name,
    encrypted_output_name,
    sanitize_filename,
    unique_destination,
    validate_input_file,
    validate_output_directory,
)

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("../../etc/passwd", ".._.._etc_passwd"),
        ("..\\..\\Windows\\System32", ".._.._Windows_System32"),
        ("arquivo\x00.txt", "arquivo.txt"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("  nome.  ", "nome"),
        ("", "arquivo"),
        ("..", "arquivo"),
    ],
)
def test_sanitize_filename_blocks_components(value: str, expected: str) -> None:
    assert sanitize_filename(value) == expected


@given(st.text(max_size=300))
def test_sanitize_filename_has_no_separators_or_controls(value: str) -> None:
    result = sanitize_filename(value)
    assert result not in {"", ".", ".."}
    assert "/" not in result
    assert "\\" not in result
    assert "\x00" not in result
    assert len(result) <= 180


def test_output_names() -> None:
    assert encrypted_output_name("relatorio.pdf") == "relatorio.pdf.cvlt"
    assert decrypted_output_name("relatorio.pdf.cvlt") == "relatorio.pdf"
    assert decrypted_output_name("../../evil.cvlt") == "_.._evil"
    assert decrypted_output_name("sem-extensao") == "sem-extensao"


def test_unique_destination_does_not_overwrite(tmp_path: Path) -> None:
    existing = tmp_path / "arquivo.txt.cvlt"
    existing.write_text("original", encoding="utf-8")
    selected = unique_destination(tmp_path, "arquivo.txt.cvlt")
    assert selected.name == "arquivo.txt (1).cvlt"
    selected.write_text("segundo", encoding="utf-8")
    third = unique_destination(tmp_path, "arquivo.txt.cvlt")
    assert third.name == "arquivo.txt (2).cvlt"
    assert existing.read_text(encoding="utf-8") == "original"


def test_direct_symlink_input_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("dados", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("criação de link simbólico indisponível")
    with pytest.raises(PathSecurityError):
        validate_input_file(link)


def test_symlink_output_directory_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("criação de link simbólico indisponível")
    with pytest.raises(PathSecurityError):
        validate_output_directory(link)


def test_non_regular_files_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathSecurityError):
        validate_input_file(tmp_path)
    with pytest.raises(PathSecurityError):
        validate_output_directory(tmp_path / "file")
    (tmp_path / "file").write_text("x", encoding="utf-8")
    with pytest.raises(PathSecurityError):
        validate_output_directory(tmp_path / "file")


def test_atomic_output_commit_and_abort(tmp_path: Path) -> None:
    with AtomicOutput(tmp_path, sensitive=False) as output:
        output.write(b"conteudo")
        committed = output.commit(tmp_path / "final.bin")
    assert committed.read_bytes() == b"conteudo"
    assert not list(tmp_path.glob(".cryptovault-*"))

    with pytest.raises(RuntimeError):
        with AtomicOutput(tmp_path, sensitive=True) as output:
            output.write(b"temporario sensivel")
            raise RuntimeError("falha")
    assert not list(tmp_path.glob(".cryptovault-*"))


def test_atomic_output_never_overwrites(tmp_path: Path) -> None:
    destination = tmp_path / "existing.bin"
    destination.write_bytes(b"preservar")
    with pytest.raises(OutputExistsError):
        with AtomicOutput(tmp_path, sensitive=False) as output:
            output.write(b"novo")
            output.commit(destination)
    assert destination.read_bytes() == b"preservar"
    assert not list(tmp_path.glob(".cryptovault-*"))


@pytest.mark.skipif(os.name == "nt", reason="semântica de permissões POSIX")
def test_atomic_temp_permissions(tmp_path: Path) -> None:
    with AtomicOutput(tmp_path, sensitive=True) as output:
        assert output.path is not None
        mode = stat.S_IMODE(output.path.stat().st_mode)
        assert mode == 0o600
        output.abort()
