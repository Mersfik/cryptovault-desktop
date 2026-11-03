from __future__ import annotations

import json
from pathlib import Path

import pytest

from cryptovault.domain.errors import SettingsError
from cryptovault.infrastructure.settings import (
    SETTINGS_VERSION,
    Settings,
    SettingsRepository,
    default_output_directory,
)

pytestmark = pytest.mark.integration


def test_defaults_are_persisted_on_first_load(data_dir: Path) -> None:
    repository = SettingsRepository(data_dir)
    settings = repository.load()
    assert settings.version == SETTINGS_VERSION
    assert settings.output_dir == str(default_output_directory())
    assert settings.log_dir == str(data_dir / "logs")
    assert settings.notifications_enabled is True
    assert settings.density == "comfortable"
    assert settings.font_scale == 100
    assert settings.history_retention_days == 180
    assert repository.path.exists()
    payload = json.loads(repository.path.read_text(encoding="utf-8"))
    assert payload["version"] == SETTINGS_VERSION
    assert "password" not in payload
    assert "kdf" not in payload


def test_roundtrip_preserves_preferences(data_dir: Path, tmp_path: Path) -> None:
    repository = SettingsRepository(data_dir)
    output = tmp_path / "output"
    output.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    candidate = Settings(
        output_dir=str(output),
        log_dir=str(logs),
        notifications_enabled=False,
        notify_on_success=False,
        notify_on_failure=True,
        density="compact",
        font_scale=125,
        history_retention_days=365,
    )
    saved = repository.save(candidate)
    loaded = repository.load()
    assert saved == loaded
    assert loaded.output_dir == str(output)
    assert loaded.log_dir == str(logs)
    assert loaded.density == "compact"
    assert loaded.font_scale == 125
    assert loaded.history_retention_days == 365
    assert loaded.notifications_enabled is False
    assert not list(data_dir.glob(".settings-*"))


def test_invalid_values_are_normalized(data_dir: Path) -> None:
    repository = SettingsRepository(data_dir)
    normalized = repository.save(
        Settings(
            density="gigante",
            font_scale=999,
            history_retention_days=1,
            output_dir="   ",
            log_dir="   ",
        )
    )
    assert normalized.density == "comfortable"
    assert normalized.font_scale == 100
    assert normalized.history_retention_days == 30
    assert normalized.output_dir == str(default_output_directory())
    assert normalized.log_dir == str(data_dir / "logs")

    too_long = repository.save(Settings(history_retention_days=99_999))
    assert too_long.history_retention_days == 3650


def test_unknown_keys_are_ignored_and_version_is_migrated(data_dir: Path) -> None:
    repository = SettingsRepository(data_dir)
    repository.path.write_text(
        json.dumps(
            {
                "version": 99,
                "density": "compact",
                "campo_desconhecido": "ignorado",
                "kdf_log_n": 1,
            }
        ),
        encoding="utf-8",
    )
    settings = repository.load()
    assert settings.version == SETTINGS_VERSION
    assert settings.density == "compact"


def test_invalid_json_raises_settings_error(data_dir: Path) -> None:
    repository = SettingsRepository(data_dir)
    repository.path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SettingsError):
        repository.load()

    repository.path.write_text("[]", encoding="utf-8")
    with pytest.raises(SettingsError):
        repository.load()


def test_file_instead_of_directory_is_rejected(data_dir: Path, tmp_path: Path) -> None:
    repository = SettingsRepository(data_dir)
    regular_file = tmp_path / "arquivo.txt"
    regular_file.write_text("x", encoding="utf-8")
    with pytest.raises(SettingsError):
        repository.save(Settings(output_dir=str(regular_file)))
    with pytest.raises(SettingsError):
        repository.save(Settings(log_dir=str(regular_file)))


def test_ensure_directories(data_dir: Path, tmp_path: Path) -> None:
    repository = SettingsRepository(data_dir)
    output = tmp_path / "novo" / "output"
    logs = tmp_path / "novo" / "logs"
    settings = Settings(output_dir=str(output), log_dir=str(logs))
    assert repository.ensure_output_directory(settings) == output.resolve()
    assert repository.ensure_log_directory(settings) == logs.resolve()
    assert output.is_dir()
    assert logs.is_dir()
