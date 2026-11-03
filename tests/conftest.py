"""Fixtures compartilhadas. O ambiente offscreen é definido antes do Qt."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from cryptovault.application.service import FileOperationService
from cryptovault.crypto.engine import CryptoEngine
from cryptovault.infrastructure.history import HistoryRepository
from cryptovault.infrastructure.settings import Settings, SettingsRepository
from cryptovault.ui.controller import AppController
from cryptovault.ui.main_window import MainWindow
from cryptovault.ui.theme import apply_theme

PASSWORD = "frase-senha-de-teste-segura-2026"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


@pytest.fixture
def history(data_dir: Path) -> HistoryRepository:
    return HistoryRepository(data_dir)


@pytest.fixture
def engine() -> CryptoEngine:
    return CryptoEngine()


@pytest.fixture
def service(engine: CryptoEngine, history: HistoryRepository) -> FileOperationService:
    return FileOperationService(engine, history)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "documento.txt"
    path.write_text("conteúdo confidencial de teste\nlinha 2\n", encoding="utf-8")
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    path = tmp_path / "saida"
    path.mkdir()
    return path


@dataclass
class WindowHarness:
    window: MainWindow
    service: FileOperationService
    controller: AppController
    repository: SettingsRepository
    settings: Settings
    output_dir: Path
    data_dir: Path


@pytest.fixture
def themed_app(qapp: QApplication) -> QApplication:
    apply_theme(qapp, density="comfortable", font_scale=100)
    return qapp


@pytest.fixture
def window_harness(
    qtbot: object,
    themed_app: QApplication,
    tmp_path: Path,
    data_dir: Path,
) -> WindowHarness:
    output = tmp_path / "saida-ui"
    output.mkdir()
    repository = SettingsRepository(data_dir)
    settings = Settings(
        output_dir=str(output),
        log_dir=str(data_dir / "logs"),
        notifications_enabled=False,
        density="comfortable",
        font_scale=100,
    ).normalized(data_dir)
    repository.save(settings)
    engine = CryptoEngine()
    history = HistoryRepository(data_dir)
    service = FileOperationService(engine, history)
    controller = AppController(service)
    window = MainWindow(
        service=service,
        controller=controller,
        settings_repository=repository,
        settings=settings,
        data_dir=data_dir,
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    qtbot.wait(30)  # type: ignore[attr-defined]
    harness = WindowHarness(
        window=window,
        service=service,
        controller=controller,
        repository=repository,
        settings=settings,
        output_dir=output,
        data_dir=data_dir,
    )
    yield harness
    controller.shutdown()
    window.close()
    qtbot.wait(10)  # type: ignore[attr-defined]
