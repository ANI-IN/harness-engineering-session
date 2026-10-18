from __future__ import annotations

import base64
import json
import re
import shlex
from pathlib import Path
from typing import Any

from shipharness.ab.referee import REFEREE_CHECKS, Referee, RefereeDeps, RefereeTask
from shipharness.events import EventBus, read_events
from shipharness.reviewer import Review, ReviewOutcome
from shipharness.runner.models import AgentRunResult
from shipharness.sandbox import ExecResult, FakeSandbox
from shipharness.tracing import read_exports

from ..verify.fakes import check_result, runner_output

PRODUCT = """diff --git a/app/api/issues.py b/app/api/issues.py
--- a/app/api/issues.py
+++ b/app/api/issues.py
@@ -1,2 +1,2 @@
 def list_issues():
-    return []
+    return ["filtered"]
diff --git a/tests/visible/test_issues_new.py b/tests/visible/test_issues_new.py
new file mode 100644
--- /dev/null
+++ b/tests/visible/test_issues_new.py
@@ -0,0 +1,6 @@
+def test_filtered():
+    assert True
+
+
+def test_second():
+    assert 1
"""
STATE = """diff --git a/progress.md b/progress.md
--- a/progress.md
+++ b/progress.md
@@ -1 +1,2 @@
 # Progress
+- did F1
"""
OUT_OF_SCOPE = """diff --git a/app/main.py b/app/main.py
--- a/app/main.py
+++ b/app/main.py
@@ -1,2 +1,2 @@
 def create_app():
-    return 'app'
+    return 'patched'
"""


def requested_checks(command: str) -> list[str]:
    argv = shlex.split(command)
    return argv[argv.index("--checks") + 1].split(",")


class Factory:
    def __init__(
        self, results: list[dict[str, Any]], failing: frozenset[str] = frozenset()
    ) -> None:
        self.results = results
        self.failing = failing  # shipped test ids that fail on the unmutated build
        self.calls: list[tuple[Path, list[Any], str]] = []
        self.sandboxes: list[FakeSandbox] = []

    def _exec(self, cmd: str) -> ExecResult:
        if "checks.runner" in cmd:
            asked = requested_checks(cmd)  # the runner answers only the checks it is asked for
            found = [r for r in self.results if r["check"] in asked]
            return ExecResult(exit_code=0, output=runner_output(found, command=cmd), duration_ms=1)
        if "-m pytest" in cmd:
            if any(t in cmd for t in self.failing):
                return ExecResult(exit_code=1, output="1 failed in 0.1s\n", duration_ms=1)
            return ExecResult(exit_code=0, output="1 passed in 0.1s\n", duration_ms=1)
        return ExecResult(exit_code=0, output="", duration_ms=1)

    def __call__(self, build: Path, mounts: list[Any], arm: str) -> FakeSandbox:
        self.calls.append((build, mounts, arm))
        box = FakeSandbox(self._exec)
        self.sandboxes.append(box)
        return box


def all_green(**overrides: dict[str, Any]) -> list[dict[str, Any]]:
    results = [check_result(c, seed=42) for c in REFEREE_CHECKS]
    by = {r["check"]: r for r in results}
    by["hidden_tests"]["total_probes"] = 4
    by["regression"]["total_probes"] = 20
    for name, value in overrides.items():
        by[name].update(value)
    return list(by.values())


def task(**kw: Any) -> RefereeTask:
    base: dict[str, Any] = dict(
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="Add cursor pagination to the issue list.",
        hidden_test_ids=["teamtrack/tests/hidden/f1/test_secret.py::test_secret"],
        allowed_paths={
            "build": ["app/api/issues.py", "tests/visible/**"],
            "test": ["tests/visible/**"],
        },
        primary_measure="r1_new_violations>=1",
    )
    base.update(kw)
    return RefereeTask(**base)


def deps(course_repo: Path, tmp_path: Path, factory: Factory, **kw: Any) -> RefereeDeps:
    base: dict[str, Any] = dict(
        course_repo=course_repo,
        checkpoint_ref="m1-s1-start",
        sandbox_factory=factory,
        exports_dir=tmp_path / "exports",
        base_dir=tmp_path / "referee",
        seed=42,
    )
    base.update(kw)
    return RefereeDeps(**base)


