"""Formatadores de apresentação sem qualquer manipulação criptográfica."""

from __future__ import annotations

from datetime import datetime


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024.0 or unit == "TB":
            if value >= 100:
                return f"{value:.0f} {unit}"
            if value >= 10:
                return f"{value:.1f} {unit}"
            return f"{value:.2f} {unit}"
    return f"{size} B"


def format_duration_ms(duration_ms: int) -> str:
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    seconds = duration_ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes} min {remainder} s"


def format_local_datetime(value: datetime) -> str:
    local = value.astimezone()
    return local.strftime("%d/%m/%Y %H:%M:%S")


def truncate_middle(text: str, max_chars: int = 54) -> str:
    if len(text) <= max_chars:
        return text
    keep = max(8, (max_chars - 3) // 2)
    return f"{text[:keep]}...{text[-keep:]}"
