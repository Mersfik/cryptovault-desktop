"""Tela de configurações locais, sem controles que reduzam segurança criptográfica."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from cryptovault import __version__
from cryptovault.domain.errors import CryptoVaultError, safe_error_message
from cryptovault.infrastructure.settings import Settings
from cryptovault.security.paths import validate_output_directory
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import icon
from cryptovault.ui.widgets import Card, PathPicker, StatusBanner, horizontal_rule


class SettingsPage(BasePage):
    saveRequested = Signal(object)
    openPathRequested = Signal(str)

    def __init__(self, data_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self._settings = Settings()
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._build_paths_card(), 1)
        row.addWidget(self._build_preferences_card(), 1)
        self.content_layout.addLayout(row)
        self.content_layout.addWidget(self._build_security_card())
        self.add_stretch()

    def _build_paths_card(self) -> Card:
        card = Card(
            "Pastas e dados",
            "Arquivos de saída e logs permanecem no computador local.",
        )
        self.output_picker = PathPicker(
            "Diretório padrão de saída",
            mode="directory",
            dialog_title="Selecionar diretório padrão de saída",
            placeholder="Diretório para novos arquivos",
        )
        self.log_picker = PathPicker(
            "Diretório dos logs",
            mode="directory",
            dialog_title="Selecionar diretório de logs",
            placeholder="Diretório dos logs estruturados",
        )
        log_note = QLabel(
            "A alteração do diretório de logs passa a valer após reiniciar a aplicação. "
            "Logs são rotativos (até 5 arquivos de 2 MB) e não contêm segredos."
        )
        log_note.setObjectName("Faint")
        log_note.setWordWrap(True)
        self.open_log_button = QPushButton("Abrir pasta de logs")
        self.open_log_button.clicked.connect(self._open_logs)
        data_label = QLabel(f"Dados da aplicação: {self.data_dir}")
        data_label.setObjectName("Mono")
        data_label.setWordWrap(True)
        data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card.add_widget(self.output_picker)
        card.add_widget(self.log_picker)
        card.add_widget(log_note)
        card.add_widget(self.open_log_button)
        card.add_widget(horizontal_rule())
        card.add_widget(data_label)
        return card

    def _build_preferences_card(self) -> Card:
        card = Card(
            "Interface e notificações",
            "Preferências visuais e de feedback; não alteram parâmetros criptográficos.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        density_label = QLabel("Densidade da interface")
        density_label.setObjectName("FieldLabel")
        self.density_combo = QComboBox()
        self.density_combo.addItem("Confortável", "comfortable")
        self.density_combo.addItem("Compacta", "compact")
        scale_label = QLabel("Escala da fonte")
        scale_label.setObjectName("FieldLabel")
        self.scale_combo = QComboBox()
        for value in (100, 110, 125):
            self.scale_combo.addItem(f"{value}%", value)
        retention_label = QLabel("Retenção do histórico")
        retention_label.setObjectName("FieldLabel")
        self.retention_combo = QComboBox()
        for days in (90, 180, 365):
            self.retention_combo.addItem(f"{days} dias", days)
        grid.addWidget(density_label, 0, 0)
        grid.addWidget(self.density_combo, 0, 1)
        grid.addWidget(scale_label, 1, 0)
        grid.addWidget(self.scale_combo, 1, 1)
        grid.addWidget(retention_label, 2, 0)
        grid.addWidget(self.retention_combo, 2, 1)
        grid.setColumnStretch(1, 1)
        card.add_layout(grid)

        self.notifications_check = QCheckBox("Ativar notificações de conclusão")
        self.notify_success_check = QCheckBox("Notificar sucessos")
        self.notify_failure_check = QCheckBox("Notificar falhas e cancelamentos")
        self.notifications_check.toggled.connect(self._toggle_notification_options)
        card.add_widget(self.notifications_check)
        card.add_widget(self.notify_success_check)
        card.add_widget(self.notify_failure_check)
        note = QLabel(
            "Se o ambiente não oferecer bandeja do sistema, o resultado continua "
            "visível na própria janela."
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)
        card.add_widget(note)

        actions = QHBoxLayout()
        self.save_button = QPushButton("Salvar configurações")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setIcon(icon("settings.svg"))
        self.save_button.clicked.connect(self._save)
        self.reload_button = QPushButton("Recarregar")
        self.reload_button.setProperty("variant", "ghost")
        self.reload_button.clicked.connect(lambda: self.set_settings(self._settings))
        actions.addWidget(self.save_button)
        actions.addWidget(self.reload_button)
        actions.addStretch(1)
        card.add_layout(actions)
        self.banner = StatusBanner()
        card.add_widget(self.banner)
        return card

    def _build_security_card(self) -> Card:
        card = Card(
            "Segurança criptográfica",
            "Parâmetros fixos e versionados. A interface não oferece redução silenciosa.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        rows = (
            ("Criptografia", "AES-256-GCM (chave de 256 bits, tag de 128 bits)"),
            ("Nonce", "96 bits, prefixo aleatório + contador por bloco"),
            ("Derivação de chave", "Scrypt com mínimo de N=2¹⁵, r=8, p=1"),
            ("Formato", "CryptoVault v1, cabeçalho versionado e autenticado por AAD"),
            ("Senhas e chaves", "Não armazenadas; retenção apenas em memória durante a operação"),
            ("Versão da aplicação", __version__),
        )
        for index, (label, value) in enumerate(rows):
            key_label = QLabel(label)
            key_label.setObjectName("Faint")
            value_label = QLabel(value)
            value_label.setObjectName("Muted")
            value_label.setWordWrap(True)
            grid.addWidget(key_label, index, 0)
            grid.addWidget(value_label, index, 1)
        grid.setColumnStretch(1, 1)
        card.add_layout(grid)
        warning = QLabel(
            "Nenhuma configuração desta tela reduz o custo do KDF, o tamanho do "
            "nonce/tag ou permite algoritmos legados."
        )
        warning.setObjectName("Faint")
        warning.setWordWrap(True)
        card.add_widget(warning)
        return card

    def set_settings(self, settings: Settings) -> None:
        self._settings = settings
        self.output_picker.set_path(settings.output_dir)
        self.log_picker.set_path(settings.log_dir)
        self.notifications_check.setChecked(settings.notifications_enabled)
        self.notify_success_check.setChecked(settings.notify_on_success)
        self.notify_failure_check.setChecked(settings.notify_on_failure)
        self._set_combo_data(self.density_combo, settings.density)
        self._set_combo_data(self.scale_combo, settings.font_scale)
        self._set_combo_data(self.retention_combo, settings.history_retention_days)
        self._toggle_notification_options(settings.notifications_enabled)
        self.banner.clear()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _toggle_notification_options(self, enabled: bool) -> None:
        self.notify_success_check.setEnabled(enabled)
        self.notify_failure_check.setEnabled(enabled)

    def _open_logs(self) -> None:
        if self.log_picker.path:
            self.openPathRequested.emit(self.log_picker.path)

    def _save(self) -> None:
        if not self.output_picker.path:
            self.banner.show_message("Selecione o diretório padrão de saída.", "warning")
            return
        if not self.log_picker.path:
            self.banner.show_message("Selecione o diretório de logs.", "warning")
            return
        try:
            validate_output_directory(self.output_picker.path)
        except CryptoVaultError as exc:
            self.banner.show_message(safe_error_message(exc), "error")
            return
        log_path = Path(self.log_picker.path)
        if log_path.exists() and not log_path.is_dir():
            self.banner.show_message("O caminho de logs não é um diretório.", "error")
            return
        settings = Settings(
            output_dir=self.output_picker.path,
            log_dir=self.log_picker.path,
            notifications_enabled=self.notifications_check.isChecked(),
            notify_on_success=self.notify_success_check.isChecked(),
            notify_on_failure=self.notify_failure_check.isChecked(),
            density=str(self.density_combo.currentData()),
            font_scale=int(self.scale_combo.currentData()),
            history_retention_days=int(self.retention_combo.currentData()),
        )
        self.saveRequested.emit(settings)

    def show_saved(self, settings: Settings, *, log_changed: bool) -> None:
        self._settings = settings
        self.banner.show_message(
            "Configurações salvas."
            + (" O novo diretório de logs será usado após reiniciar." if log_changed else ""),
            "success",
        )

    def show_error(self, message: str) -> None:
        self.banner.show_message(message, "error")
