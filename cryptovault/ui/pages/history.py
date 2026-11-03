"""Tela de histórico local com filtros por operação e resultado."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from cryptovault.domain.models import OperationKind, OperationOutcome, OperationRecord
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.theme import COLORS, icon
from cryptovault.ui.utils import format_bytes, format_duration_ms, format_local_datetime
from cryptovault.ui.widgets import Card


class HistoryPage(BasePage):
    refreshRequested = Signal(object, object)
    clearConfirmed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[OperationRecord] = []
        self._build_filters()
        self._build_table()
        self.add_stretch()

    def _build_filters(self) -> None:
        card = Card(
            "Filtros",
            "O histórico registra nome do arquivo, operação, horário e resultado. "
            "Nunca registra senhas, chaves ou conteúdo.",
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        operation_label = QLabel("Operação")
        operation_label.setObjectName("FieldLabel")
        self.operation_filter = QComboBox()
        self.operation_filter.setAccessibleName("Filtrar por operação")
        self.operation_filter.addItem("Todas", None)
        for kind in OperationKind:
            self.operation_filter.addItem(kind.label_pt, kind.value)
        result_label = QLabel("Resultado")
        result_label.setObjectName("FieldLabel")
        self.result_filter = QComboBox()
        self.result_filter.setAccessibleName("Filtrar por resultado")
        self.result_filter.addItem("Todos", None)
        for outcome in OperationOutcome:
            self.result_filter.addItem(outcome.label_pt, outcome.value)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setIcon(icon("history.svg"))
        self.refresh_button.clicked.connect(self.request_refresh)
        self.clear_button = QPushButton("Limpar histórico")
        self.clear_button.setProperty("variant", "danger")
        self.clear_button.setToolTip("Excluir permanentemente os registros do histórico local")
        self.clear_button.clicked.connect(self._confirm_clear)
        self.clear_button.setEnabled(False)
        row.addWidget(operation_label)
        row.addWidget(self.operation_filter)
        row.addWidget(result_label)
        row.addWidget(self.result_filter)
        row.addStretch(1)
        row.addWidget(self.refresh_button)
        row.addWidget(self.clear_button)
        card.add_layout(row)
        self.count_label = QLabel("0 registro(s)")
        self.count_label.setObjectName("Faint")
        card.add_widget(self.count_label)
        self.content_layout.addWidget(card)
        self.operation_filter.currentIndexChanged.connect(self.request_refresh)
        self.result_filter.currentIndexChanged.connect(self.request_refresh)

    def _build_table(self) -> None:
        card = Card(
            "Registros",
            "Histórico local não é um mecanismo de auditoria inviolável.",
        )
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("HistoryTable")
        self.table.setHorizontalHeaderLabels(
            ["Data e hora", "Operação", "Arquivo", "Resultado", "Detalhes", "Duração"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(320)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.empty_label = QLabel(
            "Nenhum registro para os filtros atuais. Operações reais aparecerão aqui."
        )
        self.empty_label.setObjectName("Muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(160)
        card.add_widget(self.empty_label)
        card.add_widget(self.table)
        self.table.setVisible(False)
        self.content_layout.addWidget(card)

    def filter_values(self) -> tuple[OperationKind | None, OperationOutcome | None]:
        operation_value = self.operation_filter.currentData()
        result_value = self.result_filter.currentData()
        operation = OperationKind(operation_value) if operation_value else None
        outcome = OperationOutcome(result_value) if result_value else None
        return operation, outcome

    def request_refresh(self, *_args: object) -> None:
        operation, outcome = self.filter_values()
        self.refreshRequested.emit(operation, outcome)

    def set_loading(self) -> None:
        self.count_label.setText("Carregando registros…")

    def set_records(self, records: Sequence[OperationRecord]) -> None:
        self._records = list(records)
        self.table.setRowCount(0)
        self.count_label.setText(f"{len(records)} registro(s) exibido(s)")
        self.clear_button.setEnabled(bool(records))
        if not records:
            self.table.setVisible(False)
            self.empty_label.setVisible(True)
            return
        self.empty_label.setVisible(False)
        self.table.setVisible(True)
        for row, record in enumerate(records):
            self.table.insertRow(row)
            values = (
                format_local_datetime(record.timestamp),
                record.kind.label_pt,
                record.filename,
                record.outcome.label_pt,
                record.message,
                format_duration_ms(record.duration_ms),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 3:
                    item.setForeground(
                        QColor(
                            {
                                OperationOutcome.SUCCESS: COLORS["success"],
                                OperationOutcome.FAILURE: COLORS["danger"],
                                OperationOutcome.CANCELLED: COLORS["warning"],
                            }[record.outcome]
                        )
                    )
                if column == 5:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)
            if record.size_bytes:
                self.table.item(row, 2).setToolTip(
                    f"{record.filename}\n{format_bytes(record.size_bytes)}"
                )
            self.table.setRowHeight(row, 32)

    def _confirm_clear(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Limpar histórico",
            "Deseja excluir permanentemente todos os registros do histórico local?\n\n"
            "Arquivos criptografados e descriptografados não serão afetados. "
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer is QMessageBox.StandardButton.Yes:
            self.clearConfirmed.emit()

    def clear_filters(self) -> None:
        self.operation_filter.setCurrentIndex(0)
        self.result_filter.setCurrentIndex(0)
        self.request_refresh()
