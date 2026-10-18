"""Building pytest commands for the sandbox and reading their output.

Test ids come from agent-written files, so they are hostile: only ids made of a safe character set
are ever placed on a command line.
"""

from __future__ import annotations

import re

SAFE_TEST_ID = re.compile(r"^[A-Za-z0-9_./\-]+(::[A-Za-z0-9_.\-\[\]]+)*$")
PYTEST_FLAGS = "-q -p no:cacheprovider --no-header -rfE"
DOCTEST_FLAG = "--doctest-modules"
_SUMMARY = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b")
_SUMMARY_LINE = re.compile(r"\d+ (passed|failed|errors?|skipped|xfailed|xpassed).* in [\d.]+s")
_SHORT = re.compile(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$")
_COLLECTED = re.compile(r"(\d+) tests? collected")


class UnsafeTestId(ValueError):
    """A test id with characters that could change the meaning of a shell command."""


def check_test_id(test_id: str) -> str:
    if not SAFE_TEST_ID.match(test_id) or ".." in test_id.split("::")[0].split("/"):
        raise UnsafeTestId(f"unsafe test id: {test_id[:120]!r}")
    return test_id


def pytest_command(
    python: str, targets: list[str], extra: str = "", *, doctest_modules: bool = False
) -> str:
    """`<python> -m pytest <flags> "<target>" ...`; every target is checked first.

    `doctest_modules` adds `--doctest-modules`, for runs of the existing suite whose baseline
    includes doctests; generated candidate tests never get it."""
    quoted = " ".join(f'"{check_test_id(t)}"' for t in targets)
    doctests = DOCTEST_FLAG if doctest_modules else ""
    parts = [python, "-m pytest", PYTEST_FLAGS, extra, doctests, quoted]
    return " ".join(part for part in parts if part)


def counts(output: str) -> dict[str, int]:
    """Totals from the pytest summary line (`3 passed, 1 failed in 0.2s`)."""
    totals = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for line in output.splitlines():
        if not _SUMMARY_LINE.search(line):
            continue
        for number, word in _SUMMARY.findall(line):
            key = "errors" if word.startswith("error") else word
            if key in totals:
                totals[key] = int(number)
    return totals


def collected(output: str) -> int:
    match = _COLLECTED.search(output)
    if match:
        return int(match.group(1))
    return sum(1 for line in output.splitlines() if "::" in line and " " not in line.strip())


def first_failure(output: str) -> tuple[str | None, str]:
    """(node id, message) of the first FAILED/ERROR line in the short summary."""
    for line in output.splitlines():
        match = _SHORT.match(line.strip())
        if match:
            return match.group(2), (match.group(3) or "").strip()
    return None, ""


def error_excerpt(output: str, limit: int = 300) -> str:
    """The most useful single line of a failing pytest run, for discard reasons."""
    node, message = first_failure(output)
    if message:
        return f"{node}: {message}"[:limit]
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("E ") and len(text) > 2:
            return text[2:].strip()[:limit]
    for line in output.splitlines():
        text = line.strip()
        if text.startswith(("ERROR", "FAILED")) or "Error" in text:
            return text[:limit]
    tail = [line.strip() for line in output.splitlines() if line.strip()]
    return (tail[-1] if tail else "no output")[:limit]
