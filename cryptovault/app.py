"""Bootstrap do CryptoVault Desktop, teste interno e execução da interface."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

from cryptovault import APP_NAME, APP_ORGANIZATION, __version__
from cryptovault.application.service import FileOperationService
from cryptovault.crypto.engine import CryptoEngine
from cryptovault.domain.errors import SettingsError
from cryptovault.domain.models import VerificationStatus
from cryptovault.infrastructure.history import HistoryRepository
from cryptovault.infrastructure.logging_setup import configure_logging, get_logger
from cryptovault.infrastructure.settings import Settings, SettingsRepository
from cryptovault.security.paths import ensure_private_directory


def resolve_data_dir(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    environment = os.environ.get("CRYPTOVAULT_DATA_DIR")
    if environment:
        return Path(environment).expanduser().resolve()
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "CryptoVault"
    return Path.home() / ".local" / "share" / "CryptoVault"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptovault", description=APP_NAME)
    parser.add_argument("--data-dir", help="Diretório de dados local da aplicação")
    parser.add_argument("--version", action="store_true", help="Exibir versão e sair")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Executar teste criptográfico interno sem abrir a interface",
    )
    parser.add_argument(
        "--report",
        help="Arquivo JSON de resultado para --self-test",
    )
    return parser


def run_self_test(report_path: str | Path | None = None) -> int:
    """Teste de fumaça para o executável empacotado; não usa dados do usuário."""
    report: dict[str, object] = {
        "version": __version__,
        "python": sys.version.split()[0],
        "checks": {},
        "success": False,
    }
    checks: dict[str, bool] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="cryptovault-selftest-") as raw:
            root = Path(raw)
            source = root / "sample.bin"
            payload = os.urandom(2 * 1024 * 1024 + 317)
            source.write_bytes(payload)
            history = HistoryRepository(root / "data")
            service = FileOperationService(CryptoEngine(), history)
            password = secrets.token_urlsafe(24)
            encrypted = service.encrypt_file(source, password, root)
            checks["encrypt"] = encrypted.output_path.exists()
            verify = service.verify_file(encrypted.output_path, password)
            checks["verify_authentic"] = verify.status is VerificationStatus.AUTHENTICATED
            decrypted = service.decrypt_file(encrypted.output_path, password, root)
            checks["decrypt"] = decrypted.output_path.read_bytes() == payload
            tampered = root / "tampered.cvlt"
            data = bytearray(encrypted.output_path.read_bytes())
            data[-1] ^= 0x01
            tampered.write_bytes(bytes(data))
            tampered_result = service.verify_file(tampered, password)
            checks["tamper_rejected"] = (
                tampered_result.status is VerificationStatus.INVALID_AUTHENTICATION
            )
            wrong = service.verify_file(encrypted.output_path, "senha-incorreta-selftest")
            checks["wrong_password_rejected"] = (
                wrong.status is VerificationStatus.INVALID_AUTHENTICATION
            )
            checks["no_service_residue"] = not list(root.glob(".cryptovault-*"))
        report["checks"] = checks
        report["success"] = all(checks.values())
    except Exception as exc:  # pragma: no cover - caminho de falha do executável
        report["error"] = f"{type(exc).__name__}: {exc}"
    if report_path:
        try:
            destination = Path(report_path).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return 1
    return 0 if report.get("success") else 1


def _load_settings(repository: SettingsRepository, data_dir: Path) -> Settings:
    try:
        settings = repository.load()
    except SettingsError:
        settings = Settings().normalized(data_dir)
        with suppress(SettingsError):
            repository.save(settings)
    try:
        repository.ensure_output_directory(settings)
    except SettingsError:
        settings = Settings(
            output_dir=str(data_dir / "output"),
            log_dir=settings.log_dir,
            notifications_enabled=settings.notifications_enabled,
            notify_on_success=settings.notify_on_success,
            notify_on_failure=settings.notify_on_failure,
            density=settings.density,
            font_scale=settings.font_scale,
            history_retention_days=settings.history_retention_days,
        ).normalized(data_dir)
        with suppress(SettingsError):
            repository.ensure_output_directory(settings)
            repository.save(settings)
    with suppress(SettingsError):
        repository.ensure_log_directory(settings)
    return settings


def main(argv: list[str] | None = None) -> int:
    args, _unknown = _parser().parse_known_args(argv)
    if args.version:
        print(f"{APP_NAME} {__version__}")  # noqa: T201
        return 0
    if args.self_test:
        return run_self_test(args.report)

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    from cryptovault.ui.controller import AppController
    from cryptovault.ui.main_window import MainWindow
    from cryptovault.ui.theme import application_icon, apply_theme

    data_dir = resolve_data_dir(args.data_dir)
    try:
        ensure_private_directory(data_dir)
    except OSError:
        return 3

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(application_icon())

    lock = QLockFile(str(data_dir / "cryptovault.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.warning(
            None,
            APP_NAME,
            "O CryptoVault já está em execução para este usuário.",
        )
        return 2

    settings_repository = SettingsRepository(data_dir)
    settings = _load_settings(settings_repository, data_dir)
    try:
        log_path = configure_logging(Path(settings.log_dir))
    except OSError:
        log_path = configure_logging(data_dir / "logs")
    logger = get_logger()
    logger.info(
        "application_started",
        extra={"event": "application_started", "version": __version__},
    )

    try:
        history = HistoryRepository(data_dir)
        service = FileOperationService(CryptoEngine(), history)
        controller = AppController(service)
        try:
            history.purge_older_than(settings.history_retention_days)
        except Exception:
            logger.warning(
                "history_retention_failed",
                extra={"event": "history_retention_failed"},
            )
        apply_theme(
            app,
            density=settings.density,
            font_scale=settings.font_scale,
        )
        window = MainWindow(
            service=service,
            controller=controller,
            settings_repository=settings_repository,
            settings=settings,
            data_dir=data_dir,
        )
        window.show()
        exit_code = app.exec()
        logger.info(
            "application_stopped",
            extra={"event": "application_stopped", "component": "ui"},
        )
        return int(exit_code)
    except Exception:
        logger.exception(
            "fatal_startup_error",
            extra={"event": "fatal_startup_error"},
        )
        QMessageBox.critical(
            None,
            APP_NAME,
            "Não foi possível iniciar a aplicação. Consulte o log local.",
        )
        return 4
    finally:
        lock.unlock()
        _ = log_path


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
