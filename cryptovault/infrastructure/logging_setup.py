"""Logs JSON estruturados, rotativos e sanitizados."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import suppress
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cryptovault.security.paths import ensure_private_directory
from cryptovault.security.redaction import sanitize_log_value

_LOGGER_NAME = "cryptovault"
_configured_path: Path | None = None


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = sanitize_log_value(record.getMessage(), max_length=2000)
            record.args = ()
        except Exception:  # pragma: no cover - proteção defensiva
            record.msg = "log_message_error"
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    _ALLOWED = (
        "event",
        "operation",
        "result",
        "file_name",
        "code",
        "duration_ms",
        "size_bytes",
        "output_count",
        "version",
        "component",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_value(record.getMessage(), max_length=2000),
        }
        for key in self._ALLOWED:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = sanitize_log_value(value, max_length=500)
        if record.exc_info:
            exc = record.exc_info[1]
            payload["exception_type"] = type(exc).__name__ if exc else "unknown"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(log_dir: Path, *, level: int = logging.INFO) -> Path:
    global _configured_path
    directory = ensure_private_directory(log_dir)
    log_path = directory / "cryptovault.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        with suppress(Exception):
            handler.close()
    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger.info(
        "logging_initialized",
        extra={"event": "logging_initialized", "component": "infrastructure"},
    )
    for suffix in ("", ".1", ".2", ".3", ".4", ".5"):
        with suppress(OSError):
            os.chmod(Path(f"{log_path}{suffix}"), 0o600)
    logging.captureWarnings(True)
    _configured_path = log_path

    def excepthook(exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
        logger.error(
            "unhandled_exception",
            exc_info=(exc_type, exc, tb),  # type: ignore[arg-type]
            extra={"event": "unhandled_exception"},
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook
    return log_path


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def current_log_path() -> Path | None:
    return _configured_path
