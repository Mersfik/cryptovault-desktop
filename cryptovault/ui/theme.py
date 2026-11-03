"""Identidade visual, paleta e folha de estilos Qt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"

COLORS = {
    "bg": "#0A0F14",
    "surface": "#101820",
    "surface_alt": "#15212C",
    "surface_high": "#1A2835",
    "border": "#243544",
    "border_soft": "#1B2A37",
    "text": "#E7EEF5",
    "muted": "#8FA3B5",
    "faint": "#65788A",
    "accent": "#36E0A0",
    "accent_dim": "#1F8F67",
    "accent_soft": "#102B24",
    "blue": "#5AA9FF",
    "danger": "#F87171",
    "danger_soft": "#321A1E",
    "warning": "#FBBF24",
    "warning_soft": "#302714",
    "success": "#36E0A0",
    "success_soft": "#102B24",
    "processing": "#60A5FA",
    "processing_soft": "#14263C",
}


def resource_path(name: str) -> Path:
    return RESOURCE_DIR / name


@lru_cache(maxsize=32)
def icon(name: str) -> QIcon:
    path = resource_path(name)
    return QIcon(str(path)) if path.exists() else QIcon()


def application_icon() -> QIcon:
    ico = resource_path("logo.ico")
    return icon("logo.ico") if ico.exists() else icon("logo.svg")


def apply_theme(app: QApplication, *, density: str = "comfortable", font_scale: int = 100) -> None:
    app.setStyle("Fusion")
    scale = max(100, min(int(font_scale), 125)) / 100.0
    base_font = QFont("Segoe UI", 10)
    base_font.setPointSizeF(10.0 * scale)
    app.setFont(base_font)
    app.setStyleSheet(build_stylesheet(density=density, scale=scale))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["surface_high"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["danger"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent_dim"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["faint"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["blue"]))
    app.setPalette(palette)


def build_stylesheet(*, density: str = "comfortable", scale: float = 1.0) -> str:
    compact = density == "compact"
    _ = compact
    body = 10.0 * scale
    small = 9.0 * scale
    tiny = 8.0 * scale
    title = 19.0 * scale
    stat = 26.0 * scale
    check_icon = resource_path("check.svg").as_posix()
    return f"""
