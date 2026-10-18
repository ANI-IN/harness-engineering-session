"""Shared plumbing for the in-process HTTP checks (R1-R5): a seeded app, a client, probe data."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from shipharness.checks.adapter import TenantAppAdapter, load_adapter
from shipharness.checks.base import CheckContext, Finding
from shipharness.checks.discovery import Endpoint, discover_endpoints
from shipharness.checks.payloads import Payloads, fill_path

_METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


def adapter_for(ctx: CheckContext) -> TenantAppAdapter:
    return load_adapter(ctx.params.get("adapter"))


@dataclass
class Target:
    """One freshly seeded build under test."""

    adapter: TenantAppAdapter
    app: Any
    client: TestClient
    payloads: Payloads
    endpoints: list[Endpoint]
    db_path: Path
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    def send(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return self.client.request(method, path, json=body, headers=headers or {}, params=params)

    def body(self, endpoint: Endpoint, ids: dict[str, int]) -> Any:
        return self.payloads.body(endpoint, ids, self.overrides)


@contextmanager
def open_target(build_dir: Path, ctx: CheckContext) -> Iterator[Target]:
    adapter = adapter_for(ctx)
    with tempfile.TemporaryDirectory(prefix="shipharness-", ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "probe.db"
        app = adapter.create_app(build_dir, db_path)
        overrides = adapter.body_overrides() if hasattr(adapter, "body_overrides") else {}
        target = Target(
            adapter=adapter,
            app=app,
            client=TestClient(app, raise_server_exceptions=False),
            payloads=Payloads(app.openapi()),
            endpoints=ordered(discover_endpoints(app)),
            db_path=db_path,
            overrides=overrides,
        )
        try:
            yield target
        finally:
            target.client.close()
            _dispose(app)


def _dispose(app: Any) -> None:
    factory = getattr(getattr(app, "state", None), "session_factory", None)
    bind = getattr(factory, "kw", {}).get("bind") if factory is not None else None
    if bind is not None:
        bind.dispose()


def ordered(endpoints: list[Endpoint]) -> list[Endpoint]:
    """Reads, then writes; deletes last and deepest first, so earlier probes find their data."""

    def key(e: Endpoint) -> tuple[int, int, str]:
        depth = -e.path.count("/") if e.method == "DELETE" else 0
        return (_METHOD_ORDER.get(e.method, 5), depth, e.path)

    return sorted(endpoints, key=key)


def path_for(endpoint: Endpoint, ids: dict[str, int]) -> str:
    return fill_path(endpoint.path, ids)


def json_body(response: Any) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def excerpt(response: Any, limit: int = 160) -> str:
    text = response.text if hasattr(response, "text") else str(response)
    return text[:limit].replace("\n", " ")


def table_counts(db_path: Path, ignore: frozenset[str]) -> dict[str, int]:
    """Row count per table of a SQLite database, skipping bookkeeping tables."""
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        names = [
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if not row[0].startswith("sqlite_") and row[0] not in ignore
        ]
        return {name: con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}
    finally:
        con.close()


def apply_exemptions(findings: list[Finding], ctx: CheckContext) -> list[Finding]:
    """Exempt findings stay visible as `info` and do not count."""
    out = []
    for f in findings:
        if f.counted and ctx.is_exempt(f.rule, f.endpoint):
            f = f.model_copy(
                update={"severity": "info", "detail": f"exempt at {ctx.checkpoint}: {f.detail}"}
            )
        out.append(f)
    return out
