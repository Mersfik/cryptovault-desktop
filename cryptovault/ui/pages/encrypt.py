"""Tela de criptografia de arquivos."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QWidget,
)

from cryptovault.domain.errors import CryptoVaultError, safe_error_message
from cryptovault.domain.models import BatchResult
from cryptovault.security.passwords import Secret, validate_password
from cryptovault.security.paths import validate_input_file, validate_output_directory
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import icon
from cryptovault.ui.utils import format_bytes
from cryptovault.ui.widgets import (
    Card,
    DropZone,
    PasswordField,
    PasswordStrengthMeter,
    PathPicker,
    StatusBanner,
    format_file_item,
)

MAX_SELECTED_FILES = 500


class EncryptPage(BasePage):
    startRequested = Signal(object, str)
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paths: list[Path] = []
        self._busy = False
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._build_source_card(), 3)
        row.addWidget(self._build_options_card(), 2)
        self.content_layout.addLayout(row)
        self.add_stretch()

    def _build_source_card(self) -> Card:
        card = Card(
            "Arquivos de origem",
            "Os caminhos são revalidados na camada de segurança antes da leitura.",
        )
        self.drop_zone = DropZone()
        self.drop_zone.filesDropped.connect(self.add_files)
        self.drop_zone.browseRequested.connect(self.browse_files)
        card.add_widget(self.drop_zone)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton("Selecionar arquivos")
        self.add_button.setIcon(icon("file.svg"))
        self.add_button.setToolTip("Selecionar um ou mais arquivos (Ctrl+O)")
        self.add_button.clicked.connect(self.browse_files)
        self.remove_button = QPushButton("Remover")
        self.remove_button.setProperty("variant", "ghost")
        self.remove_button.setToolTip("Remover o arquivo selecionado da lista")
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton("Limpar")
        self.clear_button.setProperty("variant", "ghost")
        self.clear_button.clicked.connect(self.clear_files)
        toolbar.addWidget(self.add_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.clear_button)
        card.add_layout(toolbar)

        self.file_list = QListWidget()
        self.file_list.setObjectName("EncryptFileList")
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(185)
        self.file_list.setAccessibleName("Arquivos selecionados para criptografia")
        card.add_widget(self.file_list)

        self.count_label = QLabel("Nenhum arquivo selecionado")
        self.count_label.setObjectName("Faint")
        card.add_widget(self.count_label)
        return card

    def _build_options_card(self) -> Card:
        card = Card(
            "Proteção e destino",
            "A chave é derivada da sua senha e não é armazenada.",
        )
        self.password = PasswordField(
            "Senha de proteção",
            placeholder="Mínimo de 8 caracteres",
        )
        self.password.textChanged.connect(self._on_password_changed)
        self.confirm_password = PasswordField(
            "Confirmar senha",
            placeholder="Repita a senha",
        )
        self.strength = PasswordStrengthMeter()
        self.output_picker = PathPicker(
            "Diretório de saída",
            mode="directory",
            dialog_title="Selecionar diretório de saída",
            placeholder="Selecione onde salvar os arquivos .cvlt",
        )
        self.start_button = QPushButton("Criptografar arquivos")
        self.start_button.setProperty("variant", "primary")
        self.start_button.setIcon(icon("encrypt.svg"))
        self.start_button.setMinimumHeight(40)
        self.start_button.setToolTip("Iniciar a criptografia autenticada (Ctrl+Enter)")
        self.start_button.clicked.connect(self._request_start)
        self.cancel_button = QPushButton("Cancelar operação")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancelRequested)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setAccessibleName("Progresso da criptografia")
        self.banner = StatusBanner()
        note = QLabel(
            "Não há recuperação de senha. Guarde-a em local seguro. "
            "A senha não é gravada no histórico nem nos logs."
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)

        card.add_widget(self.password)
        card.add_widget(self.confirm_password)
        card.add_widget(self.strength)
        card.add_widget(self.output_picker)
        card.add_widget(self.progress)
        card.add_layout(buttons)
        card.add_widget(self.banner)
        card.add_widget(note)
        return card

    def set_default_output_dir(self, path: str | Path) -> None:
        if not self.output_picker.path:
            self.output_picker.set_path(path)
            self.output_picker.set_start_dir(path)

    def browse_files(self) -> None:
        if self._busy:
            return
        start = str(self._paths[0].parent) if self._paths else str(Path.home())
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar arquivos para criptografar",
            start,
            "Todos os arquivos (*)",
        )
        if selected:
            self.add_files(selected)

    def add_files(self, paths: Sequence[str]) -> None:
        if self._busy:
            return
        added = 0
        errors: list[str] = []
        for raw in paths:
            if len(self._paths) >= MAX_SELECTED_FILES:
                errors.append(f"Limite de {MAX_SELECTED_FILES} arquivos por lote.")
                break
            try:
                validated = validate_input_file(raw)
            except CryptoVaultError as exc:
                errors.append(f"{Path(raw).name}: {safe_error_message(exc)}")
                continue
            if validated in self._paths:
                continue
            self._paths.append(validated)
            item = QListWidgetItem(format_file_item(validated, validated.stat().st_size))
            item.setData(Qt.ItemDataRole.UserRole, str(validated))
            item.setToolTip(str(validated))
            self.file_list.addItem(item)
            added += 1
        self._refresh_count()
        if errors:
            self.banner.show_message(
                "Alguns itens não foram adicionados:\n" + "\n".join(errors[:5]),
                "warning",
            )
        elif added:
            self.banner.clear()

    def clear_files(self) -> None:
        if self._busy:
            return
        self._paths.clear()
        self.file_list.clear()
        self._refresh_count()
        self.banner.clear()

    def _remove_selected(self) -> None:
        if self._busy:
            return
        selected = self.file_list.selectedItems()
        for item in selected:
            self.file_list.takeItem(self.file_list.row(item))
        if selected:
            self._sync_paths_from_list()
            self._refresh_count()

    def _sync_paths_from_list(self) -> None:
        self._paths = [
            Path(self.file_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.file_list.count())
        ]

    def _refresh_count(self) -> None:
        total = 0
        for path in self._paths:
            try:
                total += path.stat().st_size
            except OSError:
                continue
        if not self._paths:
            self.count_label.setText("Nenhum arquivo selecionado")
        else:
            self.count_label.setText(
                f"{len(self._paths)} arquivo(s) • {format_bytes(total)} no total"
            )

    def _on_password_changed(self, text: str) -> None:
        self.strength.update_from_text(text)

    def _request_start(self) -> None:
        if self._busy:
            return
        if not self._paths:
            self.banner.show_message("Selecione pelo menos um arquivo.", "warning")
            return
        if not self.password.value or not self.confirm_password.value:
            self.banner.show_message("Informe e confirme a senha de proteção.", "warning")
            self.password.focus_input()
            return
        if self.password.value != self.confirm_password.value:
            self.banner.show_message("As senhas não conferem.", "error")
            self.confirm_password.focus_input()
            return
        try:
            validate_password(self.password.value)
            output_dir = validate_output_directory(self.output_picker.path)
        except CryptoVaultError as exc:
            self.banner.show_message(safe_error_message(exc), "error")
            return
        if not self._paths:
            return
        self.startRequested.emit(list(self._paths), str(output_dir))

    def take_password(self) -> Secret:
        secret = Secret.from_text(self.password.value)
        self.password.clear()
        self.confirm_password.clear()
        self.strength.update_from_text("")
        return secret

    def prepare_start(self) -> None:
        self.progress.setValue(0)
        self.banner.clear()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.drop_zone.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.remove_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.file_list.setEnabled(not busy)
        self.password.setEnabled(not busy)
        self.confirm_password.setEnabled(not busy)
        self.output_picker.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        if busy:
            self.banner.show_message(
                "Processando em segundo plano. A interface permanece responsiva.",
                "processing",
            )
            self.progress.setValue(0)

    def update_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(max(0, min(percent, 100)))
        if message:
            self.banner.show_message(message, "processing")

    def set_result(self, result: BatchResult) -> None:
        self.cancel_button.setVisible(False)
        self.progress.setValue(100 if result.succeeded else self.progress.value())
        if result.cancelled:
            self.banner.show_message(
                f"Operação cancelada. {result.succeeded} arquivo(s) já haviam sido concluídos.",
                "warning",
            )
            return
        if result.failed == 0:
            destination = ""
            successful = [item for item in result.items if item.output_path]
            if successful and successful[0].output_path is not None:
                destination = f" Destino: {successful[0].output_path.parent}"
            self.clear_files()
            self.banner.show_message(
                f"{result.succeeded} arquivo(s) criptografado(s) com sucesso.{destination}",
                "success",
            )
        else:
            details = "\n".join(
                f"• {item.filename}: {item.message}"
                for item in result.items
                if not item.success and not item.cancelled
            )
            self.banner.show_message(
                f"{result.succeeded} concluído(s), {result.failed} com falha.\n{details}",
                "error",
            )

    def trigger_shortcut(self) -> None:
        self.browse_files()

    def apply_icon(self, qicon: QIcon) -> None:
        self.start_button.setIcon(qicon)
