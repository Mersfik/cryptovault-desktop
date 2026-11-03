from __future__ import annotations

import json
from pathlib import Path

import pytest

from cryptovault import APP_NAME, __version__
from cryptovault.app import main, resolve_data_dir, run_self_test

pytestmark = pytest.mark.integration


def test_self_test_reports_all_checks(tmp_path: Path) -> None:
    report_path = tmp_path / "self-test.json"
    assert run_self_test(report_path) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["version"] == __version__
    assert report["checks"] == {
        "encrypt": True,
        "verify_authentic": True,
        "decrypt": True,
        "tamper_rejected": True,
        "wrong_password_rejected": True,
        "no_service_residue": True,
    }
    serialized = json.dumps(report)
    assert set(report) == {"version", "python", "checks", "success"}
    assert "senha-incorreta-selftest" not in serialized
    assert "token" not in serialized.casefold()


def test_self_test_without_report_path(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_self_test() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_version_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert APP_NAME in captured.out
    assert __version__ in captured.out


def test_resolve_data_dir_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = tmp_path / "explicito"
    assert resolve_data_dir(str(explicit)) == explicit.resolve()

    monkeypatch.setenv("CRYPTOVAULT_DATA_DIR", str(tmp_path / "ambiente"))
    assert resolve_data_dir() == (tmp_path / "ambiente").resolve()

    monkeypatch.delenv("CRYPTOVAULT_DATA_DIR")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert resolve_data_dir() == tmp_path / "local" / "CryptoVault"
