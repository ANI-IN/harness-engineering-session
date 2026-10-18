"""Tracing to LangSmith. Keys and credentials never reach a trace (§20)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol

import structlog

from shipharness.config import Settings
from shipharness.log_setup import redact

log = structlog.get_logger(__name__)


def scrub_inputs(data: Mapping[str, Any]) -> dict[str, Any]:
    """Remove credential fields and key-shaped strings before anything is sent to LangSmith."""
    return dict(redact(dict(data)))


class RunHandle:
    """A traced run. Wraps a LangSmith RunTree, or nothing for NullTracer."""

    def __init__(self, run_tree: Any | None = None) -> None:
        self.run_tree = run_tree

    def set_outputs(self, outputs: Mapping[str, Any]) -> None:
        if self.run_tree is None:
            return
        add = getattr(self.run_tree, "add_outputs", None)
        if callable(add):
            add(scrub_inputs(outputs))

    def add_metadata(self, metadata: Mapping[str, Any]) -> None:
        if self.run_tree is None:
            return
        add = getattr(self.run_tree, "add_metadata", None)
        if callable(add):
            add(scrub_inputs(metadata))


class Tracer(Protocol):
    def agent_run(
        self,
        name: str,
        metadata: Mapping[str, Any],
        tags: list[str] | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager[RunHandle]: ...

    def child(
        self, name: str, run_type: str, inputs: Mapping[str, Any] | None = None, **metadata: Any
    ) -> AbstractContextManager[RunHandle]: ...

    def url(self, handle: RunHandle) -> str | None: ...

    def wrap_openai(self, client: Any) -> Any: ...


class NullTracer:
    """Used when tracing is off or no LangSmith key is configured."""

    @contextmanager
    def agent_run(
        self,
        name: str,
        metadata: Mapping[str, Any],
        tags: list[str] | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> Iterator[RunHandle]:
        yield RunHandle()

    @contextmanager
    def child(
        self, name: str, run_type: str, inputs: Mapping[str, Any] | None = None, **metadata: Any
    ) -> Iterator[RunHandle]:
        yield RunHandle()

    def url(self, handle: RunHandle) -> str | None:
        return None

    def wrap_openai(self, client: Any) -> Any:
        return client


class LangSmithTracer:
    """Nested runs via langsmith `trace`; nesting follows the call stack (context variables)."""

    def __init__(
        self, client: Any, project_name: str, trace_fn: Callable[..., Any] | None = None
    ) -> None:
        if trace_fn is None:
            from langsmith import trace as trace_fn  # local import keeps NullTracer dependency-free
        self.client = client
        self.project_name = project_name
        self._trace = trace_fn

    @contextmanager
    def agent_run(
        self,
        name: str,
        metadata: Mapping[str, Any],
        tags: list[str] | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> Iterator[RunHandle]:
        from langsmith import tracing_context

        # LangSmith posts nothing unless tracing is enabled, and Settings reads .env without
        # exporting LANGSMITH_TRACING, so enable it explicitly for everything inside this run.
        with (
            tracing_context(enabled=True, project_name=self.project_name, client=self.client),
            self._trace(
                name,
                "chain",
                inputs=scrub_inputs(inputs or metadata),
                metadata=scrub_inputs(metadata),
                tags=list(tags or []),
                project_name=self.project_name,
                client=self.client,
            ) as run_tree,
        ):
            yield RunHandle(run_tree)

    @contextmanager
    def child(
        self, name: str, run_type: str, inputs: Mapping[str, Any] | None = None, **metadata: Any
    ) -> Iterator[RunHandle]:
        with self._trace(
            name,
            run_type,
            inputs=scrub_inputs(inputs or {}),
            metadata=scrub_inputs(metadata),
            project_name=self.project_name,
            client=self.client,
        ) as run_tree:
            yield RunHandle(run_tree)

    def url(self, handle: RunHandle) -> str | None:
        if handle.run_tree is None:
            return None
        try:
            return str(handle.run_tree.get_url())
        except Exception:  # noqa: BLE001 - a missing link must never break a run
            return None

    def wrap_openai(self, client: Any) -> Any:
        from langsmith.wrappers import wrap_openai

        return wrap_openai(client)


def make_tracer(settings: Settings, project_name: str) -> Tracer:
    """LangSmithTracer when tracing is on and a key is set; NullTracer otherwise."""
    if not settings.langsmith_tracing:
        return NullTracer()
    if settings.langsmith_api_key is None:
        log.warning("langsmith tracing disabled: LANGSMITH_API_KEY is missing")
        return NullTracer()
    from langsmith import Client

    client = Client(
        api_key=settings.langsmith_api_key.get_secret_value(),
        api_url=settings.langsmith_endpoint,
    )
    return LangSmithTracer(client=client, project_name=project_name)
