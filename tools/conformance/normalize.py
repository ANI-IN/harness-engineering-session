"""Output normalization for cross-stack conformance.

"Byte-identical" across Python and TypeScript is only meaningful after a
defined normalization pass. This module IS that definition; it is part of the
parity contract (docs/conventions.md). Any divergence normalization cannot
absorb is a spec bug in the unit, never a runner setting.

Normalization rules, applied in order:
1. Line endings: CRLF and CR become LF.
2. Trailing whitespace on every line is stripped.
3. The output ends with exactly one trailing newline (unless it is empty).
4. JSON content (detected or declared) is re-serialized canonically:
   sorted keys, 2-space indent, no trailing spaces.
5. Path separators inside JSON string values and text lines are normalized
   to POSIX ("/").
6. Floats inside JSON are formatted with repr-shortest form via Python's
   json module after round-tripping; text-mode floats are left untouched
   (units that print floats must format them explicitly per their SPEC.md).
"""

from __future__ import annotations

import json
from typing import Any

_WINDOWS_SEP = "\\"
_POSIX_SEP = "/"


def normalize_lines(text: str) -> str:
    """Rules 1-3: newlines, trailing whitespace, final newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = normalized.rstrip("\n")
    if normalized:
        normalized += "\n"
    return normalized


def normalize_paths_in_text(text: str) -> str:
    """Rule 5 for plain text: backslash path separators become POSIX."""
    return text.replace(_WINDOWS_SEP, _POSIX_SEP)


def _normalize_json_value(value: Any) -> Any:
    """Recursively normalize path separators inside JSON string values."""
    if isinstance(value, str):
        return normalize_paths_in_text(value)
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_json_value(val) for key, val in value.items()}
    return value


def normalize_json(text: str) -> str:
    """Rule 4 + 6: canonical JSON serialization (sorted keys, 2-space indent)."""
    parsed = json.loads(text)
    parsed = _normalize_json_value(parsed)
    return json.dumps(parsed, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def looks_like_json(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith(("{", "[")) and stripped.endswith(("}", "]"))


def normalize(text: str, *, kind: str = "auto") -> str:
    """Normalize an output payload.

    kind: "json" forces canonical JSON, "text" forces plain-text rules,
    "auto" canonicalizes as JSON when the payload parses as JSON.
    """
    if kind not in ("auto", "json", "text"):
        raise ValueError(f"unknown normalization kind: {kind!r}")
    if kind == "json" or (kind == "auto" and looks_like_json(text)):
        try:
            return normalize_json(text)
        except json.JSONDecodeError:
            if kind == "json":
                raise
    return normalize_lines(normalize_paths_in_text(text))
