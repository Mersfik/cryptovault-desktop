"""Base comum das páginas com rolagem e espaçamento responsivo."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from cryptovault.ui.theme import density_gap, page_padding


class BasePage(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._container.setObjectName("PageContainer")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(*page_padding("comfortable"))
        self._layout.setSpacing(density_gap("comfortable"))
        self.setWidget(self._container)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout) -> None:
        self._layout.addLayout(layout)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)

    def set_density(self, density: str) -> None:
        self._layout.setContentsMargins(*page_padding(density))
        self._layout.setSpacing(density_gap(density))
