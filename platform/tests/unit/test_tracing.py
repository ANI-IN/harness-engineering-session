from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import Settings
from shipharness.log_setup import REDACTED
from shipharness.tracing import (
    LangSmithTracer,
    NullTracer,
    make_tracer,
    scrub_inputs,
    write_export,
)

from .fakes import fake_langsmith_key, fake_openai_key


def test_null_tracer_contexts_nest_and_have_no_url() -> None:
    tracer = NullTracer()
    with tracer.agent_run("agent_run", {"run_id": "r-1"}) as root:
        with tracer.child("phase:build", "chain") as child:
            child.set_outputs({"ok": True})
        assert tracer.url(root) is None


def test_scrub_inputs_removes_credentials_at_any_depth() -> None:
    key = fake_openai_key()
    out = scrub_inputs(
        {"api_key": key, "nested": {"authorization": f"Bearer {key}"}, "note": f"used {key}"}
    )
    text = json.dumps(out)
    assert key not in text
    assert out["api_key"] == REDACTED
    assert out["nested"]["authorization"] == REDACTED


def test_make_tracer_without_key_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    settings = Settings(_env_file=None, langsmith_tracing=True)
    assert isinstance(make_tracer(settings, "shipharness-test"), NullTracer)


def test_make_tracer_with_tracing_off_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", fake_langsmith_key())
    settings = Settings(_env_file=None, langsmith_tracing=False)
    assert isinstance(make_tracer(settings, "shipharness-test"), NullTracer)


def test_langsmith_tracer_scrubs_inputs_and_sets_project() -> None:
    calls: list[dict[str, Any]] = []

    class FakeRun:
        def get_url(self) -> str:
            return "https://smith.example/r/1"

        def end(self, **_kw: Any) -> None:
            return None

        def add_metadata(self, _md: dict[str, Any]) -> None:
            return None

    @contextmanager
    def fake_trace(name: str, run_type: str = "chain", **kwargs: Any):  # type: ignore[no-untyped-def]
        calls.append({"name": name, "run_type": run_type, **kwargs})
        yield FakeRun()

    tracer = LangSmithTracer(client=object(), project_name="proj-x", trace_fn=fake_trace)
    key = fake_openai_key()
    with tracer.agent_run("agent_run", {"run_id": "r-1", "api_key": key}, tags=["section-1"]) as h:
        assert tracer.url(h) == "https://smith.example/r/1"
    [call] = calls
    assert call["project_name"] == "proj-x"
    assert call["tags"] == ["section-1"]
    assert key not in json.dumps(call["inputs"]) + json.dumps(call["metadata"])


def test_langsmith_tracer_enables_tracing_even_without_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LangSmith posts nothing unless tracing is enabled; Settings does not export env vars."""
    from langsmith import utils

    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING_V2"):
        monkeypatch.delenv(name, raising=False)
    seen: list[bool] = []

    @contextmanager
    def fake_trace(name: str, run_type: str = "chain", **kwargs: Any):  # type: ignore[no-untyped-def]
        seen.append(utils.tracing_is_enabled())
        yield object()

    tracer = LangSmithTracer(client=object(), project_name="p", trace_fn=fake_trace)
    with tracer.agent_run("agent_run", {"run_id": "r-1"}), tracer.child("phase:build", "chain"):
        pass
    assert seen == [True, True]


def test_write_export_writes_sorted_json(tmp_path: Path) -> None:
    path = write_export("scores", "r-1", {"b": 1, "a": 2}, tmp_path)
    assert path == tmp_path / "scores" / "r-1.json"
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert list(json.loads(text)) == ["a", "b"]


def test_write_export_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_export("misc", "x", {}, tmp_path)  # type: ignore[arg-type]
