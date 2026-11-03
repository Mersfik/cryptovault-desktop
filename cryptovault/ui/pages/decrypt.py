"""Tela de descriptografia autenticada."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from cryptovault.domain.errors import CryptoVaultError, safe_error_message
from cryptovault.domain.models import BatchResult, HeaderInfo
from cryptovault.security.passwords import Secret, validate_password
from cryptovault.security.paths import validate_output_directory
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import icon
from cryptovault.ui.utils import format_bytes
from cryptovault.ui.widgets import (
    Card,
    PasswordField,
    PathPicker,
    StatusBanner,
)


class DecryptPage(BasePage):
    startRequested = Signal(object, str)
    cancelRequested = Signal()
    inspectRequested = Signal(str)
    openFolderRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._output_path: Path | None = None
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._build_source_card(), 3)
        row.addWidget(self._build_action_card(), 2)
        self.content_layout.addLayout(row)
        self.add_stretch()

    def _build_source_card(self) -> Card:
        card = Card(
            "Arquivo criptografado",
            "Selecione um envelope CryptoVault (.cvlt). O cabeçalho é "
            "inspecionado antes da operação.",
        )
        self.file_picker = PathPicker(
            "Arquivo de entrada",
            mode="file",
            dialog_title="Selecionar arquivo criptografado",
            file_filter="CryptoVault (*.cvlt);;Todos os arquivos (*)",
            placeholder="Selecione um arquivo .cvlt",
        )
        self.file_picker.pathChanged.connect(self._on_path_changed)
        card.add_widget(self.file_picker)

        self.info_card = QLabel(
            "Nenhum arquivo selecionado. A inspeção do cabeçalho não executa derivação de chave."
        )
        self.info_card.setObjectName("Muted")
        self.info_card.setWordWrap(True)
        self.info_card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card.add_widget(self.info_card)

        self.header_grid_widget = QWidget()
        grid = QGridLayout(self.header_grid_widget)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        self.header_values: dict[str, QLabel] = {}
        fields = (
            ("format", "Formato"),
            ("algorithm", "Algoritmo"),
            ("kdf", "Derivação de chave"),
            ("chunk", "Bloco autenticado"),
            ("size", "Tamanho em claro"),
            ("fingerprint", "Fingerprint do cabeçalho"),
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

        warning = QLabel(
            "Um cabeçalho estruturalmente válido não comprova autenticidade. "
            "A senha correta e a tag de autenticação são necessárias para validar "
            "o conteúdo antes de liberar o arquivo final."
        )
        warning.setObjectName("Faint")
        warning.setWordWrap(True)
        card.add_widget(warning)
        return card

    def _build_action_card(self) -> Card:
        card = Card(
            "Recuperar conteúdo",
            "O arquivo de saída só é publicado após todos os blocos serem autenticados.",
        )
        self.password = PasswordField(
            "Senha de descriptografia",
            placeholder="Digite a senha usada na criptografia",
        )
        self.output_picker = PathPicker(
            "Diretório de destino",
            mode="directory",
            dialog_title="Selecionar diretório de destino",
            placeholder="Selecione onde salvar o arquivo recuperado",
        )
        self.start_button = QPushButton("Descriptografar")
        self.start_button.setProperty("variant", "primary")
        self.start_button.setIcon(icon("decrypt.svg"))
        self.start_button.setMinimumHeight(40)
        self.start_button.setToolTip("Validar autenticação e recuperar o arquivo")
        self.start_button.clicked.connect(self._request_start)
        self.cancel_button = QPushButton("Cancelar operação")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancelRequested)
        self.open_folder_button = QPushButton("Abrir pasta de destino")
        self.open_folder_button.setProperty("variant", "ghost")
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._open_folder)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setAccessibleName("Progresso da descriptografia")
        self.banner = StatusBanner()
        note = QLabel(
            "Arquivos adulterados, corrompidos ou com senha incorreta são "
            "rejeitados. Nenhum arquivo final é publicado nesses casos."
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)
        card.add_widget(self.password)
        card.add_widget(self.output_picker)
        card.add_widget(self.progress)
        card.add_layout(buttons)
        card.add_widget(self.open_folder_button)
        card.add_widget(self.banner)
        card.add_widget(note)
        return card

    def set_default_output_dir(self, path: str | Path) -> None:
        if not self.output_picker.path:
            self.output_picker.set_path(path)
            self.output_picker.set_start_dir(path)

    def _on_path_changed(self, path: str) -> None:
        self.banner.clear()
        self.open_folder_button.setVisible(False)
        self.header_grid_widget.setVisible(False)
        self.info_card.setText("Inspecionando cabeçalho…")
        if path:
            self.inspectRequested.emit(path)
        else:
            self.info_card.setText("Nenhum arquivo selecionado.")

    def show_header_info(self, info: HeaderInfo) -> None:
        self.info_card.setText(
            "Cabeçalho estruturalmente válido. A autenticidade ainda não foi verificada."
        )
        self.header_values["format"].setText(f"CryptoVault v{info.version}")
        self.header_values["algorithm"].setText(f"{info.algorithm_label} · tag de {128} bits")
        self.header_values["kdf"].setText(
            f"{info.kdf_label} · N=2^{info.kdf_log_n}, r={info.kdf_r}, p={info.kdf_p}"
        )
        self.header_values["chunk"].setText(
            f"{format_bytes(info.chunk_size)} · {info.chunk_count} bloco(s)"
        )
        self.header_values["size"].setText(format_bytes(info.plaintext_size))
        self.header_values["fingerprint"].setText(info.fingerprint)
        self.header_grid_widget.setVisible(True)

    def show_inspect_error(self, message: str) -> None:
        self.header_grid_widget.setVisible(False)
        self.info_card.setText(f"Cabeçalho inválido: {message}")
        self.banner.show_message(
            "O arquivo selecionado não parece ser um envelope CryptoVault válido.",
            "warning",
        )

    def _request_start(self) -> None:
        if self._busy:
            return
        if not self.file_picker.path:
            self.banner.show_message("Selecione o arquivo criptografado.", "warning")
            return
        if not self.password.value:
            self.banner.show_message("Informe a senha de descriptografia.", "warning")
            self.password.focus_input()
            return
        try:
            validate_password(self.password.value)
            output_dir = validate_output_directory(self.output_picker.path)
        except CryptoVaultError as exc:
            self.banner.show_message(safe_error_message(exc), "error")
            return
        self.startRequested.emit([Path(self.file_picker.path)], str(output_dir))

    def take_password(self) -> Secret:
        secret = Secret.from_text(self.password.value)
        self.password.clear()
        return secret

    def prepare_start(self) -> None:
        self.progress.setValue(0)
        self.banner.clear()
        self.open_folder_button.setVisible(False)
        self._output_path = None

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.file_picker.setEnabled(not busy)
        self.password.setEnabled(not busy)
        self.output_picker.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        if busy:
            self.progress.setValue(0)
            self.banner.show_message(
                "Validando autenticação em segundo plano. A interface permanece responsiva.",
                "processing",
            )

    def update_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(max(0, min(percent, 100)))
        if message:
            self.banner.show_message(message, "processing")

    def set_result(self, result: BatchResult) -> None:
        self.cancel_button.setVisible(False)
        if result.cancelled:
            self.banner.show_message(
                "Descriptografia cancelada. Nenhum arquivo final foi publicado.",
                "warning",
            )
            return
        if not result.items:
            self.banner.show_message("Nenhum arquivo foi processado.", "warning")
            return
        item = result.items[0]
        if item.success and item.output_path is not None:
            self._output_path = item.output_path
            self.progress.setValue(100)
            self.banner.show_message(
                f"Arquivo autenticado e recuperado: {item.output_path.name} "
                f"({format_bytes(item.size_bytes)}).",
                "success",
            )
            self.open_folder_button.setVisible(True)
        else:
            self.open_folder_button.setVisible(False)
            self.banner.show_message(item.message, "error")
        self.password.clear()

    def _open_folder(self) -> None:
        if self._output_path is not None:
            self.openFolderRequested.emit(str(self._output_path.parent))

    def trigger_shortcut(self) -> None:
        self.file_picker.button.click()

    def clear_selection(self) -> None:
        self.file_picker.clear()
        self.header_grid_widget.setVisible(False)
        self.info_card.setText("Nenhum arquivo selecionado.")
