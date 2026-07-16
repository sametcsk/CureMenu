from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_MAX_TEXT_LENGTH = 4000
SECRET_KEY_HINTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "cookie",
    "set_cookie",
    "password",
    "sifre",
    "secret",
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
IBAN_RE = re.compile(r"\bTR\d{2}(?:[\s-]?\d{4}){5}[\s-]?\d{2}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?90[\s-]?)?(?:0[\s-]?)?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
TC_ID_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
URL_SECRET_RE = re.compile(
    r"([?&](?:access_token|refresh_token|token|api_key|apikey|secret|password|sifre)=)[^&#\s]+",
    re.IGNORECASE,
)
BEARER_SECRET_RE = re.compile(r"\b(Bearer\s+)[A-Z0-9._~+/=-]+", re.IGNORECASE)


def redact_text(value: str, max_length: int = DEFAULT_MAX_TEXT_LENGTH) -> str:
    """Mask direct personal identifiers in free text while preserving clinical context."""
    text = value or ""
    text = IBAN_RE.sub("[REDACTED_IBAN]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = TC_ID_RE.sub("[REDACTED_ID]", text)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = URL_SECRET_RE.sub(r"\1[REDACTED_SECRET]", text)
    text = BEARER_SECRET_RE.sub(r"\1[REDACTED_SECRET]", text)
    if max_length > 0 and len(text) > max_length:
        return f"{text[:max_length]}...[TRUNCATED]"
    return text


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(hint in normalized for hint in SECRET_KEY_HINTS)


def redact_data(value: Any, max_text_length: int = DEFAULT_MAX_TEXT_LENGTH) -> Any:
    """Recursively redact nested metadata before persistence."""
    if isinstance(value, str):
        return redact_text(value, max_text_length)
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _is_secret_key(key):
                redacted[key] = "[REDACTED_SECRET]"
            else:
                redacted[key] = redact_data(item, max_text_length)
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact_data(item, max_text_length) for item in value]
    return value


def redact_json_string(value: str | None, max_text_length: int = DEFAULT_MAX_TEXT_LENGTH) -> str | None:
    """Redact a JSON string if possible; otherwise redact it as plain text."""
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return redact_text(str(value), max_text_length)
    return json.dumps(redact_data(parsed, max_text_length), ensure_ascii=False)


def dumps_redacted_json(value: Any, max_text_length: int = DEFAULT_MAX_TEXT_LENGTH) -> str:
    return json.dumps(redact_data(value, max_text_length), ensure_ascii=False)
