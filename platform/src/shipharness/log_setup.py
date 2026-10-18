"""Structured logging with key redaction."""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from typing import Any

import structlog
from pydantic import SecretStr

REDACTED = "[redacted]"

# OpenAI keys start with "sk-"; LangSmith keys start with "lsv2_pt_" or "lsv2_sk_".
KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\blsv2_(?:pt|sk)_[A-Za-z0-9_]{20,}"),
)

# Whole credential-like field names only ("input_tokens" or "idempotency_key" are not secrets).
_SENSITIVE_NAME = re.compile(
    r"(^|[_-])(api[_-]?key|secret|password|passwd|authorization|token|access[_-]?token|"
    r"refresh[_-]?token|bearer)$",
    re.IGNORECASE,
)


def mask_keys(text: str) -> str:
    """Replace key-shaped substrings (OpenAI, LangSmith) with [redacted]."""
    for pattern in KEY_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def redact(value: Any) -> Any:
    """Return a copy of `value` with credentials removed.

    Mapping entries whose name looks like a credential are replaced; key-shaped substrings in any
    string are masked; SecretStr values are never revealed.
    """
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, str):
        return mask_keys(value)
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for name, item in value.items():
            if isinstance(name, str) and _SENSITIVE_NAME.search(name) and item not in (None, ""):
                out[name] = REDACTED
            else:
                out[name] = redact(item)
        return out
    if isinstance(value, list | tuple):
        return type(value)(redact(item) for item in value)
    return value


def _redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact(event_dict)


class _CurrentStderr:
    """Writes to whatever sys.stderr is at call time (survives stream swaps by test runners)."""

    def write(self, text: str) -> int:
        return sys.stderr.write(text)

    def flush(self) -> None:
        sys.stderr.flush()


def configure_logging(json: bool = False) -> None:
    """Configure structlog to write redacted records to stderr."""
    renderer: Any = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(file=_CurrentStderr()),  # type: ignore[arg-type]
        cache_logger_on_first_use=False,
    )