* {{
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    outline: none;
}}
QWidget {{
    background-color: {COLORS["bg"]};
    color: {COLORS["text"]};
    font-size: {body:.1f}pt;
}}
QMainWindow, QDialog {{
    background-color: {COLORS["bg"]};
}}
QToolTip {{
    background-color: {COLORS["surface_high"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 8px;
}}
QFrame#Sidebar {{
    background-color: {COLORS["surface"]};
    border-right: 1px solid {COLORS["border_soft"]};
}}
QLabel#BrandTitle {{
    font-size: {13.0 * scale:.1f}pt;
    font-weight: 700;
    color: {COLORS["text"]};
}}
QLabel#BrandSubtitle {{
    font-size: {tiny:.1f}pt;
    color: {COLORS["faint"]};
    letter-spacing: 2px;
    font-weight: 600;
}}
QLabel#SidebarSection {{
    font-size: {tiny:.1f}pt;
    color: {COLORS["faint"]};
    font-weight: 600;
    letter-spacing: 1px;
    padding: 4px 10px;
}}
QPushButton#NavButton {{
    text-align: left;
    padding: 10px 12px;
    border: 1px solid transparent;
    border-left: 3px solid transparent;
    border-radius: 8px;
    background-color: transparent;
    color: {COLORS["muted"]};
    font-size: {body:.1f}pt;
    font-weight: 500;
}}
QPushButton#NavButton:hover {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
}}
QPushButton#NavButton:checked {{
    background-color: {COLORS["accent_soft"]};
    border-left: 3px solid {COLORS["accent"]};
    color: {COLORS["text"]};
    font-weight: 600;
}}
QPushButton#NavButton:focus {{
    border: 1px solid {COLORS["accent_dim"]};
}}
QFrame#TopBar {{
    background-color: {COLORS["bg"]};
    border-bottom: 1px solid {COLORS["border_soft"]};
}}
QLabel#PageTitle {{
    font-size: {title:.1f}pt;
    font-weight: 700;
    color: {COLORS["text"]};
}}
QLabel#PageSubtitle {{
    font-size: {small:.1f}pt;
    color: {COLORS["muted"]};
}}
QLabel#BrandTagline, QLabel#Muted {{
    color: {COLORS["muted"]};
    font-size: {small:.1f}pt;
}}
QLabel#Faint {{
    color: {COLORS["faint"]};
    font-size: {tiny:.1f}pt;
}}
QLabel#CardTitle {{
    font-size: {11.5 * scale:.1f}pt;
    font-weight: 600;
    color: {COLORS["text"]};
}}
QLabel#CardHint {{
    font-size: {small:.1f}pt;
    color: {COLORS["muted"]};
}}
QLabel#FieldLabel {{
    font-size: {small:.1f}pt;
    color: {COLORS["muted"]};
    font-weight: 600;
}}
QLabel#StatValue {{
    font-size: {stat:.1f}pt;
    font-weight: 700;
    color: {COLORS["text"]};
}}
QLabel#StatLabel {{
    color: {COLORS["muted"]};
    font-size: {small:.1f}pt;
}}
QLabel#StatHint {{
    color: {COLORS["faint"]};
    font-size: {tiny:.1f}pt;
}}
QLabel#StatusDot {{
    color: {COLORS["success"]};
    font-size: {body:.1f}pt;
}}
QLabel#Mono {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small:.1f}pt;
    color: {COLORS["muted"]};
}}
QFrame#Card, QFrame#StatCard, QFrame#InfoPanel {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 12px;
}}
QFrame#StatCard {{
    border-left: 3px solid {COLORS["border"]};
}}
QFrame#StatCard[tone="success"] {{ border-left-color: {COLORS["success"]}; }}
QFrame#StatCard[tone="processing"] {{ border-left-color: {COLORS["processing"]}; }}
QFrame#StatCard[tone="warning"] {{ border-left-color: {COLORS["warning"]}; }}
QFrame#StatCard[tone="muted"] {{ border-left-color: {COLORS["faint"]}; }}
QFrame#InfoPanel {{
    background-color: {COLORS["surface_alt"]};
    border-color: {COLORS["border"]};
}}
QPushButton {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 7px;
    color: {COLORS["text"]};
    padding: 8px 15px;
    min-height: 18px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLORS["surface_high"]};
    border-color: {COLORS["border"]};
}}
QPushButton:pressed {{
    background-color: {COLORS["surface"]};
}}
QPushButton:focus {{
    border: 1px solid {COLORS["accent"]};
}}
QPushButton:disabled {{
    color: {COLORS["faint"]};
    background-color: {COLORS["surface"]};
    border-color: {COLORS["border_soft"]};
}}
QPushButton[variant="primary"] {{
    background-color: {COLORS["accent"]};
    border: 1px solid {COLORS["accent"]};
    color: #06130D;
}}
QPushButton[variant="primary"]:hover {{
    background-color: #5BEAB6;
    border-color: #5BEAB6;
}}
QPushButton[variant="primary"]:pressed {{
    background-color: #26BF85;
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {COLORS["accent_soft"]};
    border-color: {COLORS["accent_dim"]};
    color: {COLORS["faint"]};
}}
QPushButton[variant="ghost"] {{
    background-color: transparent;
    border-color: transparent;
    color: {COLORS["muted"]};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
}}
QPushButton[variant="danger"] {{
    background-color: {COLORS["danger_soft"]};
    border-color: #623238;
    color: #FCA5A5;
}}
QPushButton[variant="danger"]:hover {{
    background-color: #452126;
}}
QPushButton#EyeButton {{
    background-color: transparent;
    border: none;
    color: {COLORS["muted"]};
    padding: 4px 8px;
    font-size: {small:.1f}pt;
    font-weight: 500;
}}
QPushButton#EyeButton:hover {{
    color: {COLORS["accent"]};
    background-color: transparent;
}}
QLineEdit, QComboBox, QSpinBox, QDateEdit {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 7px;
    padding: 8px 10px;
    color: {COLORS["text"]};
    selection-background-color: {COLORS["accent_dim"]};
    min-height: 20px;
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: #334B60;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {COLORS["accent_dim"]};
}}
QLineEdit:read-only {{
    color: {COLORS["muted"]};
    background-color: {COLORS["surface"]};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: {COLORS["faint"]};
    background-color: {COLORS["surface"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS["surface_high"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
    padding: 4px;
}}
QCheckBox {{
    color: {COLORS["text"]};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    background-color: {COLORS["surface_alt"]};
}}
QCheckBox::indicator:checked {{
    background-color: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
    image: url("{check_icon}");
}}
QCheckBox::indicator:disabled {{
    background-color: {COLORS["surface"]};
    border-color: {COLORS["border_soft"]};
}}
QProgressBar {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 5px;
    height: 9px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {COLORS["accent"]};
    border-radius: 4px;
}}
QProgressBar[quality="0"]::chunk {{ background-color: {COLORS["danger"]}; }}
QProgressBar[quality="1"]::chunk {{ background-color: {COLORS["warning"]}; }}
QProgressBar[quality="2"]::chunk {{ background-color: #7DD3FC; }}
QProgressBar[quality="3"]::chunk, QProgressBar[quality="4"]::chunk {{
    background-color: {COLORS["success"]};
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS["border"]};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: #355066; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS["border"]};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QListWidget, QTableWidget, QTreeWidget {{
    background-color: {COLORS["surface"]};
    alternate-background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 8px;
    color: {COLORS["text"]};
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
    gridline-color: {COLORS["border_soft"]};
}}
QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {COLORS["border_soft"]};
}}
QListWidget::item:selected {{
    background-color: {COLORS["accent_soft"]};
}}
QTableWidget::item {{
    padding: 6px;
}}
QHeaderView::section {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["muted"]};
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    padding: 8px;
    font-weight: 600;
    font-size: {small:.1f}pt;
}}
QTableCornerButton::section {{
    background-color: {COLORS["surface_alt"]};
    border: none;
}}
QFrame#DropZone {{
    background-color: {COLORS["surface"]};
    border: 1px dashed #365267;
    border-radius: 12px;
}}
QFrame#DropZone:hover, QFrame#DropZone[dragActive="true"] {{
    background-color: {COLORS["accent_soft"]};
    border: 1px dashed {COLORS["accent"]};
}}
QLabel#DropTitle {{
    font-size: {12.0 * scale:.1f}pt;
    font-weight: 600;
    color: {COLORS["text"]};
}}
QLabel#DropHint {{
    color: {COLORS["muted"]};
    font-size: {small:.1f}pt;
}}
QFrame#Banner {{
    border-radius: 8px;
    border: 1px solid {COLORS["border"]};
    background-color: {COLORS["surface_alt"]};
}}
QFrame#Banner[variant="success"] {{
    background-color: {COLORS["success_soft"]};
    border-color: {COLORS["accent_dim"]};
}}
QFrame#Banner[variant="error"] {{
    background-color: {COLORS["danger_soft"]};
    border-color: #623238;
}}
QFrame#Banner[variant="warning"] {{
    background-color: {COLORS["warning_soft"]};
    border-color: #6B551D;
}}
QFrame#Banner[variant="processing"] {{
    background-color: {COLORS["processing_soft"]};
    border-color: #2C4A71;
}}
QLabel#BannerText {{
    font-size: {small:.1f}pt;
    color: {COLORS["text"]};
}}
QLabel#Badge {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 9px;
    padding: 2px 8px;
    color: {COLORS["muted"]};
    font-size: {tiny:.1f}pt;
    font-weight: 600;
}}
QLabel#Badge[tone="success"] {{
    background-color: {COLORS["success_soft"]};
    border-color: {COLORS["accent_dim"]};
    color: {COLORS["success"]};
}}
QLabel#Badge[tone="error"] {{
    background-color: {COLORS["danger_soft"]};
    border-color: #623238;
    color: {COLORS["danger"]};
}}
QLabel#Badge[tone="processing"] {{
    background-color: {COLORS["processing_soft"]};
    border-color: #2C4A71;
    color: {COLORS["processing"]};
}}
QFrame#Toast {{
    background-color: {COLORS["surface_high"]};
    border: 1px solid {COLORS["border"]};
    border-left: 4px solid {COLORS["accent"]};
    border-radius: 8px;
}}
QFrame#Toast[variant="error"] {{ border-left-color: {COLORS["danger"]}; }}
QFrame#Toast[variant="warning"] {{ border-left-color: {COLORS["warning"]}; }}
QLabel#ToastText {{
    color: {COLORS["text"]};
    font-size: {small:.1f}pt;
}}
QStatusBar {{
    background-color: {COLORS["surface"]};
    border-top: 1px solid {COLORS["border_soft"]};
    color: {COLORS["muted"]};
    font-size: {tiny:.1f}pt;
}}
QStatusBar::item {{ border: none; }}
QMenu {{
    background-color: {COLORS["surface_high"]};
    border: 1px solid {COLORS["border"]};
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: {COLORS["accent_soft"]};
}}
QMessageBox {{
    background-color: {COLORS["surface"]};
}}
QMessageBox QLabel {{
    color: {COLORS["text"]};
}}
QDialogButtonBox QPushButton {{
    min-width: 84px;
}}
QGroupBox {{
    border: 1px solid {COLORS["border_soft"]};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLORS["muted"]};
}}
QFrame#Separator {{
    background-color: {COLORS["border_soft"]};
    max-height: 1px;
}}
QSplitter::handle {{ background-color: {COLORS["border_soft"]}; }}
QTabWidget::pane {{ border: 1px solid {COLORS["border_soft"]}; }}
QTabBar::tab {{
    background: {COLORS["surface"]};
    padding: 8px 14px;
    border: 1px solid transparent;
}}
QTabBar::tab:selected {{
    background: {COLORS["surface_alt"]};
    border-bottom: 2px solid {COLORS["accent"]};
}}
"""


def density_gap(density: str) -> int:
    return 12 if density == "compact" else 18


def page_padding(density: str) -> tuple[int, int, int, int]:
    value = 20 if density == "compact" else 28
    return value, value, value, value


__all__ = [
    "COLORS",
    "RESOURCE_DIR",
    "application_icon",
    "apply_theme",
    "build_stylesheet",
    "density_gap",
    "icon",
    "page_padding",
    "resource_path",
]
