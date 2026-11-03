"""Componentes Qt reutilizáveis, sem chamadas diretas ao motor criptográfico."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cryptovault.security.passwords import estimate_quality
from cryptovault.ui.theme import resource_path
from cryptovault.ui.utils import format_bytes


class Card(QFrame):
    def __init__(
        self,
        title: str = "",
        hint: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            root.addWidget(title_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("CardHint")
            hint_label.setWordWrap(True)
            root.addWidget(hint_label)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        root.addLayout(self.body)

    def add_widget(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        self.body.addLayout(layout)


class StatCard(QFrame):
    def __init__(
        self,
        label: str,
        *,
        hint: str = "",
        tone: str = "muted",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setProperty("tone", tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(4)
        self.value_label = QLabel("0")
        self.value_label.setObjectName("StatValue")
        label_widget = QLabel(label)
        label_widget.setObjectName("StatLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("StatHint")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: int | str) -> None:
        self.value_label.setText(str(value))


class PasswordField(QWidget):
    textChanged = Signal(str)

    def __init__(
        self,
        label: str = "Senha",
        *,
        placeholder: str = "Digite a senha",
        auto_hide_ms: int = 10_000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._auto_hide_ms = auto_hide_ms
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        root.addWidget(self.label)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setPlaceholderText(placeholder)
        self.input.setAccessibleName(label)
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(self.textChanged)
        self.toggle_button = QPushButton("Mostrar")
        self.toggle_button.setObjectName("EyeButton")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setToolTip("Mostrar a senha por 10 segundos")
        self.toggle_button.setAccessibleName("Mostrar ou ocultar senha")
        self.toggle_button.toggled.connect(self._on_toggle)
        row.addWidget(self.input, 1)
        row.addWidget(self.toggle_button)
        root.addLayout(row)
        self.label.setBuddy(self.input)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_password)

    @property
    def value(self) -> str:
        return self.input.text()

    def clear(self) -> None:
        self._hide_timer.stop()
        self.input.clear()
        self.toggle_button.setChecked(False)
        self.input.setEchoMode(QLineEdit.EchoMode.Password)

    def focus_input(self) -> None:
        self.input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_toggle(self, visible: bool) -> None:
        if visible:
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_button.setText("Ocultar")
            self.toggle_button.setToolTip("Ocultar a senha agora")
            if self._auto_hide_ms > 0:
                self._hide_timer.start(self._auto_hide_ms)
        else:
            self.hide_password()

    def hide_password(self) -> None:
        self._hide_timer.stop()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_button.blockSignals(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.blockSignals(False)
        self.toggle_button.setText("Mostrar")
        self.toggle_button.setToolTip("Mostrar a senha por 10 segundos")


class PasswordStrengthMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.bar = QProgressBar()
        self.bar.setRange(0, 4)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setAccessibleName("Estimativa de força da senha")
        self.label = QLabel("Estimativa de força: não informada")
        self.label.setObjectName("Faint")
        self.label.setWordWrap(True)
        layout.addWidget(self.bar)
        layout.addWidget(self.label)

    def update_from_text(self, text: str) -> None:
        quality = estimate_quality(text)
        self.bar.setValue(quality.score)
        self.bar.setProperty("quality", str(quality.score))
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
        if not text:
            self.label.setText("Estimativa heurística de força. Não é uma garantia de segurança.")
        else:
            self.label.setText(f"Estimativa de força: {quality.label}. {quality.hint}")
        self.bar.setToolTip(self.label.text())


class DropZone(QFrame):
    filesDropped = Signal(list)
    browseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Área para arrastar arquivos ou pressionar Enter para selecionar")
        self.setMinimumHeight(142)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(5)
        pixmap = QPixmap(str(resource_path("file.svg"))).scaled(
            38,
            38,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Arraste arquivos para cá")
        title.setObjectName("DropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("ou clique para selecionar • somente arquivos locais")
        hint.setObjectName("DropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(hint)

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QEvent) -> None:  # type: ignore[override]
        mime = getattr(event, "mimeData", lambda: None)()
        if mime is not None and mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            self._set_drag_active(True)
            event.acceptProposedAction()  # type: ignore[attr-defined]
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QEvent) -> None:  # type: ignore[override]
        self._set_drag_active(False)
        super().dragLeaveEvent(event)  # type: ignore[arg-type]

    def dropEvent(self, event: QEvent) -> None:  # type: ignore[override]
        self._set_drag_active(False)
        mime = getattr(event, "mimeData", lambda: None)()
        if mime is None or not mime.hasUrls():
            return
        paths = [
            url.toLocalFile() for url in mime.urls() if url.isLocalFile() and url.toLocalFile()
        ]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()  # type: ignore[attr-defined]
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.browseRequested.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.browseRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class PathPicker(QWidget):
    pathChanged = Signal(str)

    def __init__(
        self,
        label: str,
        *,
        mode: str = "file",
        dialog_title: str = "Selecionar",
        file_filter: str = "Todos os arquivos (*)",
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if mode not in {"file", "directory"}:
            raise ValueError("Modo de seletor inválido.")
        self.mode = mode
        self.dialog_title = dialog_title
        self.file_filter = file_filter
        self._start_dir = str(Path.home())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.line_edit = QLineEdit()
        self.line_edit.setReadOnly(True)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setAccessibleName(label)
        self.button = QPushButton("Selecionar")
        self.button.setAccessibleName(f"Selecionar {label.lower()}")
        self.button.clicked.connect(self._browse)
        row.addWidget(self.line_edit, 1)
        row.addWidget(self.button)
        root.addWidget(self.label)
        root.addLayout(row)
        self.label.setBuddy(self.line_edit)
        self.line_edit.textChanged.connect(self.pathChanged)

    @property
    def path(self) -> str:
        return self.line_edit.text().strip()

    def set_path(self, value: str | Path) -> None:
        self.line_edit.setText(str(value))

    def set_start_dir(self, value: str | Path) -> None:
        self._start_dir = str(value)

    def clear(self) -> None:
        self.line_edit.clear()

    def _browse(self) -> None:
        if self.mode == "directory":
            selected = QFileDialog.getExistingDirectory(
                self,
                self.dialog_title,
                self._start_dir,
                QFileDialog.Option.ShowDirsOnly,
            )
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                self._start_dir,
                self.file_filter,
            )
        if selected:
            self.set_path(selected)


class StatusBanner(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Banner")
        self.setProperty("variant", "info")
        self.setVisible(False)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 9, 12, 9)
        self._layout.setSpacing(9)
        self.icon_label = QLabel("i")
        self.icon_label.setFixedWidth(16)
        self.icon_label.setObjectName("CardTitle")
        self.text_label = QLabel("")
        self.text_label.setObjectName("BannerText")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self.text_label, 1)

    def show_message(self, text: str, variant: str = "info") -> None:
        variant = (
            variant if variant in {"info", "success", "error", "warning", "processing"} else "info"
        )
        self.setProperty("variant", variant)
        icons = {"success": "✓", "error": "×", "warning": "!", "processing": "…"}
        self.icon_label.setText(icons.get(variant, "i"))
        self.text_label.setText(text)
        self.setAccessibleName(text)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setVisible(bool(text))

    def clear(self) -> None:
        self.text_label.clear()
        self.setVisible(False)


class Toast(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("variant", "success")
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)
        self.text_label = QLabel("")
        self.text_label.setObjectName("ToastText")
        self.text_label.setWordWrap(True)
        close_button = QPushButton("×")
        close_button.setObjectName("EyeButton")
        close_button.setFixedWidth(28)
        close_button.setToolTip("Fechar notificação")
        close_button.clicked.connect(self.hide)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(close_button)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, variant: str = "success", timeout_ms: int = 6000) -> None:
        self.setProperty("variant", variant)
        self.text_label.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setVisible(True)
        self._timer.start(timeout_ms)


class LabeledCombo(QWidget):
    def __init__(
        self,
        label: str,
        options: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label_widget = QLabel(label)
        label_widget.setObjectName("FieldLabel")
        self.combo = QComboBox()
        for text, value in options:
            self.combo.addItem(text, value)
        self.combo.setAccessibleName(label)
        label_widget.setBuddy(self.combo)
        layout.addWidget(label_widget)
        layout.addWidget(self.combo)


def horizontal_rule() -> QFrame:
    line = QFrame()
    line.setObjectName("Separator")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def format_file_item(path: Path, size: int) -> str:
    return f"{path.name}   •   {format_bytes(size)}   •   {path.parent}"
