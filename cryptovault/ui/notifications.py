"""Notificações de desktop opcionais, com fallback visual na janela."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from cryptovault.ui.theme import application_icon


class DesktopNotifier(QObject):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._enabled = True
        self._tray: QSystemTrayIcon | None = None
        if (
            QGuiApplication.platformName() != "offscreen"
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            self._tray = QSystemTrayIcon(application_icon(), self)
            self._tray.setToolTip("CryptoVault Desktop")
            self._tray.show()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if self._tray is not None:
            if enabled:
                self._tray.show()
            else:
                self._tray.hide()

    def notify(self, title: str, message: str, *, error: bool = False) -> None:
        if not self._enabled or self._tray is None:
            return
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if error
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray.showMessage(title, message, icon, 5000)

    def shutdown(self) -> None:
        if self._tray is not None:
            self._tray.hide()
