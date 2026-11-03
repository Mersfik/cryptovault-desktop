"""Sanitização de dados antes de compor logs estruturados."""

from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_SECRET_PATTERNS = (
    (
        # Redige o restante da linha: frases-senha podem conter espaços.
        re.compile(r"(?i)(password|senha|passphrase|secret|token|key)\s*[=:]\s*\S.*"),
        r"\1=<redacted>",
    ),
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"), "bearer <redacted>"),
)


def sanitize_log_value(value: object, *, max_length: int = 512) -> str:
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("_", text)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > max_length:
        text = f"{text[:max_length]}..."
    return text


def safe_filename(value: object) -> str:
    text = sanitize_log_value(value, max_length=200)
    return text.replace("\\", "_").replace("/", "_")
