"""Tela de verificação de formato, integridade e autenticidade."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from cryptovault.domain.errors import CryptoVaultError, safe_error_message
from cryptovault.domain.models import (
    BatchResult,
    HeaderInfo,
    VerificationStatus,
)
from cryptovault.security.passwords import Secret, validate_password
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import COLORS, icon
from cryptovault.ui.utils import format_bytes
from cryptovault.ui.widgets import Card, PasswordField, PathPicker, StatusBanner


class VerifyPage(BasePage):
    startRequested = Signal(object)
    cancelRequested = Signal()
    inspectRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._build_input_card(), 3)
        row.addWidget(self._build_result_card(), 2)
        self.content_layout.addLayout(row)
        self.add_stretch()

    def _build_input_card(self) -> Card:
        card = Card(
            "Arquivo e senha",
            "A verificação completa exige a senha e valida cada tag de autenticação.",
        )
        self.file_picker = PathPicker(
            "Arquivo criptografado",
            mode="file",
            dialog_title="Selecionar arquivo para verificar",
            file_filter="CryptoVault (*.cvlt);;Todos os arquivos (*)",
            placeholder="Selecione um arquivo .cvlt",
        )
        self.file_picker.pathChanged.connect(self._on_path_changed)
        self.password = PasswordField(
            "Senha",
            placeholder="Digite a senha usada na criptografia",
        )
        self.start_button = QPushButton("Verificar integridade e autenticidade")
        self.start_button.setProperty("variant", "primary")
        self.start_button.setIcon(icon("verify.svg"))
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._request_start)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancelRequested)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.banner = StatusBanner()
        note = QLabel(
            "A aplicação não declara um arquivo 'seguro' apenas porque o "
            "cabeçalho é válido. Autenticação bem-sucedida indica que os dados "
            "conferem com a senha e não foram alterados de forma detectável."
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)
        card.add_widget(self.file_picker)
        card.add_widget(self.password)
        card.add_widget(self.progress)
        card.add_layout(buttons)
        card.add_widget(self.banner)
        card.add_widget(note)
        return card

    def _build_result_card(self) -> Card:
        card = Card("Resultado da validação", "Metadados públicos do envelope.")
        self.status_label = QLabel("Aguardando verificação")
        self.status_label.setObjectName("CardTitle")
        self.status_label.setWordWrap(True)
        self.detail_label = QLabel("Selecione um arquivo, informe a senha e execute a verificação.")
        self.detail_label.setObjectName("Muted")
        self.detail_label.setWordWrap(True)
        card.add_widget(self.status_label)
        card.add_widget(self.detail_label)

        self.header_grid_widget = QWidget()
        grid = QGridLayout(self.header_grid_widget)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)
        self.header_values: dict[str, QLabel] = {}
        fields = (
            ("format", "Formato"),
            ("algorithm", "Algoritmo"),
            ("kdf", "KDF"),
            ("nonce", "Nonce / salt"),
            ("chunk", "Blocos"),
            ("size", "Tamanho em claro"),
            ("fingerprint", "Fingerprint"),
        )
        for index, (key, label) in enumerate(fields):
            key_label = QLabel(label)
            key_label.setObjectName("Faint")
            value_label = QLabel("—")
            value_label.setObjectName("Mono")
            value_label.setWordWrap(True)
            grid.addWidget(key_label, index, 0)
            grid.addWidget(value_label, index, 1)
            self.header_values[key] = value_label
        grid.setColumnStretch(1, 1)
        self.header_grid_widget.setVisible(False)
        card.add_widget(self.header_grid_widget)

        self.interpretation = QLabel(
            "Autenticação não identifica autoria nem garante que o arquivo "
            "esteja livre de malware. Ela comprova posse da senha e integridade "
            "do conteúdo em relação à tag GCM."
        )
        self.interpretation.setObjectName("Faint")
        self.interpretation.setWordWrap(True)
        card.add_widget(self.interpretation)
        return card

    def _on_path_changed(self, path: str) -> None:
        self.banner.clear()
        self.header_grid_widget.setVisible(False)
        self.status_label.setText("Inspecionando cabeçalho…")
        self.status_label.setStyleSheet("")
        self.detail_label.setText(
            "A inspeção valida apenas estrutura, versão e limites de parâmetros."
        )
        if path:
            self.inspectRequested.emit(path)
        else:
            self.status_label.setText("Aguardando verificação")

    def show_header_info(self, info: HeaderInfo) -> None:
        self.header_values["format"].setText(f"CryptoVault v{info.version}")
        self.header_values["algorithm"].setText(f"{info.algorithm_label} · 256 bits")
        self.header_values["kdf"].setText(
            f"{info.kdf_label} · N=2^{info.kdf_log_n}, r={info.kdf_r}, p={info.kdf_p}"
        )
        self.header_values["nonce"].setText(
            f"nonce {info.nonce_size} bytes · salt {info.salt_size} bytes"
        )
        self.header_values["chunk"].setText(
            f"{info.chunk_count} bloco(s) de {format_bytes(info.chunk_size)}"
        )
        self.header_values["size"].setText(format_bytes(info.plaintext_size))
        self.header_values["fingerprint"].setText(info.fingerprint)
        self.header_grid_widget.setVisible(True)
        if not self._busy:
            self.status_label.setText("Cabeçalho válido; autenticidade não verificada")
            self.status_label.setStyleSheet(f"color: {COLORS['blue']};")
            self.detail_label.setText(
                "A senha é necessária para validar a tag de autenticação do conteúdo."
            )

    def show_inspect_error(self, message: str) -> None:
        self.header_grid_widget.setVisible(False)
        self.status_label.setText("Formato inválido")
        self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
        self.detail_label.setText(message)
        self.banner.show_message(
            "O arquivo não passou na validação estrutural do formato.", "error"
        )

    def _request_start(self) -> None:
        if self._busy:
            return
        if not self.file_picker.path:
            self.banner.show_message("Selecione um arquivo criptografado.", "warning")
            return
        if not self.password.value:
            self.banner.show_message("Informe a senha para verificar a autenticidade.", "warning")
            self.password.focus_input()
            return
        try:
            validate_password(self.password.value)
        except CryptoVaultError as exc:
            self.banner.show_message(safe_error_message(exc), "error")
            return
        self.startRequested.emit([Path(self.file_picker.path)])

    def take_password(self) -> Secret:
        secret = Secret.from_text(self.password.value)
        self.password.clear()
        return secret

    def prepare_start(self) -> None:
        self.progress.setValue(0)
        self.banner.clear()
        self.status_label.setText("Verificando…")
        self.status_label.setStyleSheet(f"color: {COLORS['processing']};")
        self.detail_label.setText(
            "Derivando a chave e validando os blocos autenticados em segundo plano."
        )

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.file_picker.setEnabled(not busy)
        self.password.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        if busy:
            self.progress.setValue(0)
            self.banner.show_message("Verificação em andamento…", "processing")

    def update_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(max(0, min(percent, 100)))
        if message:
            self.banner.show_message(message, "processing")

    def set_result(self, result: BatchResult) -> None:
        self.cancel_button.setVisible(False)
        if result.cancelled:
            self.status_label.setText("Verificação cancelada")
            self.status_label.setStyleSheet(f"color: {COLORS['warning']};")
            self.detail_label.setText("Nenhuma conclusão de autenticidade foi emitida.")
            self.banner.show_message("Verificação cancelada.", "warning")
            return
        if not result.items:
            self.banner.show_message("Nenhum arquivo processado.", "warning")
            return
        item = result.items[0]
        status = item.verification_status
        if status is VerificationStatus.AUTHENTICATED:
            self.progress.setValue(100)
            self.status_label.setText("Conteúdo autenticado")
            self.status_label.setStyleSheet(f"color: {COLORS['success']};")
            self.detail_label.setText(
                "A senha está correta e todas as tags GCM, o cabeçalho e a "
                "estrutura dos blocos foram validados."
            )
            self.banner.show_message(
                "Autenticidade e integridade verificadas. O conteúdo não foi extraído para disco.",
                "success",
            )
        elif status is VerificationStatus.INVALID_AUTHENTICATION:
            self.progress.setValue(100)
            self.status_label.setText("Autenticação recusada")
            self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
            self.detail_label.setText(
                "Senha incorreta ou arquivo adulterado/corrompido. O GCM não "
                "permite distinguir essas causas com segurança."
            )
            self.banner.show_message(
                "A autenticação falhou. Nenhuma garantia de integridade pode ser emitida.",
                "error",
            )
        else:
            self.progress.setValue(100)
            self.status_label.setText("Formato ou conteúdo inválido")
            self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
            self.detail_label.setText(item.message)
            self.banner.show_message(item.message, "error")
        self.password.clear()

    def trigger_shortcut(self) -> None:
        self.file_picker.button.click()
