"""Dashboard com dados reais da sessão e do histórico local."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from cryptovault.domain.models import (
    OperationOutcome,
    OperationRecord,
    SessionStats,
)
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import COLORS, icon
from cryptovault.ui.utils import format_local_datetime
from cryptovault.ui.widgets import Card, StatCard


class DashboardPage(BasePage):
    navigateRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_stats()
        self._build_middle()
        self._build_recent()
        self._build_note()
        self.add_stretch()

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.encrypted_card = StatCard(
            "Criptografados nesta sessão",
            hint="Arquivos concluídos desde a abertura do aplicativo.",
            tone="success",
        )
        self.decrypted_card = StatCard(
            "Descriptografados nesta sessão",
            hint="Somente após validação da tag GCM.",
            tone="processing",
        )
        self.verified_card = StatCard(
            "Verificações autenticadas",
            hint="Conteúdo e metadados validados nesta sessão.",
            tone="success",
        )
        self.failures_card = StatCard(
            "Falhas nesta sessão",
            hint="Erros e autenticações recusadas.",
            tone="warning",
        )
        for card in (
            self.encrypted_card,
            self.decrypted_card,
            self.verified_card,
            self.failures_card,
        ):
            row.addWidget(card)
        self.content_layout.addLayout(row)

    def _build_middle(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)

        quick = Card(
            "Acesso rápido",
            "Inicie uma operação. Nenhuma senha é armazenada.",
        )
        encrypt_button = QPushButton("Criptografar arquivos")
        encrypt_button.setObjectName("QuickEncrypt")
        encrypt_button.setProperty("variant", "primary")
        encrypt_button.setIcon(icon("encrypt.svg"))
        encrypt_button.setToolTip("Ir para a tela de criptografia (Ctrl+2)")
        encrypt_button.clicked.connect(lambda: self.navigateRequested.emit("encrypt"))
        decrypt_button = QPushButton("Descriptografar arquivos")
        decrypt_button.setObjectName("QuickDecrypt")
        decrypt_button.setIcon(icon("decrypt.svg"))
        decrypt_button.setToolTip("Ir para a tela de descriptografia (Ctrl+3)")
        decrypt_button.clicked.connect(lambda: self.navigateRequested.emit("decrypt"))
        verify_button = QPushButton("Verificar integridade")
        verify_button.setObjectName("QuickVerify")
        verify_button.setIcon(icon("verify.svg"))
        verify_button.setToolTip("Ir para a tela de verificação (Ctrl+4)")
        verify_button.clicked.connect(lambda: self.navigateRequested.emit("verify"))
        for button in (encrypt_button, decrypt_button, verify_button):
            button.setMinimumHeight(40)
            quick.add_widget(button)
        row.addWidget(quick, 3)

        status = Card(
            "Status da aplicação",
            "Configuração aplicada; não representa certificação de segurança.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(9)
        rows = (
            ("Aplicação", "Pronto", "status"),
            ("Criptografia", "AES-256-GCM · 256 bits", ""),
            ("Derivação", "Scrypt · N=2¹⁵, r=8, p=1", ""),
            ("Formato", "CryptoVault v1 · cabeçalho autenticado", ""),
            ("Persistência", "Histórico local em SQLite", ""),
        )
        self.status_value_label: QLabel | None = None
        for index, (label, value, role) in enumerate(rows):
            key = QLabel(label)
            key.setObjectName("Faint")
            val = QLabel(value)
            val.setObjectName("Mono")
            val.setWordWrap(True)
            if role == "status":
                self.status_value_label = val
                val.setObjectName("CardTitle")
            grid.addWidget(key, index, 0)
            grid.addWidget(val, index, 1)
        grid.setColumnStretch(1, 1)
        quick_status = QWidget()
        quick_status.setLayout(grid)
        status.add_widget(quick_status)
        note = QLabel("Histórico local não é auditoria inviolável.")
        note.setObjectName("Faint")
        note.setWordWrap(True)
        status.add_widget(note)
        row.addWidget(status, 2)
        self.content_layout.addLayout(row)

    def _build_recent(self) -> None:
        self.recent_card = Card(
            "Últimas operações",
            "Registros efetivamente gravados no histórico local.",
        )
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setObjectName("RecentTable")
        self.recent_table.setHorizontalHeaderLabels(
            ["Data e hora", "Operação", "Arquivo", "Resultado"]
        )
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_table.setShowGrid(False)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setMinimumHeight(176)
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_empty = QLabel(
            "Nenhuma operação registrada ainda. O histórico será preenchido "
            "somente após operações reais."
        )
        self.recent_empty.setObjectName("Muted")
        self.recent_empty.setWordWrap(True)
        self.recent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_empty.setMinimumHeight(120)
        self.recent_card.add_widget(self.recent_empty)
        self.recent_card.add_widget(self.recent_table)
        self.recent_table.setVisible(False)
        self.content_layout.addWidget(self.recent_card)

    def _build_note(self) -> None:
        panel = QFrame()
        panel.setObjectName("InfoPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(icon("secure.svg").pixmap(18, 18))
        text = QLabel(
            "A senha protege a chave derivada e nunca é gravada. "
            "A criptografia autenticada detecta alterações, mas não impede "
            "malware com os mesmos privilégios do usuário. Não há promessa de segurança absoluta."
        )
        text.setObjectName("Muted")
        text.setWordWrap(True)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(text, 1)
        self.content_layout.addWidget(panel)

    def refresh(
        self,
        stats: SessionStats,
        records: Sequence[OperationRecord],
        *,
        busy: bool,
    ) -> None:
        self.encrypted_card.set_value(stats.encrypted)
        self.decrypted_card.set_value(stats.decrypted)
        self.verified_card.set_value(stats.verified)
        self.failures_card.set_value(stats.failures)
        if self.status_value_label is not None:
            self.status_value_label.setText("Operação em andamento" if busy else "Pronto")
            self.status_value_label.setStyleSheet(
                f"color: {COLORS['processing'] if busy else COLORS['success']};"
            )
        self._set_recent(records[:5])

    def _set_recent(self, records: Sequence[OperationRecord]) -> None:
        self.recent_table.setRowCount(0)
        if not records:
            self.recent_empty.setVisible(True)
            self.recent_table.setVisible(False)
            return
        self.recent_empty.setVisible(False)
        self.recent_table.setVisible(True)
        for row, record in enumerate(records):
            self.recent_table.insertRow(row)
            values = (
                format_local_datetime(record.timestamp),
                record.kind.label_pt,
                record.filename,
                record.outcome.label_pt,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    color = {
                        OperationOutcome.SUCCESS: COLORS["success"],
                        OperationOutcome.FAILURE: COLORS["danger"],
                        OperationOutcome.CANCELLED: COLORS["warning"],
                    }[record.outcome]
                    item.setForeground(QColor(color))
                self.recent_table.setItem(row, column, item)
            self.recent_table.setRowHeight(row, 32)
