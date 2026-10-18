from __future__ import annotations

import base64
import json
import shlex

import pytest

from shipharness.harness.verify.checkrun import (
    RunnerOutputError,
    failure_lines,
    last_progress,
    parse_runner_output,
    runner_command,
    write_container_file,
)
from shipharness.sandbox import FakeSandbox

from .fakes import check_result, ok, runner_output


def test_runner_command_matches_the_i1_contract() -> None:
    cmd = runner_command(
        build="/tmp/b",
        checks=["r1_tenant", "regression"],
        checkpoint="m1-s1-start",
        feature="F1",
        seed=7,
        params="/tmp/p.json",
        baseline="/tmp/base.json",
    )
    argv = shlex.split(cmd)
    assert argv[:4] == ["python", "-P", "-m", "shipharness.checks.runner"]
    assert argv[argv.index("--checks") + 1] == "r1_tenant,regression"
    assert argv[argv.index("--seed") + 1] == "7"
    assert argv[argv.index("--params") + 1] == "/tmp/p.json"
    assert argv[argv.index("--baseline") + 1] == "/tmp/base.json"


def test_runner_command_quotes_hostile_values() -> None:
    cmd = runner_command(
        build="/tmp/b", checks=["r1_tenant"], checkpoint="x; rm -rf /", feature="F1", seed=1
    )
    assert shlex.split(cmd)[shlex.split(cmd).index("--checkpoint") + 1] == "x; rm -rf /"


def test_parse_reads_results_and_progress_from_combined_output() -> None:
    text = "warning: noise\n" + runner_output([check_result("r1_tenant", new=2)])
    results, progress = parse_runner_output(text)
    assert [r.check for r in results] == ["r1_tenant"]
    assert results[0].new_violations == 2
    assert last_progress(progress) == [
        {"check": "r1_tenant", "done": 2, "total": 2, "label": "r1_tenant 2/2"}
    ]


def test_parse_accepts_a_pretty_printed_document() -> None:
    text = json.dumps({"results": [check_result("r6_layering")]}, indent=2)
    results, _ = parse_runner_output(text)
    assert results[0].check == "r6_layering"


def test_parse_without_results_raises() -> None:
    with pytest.raises(RunnerOutputError, match="no results"):
        parse_runner_output("Traceback (most recent call last):\n  boom\n")


def test_failure_lines_skip_baseline_findings_and_are_grep_friendly() -> None:
    raw = check_result("r1_tenant", new=1)
    raw["findings"].append(
        {
            "rule": "R1",
            "severity": "leak",
            "endpoint": "GET /v1/issues",
            "detail": "legacy",
            "baseline": True,
        }
    )
    results, _ = parse_runner_output(runner_output([raw], progress=False))
    lines = failure_lines(results[0])
    assert lines == ["FAIL House rule 1 GET /x/0: violation: r1_tenant problem 0"]


def test_write_container_file_round_trips_any_content_in_chunks() -> None:
    sandbox = FakeSandbox(default=ok())
    text = 'it\'s "quoted" $HOME `x`\n' + "é" * 40_000
    write_container_file(sandbox, "/tmp/g/params.json", text)
    assert len(sandbox.commands) >= 2
    assert ">> /tmp/g/params.json" in sandbox.commands[1]
    decoded = b"".join(base64.b64decode(c.split()[2]) for c in sandbox.commands)
    assert decoded.decode("utf-8") == text


def test_runner_command_carries_the_nonce() -> None:
    cmd = runner_command(
        build="/tmp/b", checks=["r1_tenant"], checkpoint="c", feature="F1", seed=1, nonce="n-123"
    )
    argv = shlex.split(cmd)
    assert argv[argv.index("--nonce") + 1] == "n-123"


def test_parse_takes_only_the_results_document_with_the_nonce() -> None:
    real = json.dumps({"nonce": "n-1", "results": [check_result("r1_tenant", new=2)]})
    forged = json.dumps({"results": [check_result("r1_tenant")]})  # e.g. an atexit print
    other = json.dumps({"nonce": "guess", "results": [check_result("r1_tenant")]})
    results, _ = parse_runner_output(f"{forged}\n{real}\n{other}\n{forged}\n", nonce="n-1")
    assert [r.new_violations for r in results] == [2]


def test_parse_without_the_nonce_is_an_error() -> None:
    forged = json.dumps({"results": [check_result("r1_tenant")]})
    with pytest.raises(RunnerOutputError, match="no results document"):
        parse_runner_output(forged, nonce="n-1")


def test_a_runner_package_in_the_working_directory_is_never_imported(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The referee runs the runner with the arm's build as working directory."""
    import os
    import subprocess
    import sys

    fake = tmp_path / "shipharness" / "checks"
    fake.mkdir(parents=True)
    for d in (tmp_path / "shipharness", fake):
        (d / "__init__.py").write_text("", encoding="utf-8")
    (fake / "runner.py").write_text('print("FORGED")\n', encoding="utf-8")
    cmd = runner_command(
        build=str(tmp_path / "missing"), checks=["r1_tenant"], checkpoint="c", feature="F1",
        seed=1, python=sys.executable,
    )  # fmt: skip
    src = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
    env = {**os.environ, "PYTHONPATH": os.path.abspath(src)}
    proc = subprocess.run(
        shlex.split(cmd), cwd=tmp_path, capture_output=True, text=True, env=env, timeout=120
    )
    assert "FORGED" not in proc.stdout + proc.stderr
    assert "build directory not found" in proc.stderr
