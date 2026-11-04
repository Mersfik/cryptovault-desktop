"""Gera os arquivos ZIP de release e o manifesto SHA-256.

Uso:
    python scripts/package_release.py

Saídas em ``release/``:
    CryptoVault-Desktop-<versao>-source.zip
    CryptoVault-Desktop-<versao>-windows-x64.zip
    SHA256SUMS.txt
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptovault import __version__  # noqa: E402

RELEASE = ROOT / "release"
VERSION = __version__

_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "release",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    "__pycache__",
    "htmlcov",
    ".tox",
    ".nox",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}
_EXCLUDED_NAMES = {
    ".coverage",
    ".coverage.",
    "coverage.xml",
    "history.db",
    "history.db-wal",
    "history.db-shm",
    "settings.json",
    "cryptovault.lock",
    "Thumbs.db",
    "Desktop.ini",
    ".DS_Store",
}


def _included_source(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in _EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in _EXCLUDED_NAMES:
        return False
    if path.name.startswith(".coverage."):
        return False
    return path.suffix.lower() not in _EXCLUDED_SUFFIXES


def _add_tree(archive: zipfile.ZipFile, base: Path, arc_prefix: str = "") -> None:
    for path in sorted(base.rglob("*")):
        if not path.is_file() or not _included_source(path):
            continue
        relative = path.relative_to(ROOT)
        archive_name = f"{arc_prefix}{relative.as_posix()}"
        archive.write(path, archive_name)


def _add_file(archive: zipfile.ZipFile, path: Path, archive_name: str | None = None) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo obrigatório ausente: {path}")
    archive.write(path, archive_name or path.relative_to(ROOT).as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_source_zip() -> Path:
    destination = RELEASE / f"CryptoVault-Desktop-{VERSION}-source.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        _add_tree(archive, ROOT)
    return destination


def _write_windows_zip() -> Path:
    destination = RELEASE / f"CryptoVault-Desktop-{VERSION}-windows-x64.zip"
    required = [
        ROOT / "dist" / "CryptoVault.exe",
        ROOT / "dist" / "CryptoVault.exe.sha256",
        ROOT / "dist" / "self-test.json",
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "SECURITY.md",
        ROOT / "CRYPTOGRAPHY.md",
        ROOT / "THREAT_MODEL.md",
        ROOT / "OWASP_MAPPING.md",
        ROOT / "ARCHITECTURE.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "installer" / "install.ps1",
        ROOT / "installer" / "uninstall.ps1",
        ROOT / "installer" / "install.cmd",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Arquivos ausentes para o pacote Windows:\n" + "\n".join(missing))

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in required:
            _add_file(archive, path, path.name)
        for pattern in ("docs/screenshots/*.png", "docs/verification/*"):
            for path in sorted(ROOT.glob(pattern)):
                if path.is_file():
                    _add_file(archive, path, path.relative_to(ROOT).as_posix())
    return destination


def _setup_installers() -> list[Path]:
    """Instaladores Inno Setup ja compilados, se existirem."""
    return sorted(RELEASE.glob(f"CryptoVault-Desktop-{VERSION}-setup*.exe"))


def _write_checksums(paths: list[Path]) -> Path:
    destination = RELEASE / "SHA256SUMS.txt"
    lines = []
    for path in paths:
        lines.append(f"{_sha256(path)}  {path.name}")
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return destination


def main() -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)
    source_zip = _write_source_zip()
    windows_zip = _write_windows_zip()
    exe = ROOT / "dist" / "CryptoVault.exe"
    installers = _setup_installers()
    checksums = _write_checksums([source_zip, windows_zip, exe, *installers])

    for path in (source_zip, windows_zip, exe, *installers, checksums):
        size = path.stat().st_size
        print(f"{path.relative_to(ROOT)}  {size:,} bytes")

    print("\nSHA-256:")
    print(checksums.read_text(encoding="ascii").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
