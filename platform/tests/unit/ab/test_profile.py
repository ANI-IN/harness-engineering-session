"""Run profiles: `class` makes live class runs fast and is identical for both
arms (reasoning effort low, 2 CPUs per arm and referee container, OpenAI Fast tier for the agent
arms, a 420 s agent time limit; the reviewer keeps its own effort and the standard tier).
`standard` keeps the settings as loaded (300 s) and is the default everywhere except the class
make targets."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from shipharness.ab.demo import ABTask, arm_specs
from shipharness.ab.runtime import build_runtime
from shipharness.config import Settings
from shipharness.config.profiles import PROFILES, apply_profile
from shipharness.reviewer import Review, ReviewInput
from shipharness.sandbox import DockerSandbox, default_policy

from ..fakes import fake_openai_key


def settings(tmp_path: Path, **kw: Any) -> Settings:
    base: dict[str, Any] = dict(
        _env_file=None,
        openai_api_key=fake_openai_key(),
        langsmith_tracing=False,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    base.update(kw)
    return Settings(**base)


def test_the_two_profiles_and_their_values() -> None:
    assert set(PROFILES) == {"standard", "class"}
    assert PROFILES["standard"] == {}
    assert PROFILES["class"] == {
        "openai_reasoning_effort": "low",
        "openai_service_tier": "fast",
        "sandbox_cpus": 2.0,
        "run_timeout_s": 420,
        "harness_timeout_s": 900,
    }


def test_standard_keeps_the_loaded_settings(tmp_path: Path) -> None:
    loaded = settings(tmp_path, openai_reasoning_effort="high", openai_service_tier="flex")
    assert apply_profile(loaded, "standard") == loaded


def test_class_sets_low_effort_fast_tier_two_cpus_420_s_and_nothing_else(tmp_path: Path) -> None:
    loaded = settings(tmp_path)
    assert loaded.run_timeout_s == 300  # standard keeps 300 s
    assert loaded.harness_timeout_s == 120  # standard keeps 120 s of harness work
    applied = apply_profile(loaded, "class")
    assert applied.openai_reasoning_effort == "low"
    assert applied.openai_service_tier == "fast"
    assert applied.sandbox_cpus == 2.0
    assert applied.run_timeout_s == 420  # fits the 25-minute class window
    # Harness work (handoff test runs, gates, test filters) gets its own 900 s: at 120 s it cut
    # harness arms in session-end work (show-2 and demo-3 on 2026-10-18, the final on 2026-10-17),
    # and show-4's test filters alone took 572 s of harness work on 2026-10-18.
    assert applied.harness_timeout_s == 900
    # The reviewer's own settings and everything else stay as loaded.
    assert applied.openai_eval_reasoning_effort == loaded.openai_eval_reasoning_effort
    assert applied.openai_eval_model == loaded.openai_eval_model
    changed = {k for k in Settings.model_fields if getattr(applied, k) != getattr(loaded, k)}
    assert changed == {
        "openai_reasoning_effort",
        "openai_service_tier",
        "sandbox_cpus",
        "run_timeout_s",
        "harness_timeout_s",
    }


def test_an_unknown_profile_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="standard, class"):
        apply_profile(settings(tmp_path), "turbo")


def test_policy_cpus_come_from_the_settings(tmp_path: Path) -> None:
    assert default_policy(settings(tmp_path)).cpus == 1.0  # standard: today's limit
    assert default_policy(settings(tmp_path, sandbox_cpus=2.0)).cpus == 2.0


@pytest.mark.parametrize(("profile", "cpus"), [("standard", 1.0), ("class", 2.0)])
def test_the_runtime_applies_the_profile_to_every_container(
    tmp_path: Path, profile: str, cpus: float
) -> None:
    rt = build_runtime(settings(tmp_path), project="p", session_id="pilot", profile=profile)
    boxes = [
        rt.sandbox_factory("bare", tmp_path, None, "r-1"),  # type: ignore[arg-type]
        rt.sandbox_factory("harness", tmp_path, None, "r-2"),  # type: ignore[arg-type]
        rt.referee_sandbox_factory(tmp_path, [], "bare"),
        rt.referee_sandbox_factory(tmp_path, [], "harness"),
    ]
    assert all(isinstance(b, DockerSandbox) for b in boxes)
    assert {b.policy.cpus for b in boxes} == {cpus}  # type: ignore[attr-defined]
    assert f"cpus: {cpus}" in rt.policy_summary
    assert rt.profile == profile
    assert rt.ab_deps("m1-s1-start").profile == profile


def test_class_agent_arms_are_identical_and_the_reviewer_keeps_its_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The runtime's ledger is .shipharness/ledger.jsonl in the working directory: use a fresh one,
    # so the machine's real pilot spend can neither cap this review nor receive its entry.
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []
    review = Review(findings=[], tenant_isolation_risk="none", verdict="accept", summary="ok")

    class Responses:
        def parse(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            usage = SimpleNamespace(input_tokens=10, output_tokens=2)
            return SimpleNamespace(output_parsed=review, status="completed", usage=usage, output=[])

    fake = SimpleNamespace(responses=Responses())
    monkeypatch.setattr("shipharness.ab.runtime.make_openai_client", lambda *a, **k: fake)
    rt = build_runtime(settings(tmp_path), project="p", session_id="pilot", profile="class")
    task = ABTask("F1", "m1-s1-start", "Add pagination.")
    specs = arm_specs(
        task,
        rt.settings,
        ab_id="ab-1",
        harness_layers=frozenset({"instructions"}),
        workspaces={"bare": tmp_path / "b", "harness": tmp_path / "h"},
        run_ids={"bare": "r-1", "harness": "r-2"},
        profile=rt.profile,
    )
    for spec in specs.values():
        assert (spec.reasoning_effort, spec.service_tier, spec.profile) == ("low", "fast", "class")
        assert spec.run_timeout_s == 420
        assert spec.public_dict()["run_timeout_s"] == 420  # ab.json arms.<arm>.spec records it
    outcome = rt.reviewer(ReviewInput(task="t", diff="d", grading_criteria="R1"))
    assert outcome.status == "ok"
    assert calls[0]["reasoning"] == {"effort": "medium"}  # OPENAI_EVAL_REASONING_EFFORT
    assert "service_tier" not in calls[0]


@pytest.mark.parametrize(("profile", "limit"), [("standard", 120), ("class", 900)])
def test_the_runner_gets_the_profile_harness_time_limit(
    tmp_path: Path, profile: str, limit: int
) -> None:
    rt = build_runtime(settings(tmp_path), project="p", session_id="pilot", profile=profile)
    assert rt.ab_deps("m1-s1-start").settings.harness_timeout_s == limit


@pytest.mark.parametrize(("profile", "limit"), [("standard", 300), ("class", 420)])
def test_both_arm_specs_record_the_agent_time_limit(
    tmp_path: Path, profile: str, limit: int
) -> None:
    applied = apply_profile(settings(tmp_path), profile)
    specs = arm_specs(
        ABTask("F1", "m1-s1-start", "Add pagination."),
        applied,
        ab_id="ab-1",
        harness_layers=frozenset({"instructions"}),
        workspaces={"bare": tmp_path / "b", "harness": tmp_path / "h"},
        run_ids={"bare": "r-1", "harness": "r-2"},
        profile=profile,
    )
    assert {spec.run_timeout_s for spec in specs.values()} == {limit}
