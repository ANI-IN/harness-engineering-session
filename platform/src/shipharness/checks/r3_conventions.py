"""R3 API conventions: list and error envelopes, cursor pagination, no server errors.

Two parts, both in process:

1. Schemathesis (in-process ASGI, `schemathesis.openapi.from_asgi`) generates requests for every
   operation in the OpenAPI document with a fixed Hypothesis seed (`ctx.seed`, recorded in the
   result). Each response is checked for server errors, conformance to the documented response
   schema (string formats are not validated: SQLite returns naive timestamps), and the envelopes.
   Integers beyond SQLite's 64-bit range are not generated (see SQLITE_INT_MAX).
2. Direct probes: every GET as the home org's admin with the home org's ids, and every endpoint
   without credentials, so the envelope assertions do not depend on what the fuzzer generated.

Envelopes (HANDBOOK R3): errors are exactly {"error": {"code": str, "message": str}}; a GET that
returns a JSON array is a "bare_array"; an object with "items" must also carry "next_cursor";
list endpoints never take `offset` or `page` parameters.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from shipharness.checks._http import Target, apply_exemptions, json_body, open_target, path_for
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check

DEFAULT_MAX_EXAMPLES = 10
_OFFSET_PARAMS = frozenset({"offset", "page"})
# Integers outside SQLite's signed 64-bit range are not generated: the demo store cannot hold them
# and every unbounded id parameter would fail the same way, which says nothing about R3.
SQLITE_INT_MAX = 2**63 - 1


def envelope_problems(method: str, status: int, body: Any) -> list[tuple[str, str]]:
    """(detail_key, detail) for every envelope rule a response breaks."""
    problems: list[tuple[str, str]] = []
    if status >= 400:
        error = body.get("error") if isinstance(body, dict) else None
        well_formed = (
            isinstance(body, dict)
            and set(body) == {"error"}
            and isinstance(error, dict)
            and set(error) == {"code", "message"}
            and all(isinstance(error[k], str) for k in ("code", "message"))
        )
        if not well_formed:
            problems.append(("error_envelope", f"{status} body is not the error envelope"))
    elif method == "GET" and 200 <= status < 300:
        if isinstance(body, list):
            problems.append(("bare_array", "list returned as a bare JSON array"))
        elif (
            isinstance(body, dict)
            and "items" in body
            and ("next_cursor" not in body or not isinstance(body["items"], list))
        ):
            problems.append(("list_envelope", "list object lacks items/next_cursor"))
    return problems


class _Collector:
    """One finding per (endpoint, detail_key), keeping the first example."""

    def __init__(self) -> None:
        self.found: dict[tuple[str, str], Finding] = {}
        self.probes = 0

    def add(self, endpoint: str, key: str, detail: str) -> None:
        if (endpoint, key) not in self.found:
            self.found[(endpoint, key)] = Finding(
                rule="R3", severity="violation", endpoint=endpoint, detail_key=key, detail=detail
            )

    def response(self, endpoint: str, method: str, path: str, status: int, body: Any) -> None:
        self.probes += 1
        for key, detail in envelope_problems(method, status, body):
            self.add(endpoint, key, f"{method} {path}: {detail}; got {str(body)[:120]}")


def _too_big(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return not -SQLITE_INT_MAX - 1 <= value <= SQLITE_INT_MAX
    if isinstance(value, dict):
        return any(_too_big(v) for v in value.values())
    if isinstance(value, list | tuple):
        return any(_too_big(v) for v in value)
    return False


def _failure_key(failure: BaseException) -> str:
    name = type(failure).__name__
    return {"ServerError": "server_error", "JsonSchemaError": "schema"}.get(name, name.lower())


def fuzz(t: Target, ctx: CheckContext, found: _Collector) -> None:
    import hypothesis
    import schemathesis
    from hypothesis import HealthCheck, Phase, given, settings
    from schemathesis.checks import not_a_server_error
    from schemathesis.specs.openapi.checks import response_schema_conformance

    home, _other = t.adapter.orgs()
    headers = t.adapter.headers(home, "admin")
    config = schemathesis.Config.from_dict(
        {"checks": {"response_schema_conformance": {"validate-formats": False}}}
    )
    schema = schemathesis.openapi.from_asgi("/openapi.json", t.app, config=config)
    operations = [result.ok() for result in schema.get_all_operations()]
    max_examples = int(ctx.params.get("r3_max_examples", DEFAULT_MAX_EXAMPLES))

    def make_test(op: Any) -> Any:
        label = f"{op.method.upper()} {op.path}"

        @hypothesis.seed(ctx.seed)
        @settings(
            max_examples=max_examples,
            database=None,
            deadline=None,
            suppress_health_check=list(HealthCheck),
            phases=[Phase.explicit, Phase.generate],
        )
        @given(op.as_strategy())
        def case_test(case: Any) -> None:
            sent = [case.path_parameters, case.query, case.body]
            hypothesis.assume(not any(_too_big(v) for v in sent))
            try:
                response = case.call(headers=headers)
            except Exception as exc:  # the app raised instead of answering
                found.add(label, "server_error", f"request raised {type(exc).__name__}: {exc}")
                return
            try:
                case.validate_response(
                    response, checks=[not_a_server_error, response_schema_conformance]
                )
            except BaseExceptionGroup as group:
                for failure in group.exceptions:
                    title = getattr(failure, "title", type(failure).__name__)
                    found.add(label, _failure_key(failure), f"{title} ({response.status_code})")
            status, body = response.status_code, json_body(response)
            found.response(label, op.method.upper(), case.formatted_path, status, body)

        return case_test

    for done, op in enumerate(operations, start=1):
        make_test(op)()
        ctx.progress(done, len(operations), f"House rule 3 operations {done}/{len(operations)}")


def direct(t: Target, found: _Collector) -> None:
    home, _other = t.adapter.orgs()
    ids, admin = t.adapter.ids(home), t.adapter.headers(home, "admin")
    paths = t.app.openapi().get("paths", {})
    for e in t.endpoints:
        op = paths.get(e.path, {}).get(e.method.lower(), {})
        names = {p.get("name") for p in op.get("parameters", []) if p.get("in") == "query"}
        if e.method == "GET" and names & _OFFSET_PARAMS:
            found.add(e.label, "offset_pagination", f"query parameters {sorted(names)}")
        path = path_for(e, ids)
        if e.method == "GET":
            response = t.send("GET", path, headers=admin, params=t.payloads.query(e, ids))
            found.response(e.label, "GET", path, response.status_code, json_body(response))
        response = t.send(e.method, path, t.body(e, ids))
        found.response(e.label, e.method, path, response.status_code, json_body(response))


@register_check
class ConventionsCheck:
    name = "r3_conventions"
    rule = "R3"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        found = _Collector()
        with open_target(build_dir, ctx) as t:
            direct(t, found)
            fuzz(t, ctx, found)
        findings = apply_exemptions(list(found.found.values()), ctx)
        return make_result(
            self.name, findings, total_probes=found.probes, started=started, seed=ctx.seed
        )
