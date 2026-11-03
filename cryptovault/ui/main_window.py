"""Janela principal, navegação e integração entre UI, controlador e serviços."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from cryptovault import APP_NAME, __version__
from cryptovault.application.service import FileOperationService
from cryptovault.domain.errors import CryptoVaultError, HistoryError, safe_error_message
from cryptovault.domain.models import BatchResult, OperationKind, OperationOutcome
from cryptovault.infrastructure.settings import Settings, SettingsRepository
from cryptovault.ui.controller import AppController
from cryptovault.ui.notifications import DesktopNotifier
from cryptovault.ui.pages.base import BasePage
from cryptovault.ui.pages.dashboard import DashboardPage
from cryptovault.ui.pages.decrypt import DecryptPage
from cryptovault.ui.pages.encrypt import EncryptPage
from cryptovault.ui.pages.history import HistoryPage
from cryptovault.ui.pages.settings import SettingsPage
from cryptovault.ui.pages.verify import VerifyPage
from cryptovault.ui.theme import COLORS, application_icon, apply_theme, icon, resource_path
from cryptovault.ui.widgets import Toast

_PAGE_META: dict[str, tuple[str, str, str]] = {
    "dashboard": (
        "Visão geral",
        "Resumo real das operações desta sessão e do histórico local.",
        "dashboard.svg",
    ),
    "encrypt": (
        "Criptografar arquivos",
        "AES-256-GCM com chave derivada por Scrypt e publicação atômica.",
        "encrypt.svg",
    ),
    "decrypt": (
        "Descriptografar arquivos",
        "Validação da tag de autenticação antes de liberar o conteúdo.",
        "decrypt.svg",
    ),
    "verify": (
        "Verificar integridade",
        "Validação de formato, versão, metadados e autenticidade do conteúdo.",
        "verify.svg",
    ),
    "history": (
        "Histórico de operações",
        "Registros locais de operações; não é uma auditoria inviolável.",
        "history.svg",
    ),
    "settings": (
        "Configurações",
        "Preferências locais sem redução dos parâmetros de segurança.",
        "settings.svg",
    ),
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        service: FileOperationService,
        controller: AppController,
        settings_repository: SettingsRepository,
        settings: Settings,
        data_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.controller = controller
        self.settings_repository = settings_repository
        self.settings = settings
        self.data_dir = data_dir
        self._current_key = "dashboard"
        self._shortcuts: list[QShortcut] = []
        self.pages: dict[str, BasePage] = {}
        self.nav_buttons: dict[str, QPushButton] = {}

        self.setObjectName("MainWindow")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(application_icon())
        self.setMinimumSize(1040, 680)
        self.resize(1280, 820)
        self._build_ui()
        self._build_shortcuts()
        self._connect_signals()
        self._apply_settings(settings, initial=True)
        self.navigate("dashboard")
        self._update_busy_ui(False)
        self._refresh_dashboard()
        self._refresh_history()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_sidebar())
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")
        self.pages = self._build_pages()
        for page in self.pages.values():
            self.stack.addWidget(page)
        right_layout.addWidget(self.stack, 1)
        self.toast = Toast()
        toast_wrap = QWidget()
        toast_layout = QHBoxLayout(toast_wrap)
        toast_layout.setContentsMargins(28, 0, 28, 10)
        toast_layout.addWidget(self.toast)
        right_layout.addWidget(toast_wrap)
        central_layout.addWidget(right, 1)
        self.setCentralWidget(central)
        self._build_statusbar()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(234)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(7)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(resource_path("logo.svg"))).scaled(
                38,
                38,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_title = QLabel("CryptoVault")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("SECURE FILE VAULT")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        layout.addSpacing(18)

        section = QLabel("NAVEGAÇÃO")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, (_title, _subtitle, icon_name) in _PAGE_META.items():
            button = QPushButton(_title)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(18, 18))
            button.setAccessibleName(f"Navegar para {_title}")
            button.setToolTip(f"{_title} (Ctrl+{list(_PAGE_META).index(key) + 1})")
            button.clicked.connect(lambda _checked=False, page_key=key: self.navigate(page_key))
            group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)

        local_panel = QFrame()
        local_panel.setObjectName("InfoPanel")
        local_layout = QVBoxLayout(local_panel)
        local_layout.setContentsMargins(10, 9, 10, 9)
        local_layout.setSpacing(3)
        local_title = QLabel("●  Processamento local")
        local_title.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600;")
        local_hint = QLabel("Sem envio de arquivos ou senhas para a rede.")
        local_hint.setObjectName("Faint")
        local_hint.setWordWrap(True)
        local_layout.addWidget(local_title)
        local_layout.addWidget(local_hint)
        layout.addWidget(local_panel)
        version = QLabel(f"v{__version__}  •  Windows / Python")
        version.setObjectName("Faint")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(78)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(28, 12, 28, 12)
        layout.setSpacing(16)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self.page_title = QLabel("Visão geral")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel("")
        self.page_subtitle.setObjectName("PageSubtitle")
        title_block.addWidget(self.page_title)
        title_block.addWidget(self.page_subtitle)
        layout.addLayout(title_block)
        layout.addStretch(1)
        self.app_status_badge = QLabel("PRONTO")
        self.app_status_badge.setObjectName("Badge")
        self.app_status_badge.setProperty("tone", "success")
        layout.addWidget(self.app_status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        return topbar

    def _build_pages(self) -> dict[str, BasePage]:
        self.dashboard_page = DashboardPage()
        self.encrypt_page = EncryptPage()
        self.decrypt_page = DecryptPage()
        self.verify_page = VerifyPage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage(self.data_dir)
        return {
            "dashboard": self.dashboard_page,
            "encrypt": self.encrypt_page,
            "decrypt": self.decrypt_page,
            "verify": self.verify_page,
            "history": self.history_page,
            "settings": self.settings_page,
        }

    def _build_statusbar(self) -> None:
        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        status.showMessage("Pronto")
        security = QLabel("AES-256-GCM  ·  Scrypt  ·  Dados locais")
        security.setObjectName("Faint")
        status.addPermanentWidget(security)
        self.status_message = QLabel("Pronto")
        self.status_message.setObjectName("Faint")
        status.addPermanentWidget(self.status_message)

    def _build_shortcuts(self) -> None:
        for index, key in enumerate(_PAGE_META, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index}"), self)
            shortcut.activated.connect(lambda page_key=key: self.navigate(page_key))
            self._shortcuts.append(shortcut)
        open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        open_shortcut.activated.connect(self._trigger_open)
        self._shortcuts.append(open_shortcut)
        start_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        start_shortcut.activated.connect(self._trigger_start)
        self._shortcuts.append(start_shortcut)
        password_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        password_shortcut.activated.connect(self._focus_password)
        self._shortcuts.append(password_shortcut)
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh_current)
        self._shortcuts.append(refresh_shortcut)

    # ------------------------------------------------------------- wiring
    def _connect_signals(self) -> None:
        self.dashboard_page.navigateRequested.connect(self.navigate)
        self.encrypt_page.startRequested.connect(self._start_encrypt)
        self.encrypt_page.cancelRequested.connect(self.controller.cancel)
        self.decrypt_page.startRequested.connect(self._start_decrypt)
        self.decrypt_page.cancelRequested.connect(self.controller.cancel)
        self.decrypt_page.inspectRequested.connect(self._inspect_for_decrypt)
        self.decrypt_page.openFolderRequested.connect(self._open_directory)
        self.verify_page.startRequested.connect(self._start_verify)
        self.verify_page.cancelRequested.connect(self.controller.cancel)
        self.verify_page.inspectRequested.connect(self._inspect_for_verify)
        self.history_page.refreshRequested.connect(self._load_history_filtered)
        self.history_page.clearConfirmed.connect(self._clear_history)
        self.settings_page.saveRequested.connect(self._save_settings)
        self.settings_page.openPathRequested.connect(self._open_directory)

        self.controller.progress.connect(self._on_progress)
        self.controller.busyChanged.connect(self._update_busy_ui)
        self.controller.statsChanged.connect(lambda _stats: self._refresh_dashboard())
        self.controller.historyChanged.connect(self._on_history_changed)
        self.controller.operationFinished.connect(self._on_operation_finished)
        self.controller.errorRaised.connect(self._on_controller_error)
        self.controller.notification.connect(self._on_notification)

        self.notifier = DesktopNotifier(self)
        self.controller.configure_notifications(
            enabled=self.settings.notifications_enabled,
            on_success=self.settings.notify_on_success,
            on_failure=self.settings.notify_on_failure,
        )
        self.notifier.set_enabled(self.settings.notifications_enabled)

    # ---------------------------------------------------------- navigation
    def navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self._current_key = key
        if key in self.nav_buttons:
            self.nav_buttons[key].setChecked(True)
        title, subtitle, _ = _PAGE_META[key]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        if key == "dashboard":
            self._refresh_dashboard()
        elif key == "history":
            self._refresh_history()
        if isinstance(page, (EncryptPage, DecryptPage)):
            page.set_default_output_dir(self.settings.output_dir)

    def _trigger_open(self) -> None:
        if self._current_key == "encrypt":
            self.encrypt_page.trigger_shortcut()
        elif self._current_key == "decrypt":
            self.decrypt_page.trigger_shortcut()
        elif self._current_key == "verify":
            self.verify_page.trigger_shortcut()

    def _trigger_start(self) -> None:
        if self.controller.busy:
            return
        if self._current_key == "encrypt":
            self.encrypt_page.start_button.click()
        elif self._current_key == "decrypt":
            self.decrypt_page.start_button.click()
        elif self._current_key == "verify":
            self.verify_page.start_button.click()

    def _focus_password(self) -> None:
        if self._current_key == "encrypt":
            self.encrypt_page.password.focus_input()
        elif self._current_key == "decrypt":
            self.decrypt_page.password.focus_input()
        elif self._current_key == "verify":
            self.verify_page.password.focus_input()

    def _refresh_current(self) -> None:
        if self._current_key == "history":
            self._refresh_history()
        elif self._current_key == "dashboard":
            self._refresh_dashboard()

    # ------------------------------------------------------------ operations
    def _start_encrypt(self, files: list[Path], output_dir: str) -> None:
        self.encrypt_page.prepare_start()
        try:
            secret = self.encrypt_page.take_password()
        except CryptoVaultError as exc:
            self._show_toast(safe_error_message(exc), "error")
            return
        try:
            self.controller.start_encrypt(files, secret, output_dir)
        except Exception as exc:  # pragma: no cover - proteção final
            secret.wipe()
            self._show_toast(self.controller.safe_error(exc), "error")

    def _start_decrypt(self, files: list[Path], output_dir: str) -> None:
        self.decrypt_page.prepare_start()
        try:
            secret = self.decrypt_page.take_password()
        except CryptoVaultError as exc:
            self._show_toast(safe_error_message(exc), "error")
            return
        try:
            self.controller.start_decrypt(files, secret, output_dir)
        except Exception as exc:  # pragma: no cover - proteção final
            secret.wipe()
            self._show_toast(self.controller.safe_error(exc), "error")

    def _start_verify(self, files: list[Path]) -> None:
        self.verify_page.prepare_start()
        try:
            secret = self.verify_page.take_password()
        except CryptoVaultError as exc:
            self._show_toast(safe_error_message(exc), "error")
            return
        try:
            self.controller.start_verify(files, secret)
        except Exception as exc:  # pragma: no cover - proteção final
            secret.wipe()
            self._show_toast(self.controller.safe_error(exc), "error")

    def _on_progress(self, percent: int, message: str) -> None:
        kind = self.controller.current_kind
        if kind is OperationKind.ENCRYPT:
            self.encrypt_page.update_progress(percent, message)
        elif kind is OperationKind.DECRYPT:
            self.decrypt_page.update_progress(percent, message)
        elif kind is OperationKind.VERIFY:
            self.verify_page.update_progress(percent, message)
        self.status_message.setText(message or "Processando…")

    def _on_operation_finished(self, result: BatchResult) -> None:
        if result.kind is OperationKind.ENCRYPT:
            self.encrypt_page.set_result(result)
        elif result.kind is OperationKind.DECRYPT:
            self.decrypt_page.set_result(result)
        elif result.kind is OperationKind.VERIFY:
            self.verify_page.set_result(result)
        self._refresh_dashboard()
        self._refresh_history()
        self.status_message.setText("Pronto")

    def _on_controller_error(self, message: str) -> None:
        self._show_toast(message, "error")
        self.status_message.setText("Erro")

    def _update_busy_ui(self, busy: bool) -> None:
        self.encrypt_page.set_busy(busy)
        self.decrypt_page.set_busy(busy)
        self.verify_page.set_busy(busy)
        self.app_status_badge.setText("PROCESSANDO" if busy else "PRONTO")
        self.app_status_badge.setProperty("tone", "processing" if busy else "success")
        self.app_status_badge.style().unpolish(self.app_status_badge)
        self.app_status_badge.style().polish(self.app_status_badge)
        self.status_message.setText("Operação em andamento…" if busy else "Pronto")
        if not busy:
            self._refresh_dashboard()

    def _on_notification(self, text: str, variant: str) -> None:
        self._show_toast(text, variant)
        self.notifier.notify(
            "CryptoVault Desktop",
            text,
            error=variant == "error",
        )

    def _show_toast(self, text: str, variant: str = "info") -> None:
        self.toast.show_message(
            text,
            variant=variant,
            timeout_ms=7000 if variant in {"error", "warning"} else 5000,
        )

    # ---------------------------------------------------------------- history
    def _on_history_changed(self) -> None:
        if self._current_key == "history":
            self._refresh_history()

    def _refresh_history(self) -> None:
        operation, outcome = self.history_page.filter_values()
        self._load_history_filtered(operation, outcome)

    def _load_history_filtered(self, operation: object, outcome: object) -> None:
        kind = operation if isinstance(operation, OperationKind) else None
        record_outcome = outcome if isinstance(outcome, OperationOutcome) else None
        try:
            records = self.controller.list_history(
                limit=1000,
                kind=kind,
                outcome=record_outcome,
            )
        except HistoryError as exc:
            self.history_page.set_records([])
            self._show_toast(safe_error_message(exc), "error")
            return
        self.history_page.set_records(records)

    def _refresh_dashboard(self) -> None:
        try:
            records = self.controller.list_history(limit=5)
        except HistoryError:
            records = []
        self.dashboard_page.refresh(
            self.controller.stats,
            records,
            busy=self.controller.busy,
        )

    def _clear_history(self) -> None:
        try:
            count = self.controller.clear_history()
        except HistoryError as exc:
            self._show_toast(safe_error_message(exc), "error")
            return
        self._show_toast(f"{count} registro(s) removido(s) do histórico.", "success")
        self._refresh_history()
        self._refresh_dashboard()

    # ---------------------------------------------------------------- inspect
    def _inspect_for_decrypt(self, path: str) -> None:
        try:
            info = self.service.inspect_file(path)
        except CryptoVaultError as exc:
            self.decrypt_page.show_inspect_error(safe_error_message(exc))
            return
        self.decrypt_page.show_header_info(info)

    def _inspect_for_verify(self, path: str) -> None:
        try:
            info = self.service.inspect_file(path)
        except CryptoVaultError as exc:
            self.verify_page.show_inspect_error(safe_error_message(exc))
            return
        self.verify_page.show_header_info(info)

    # --------------------------------------------------------------- settings
    def _apply_settings(self, settings: Settings, *, initial: bool = False) -> None:
        self.settings = settings
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(
                app,
                density=settings.density,
                font_scale=settings.font_scale,
            )
        for page in self.pages.values():
            page.set_density(settings.density)
        self.encrypt_page.set_default_output_dir(settings.output_dir)
        self.decrypt_page.set_default_output_dir(settings.output_dir)
        self.settings_page.set_settings(settings)
        self.controller.configure_notifications(
            enabled=settings.notifications_enabled,
            on_success=settings.notify_on_success,
            on_failure=settings.notify_on_failure,
        )
        if hasattr(self, "notifier"):
            self.notifier.set_enabled(settings.notifications_enabled)
        if not initial:
            self._refresh_dashboard()

    def _save_settings(self, candidate: Settings) -> None:
        previous = self.settings
        try:
            self.settings_repository.ensure_output_directory(candidate)
            self.settings_repository.ensure_log_directory(candidate)
            saved = self.settings_repository.save(candidate)
        except CryptoVaultError as exc:
            self.settings_page.show_error(safe_error_message(exc))
            return
        log_changed = Path(saved.log_dir).resolve() != Path(previous.log_dir).resolve()
        self._apply_settings(saved)
        self.settings_page.show_saved(saved, log_changed=log_changed)
        self._show_toast(
            "Configurações salvas."
            + (" Reinicie para usar o novo diretório de logs." if log_changed else ""),
            "success",
        )
        with suppress(HistoryError):
            self.controller.record_retention(saved.history_retention_days)

    def _open_directory(self, path: str) -> None:
        candidate = Path(path).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            self._show_toast("A pasta não existe ou não pode ser acessada.", "error")
            return
        if not resolved.is_dir():
            self._show_toast("O caminho não é um diretório.", "warning")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved))):
            self._show_toast("Não foi possível abrir a pasta.", "error")

    # ----------------------------------------------------------------- close
    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self.controller.busy:
            answer = QMessageBox.question(
                self,
                "Operação em andamento",
                "Há uma operação criptográfica em andamento. Deseja cancelar e sair?\n\n"
                "Arquivos temporários serão removidos e nenhum arquivo parcial será publicado.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                event.ignore()  # type: ignore[attr-defined]
                return
            self.controller.cancel()
        self.controller.shutdown()
        self.notifier.shutdown()
        event.accept()  # type: ignore[attr-defined]


__all__ = ["MainWindow"]
