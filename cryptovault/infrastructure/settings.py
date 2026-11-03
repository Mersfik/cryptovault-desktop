"""Configurações locais versionadas. Não há opções para reduzir parâmetros criptográficos."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from cryptovault.domain.errors import SettingsError
from cryptovault.security.paths import ensure_private_directory

SETTINGS_VERSION = 1
_VALID_DENSITIES = {"comfortable", "compact"}
_VALID_FONT_SCALES = {100, 110, 125}


def default_output_directory() -> Path:
    return Path.home() / "Documents" / "CryptoVault"


@dataclass(frozen=True, slots=True)
class Settings:
    version: int = SETTINGS_VERSION
    output_dir: str = ""
    log_dir: str = ""
    notifications_enabled: bool = True
    notify_on_success: bool = True
    notify_on_failure: bool = True
    density: str = "comfortable"
    font_scale: int = 100
    history_retention_days: int = 180

    def normalized(self, data_dir: Path) -> Settings:
        output = self.output_dir.strip() or str(default_output_directory())
        log_dir = self.log_dir.strip() or str(data_dir / "logs")
        density = self.density if self.density in _VALID_DENSITIES else "comfortable"
        scale = self.font_scale if self.font_scale in _VALID_FONT_SCALES else 100
        retention = max(30, min(int(self.history_retention_days), 3650))
        return replace(
            self,
            version=SETTINGS_VERSION,
            output_dir=output,
            log_dir=log_dir,
            density=density,
            font_scale=scale,
            history_retention_days=retention,
            notifications_enabled=bool(self.notifications_enabled),
            notify_on_success=bool(self.notify_on_success),
            notify_on_failure=bool(self.notify_on_failure),
        )


class SettingsRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = ensure_private_directory(data_dir)
        self.path = self.data_dir / "settings.json"
        self._data_dir = self.data_dir

    def load(self) -> Settings:
        if not self.path.exists():
            settings = Settings().normalized(self._data_dir)
            self.save(settings)
            return settings
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Configuração deve ser um objeto JSON.")
            if payload.get("version") != SETTINGS_VERSION:
                payload["version"] = SETTINGS_VERSION
            allowed = set(Settings.__dataclass_fields__)
            values = {key: value for key, value in payload.items() if key in allowed}
            settings = Settings(**values).normalized(self._data_dir)
            self._validate_paths(settings)
            return settings
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SettingsError("Configurações inválidas ou ilegíveis.") from exc

    def _validate_paths(self, settings: Settings) -> None:
        output = Path(settings.output_dir).expanduser()
        if output.exists() and not output.is_dir():
            raise SettingsError("Diretório de saída configurado não é um diretório.")
        log_dir = Path(settings.log_dir).expanduser()
        if log_dir.exists() and not log_dir.is_dir():
            raise SettingsError("Diretório de log configurado não é um diretório.")

    def save(self, settings: Settings) -> Settings:
        normalized = settings.normalized(self._data_dir)
        self._validate_paths(normalized)
        payload = asdict(normalized)
        temp_path: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=".settings-", suffix=".tmp", dir=self.data_dir
            )
            temp_path = Path(raw_path)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, self.path)
            temp_path = None
            return normalized
        except OSError as exc:
            raise SettingsError("Falha ao salvar as configurações.") from exc
        finally:
            if temp_path is not None:
                from contextlib import suppress

                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)

    def ensure_output_directory(self, settings: Settings) -> Path:
        try:
            return ensure_private_directory(Path(settings.output_dir).expanduser())
        except OSError as exc:
            raise SettingsError("Não foi possível criar o diretório de saída padrão.") from exc

    def ensure_log_directory(self, settings: Settings) -> Path:
        try:
            return ensure_private_directory(Path(settings.log_dir).expanduser())
        except OSError as exc:
            raise SettingsError("Não foi possível criar o diretório de logs.") from exc
