from __future__ import annotations

from pathlib import Path

import pytest

from cryptovault.domain.models import OperationKind

pytestmark = pytest.mark.ui

PASSWORD = "frase-senha-de-teste-segura-2026"


def _wait_banner(qtbot, page, needle: str, timeout: int = 25_000) -> None:
    qtbot.waitUntil(
        lambda: needle in page.banner.text_label.text().casefold(),
        timeout=timeout,
    )


def test_navigation_uses_real_pages(window_harness, qtbot) -> None:
    window = window_harness.window
    assert set(window.pages) == {
        "dashboard",
        "encrypt",
        "decrypt",
        "verify",
        "history",
        "settings",
    }
    for key, page in window.pages.items():
        window.nav_buttons[key].click()
        qtbot.wait(10)
        assert window.stack.currentWidget() is page
        assert window.page_title.text()
        assert window.page_subtitle.text()


def test_password_reveal_and_auto_hide(window_harness, qtbot) -> None:
    page = window_harness.window.encrypt_page
    page.password.input.setText(PASSWORD)
    assert page.strength.bar.value() >= 0
    page.password.toggle_button.click()
    qtbot.wait(10)
    assert page.password.input.echoMode().name == "Normal"
    page.password.hide_password()
    assert page.password.input.echoMode().name == "Password"
    page.password.clear()
    assert page.password.value == ""


def test_encrypt_through_ui_updates_history_and_dashboard(
    window_harness,
    qtbot,
    sample_file: Path,
) -> None:
    harness = window_harness
    window = harness.window
    page = window.encrypt_page
    window.navigate("encrypt")
    page.add_files([str(sample_file)])
    assert page.file_list.count() == 1
    assert page.count_label.text() != "Nenhum arquivo selecionado"
    page.password.input.setText(PASSWORD)
    page.confirm_password.input.setText(PASSWORD)
    page.output_picker.set_path(str(harness.output_dir))
    page.start_button.click()

    qtbot.waitUntil(lambda: not harness.controller.busy, timeout=30_000)
    _wait_banner(qtbot, page, "sucesso")
    encrypted = harness.output_dir / "documento.txt.cvlt"
    assert encrypted.exists()
    assert page.password.value == ""
    assert page.confirm_password.value == ""
    assert page.file_list.count() == 0

    records = harness.service.list_history()
    assert records[0].kind is OperationKind.ENCRYPT
    assert records[0].outcome.value == "success"

    window.navigate("history")
    qtbot.wait(20)
    assert window.history_page.table.rowCount() == 1
    assert window.history_page.table.item(0, 2).text() == "documento.txt"


def test_decrypt_through_ui_publishes_authenticated_file(
    window_harness,
    qtbot,
    sample_file: Path,
) -> None:
    harness = window_harness
    encrypted = harness.service.encrypt_file(sample_file, PASSWORD, harness.output_dir)
    page = harness.window.decrypt_page
    harness.window.navigate("decrypt")
    page.file_picker.set_path(str(encrypted.output_path))
    qtbot.wait(10)
    assert page.header_grid_widget.isVisible()
    assert "CryptoVault v1" in page.header_values["format"].text()
    page.password.input.setText(PASSWORD)
    page.output_picker.set_path(str(harness.output_dir))
    page.start_button.click()

    qtbot.waitUntil(
        lambda: (harness.output_dir / "documento.txt").exists() and not harness.controller.busy,
        timeout=30_000,
    )
    _wait_banner(qtbot, page, "recuperado")
    restored = harness.output_dir / "documento.txt"
    assert restored.read_bytes() == sample_file.read_bytes()
    assert page.password.value == ""
    assert page.open_folder_button.isVisible()

    records = harness.service.list_history()
    assert records[0].kind is OperationKind.DECRYPT
    assert records[0].outcome.value == "success"


def test_verify_through_ui_reports_authenticated_and_tamper(
    window_harness,
    qtbot,
    sample_file: Path,
) -> None:
    harness = window_harness
    encrypted = harness.service.encrypt_file(sample_file, PASSWORD, harness.output_dir)
    page = harness.window.verify_page
    harness.window.navigate("verify")
    page.file_picker.set_path(str(encrypted.output_path))
    page.password.input.setText(PASSWORD)
    page.start_button.click()
    qtbot.waitUntil(
        lambda: page.status_label.text() == "Conteúdo autenticado",
        timeout=30_000,
    )
    assert page.banner.property("variant") == "success"
    assert page.progress.value() == 100
    assert page.password.value == ""

    tampered = harness.output_dir / "tampered.cvlt"
    data = bytearray(encrypted.output_path.read_bytes())
    data[-1] ^= 0x01
    tampered.write_bytes(bytes(data))
    page.file_picker.set_path(str(tampered))
    page.password.input.setText(PASSWORD)
    page.start_button.click()
    qtbot.waitUntil(
        lambda: page.status_label.text() == "Autenticação recusada",
        timeout=30_000,
    )
    assert "falhou" in page.banner.text_label.text().casefold()


def test_history_filters(window_harness, qtbot, sample_file: Path) -> None:
    harness = window_harness
    harness.service.encrypt_file(sample_file, PASSWORD, harness.output_dir)
    page = harness.window.history_page
    harness.window.navigate("history")
    qtbot.wait(20)
    assert page.table.rowCount() == 1

    page.operation_filter.setCurrentIndex(page.operation_filter.findData("encrypt"))
    qtbot.wait(10)
    assert page.table.rowCount() == 1
    page.result_filter.setCurrentIndex(page.result_filter.findData("failure"))
    qtbot.wait(10)
    assert page.table.rowCount() == 0
    assert "0 registro(s)" in page.count_label.text()
    assert not page.table.isVisible()

    page.clear_filters()
    qtbot.wait(10)
    assert page.table.rowCount() == 1


def test_settings_are_saved_and_applied(window_harness, qtbot, tmp_path: Path) -> None:
    harness = window_harness
    page = harness.window.settings_page
    harness.window.navigate("settings")
    page.density_combo.setCurrentIndex(page.density_combo.findData("compact"))
    page.scale_combo.setCurrentIndex(page.scale_combo.findData(125))
    page.retention_combo.setCurrentIndex(page.retention_combo.findData(365))
    page.notifications_check.setChecked(False)
    page.save_button.click()
    qtbot.waitUntil(lambda: harness.window.settings.density == "compact", timeout=5_000)
    assert harness.window.settings.font_scale == 125
    assert harness.window.settings.history_retention_days == 365
    assert harness.window.settings.notifications_enabled is False
    assert "salvas" in page.banner.text_label.text().casefold()
    assert harness.repository.load().density == "compact"

    harness.window.navigate("encrypt")
    assert harness.window.encrypt_page.drop_zone.isEnabled()


def test_busy_state_disables_operation_controls(window_harness) -> None:
    window = window_harness.window
    window._update_busy_ui(True)
    assert window.encrypt_page.start_button.isEnabled() is False
    assert window.decrypt_page.start_button.isEnabled() is False
    assert window.verify_page.start_button.isEnabled() is False
    assert window.app_status_badge.text() == "PROCESSANDO"
    window._update_busy_ui(False)
    assert window.encrypt_page.start_button.isEnabled() is True
    assert window.app_status_badge.text() == "PRONTO"