def result(status: str = "completed", claim: str = "done") -> AgentRunResult:
    return AgentRunResult(
        run_id="r-1",
        arm="harness",
        status=status,  # type: ignore[arg-type]
        claim=claim,  # type: ignore[arg-type]
        claim_summary="",
        sessions=[],
        phase_shas={},
        diff_path=None,
        cost_usd=0.05,
        turns_total=12,
        wall_s=80.0,
        trace_url="https://smith.example/t/1",
    )


def judge(referee: Referee, tmp_path: Path, diff: str, **kw: Any):  # type: ignore[no-untyped-def]
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        verdict = referee.judge(
            run_id=kw.pop("run_id", "r-1"),
            ab_id="ab-1",
            arm=kw.pop("arm", "harness"),
            layers=["instructions"],
            result=kw.pop("result", result()),
            diff=diff.encode(),
            bus=bus,
            **kw,
        )
    return verdict, list(read_events(log))


def test_referee_applies_only_product_changes(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    verdict, _ = judge(
        Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT + STATE
    )
    build = verdict.referee_dir / "build"
    assert '"filtered"' in (build / "app" / "api" / "issues.py").read_text(encoding="utf-8")
    assert (build / "tests" / "visible" / "test_issues_new.py").exists()
    assert not (build / "progress.md").exists()
    assert verdict.apply_error is None
    assert verdict.record.out_of_scope_files == 0


def test_a_relative_referee_dir_still_applies_the_patch(
    course_repo: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    # `git apply` runs inside the build folder; a relative product.patch path cannot be opened
    # from there, so the run was not judged ("can't open patch"). Bug fix, applies to both arms.
    monkeypatch.chdir(tmp_path)
    factory = Factory(all_green())
    referee = Referee(task(), deps(course_repo, tmp_path, factory, base_dir=Path("referee")))
    verdict, _ = judge(referee, tmp_path, PRODUCT)
    assert verdict.apply_error is None
    build = verdict.referee_dir / "build"
    assert '"filtered"' in (build / "app" / "api" / "issues.py").read_text(encoding="utf-8")
    assert verdict.record.hidden_total > 0


def test_hidden_tests_are_mounted_read_only_and_never_in_the_build(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    verdict, _ = judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    build, mounts, _arm = factory.calls[-1]
    assert not (build / "tests" / "hidden").exists()
    [(host, container, mode)] = [m for m in mounts if m[1] == "/work/tests/hidden"]
    assert mode == "ro" and (host / "f1" / "test_secret.py").exists()
    assert not str(host.resolve()).startswith(str(build.resolve()))


def test_runner_gets_the_fixed_seed_and_params(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    box = factory.sandboxes[-1]
    # Two runner calls: the primary measure's check (R1 for F1) first, then the rest.
    first, rest = [shlex.split(c) for c in box.commands if "checks.runner" in c]
    assert first[first.index("--checks") + 1] == "r1_tenant"
    asked = [
        *first[first.index("--checks") + 1].split(","),
        *rest[rest.index("--checks") + 1].split(","),
    ]
    assert sorted(asked) == sorted(REFEREE_CHECKS)
    for argv in (first, rest):
        assert argv[argv.index("--seed") + 1] == "42"
        assert "--baseline" in argv
    [params_cmd] = [c for c in box.commands if c.startswith("printf") and "params" in c]
    params = json.loads(base64.b64decode(params_cmd.split()[2]))
    assert params["hidden_dir"] == "tests/hidden"
    assert "progress.md" in params["harness_artifacts"]
    assert params["hidden_tests"] == ["teamtrack/tests/hidden/f1/test_secret.py::test_secret"]
    assert params["shipped_tests"] == [
        "tests/visible/test_issues_new.py::test_filtered",
        "tests/visible/test_issues_new.py::test_second",
    ]


def test_run_log_and_session_patches_are_mounted_read_only(
    course_repo: Path, tmp_path: Path
) -> None:
    run_log = tmp_path / "events.jsonl"
    sessions = []
    for i in (1, 2):
        sessions.append(tmp_path / f"s{i}.patch")
        sessions[-1].write_bytes(b"")
    factory = Factory(all_green())
    judge(
        Referee(task(), deps(course_repo, tmp_path, factory)),
        tmp_path,
        PRODUCT,
        run_log=run_log,
        session_patches=sessions,
    )
    _build, mounts, _arm = factory.calls[-1]
    by_target = {container: (host, mode) for host, container, mode in mounts}
    host, mode = by_target["/referee-in/session-2.patch"]
    assert mode == "ro" and host.read_bytes() == sessions[1].read_bytes()  # stripped copy
    assert by_target["/referee-in/events.jsonl"][1] == "ro"
    [params_cmd] = [
        c for c in factory.sandboxes[-1].commands if c.startswith("printf") and "params" in c
    ]
    params = json.loads(base64.b64decode(params_cmd.split()[2]))
    assert params["session_patches"] == [
        "/referee-in/session-1.patch",
        "/referee-in/session-2.patch",
    ]
    assert params["run_log"] == "/referee-in/events.jsonl"


def test_unsandboxed_fallback_copies_hidden_tests_into_the_referee_build(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    d = deps(course_repo, tmp_path, factory, container_paths=False, sandboxed=False)
    verdict, _ = judge(Referee(task(), d), tmp_path, PRODUCT)
    _build, mounts, _arm = factory.calls[-1]
    assert mounts == []
    assert (verdict.referee_dir / "build" / "tests" / "hidden" / "f1" / "test_secret.py").exists()
    assert verdict.record.sandboxed is False


def test_baseline_is_computed_once_for_both_arms(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    referee = Referee(task(), deps(course_repo, tmp_path, factory))
    judge(referee, tmp_path, PRODUCT, run_id="r-b", arm="bare")
    judge(referee, tmp_path, PRODUCT, run_id="r-h", arm="harness")
    assert len(factory.calls) == 3  # one baseline container, one per arm


def test_score_record_maps_check_results_and_is_exported(course_repo: Path, tmp_path: Path) -> None:
    results = all_green(
        r1_tenant={
            "new_violations": 2,
            "passed": False,
            "findings": [
                {
                    "rule": "R1",
                    "severity": "leak",
                    "endpoint": "GET /a",
                    "detail": "x",
                    "baseline": False,
                },
                {
                    "rule": "R1",
                    "severity": "violation",
                    "endpoint": "GET /b",
                    "detail": "y",
                    "baseline": False,
                },
            ],
        },
        hidden_tests={"new_violations": 1, "passed": False},
        flakiness={"new_violations": 1, "passed": False},
    )
    factory = Factory(results)
    verdict, events = judge(
        Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT
    )
    rec = verdict.record
    assert (rec.r1_new_violations, rec.r1_leaks) == (2, 1)
    assert (rec.hidden_passed, rec.hidden_total) == (3, 4)
    assert (rec.regression_passed, rec.regression_total) == (20, 20)
    assert rec.flaky_tests == 1 and rec.shipped_tests == 2
    assert rec.primary == {"r1_new_violations": 2} and rec.passed_primary is False
    assert rec.cost_usd == 0.05 and rec.turns_total == 12
    [exported] = read_exports("scores", tmp_path / "exports")
    assert exported["run_id"] == "r-1" and exported["r1_new_violations"] == 2
    types = [e.type for e in events]
    assert types.count("check_result") == len(REFEREE_CHECKS)
    assert "check_progress" in types and types[-1] == "verdict"
    verdict_event = events[-1]
    assert "agent said done" in verdict_event.data["summary"]


def test_aborted_runs_are_judged_and_kept(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    verdict, _ = judge(
        Referee(task(), deps(course_repo, tmp_path, factory)),
        tmp_path,
        "",
        result=result(status="ABORTED: cap", claim="none"),
    )
    assert verdict.record.status == "ABORTED: cap"
    assert verdict.record.passed_primary is True  # an empty diff leaks nothing; it is still a dot
    assert read_exports("scores", tmp_path / "exports")


def test_out_of_scope_and_test_phase_source_edits(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    t = task(primary_measure="out_of_scope_files>=1 or test_phase_source_edits>=1")
    verdict, _ = judge(
        Referee(t, deps(course_repo, tmp_path, factory)),
        tmp_path,
        PRODUCT + OUT_OF_SCOPE,
        test_phase_files=["app/api/issues.py", "tests/visible/test_issues_new.py", "progress.md"],
    )
    assert verdict.record.out_of_scope_files == 1
    assert verdict.record.test_phase_source_edits == 1
    assert verdict.record.passed_primary is False


def test_diff_that_does_not_apply_fails_closed(course_repo: Path, tmp_path: Path) -> None:
    broken = PRODUCT.replace(" def list_issues():", " def list_things():")
    assert broken != PRODUCT
    factory = Factory(all_green())
    verdict, events = judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, broken)
    assert verdict.apply_error is not None
    assert verdict.record.passed_primary is False
    assert "could not judge" in events[-1].data["summary"]


def test_reviewer_sees_a_blinded_diff_and_its_cost_is_recorded(
    course_repo: Path, tmp_path: Path
) -> None:
    seen = []
    review = Review(findings=[], tenant_isolation_risk="none", verdict="accept", summary="ok")

    def reviewer(inp):  # type: ignore[no-untyped-def]
        seen.append(inp)
        return ReviewOutcome(review=review, status="ok", cost_usd=0.004)

    factory = Factory(all_green())
    d = deps(course_repo, tmp_path, factory, reviewer=reviewer, grading_criteria="R1..R7")
    verdict, events = judge(Referee(task(), d), tmp_path, PRODUCT + STATE)
    [inp] = seen
    assert "progress.md" not in inp.diff and "app/api/issues.py" in inp.diff
    assert "harness" not in inp.model_dump_json()
    assert verdict.record.reviewer_verdict == "accept"
    assert verdict.record.reviewer_agrees is True
    assert verdict.record.review_cost_usd == 0.004
    assert any(e.type == "reviewer_output" for e in events)


def test_referee_mutants_run_against_shipped_tests(course_repo: Path, tmp_path: Path) -> None:
    calls = []

    def runner(mutant, tests, build, sandbox):  # type: ignore[no-untyped-def]
        calls.append((mutant["id"], tests))
        return "killed" if mutant["id"] == "issues-m1" else "survived"

    mutants = [{"id": "issues-m1"}, {"id": "issues-m2"}]
    factory = Factory(all_green())
    d = deps(course_repo, tmp_path, factory, mutants=mutants, mutant_runner=runner)
    verdict, events = judge(Referee(task(), d), tmp_path, PRODUCT)
    assert (verdict.record.mutants_killed, verdict.record.mutants_total) == (1, 2)
    assert calls[0][1] == [
        "tests/visible/test_issues_new.py::test_filtered",
        "tests/visible/test_issues_new.py::test_second",
    ]
    outcomes = [e.data for e in events if e.type == "mutant_result"]
    assert [o["set"] for o in outcomes] == ["referee", "referee"]


def test_runner_failure_is_reported_not_passed(course_repo: Path, tmp_path: Path) -> None:
    class Broken(Factory):
        def __call__(self, build, mounts, arm):  # type: ignore[no-untyped-def]
            self.calls.append((build, mounts, arm))
            return FakeSandbox(default=ExecResult(exit_code=1, output="Traceback\n", duration_ms=1))

    verdict, events = judge(
        Referee(task(), deps(course_repo, tmp_path, Broken([]))), tmp_path, PRODUCT
    )
    assert verdict.record.passed_primary is False
    assert "could not judge" in events[-1].data["summary"]


def test_both_arms_go_through_the_same_checks(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    referee = Referee(task(), deps(course_repo, tmp_path, factory))
    judge(referee, tmp_path, PRODUCT, run_id="r-b", arm="bare")
    judge(referee, tmp_path, PRODUCT, run_id="r-h", arm="harness")

    def normalised(command: str) -> str:
        if command.startswith("printf") and "params.json" in command:
            params = json.loads(base64.b64decode(command.split()[2]))
            params.pop("run_id")  # names the scored run, for the continuity count
            return "params " + json.dumps(params, sort_keys=True)
        return re.sub(r"--nonce \S+", "--nonce N", command)

    commands = [normalised(c) for box in factory.sandboxes[1:] for c in box.commands]
    # Identical commands for both arms, apart from the per-run nonce and the scored run id.
    assert len(set(commands)) == len(commands) // 2


def test_shipped_tests_failing_on_the_unmutated_build_never_kill_mutants(
    course_repo: Path, tmp_path: Path
) -> None:
    calls = []

    def runner(mutant, tests, build, sandbox):  # type: ignore[no-untyped-def]
        calls.append(tests)
        return "killed"  # a failing test "kills" every mutant

    second = "tests/visible/test_issues_new.py::test_second"
    factory = Factory(all_green(), failing=frozenset({second}))
    d = deps(course_repo, tmp_path, factory, mutants=[{"id": "m1"}], mutant_runner=runner)
    judge(Referee(task(), d), tmp_path, PRODUCT)
    assert calls == [["tests/visible/test_issues_new.py::test_filtered"]]


def test_all_shipped_tests_failing_means_every_mutant_survives(
    course_repo: Path, tmp_path: Path
) -> None:
    def runner(mutant, tests, build, sandbox):  # type: ignore[no-untyped-def]
        return "killed"

    ids = frozenset({"test_issues_new.py::test_filtered", "test_issues_new.py::test_second"})
    factory = Factory(all_green(), failing=ids)
    d = deps(course_repo, tmp_path, factory, mutants=[{"id": "m1"}], mutant_runner=runner)
    verdict, _ = judge(Referee(task(), d), tmp_path, PRODUCT)
    assert (verdict.record.mutants_killed, verdict.record.mutants_total) == (0, 1)


JUDGE_CONFIG = """diff --git a/conftest.py b/conftest.py
new file mode 100644
--- /dev/null
+++ b/conftest.py
@@ -0,0 +1,2 @@
+def pytest_runtest_makereport(item, call):
+    pass
diff --git a/tests/hidden/conftest.py b/tests/hidden/conftest.py
new file mode 100644
--- /dev/null
+++ b/tests/hidden/conftest.py
@@ -0,0 +1 @@
+FORCED = True
"""


def _referee_params(factory: Factory) -> dict[str, Any]:
    box = factory.sandboxes[-1]
    [cmd] = [c for c in box.commands if c.startswith("printf") and "params.json" in c]
    return json.loads(base64.b64decode(cmd.split()[2]))


def test_arm_changes_to_test_configuration_are_reverted_before_judging(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    verdict, _ = judge(
        Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, JUDGE_CONFIG
    )
    build = verdict.referee_dir / "build"
    assert verdict.apply_error is None
    assert not (build / "conftest.py").exists()
    assert not (build / "tests" / "hidden" / "conftest.py").exists()


def test_regression_expects_every_test_that_existed_at_the_checkpoint(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    params = _referee_params(factory)
    assert params["regression_expected"] == ["tests/visible/test_app.py::test_app"]


def test_shipped_tests_are_run_five_times_for_flakiness(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    assert _referee_params(factory)["flaky_runs"] == 5


def test_referee_tells_continuity_which_run_it_scores(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT, run_id="r-h7")
    assert _referee_params(factory)["run_id"] == "r-h7"


ADDS_FAILING_TESTS = """diff --git a/tests/visible/test_app.py b/tests/visible/test_app.py
--- a/tests/visible/test_app.py
+++ b/tests/visible/test_app.py
@@ -1,2 +1,6 @@
 def test_app():
     assert True
+
+
+def test_added_to_an_existing_file():
+    assert False
diff --git a/tests/visible/test_added.py b/tests/visible/test_added.py
new file mode 100644
--- /dev/null
+++ b/tests/visible/test_added.py
@@ -0,0 +1,2 @@
+def test_added_in_a_new_file():
+    assert False
"""


class LiveRegression(Factory):
    """Runs the real regression check in-process on the referee build with the params the
    referee sent; every other check is canned green."""

    def __init__(self) -> None:
        super().__init__(all_green())
        self.regression: list[dict[str, Any]] = []

    def __call__(self, build: Path, mounts: list[Any], arm: str) -> FakeSandbox:
        from shipharness.checks.runner import run_checks

        commands: list[str] = []

        def exec_(cmd: str) -> ExecResult:
            commands.append(cmd)
            if "checks.runner" not in cmd or "regression" not in requested_checks(cmd):
                return self._exec(cmd)
            [params_cmd] = [c for c in commands if c.startswith("printf") and "params" in c]
            params = json.loads(base64.b64decode(params_cmd.split()[2]))
            [real], _crashed = run_checks(
                build,
                ["regression"],
                checkpoint="m1-s1-start",
                feature_id="F1",
                seed=42,
                params=params,
            )
            dumped = real.model_dump(mode="json")
            self.regression.append(dumped)
            asked = requested_checks(cmd)
            results = [
                r if r["check"] != "regression" else dumped
                for r in all_green()
                if r["check"] in asked
            ]
            output = runner_output(results, command=cmd)
            return ExecResult(exit_code=0, output=output, duration_ms=1)

        self.calls.append((build, mounts, arm))
        box = FakeSandbox(exec_)
        self.sandboxes.append(box)
        return box


def test_regression_runs_only_the_tests_that_existed_at_the_checkpoint(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = LiveRegression()
    verdict, _ = judge(
        Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, ADDS_FAILING_TESTS
    )
    assert verdict.apply_error is None
    baseline, arm = factory.regression  # the clean checkpoint, then the arm's build
    assert arm["new_violations"] == 0 and arm["passed"] is True, arm["findings"]
    assert arm["total_probes"] == baseline["total_probes"] == 1
    assert (verdict.record.regression_passed, verdict.record.regression_total) == (1, 1)
    params = _referee_params(factory)
    assert params["regression_targets"] == ["tests/visible/test_app.py::test_app"]
    # The arm's added tests are judged by flakiness and mutants, not by regression.
    assert "tests/visible/test_app.py::test_added_to_an_existing_file" in params["shipped_tests"]
    assert "tests/visible/test_added.py::test_added_in_a_new_file" in params["shipped_tests"]


def test_default_params_leave_exemptions_to_the_adapter(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    assert "exemptions" not in _referee_params(factory)


def test_explicit_task_exemptions_are_passed_through(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    exempt = {"R4": ["POST /projects/{project_id}/issues"]}
    referee = Referee(task(exemptions=exempt), deps(course_repo, tmp_path, factory))
    judge(referee, tmp_path, PRODUCT)
    assert _referee_params(factory)["exemptions"] == exempt


def test_score_record_carries_the_checkpoint_commit(course_repo: Path, tmp_path: Path) -> None:
    import subprocess

    sha = subprocess.run(
        ["git", "rev-parse", "m1-s1-start^{commit}"],
        cwd=course_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    factory = Factory(all_green())
    verdict, _ = judge(Referee(task(), deps(course_repo, tmp_path, factory)), tmp_path, PRODUCT)
    assert verdict.record.checkpoint_sha == sha
    exported = read_exports("scores", tmp_path / "exports")
    assert {row["checkpoint_sha"] for row in exported} == {sha}


def test_working_tree_judging_records_no_checkpoint_commit(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    d = deps(course_repo, tmp_path, factory, checkpoint_ref=None)
    verdict, _ = judge(Referee(task(), d), tmp_path, PRODUCT)
    assert verdict.record.checkpoint_sha is None


def _baseline_calls(factory: Factory) -> int:
    return sum(1 for build, _m, _a in factory.calls if build.parent.name == "baseline")


def test_referee_baseline_is_cached_per_checkpoint_commit_and_task(
    course_repo: Path, tmp_path: Path
) -> None:
    factory = Factory(all_green())
    cache = tmp_path / "cache"
    one = Referee(task(), deps(course_repo, tmp_path / "a", factory, baseline_cache_dir=cache))
    two = Referee(task(), deps(course_repo, tmp_path / "b", factory, baseline_cache_dir=cache))
    assert one.baseline() is not None
    assert two.baseline() == one.baseline()
    assert _baseline_calls(factory) == 1  # the second A/B of the same task reuses the baseline
    other = Referee(
        task(hidden_test_ids=["tests/hidden/f1/test_secret.py::test_other"]),
        deps(course_repo, tmp_path / "c", factory, baseline_cache_dir=cache),
    )
    other.baseline()
    assert _baseline_calls(factory) == 2  # different task inputs, different key


def test_no_baseline_cache_for_working_tree_judging(course_repo: Path, tmp_path: Path) -> None:
    factory = Factory(all_green())
    cache = tmp_path / "cache"
    for name in ("a", "b"):
        d = deps(
            course_repo, tmp_path / name, factory, baseline_cache_dir=cache, checkpoint_ref=None
        )
        Referee(task(), d).baseline()
    assert _baseline_calls(factory) == 2


def test_session_patches_reach_continuity_without_harness_files(
    course_repo: Path, tmp_path: Path
) -> None:
    # M6 pilot run 2: the harness rewrites progress.md and session-handoff.md every session, and
    # the continuity check counted that as session 2 removing session 1's work.
    first = tmp_path / "s1.patch"
    first.write_text(STATE + PRODUCT, encoding="utf-8")
    second = tmp_path / "s2.patch"
    second.write_text(STATE, encoding="utf-8")
    factory = Factory(all_green())
    judge(
        Referee(task(), deps(course_repo, tmp_path, factory)),
        tmp_path,
        PRODUCT,
        run_log=tmp_path / "events.jsonl",
        session_patches=[first, second],
    )
    _build, mounts, _arm = factory.calls[-1]
    by_target = {container: host for host, container, _mode in mounts}
    one = by_target["/referee-in/session-1.patch"].read_text(encoding="utf-8")
    two = by_target["/referee-in/session-2.patch"].read_text(encoding="utf-8")
    assert "progress.md" not in one and "app/api/issues.py" in one
    assert two == ""
    assert "progress.md" in first.read_text(encoding="utf-8")  # the arm's record is unchanged


# --- batched unmutated-pass step (approved after pilot run 2) ---------------------------


def _batched_box(lines: dict[str, str], *, summary_only: bool = False) -> FakeSandbox:
    """A sandbox whose `-rA` pytest run reports `lines` (node id -> PASSED/FAILED); single-test
    runs pass unless the id is FAILED in `lines`."""

    def exec_(cmd: str) -> ExecResult:
        if "-rA" in cmd:
            if summary_only:
                return ExecResult(
                    exit_code=2, output="ERROR collecting\n1 error in 0.1s\n", duration_ms=1
                )
            body = "".join(f"{outcome} {node}\n" for node, outcome in lines.items())
            failed = sum(o != "PASSED" for o in lines.values())
            passed = len(lines) - failed
            return ExecResult(
                exit_code=1 if failed else 0,
                output=f"{body}{passed} passed, {failed} failed in 0.1s\n",
                duration_ms=1,
            )
        target = cmd.rsplit('"', 2)[-2]
        if lines.get(target) == "FAILED":
            return ExecResult(exit_code=1, output="1 failed in 0.1s\n", duration_ms=1)
        return ExecResult(exit_code=0, output="1 passed in 0.1s\n", duration_ms=1)

    return FakeSandbox(exec_)


def test_unmutated_pass_step_runs_all_shipped_tests_in_one_process() -> None:
    a, b = "tests/visible/test_x.py::test_a", "tests/visible/test_x.py::test_b"
    box = _batched_box({a: "PASSED", b: "FAILED"})
    assert Referee._passing_unmutated(box, [a, b]) == [a]
    assert sum("-m pytest" in c for c in box.commands) == 1


def test_a_shipped_file_passes_only_if_every_test_in_it_passes() -> None:
    file = "tests/visible/test_x.py"
    good, bad = "tests/visible/test_y.py", "tests/visible/test_x.py::test_b"
    box = _batched_box({f"{file}::test_a": "PASSED", bad: "FAILED", f"{good}::test_c": "PASSED"})
    assert Referee._passing_unmutated(box, [file, good]) == [good]


def test_ids_without_a_batched_outcome_fall_back_to_isolated_runs() -> None:
    a, b = "tests/visible/test_x.py::test_a", "tests/visible/test_x.py::test_b"
    box = _batched_box({a: "PASSED", b: "FAILED"}, summary_only=True)
    assert Referee._passing_unmutated(box, [a, b]) == [a]
    assert sum("-m pytest" in c for c in box.commands) == 3  # one batch, then one per test
