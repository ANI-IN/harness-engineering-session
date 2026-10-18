from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
import typer
from pydantic import SecretStr
from typer.testing import CliRunner

from shipharness.ab import commands
from shipharness.config import Settings
from shipharness.reviewer import Review, ReviewOutcome
from shipharness.tracing import NullTracer

from ..fakes import fake_openai_key
from .test_demo import LINE, Clients, make_deps
from .test_referee import Factory, all_green
from .test_report import fixture_exports

COMMANDS = ["run", "review", "ab", "replay", "report", "experiments", "warm"]


def make_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """test app"""

    commands.register(app)
    return app


@pytest.fixture
def env(course_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    settings = Settings(
        _env_file=None,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
        shipharness_class_date="2026-10-20",
    )
    deps = make_deps(course_repo, tmp_path, Clients())
    deps.client_factory = lambda arm: Clients()(arm)
    review = Review(findings=[], tenant_isolation_risk="none", verdict="accept", summary="fine")
    reviews: list[Any] = []

    def reviewer(inp):  # type: ignore[no-untyped-def]
        reviews.append(inp)
        return ReviewOutcome(review=review, status="ok", cost_usd=0.001)

    runtime = SimpleNamespace(
        cost=deps.cost,
        course_repo=course_repo,
        tracer=NullTracer(),
        reviewer=reviewer,
        referee_sandbox_factory=Factory(all_green()),
        sandboxed=True,
        ab_deps=lambda ref, reviewer=True, **kw: deps,
    )
    monkeypatch.setattr(commands, "_settings", lambda: settings)
    # These tests drive the A/B logic offline with scripted clients; the live-client guard is
    # tested on its own in test_class_live_guard.py.
    monkeypatch.setattr(commands, "_live_guard", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(commands, "_runtime", lambda *a, **kw: runtime)
    dataset = tmp_path / "features.jsonl"
    dataset.write_text(json.dumps(LINE) + "\n", encoding="utf-8")
    return SimpleNamespace(settings=settings, dataset=dataset, reviews=reviews, tmp=tmp_path)


def test_register_adds_every_command() -> None:
    app = make_app()
    for name in COMMANDS:
        result = CliRunner().invoke(app, [name, "--help"])
        assert result.exit_code == 0, (name, result.output)


def test_report_command_reads_exports_and_prints_counts(tmp_path: Path) -> None:
    exports = fixture_exports(tmp_path)
    result = CliRunner().invoke(make_app(), ["report", "--exports", str(exports)])
    assert result.exit_code == 0, result.output
    # The score summary names the feature and the measure as people read them.
    assert (
        "Feature 1: Org-wide issue search; House rule 1: Tenant isolation, new violations: "
        "bare 2/3 failing, harness 1/3 failing"
    ) in result.output
    assert (exports / "report.html").exists()
    assert result.output.strip().splitlines()[-1].startswith("Cost: $")


def test_review_command_blinds_the_diff(env, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    diff = tmp_path / "d.patch"
    diff.write_text(
        "diff --git a/progress.md b/progress.md\n--- a/progress.md\n+++ b/progress.md\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n-a\n+b\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        make_app(), ["review", "--diff", str(diff), "--task", "Add a filter."]
    )
    assert result.exit_code == 0, result.output
    assert '"verdict": "accept"' in result.output
    [inp] = env.reviews
    assert "progress.md" not in inp.diff and "app/x.py" in inp.diff
    assert "Cost: $" in result.output


def test_ab_command_runs_both_arms_and_then_swap_and_replay(env) -> None:  # type: ignore[no-untyped-def]
    app = make_app()
    result = CliRunner().invoke(
        app, ["ab", "--feature", "F1", "--section", "demo-1", "--dataset", str(env.dataset)]
    )
    assert result.exit_code == 0, result.output
    assert "bare" in result.output and "harness" in result.output
    assert "Cost: $" in result.output
    ab_id = next(line.split()[1] for line in result.output.splitlines() if line.startswith("A/B "))

    swap = CliRunner().invoke(app, ["ab", "--swap", ab_id])
    assert swap.exit_code == 0, swap.output
    assert "identical" in swap.output

    replay = CliRunner().invoke(app, ["replay", ab_id])
    assert replay.exit_code == 0, replay.output
    assert "RECORDING" in replay.output and "Cost: $" in replay.output


def _one_line_error(result) -> str:  # type: ignore[no-untyped-def]
    assert result.exit_code == 2, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    lines = result.output.strip().splitlines()
    assert len(lines) == 1, result.output
    return lines[0]


@pytest.mark.parametrize("runs", ["empty", "no-section", "other-section"])
def test_swap_latest_without_a_match_is_one_line_with_a_hint(env, runs: str) -> None:  # type: ignore[no-untyped-def]
    root = Path(env.settings.runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    if runs != "empty":
        record = root / "ab-20261016-090000-aaaaaa" / "ab.json"
        record.parent.mkdir(parents=True)
        section = None if runs == "no-section" else "demo-1"
        record.write_text(json.dumps({"section": section, "arms": {}}), encoding="utf-8")
    result = CliRunner().invoke(make_app(), ["ab", "--swap", "latest", "--section", "demo-4"])
    line = _one_line_error(result)
    assert "demo-4" in line and "make demo-4" in line and "AB=<id>" in line


def test_swap_of_an_unknown_id_is_one_line(env) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(make_app(), ["ab", "--swap", "ab-nothing"])
    line = _one_line_error(result)
    assert "ab-nothing" in line


def test_swap_of_a_record_without_a_pinned_commit_is_refused(env) -> None:  # type: ignore[no-untyped-def]
    app = make_app()
    args = ["ab", "--feature", "F1", "--section", "demo-1", "--dataset", str(env.dataset)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    ab_id = next(line.split()[1] for line in result.output.splitlines() if line.startswith("A/B "))
    path = Path(env.settings.runs_dir) / ab_id / "ab.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["checkpoint_sha"]
    path.write_text(json.dumps(data), encoding="utf-8")
    for args in (["ab", "--swap", ab_id], ["replay", ab_id]):
        line = _one_line_error(CliRunner().invoke(app, args))
        assert "predates" in line


def test_ab_command_unknown_feature_exits_1(env) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(
        make_app(), ["ab", "--feature", "F9", "--dataset", str(env.dataset)]
    )
    assert result.exit_code == 1
    assert "no task" in result.output


@pytest.mark.parametrize("name", ["org-search", "ORG-SEARCH", "Org-Search", "f1", "F1"])
def test_ab_accepts_the_readable_name_or_the_code(env, name: str) -> None:  # type: ignore[no-untyped-def]
    args = ["ab", "--feature", name, "--section", "demo-1", "--no-preview"]
    result = CliRunner().invoke(make_app(), [*args, "--dataset", str(env.dataset)])
    assert result.exit_code == 0, result.output
    header = next(line for line in result.output.splitlines() if line.startswith("A/B "))
    assert "(Feature 1: Org-wide issue search, layers=" in header  # the course name
    scores = sorted(env.tmp.rglob("scores/*.json"))
    assert scores
    for path in scores:  # machine-readable records keep the code
        assert json.loads(path.read_text(encoding="utf-8"))["feature_id"] == "F1"


def test_ab_refuses_an_unknown_name_with_the_valid_names(env) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(
        make_app(), ["ab", "--feature", "versions", "--dataset", str(env.dataset)]
    )
    assert result.exit_code == 2
    text = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())  # the error box borders
    assert "versions" in text
    assert "version-checks (F4)" in text and "org-search (F1)" in text and "labels (F7)" in text
    assert "safe-retries (F3)" in text


@pytest.mark.parametrize("name", ["safe-retries", "Safe-Retries", "idempotent-create", "F3"])
def test_feature_3_takes_its_new_name_its_earlier_name_or_its_code(name: str) -> None:
    assert commands._feature_option(name) == "F3"


@pytest.mark.parametrize("command", ["ab", "run"])
def test_feature_help_names_the_aliases(command: str) -> None:
    group = typer.main.get_command(make_app())
    [option] = [p for p in group.commands[command].params if p.name == "feature"]  # type: ignore[attr-defined]
    assert "version-checks" in option.help and "bulk-close" in option.help
    assert "F4" in option.help
    assert "safe-retries" in option.help and "idempotent-create" in option.help


def test_run_command_accepts_the_readable_name(env, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shipharness.ab import demo

    seen: list[str] = []
    real = demo.run_arm

    def spy(task, *a, **kw):  # type: ignore[no-untyped-def]
        seen.append(task.feature_id)
        return real(task, *a, **kw)

    monkeypatch.setattr(demo, "run_arm", spy)
    ticket = tmp_path / "ticket.md"
    ticket.write_text("Add cursor pagination.", encoding="utf-8")
    args = ["run", "--feature", "Org-Search", "--checkpoint", "m1-s1-start"]
    result = CliRunner().invoke(
        make_app(), [*args, "--ticket-file", str(ticket), "--layers", "none"]
    )
    assert result.exit_code == 0, result.output
    assert seen == ["F1"]


def test_run_command_runs_one_arm(env, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ticket = tmp_path / "ticket.md"
    ticket.write_text("Add cursor pagination.", encoding="utf-8")
    result = CliRunner().invoke(
        make_app(),
        [
            "run",
            "--feature",
            "F1",
            "--checkpoint",
            "m1-s1-start",
            "--ticket-file",
            str(ticket),
            "--layers",
            "none",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("bare: completed")
    assert "Cost: $" in result.output


@pytest.mark.parametrize(("flag", "previews"), [([], True), (["--no-preview"], False)])
def test_ab_previews_can_be_turned_off_for_batch_runs(env, flag, previews) -> None:  # type: ignore[no-untyped-def]
    """Batch runs (pilot, experiments) need no board previews; the class demo keeps them."""
    seen: list[dict] = []
    runtime = commands._runtime(env.settings, "x")
    original = runtime.ab_deps

    def ab_deps(ref, reviewer=True, **kw):  # type: ignore[no-untyped-def]
        seen.append(kw)
        return original(ref, reviewer=reviewer, **kw)

    runtime.ab_deps = ab_deps
    args = ["ab", "--feature", "F1", "--section", "demo-1", "--dataset", str(env.dataset), *flag]
    result = CliRunner().invoke(make_app(), args)
    assert result.exit_code == 0, result.output
    assert ("preview_factory" in seen[0] and seen[0]["preview_factory"] is None) is (not previews)


# --- trace projects -------------------------------------------------------


def _record_targets(monkeypatch: pytest.MonkeyPatch, runtime_factory: Any) -> list[tuple]:  # type: ignore[type-arg]
    seen: list[tuple] = []  # type: ignore[type-arg]

    def runtime(settings, project, **kw):  # type: ignore[no-untyped-def]
        seen.append((project, kw.get("session_id")))
        return runtime_factory(settings, project, **kw)

    monkeypatch.setattr(commands, "_runtime", runtime)
    return seen


@pytest.mark.parametrize(
    ("purpose", "project", "session"),
    [
        ("pilot", "shipharness-pilot", "pilot"),
        ("assignment", "shipharness-assignments", "assignment"),
        ("class", "shipharness-class-2026-10-20", "2026-10-20"),
    ],
)
def test_ab_traces_to_the_project_for_its_purpose(
    env, monkeypatch, purpose, project, session
) -> None:  # type: ignore[no-untyped-def]
    seen = _record_targets(monkeypatch, commands._runtime)
    result = CliRunner().invoke(
        make_app(),
        [
            "ab",
            "--feature",
            "F1",
            "--purpose",
            purpose,
            "--no-preview",
            "--dataset",
            str(env.dataset),
        ],
    )
    assert result.exit_code in (0, 1), result.output
    assert seen and seen[0] == (project, session)


def test_class_commands_refuse_without_an_explicit_class_date(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(commands, "_settings", lambda: Settings(_env_file=None))
    result = CliRunner().invoke(
        make_app(), ["ab", "--feature", "F1", "--dataset", str(env.dataset)]
    )
    assert result.exit_code == 2
    assert "SHIPHARNESS_CLASS_DATE" in result.output and "--purpose pilot" in result.output


# --- no static class -----------------------------------------------------
# Every live A/B (make demo-N, make final, pilot runs) calls OpenAI. `shipharness ab` refuses before
# any arm starts when the key is missing or rejected, or when the runtime would use a stand-in model
# client; it never falls back. Replay stays the fallback and is always marked RECORDING.

REAL_GUARD = commands._live_guard  # the env fixture turns it off for offline A/B logic tests


def run_ab(env, *args: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(make_app(), ["ab", "--dataset", str(env.dataset), *args])


def with_key(env) -> Settings:  # type: ignore[no-untyped-def]
    return env.settings.model_copy(update={"openai_api_key": SecretStr(fake_openai_key())})


# The command paths of make demo-N, make final, and make show-N (the harness arm alone, class
# profile): every one refuses the same way before any arm starts.
LIVE_PATHS = {
    "demo-N": ["--section", "demo-1"],
    "final": ["--section", "final"],
    "show-N": ["--section", "demo-1", "--arms", "harness", "--profile", "class"],
}
live_paths = pytest.mark.parametrize("path", list(LIVE_PATHS.values()), ids=list(LIVE_PATHS))


@live_paths
def test_live_ab_refuses_without_an_openai_key(env, monkeypatch, path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(commands, "_live_guard", REAL_GUARD)
    monkeypatch.setattr(commands, "_settings", lambda: env.settings)  # no key in the fixture
    result = run_ab(env, "--feature", "F1", *path, "--no-preview")
    assert result.exit_code == 2, result.output
    assert "OPENAI_API_KEY" in result.output and "never" in result.output
    assert not list(Path(env.settings.runs_dir).glob("ab-*"))  # no arm started


@live_paths
def test_live_ab_refuses_a_stand_in_model_client(env, monkeypatch, path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(commands, "_live_guard", REAL_GUARD)
    monkeypatch.setattr(commands, "_settings", lambda: with_key(env))
    monkeypatch.setattr(commands, "_key_problem", lambda settings: None)
    result = run_ab(env, "--feature", "F1", *path, "--no-preview")  # scripted deps
    assert result.exit_code == 2, result.output
    assert "stand-in" in result.output
    assert not list(Path(env.settings.runs_dir).glob("ab-*"))


@live_paths
def test_live_ab_refuses_a_key_openai_rejects(env, monkeypatch, path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(commands, "_live_guard", REAL_GUARD)
    monkeypatch.setattr(commands, "_settings", lambda: with_key(env))
    monkeypatch.setattr(commands, "_key_problem", lambda s: "invalid key (AuthenticationError)")
    result = run_ab(env, "--feature", "F1", *path, "--no-preview")
    assert result.exit_code == 2
    assert "AuthenticationError" in result.output
    assert not list(Path(env.settings.runs_dir).glob("ab-*"))


def test_the_show_path_checks_the_client_of_the_arm_it_runs(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    asked: list[str] = []
    monkeypatch.setattr(commands, "_live_guard", lambda s, deps, arm="bare": asked.append(arm))
    result = run_ab(env, "--feature", "F1", *LIVE_PATHS["show-N"], "--no-preview")
    assert result.exit_code == 0, result.output
    assert asked == ["harness"]


def test_ab_profile_reaches_the_runtime_and_unknown_profiles_are_refused(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: list[dict] = []  # type: ignore[type-arg]
    original = commands._runtime

    def runtime(settings, project, **kw):  # type: ignore[no-untyped-def]
        seen.append(kw)
        return original(settings, project, **kw)

    monkeypatch.setattr(commands, "_runtime", runtime)
    for flag, profile in (([], "standard"), (["--profile", "class"], "class")):
        result = run_ab(env, "--feature", "F1", "--no-preview", *flag)
        assert result.exit_code in (0, 1), result.output
        assert seen[-1]["profile"] == profile
        assert f"profile={profile}" in result.output
    bad = run_ab(env, "--feature", "F1", "--profile", "turbo")
    assert bad.exit_code == 2 and "standard, class" in bad.output


def test_a_tier_the_prices_cannot_price_is_one_line_at_startup(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shipharness.ab.runtime import build_runtime

    monkeypatch.setattr(
        commands, "_runtime", lambda s, project, **kw: build_runtime(s, project=project, **kw)
    )
    monkeypatch.setattr(
        commands,
        "_settings",
        lambda: env.settings.model_copy(update={"openai_model": "gpt-5.6-luna"}),
    )
    result = run_ab(env, "--feature", "F1", "--profile", "class", "--purpose", "pilot")
    line = _one_line_error(result)
    assert "Fast" in line and "gpt-5.6-luna" in line


def test_key_problem_names_the_openai_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    response = httpx.Response(401, request=httpx.Request("GET", "https://api.openai.com/v1/models"))

    class Models:
        def retrieve(self, model: str) -> None:
            raise openai.AuthenticationError("rejected", response=response, body=None)

    class Client:
        models = Models()

    monkeypatch.setattr("shipharness.ab.clients.make_openai_client", lambda *a, **k: Client())
    settings = Settings(_env_file=None, openai_api_key=fake_openai_key())
    assert commands._key_problem(settings) == "invalid key (AuthenticationError)"


def test_the_runtime_builds_the_live_openai_client(tmp_path: Path) -> None:
    from shipharness.ab.runtime import build_runtime
    from shipharness.runner.model import OpenAIModelClient

    settings = Settings(
        _env_file=None,
        openai_api_key=fake_openai_key(),
        langsmith_tracing=False,
        runs_dir=tmp_path / "runs",
        sandbox_mode="none",
    )
    runtime = build_runtime(settings, project="shipharness-pilot", session_id="pilot")
    assert isinstance(runtime.client_factory("bare"), OpenAIModelClient)  # no network on build


def test_session_budget_override_reaches_both_arms_and_the_record(env) -> None:  # type: ignore[no-untyped-def]
    # Pre-registered F2 lever: first session 12 turns, total unchanged.
    result = CliRunner().invoke(
        make_app(),
        ["ab", "--feature", "F1", "--session-budget", "2,3", "--no-preview",
         "--dataset", str(env.dataset)],
    )  # fmt: skip
    assert result.exit_code in (0, 1), result.output
    ab_id = next(line.split()[1] for line in result.output.splitlines() if line.startswith("A/B "))
    record = json.loads((Path(env.settings.runs_dir) / ab_id / "ab.json").read_text())
    assert record["task"]["session_budget"] == [2, 3]
    assert {a["spec"]["session_budget"] == [2, 3] for a in record["arms"].values()} == {True}


def test_session_budget_override_rejects_bad_values(env) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(
        make_app(),
        ["ab", "--feature", "F1", "--session-budget", "12,x", "--dataset", str(env.dataset)],
    )
    assert result.exit_code == 2


def test_replay_traces_to_the_project_for_its_purpose(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen = _record_targets(monkeypatch, commands._runtime)
    result = CliRunner().invoke(make_app(), ["replay", "ab-none", "--purpose", "pilot"])
    assert result.exit_code == 2  # no such A/B; the runtime is never built for an unknown id
    seen.clear()
    first = CliRunner().invoke(
        make_app(), ["ab", "--feature", "F1", "--no-preview", "--dataset", str(env.dataset)]
    )
    ab_id = next(line.split()[1] for line in first.output.splitlines() if line.startswith("A/B "))
    seen.clear()
    replay = CliRunner().invoke(make_app(), ["replay", ab_id, "--purpose", "pilot"])
    assert replay.exit_code == 0, replay.output
    assert seen and seen[0] == ("shipharness-pilot", "pilot")


def test_warm_refuses_without_containers(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        commands, "_settings", lambda: env.settings.model_copy(update={"sandbox_mode": "none"})
    )
    line = _one_line_error(CliRunner().invoke(make_app(), ["warm"]))
    assert "SANDBOX_MODE=none" in line


def test_warm_passes_the_profile_and_runs_the_warm_up(env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shipharness.ab import warm

    seen: dict[str, Any] = {}
    original = commands._runtime

    def runtime(settings, project, **kw):  # type: ignore[no-untyped-def]
        seen["runtime"] = (settings.langsmith_tracing, kw)
        return original(settings, project, **kw)

    def warm_up(**kw):  # type: ignore[no-untyped-def]
        seen["warm"] = kw
        kw["echo"]("warm: done (0.0 s)")
        return True

    monkeypatch.setattr(commands, "_runtime", runtime)
    monkeypatch.setattr(warm, "warm_up", warm_up)
    result = CliRunner().invoke(make_app(), ["warm", "--profile", "standard", "--jobs", "2"])
    assert result.exit_code == 0, result.output
    assert seen["runtime"][0] is False  # warm-up never traces
    assert seen["runtime"][1]["profile"] == "standard"
    kw = seen["warm"]
    assert kw["images"] == ["shipharness-agent:1", "shipharness-referee:1"]
    assert kw["images_command"] == "make images RUNTIME=docker"
    assert [(t.section, t.task.feature_id) for t in kw["tasks"]][-1] == ("final", "F7")
    assert kw["jobs"] == 2
    assert "warm: done" in result.output and "Cost: $" in result.output
