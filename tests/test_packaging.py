"""Consistência de empacotamento: recursos visuais, versão Windows e spec."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cryptovault import __version__
from cryptovault.ui import theme

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "installer" / "version_info.txt"


def test_resource_directory_points_to_bundled_assets() -> None:
    assert theme.RESOURCE_DIR.is_dir()
    assert theme.RESOURCE_DIR.name == "resources"
    assert theme.RESOURCE_DIR.parent.name == "cryptovault"


def test_logo_assets_are_present() -> None:
    assert theme.resource_path("logo.ico").is_file()
    assert theme.resource_path("logo.svg").is_file()
    assert theme.resource_path("logo.png").is_file()


def test_application_icon_loads(qapp: QApplication) -> None:
    icon = theme.application_icon()
    assert not icon.isNull()
    assert not icon.pixmap(64, 64).isNull()


def test_windows_version_resource_matches_package_version() -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    matches = re.findall(
        r"(?:filevers|prodvers)=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)",
        text,
    )
    assert len(matches) == 2
    expected = tuple(__version__.split("."))
    for major, minor, patch, build in matches:
        assert (major, minor, patch) == expected
        assert build == "0"
    assert f'"FileVersion", "{__version__}.0"' in text
    assert f'"ProductVersion", "{__version__}"' in text


def test_spec_is_windowed_and_uses_version_resource() -> None:
    spec = (ROOT / "CryptoVault.spec").read_text(encoding="utf-8")
    assert "console=False" in spec
    assert "icon=str(ICON)" in spec
    assert "version_info.txt" in spec
    assert 'name="CryptoVault"' in spec
