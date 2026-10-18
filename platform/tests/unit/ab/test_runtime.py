from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.ab.runtime import build_runtime, cost_line
from shipharness.config import Settings
from shipharness.sandbox import DockerSandbox, LocalSandbox

from ..fakes import fake_openai_key


def settings(**kw: object) -> Settings:
    return Settings(_env_file=None, langsmith_tracing=False, **kw)  # type: ignore[arg-type]


def test_docker_mode_gives_docker_sandboxes_with_referee_mounts(tmp_path: Path) -> None:
    rt = build_runtime(settings(), project="p")
    assert rt.sandboxed
    arm = rt.sandbox_factory("bare", tmp_path, None, "r-1")  # type: ignore[arg-type]
    assert isinstance(arm, DockerSandbox) and arm.image == "shipharness-agent:1"
    referee = rt.referee_sandbox_factory(tmp_path, [(tmp_path, "/work/tests/hidden", "ro")], "bare")
    assert isinstance(referee, DockerSandbox) and referee.image == "shipharness-referee:1"
    assert referee.extra_mounts == [(tmp_path, "/work/tests/hidden", "ro")]
    assert referee.bus is None


def test_no_docker_mode_is_labelled_unsandboxed(tmp_path: Path) -> None:
    rt = build_runtime(settings(sandbox_mode="none"), project="p")
    assert not rt.sandboxed
    assert isinstance(rt.sandbox_factory("bare", tmp_path, None, "r-1"), LocalSandbox)  # type: ignore[arg-type]
    deps = rt.ab_deps("m1-s1-start")
    assert deps.sandboxed is False and deps.container_paths is False


def test_openai_client_is_built_lazily_with_no_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", fake_openai_key())
    rt = build_runtime(settings(), project="p")
    client = rt.client_factory("bare")
    assert client.client.max_retries == 0  # type: ignore[attr-defined]
    assert rt.client_factory("harness").client is client.client  # type: ignore[attr-defined]


def test_cost_line_names_the_scope_and_cap() -> None:
    rt = build_runtime(settings(), project="p")
    line = cost_line(rt.cost)
    assert line.startswith("Cost: $0.000000 (this command: no calls; session $")
    assert "of $2.50" in line


def test_ab_deps_give_the_verify_layer_a_gate_baseline_cache(tmp_path: Path) -> None:
    from shipharness.ab.runtime import Runtime
    from shipharness.config import Settings

    settings = Settings(_env_file=None, runs_dir=tmp_path / "runs")
    runtime = Runtime(
        settings=settings,
        cost=None,  # type: ignore[arg-type]
        tracer=None,  # type: ignore[arg-type]
        client_factory=None,  # type: ignore[arg-type]
        sandbox_factory=None,  # type: ignore[arg-type]
        referee_sandbox_factory=None,  # type: ignore[arg-type]
        reviewer=None,
        sandboxed=False,
        policy_summary="",
    )
    deps = runtime.ab_deps("m1-s4-start", reviewer=False)
    assert deps.harness_kwargs["gate_baseline_cache_dir"] == tmp_path / "cache" / "gate-baseline"
