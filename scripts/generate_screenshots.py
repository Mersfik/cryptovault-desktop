"""Gera screenshots reais da interface usando operações criptográficas reais."""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from cryptovault.application.service import FileOperationService  # noqa: E402
from cryptovault.crypto.engine import CryptoEngine  # noqa: E402
from cryptovault.infrastructure.history import HistoryRepository  # noqa: E402
from cryptovault.infrastructure.logging_setup import configure_logging  # noqa: E402
from cryptovault.infrastructure.settings import Settings, SettingsRepository  # noqa: E402
from cryptovault.security.passwords import Secret  # noqa: E402
from cryptovault.ui.controller import AppController  # noqa: E402
from cryptovault.ui.main_window import MainWindow  # noqa: E402
from cryptovault.ui.theme import apply_theme  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"
PASSWORD = "frase-senha-demonstracao-2026"
WRONG_PASSWORD = "senha-incorreta-demonstracao"


def wait_until_idle(app: QApplication, controller: AppController, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while controller.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    if controller.busy:
        raise TimeoutError("Operação não terminou dentro do tempo esperado.")
    for _ in range(30):
        app.processEvents()
        time.sleep(0.01)


def capture(window: MainWindow, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        QApplication.processEvents()
    pixmap = window.grab()
    destination = SHOTS / name
    if not pixmap.save(str(destination), "PNG"):
        raise RuntimeError(f"Falha ao salvar {destination}")
    print(f"Screenshot: {destination.relative_to(ROOT)} ({pixmap.width()}x{pixmap.height()})")


def main() -> int:
    app = QApplication(sys.argv[:1])
    app.setApplicationName("CryptoVault Desktop")
    apply_theme(app, density="comfortable", font_scale=100)
    SHOTS.mkdir(parents=True, exist_ok=True)

    work = Path(os.environ.get("PUBLIC", str(ROOT.parent))) / "CryptoVaultDemo"
    if work.exists():
        shutil.rmtree(work)
    data_dir = work / "data"
    samples = work / "samples"
    output = work / "output"
    logs = work / "logs"
    for directory in (data_dir, samples, output, logs):
        directory.mkdir(parents=True, exist_ok=True)
    configure_logging(logs)

    repository = SettingsRepository(data_dir)
    settings = repository.save(
        Settings(
            output_dir=str(output),
            log_dir=str(logs),
            notifications_enabled=False,
            density="comfortable",
            font_scale=100,
        )
    )
    history = HistoryRepository(data_dir)
    service = FileOperationService(CryptoEngine(), history)
    controller = AppController(service)
    window = MainWindow(
        service=service,
        controller=controller,
        settings_repository=repository,
        settings=settings,
        data_dir=data_dir,
    )
    window.show()
    app.processEvents()

    sample_files = {
        "Contrato-assinado.pdf": b"%PDF-1.7\n" + os.urandom(384 * 1024),
        "Relatorio-financeiro-Q4.xlsx": os.urandom(512 * 1024),
        "Fotos-viagem.zip": os.urandom(768 * 1024),
    }
    paths = []
    for name, payload in sample_files.items():
        path = samples / name
        path.write_bytes(payload)
        paths.append(path)

    controller.start_encrypt(paths, Secret(PASSWORD), output)
    wait_until_idle(app, controller)
    encrypted = sorted(output.glob("*.cvlt"))
    if len(encrypted) != 3:
        raise RuntimeError(f"Esperados 3 envelopes, encontrados {len(encrypted)}")

    controller.start_decrypt([encrypted[0]], Secret(PASSWORD), output)
    wait_until_idle(app, controller)

    verify_page = window.verify_page
    window.navigate("verify")
    verify_page.file_picker.set_path(str(encrypted[0]))
    verify_page.password.input.setText(PASSWORD)
    verify_page.start_button.click()
    wait_until_idle(app, controller)
    if verify_page.status_label.text() != "Conteúdo autenticado":
        raise RuntimeError("A verificação real não resultou em conteúdo autenticado.")
    capture(window, "04-verify-authenticated.png")

    controller.start_decrypt([encrypted[0]], Secret(WRONG_PASSWORD), output)
    wait_until_idle(app, controller)

    window.navigate("dashboard")
    capture(window, "01-dashboard.png")

    encrypt_page = window.encrypt_page
    window.navigate("encrypt")
    encrypt_page.add_files([str(samples / "Relatorio-financeiro-Q4.xlsx")])
    encrypt_page.password.input.setText(PASSWORD)
    encrypt_page.confirm_password.input.setText(PASSWORD)
    encrypt_page.output_picker.set_path(str(output))
    app.processEvents()
    capture(window, "02-encrypt.png")

    decrypt_page = window.decrypt_page
    window.navigate("decrypt")
    decrypt_page.file_picker.set_path(str(encrypted[0]))
    decrypt_page.password.input.setText(PASSWORD)
    decrypt_page.output_picker.set_path(str(output))
    app.processEvents()
    capture(window, "03-decrypt.png")

    window.navigate("history")
    app.processEvents()
    capture(window, "05-history.png")

    window.navigate("settings")
    app.processEvents()
    capture(window, "06-settings.png")

    window.close()
    controller.shutdown()
    app.processEvents()
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
