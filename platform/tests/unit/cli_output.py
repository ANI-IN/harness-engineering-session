"""Helpers for tests that read CLI output."""

from __future__ import annotations

import re

# CSI sequences (colour, bold, cursor) and OSC hyperlinks that rich or click may print.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(text: str) -> str:
    """`text` without ANSI escape sequences, so assertions do not depend on the terminal."""
    return _ANSI.sub("", text)
