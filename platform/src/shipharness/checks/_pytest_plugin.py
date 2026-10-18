"""pytest plugin loaded with `-p`: writes one JSON line per test outcome to a report file.

The file path comes from SHIPHARNESS_PYTEST_REPORT. Outcomes: passed, failed, skipped, error
(setup or teardown failed), and collect_error for a module that does not import.
"""

from __future__ import annotations

import json
import os
from typing import Any


def _write(record: dict[str, Any]) -> None:
    path = os.environ.get("SHIPHARNESS_PYTEST_REPORT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


def pytest_runtest_logreport(report: Any) -> None:
    if report.when == "call" or (report.when == "setup" and not report.passed):
        outcome = "error" if report.when == "setup" and report.failed else report.outcome
        _write({"nodeid": report.nodeid, "outcome": outcome, "when": report.when})
    elif report.when == "teardown" and report.failed:
        _write({"nodeid": report.nodeid, "outcome": "error", "when": "teardown"})


def pytest_collectreport(report: Any) -> None:
    if report.failed:
        _write({"nodeid": report.nodeid, "outcome": "collect_error", "when": "collect"})
