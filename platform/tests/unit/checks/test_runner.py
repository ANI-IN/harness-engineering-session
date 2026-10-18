"""The check runner (I-1): JSON on stdout, JSON progress on stderr, baselines, exit codes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.checks import CheckContext, CheckResult, register_check
from shipharness.checks.base import make_result
from shipharness.checks.runner import exit_code, resolve_names, run_checks
from shipharness.checks.scores import score_fields

ALL_RULES = "r1_tenant,r2_roles,r3_conventions,r4_idempotency,r5_audit,r6_layering,r7_migrations"


def runner(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "shipharness.checks.runner", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        check=False,
        timeout=600,
    )


@pytest.fixture(scope="module")
def base_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    from tests.unit.checks.seeds import copy_teamtrack

    build = copy_teamtrack(tmp_path_factory.mktemp("runner") / "teamtrack")
    params = tmp_path_factory.mktemp("params") / "params.json"
    params.write_text(json.dumps({"board_mode": "html", "r3_max_examples": 5}), encoding="utf-8")
    proc = runner(
        "--build", str(build), "--checks", f"{ALL_RULES},board", "--checkpoint", "m1-base",
        "--feature", "F1", "--seed", "5", "--params", str(params),
    )  # fmt: skip
    return proc, build


def test_teamtrack_base_has_no_new_violations_except_the_legacy_r1_leak(
    base_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    proc, _build = base_run
    results = [CheckResult.model_validate(r) for r in json.loads(proc.stdout)["results"]]
    assert [r.check for r in results] == [*ALL_RULES.split(","), "board"]
    failing = {
        r.check: [(f.endpoint, f.severity) for f in r.findings if f.counted] for r in results
    }
    assert failing.pop("r1_tenant") == [("GET /v1/issues", "leak")]
    assert all(found == [] for found in failing.values()), failing
    assert proc.returncode == 3
    fields = score_fields(results)
    assert fields["r1_leaks"] == 1
    assert fields["r6_ok"] is True and fields["r7_ok"] is True


def test_progress_lines_on_stderr_are_json(
    base_run: tuple[subprocess.CompletedProcess[str], Path],
) -> None:
    proc, _build = base_run
    progress = []
    for line in proc.stderr.splitlines():
        if line.startswith('{"check"'):
            progress.append(json.loads(line))
    assert {p["check"] for p in progress} >= {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "board"}
    assert all(set(p) == {"check", "done", "total", "label"} for p in progress)


def test_baseline_marks_the_legacy_leak_and_exits_zero(
    base_run: tuple[subprocess.CompletedProcess[str], Path], tmp_path: Path
) -> None:
    proc, build = base_run
    baseline = tmp_path / "baseline.json"
    baseline.write_text(proc.stdout, encoding="utf-8")
    again = runner(
        "--build", str(build), "--checks", "R1", "--checkpoint", "m1-base", "--feature", "F1",
        "--baseline", str(baseline),
    )  # fmt: skip
    assert again.returncode == 0, again.stderr[-2000:]
    (r1,) = json.loads(again.stdout)["results"]
    assert r1["new_violations"] == 0
    assert r1["baseline_violations"] == 1
    assert r1["findings"][0]["baseline"] is True


def test_unknown_check_is_an_error(tmp_path: Path) -> None:
    proc = runner(
        "--build", str(tmp_path), "--checks", "r9_magic", "--checkpoint", "m1-base",
        "--feature", "F1",
    )  # fmt: skip
    assert proc.returncode == 1
    assert "unknown check" in proc.stderr


def test_rule_labels_resolve_to_check_names() -> None:
    assert resolve_names("R1,r2_roles,hidden,scope") == [
        "r1_tenant",
        "r2_roles",
        "hidden_tests",
        "diff_scope",
    ]


@register_check
class _Exploding:
    name = "exploding_check_for_test"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        raise RuntimeError("boom")


@register_check
class _Clean:
    name = "clean_check_for_test"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        assert ctx.exemptions == {"R3": ["GET /v1/issues"]}  # adapter default after F3
        ctx.progress(1, 1, "clean")
        return make_result(self.name, [], total_probes=1, started=0.0)


def test_a_crashing_check_becomes_an_error_result(tmp_path: Path) -> None:
    seen: list[tuple[str, int, int, str]] = []
    results, crashed = run_checks(
        tmp_path,
        ["exploding_check_for_test", "clean_check_for_test"],
        checkpoint="m1-s4-start",
        feature_id="F4",
        seed=0,
        progress=lambda *args: seen.append(args),
    )
    assert crashed is True
    assert results[0].findings[0].severity == "error"
    assert "boom" in results[0].findings[0].detail
    assert results[1].passed is True
    assert seen == [("clean_check_for_test", 1, 1, "clean")]
    assert exit_code(results, crashed) == 1
    assert exit_code(results[1:], False) == 0


def test_results_document_echoes_the_nonce(tmp_path: Path) -> None:
    proc = runner(
        "--build", str(tmp_path), "--checks", "r7_migrations", "--checkpoint", "m1-base",
        "--feature", "F1", "--nonce", "n-42",
    )  # fmt: skip
    assert json.loads(proc.stdout)["nonce"] == "n-42"
