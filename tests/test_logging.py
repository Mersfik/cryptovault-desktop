from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from cryptovault.infrastructure.logging_setup import (
    JsonFormatter,
    RedactionFilter,
    configure_logging,
    current_log_path,
    get_logger,
)
from cryptovault.security.redaction import safe_filename, sanitize_log_value

pytestmark = pytest.mark.security


@pytest.fixture
def log_file(tmp_path: Path) -> Iterator[Path]:
    path = configure_logging(tmp_path / "logs")
    logger = get_logger()
    yield path
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _read_records(path: Path) -> list[dict[str, object]]:
    contents = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in contents if line.strip()]


def test_json_structure_and_allowed_fields(log_file: Path) -> None:
    logger = get_logger()
    logger.info(
        "operacao_concluida",
        extra={
            "event": "encrypt_completed",
            "operation": "encrypt",
            "file_name": "relatorio.pdf",
            "result": "success",
            "duration_ms": 42,
            "size_bytes": 1024,
            "campo_nao_permitido": "não deve aparecer",
        },
    )
    for handler in logger.handlers:
        handler.flush()
    records = _read_records(log_file)
    record = records[-1]
    assert record["level"] == "INFO"
    assert record["logger"] == "cryptovault"
    assert record["message"] == "operacao_concluida"
    assert record["event"] == "encrypt_completed"
    assert record["file_name"] == "relatorio.pdf"
    assert record["duration_ms"] == "42"
    assert "campo_nao_permitido" not in record
    assert current_log_path() == log_file


def test_passwords_are_redacted_from_logs(log_file: Path) -> None:
    logger = get_logger()
    secret = "minha-senha-super-secreta-2026"
    logger.info("falha com senha=%s", secret)
    logger.info("evento", extra={"event": "login", "file_name": f"senha={secret}"})
    for handler in logger.handlers:
        handler.flush()
    raw = log_file.read_text(encoding="utf-8")
    assert secret not in raw
    assert "<redacted>" in raw
    records = _read_records(log_file)
    assert all(secret not in json.dumps(record, ensure_ascii=False) for record in records)


def test_control_characters_are_neutralized(log_file: Path) -> None:
    logger = get_logger()
    logger.info("linha\x00com\x1fcontrole")
    for handler in logger.handlers:
        handler.flush()
    record = _read_records(log_file)[-1]
    assert "\x00" not in str(record["message"])
    assert "\x1f" not in str(record["message"])
    assert "_" in str(record["message"])


def test_exception_logs_only_type(log_file: Path) -> None:
    logger = get_logger()
    try:
        raise RuntimeError("detalhe interno com senha=segredo")
    except RuntimeError:
        logger.exception("falhou", extra={"event": "unhandled_exception"})
    for handler in logger.handlers:
        handler.flush()
    record = _read_records(log_file)[-1]
    assert record["exception_type"] == "RuntimeError"
    assert "segredo" not in json.dumps(record, ensure_ascii=False)
    assert "Traceback" not in json.dumps(record, ensure_ascii=False)


def test_redaction_filter_and_formatter_are_defensive() -> None:
    record = logging.LogRecord(
        name="cryptovault",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=abc123",
        args=(),
        exc_info=None,
    )
    assert RedactionFilter().filter(record) is True
    assert record.getMessage() == "token=<redacted>"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "token=<redacted>"


def test_sanitize_log_value_limits_and_replaces_secrets() -> None:
    assert sanitize_log_value("x" * 600, max_length=10) == f"{'x' * 10}..."
    assert sanitize_log_value("Bearer abc.def-123") == "bearer <redacted>"
    assert sanitize_log_value("passphrase=minha frase") == "passphrase=<redacted>"
    assert safe_filename("C:\\Users\\maria\\segredo.txt") == "C:_Users_maria_segredo.txt"
    assert safe_filename("a/b\nc") == "a_b_c"
